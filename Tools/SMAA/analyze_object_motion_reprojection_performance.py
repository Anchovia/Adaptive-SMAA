#!/usr/bin/env python3
"""Validate and analyze the rigid-object reprojection performance gate."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from analyze_eight_case_performance import (
    FRAME_RATE_FIELDS,
    clean_row,
    extract_metadata,
    integer,
    number,
    percent_delta,
)


MODE_SPECS = (
    ("O-T2X-R / camera-only", "Standard", False),
    ("O-T2X-R / camera+rigid", "Standard", True),
    ("O-ET2X-R / camera-only", "Edge-selective", False),
    ("O-ET2X-R / camera+rigid", "Edge-selective", True),
)
MODES = tuple(item[0] for item in MODE_SPECS)
COMMON_METRICS = (
    "ApplicationFrameWall",
    "WholeFrame",
    "SMAA",
    "SMAAGenerateCameraVelocity",
)
STANDARD_METRICS = ("SMAAStandardSpatialT2X", "SMAAStandardTemporalResolve")
EDGE_METRICS = (
    "SMAASpatial1X",
    "TSCMAACopySpatialToHistory",
    "TSCMAAClearIntegratedCandidateBuffers",
    "TSCMAAComputeDispatchArgs",
    "TSCMAAResolveCandidates",
    "TSCMAAOutputCopy",
)
RIGID_METRIC = "SMAAGenerateRigidObjectVelocity"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze camera-only versus rigid-object reprojection performance."
    )
    parser.add_argument("results_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--window-state", choices=("visible", "hidden", "unknown"), default="unknown"
    )
    parser.add_argument(
        "--classification", choices=("engineering", "formal"), default="engineering"
    )
    parser.add_argument(
        "--expect-readback", choices=("on", "off", "either"), default="either"
    )
    return parser.parse_args()


def required_metrics(profile: str, rigid: bool) -> set[str]:
    result = set(COMMON_METRICS)
    result.update(STANDARD_METRICS if profile == "Standard" else EDGE_METRICS)
    if rigid:
        result.add(RIGID_METRIC)
    return result


def parse_results(path: Path) -> tuple[
    str,
    dict[str, Any],
    dict[str, dict[str, dict[str, Any]]],
    dict[str, dict[str, float]],
    dict[str, dict[str, float]],
]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text = "\n".join(lines)
    metadata = extract_metadata(lines)
    metadata["candidate_readback_enabled"] = (
        "Candidate counter readback: enabled" in text
        and "Candidate counter characterization" in text
    )
    rows = [clean_row(row) for row in csv.reader(lines)]
    timing_header = next(
        i for i, row in enumerate(rows) if row[:3] == ["Mode", "Timing metric", "Type"]
    )
    frame_section = next(
        i for i, row in enumerate(rows) if row and row[0] == "Frame-rate characterization:"
    )
    frame_header = next(
        i for i in range(frame_section + 1, len(rows)) if rows[i] and rows[i][0] == "Mode"
    )
    counter_headers = [
        i for i, row in enumerate(rows) if row[:2] == ["Mode", "Counter samples"]
    ]
    frame_end = counter_headers[0] if counter_headers else len(rows)

    timings: dict[str, dict[str, dict[str, Any]]] = {mode: {} for mode in MODES}
    for row in rows[timing_header + 1 : frame_section]:
        if len(row) < 12 or row[0] not in timings:
            continue
        timings[row[0]][row[1]] = {
            "type": row[2],
            "samples": integer(row[3]),
            "mean_ms": number(row[4]),
            "median_ms": number(row[5]),
            "frame_stddev_ms": number(row[6]),
            "p95_ms": number(row[7]),
            "p99_ms": number(row[8]),
            "max_ms": number(row[9]),
            "runs": integer(row[10]),
            "run_mean_stddev_ms": number(row[11]),
        }

    frame_rates: dict[str, dict[str, float]] = {}
    for row in rows[frame_header + 1 : frame_end]:
        if len(row) < 5 or row[0] not in timings:
            continue
        frame_rates[row[0]] = {
            key: number(value) for key, value in zip(FRAME_RATE_FIELDS, row[1:5])
        }

    counters: dict[str, dict[str, float]] = {}
    if counter_headers:
        for row in rows[counter_headers[0] + 1 :]:
            if len(row) < 6 or row[0] not in timings:
                continue
            counters[row[0]] = {
                "samples": integer(row[1]),
                "base_edges": number(row[2]),
                "candidates": number(row[3]),
                "process_count": number(row[4]),
                "candidate_to_base": number(row[5]),
            }
    return text, metadata, timings, frame_rates, counters


def validate(
    text: str,
    metadata: dict[str, Any],
    timings: dict[str, dict[str, dict[str, Any]]],
    frame_rates: dict[str, dict[str, float]],
    counters: dict[str, dict[str, float]],
    classification: str,
    expect_readback: str,
) -> dict[str, Any]:
    errors: list[str] = []
    expected_samples = metadata.get("repeats", 0) * metadata.get("measurement_frames", 0)
    if "SMAA rigid-object reprojection" not in text:
        errors.append("missing rigid-object benchmark title")
    if "Scene: procedural object-motion." not in text:
        errors.append("unexpected scene")
    for mode, profile, rigid in MODE_SPECS:
        required = required_metrics(profile, rigid)
        present = set(timings[mode])
        missing = sorted(required - present)
        if missing:
            errors.append(f"{mode}: missing {', '.join(missing)}")
        for metric in required & present:
            row = timings[mode][metric]
            if expected_samples and row["samples"] != expected_samples:
                errors.append(
                    f"{mode}/{metric}: samples {row['samples']} != {expected_samples}"
                )
            if row["runs"] != metadata.get("repeats"):
                errors.append(
                    f"{mode}/{metric}: runs {row['runs']} != {metadata.get('repeats')}"
                )
        if not rigid and RIGID_METRIC in present:
            errors.append(f"{mode}: unexpected rigid-object timer")
        if mode not in frame_rates:
            errors.append(f"{mode}: missing frame-rate characterization")

    readback_on = metadata.get("candidate_readback_enabled", False)
    readback_off = metadata.get("candidate_readback_disabled", False)
    if expect_readback == "on" and not readback_on:
        errors.append("candidate readback was not reported enabled")
    if expect_readback == "off" and not readback_off:
        errors.append("candidate readback was not reported disabled")
    edge_modes = MODES[2:]
    if readback_on:
        for mode in edge_modes:
            counter = counters.get(mode)
            if counter is None:
                errors.append(f"{mode}: missing candidate counters")
                continue
            if counter["samples"] != expected_samples:
                errors.append(
                    f"{mode}: counter samples {counter['samples']} != {expected_samples}"
                )
            if abs(counter["candidates"] - counter["process_count"]) > 0.001:
                errors.append(f"{mode}: candidate/process mismatch")
        if all(mode in counters for mode in edge_modes):
            for field in ("base_edges", "candidates", "process_count"):
                if abs(counters[edge_modes[0]][field] - counters[edge_modes[1]][field]) > 0.001:
                    errors.append(f"ET2X camera-only/rigid {field} mismatch")
    elif counters:
        errors.append("counter rows exist while readback is disabled")

    if classification == "formal":
        if metadata.get("warmup_frames") != 300:
            errors.append("formal run must use 300 warm-up frames")
        if metadata.get("measurement_frames") != 4800:
            errors.append("formal run must use 4800 measurement frames")
        if metadata.get("repeats", 0) < 3:
            errors.append("formal run must use at least 3 repeats")
        if not readback_off:
            errors.append("formal run requires candidate readback Off")
    if not metadata.get("benchmark_validation_pass"):
        errors.append("benchmark did not report PASS")
    return {
        "pass": not errors,
        "errors": errors,
        "expected_samples": expected_samples,
        "readback_on": readback_on,
        "readback_off": readback_off,
    }


def make_comparison(
    profile: str,
    metric: str,
    camera_mode: str,
    rigid_mode: str,
    timings: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    baseline = timings[camera_mode][metric]
    variant = timings[rigid_mode][metric]
    base_value = baseline["mean_ms"]
    value = variant["mean_ms"]
    combined_stddev = math.hypot(
        baseline["run_mean_stddev_ms"], variant["run_mean_stddev_ms"]
    )
    return {
        "profile": profile,
        "metric": metric,
        "baseline": camera_mode,
        "variant": rigid_mode,
        "baseline_mean_ms": base_value,
        "variant_mean_ms": value,
        "delta_ms": value - base_value,
        "delta_percent": percent_delta(value, base_value),
        "combined_run_mean_stddev_ms": combined_stddev,
        "absolute_delta_to_combined_run_stddev": (
            abs(value - base_value) / combined_stddev if combined_stddev > 0.0 else 0.0
        ),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_markdown(result: dict[str, Any]) -> str:
    timings = result["timings"]
    rates = result["frame_rates"]
    comparison_lookup = {
        (row["profile"], row["metric"]): row for row in result["comparisons"]
    }
    lines = [
        "# Rigid-object motion reprojection 성능 gate",
        "",
        "절차적 object-motion fixture에서 camera/depth-only reprojection과 rigid-object velocity 추가 경로를 비교한다. 이는 engineering gate이며 실제 textured dynamic scene의 최종 결과가 아니다.",
        "",
        "| Mode | Wall FPS | WholeFrame ms | SMAA ms | Rigid pass ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for mode, _, rigid in MODE_SPECS:
        rigid_text = (
            f"{timings[mode][RIGID_METRIC]['mean_ms']:.6f}" if rigid else "-"
        )
        lines.append(
            f"| `{mode}` | {rates[mode]['wall_average_fps']:.3f} "
            f"| {timings[mode]['WholeFrame']['mean_ms']:.6f} "
            f"| {timings[mode]['SMAA']['mean_ms']:.6f} | {rigid_text} |"
        )
    lines.extend(
        [
            "",
            "## camera+rigid의 camera-only 대비 비용",
            "",
            "| Profile | WholeFrame | SMAA | Camera velocity |",
            "|---|---:|---:|---:|",
        ]
    )
    for profile in ("Standard", "Edge-selective"):
        whole = comparison_lookup[(profile, "WholeFrame")]
        smaa = comparison_lookup[(profile, "SMAA")]
        camera = comparison_lookup[(profile, "SMAAGenerateCameraVelocity")]
        lines.append(
            f"| {profile} | {whole['delta_ms']:+.6f} ms ({whole['delta_percent']:+.3f}%) "
            f"| {smaa['delta_ms']:+.6f} ms ({smaa['delta_percent']:+.3f}%) "
            f"| {camera['delta_ms']:+.6f} ms ({camera['delta_percent']:+.3f}%) |"
        )
    lines.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- rigid pass의 0 ms 표본은 빈 작업 또는 GPU timestamp 해상도 미만의 유효 표본이다.",
            "- 품질 gate와 함께 해석하되, 절차적 fixture만으로 최종 8-case의 `-R` 의미를 바꾸지 않는다.",
            "- skinned/deforming/transparent motion 및 previous-depth disocclusion rejection은 포함하지 않는다.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    source = args.results_csv.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    text, metadata, timings, frame_rates, counters = parse_results(source)
    validation = validate(
        text,
        metadata,
        timings,
        frame_rates,
        counters,
        args.classification,
        args.expect_readback,
    )
    if not validation["pass"]:
        raise RuntimeError(f"validation failed: {validation['errors']}")

    comparisons: list[dict[str, Any]] = []
    for profile, camera_mode, rigid_mode, profile_metrics in (
        ("Standard", MODES[0], MODES[1], (*COMMON_METRICS, *STANDARD_METRICS)),
        ("Edge-selective", MODES[2], MODES[3], (*COMMON_METRICS, *EDGE_METRICS)),
    ):
        for metric in profile_metrics:
            comparisons.append(
                make_comparison(profile, metric, camera_mode, rigid_mode, timings)
            )

    mode_rows: list[dict[str, Any]] = []
    for mode, profile, rigid in MODE_SPECS:
        row: dict[str, Any] = {
            "mode": mode,
            "profile": profile,
            "rigid_object_velocity": rigid,
            "wall_fps": frame_rates[mode]["wall_average_fps"],
            "whole_frame_ms": timings[mode]["WholeFrame"]["mean_ms"],
            "smaa_ms": timings[mode]["SMAA"]["mean_ms"],
            "smaa_run_mean_stddev_ms": timings[mode]["SMAA"]["run_mean_stddev_ms"],
            "samples": timings[mode]["SMAA"]["samples"],
            "runs": timings[mode]["SMAA"]["runs"],
        }
        if rigid:
            row["rigid_object_velocity_ms"] = timings[mode][RIGID_METRIC]["mean_ms"]
        mode_rows.append(row)

    result = {
        "classification": args.classification,
        "window_state": args.window_state,
        "source": str(source),
        "metadata": metadata,
        "validation": validation,
        "timings": timings,
        "frame_rates": frame_rates,
        "candidate_counters": counters,
        "comparisons": comparisons,
    }
    write_csv(output / "object_motion_reprojection_performance_modes.csv", mode_rows)
    write_csv(output / "object_motion_reprojection_performance_effects.csv", comparisons)
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "SMAA-Object-Motion-Reprojection-Performance-ko.md").write_text(
        build_markdown(result), encoding="utf-8"
    )
    print(f"VALIDATION=PASS modes={len(mode_rows)} comparisons={len(comparisons)}")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
