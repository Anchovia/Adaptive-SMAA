"""Convert San Miguel 2.1 low-poly OBJ to an external textured CMAA2 cache.

The original asset and generated cache remain outside Git. The converter
processes one OBJ object at a time, preserves material boundaries, deduplicates
position/normal/UV corner tuples, and records relative diffuse texture paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import sys
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from prepare_san_miguel_scene import (
    EXPECTED_LOW_POLY_OBJ_SHA256,
    sha256_file,
)


CACHE_MAGIC = b"SMAASM1\0"
CACHE_VERSION = 1
CACHE_HEADER = struct.Struct("<8sIIIIQQ6f")
MATERIAL_HEADER = struct.Struct("<IIII5f")
CHUNK_HEADER = struct.Struct("<IIII")


@dataclass(frozen=True)
class Material:
    name: str
    diffuse: tuple[float, float, float, float]
    diffuse_texture: str
    alpha_test: bool
    specular_power: float


@dataclass
class MeshChunk:
    material_index: int
    positions: array = field(default_factory=lambda: array("f"))
    normals: array = field(default_factory=lambda: array("f"))
    texcoords: array = field(default_factory=lambda: array("f"))
    indices: array = field(default_factory=lambda: array("I"))
    vertex_lookup: dict[tuple[int, int, int], int] = field(default_factory=dict)

    def add_corner(
        self,
        position_index: int,
        texture_index: int,
        normal_index: int,
        source_positions: array,
        source_texcoords: array,
        source_normals: array,
        center_x: float,
        center_z: float,
        ground_y: float,
    ) -> int:
        key = (position_index, texture_index, normal_index)
        cached = self.vertex_lookup.get(key)
        if cached is not None:
            return cached

        p = position_index * 3
        n = normal_index * 3
        px, py, pz = source_positions[p : p + 3]
        nx, ny, nz = source_normals[n : n + 3]
        # Proper +90 degree X rotation: source Y-up -> engine Z-up.
        self.positions.extend((px - center_x, -(pz - center_z), py - ground_y))
        self.normals.extend((nx, -nz, ny))
        if texture_index >= 0:
            t = texture_index * 2
            u, v = source_texcoords[t : t + 2]
            self.texcoords.extend((u, 1.0 - v))
        else:
            self.texcoords.extend((0.0, 0.0))
        result = len(self.positions) // 3 - 1
        self.vertex_lookup[key] = result
        return result


@dataclass
class ObjectState:
    name: str
    position_base: int
    texcoord_base: int
    normal_base: int
    positions: array = field(default_factory=lambda: array("f"))
    texcoords: array = field(default_factory=lambda: array("f"))
    normals: array = field(default_factory=lambda: array("f"))
    chunks: dict[int, MeshChunk] = field(default_factory=dict)
    face_count: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert San Miguel low-poly OBJ to a CMAA2 .smaasm cache."
    )
    parser.add_argument(
        "source_root",
        type=Path,
        help="SanMiguel directory containing SourceLowPoly and the ZIP.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="External .smaasm cache path, normally inside PreparedLowPoly.",
    )
    parser.add_argument(
        "--source-manifest",
        type=Path,
        required=True,
        help="Validated san_miguel_source_manifest.json path.",
    )
    parser.add_argument("--skip-hash", action="store_true")
    return parser.parse_args()


def parse_mtl(path: Path, alpha_textures: set[str]) -> list[Material]:
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    with path.open("r", encoding="utf-8-sig", errors="strict") as stream:
        for source_line in stream:
            line = source_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            command = parts[0]
            value = parts[1] if len(parts) > 1 else ""
            if command == "newmtl":
                current = {
                    "name": value,
                    "Kd": (0.7, 0.7, 0.7),
                    "Ns": 16.0,
                    "map_Kd": "",
                }
                records.append(current)
            elif current is None:
                raise RuntimeError(f"MTL property before newmtl: {line!r}")
            elif command == "Kd":
                values = tuple(float(component) for component in value.split())
                if len(values) != 3:
                    raise RuntimeError(f"Invalid Kd: {line!r}")
                current["Kd"] = values
            elif command == "Ns":
                current["Ns"] = float(value)
            elif command == "map_Kd":
                current["map_Kd"] = value.replace("\\", "/")

    materials: list[Material] = []
    names: set[str] = set()
    for record in records:
        name = str(record["name"])
        if not name or name in names:
            raise RuntimeError(f"Invalid or duplicate material {name!r}")
        names.add(name)
        kd = tuple(record["Kd"])
        texture = str(record["map_Kd"])
        specular_power = float(record["Ns"])
        if not math.isfinite(specular_power):
            raise RuntimeError(f"Non-finite Ns in {name}")
        materials.append(
            Material(
                name,
                (float(kd[0]), float(kd[1]), float(kd[2]), 1.0),
                texture,
                texture.lower() in alpha_textures,
                specular_power,
            )
        )
    if not materials:
        raise RuntimeError(f"No materials found in {path}")
    return sorted(materials, key=lambda material: material.name)


def parse_float_values(line: bytes, count: int) -> tuple[float, ...]:
    parts = line.split()
    if len(parts) < count + 1:
        raise RuntimeError(f"Malformed numeric OBJ line: {line[:120]!r}")
    return tuple(float(parts[index]) for index in range(1, count + 1))


def parse_corner(token: bytes) -> tuple[int, int, int]:
    parts = token.split(b"/")
    if len(parts) == 3 and parts[0] and parts[2]:
        return int(parts[0]), int(parts[1]) if parts[1] else 0, int(parts[2])
    raise RuntimeError(f"Expected position/uv/normal OBJ corner, got {token!r}")


def resolve_index(index: int, global_count: int, local_base: int, local_count: int) -> int:
    if index == 0:
        return -1
    global_index = index - 1 if index > 0 else global_count + index
    local_index = global_index - local_base
    if local_index < 0 or local_index >= local_count:
        raise RuntimeError(
            f"OBJ index {index} outside object-local data: "
            f"resolved={local_index}, count={local_count}"
        )
    return local_index


def write_materials(stream: BinaryIO, materials: list[Material]) -> None:
    for material in materials:
        name = material.name.encode("utf-8")
        texture = material.diffuse_texture.encode("utf-8")
        stream.write(
            MATERIAL_HEADER.pack(
                len(name),
                len(texture),
                1 if material.alpha_test else 0,
                0,
                *material.diffuse,
                material.specular_power,
            )
        )
        stream.write(name)
        stream.write(texture)


def convert_obj(
    obj_path: Path,
    output_path: Path,
    materials: list[Material],
    bounds: list[float],
) -> dict[str, object]:
    material_indices = {material.name: index for index, material in enumerate(materials)}
    center_x = (bounds[0] + bounds[3]) * 0.5
    center_z = (bounds[2] + bounds[5]) * 0.5
    ground_y = bounds[1]
    engine_bounds = (
        bounds[0] - center_x,
        -(bounds[5] - center_z),
        0.0,
        bounds[3] - center_x,
        -(bounds[2] - center_z),
        bounds[4] - ground_y,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    total_vertices = 0
    total_indices = 0
    chunk_count = 0
    object_count = 0
    global_positions = 0
    global_texcoords = 0
    global_normals = 0
    current: ObjectState | None = None
    current_material = -1

    with temporary.open("w+b") as destination:
        destination.write(b"\0" * CACHE_HEADER.size)
        write_materials(destination, materials)

        def finalize_object() -> None:
            nonlocal current, total_vertices, total_indices, chunk_count, object_count
            if current is None:
                return
            if current.face_count == 0:
                current = None
                return
            object_count += 1
            for material_index in sorted(current.chunks):
                chunk = current.chunks[material_index]
                name = current.name.encode("utf-8")
                vertex_count = len(chunk.positions) // 3
                index_count = len(chunk.indices)
                destination.write(
                    CHUNK_HEADER.pack(
                        len(name), material_index, vertex_count, index_count
                    )
                )
                destination.write(name)
                chunk.positions.tofile(destination)
                chunk.normals.tofile(destination)
                chunk.texcoords.tofile(destination)
                chunk.indices.tofile(destination)
                total_vertices += vertex_count
                total_indices += index_count
                chunk_count += 1
            if object_count % 100 == 0:
                print(
                    f"objects={object_count:,}, chunks={chunk_count:,}, "
                    f"triangles={total_indices // 3:,}"
                )
            current = None

        with obj_path.open("rb", buffering=8 * 1024 * 1024) as source:
            for line_number, line in enumerate(source, start=1):
                if line.startswith(b"o "):
                    finalize_object()
                    name = line[2:].strip().decode("utf-8", errors="strict")
                    current = ObjectState(
                        name or f"Object_{object_count}",
                        global_positions,
                        global_texcoords,
                        global_normals,
                    )
                    current_material = -1
                elif line.startswith(b"v "):
                    if current is None:
                        raise RuntimeError(f"Vertex before object at line {line_number}")
                    if current.face_count:
                        raise RuntimeError(f"Vertex after face at line {line_number}")
                    current.positions.extend(parse_float_values(line, 3))
                    global_positions += 1
                elif line.startswith(b"vt "):
                    if current is None:
                        raise RuntimeError(f"UV before object at line {line_number}")
                    if current.face_count:
                        raise RuntimeError(f"UV after face at line {line_number}")
                    current.texcoords.extend(parse_float_values(line, 2))
                    global_texcoords += 1
                elif line.startswith(b"vn "):
                    if current is None:
                        raise RuntimeError(f"Normal before object at line {line_number}")
                    if current.face_count:
                        raise RuntimeError(f"Normal after face at line {line_number}")
                    current.normals.extend(parse_float_values(line, 3))
                    global_normals += 1
                elif line.startswith(b"usemtl "):
                    material_name = line[7:].strip().decode("utf-8", errors="strict")
                    if material_name not in material_indices:
                        raise RuntimeError(
                            f"Unknown material {material_name!r} at line {line_number}"
                        )
                    current_material = material_indices[material_name]
                elif line.startswith(b"f "):
                    if current is None or current_material < 0:
                        raise RuntimeError(f"Face without object/material at line {line_number}")
                    chunk = current.chunks.setdefault(
                        current_material, MeshChunk(current_material)
                    )
                    corners: list[int] = []
                    for token in line.split()[1:]:
                        position_obj, texture_obj, normal_obj = parse_corner(token)
                        position_index = resolve_index(
                            position_obj,
                            global_positions,
                            current.position_base,
                            len(current.positions) // 3,
                        )
                        texture_index = resolve_index(
                            texture_obj,
                            global_texcoords,
                            current.texcoord_base,
                            len(current.texcoords) // 2,
                        )
                        normal_index = resolve_index(
                            normal_obj,
                            global_normals,
                            current.normal_base,
                            len(current.normals) // 3,
                        )
                        corners.append(
                            chunk.add_corner(
                                position_index,
                                texture_index,
                                normal_index,
                                current.positions,
                                current.texcoords,
                                current.normals,
                                center_x,
                                center_z,
                                ground_y,
                            )
                        )
                    if len(corners) < 3:
                        raise RuntimeError(f"Malformed face at line {line_number}")
                    for corner_index in range(1, len(corners) - 1):
                        chunk.indices.extend(
                            (corners[0], corners[corner_index], corners[corner_index + 1])
                        )
                    current.face_count += 1
        finalize_object()

        if total_indices // 3 != 5_617_451:
            raise RuntimeError(
                f"Triangle count mismatch: {total_indices // 3:,} != 5,617,451"
            )
        destination.seek(0)
        destination.write(
            CACHE_HEADER.pack(
                CACHE_MAGIC,
                CACHE_VERSION,
                len(materials),
                chunk_count,
                0,
                total_vertices,
                total_indices,
                *engine_bounds,
            )
        )
    os.replace(temporary, output_path)
    return {
        "schema": "smaa-san-miguel-textured-cache-v1",
        "cache_path": output_path.name,
        "cache_bytes": output_path.stat().st_size,
        "cache_sha256": sha256_file(output_path),
        "materials": len(materials),
        "alpha_test_materials": sum(material.alpha_test for material in materials),
        "objects": object_count,
        "chunks": chunk_count,
        "vertices": total_vertices,
        "indices": total_indices,
        "triangles": total_indices // 3,
        "bounds_min": list(engine_bounds[:3]),
        "bounds_max": list(engine_bounds[3:]),
    }


def main() -> None:
    args = parse_args()
    source_root = args.source_root.resolve()
    source_dir = source_root / "SourceLowPoly"
    obj_path = source_dir / "san-miguel-low-poly.obj"
    mtl_path = source_dir / "san-miguel-low-poly.mtl"
    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    if manifest.get("schema") != "smaa-san-miguel-source-manifest-v1":
        raise RuntimeError("Unexpected San Miguel source manifest schema")
    if not args.skip_hash:
        obj_hash = sha256_file(obj_path)
        if obj_hash != EXPECTED_LOW_POLY_OBJ_SHA256:
            raise RuntimeError(f"Unexpected low-poly OBJ SHA-256: {obj_hash}")
    texture_data = manifest["textures"]
    alpha_textures = {
        str(path).lower() for path in texture_data["meaningful_alpha_textures"]
    }
    materials = parse_mtl(mtl_path, alpha_textures)
    geometry = manifest["low_poly_geometry"]
    bounds = list(geometry["bounds_min"]) + list(geometry["bounds_max"])
    result = convert_obj(obj_path, args.output.resolve(), materials, bounds)
    result["source_obj_sha256"] = EXPECTED_LOW_POLY_OBJ_SHA256
    result_path = args.output.with_suffix(".manifest.json")
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"PASS: {result['objects']:,} objects, {result['chunks']:,} chunks, "
        f"{result['triangles']:,} triangles, "
        f"{result['cache_bytes'] / (1024 * 1024):.2f} MiB"
    )
    print(args.output.resolve())
    print(result_path.resolve())


if __name__ == "__main__":
    if sys.byteorder != "little":
        raise RuntimeError("San Miguel cache writer requires a little-endian host")
    main()
