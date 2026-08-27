from __future__ import annotations

import argparse
import csv
import json
import math
import re
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
    ("O-ET2X [removal=0.50]", False, 0.50),
    ("O-ET2X [removal=0.65]", False, 0.65),
    ("O-ET2X [removal=0.70]", False, 0.70),
    ("O-ET2X [removal=0.75]", False, 0.75),
    ("O-ET2X-R [removal=0.50]", True, 0.50),
    ("O-ET2X-R [removal=0.65]", True, 0.65),
    ("O-ET2X-R [removal=0.70]", True, 0.70),
    ("O-ET2X-R [removal=0.75]", True, 0.75),
)
MODES = tuple(spec[0] for spec in MODE_SPECS)
REMOVALS = (0.50, 0.65, 0.70, 0.75)
COMMON_METRICS = (
    "ApplicationFrameWall",
    "WholeFrame",
    "SMAA",
    "SMAASpatial1X",
    "TSCMAACopySpatialToHistory",
    "TSCMAAClearIntegratedCandidateBuffers",
    "TSCMAAComputeDispatchArgs",
    "TSCMAAResolveCandidates",
    "TSCMAAOutputCopy",
)
FORBIDDEN_METRICS = (
    "SMAAStandardSpatialT2X",
    "SMAAStandardTemporalResolve",
    "TSCMAAPrepareCandidates",
    "TSCMAAExtractCandidates",
    "TSCMAADilateCandidates3x3",
    "TSCMAAFilteredQuarterDownsample",
    "TSCMAAFilteredQuarterUpsample",
    "TSCMAAArmDualDownsampleHalf",
    "TSCMAAArmDualDownsampleQuarter",
    "TSCMAAArmDualUpsampleHalf",
    "TSCMAAArmDualUpsampleFull",
)
COMPARISON_METRICS = (
    "ApplicationFrameWall",
    "WholeFrame",
    "SMAA",
    "SMAASpatial1X",
    "TSCMAAComputeDispatchArgs",
    "TSCMAAResolveCandidates",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the integrated candidate-removal performance matrix."
    )
    parser.add_argument("results_csv", type=Path)
    parser.add_argument("--output", type=Path)
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


def mode_label(reprojected: bool, removal: float) -> str:
    suffix = "-R" if reprojected else ""
    return f"O-ET2X{suffix} [removal={removal:.2f}]"


def parse_results(
    path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, dict[str, dict[str, Any]]],
    dict[str, dict[str, float]],
    dict[str, dict[str, float]],
]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text = "\n".join(lines)
    metadata = extract_metadata(lines)
    scene_match = re.search(r"^Scene:\s*([^.\r\n]+)", text, re.MULTILINE)
    metadata["scene"] = scene_match.group(1).strip() if scene_match else "unknown"
    metadata["candidate_readback_enabled"] = (
        "Candidate counter readback: enabled" in text
        and "Candidate counter characterization" in text
    )
    rows = [clean_row(row) for row in csv.reader(lines)]
    timing_header = next(
        index
        for index, row in enumerate(rows)
        if row[:3] == ["Mode", "Timing metric", "Type"]
    )
    frame_section = next(
        index
        for index, row in enumerate(rows)
        if row and row[0] == "Frame-rate characterization:"
    )
    frame_header = next(
        index
        for index in range(frame_section + 1, len(rows))
        if rows[index] and rows[index][0] == "Mode"
    )

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
    for row in rows[frame_header + 1 :]:
        if len(row) < 5 or row[0] not in timings:
            continue
        frame_rates[row[0]] = {
            field: number(value)
            for field, value in zip(FRAME_RATE_FIELDS, row[1:5])
        }

    counters: dict[str, dict[str, float]] = {}
    counter_headers = [
        index
        for index, row in enumerate(rows)
        if row[:2] == ["Mode", "Counter samples"]
    ]
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
    return metadata, timings, frame_rates, counters


def validate(
    metadata: dict[str, Any],
    timings: dict[str, dict[str, dict[str, Any]]],
    frame_rates: dict[str, dict[str, float]],
    counters: dict[str, dict[str, float]],
    classification: str,
    expect_readback: str,
) -> dict[str, Any]:
    errors: list[str] = []
    expected_samples = metadata.get("repeats", 0) * metadata.get(
        "measurement_frames", 0
    )
    for mode, reprojected, _ in MODE_SPECS:
        required = list(COMMON_METRICS)
        if reprojected:
            required.append("SMAAGenerateCameraVelocity")
        for metric in required:
            if metric not in timings[mode]:
                errors.append(f"{mode}: missing {metric}")
                continue
            row = timings[mode][metric]
            if expected_samples and row["samples"] != expected_samples:
                errors.append(
                    f"{mode}/{metric}: samples {row['samples']} != {expected_samples}"
                )
            if row["runs"] != metadata.get("repeats"):
                errors.append(
                    f"{mode}/{metric}: runs {row['runs']} != {metadata.get('repeats')}"
                )
        if not reprojected and "SMAAGenerateCameraVelocity" in timings[mode]:
            errors.append(f"{mode}: unexpected camera velocity timer")
        for metric in FORBIDDEN_METRICS:
            if metric in timings[mode]:
                errors.append(f"{mode}: unexpected {metric}")
        if mode not in frame_rates:
            errors.append(f"{mode}: missing frame-rate characterization")

    readback_on = metadata.get("candidate_readback_enabled", False)
    readback_off = metadata.get("candidate_readback_disabled", False)
    if expect_readback == "on" and not readback_on:
        errors.append("candidate readback was not reported enabled")
    if expect_readback == "off" and not readback_off:
        errors.append("candidate readback was not reported disabled")
    if readback_on:
        for mode in MODES:
            if mode not in counters:
                errors.append(f"{mode}: missing candidate counter row")
                continue
            counter = counters[mode]
            if counter["samples"] <= 0:
                errors.append(f"{mode}: empty candidate counter samples")
            if abs(counter["candidates"] - counter["process_count"]) > 0.001:
                errors.append(f"{mode}: candidate/process count mismatch")
        for reprojected in (False, True):
            ratios = [
                counters.get(mode_label(reprojected, removal), {}).get(
                    "candidate_to_base", float("nan")
                )
                for removal in REMOVALS
            ]
            if all(value == value for value in ratios):
                if any(a < b for a, b in zip(ratios, ratios[1:])):
                    errors.append(
                        f"{'reprojected' if reprojected else 'no-reprojection'} ratios are not monotonically non-increasing"
                    )
        for removal in REMOVALS:
            no_r = counters.get(mode_label(False, removal))
            with_r = counters.get(mode_label(True, removal))
            if no_r and with_r and abs(
                no_r["candidate_to_base"] - with_r["candidate_to_base"]
            ) > 0.000001:
                errors.append(
                    f"removal={removal:.2f}: reprojection changed candidate ratio"
                )
    elif counters:
        errors.append("counter rows exist while candidate readback is not enabled")

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


def make_comparisons(
    timings: dict[str, dict[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for reprojected in (False, True):
        baseline = mode_label(reprojected, 0.50)
        for removal in REMOVALS[1:]:
            variant = mode_label(reprojected, removal)
            for metric in COMPARISON_METRICS:
                base_value = timings[baseline][metric]["mean_ms"]
                value = timings[variant][metric]["mean_ms"]
                combined_run_stddev = math.hypot(
                    timings[baseline][metric]["run_mean_stddev_ms"],
                    timings[variant][metric]["run_mean_stddev_ms"],
                )
                rows.append(
                    {
                        "axis": "removal",
                        "reprojection": "On" if reprojected else "Off",
                        "removal": removal,
                        "baseline": baseline,
                        "variant": variant,
                        "metric": metric,
                        "baseline_mean_ms": base_value,
                        "variant_mean_ms": value,
                        "delta_ms": value - base_value,
                        "delta_percent": percent_delta(value, base_value),
                        "combined_run_mean_stddev_ms": combined_run_stddev,
                        "absolute_delta_to_combined_run_stddev": (
                            abs(value - base_value) / combined_run_stddev
                            if combined_run_stddev > 0.0
                            else 0.0
                        ),
                    }
                )
    for removal in REMOVALS:
        baseline = mode_label(False, removal)
        variant = mode_label(True, removal)
        for metric in COMPARISON_METRICS:
            base_value = timings[baseline][metric]["mean_ms"]
            value = timings[variant][metric]["mean_ms"]
            combined_run_stddev = math.hypot(
                timings[baseline][metric]["run_mean_stddev_ms"],
                timings[variant][metric]["run_mean_stddev_ms"],
            )
            rows.append(
                {
                    "axis": "reprojection",
                    "reprojection": "Off→On",
                    "removal": removal,
                    "baseline": baseline,
                    "variant": variant,
                    "metric": metric,
                    "baseline_mean_ms": base_value,
                    "variant_mean_ms": value,
                    "delta_ms": value - base_value,
                    "delta_percent": percent_delta(value, base_value),
                    "combined_run_mean_stddev_ms": combined_run_stddev,
                    "absolute_delta_to_combined_run_stddev": (
                        abs(value - base_value) / combined_run_stddev
                        if combined_run_stddev > 0.0
                        else 0.0
                    ),
                }
            )
    return rows


def main() -> None:
    args = parse_args()
    source = args.results_csv.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else source.parent / "IntegratedCandidateRemovalPerformance"
    )
    output.mkdir(parents=True, exist_ok=True)
    metadata, timings, frame_rates, counters = parse_results(source)
    validation = validate(
        metadata,
        timings,
        frame_rates,
        counters,
        args.classification,
        args.expect_readback,
    )
    comparisons = make_comparisons(timings)

    mode_csv = output / "integrated_candidate_removal_performance_modes.csv"
    with mode_csv.open("w", newline="", encoding="utf-8-sig") as stream:
        fields = [
            "mode",
            "reprojection",
            "removal",
            "wall_fps",
            "wall_1pct_low_fps",
            "whole_frame_ms",
            "smaa_ms",
            "spatial_ms",
            "clear_ms",
            "dispatch_args_ms",
            "resolve_ms",
            "output_copy_ms",
            "velocity_ms",
            "smaa_run_mean_stddev_ms",
            "samples",
            "runs",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for mode, reprojected, removal in MODE_SPECS:
            smaa = timings[mode]["SMAA"]
            velocity = timings[mode].get("SMAAGenerateCameraVelocity")
            writer.writerow(
                {
                    "mode": mode,
                    "reprojection": "On" if reprojected else "Off",
                    "removal": f"{removal:.2f}",
                    "wall_fps": frame_rates[mode]["wall_average_fps"],
                    "wall_1pct_low_fps": frame_rates[mode]["wall_1pct_low_fps"],
                    "whole_frame_ms": timings[mode]["WholeFrame"]["mean_ms"],
                    "smaa_ms": smaa["mean_ms"],
                    "spatial_ms": timings[mode]["SMAASpatial1X"]["mean_ms"],
                    "clear_ms": timings[mode]["TSCMAAClearIntegratedCandidateBuffers"]["mean_ms"],
                    "dispatch_args_ms": timings[mode]["TSCMAAComputeDispatchArgs"]["mean_ms"],
                    "resolve_ms": timings[mode]["TSCMAAResolveCandidates"]["mean_ms"],
                    "output_copy_ms": timings[mode]["TSCMAAOutputCopy"]["mean_ms"],
                    "velocity_ms": velocity["mean_ms"] if velocity else "",
                    "smaa_run_mean_stddev_ms": smaa["run_mean_stddev_ms"],
                    "samples": smaa["samples"],
                    "runs": smaa["runs"],
                }
            )

    comparison_csv = output / "integrated_candidate_removal_performance_effects.csv"
    with comparison_csv.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)

    result = {
        "source": str(source),
        "window_state": args.window_state,
        "classification": args.classification,
        "metadata": metadata,
        "validation": validation,
        "timings": timings,
        "frame_rates": frame_rates,
        "candidate_counters": counters,
        "comparisons": comparisons,
    }
    json_path = output / "integrated_candidate_removal_performance_summary.json"
    json_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# Integrated Candidate Removal 성능 분석",
        "",
        "## 조건",
        "",
        f"- 장면: `{metadata.get('scene', 'unknown')}`",
        f"- 분류/창 상태: `{args.classification}` / `{args.window_state}`",
        f"- 시스템: {metadata.get('system_info', 'unknown')}",
        f"- 해상도/API: {metadata.get('resolution', 'unknown')}, {metadata.get('api', 'unknown')}",
        f"- warm-up {metadata.get('warmup_frames')} frame, 측정 {metadata.get('measurement_frames')} frame × {metadata.get('repeats')}회",
        "- Original SMAA, integrated edge candidates, expansion None, PNG Off",
        f"- candidate readback: `{'On' if validation['readback_on'] else 'Off'}`",
        f"- 내부 검증: `{'PASS' if validation['pass'] else 'FAIL'}`",
        "",
        "## Mode별 결과",
        "",
        "| Mode | Wall FPS | WholeFrame | SMAA | Spatial | Clear | Args | Resolve | Velocity | SMAA run stddev |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, reprojected, _ in MODE_SPECS:
        velocity = timings[mode].get("SMAAGenerateCameraVelocity")
        velocity_text = f"{velocity['mean_ms']:.6f}" if velocity else "-"
        report.append(
            f"| `{mode}` | {frame_rates[mode]['wall_average_fps']:.3f} "
            f"| {timings[mode]['WholeFrame']['mean_ms']:.6f} "
            f"| {timings[mode]['SMAA']['mean_ms']:.6f} "
            f"| {timings[mode]['SMAASpatial1X']['mean_ms']:.6f} "
            f"| {timings[mode]['TSCMAAClearIntegratedCandidateBuffers']['mean_ms']:.6f} "
            f"| {timings[mode]['TSCMAAComputeDispatchArgs']['mean_ms']:.6f} "
            f"| {timings[mode]['TSCMAAResolveCandidates']['mean_ms']:.6f} "
            f"| {velocity_text} | {timings[mode]['SMAA']['run_mean_stddev_ms']:.6f} |"
        )

    report.extend(
        [
            "",
            "## removal=0.50 대비 변화",
            "",
            "| Reprojection | Removal | Metric | 변화 | 변화율 | |Δ|/결합 run σ |",
            "|---|---:|---|---:|---:|---:|",
        ]
    )
    for row in comparisons:
        if row["axis"] != "removal":
            continue
        report.append(
            f"| {row['reprojection']} | {row['removal']:.2f} | `{row['metric']}` "
            f"| {row['delta_ms']:+.6f} ms | {row['delta_percent']:+.3f}% "
            f"| {row['absolute_delta_to_combined_run_stddev']:.3f} |"
        )

    if counters:
        report.extend(
            [
                "",
                "## Candidate smoke 특성화",
                "",
                "| Mode | Samples | Base | Candidates | Process | Candidate/base |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for mode in MODES:
            counter = counters[mode]
            report.append(
                f"| `{mode}` | {int(counter['samples'])} | {counter['base_edges']:.3f} "
                f"| {counter['candidates']:.3f} | {counter['process_count']:.3f} "
                f"| {counter['candidate_to_base']:.6f} |"
            )

    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- Candidate 비율 감소만으로 성능 향상을 주장하지 않고 SMAA/WholeFrame 실측을 사용한다.",
            "- `-R`은 camera/depth reprojection이며 object motion vector는 포함하지 않는다.",
            "- removal은 공개 Intel 원본 식이 아니라 document-based SMAA adaptation의 파라미터다.",
            "- 작은 차이는 run-mean 표준편차 및 두 장면에서의 재현 여부와 함께 판정한다.",
        ]
    )
    report_path = output / "SMAA-Integrated-Candidate-Removal-Performance-ko.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    if not validation["pass"]:
        raise RuntimeError("; ".join(validation["errors"]))
    print(report_path)
    print(json_path)


if __name__ == "__main__":
    main()
