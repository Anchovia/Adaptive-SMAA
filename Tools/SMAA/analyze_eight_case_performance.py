from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


MODES = (
    "O-T2X",
    "O-T2X-R",
    "O-ET2X",
    "O-ET2X-R",
    "A-T2X",
    "A-T2X-R",
    "A-ET2X",
    "A-ET2X-R",
)
REQUIRED_TIMINGS = ("ApplicationFrameWall", "WholeFrame", "SMAA")
COMPARISONS = (
    ("adaptive", "O-T2X", "A-T2X"),
    ("adaptive", "O-T2X-R", "A-T2X-R"),
    ("adaptive", "O-ET2X", "A-ET2X"),
    ("adaptive", "O-ET2X-R", "A-ET2X-R"),
    ("edge_selective", "O-T2X", "O-ET2X"),
    ("edge_selective", "O-T2X-R", "O-ET2X-R"),
    ("edge_selective", "A-T2X", "A-ET2X"),
    ("edge_selective", "A-T2X-R", "A-ET2X-R"),
    ("reprojection", "O-T2X", "O-T2X-R"),
    ("reprojection", "O-ET2X", "O-ET2X-R"),
    ("reprojection", "A-T2X", "A-T2X-R"),
    ("reprojection", "A-ET2X", "A-ET2X-R"),
)
FRAME_RATE_FIELDS = (
    "wall_average_fps",
    "wall_1pct_low_fps",
    "gpu_equivalent_average_fps",
    "gpu_equivalent_1pct_low_fps",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze an SMAA eight-case repeated performance benchmark CSV."
    )
    parser.add_argument("results_csv", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--window-state",
        choices=("visible", "hidden", "unknown"),
        default="unknown",
        help="Record how the application window was presented during the run.",
    )
    parser.add_argument(
        "--classification",
        choices=("engineering", "formal"),
        default="engineering",
        help="Mark whether the run is engineering evidence or a formal research result.",
    )
    return parser.parse_args()


def clean_row(row: list[str]) -> list[str]:
    values = [value.strip() for value in row]
    while values and values[-1] == "":
        values.pop()
    return values


def number(value: str) -> float:
    return float(value.replace(",", ""))


def integer(value: str) -> int:
    return int(number(value))


def percent_delta(value: float, baseline: float) -> float:
    return (value - baseline) / baseline * 100.0 if baseline != 0.0 else 0.0


def extract_metadata(lines: list[str]) -> dict[str, Any]:
    text = "\n".join(lines)
    metadata: dict[str, Any] = {}

    patterns = {
        "system_info": r"^System info:\s*(.+)$",
        "api": r"^API:\s*(.+)$",
        "resolution": r"^Resolution:\s*(.+)$",
        "vsync": r"^Vsync:\s*(.+)$",
        "fullscreen": r"^Fullscreen:\s*(.+)$",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            metadata[key] = match.group(1).strip()

    settings = re.search(
        r"Start time:\s*([0-9.]+)\s*s,\s*repeats:\s*(\d+),\s*"
        r"warm-up:\s*(\d+)\s*frames,\s*measurement:\s*(\d+)\s*"
        r"frames per mode per repeat",
        text,
    )
    if settings:
        metadata.update(
            {
                "start_time_seconds": float(settings.group(1)),
                "repeats": int(settings.group(2)),
                "warmup_frames": int(settings.group(3)),
                "measurement_frames": int(settings.group(4)),
            }
        )

    metadata["candidate_readback_disabled"] = (
        "Candidate counter readback was disabled" in text
    )
    metadata["benchmark_validation_pass"] = (
        "Performance benchmark validation: PASS" in text
    )
    return metadata


def parse_results(
    path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, float]]]:
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
        values = {
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
        timings[row[0]][row[1]] = values

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
    expected_samples: int | None = None
    if "repeats" in metadata and "measurement_frames" in metadata:
        expected_samples = metadata["repeats"] * metadata["measurement_frames"]

    for mode in MODES:
        for metric in REQUIRED_TIMINGS:
            if metric not in timings[mode]:
                errors.append(f"{mode}: missing {metric}")
                continue
            row = timings[mode][metric]
            if expected_samples is not None and row["samples"] != expected_samples:
                errors.append(
                    f"{mode}/{metric}: samples {row['samples']} != {expected_samples}"
                )
            if "repeats" in metadata and row["runs"] != metadata["repeats"]:
                errors.append(
                    f"{mode}/{metric}: runs {row['runs']} != {metadata['repeats']}"
                )
        if mode not in frame_rates:
            errors.append(f"{mode}: missing frame-rate characterization")

    if not metadata.get("benchmark_validation_pass", False):
        errors.append("benchmark did not report PASS")
    if not metadata.get("candidate_readback_disabled", False):
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
    rows: list[dict[str, Any]] = []
    for axis, baseline, variant in COMPARISONS:
        for metric in REQUIRED_TIMINGS:
            baseline_value = timings[baseline][metric]["mean_ms"]
            variant_value = timings[variant][metric]["mean_ms"]
            rows.append(
                {
                    "axis": axis,
                    "baseline": baseline,
                    "variant": variant,
                    "metric": metric,
                    "baseline_mean_ms": baseline_value,
                    "variant_mean_ms": variant_value,
                    "delta_ms": variant_value - baseline_value,
                    "delta_percent": percent_delta(variant_value, baseline_value),
                }
            )
    return rows


def write_mode_summary(
    output: Path,
    timings: dict[str, dict[str, dict[str, Any]]],
    frame_rates: dict[str, dict[str, float]],
) -> str:
    name = "smaa_eight_case_performance_modes.csv"
    fieldnames = [
        "mode",
        "wall_mean_ms",
        "wall_p95_ms",
        "wall_p99_ms",
        "wall_run_mean_stddev_ms",
        "wall_average_fps",
        "wall_1pct_low_fps",
        "whole_frame_mean_ms",
        "whole_frame_p95_ms",
        "whole_frame_p99_ms",
        "whole_frame_run_mean_stddev_ms",
        "gpu_equivalent_average_fps",
        "gpu_equivalent_1pct_low_fps",
        "smaa_mean_ms",
        "smaa_p95_ms",
        "smaa_p99_ms",
        "smaa_run_mean_stddev_ms",
        "samples",
        "runs",
    ]
    with (output / name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for mode in MODES:
            wall = timings[mode]["ApplicationFrameWall"]
            whole = timings[mode]["WholeFrame"]
            smaa = timings[mode]["SMAA"]
            fps = frame_rates[mode]
            writer.writerow(
                {
                    "mode": mode,
                    "wall_mean_ms": wall["mean_ms"],
                    "wall_p95_ms": wall["p95_ms"],
                    "wall_p99_ms": wall["p99_ms"],
                    "wall_run_mean_stddev_ms": wall["run_mean_stddev_ms"],
                    "wall_average_fps": fps["wall_average_fps"],
                    "wall_1pct_low_fps": fps["wall_1pct_low_fps"],
                    "whole_frame_mean_ms": whole["mean_ms"],
                    "whole_frame_p95_ms": whole["p95_ms"],
                    "whole_frame_p99_ms": whole["p99_ms"],
                    "whole_frame_run_mean_stddev_ms": whole[
                        "run_mean_stddev_ms"
                    ],
                    "gpu_equivalent_average_fps": fps[
                        "gpu_equivalent_average_fps"
                    ],
                    "gpu_equivalent_1pct_low_fps": fps[
                        "gpu_equivalent_1pct_low_fps"
                    ],
                    "smaa_mean_ms": smaa["mean_ms"],
                    "smaa_p95_ms": smaa["p95_ms"],
                    "smaa_p99_ms": smaa["p99_ms"],
                    "smaa_run_mean_stddev_ms": smaa["run_mean_stddev_ms"],
                    "samples": smaa["samples"],
                    "runs": smaa["runs"],
                }
            )
    return name


def write_comparison_csv(output: Path, comparisons: list[dict[str, Any]]) -> str:
    name = "smaa_eight_case_performance_comparisons.csv"
    with (output / name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0].keys()))
        writer.writeheader()
        writer.writerows(comparisons)
    return name


def average_axis_delta(
    comparisons: list[dict[str, Any]], axis: str, metric: str
) -> float:
    values = [
        row["delta_percent"]
        for row in comparisons
        if row["axis"] == axis and row["metric"] == metric
    ]
    return sum(values) / len(values)


def comparison_table(
    comparisons: list[dict[str, Any]], axis: str, label: str
) -> list[str]:
    lines = [
        f"### {label}",
        "",
        "| 비교 | Wall 평균 변화 | WholeFrame 평균 변화 | SMAA 평균 변화 |",
        "|---|---:|---:|---:|",
    ]
    pairs = [(base, variant) for item_axis, base, variant in COMPARISONS if item_axis == axis]
    for baseline, variant in pairs:
        pair_rows = {
            row["metric"]: row
            for row in comparisons
            if row["axis"] == axis
            and row["baseline"] == baseline
            and row["variant"] == variant
        }
        lines.append(
            f"| `{variant}` vs `{baseline}` | "
            f"{pair_rows['ApplicationFrameWall']['delta_percent']:+.2f}% | "
            f"{pair_rows['WholeFrame']['delta_percent']:+.2f}% | "
            f"{pair_rows['SMAA']['delta_percent']:+.2f}% |"
        )
    lines.append("")
    return lines


def write_markdown(
    output: Path,
    source: Path,
    metadata: dict[str, Any],
    timings: dict[str, dict[str, dict[str, Any]]],
    frame_rates: dict[str, dict[str, float]],
    comparisons: list[dict[str, Any]],
    validation: dict[str, Any],
    window_state: str,
    classification: str,
    mode_csv: str,
    comparison_csv: str,
) -> str:
    name = "SMAA-Eight-Case-Performance-Analysis-ko.md"
    formal = classification == "formal" and window_state == "visible"
    lines = [
        "# SMAA 8-case 성능 분석",
        "",
        "## 결과 분류",
        "",
        f"- 분류: `{classification}`",
        f"- 애플리케이션 창 상태: `{window_state}`",
        f"- 본 측정으로 취급 가능: `{'예' if formal else '아니요'}`",
        f"- 원본 CSV: `{source}`",
        f"- 벤치마크 내부 검증: `{'PASS' if validation['pass'] else 'FAIL'}`",
        "",
    ]
    if not formal:
        lines.extend(
            [
                "> 이 실행은 창 상태 또는 명시적 분류 때문에 engineering evidence로만 "
                "취급한다. 논문용 FPS·전체 프레임 결론은 visible-window formal 실행으로 "
                "재현한 뒤 확정한다.",
                "",
            ]
        )

    lines.extend(
        [
            "## 측정 조건",
            "",
            f"- 시스템: {metadata.get('system_info', '미기록')}",
            f"- API: {metadata.get('api', '미기록')}",
            f"- 해상도: {metadata.get('resolution', '미기록')}",
            f"- VSync: {metadata.get('vsync', '미기록')}",
            f"- 화면 모드: {metadata.get('fullscreen', '미기록')}",
            f"- 시작 시각: {metadata.get('start_time_seconds', '미기록')}초",
            f"- 반복: {metadata.get('repeats', '미기록')}회",
            f"- warm-up: {metadata.get('warmup_frames', '미기록')}프레임",
            f"- mode별 반복당 측정: {metadata.get('measurement_frames', '미기록')}프레임",
            f"- candidate readback: {'Off' if metadata.get('candidate_readback_disabled') else '확인 필요'}",
            "",
            "## Mode별 결과",
            "",
            "| Mode | Wall 평균 | Wall p99 | Wall FPS | Wall 1% low | WholeFrame 평균 | WholeFrame p99 | SMAA 평균 | SMAA run σ |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for mode in MODES:
        wall = timings[mode]["ApplicationFrameWall"]
        whole = timings[mode]["WholeFrame"]
        smaa = timings[mode]["SMAA"]
        fps = frame_rates[mode]
        lines.append(
            f"| `{mode}` | {wall['mean_ms']:.6f} ms | {wall['p99_ms']:.6f} ms | "
            f"{fps['wall_average_fps']:.3f} | {fps['wall_1pct_low_fps']:.3f} | "
            f"{whole['mean_ms']:.6f} ms | {whole['p99_ms']:.6f} ms | "
            f"{smaa['mean_ms']:.6f} ms | {smaa['run_mean_stddev_ms']:.6f} ms |"
        )
    lines.append("")

    lines.extend(comparison_table(comparisons, "adaptive", "Adaptive 공간 탐색 효과"))
    lines.extend(
        comparison_table(
            comparisons, "edge_selective", "Edge-selective temporal 처리 효과"
        )
    )
    lines.extend(
        comparison_table(comparisons, "reprojection", "Camera reprojection 비용")
    )

    adaptive_delta = average_axis_delta(comparisons, "adaptive", "SMAA")
    edge_delta = average_axis_delta(comparisons, "edge_selective", "SMAA")
    reprojection_delta = average_axis_delta(comparisons, "reprojection", "SMAA")
    lines.extend(
        [
            "## 관측 요약",
            "",
            f"- Adaptive 공간 탐색의 대응 case 평균 SMAA 변화: `{adaptive_delta:+.2f}%`",
            f"- Edge-selective 처리의 대응 Standard 대비 평균 SMAA 변화: `{edge_delta:+.2f}%`",
            f"- Camera reprojection On의 대응 Off 대비 평균 SMAA 변화: `{reprojection_delta:+.2f}%`",
            "- 부호가 음수이면 시간이 감소했고, 양수이면 시간이 증가했다.",
            "- Wall FPS의 작은 차이는 Present와 OS scheduling을 포함하므로 알고리즘 원인으로 단정하지 않는다.",
            "- Edge 후보 감소만으로 최적화 성공을 주장하지 않고 SMAA와 WholeFrame GPU timestamp를 우선 확인한다.",
            "- 현재 reprojection은 camera motion만 처리하며 object motion vector는 지원하지 않는다.",
            "",
            "## 산출물",
            "",
            f"- Mode 요약: `{mode_csv}`",
            f"- 축별 비교: `{comparison_csv}`",
            "- 전체 JSON: `smaa_eight_case_performance_analysis.json`",
            "",
        ]
    )
    (output / name).write_text("\n".join(lines), encoding="utf-8")
    return name


def main() -> None:
    args = parse_args()
    source = args.results_csv.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    output = (
        args.output.resolve()
        if args.output
        else source.parent / "PerformanceAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)

    metadata, timings, frame_rates = parse_results(source)
    validation = validate(metadata, timings, frame_rates)
    if not validation["pass"]:
        raise RuntimeError("; ".join(validation["errors"]))

    comparisons = make_comparisons(timings)
    mode_csv = write_mode_summary(output, timings, frame_rates)
    comparison_csv = write_comparison_csv(output, comparisons)
    report = write_markdown(
        output,
        source,
        metadata,
        timings,
        frame_rates,
        comparisons,
        validation,
        args.window_state,
        args.classification,
        mode_csv,
        comparison_csv,
    )

    payload = {
        "source_csv": str(source),
        "output_directory": str(output),
        "classification": args.classification,
        "window_state": args.window_state,
        "formal_measurement": (
            args.classification == "formal" and args.window_state == "visible"
        ),
        "metadata": metadata,
        "validation": validation,
        "modes": timings,
        "frame_rates": frame_rates,
        "comparisons": comparisons,
        "artifacts": {
            "report": report,
            "mode_summary_csv": mode_csv,
            "comparison_csv": comparison_csv,
        },
    }
    json_name = "smaa_eight_case_performance_analysis.json"
    (output / json_name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Validation: PASS ({len(MODES)} modes)")
    print(f"Classification: {args.classification}, window: {args.window_state}")
    print(f"Report: {output / report}")
    print(f"JSON: {output / json_name}")


if __name__ == "__main__":
    main()
