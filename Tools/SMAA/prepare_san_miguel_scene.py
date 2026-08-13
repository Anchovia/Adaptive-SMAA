"""Validate and characterize the external San Miguel 2.1 research scene.

The source archive and extracted OBJ/PNG assets remain outside Git.  This tool
streams the real-time low-poly OBJ, validates its MTL texture references, and
writes compact JSON/Markdown provenance manifests for reproducible SMAA tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter
from pathlib import Path

from PIL import Image


EXPECTED_ARCHIVE_SHA256 = (
    "85874077735808150e679b3c71d70a37a270cb8833f4911325aa1099da3f7d4a"
)
EXPECTED_LOW_POLY_OBJ_SHA256 = (
    "7142519da39589857d7dfcd3143a7b41bd444279f65dd5177c3adfad29a1ecc9"
)
SOURCE_URL = (
    "https://casual-effects.com/g3d/data10/research/model/San_Miguel/"
    "San_Miguel.zip"
)
ARCHIVE_PAGE = "https://casual-effects.com/data"
LICENSE = "free for research and educational use with attribution"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the external San Miguel low-poly OBJ and textures."
    )
    parser.add_argument(
        "source_root",
        type=Path,
        help=(
            "Directory containing San_Miguel.zip and SourceLowPoly/ with the "
            "extracted low-poly OBJ, MTL, license, and textures."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory for generated JSON and Korean Markdown manifests.",
    )
    parser.add_argument(
        "--skip-hash",
        action="store_true",
        help="Skip archive and extracted source SHA-256 calculation.",
    )
    parser.add_argument(
        "--prepared-output",
        type=Path,
        help=(
            "Optional external output directory for an import-ready tree. "
            "Large source files are hard-linked and a derived MTL marks "
            "diffuse textures with real alpha as alpha-tested materials."
        ),
    )
    return parser.parse_args()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def parse_mtl(path: Path) -> dict[str, object]:
    materials: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    map_counts: Counter[str] = Counter()
    referenced_textures: set[str] = set()
    material_diffuse_maps: dict[str, str] = {}
    current_name = ""

    with path.open("r", encoding="utf-8-sig", errors="strict") as stream:
        for source_line in stream:
            line = source_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            command = parts[0]
            value = parts[1] if len(parts) > 1 else ""
            if command == "newmtl":
                if not value or value in materials:
                    raise RuntimeError(f"Invalid or duplicate material: {value!r}")
                current = {}
                materials[value] = current
                current_name = value
            elif current is None:
                raise RuntimeError(f"MTL property before newmtl: {line!r}")
            elif command in {"Kd", "Ks", "Ka", "Tf"}:
                current[command] = [float(component) for component in value.split()]
            elif command in {"Ns", "Ni", "d", "Tr"}:
                current[command] = float(value)
            elif command == "illum":
                current[command] = int(value)
            elif command.lower().startswith("map_") or command.lower() in {
                "bump",
                "disp",
                "decal",
            }:
                normalized = value.replace("\\", "/")
                current[command] = normalized
                map_counts[command] += 1
                referenced_textures.add(normalized)
                if command == "map_Kd":
                    material_diffuse_maps[current_name] = normalized

    return {
        "material_count": len(materials),
        "map_counts": dict(sorted(map_counts.items())),
        "referenced_textures": sorted(referenced_textures),
        "material_diffuse_maps": material_diffuse_maps,
        "constant_opacity_below_one": sorted(
            name
            for name, material in materials.items()
            if float(material.get("d", 1.0)) < 1.0
        ),
    }


def hardlink_source(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if os.path.samefile(source, destination):
            return
        raise RuntimeError(
            f"Prepared file exists but is not the source hard link: {destination}"
        )
    os.link(source, destination)


def prepare_import_tree(
    source_dir: Path,
    output_dir: Path,
    alpha_materials: set[str],
    referenced_textures: list[str],
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_obj = source_dir / "san-miguel-low-poly.obj"
    source_mtl = source_dir / "san-miguel-low-poly.mtl"
    hardlink_source(source_obj, output_dir / source_obj.name)
    hardlink_source(source_dir / "license.txt", output_dir / "license.txt")
    for name in referenced_textures:
        normalized = Path(name.replace("\\", "/"))
        hardlink_source(source_dir / normalized, output_dir / normalized)

    current_material = ""
    replaced_opacity: set[str] = set()
    output_lines = [
        "# Derived for CMAA2 research import; original MTL is unchanged.\n",
        "# d 0 is the existing importer convention for alpha-test materials.\n",
    ]
    with source_mtl.open("r", encoding="utf-8-sig", errors="strict") as stream:
        for source_line in stream:
            stripped = source_line.strip()
            if stripped.startswith("newmtl "):
                current_material = stripped.split(maxsplit=1)[1]
            if stripped.startswith("d ") and current_material in alpha_materials:
                output_lines.append("d 0\n")
                replaced_opacity.add(current_material)
            else:
                output_lines.append(source_line)
    missing_opacity = alpha_materials - replaced_opacity
    if missing_opacity:
        raise RuntimeError(
            "Alpha materials without a replaceable d entry: "
            + ", ".join(sorted(missing_opacity))
        )
    prepared_mtl = output_dir / source_mtl.name
    prepared_mtl.write_text("".join(output_lines), encoding="utf-8")
    return {
        "classification": "derived-import-tree-outside-git",
        "hardlinked_obj": True,
        "hardlinked_texture_count": len(referenced_textures),
        "alpha_test_material_count": len(alpha_materials),
        "prepared_mtl_sha256": sha256_file(prepared_mtl),
    }


def analyze_obj(path: Path) -> dict[str, object]:
    counts: Counter[str] = Counter()
    materials: Counter[str] = Counter()
    objects: list[str] = []
    groups: set[str] = set()
    current_material = "unassigned"
    bounds_min = [math.inf, math.inf, math.inf]
    bounds_max = [-math.inf, -math.inf, -math.inf]

    with path.open("rb", buffering=8 * 1024 * 1024) as stream:
        for line_number, line in enumerate(stream, start=1):
            if line.startswith(b"v "):
                parts = line.split()
                if len(parts) < 4:
                    raise RuntimeError(f"Malformed vertex at line {line_number}")
                values = [float(parts[index]) for index in range(1, 4)]
                for axis, value in enumerate(values):
                    bounds_min[axis] = min(bounds_min[axis], value)
                    bounds_max[axis] = max(bounds_max[axis], value)
                counts["vertices"] += 1
            elif line.startswith(b"vt "):
                counts["texture_coordinates"] += 1
            elif line.startswith(b"vn "):
                counts["normals"] += 1
            elif line.startswith(b"f "):
                corner_count = len(line.split()) - 1
                if corner_count < 3:
                    raise RuntimeError(f"Malformed face at line {line_number}")
                counts["face_records"] += 1
                triangle_count = corner_count - 2
                counts["triangles"] += triangle_count
                materials[current_material] += triangle_count
            elif line.startswith(b"o "):
                objects.append(line[2:].strip().decode("utf-8", errors="strict"))
            elif line.startswith(b"g "):
                groups.add(line[2:].strip().decode("utf-8", errors="strict"))
            elif line.startswith(b"usemtl "):
                current_material = line[7:].strip().decode("utf-8", errors="strict")
                counts["material_switches"] += 1
            counts["source_lines"] = line_number

    if counts["vertices"] == 0 or counts["triangles"] == 0:
        raise RuntimeError("OBJ contains no renderable geometry")
    return {
        **dict(counts),
        "object_count": len(objects),
        "group_count": len(groups),
        "used_material_count": len(materials),
        "unassigned_triangles": materials.get("unassigned", 0),
        "bounds_min": bounds_min,
        "bounds_max": bounds_max,
        "extent": [bounds_max[i] - bounds_min[i] for i in range(3)],
        "objects": objects,
        "material_triangles": dict(sorted(materials.items())),
    }


def inspect_textures(
    source_dir: Path, referenced_names: list[str]
) -> dict[str, object]:
    files = [path for path in (source_dir / "textures").iterdir() if path.is_file()]
    by_lower_relative = {
        path.relative_to(source_dir).as_posix().lower(): path for path in files
    }
    missing: list[str] = []
    meaningful_alpha: list[str] = []
    dimensions: Counter[str] = Counter()
    modes: Counter[str] = Counter()

    for name in referenced_names:
        path = by_lower_relative.get(name.lower())
        if path is None:
            missing.append(name)
            continue
        with Image.open(path) as image:
            image.load()
            dimensions[f"{image.width}x{image.height}"] += 1
            modes[image.mode] += 1
            if "A" in image.getbands():
                minimum, maximum = image.getchannel("A").getextrema()
                if minimum < 255:
                    meaningful_alpha.append(name)
                if maximum > 255:
                    raise RuntimeError(f"Invalid alpha range in {name}")

    return {
        "archive_texture_count": len(files),
        "referenced_texture_count": len(referenced_names),
        "missing_textures": missing,
        "meaningful_alpha_texture_count": len(meaningful_alpha),
        "meaningful_alpha_textures": sorted(meaningful_alpha),
        "referenced_dimensions": dict(sorted(dimensions.items())),
        "referenced_modes": dict(sorted(modes.items())),
    }


def format_vector(values: list[float]) -> str:
    return "(" + ", ".join(f"{value:.3f}" for value in values) + ")"


def write_markdown(path: Path, manifest: dict[str, object]) -> None:
    geometry = manifest["low_poly_geometry"]
    materials = manifest["materials"]
    textures = manifest["textures"]
    assert isinstance(geometry, dict)
    assert isinstance(materials, dict)
    assert isinstance(textures, dict)
    map_counts = materials["map_counts"]
    assert isinstance(map_counts, dict)

    lines = [
        "# San Miguel 2.1 외부 장면 검증 결과",
        "",
        "이 파일은 원본 장면을 Git에 복제하지 않고 출처, 해시와 저폴리 구성만 기록한다.",
        "",
        "## 출처 및 사용 조건",
        "",
        f"- 배포 페이지: {ARCHIVE_PAGE}",
        f"- 다운로드 URL: {SOURCE_URL}",
        "- 원 저작자: Guillermo M. Leal Llaguno",
        "- 2017 개선: Morgan McGuire, Guedis Cardenas, Michael Mara, Nicholas Hull",
        f"- 원본 license.txt 조건: {LICENSE}",
        f"- ZIP SHA-256: `{manifest['archive_sha256']}`",
        f"- 저폴리 OBJ SHA-256: `{manifest['low_poly_obj_sha256']}`",
        "",
        "## 저폴리 실시간 장면 구성",
        "",
        f"- OBJ 크기: {int(manifest['low_poly_obj_bytes']):,} bytes",
        f"- 정점: {int(geometry['vertices']):,}",
        f"- texture coordinates: {int(geometry['texture_coordinates']):,}",
        f"- 법선: {int(geometry['normals']):,}",
        f"- 삼각형: {int(geometry['triangles']):,}",
        f"- 오브젝트: {int(geometry['object_count']):,}",
        f"- 사용 재질: {int(geometry['used_material_count']):,}",
        f"- AABB extent: {format_vector(geometry['extent'])}",
        "",
        "## 재질과 텍스처",
        "",
        f"- MTL 재질: {int(materials['material_count']):,}",
        f"- diffuse map: {int(map_counts.get('map_Kd', 0)):,}",
        f"- bump/normal 계열: {int(map_counts.get('map_Bump', 0)):,}",
        f"- specular map: {int(map_counts.get('map_Ks', 0)):,}",
        f"- ZIP PNG: {int(textures['archive_texture_count']):,}",
        f"- 실제 alpha 포함 참조 texture: {int(textures['meaningful_alpha_texture_count']):,}",
        f"- alpha-test로 표시한 재질: {int(manifest['alpha_test_material_count']):,}",
        f"- 누락 참조: {len(textures['missing_textures']):,}",
        "",
        "## 연구상 분류",
        "",
        "- 텍스처와 실제 건축·가구·식생을 포함하는 현실적 품질 장면이다.",
        "- alpha texture 식생과 얇은 난간·가구는 subpixel geometry 복구 평가에 사용한다.",
        "- Power Plant는 배관 geometry stress, San Miguel은 textured real-scene quality로 구분한다.",
        "- 원본 ZIP, OBJ와 PNG는 D 드라이브에만 두며 Git에는 포함하지 않는다.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    source_root = args.source_root.resolve()
    archive_path = source_root / "San_Miguel.zip"
    source_dir = source_root / "SourceLowPoly"
    obj_path = source_dir / "san-miguel-low-poly.obj"
    mtl_path = source_dir / "san-miguel-low-poly.mtl"
    license_path = source_dir / "license.txt"
    for required in (archive_path, obj_path, mtl_path, license_path):
        if not required.is_file():
            raise FileNotFoundError(required)

    archive_sha256 = (
        "skipped" if args.skip_hash else sha256_file(archive_path)
    )
    obj_sha256 = "skipped" if args.skip_hash else sha256_file(obj_path)
    mtl_sha256 = "skipped" if args.skip_hash else sha256_file(mtl_path)
    if not args.skip_hash and archive_sha256 != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError(
            f"Unexpected archive SHA-256 {archive_sha256}; "
            f"expected {EXPECTED_ARCHIVE_SHA256}"
        )
    if not args.skip_hash and obj_sha256 != EXPECTED_LOW_POLY_OBJ_SHA256:
        raise RuntimeError(
            f"Unexpected low-poly OBJ SHA-256 {obj_sha256}; "
            f"expected {EXPECTED_LOW_POLY_OBJ_SHA256}"
        )

    material_manifest = parse_mtl(mtl_path)
    referenced = material_manifest["referenced_textures"]
    assert isinstance(referenced, list)
    texture_manifest = inspect_textures(source_dir, referenced)
    if texture_manifest["missing_textures"]:
        raise RuntimeError(
            "Missing MTL textures: "
            + ", ".join(texture_manifest["missing_textures"])
        )

    meaningful_alpha = {
        str(name).lower() for name in texture_manifest["meaningful_alpha_textures"]
    }
    diffuse_maps = material_manifest.pop("material_diffuse_maps")
    assert isinstance(diffuse_maps, dict)
    alpha_materials = {
        str(material)
        for material, texture in diffuse_maps.items()
        if str(texture).lower() in meaningful_alpha
    }
    prepared_manifest: dict[str, object] | None = None
    if args.prepared_output is not None:
        prepared_manifest = prepare_import_tree(
            source_dir,
            args.prepared_output.resolve(),
            alpha_materials,
            referenced,
        )

    geometry_manifest = analyze_obj(obj_path)
    manifest: dict[str, object] = {
        "schema": "smaa-san-miguel-source-manifest-v1",
        "classification": "external-textured-real-scene-quality",
        "redistribution": "source asset excluded from Git",
        "source_page": ARCHIVE_PAGE,
        "source_url": SOURCE_URL,
        "copyright": "Guillermo M. Leal Llaguno",
        "license": LICENSE,
        "archive_path": "SanMiguel/San_Miguel.zip",
        "low_poly_obj_path": "SanMiguel/SourceLowPoly/san-miguel-low-poly.obj",
        "archive_bytes": archive_path.stat().st_size,
        "low_poly_obj_bytes": obj_path.stat().st_size,
        "archive_sha256": archive_sha256,
        "low_poly_obj_sha256": obj_sha256,
        "low_poly_mtl_sha256": mtl_sha256,
        "low_poly_geometry": geometry_manifest,
        "materials": material_manifest,
        "textures": texture_manifest,
        "alpha_test_material_count": len(alpha_materials),
    }
    if prepared_manifest is not None:
        manifest["prepared_import"] = prepared_manifest

    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "san_miguel_source_manifest.json"
    markdown_path = args.output / "san_miguel_source_manifest-ko.md"
    json_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_markdown(markdown_path, manifest)
    print(
        "PASS: "
        f"{geometry_manifest['triangles']:,} triangles, "
        f"{material_manifest['material_count']:,} materials, "
        f"{texture_manifest['meaningful_alpha_texture_count']:,} alpha textures"
    )
    print(json_path)
    print(markdown_path)


if __name__ == "__main__":
    main()
