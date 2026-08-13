"""Validate and characterize the UNC Power Plant research scene.

The source asset is intentionally kept outside Git because its license permits
non-commercial use only and the merged OBJ is about 780 MiB.  This tool reads
the original OBJ as a stream, records reproducible per-section statistics, and
writes small JSON/Markdown manifests that can be committed with the research
code.  It does not modify, simplify, or repack the source geometry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO


EXPECTED_ARCHIVE_SHA256 = (
    "e5f9e9805c54b1e5b45ca38150ed40ff4b385206e50a8bbc501aaafccff2cad3"
)
EXPECTED_OBJ_SHA256 = (
    "1bda60ac06a11a6299799c95f4caac63b5c2a3654464040ff5b7d4bb8db190a8"
)
SCENE_SOURCE_URL = (
    "https://casual-effects.com/g3d/data10/research/model/powerplant/"
    "powerplant.zip"
)
SCENE_ARCHIVE_URL = "https://casual-effects.com/data"
SCENE_ORIGIN_URL = "http://gamma.cs.unc.edu/POWERPLANT/#acknowledgements"


@dataclass
class SectionStats:
    name: str
    vertex_count: int = 0
    normal_count: int = 0
    triangle_count: int = 0
    material_triangles: Counter[str] = field(default_factory=Counter)
    bounds_min: list[float] = field(
        default_factory=lambda: [math.inf, math.inf, math.inf]
    )
    bounds_max: list[float] = field(
        default_factory=lambda: [-math.inf, -math.inf, -math.inf]
    )

    def add_position(self, x: float, y: float, z: float) -> None:
        self.vertex_count += 1
        values = (x, y, z)
        for axis, value in enumerate(values):
            self.bounds_min[axis] = min(self.bounds_min[axis], value)
            self.bounds_max[axis] = max(self.bounds_max[axis], value)

    def to_dict(self) -> dict[str, object]:
        if self.vertex_count == 0:
            bounds_min: list[float] | None = None
            bounds_max: list[float] | None = None
            extent: list[float] | None = None
        else:
            bounds_min = self.bounds_min
            bounds_max = self.bounds_max
            extent = [
                self.bounds_max[axis] - self.bounds_min[axis]
                for axis in range(3)
            ]
        return {
            "name": self.name,
            "vertex_count": self.vertex_count,
            "normal_count": self.normal_count,
            "triangle_count": self.triangle_count,
            "material_count": len(self.material_triangles),
            "material_triangles": dict(sorted(self.material_triangles.items())),
            "bounds_min": bounds_min,
            "bounds_max": bounds_max,
            "extent": extent,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the UNC Power Plant OBJ and emit per-section research "
            "manifests without copying the source asset into Git."
        )
    )
    parser.add_argument(
        "source_root",
        type=Path,
        help="Directory containing powerplant.zip and Source/powerplant.obj.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory for the generated JSON and Markdown manifests.",
    )
    parser.add_argument(
        "--skip-hash",
        action="store_true",
        help="Skip SHA-256 validation during quick local iterations.",
    )
    return parser.parse_args()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def parse_float3(line: bytes) -> tuple[float, float, float]:
    parts = line.split()
    if len(parts) < 4:
        raise RuntimeError(f"Malformed vertex line: {line[:120]!r}")
    return float(parts[1]), float(parts[2]), float(parts[3])


def count_face_triangles(line: bytes) -> int:
    vertex_count = len(line.split()) - 1
    if vertex_count < 3:
        raise RuntimeError(f"Malformed face line: {line[:120]!r}")
    return vertex_count - 2


def analyze_obj(stream: BinaryIO) -> tuple[list[SectionStats], dict[str, int]]:
    sections: list[SectionStats] = []
    current_section: SectionStats | None = None
    current_material = "unassigned"
    global_vertices = 0
    global_normals = 0
    source_faces = 0
    source_lines = 0

    for source_lines, line in enumerate(stream, start=1):
        if line.startswith(b"g "):
            name = line[2:].strip().decode("utf-8", errors="strict")
            current_section = SectionStats(name=name)
            sections.append(current_section)
            current_material = "unassigned"
        elif line.startswith(b"v "):
            if current_section is None:
                raise RuntimeError(
                    f"Vertex before first group at source line {source_lines}"
                )
            current_section.add_position(*parse_float3(line))
            global_vertices += 1
        elif line.startswith(b"vn "):
            if current_section is None:
                raise RuntimeError(
                    f"Normal before first group at source line {source_lines}"
                )
            current_section.normal_count += 1
            global_normals += 1
        elif line.startswith(b"usemtl "):
            current_material = line[7:].strip().decode("utf-8", errors="strict")
        elif line.startswith(b"f "):
            if current_section is None:
                raise RuntimeError(
                    f"Face before first group at source line {source_lines}"
                )
            triangle_count = count_face_triangles(line)
            current_section.triangle_count += triangle_count
            current_section.material_triangles[current_material] += triangle_count
            source_faces += 1

    totals = {
        "source_lines": source_lines,
        "source_face_records": source_faces,
        "vertex_count": global_vertices,
        "normal_count": global_normals,
        "triangle_count": sum(section.triangle_count for section in sections),
    }
    return sections, totals


def format_vector(values: list[float] | None) -> str:
    if values is None:
        return "n/a"
    return "(" + ", ".join(f"{value:.3f}" for value in values) + ")"


def write_markdown(path: Path, manifest: dict[str, object]) -> None:
    totals = manifest["totals"]
    assert isinstance(totals, dict)
    sections = manifest["sections"]
    assert isinstance(sections, list)

    lines = [
        "# UNC Power Plant 외부 장면 검증 결과",
        "",
        "이 파일은 원본 장면을 복제하지 않고, 연구용 외부 데이터의 출처와 구조만 기록한다.",
        "원본은 비상업 용도만 허용되므로 Git에 포함하지 않는다.",
        "",
        "## 출처 및 사용 조건",
        "",
        f"- 배포 아카이브: {SCENE_ARCHIVE_URL}",
        f"- 원 출처 및 acknowledgements: {SCENE_ORIGIN_URL}",
        "- 저작권: University of North Carolina at Chapel Hill, 1999",
        "- 사용 조건: non-commercial use only",
        f"- 다운로드 URL: {SCENE_SOURCE_URL}",
        f"- ZIP SHA-256: `{manifest['archive_sha256']}`",
        f"- OBJ SHA-256: `{manifest['obj_sha256']}`",
        "",
        "## 전체 구조",
        "",
        f"- 구역 수: {len(sections):,}",
        f"- 정점: {int(totals['vertex_count']):,}",
        f"- 법선: {int(totals['normal_count']):,}",
        f"- 삼각형: {int(totals['triangle_count']):,}",
        f"- 원본 텍스트 행: {int(totals['source_lines']):,}",
        "",
        "## 구역별 통계",
        "",
        "| 구역 | 정점 | 법선 | 삼각형 | 재질 | AABB extent |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for section in sections:
        assert isinstance(section, dict)
        lines.append(
            "| {name} | {vertices:,} | {normals:,} | {triangles:,} | "
            "{materials:,} | {extent} |".format(
                name=section["name"],
                vertices=int(section["vertex_count"]),
                normals=int(section["normal_count"]),
                triangles=int(section["triangle_count"]),
                materials=int(section["material_count"]),
                extent=format_vector(section["extent"]),
            )
        )

    lines.extend(
        [
            "",
            "## 연구상 분류",
            "",
            "- 실제 발전소를 모델링한 외부 3D 장면이며 절차적 thin-lines control과 구분한다.",
            "- 배관, 난간, 프레임 등 실제 얇은 기하를 포함하는 quality stress 후보로 사용한다.",
            "- 이 통계만으로 구역을 선택하지 않고, 구역별 렌더 미리보기와 screen-space "
            "edge 통계를 추가 확인한 뒤 최종 subset을 고른다.",
            "- 원본 파일과 변환 캐시는 D 드라이브 연구 데이터 폴더에만 보관한다.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    source_root = args.source_root.resolve()
    archive_path = source_root / "powerplant.zip"
    obj_path = source_root / "Source" / "powerplant.obj"
    copyright_path = source_root / "Source" / "copyright.txt"

    for required_path in (archive_path, obj_path, copyright_path):
        if not required_path.is_file():
            raise FileNotFoundError(required_path)

    archive_sha256 = sha256_file(archive_path)
    obj_sha256 = sha256_file(obj_path)
    if not args.skip_hash:
        if archive_sha256 != EXPECTED_ARCHIVE_SHA256:
            raise RuntimeError(
                f"Unexpected archive SHA-256: {archive_sha256}; "
                f"expected {EXPECTED_ARCHIVE_SHA256}"
            )
        if obj_sha256 != EXPECTED_OBJ_SHA256:
            raise RuntimeError(
                f"Unexpected OBJ SHA-256: {obj_sha256}; "
                f"expected {EXPECTED_OBJ_SHA256}"
            )

    with obj_path.open("rb", buffering=8 * 1024 * 1024) as stream:
        sections, totals = analyze_obj(stream)

    if len(sections) != 21:
        raise RuntimeError(f"Expected 21 sections, found {len(sections)}")
    if totals["triangle_count"] != 12_759_246:
        raise RuntimeError(
            "Unexpected triangle count: "
            f"{totals['triangle_count']:,}; expected 12,759,246"
        )

    manifest: dict[str, object] = {
        "schema": "smaa-powerplant-source-manifest-v1",
        "classification": "external-real-geometry-research-scene",
        "redistribution": "source asset excluded from Git; non-commercial use only",
        "source_archive": SCENE_ARCHIVE_URL,
        "source_url": SCENE_SOURCE_URL,
        "origin_url": SCENE_ORIGIN_URL,
        "copyright": "University of North Carolina at Chapel Hill 1999",
        # Keep the committed manifest independent of the workstation drive
        # letter.  The caller-selected source_root is deliberately local and
        # the large source asset remains outside Git.
        "archive_path": "PowerPlant/powerplant.zip",
        "obj_path": "PowerPlant/Source/powerplant.obj",
        "archive_bytes": archive_path.stat().st_size,
        "obj_bytes": obj_path.stat().st_size,
        "archive_sha256": archive_sha256,
        "obj_sha256": obj_sha256,
        "totals": totals,
        "sections": [section.to_dict() for section in sections],
    }

    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "powerplant_source_manifest.json"
    markdown_path = args.output / "powerplant_source_manifest-ko.md"
    json_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_markdown(markdown_path, manifest)

    print(f"PASS: {len(sections)} sections, {totals['triangle_count']:,} triangles")
    print(json_path)
    print(markdown_path)


if __name__ == "__main__":
    main()
