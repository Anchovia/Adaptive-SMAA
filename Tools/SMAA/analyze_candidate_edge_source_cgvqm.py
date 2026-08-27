#!/usr/bin/env python3
"""Validate and aggregate the candidate edge-source CGVQM-2 gate."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PROFILE = "flythrough-wide-yaw-360"
REFERENCE_ID = "SS-Reference"
OFFICIAL_COMMIT = "8302ff45b4ff5a691682baf23f7c007d6b591e98"
SCENES = ("Bistro", "Minecraft")
WINDOWS = {
    "stable_motion_00210_00329": (210, 329),
    "transition_00410_00439": (410, 439),
}
SOURCES = {
    "LegacyLumaRedetect": "O_ET2X_R_LegacyLuma",
    "SMAAFirstPassEdges": "O_ET2X_R_SMAAEdges",
}
TEST_MODES = {
    "LegacyLumaRedetect": "O-ET2X-R-LegacyLuma",
    "SMAAFirstPassEdges": "O-ET2X-R-SMAAEdges",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and aggregate the formal Bistro/Minecraft candidate "
            "edge-source CGVQM-2 results."
        )
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def require(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{label}: {actual!r}, expected {expected!r}")


def validate_round_trip(entry: dict[str, Any], frame_count: int, label: str) -> None:
    require(entry.get("codec"), "ffv1", f"{label}.codec")
    require(entry.get("decoded_frames"), frame_count, f"{label}.decoded_frames")
    require(entry.get("mismatched_values"), 0, f"{label}.mismatched_values")
    require(entry.get("max_absolute_difference"), 0, f"{label}.max_difference")


def validate_result(
    path: Path,
    scene: str,
    window: str,
    source: str,
) -> dict[str, Any]:
    result = read_json(path)
    start, end = WINDOWS[window]
    frame_count = end - start + 1
    mode = TEST_MODES[source]

    require(result.get("classification"), "formal", f"{path}.classification")
    provenance = result.get("provenance", {})
    require(provenance.get("scene"), scene, f"{path}.scene")
    require(provenance.get("camera_profile"), PROFILE, f"{path}.camera_profile")
    require(provenance.get("test_mode"), mode, f"{path}.test_mode")
    require(provenance.get("reference_id"), REFERENCE_ID, f"{path}.reference_id")
    require(
        result.get("official_cgvqm", {}).get("commit"),
        OFFICIAL_COMMIT,
        f"{path}.official_commit",
    )

    runtime = result.get("runtime", {})
    require(runtime.get("device"), "cuda", f"{path}.device")
    require(runtime.get("cuda_available"), True, f"{path}.cuda_available")
    configuration = result.get("configuration", {})
    expected_configuration = {
        "fps": 60,
        "patch_scale": 4,
        "patch_pool": "mean",
        "models": ["2"],
        "reference_index_offset": 0,
    }
    for key, expected in expected_configuration.items():
        require(configuration.get(key), expected, f"{path}.configuration.{key}")

    for key in ("test_sequence", "reference_sequence"):
        sequence = result.get(key, {})
        expected_sequence = {
            "frame_count": frame_count,
            "first_index": start,
            "last_index": end,
            "width": 1920,
            "height": 1017,
        }
        for field, expected in expected_sequence.items():
            require(sequence.get(field), expected, f"{path}.{key}.{field}")

    validate_round_trip(result["test_round_trip"], frame_count, f"{path}.test")
    validate_round_trip(
        result["reference_round_trip"], frame_count, f"{path}.reference"
    )
    model = result.get("results", {}).get("CGVQM-2")
    if model is None:
        raise RuntimeError(f"{path}: missing CGVQM-2")
    error = model.get("error_map", {})
    return {
        "scene": scene,
        "window": window,
        "source": source,
        "start_frame": start,
        "end_frame": end,
        "frame_count": frame_count,
        "score": float(model["score_higher_is_better"]),
        "error_mean": float(error["mean"]),
        "error_p95": float(error["p95"]),
        "error_p99": float(error["p99"]),
        "error_max": float(error["maximum"]),
        "result_json": str(path.resolve()),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(
    path: Path,
    rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> None:
    lines = [
        "# Candidate edge-source CGVQM-2 정식 결과",
        "",
        "Intel 공식 CGVQM commit `8302ff45`의 CGVQM-2를 CUDA에서 실행했다. ",
        "모든 입력은 FFV1 무손실 왕복 시 픽셀 불일치 0을 통과했다. 점수는 높을수록 좋지만, ",
        "SS-Reference는 동일 pose의 spatial-reference proxy이며 절대적인 ghosting ground truth가 아니다.",
        "",
        "| Scene | Window | Source | CGVQM-2 ↑ | Error mean ↓ | Error p95 ↓ |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['scene']} | {row['window']} | {row['source']} | "
            f"{row['score']:.9f} | {row['error_mean']:.9f} | "
            f"{row['error_p95']:.9f} |"
        )
    lines.extend(
        [
            "",
            "## First-pass − Legacy 차이",
            "",
            "| Scene | Window | Score delta | Error-mean delta |",
            "|---|---|---:|---:|",
        ]
    )
    for item in comparisons:
        lines.append(
            f"| {item['scene']} | {item['window']} | "
            f"{item['score_delta']:+.9f} | {item['error_mean_delta']:+.9f} |"
        )
    lines.extend(
        [
            "",
            "Bistro 안정 구간만 아주 작게 양수였고, 나머지 세 비교는 아주 작게 음수였다. ",
            "변화의 크기와 방향이 장면·구간에 따라 달라지므로 first-pass source의 일관된 ",
            "품질 개선 근거로 사용하지 않는다.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for scene in SCENES:
        for window in WINDOWS:
            for source, directory in SOURCES.items():
                path = args.root / scene / window / directory / "CGVQM-Results.json"
                if not path.is_file():
                    raise RuntimeError(f"Missing result: {path}")
                rows.append(validate_result(path, scene, window, source))

    comparisons: list[dict[str, Any]] = []
    for scene in SCENES:
        for window in WINDOWS:
            pair = {
                row["source"]: row
                for row in rows
                if row["scene"] == scene and row["window"] == window
            }
            legacy = pair["LegacyLumaRedetect"]
            first = pair["SMAAFirstPassEdges"]
            comparisons.append(
                {
                    "scene": scene,
                    "window": window,
                    "score_delta": first["score"] - legacy["score"],
                    "error_mean_delta": first["error_mean"] - legacy["error_mean"],
                }
            )

    write_csv(args.output / "candidate_edge_source_cgvqm_results.csv", rows)
    payload = {
        "validation": "PASS",
        "official_commit": OFFICIAL_COMMIT,
        "rows": rows,
        "comparisons": comparisons,
    }
    (args.output / "candidate_edge_source_cgvqm_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(
        args.output / "candidate_edge_source_cgvqm_summary-ko.md",
        rows,
        comparisons,
    )
    print(f"VALIDATION=PASS rows={len(rows)} comparisons={len(comparisons)}")


if __name__ == "__main__":
    main()
