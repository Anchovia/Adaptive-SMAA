#!/usr/bin/env python3
"""Validate and aggregate the formal final 8-case wide-camera CGVQM-2 matrix."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np


PROFILE = "flythrough-wide-yaw-360"
OFFICIAL_COMMIT = "8302ff45b4ff5a691682baf23f7c007d6b591e98"
CLIP_SIZE = 30
TEMPORAL_RADIUS = 5
SCENES = ("Bistro", "Minecraft")
MODES = (
    ("O-1X", "O_1X"),
    ("O-T2X", "O_T2X"),
    ("O-T2X-R", "O_T2X_R"),
    ("O-ET2X", "O_ET2X"),
    ("O-ET2X-R", "O_ET2X_R"),
    ("A-1X", "A_1X"),
    ("A-T2X", "A_T2X"),
    ("A-T2X-R", "A_T2X_R"),
    ("A-ET2X", "A_ET2X"),
    ("A-ET2X-R", "A_ET2X_R"),
)
WINDOWS = {
    "central_motion_00150_00329": (150, 329),
    "transition_00410_00439": (410, 439),
}
AXIS_PAIRS = (
    ("spatial", "O-T2X", "A-T2X"),
    ("spatial", "O-T2X-R", "A-T2X-R"),
    ("spatial", "O-ET2X", "A-ET2X"),
    ("spatial", "O-ET2X-R", "A-ET2X-R"),
    ("temporal_coverage", "O-T2X", "O-ET2X"),
    ("temporal_coverage", "O-T2X-R", "O-ET2X-R"),
    ("temporal_coverage", "A-T2X", "A-ET2X"),
    ("temporal_coverage", "A-T2X-R", "A-ET2X-R"),
    ("reprojection", "O-T2X", "O-T2X-R"),
    ("reprojection", "O-ET2X", "O-ET2X-R"),
    ("reprojection", "A-T2X", "A-T2X-R"),
    ("reprojection", "A-ET2X", "A-ET2X-R"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cgvqm-root", type=Path, required=True)
    parser.add_argument("--spatial-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_round_trip(entry: dict[str, Any], frames: int, label: str) -> None:
    expected = {
        "codec": "ffv1",
        "decoded_frames": frames,
        "mismatched_values": 0,
        "max_absolute_difference": 0,
    }
    for key, value in expected.items():
        if entry.get(key) != value:
            raise RuntimeError(f"{label}: {key}={entry.get(key)!r}, expected {value!r}")


def read_frame_errors(path: Path, start: int, end: int) -> dict[str, float | int]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    indices = [int(row["frame_index"]) for row in rows]
    if indices != list(range(start, end + 1)):
        raise RuntimeError(f"{path}: frame range is not {start}..{end}")
    all_values = [float(row["mean"]) for row in rows]
    interior_values = []
    for ordinal, row in enumerate(rows):
        offset = ordinal % CLIP_SIZE
        if TEMPORAL_RADIUS <= offset < CLIP_SIZE - TEMPORAL_RADIUS:
            interior_values.append(float(row["mean"]))
    return {
        "per_frame_error_mean": statistics.fmean(all_values),
        "per_frame_error_p95": float(np.percentile(all_values, 95)),
        "per_frame_error_max": max(all_values),
        "interior_frame_count": len(interior_values),
        "interior_error_mean": statistics.fmean(interior_values),
        "interior_error_p95": float(np.percentile(interior_values, 95)),
        "interior_error_max": max(interior_values),
    }


def validate_result(root: Path, scene: str, window: str, mode: str, directory: str) -> dict[str, Any]:
    path = root / scene / window / directory / "CGVQM-Results.json"
    if not path.is_file():
        raise RuntimeError(f"Missing result: {path}")
    data = read_json(path)
    start, end = WINDOWS[window]
    frame_count = end - start + 1
    provenance = data.get("provenance", {})
    expected_provenance = {
        "scene": scene,
        "camera_profile": PROFILE,
        "test_mode": mode,
        "reference_id": "SS-Reference",
    }
    for key, value in expected_provenance.items():
        if provenance.get(key) != value:
            raise RuntimeError(f"{path}: {key}={provenance.get(key)!r}, expected {value!r}")
    if data.get("classification") != "formal":
        raise RuntimeError(f"{path}: not formal")
    if data.get("official_cgvqm", {}).get("commit") != OFFICIAL_COMMIT:
        raise RuntimeError(f"{path}: wrong official commit")
    runtime = data.get("runtime", {})
    if runtime.get("device") != "cuda" or not runtime.get("cuda_available"):
        raise RuntimeError(f"{path}: CUDA validation failed")
    configuration = data.get("configuration", {})
    expected_config = {
        "fps": 60,
        "patch_scale": 4,
        "patch_pool": "mean",
        "models": ["2"],
        "reference_index_offset": 0,
    }
    for key, value in expected_config.items():
        if configuration.get(key) != value:
            raise RuntimeError(f"{path}: {key}={configuration.get(key)!r}, expected {value!r}")
    for sequence_name in ("test_sequence", "reference_sequence"):
        sequence = data.get(sequence_name, {})
        expected_sequence = {
            "frame_count": frame_count,
            "first_index": start,
            "last_index": end,
            "width": 1920,
            "height": 1017,
        }
        for key, value in expected_sequence.items():
            if sequence.get(key) != value:
                raise RuntimeError(f"{path}: {sequence_name}.{key} invalid")
    validate_round_trip(data["test_round_trip"], frame_count, f"{path}/test")
    validate_round_trip(data["reference_round_trip"], frame_count, f"{path}/reference")
    model = data.get("results", {}).get("CGVQM-2")
    if model is None:
        raise RuntimeError(f"{path}: missing CGVQM-2")
    per_frame_path = Path(model["per_frame_csv"])
    if not per_frame_path.is_file():
        raise RuntimeError(f"{path}: missing per-frame CSV")
    return {
        "scene": scene,
        "window": window,
        "mode": mode,
        "start_frame": start,
        "end_frame": end,
        "frame_count": frame_count,
        "score_higher_is_better": float(model["score_higher_is_better"]),
        "error_map_mean": float(model["error_map"]["mean"]),
        "error_map_p95": float(model["error_map"]["p95"]),
        "error_map_p99": float(model["error_map"]["p99"]),
        "error_map_maximum": float(model["error_map"]["maximum"]),
        "result_json": str(path.resolve()),
        "per_frame_csv": str(per_frame_path.resolve()),
        "gpu": runtime.get("gpu"),
        **read_frame_errors(per_frame_path, start, end),
    }


def percent_delta(before: float, after: float) -> float:
    return (after - before) / before * 100.0 if abs(before) > 1.0e-12 else math.nan


def add_deltas(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["scene"], row["window"], row["mode"]): row for row in records}
    effects: list[dict[str, Any]] = []
    for scene in SCENES:
        for window in WINDOWS:
            original_control = by_key[(scene, window, "O-1X")]
            adaptive_control = by_key[(scene, window, "A-1X")]
            for mode, _ in MODES:
                row = by_key[(scene, window, mode)]
                control = adaptive_control if mode.startswith("A-") else original_control
                row["score_delta_vs_spatial_1x"] = row["score_higher_is_better"] - control["score_higher_is_better"]
                row["error_mean_delta_vs_spatial_1x_percent"] = percent_delta(
                    control["error_map_mean"], row["error_map_mean"]
                )
            for axis, before_mode, after_mode in AXIS_PAIRS:
                before = by_key[(scene, window, before_mode)]
                after = by_key[(scene, window, after_mode)]
                effects.append({
                    "scene": scene,
                    "window": window,
                    "axis": axis,
                    "baseline": before_mode,
                    "variant": after_mode,
                    "score_delta": after["score_higher_is_better"] - before["score_higher_is_better"],
                    "error_map_mean_delta_percent": percent_delta(before["error_map_mean"], after["error_map_mean"]),
                    "interior_error_mean_delta_percent": percent_delta(before["interior_error_mean"], after["interior_error_mean"]),
                })
    return effects


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, records: list[dict[str, Any]], effects: list[dict[str, Any]]) -> None:
    lines = [
        "# Final integrated 8-case wide-camera CGVQM-2 분석",
        "",
        "IntelLabs/CGVQM 공식 commit `8302ff45`, model 2, CUDA, 60 FPS, patch scale 4,",
        "mean pooling으로 Bistro/Minecraft의 final 8 cases와 O/A-1X control을",
        "동일 pose supersample spatial-reference proxy에 비교했다.",
        "",
        "## 공식 점수",
        "",
        "높을수록 reference에 가깝다. 두 window는 독립 clip 집합이므로 서로 평균하지 않는다.",
        "",
        "| Scene | Window | Mode | CGVQM-2↑ | Δ vs spatial 1X | Error mean |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in records:
        lines.append(
            f"| {row['scene']} | {row['window']} | {row['mode']} | "
            f"{row['score_higher_is_better']:.4f} | {row['score_delta_vs_spatial_1x']:+.4f} | "
            f"{row['error_map_mean']:.6f} |"
        )
    lines.extend([
        "",
        "## 독립 축 효과",
        "",
        "CGVQM score delta는 양수가 variant 우세, error delta는 음수가 variant 우세다.",
        "",
        "| Scene | Window | Axis | Comparison | Score Δ | Error mean Δ |",
        "|---|---|---|---|---:|---:|",
    ])
    for row in effects:
        lines.append(
            f"| {row['scene']} | {row['window']} | {row['axis']} | "
            f"{row['baseline']} → {row['variant']} | {row['score_delta']:+.4f} | "
            f"{row['error_map_mean_delta_percent']:+.3f}% |"
        )
    lines.extend([
        "",
        "## 해석 제한",
        "",
        "- Reference는 temporal history가 없는 spatial proxy이며 절대 ghosting ground truth가 아니다.",
        "- Official score는 clip 전체를 그대로 사용했다. Per-frame 보조 통계만 각 30-frame clip 경계 5 frames를 제외한다.",
        "- Camera/depth reprojection 결과이며 object motion vector 품질을 나타내지 않는다.",
        "- 성능 우열은 별도 4,800×3 GPU timing 결과로 판단한다.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = args.cgvqm_root.resolve()
    spatial_path = args.spatial_summary.resolve()
    spatial = read_json(spatial_path)
    if set(spatial) != {"bistro", "minecraft"}:
        raise RuntimeError("Spatial summary is missing required scenes")
    records: list[dict[str, Any]] = []
    for scene in SCENES:
        for window in WINDOWS:
            for mode, directory in MODES:
                records.append(validate_result(root, scene, window, mode, directory))
    effects = add_deltas(records)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "final_eight_cgvqm_scores.csv", records)
    write_csv(output / "final_eight_cgvqm_axis_effects.csv", effects)
    (output / "final_eight_cgvqm_summary.json").write_text(
        json.dumps(
            {
                "validation": "PASS",
                "official_commit": OFFICIAL_COMMIT,
                "spatial_summary": str(spatial_path),
                "records": records,
                "axis_effects": effects,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_markdown(output / "SMAA-Final-Eight-Case-CGVQM-Analysis-ko.md", records, effects)
    print(f"VALIDATION=PASS jobs={len(records)} effects={len(effects)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
