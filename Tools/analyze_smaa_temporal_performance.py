#!/usr/bin/env python3
"""Analyze SMAA V2/V3c/V4b temporal performance benchmark CSV output."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable


MODE_ORDER = (
    "V2_ReprojectedT2X",
    "V3c_StableEdgeUnion",
    "V4b_ExpandedIntersection",
)

METRIC_COLUMNS = (
    "frame_delta_ms",
    "frame_render_gpu_ms",
    "smaa_gpu_ms",
    "temporal_resolve_gpu_ms",
)


def percentile(values: Iterable[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_values(values: list[float]) -> dict[str, float]:
    valid = [value for value in values if math.isfinite(value) and value > 0.0]
    if not valid:
        return {
            "count": 0,
            "mean": math.nan,
            "median": math.nan,
            "sample_stddev": math.nan,
            "p95": math.nan,
            "p99": math.nan,
            "minimum": math.nan,
            "maximum": math.nan,
        }
    return {
        "count": len(valid),
        "mean": statistics.fmean(valid),
        "median": statistics.median(valid),
        "sample_stddev": statistics.stdev(valid) if len(valid) > 1 else 0.0,
        "p95": percentile(valid, 0.95),
        "p99": percentile(valid, 0.99),
        "minimum": min(valid),
        "maximum": max(valid),
    }


def load_rows(path: Path) -> list[dict[str, str | int | float]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {
            "scenario",
            "run",
            "order",
            "mode",
            "frame",
            *METRIC_COLUMNS,
            "temporal_stats_enabled",
        }
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

        rows: list[dict[str, str | int | float]] = []
        for source in reader:
            row: dict[str, str | int | float] = {
                "scenario": source["scenario"],
                "run": int(source["run"]),
                "order": int(source["order"]),
                "mode": source["mode"],
                "frame": int(source["frame"]),
                "temporal_stats_enabled": int(source["temporal_stats_enabled"]),
            }
            for column in METRIC_COLUMNS:
                row[column] = float(source[column])
            rows.append(row)
    if not rows:
        raise ValueError("No performance samples found")
    return rows


def summarize_group(rows: list[dict[str, str | int | float]]) -> dict[str, float | int | str]:
    summary: dict[str, float | int | str] = {
        "scenario": str(rows[0]["scenario"]),
        "mode": str(rows[0]["mode"]),
        "sample_count": len(rows),
        "run_count": len({int(row["run"]) for row in rows}),
    }
    for column in METRIC_COLUMNS:
        stats = summarize_values([float(row[column]) for row in rows])
        prefix = column.removesuffix("_ms")
        summary[f"{prefix}_valid_count"] = int(stats["count"])
        for statistic in ("mean", "median", "sample_stddev", "p95", "p99", "minimum", "maximum"):
            summary[f"{prefix}_{statistic}_ms"] = stats[statistic]

    frame_mean = float(summary["frame_delta_mean_ms"])
    frame_p99 = float(summary["frame_delta_p99_ms"])
    summary["average_fps"] = 1000.0 / frame_mean
    summary["one_percent_low_fps"] = 1000.0 / frame_p99
    summary["render_gpu_fps_equivalent"] = 1000.0 / float(summary["frame_render_gpu_mean_ms"])
    return summary


def add_v2_deltas(summaries: list[dict[str, float | int | str]]) -> None:
    baseline = next(summary for summary in summaries if summary["mode"] == MODE_ORDER[0])
    delta_metrics = (
        "frame_delta_mean_ms",
        "frame_render_gpu_mean_ms",
        "smaa_gpu_mean_ms",
        "temporal_resolve_gpu_mean_ms",
    )
    for summary in summaries:
        for metric in delta_metrics:
            baseline_value = float(baseline[metric])
            value = float(summary[metric])
            summary[f"{metric.removesuffix('_ms')}_delta_vs_v2_percent"] = (
                (value / baseline_value) - 1.0
            ) * 100.0


def run_summaries(rows: list[dict[str, str | int | float]]) -> list[dict[str, float | int | str]]:
    grouped: dict[tuple[int, str], list[dict[str, str | int | float]]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["run"]), str(row["mode"]))].append(row)

    summaries: list[dict[str, float | int | str]] = []
    for (run, mode), group in sorted(
        grouped.items(), key=lambda item: (item[0][0], MODE_ORDER.index(item[0][1]))
    ):
        summary = summarize_group(group)
        summary["run"] = run
        summary["order"] = int(group[0]["order"])
        summaries.append(summary)
    return summaries


def pooled_summaries(rows: list[dict[str, str | int | float]]) -> list[dict[str, float | int | str]]:
    grouped: dict[str, list[dict[str, str | int | float]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["mode"])].append(row)
    summaries = [summarize_group(grouped[mode]) for mode in MODE_ORDER]
    add_v2_deltas(summaries)
    return summaries


def add_repeat_statistics(
    pooled: list[dict[str, float | int | str]],
    per_run: list[dict[str, float | int | str]],
) -> None:
    for summary in pooled:
        mode = str(summary["mode"])
        mode_runs = [row for row in per_run if row["mode"] == mode]
        for metric in (
            "frame_delta_mean_ms",
            "frame_render_gpu_mean_ms",
            "smaa_gpu_mean_ms",
            "temporal_resolve_gpu_mean_ms",
            "average_fps",
            "one_percent_low_fps",
        ):
            values = [float(row[metric]) for row in mode_runs]
            summary[f"{metric.removesuffix('_ms')}_repeat_mean"] = statistics.fmean(values)
            summary[f"{metric.removesuffix('_ms')}_repeat_stddev"] = (
                statistics.stdev(values) if len(values) > 1 else 0.0
            )


def write_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def format_ms(value: object) -> str:
    return f"{float(value):.4f}"


def format_pct(value: object) -> str:
    return f"{float(value):+.2f}%"


def write_report(
    path: Path,
    source_csv: Path,
    rows: list[dict[str, str | int | float]],
    pooled: list[dict[str, float | int | str]],
    per_run: list[dict[str, float | int | str]],
) -> None:
    mode_lookup = {str(summary["mode"]): summary for summary in pooled}
    scenario = str(rows[0]["scenario"])
    run_count = len({int(row["run"]) for row in rows})
    samples_per_mode = len(rows) // len(MODE_ORDER)
    all_stats_disabled = all(int(row["temporal_stats_enabled"]) == 0 for row in rows)
    all_gpu_valid = all(
        float(row["frame_render_gpu_ms"]) > 0.0
        and float(row["smaa_gpu_ms"]) > 0.0
        and float(row["temporal_resolve_gpu_ms"]) > 0.0
        for row in rows
    )

    v3c = mode_lookup[MODE_ORDER[1]]
    v4b = mode_lookup[MODE_ORDER[2]]
    v4b_vs_v3c_smaa = (
        float(v4b["smaa_gpu_mean_ms"]) / float(v3c["smaa_gpu_mean_ms"]) - 1.0
    ) * 100.0
    v4b_vs_v3c_resolve = (
        float(v4b["temporal_resolve_gpu_mean_ms"])
        / float(v3c["temporal_resolve_gpu_mean_ms"])
        - 1.0
    ) * 100.0

    lines = [
        "# SMAA T2X V2 / V3c / V4b 성능 비교",
        "",
        "## 측정 개요",
        "",
        f"- 입력 CSV: `{source_csv}`",
        f"- 시나리오: {scenario}",
        f"- 반복 횟수: {run_count}",
        f"- 모드당 측정 표본: {samples_per_mode:,}프레임",
        "- 모드 순서: 반복마다 순환 배치하여 실행 순서와 발열 편향을 완화",
        f"- temporal 후보 통계 pass: {'비활성 확인' if all_stats_disabled else '활성 행 발견'}",
        f"- GPU 타이밍 유효성: {'모든 행 정상' if all_gpu_valid else '0 이하 값 존재'}",
        "",
        "1% low FPS는 `1000 / P99 실제 frame delta(ms)`로 계산했다. "
        "GPU frame time은 `FrameRender` 범위이며 Present와 ImGui는 제외한다.",
        "",
        "## 전체 표본 결과",
        "",
        "| 모드 | 실제 평균 FPS | 1% low FPS | Render GPU 평균 (ms) | SMAA GPU 평균 (ms) | Resolve GPU 평균 (ms) | SMAA vs V2 | Resolve vs V2 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode in MODE_ORDER:
        summary = mode_lookup[mode]
        lines.append(
            f"| {mode} | {float(summary['average_fps']):.2f} | "
            f"{float(summary['one_percent_low_fps']):.2f} | "
            f"{format_ms(summary['frame_render_gpu_mean_ms'])} | "
            f"{format_ms(summary['smaa_gpu_mean_ms'])} | "
            f"{format_ms(summary['temporal_resolve_gpu_mean_ms'])} | "
            f"{format_pct(summary['smaa_gpu_mean_delta_vs_v2_percent'])} | "
            f"{format_pct(summary['temporal_resolve_gpu_mean_delta_vs_v2_percent'])} |"
        )

    lines.extend(
        [
            "",
            "## 분포 통계",
            "",
            "| 모드 | Frame 중앙값 (ms) | Frame 표준편차 (ms) | Frame P95 (ms) | SMAA 중앙값 (ms) | SMAA 표준편차 (ms) | SMAA P95 (ms) | Resolve 중앙값 (ms) | Resolve 표준편차 (ms) | Resolve P95 (ms) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for mode in MODE_ORDER:
        summary = mode_lookup[mode]
        lines.append(
            f"| {mode} | "
            f"{format_ms(summary['frame_delta_median_ms'])} | "
            f"{format_ms(summary['frame_delta_sample_stddev_ms'])} | "
            f"{format_ms(summary['frame_delta_p95_ms'])} | "
            f"{format_ms(summary['smaa_gpu_median_ms'])} | "
            f"{format_ms(summary['smaa_gpu_sample_stddev_ms'])} | "
            f"{format_ms(summary['smaa_gpu_p95_ms'])} | "
            f"{format_ms(summary['temporal_resolve_gpu_median_ms'])} | "
            f"{format_ms(summary['temporal_resolve_gpu_sample_stddev_ms'])} | "
            f"{format_ms(summary['temporal_resolve_gpu_p95_ms'])} |"
        )

    lines.extend(
        [
            "",
            "## 반복별 SMAA GPU 평균",
            "",
            "| 반복 | 실행 순서 | 모드 | SMAA 평균 (ms) | Resolve 평균 (ms) | Render GPU 평균 (ms) |",
            "|---:|---:|---|---:|---:|---:|",
        ]
    )
    for summary in sorted(per_run, key=lambda row: (int(row["run"]), int(row["order"]))):
        lines.append(
            f"| {summary['run']} | {summary['order']} | {summary['mode']} | "
            f"{format_ms(summary['smaa_gpu_mean_ms'])} | "
            f"{format_ms(summary['temporal_resolve_gpu_mean_ms'])} | "
            f"{format_ms(summary['frame_render_gpu_mean_ms'])} |"
        )

    lines.extend(
        [
            "",
            "## V3c와 V4b 직접 비교",
            "",
            f"- V4b 전체 SMAA GPU 시간은 V3c 대비 {v4b_vs_v3c_smaa:+.2f}%다.",
            f"- V4b temporal resolve GPU 시간은 V3c 대비 {v4b_vs_v3c_resolve:+.2f}%다.",
            "- 후보 픽셀 감소가 실제 GPU 시간 감소로 이어졌는지는 위 두 값과 반복별 편차를 함께 판단해야 한다.",
            "- 전체 프레임 차이는 SMAA 외 렌더링 변동의 영향을 크게 받으므로 알고리즘 비용 판단은 SMAA와 resolve GPU 시간을 우선한다.",
            "",
            "## 해석 주의사항",
            "",
            "- 프레임별 표본은 연속 프레임이므로 서로 완전히 독립인 통계 표본은 아니다.",
            "- 공식 결론은 개별 프레임 표준편차보다 3회 반복 평균의 일관성을 우선한다.",
            "- 이 측정은 카메라 reprojection 기반 구현이며 움직이는 물체의 object motion vector는 아직 포함하지 않는다.",
            "- 품질 결론은 별도의 연속 프레임/GIF 분석과 함께 해석해야 한다.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark_dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    benchmark_dir = args.benchmark_dir.resolve()
    source_csv = benchmark_dir / "smaa_temporal_performance_raw.csv"
    output_dir = (args.output_dir or (benchmark_dir / "Analysis")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(source_csv)
    modes = {str(row["mode"]) for row in rows}
    if modes != set(MODE_ORDER):
        raise ValueError(f"Unexpected modes: {sorted(modes)}")
    if any(int(row["temporal_stats_enabled"]) != 0 for row in rows):
        raise ValueError("Temporal diagnostic stats were enabled in at least one sample")

    per_run = run_summaries(rows)
    pooled = pooled_summaries(rows)
    add_repeat_statistics(pooled, per_run)

    run_csv = output_dir / "smaa_temporal_performance_run_summary.csv"
    summary_csv = output_dir / "smaa_temporal_performance_summary.csv"
    report = output_dir / "SMAA-T2X-V2-V3c-V4b-Performance-Analysis-ko.md"
    write_csv(run_csv, per_run)
    write_csv(summary_csv, pooled)
    write_report(report, source_csv, rows, pooled, per_run)

    print(f"raw_rows={len(rows)}")
    print(f"run_summary={run_csv}")
    print(f"summary={summary_csv}")
    print(f"report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
