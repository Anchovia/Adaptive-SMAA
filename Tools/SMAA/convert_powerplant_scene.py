"""Convert selected UNC Power Plant OBJ sections to compact SMAA preview caches.

The original 780 MiB OBJ is intentionally stored outside Git.  CMAA2 has no
enabled general-purpose OBJ importer, so this tool performs a deterministic
offline conversion of selected ``secN`` groups.  The resulting ``.smaapp``
files also remain outside Git and are consumed only by the research preview
scene.

Cache format v1 is little-endian and deliberately simple:

* 64-byte file header (magic, version, section/chunk counts, totals, AABB)
* UTF-8 section name
* for every material chunk: metadata, UTF-8 name, float3 positions,
  float3 normals, uint32 triangle indices

Materials use the source MTL ``Kd`` colour but are rendered opaque.  Source Y
is mapped to engine Z with a proper rotation (x, y, z) -> (x, -z, y), and each
section is centred and uniformly normalized to ``--target-extent`` units.
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

from prepare_powerplant_scene import EXPECTED_OBJ_SHA256, sha256_file


CACHE_MAGIC = b"SMAAPP1\0"
CACHE_VERSION = 1
CACHE_HEADER = struct.Struct("<8sIIIIQQ6f")
CHUNK_HEADER = struct.Struct("<I4fII")


@dataclass(frozen=True)
class Material:
    name: str
    diffuse: tuple[float, float, float]


@dataclass
class MeshChunk:
    material: Material
    positions: array = field(default_factory=lambda: array("f"))
    normals: array = field(default_factory=lambda: array("f"))
    indices: array = field(default_factory=lambda: array("I"))
    vertex_lookup: dict[tuple[int, int], int] = field(default_factory=dict)

    def add_corner(
        self,
        position_index: int,
        normal_index: int,
        source_positions: list[tuple[float, float, float]],
        source_normals: list[tuple[float, float, float]],
        centre: tuple[float, float, float],
        scale: float,
    ) -> int:
        key = (position_index, normal_index)
        cached = self.vertex_lookup.get(key)
        if cached is not None:
            return cached

        px, py, pz = source_positions[position_index]
        nx, ny, nz = source_normals[normal_index]
        cx, cy, cz = centre
        # Proper +90 degree X rotation: source Y-up -> engine Z-up.
        self.positions.extend(
            ((px - cx) * scale, -(pz - cz) * scale, (py - cy) * scale)
        )
        self.normals.extend((nx, -nz, ny))
        new_index = len(self.positions) // 3 - 1
        self.vertex_lookup[key] = new_index
        return new_index


@dataclass
class SelectedSection:
    name: str
    position_base: int
    normal_base: int
    positions: list[tuple[float, float, float]] = field(default_factory=list)
    normals: list[tuple[float, float, float]] = field(default_factory=list)
    chunks_by_material: dict[str, MeshChunk] = field(default_factory=dict)
    centre: tuple[float, float, float] | None = None
    scale: float | None = None
    bounds: tuple[float, ...] | None = None
    face_count: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert selected Power Plant OBJ groups to CMAA2 preview caches."
    )
    parser.add_argument(
        "source_root",
        type=Path,
        help="Directory containing Source/powerplant.obj and powerplant.mtl.",
    )
    parser.add_argument(
        "--cache-output",
        type=Path,
        required=True,
        help="External output directory for .smaapp caches and cache manifest.",
    )
    parser.add_argument(
        "--sections",
        required=True,
        help="Comma-separated section names, for example sec14,sec16.",
    )
    parser.add_argument(
        "--target-extent",
        type=float,
        default=20.0,
        help="Uniformly normalize each selected section's longest AABB extent.",
    )
    parser.add_argument(
        "--skip-hash",
        action="store_true",
        help="Skip source OBJ SHA-256 validation during quick local iterations.",
    )
    return parser.parse_args()


def parse_mtl(path: Path) -> dict[str, Material]:
    result: dict[str, Material] = {}
    current_name: str | None = None
    current_diffuse = (0.7, 0.7, 0.7)
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            parts = line.split()
            if not parts or parts[0].startswith("#"):
                continue
            if parts[0] == "newmtl":
                if current_name is not None:
                    result[current_name] = Material(current_name, current_diffuse)
                if len(parts) != 2:
                    raise RuntimeError(f"Malformed newmtl line: {line.rstrip()}")
                current_name = parts[1]
                current_diffuse = (0.7, 0.7, 0.7)
            elif parts[0] == "Kd" and current_name is not None:
                if len(parts) != 4:
                    raise RuntimeError(f"Malformed Kd line: {line.rstrip()}")
                current_diffuse = tuple(float(value) for value in parts[1:4])
    if current_name is not None:
        result[current_name] = Material(current_name, current_diffuse)
    if not result:
        raise RuntimeError(f"No materials found in {path}")
    return result


def parse_float3(line: bytes) -> tuple[float, float, float]:
    parts = line.split()
    if len(parts) < 4:
        raise RuntimeError(f"Malformed float3 line: {line[:120]!r}")
    return float(parts[1]), float(parts[2]), float(parts[3])


def parse_corner(token: bytes) -> tuple[int, int]:
    parts = token.split(b"/")
    if len(parts) != 3 or not parts[0] or not parts[2]:
        raise RuntimeError(f"Expected position//normal OBJ corner, got {token!r}")
    return int(parts[0]), int(parts[2])


def resolve_index(index: int, global_count: int, section_base: int, local_count: int) -> int:
    global_index = index - 1 if index > 0 else global_count + index
    local_index = global_index - section_base
    if local_index < 0 or local_index >= local_count:
        raise RuntimeError(
            f"OBJ index {index} resolved outside current section: local={local_index}, "
            f"count={local_count}"
        )
    return local_index


def section_transform(
    positions: list[tuple[float, float, float]], target_extent: float
) -> tuple[tuple[float, float, float], float, tuple[float, ...]]:
    if not positions:
        raise RuntimeError("Selected section contains no positions")
    mins = [math.inf, math.inf, math.inf]
    maxs = [-math.inf, -math.inf, -math.inf]
    for position in positions:
        for axis, value in enumerate(position):
            mins[axis] = min(mins[axis], value)
            maxs[axis] = max(maxs[axis], value)
    centre = tuple((mins[axis] + maxs[axis]) * 0.5 for axis in range(3))
    longest_extent = max(maxs[axis] - mins[axis] for axis in range(3))
    if longest_extent <= 0.0 or not math.isfinite(longest_extent):
        raise RuntimeError(f"Invalid section extent: {longest_extent}")
    scale = target_extent / longest_extent

    # Cache-space AABB after (x, y, z) -> (x, -z, y).
    engine_min = (
        (mins[0] - centre[0]) * scale,
        -(maxs[2] - centre[2]) * scale,
        (mins[1] - centre[1]) * scale,
    )
    engine_max = (
        (maxs[0] - centre[0]) * scale,
        -(mins[2] - centre[2]) * scale,
        (maxs[1] - centre[1]) * scale,
    )
    return centre, scale, engine_min + engine_max


def add_face(
    section: SelectedSection,
    material_name: str,
    tokens: tuple[bytes, ...],
    materials: dict[str, Material],
    global_position_count: int,
    global_normal_count: int,
    target_extent: float,
) -> None:
    material = materials.get(material_name)
    if material is None:
        raise RuntimeError(f"Unknown material {material_name!r} in {section.name}")
    if section.centre is None:
        section.centre, section.scale, section.bounds = section_transform(
            section.positions, target_extent
        )
    assert section.scale is not None
    chunk = section.chunks_by_material.setdefault(material_name, MeshChunk(material))
    corners = [parse_corner(token) for token in tokens]
    if len(corners) < 3:
        raise RuntimeError(f"Malformed face with {len(corners)} corners")
    resolved: list[int] = []
    for position_obj_index, normal_obj_index in corners:
        position_index = resolve_index(
            position_obj_index,
            global_position_count,
            section.position_base,
            len(section.positions),
        )
        normal_index = resolve_index(
            normal_obj_index,
            global_normal_count,
            section.normal_base,
            len(section.normals),
        )
        resolved.append(
            chunk.add_corner(
                position_index,
                normal_index,
                section.positions,
                section.normals,
                section.centre,
                section.scale,
            )
        )
    for corner_index in range(1, len(resolved) - 1):
        chunk.indices.extend(
            (resolved[0], resolved[corner_index], resolved[corner_index + 1])
        )
    section.face_count += 1


def write_cache(
    path: Path,
    section_name: str,
    chunks: list[MeshChunk],
    bounds: tuple[float, ...],
) -> dict[str, object]:
    if sys.byteorder != "little":
        raise RuntimeError("Power Plant cache writer requires a little-endian host")
    section_bytes = section_name.encode("utf-8")
    total_vertices = sum(len(chunk.positions) // 3 for chunk in chunks)
    total_indices = sum(len(chunk.indices) for chunk in chunks)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("wb") as stream:
        stream.write(
            CACHE_HEADER.pack(
                CACHE_MAGIC,
                CACHE_VERSION,
                len(section_bytes),
                len(chunks),
                0,
                total_vertices,
                total_indices,
                *bounds,
            )
        )
        stream.write(section_bytes)
        for chunk in chunks:
            material_bytes = chunk.material.name.encode("utf-8")
            vertex_count = len(chunk.positions) // 3
            index_count = len(chunk.indices)
            if len(chunk.normals) != len(chunk.positions):
                raise RuntimeError(f"Position/normal mismatch in {chunk.material.name}")
            stream.write(
                CHUNK_HEADER.pack(
                    len(material_bytes),
                    *chunk.material.diffuse,
                    1.0,
                    vertex_count,
                    index_count,
                )
            )
            stream.write(material_bytes)
            chunk.positions.tofile(stream)
            chunk.normals.tofile(stream)
            chunk.indices.tofile(stream)
    os.replace(temporary_path, path)
    return {
        "section": section_name,
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "material_chunks": len(chunks),
        "vertices": total_vertices,
        "indices": total_indices,
        "triangles": total_indices // 3,
        "bounds_min": list(bounds[:3]),
        "bounds_max": list(bounds[3:]),
        "materials": [
            {
                "name": chunk.material.name,
                "diffuse": list(chunk.material.diffuse),
                "vertices": len(chunk.positions) // 3,
                "triangles": len(chunk.indices) // 3,
            }
            for chunk in chunks
        ],
    }


def convert_obj(
    stream: BinaryIO,
    selected_names: set[str],
    materials: dict[str, Material],
    output: Path,
    target_extent: float,
) -> list[dict[str, object]]:
    current: SelectedSection | None = None
    current_material = ""
    global_positions = 0
    global_normals = 0
    found: set[str] = set()
    cache_entries: list[dict[str, object]] = []

    def finalize(section: SelectedSection | None) -> None:
        if section is None:
            return
        chunks = [
            section.chunks_by_material[name]
            for name in sorted(section.chunks_by_material)
        ]
        if not chunks or section.bounds is None or section.scale is None:
            raise RuntimeError(f"Selected section {section.name} contains no faces")
        entry = write_cache(
            output / f"{section.name}.smaapp",
            section.name,
            chunks,
            section.bounds,
        )
        entry["normalization_scale"] = section.scale
        cache_entries.append(entry)
        found.add(section.name)
        print(
            f"WROTE {section.name}: {entry['triangles']:,} triangles, "
            f"{entry['vertices']:,} vertices, {entry['bytes'] / (1024 * 1024):.2f} MiB"
        )

    for source_line, line in enumerate(stream, start=1):
        if line.startswith(b"g "):
            finalize(current)
            name = line[2:].strip().decode("utf-8", errors="strict")
            current = (
                SelectedSection(name, global_positions, global_normals)
                if name in selected_names
                else None
            )
            current_material = ""
        elif line.startswith(b"v "):
            if current is not None:
                if current.face_count != 0:
                    raise RuntimeError(
                        f"Position after faces in selected section at source line {source_line}"
                    )
                current.positions.append(parse_float3(line))
            global_positions += 1
        elif line.startswith(b"vn "):
            if current is not None:
                if current.face_count != 0:
                    raise RuntimeError(
                        f"Normal after faces in selected section at source line {source_line}"
                    )
                current.normals.append(parse_float3(line))
            global_normals += 1
        elif line.startswith(b"usemtl "):
            current_material = line[7:].strip().decode("utf-8", errors="strict")
        elif line.startswith(b"f ") and current is not None:
            if not current_material:
                raise RuntimeError(f"Face before usemtl at source line {source_line}")
            add_face(
                current,
                current_material,
                tuple(line.split()[1:]),
                materials,
                global_positions,
                global_normals,
                target_extent,
            )
    finalize(current)

    missing = selected_names - found
    if missing:
        raise RuntimeError(f"Requested sections not found: {', '.join(sorted(missing))}")
    return sorted(cache_entries, key=lambda entry: str(entry["section"]))


def main() -> None:
    args = parse_args()
    if args.target_extent <= 0.0 or not math.isfinite(args.target_extent):
        raise ValueError("--target-extent must be a positive finite number")
    selected_names = {value.strip() for value in args.sections.split(",") if value.strip()}
    if not selected_names:
        raise ValueError("--sections must contain at least one section name")
    for name in selected_names:
        if not name.startswith("sec") or not name[3:].isdigit():
            raise ValueError(f"Invalid section name: {name!r}")

    source_root = args.source_root.resolve()
    obj_path = source_root / "Source" / "powerplant.obj"
    mtl_path = source_root / "Source" / "powerplant.mtl"
    for required_path in (obj_path, mtl_path):
        if not required_path.is_file():
            raise FileNotFoundError(required_path)
    obj_sha256 = sha256_file(obj_path)
    if not args.skip_hash and obj_sha256 != EXPECTED_OBJ_SHA256:
        raise RuntimeError(
            f"Unexpected OBJ SHA-256: {obj_sha256}; expected {EXPECTED_OBJ_SHA256}"
        )

    materials = parse_mtl(mtl_path)
    output = args.cache_output.resolve()
    with obj_path.open("rb", buffering=8 * 1024 * 1024) as stream:
        cache_entries = convert_obj(
            stream, selected_names, materials, output, args.target_extent
        )

    manifest = {
        "schema": "smaa-powerplant-preview-cache-v1",
        "source_obj_sha256": obj_sha256,
        "target_extent": args.target_extent,
        "coordinate_mapping": "source (x,y,z) -> engine (x,-z,y), centered and uniformly scaled",
        "material_policy": "source Kd, forced opaque; textures absent in source OBJ",
        "caches": cache_entries,
    }
    manifest_path = output / "powerplant_cache_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"PASS: converted {len(cache_entries)} section(s)")
    print(manifest_path)


if __name__ == "__main__":
    main()
