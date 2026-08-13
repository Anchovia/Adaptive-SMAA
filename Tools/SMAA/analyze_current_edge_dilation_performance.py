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
    "O-ET2X-R-Document",
    "ABL-Document-Dilate3x3-R",
    "ABL-Candidate-Jitter-R",
    "ABL-Candidate-Jitter-Dilate3x3-R",
)
PAIRS = (
    ("Document", "O-ET2X-R-Document", "ABL-Document-Dilate3x3-R"),
    (
        "Candidate-Jitter",
        "ABL-Candidate-Jitter-R",
        "ABL-Candidate-Jitter-Dilate3x3-R",
    ),
)
REQUIRED_COMMON = (
    "ApplicationFrameWall",
    "WholeFrame",
    "SMAA",
    "TSCMAAExtractCandidates",
    "TSCMAAResolveCandidates",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the current-edge 3x3 dilation performance matrix."
    )
    parser.add_argument("results_csv", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--window-state", choices=("visible", "hidden", "unknown"), default="unknown"
    )
    parser.add_argument(
        "--classification", choices=("engineering", "formal"), default="engineering"
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
    expected = metadata.get("repeats", 0) * metadata.get("measurement_frames", 0)
    for mode in MODES:
        required = list(REQUIRED_COMMON)
        if "Dilate3x3" in mode:
            required.append("TSCMAADilateCandidates3x3")
        for metric in required:
            if metric not in timings[mode]:
                errors.append(f"{mode}: missing {metric}")
                continue
            row = timings[mode][metric]
            if expected and row["samples"] != expected:
                errors.append(
                    f"{mode}/{metric}: samples {row['samples']} != {expected}"
                )
            if row["runs"] != metadata.get("repeats"):
                errors.append(
                    f"{mode}/{metric}: runs {row['runs']} != {metadata.get('repeats')}"
                )
        if "Dilate3x3" not in mode and "TSCMAADilateCandidates3x3" in timings[mode]:
            errors.append(f"{mode}: unexpected dilation timer")
        if mode not in frame_rates:
            errors.append(f"{mode}: missing frame-rate characterization")
    if not metadata.get("benchmark_validation_pass"):
        errors.append("benchmark did not report PASS")
    if not metadata.get("candidate_readback_disabled"):
        errors.append("candidate readback was not reported disabled")
    return {"pass": not errors, "errors": errors, "expected_samples": expected}


def main() -> None:
    args = parse_args()
    source = args.results_csv.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else source.parent / "CurrentEdgeDilationPerformance"
    )
    output.mkdir(parents=True, exist_ok=True)
    metadata, timings, frame_rates = parse_results(source)
    validation = validate(metadata, timings, frame_rates)

    effects: list[dict[str, Any]] = []
    for label, baseline, dilated in PAIRS:
        for metric in ("ApplicationFrameWall", "WholeFrame", "SMAA", "TSCMAAResolveCandidates"):
            base = timings[baseline][metric]["mean_ms"]
            value = timings[dilated][metric]["mean_ms"]
            effects.append(
                {
                    "pair": label,
                    "baseline": baseline,
                    "dilated": dilated,
                    "metric": metric,
                    "baseline_mean_ms": base,
                    "dilated_mean_ms": value,
                    "delta_ms": value - base,
                    "delta_percent": percent_delta(value, base),
                }
            )

    mode_csv = "current_edge_dilation_performance_modes.csv"
    with (output / mode_csv).open("w", newline="", encoding="utf-8-sig") as stream:
        fields = [
            "mode",
            "wall_fps",
            "whole_frame_ms",
            "smaa_ms",
            "extract_ms",
            "dilate_ms",
            "resolve_ms",
            "samples",
            "runs",
            "smaa_run_mean_stddev_ms",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for mode in MODES:
            smaa = timings[mode]["SMAA"]
            writer.writerow(
                {
                    "mode": mode,
                    "wall_fps": frame_rates[mode]["wall_average_fps"],
                    "whole_frame_ms": timings[mode]["WholeFrame"]["mean_ms"],
                    "smaa_ms": smaa["mean_ms"],
                    "extract_ms": timings[mode]["TSCMAAExtractCandidates"]["mean_ms"],
                    "dilate_ms": timings[mode].get(
                        "TSCMAADilateCandidates3x3", {}
                    ).get("mean_ms", ""),
                    "resolve_ms": timings[mode]["TSCMAAResolveCandidates"]["mean_ms"],
                    "samples": smaa["samples"],
                    "runs": smaa["runs"],
                    "smaa_run_mean_stddev_ms": smaa["run_mean_stddev_ms"],
                }
            )

    effect_csv = "current_edge_dilation_performance_effects.csv"
    with (output / effect_csv).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(effects[0]))
        writer.writeheader()
        writer.writerows(effects)

    result = {
        "source": str(source),
        "window_state": args.window_state,
        "classification": args.classification,
        "metadata": metadata,
        "validation": validation,
        "modes": timings,
        "frame_rates": frame_rates,
        "dilation_effects": effects,
    }
    json_name = "current_edge_dilation_performance_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# Current-edge 3×3 dilation 성능 분석",
        "",
        "## 조건",
        "",
        f"- 분류/창 상태: `{args.classification}` / `{args.window_state}`",
        f"- 시스템: {metadata.get('system_info', 'unknown')}",
        f"- 해상도/API: {metadata.get('resolution', 'unknown')}, {metadata.get('api', 'unknown')}",
        f"- warm-up {metadata.get('warmup_frames')} frame, 측정 {metadata.get('measurement_frames')} frame × {metadata.get('repeats')}회",
        "- Release x64, SMAA Ultra, VSync Off, PNG Off, candidate readback Off",
        f"- 내부 검증: `{'PASS' if validation['pass'] else 'FAIL'}`",
        "",
        "## Mode별 결과",
        "",
        "| Mode | Wall FPS | WholeFrame | SMAA | Extract | 3×3 dilation | Resolve | SMAA run stddev |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode in MODES:
        dilate = timings[mode].get("TSCMAADilateCandidates3x3")
        dilate_text = f"{dilate['mean_ms']:.6f} ms" if dilate else "-"
        report.append(
            f"| `{mode}` | {frame_rates[mode]['wall_average_fps']:.3f} | "
            f"{timings[mode]['WholeFrame']['mean_ms']:.6f} ms | "
            f"{timings[mode]['SMAA']['mean_ms']:.6f} ms | "
            f"{timings[mode]['TSCMAAExtractCandidates']['mean_ms']:.6f} ms | "
            f"{dilate_text} | "
            f"{timings[mode]['TSCMAAResolveCandidates']['mean_ms']:.6f} ms | "
            f"{timings[mode]['SMAA']['run_mean_stddev_ms']:.6f} ms |"
        )
    report.extend(
        [
            "",
            "## 3×3 효과",
            "",
            "| Pair | Metric | 변화 | 변화율 |",
            "|---|---|---:|---:|",
        ]
    )
    for row in effects:
        report.append(
            f"| {row['pair']} | `{row['metric']}` | {row['delta_ms']:+.6f} ms | "
            f"{row['delta_percent']:+.3f}% |"
        )
    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            (
                "- 단일 smoke는 구현·계측 경로 검증이며 최종 성능 결론이 아니다."
                if metadata.get("repeats", 0) == 1
                else "- 이 반복 측정은 hidden-window engineering 결과이며 논문용 formal 성능 결과가 아니다."
            ),
            "- 후보 증가에 따른 품질 이득과 GPU 비용을 함께 판단해야 한다.",
            "- wall/WholeFrame의 작은 차이는 run-mean 변동보다 큰지 확인한다.",
        ]
    )
    report_name = "Current-Edge-Dilation-Performance-Report-ko.md"
    (output / report_name).write_text("\n".join(report) + "\n", encoding="utf-8")
    if not validation["pass"]:
        raise RuntimeError("; ".join(validation["errors"]))
    print(output / report_name)
    print(output / json_name)


if __name__ == "__main__":
    main()
