from __future__ import annotations

import argparse
import csv
import json
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


MODES = (
    "O-T2X-R",
    "ABL-CandidateOnly-R",
    "ABL-Candidate+Catmull-R",
    "ABL-Candidate+Catmull+Clip-R",
    "ABL-Candidate+Catmull+Clip+W0.8-R",
    "O-ET2X-R-Document",
)
REQUIRED_TIMINGS = ("ApplicationFrameWall", "WholeFrame", "SMAA")
ADJACENT_COMPARISONS = (
    ("candidate_coverage", "O-T2X-R", "ABL-CandidateOnly-R"),
    (
        "catmull_rom",
        "ABL-CandidateOnly-R",
        "ABL-Candidate+Catmull-R",
    ),
    (
        "variance_clipping",
        "ABL-Candidate+Catmull-R",
        "ABL-Candidate+Catmull+Clip-R",
    ),
    (
        "history_weight_0_8",
        "ABL-Candidate+Catmull+Clip-R",
        "ABL-Candidate+Catmull+Clip+W0.8-R",
    ),
    (
        "disable_deliberate_jitter",
        "ABL-Candidate+Catmull+Clip+W0.8-R",
        "O-ET2X-R-Document",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the repeated SMAA temporal component ablation benchmark."
    )
    parser.add_argument("results_csv", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--window-state",
        choices=("visible", "hidden", "unknown"),
        default="unknown",
    )
    parser.add_argument(
        "--classification",
        choices=("engineering", "formal"),
        default="engineering",
    )
    return parser.parse_args()


def parse_results(
    path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, dict[str, dict[str, Any]]],
    dict[str, dict[str, float]],
]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    metadata = extract_metadata(lines)
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
    return metadata, timings, frame_rates


def validate(
    metadata: dict[str, Any],
    timings: dict[str, dict[str, dict[str, Any]]],
    frame_rates: dict[str, dict[str, float]],
) -> dict[str, Any]:
    errors: list[str] = []
    expected_samples = (
        metadata.get("repeats", 0) * metadata.get("measurement_frames", 0)
    )
    for mode in MODES:
        for metric in REQUIRED_TIMINGS:
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
        if mode != "O-T2X-R" and "TSCMAAResolveCandidates" not in timings[mode]:
            errors.append(f"{mode}: missing TSCMAAResolveCandidates")
        if mode not in frame_rates:
            errors.append(f"{mode}: missing frame-rate characterization")
    if not metadata.get("benchmark_validation_pass"):
        errors.append("benchmark did not report PASS")
    if not metadata.get("candidate_readback_disabled"):
        errors.append("candidate readback was not reported disabled")
    return {
        "pass": not errors,
        "errors": errors,
        "mode_count": len(MODES),
        "expected_samples_per_required_metric": expected_samples,
    }


def make_comparisons(
    timings: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for component, baseline, variant in ADJACENT_COMPARISONS:
        metrics = list(REQUIRED_TIMINGS)
        if baseline != "O-T2X-R":
            metrics.append("TSCMAAResolveCandidates")
        for metric in metrics:
            baseline_value = timings[baseline][metric]["mean_ms"]
            variant_value = timings[variant][metric]["mean_ms"]
            comparisons.append(
                {
                    "component": component,
                    "baseline": baseline,
                    "variant": variant,
                    "metric": metric,
                    "baseline_mean_ms": baseline_value,
                    "variant_mean_ms": variant_value,
                    "delta_ms": variant_value - baseline_value,
                    "delta_percent": percent_delta(variant_value, baseline_value),
                }
            )
    return comparisons


def write_csvs(
    output: Path,
    timings: dict[str, dict[str, dict[str, Any]]],
    frame_rates: dict[str, dict[str, float]],
    comparisons: list[dict[str, Any]],
) -> tuple[str, str]:
    mode_name = "temporal_component_performance_modes.csv"
    mode_fields = [
        "mode",
        "wall_mean_ms",
        "wall_average_fps",
        "wall_1pct_low_fps",
        "whole_frame_mean_ms",
        "whole_frame_p95_ms",
        "whole_frame_run_mean_stddev_ms",
        "smaa_mean_ms",
        "smaa_p95_ms",
        "smaa_run_mean_stddev_ms",
        "candidate_resolve_mean_ms",
        "samples",
        "runs",
    ]
    with (output / mode_name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=mode_fields)
        writer.writeheader()
        for mode in MODES:
            wall = timings[mode]["ApplicationFrameWall"]
            whole = timings[mode]["WholeFrame"]
            smaa = timings[mode]["SMAA"]
            resolve = timings[mode].get("TSCMAAResolveCandidates")
            writer.writerow(
                {
                    "mode": mode,
                    "wall_mean_ms": wall["mean_ms"],
                    "wall_average_fps": frame_rates[mode]["wall_average_fps"],
                    "wall_1pct_low_fps": frame_rates[mode]["wall_1pct_low_fps"],
                    "whole_frame_mean_ms": whole["mean_ms"],
                    "whole_frame_p95_ms": whole["p95_ms"],
                    "whole_frame_run_mean_stddev_ms": whole[
                        "run_mean_stddev_ms"
                    ],
                    "smaa_mean_ms": smaa["mean_ms"],
                    "smaa_p95_ms": smaa["p95_ms"],
                    "smaa_run_mean_stddev_ms": smaa["run_mean_stddev_ms"],
                    "candidate_resolve_mean_ms": (
                        resolve["mean_ms"] if resolve is not None else ""
                    ),
                    "samples": smaa["samples"],
                    "runs": smaa["runs"],
                }
            )

    comparison_name = "temporal_component_performance_adjacent_effects.csv"
    with (output / comparison_name).open(
        "w", newline="", encoding="utf-8-sig"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    return mode_name, comparison_name


def main() -> None:
    args = parse_args()
    source = args.results_csv.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else source.parent / "ComponentPerformanceAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)
    metadata, timings, frame_rates = parse_results(source)
    validation = validate(metadata, timings, frame_rates)
    comparisons = make_comparisons(timings)
    mode_csv, comparison_csv = write_csvs(
        output, timings, frame_rates, comparisons
    )

    result = {
        "source": str(source),
        "window_state": args.window_state,
        "classification": args.classification,
        "metadata": metadata,
        "validation": validation,
        "modes": timings,
        "frame_rates": frame_rates,
        "adjacent_effects": comparisons,
    }
    json_name = "temporal_component_performance_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# SMAA temporal 구성요소 ablation 성능 분석",
        "",
        "## 조건",
        "",
        f"- 분류: `{args.classification}`",
        f"- 창 상태: `{args.window_state}`",
        f"- GPU/CPU: {metadata.get('system_info', 'unknown')}",
        f"- 해상도/API: {metadata.get('resolution', 'unknown')}, {metadata.get('api', 'unknown')}",
        f"- warm-up {metadata.get('warmup_frames')}프레임, 측정 {metadata.get('measurement_frames')}프레임 × {metadata.get('repeats')}회",
        "- Release x64, SMAA Ultra, VSync Off, fixed camera path, PNG Off, candidate readback Off",
        f"- 내부 검증: `{'PASS' if validation['pass'] else 'FAIL'}`",
        "",
        "## Mode별 성능",
        "",
        "| Mode | Wall FPS | WholeFrame GPU | SMAA GPU | Candidate resolve | Run-mean stddev (SMAA) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mode in MODES:
        whole = timings[mode]["WholeFrame"]
        smaa = timings[mode]["SMAA"]
        resolve = timings[mode].get("TSCMAAResolveCandidates")
        report.append(
            f"| `{mode}` | {frame_rates[mode]['wall_average_fps']:.3f} | "
            f"{whole['mean_ms']:.6f} ms | {smaa['mean_ms']:.6f} ms | "
            f"{resolve['mean_ms']:.6f} ms | " if resolve is not None else
            f"| `{mode}` | {frame_rates[mode]['wall_average_fps']:.3f} | "
            f"{whole['mean_ms']:.6f} ms | {smaa['mean_ms']:.6f} ms | - | "
        )
        report[-1] += f"{smaa['run_mean_stddev_ms']:.6f} ms |"

    report.extend(
        [
            "",
            "## 인접 구성요소 효과",
            "",
            "| 구성요소 | 비교 | 지표 | 변화 | 변화율 |",
            "|---|---|---|---:|---:|",
        ]
    )
    for row in comparisons:
        report.append(
            f"| `{row['component']}` | `{row['variant']}` vs `{row['baseline']}` | "
            f"`{row['metric']}` | {row['delta_ms']:+.6f} ms | "
            f"{row['delta_percent']:+.3f}% |"
        )
    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- Candidate coverage 단계는 full-screen Standard 경로에서 candidate compact/indirect 경로로 실행 구조 자체가 바뀐다.",
            "- Catmull-Rom, clipping, weight와 jitter 단계는 같은 edge-selective 경로 안의 인접 변화다.",
            "- 단일 3회 반복 결과의 작은 WholeFrame 차이는 run-mean 변동과 함께 판단한다.",
            "- 품질 결론은 별도 stress sequence ablation과 함께 판단한다.",
            "",
            "## 산출물",
            "",
            f"- Mode 표: `{mode_csv}`",
            f"- 인접 효과 표: `{comparison_csv}`",
            f"- JSON: `{json_name}`",
            "",
        ]
    )
    report_name = "SMAA-Temporal-Component-Performance-Analysis-ko.md"
    (output / report_name).write_text("\n".join(report), encoding="utf-8")
    if not validation["pass"]:
        raise RuntimeError("; ".join(validation["errors"]))
    print(f"Temporal component performance analysis complete: {output}")


if __name__ == "__main__":
    main()
