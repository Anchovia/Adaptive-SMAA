#!/usr/bin/env python3
"""Validate and aggregate the integrated candidate-removal CGVQM-2 matrix."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from analyze_wide_camera_cgvqm import OFFICIAL_COMMIT, validate_result


SCENES = ("Bistro", "Minecraft")
WINDOWS = ("central_motion_00150_00329", "transition_00410_00439")
MODES = (
    ("O-1X", "O_1X", "control", None),
    ("O-T2X", "O_T2X", "off", None),
    ("O-ET2X [removal=0.50]", "O_ET2X_Removal_050", "off", 0.50),
    ("O-ET2X [removal=0.70]", "O_ET2X_Removal_070", "off", 0.70),
    ("O-ET2X [removal=0.75]", "O_ET2X_Removal_075", "off", 0.75),
    ("O-T2X-R", "O_T2X_R", "on", None),
    ("O-ET2X-R [removal=0.50]", "O_ET2X_R_Removal_050", "on", 0.50),
    ("O-ET2X-R [removal=0.70]", "O_ET2X_R_Removal_070", "on", 0.70),
    ("O-ET2X-R [removal=0.75]", "O_ET2X_R_Removal_075", "on", 0.75),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate 36 formal CGVQM-2 results")
    parser.add_argument("--cgvqm-root", type=Path, required=True)
    parser.add_argument("--spatial-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def percent_change(value: float, baseline: float) -> float:
    return (value / baseline - 1.0) * 100.0 if baseline != 0.0 else math.nan


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def add_deltas(records: list[dict[str, Any]]) -> None:
    by_group: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for record in records:
        by_group.setdefault((record["scene"], record["window"]), {})[
            record["mode"]
        ] = record
    for modes in by_group.values():
        o1x = modes["O-1X"]
        for record in modes.values():
            record["score_delta_vs_o_1x"] = (
                record["score_higher_is_better"] - o1x["score_higher_is_better"]
            )
        for group, standard_label, prefix in (
            ("off", "O-T2X", "O-ET2X"),
            ("on", "O-T2X-R", "O-ET2X-R"),
        ):
            standard = modes[standard_label]
            baseline = modes[f"{prefix} [removal=0.50]"]
            for removal in (0.50, 0.70, 0.75):
                record = modes[f"{prefix} [removal={removal:.2f}]"]
                record["reprojection_group"] = group
                record["removal"] = removal
                record["score_delta_vs_standard"] = (
                    record["score_higher_is_better"]
                    - standard["score_higher_is_better"]
                )
                record["score_delta_vs_removal_050"] = (
                    record["score_higher_is_better"]
                    - baseline["score_higher_is_better"]
                )
                record["error_mean_change_vs_removal_050_percent"] = percent_change(
                    record["error_map_mean"], baseline["error_map_mean"]
                )


def build_markdown(records: list[dict[str, Any]], spatial_summary: Path) -> str:
    lookup = {(row["scene"], row["window"], row["mode"]): row for row in records}
    lines = [
        "# Integrated Candidate Removal Full-Timeline CGVQM-2 결과",
        "",
        f"IntelLabs/CGVQM 공식 commit `{OFFICIAL_COMMIT}`의 CGVQM-2를 CUDA에서 순차 실행했다.",
        "Reference는 동일 pose supersample spatial proxy이며 CGVQM도 절대 고스팅 ground truth가 아니다.",
        "Standard와 document profile에는 coverage 외의 jitter/sampler/clipping/weight 차이도 있으므로 candidate 선택 단독 효과로 표현하지 않는다.",
        "",
        f"- 대응 spatial/temporal summary: `{spatial_summary.resolve()}`",
        "- 모든 test/reference FFV1 decode는 원본 PNG와 pixel mismatch 0을 요구한다.",
        "- CGVQM-2 temporal receptive-field 경계의 5프레임은 공식 점수에서 제거하지 않고 per-frame interior 보조값에서만 구분한다.",
        "",
    ]
    for scene in SCENES:
        lines.extend([f"## {scene}", ""])
        for window in WINDOWS:
            lines.extend(
                [
                    f"### {window}",
                    "",
                    "| Mode | CGVQM-2 ↑ | Δ vs O-1X | Δ vs matched Standard | Δ vs removal 0.50 | Error mean ↓ | Error mean Δ vs 0.50 | Interior error mean ↓ |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|",
                ]
            )
            for mode, _, _, _ in MODES:
                row = lookup[(scene, window, mode)]
                standard_delta = row.get("score_delta_vs_standard")
                removal_delta = row.get("score_delta_vs_removal_050")
                error_delta = row.get("error_mean_change_vs_removal_050_percent")
                standard_text = (
                    f"{standard_delta:+.6f}" if standard_delta is not None else "-"
                )
                lines.append(
                    f"| `{mode}` | {row['score_higher_is_better']:.6f} "
                    f"| {row['score_delta_vs_o_1x']:+.6f} | {standard_text}"
                )
                suffix = (
                    f" | {removal_delta:+.6f} | {row['error_map_mean']:.8f} | {error_delta:+.3f}% | {row['interior_error_mean']:.8f} |"
                    if removal_delta is not None and error_delta is not None
                    else f" | - | {row['error_map_mean']:.8f} | - | {row['interior_error_mean']:.8f} |"
                )
                lines[-1] += suffix
            lines.append("")
        lines.extend(
            [
                "### removal 0.70/0.75 대 0.50 요약",
                "",
                "| Window | Reprojection | Removal | CGVQM-2 Δ | Error mean Δ |",
                "|---|---|---:|---:|---:|",
            ]
        )
        for window in WINDOWS:
            for prefix, group in (("O-ET2X", "Off"), ("O-ET2X-R", "On")):
                for removal in (0.70, 0.75):
                    row = lookup[(scene, window, f"{prefix} [removal={removal:.2f}]")]
                    lines.append(
                        f"| {window} | {group} | {removal:.2f} "
                        f"| {row['score_delta_vs_removal_050']:+.6f} "
                        f"| {row['error_mean_change_vs_removal_050_percent']:+.3f}% |"
                    )
        lines.append("")
    lines.extend(
        [
            "## 판정 원칙",
            "",
            "- CGVQM 개선만으로 removal을 선택하지 않고, full-timeline spatial-reference·O-1X 거리·시간 변화·연속 프레임과 함께 판정한다.",
            "- 0.70이 0.50보다 CGVQM을 유지하면서 temporal 손실 증가가 허용 가능한지 두 장면과 Off/On 모두 확인한다.",
            "- 0.75는 성능 경계 ablation이며, 이득이 0.70보다 명확하지 않으면 더 큰 O-1X 회귀 때문에 기본 후보로 승격하지 않는다.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    root = args.cgvqm_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not args.spatial_summary.is_file():
        raise FileNotFoundError(args.spatial_summary)
    records: list[dict[str, Any]] = []
    for scene in SCENES:
        for window in WINDOWS:
            for mode, directory, group, removal in MODES:
                path = root / scene / window / directory / "CGVQM-Results.json"
                if not path.is_file():
                    raise FileNotFoundError(path)
                record, _ = validate_result(path, scene, window, mode)
                record["reprojection_group"] = group
                record["removal"] = removal
                records.append(record)
    add_deltas(records)
    write_csv(output / "integrated_candidate_removal_cgvqm_summary.csv", records)
    payload = {
        "classification": "formal_parameter_quality_gate",
        "official_cgvqm_commit": OFFICIAL_COMMIT,
        "model": "CGVQM-2",
        "job_count": len(records),
        "records": records,
    }
    (output / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "SMAA-Integrated-Candidate-Removal-CGVQM-Results-ko.md").write_text(
        build_markdown(records, args.spatial_summary), encoding="utf-8"
    )
    print(f"PASS: validated {len(records)} formal CGVQM-2 results")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
