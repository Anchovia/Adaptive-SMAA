#!/usr/bin/env python3
"""Validate and summarize the candidate edge-source performance benchmark."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


MODES = (
    "O-ET2X / LegacyLumaRedetect",
    "O-ET2X / SMAAFirstPassEdges",
    "O-ET2X-R / LegacyLumaRedetect",
    "O-ET2X-R / SMAAFirstPassEdges",
)
METRICS = (
    "ApplicationFrameWall",
    "WholeFrame",
    "SMAA",
    "SMAASpatial1X",
    "TSCMAAExtractCandidates",
    "TSCMAAResolveCandidates",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and summarize the formal candidate edge-source benchmark."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def percent_delta(value: float, baseline: float) -> float:
    if baseline == 0.0:
        raise RuntimeError("Cannot compute a percentage delta from zero")
    return (value - baseline) * 100.0 / baseline


def parse_rows(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    try:
        first = next(
            index for index, line in enumerate(lines) if line.startswith("Mode, Timing metric")
        )
        last = next(
            index for index in range(first + 1, len(lines))
            if lines[index].startswith("Frame-rate characterization:")
        )
    except StopIteration as exc:
        raise RuntimeError("Could not locate benchmark timing table") from exc

    parsed: list[dict[str, Any]] = []
    for fields in csv.reader(lines[first + 1 : last], skipinitialspace=True):
        fields = [field.strip() for field in fields]
        if not fields or not fields[0]:
            continue
        while fields and not fields[-1]:
            fields.pop()
        if len(fields) != 12:
            raise RuntimeError(f"Unexpected benchmark row width {len(fields)}: {fields}")
        parsed.append(
            {
                "mode": fields[0],
                "metric": fields[1],
                "type": fields[2],
                "samples": int(fields[3]),
                "mean_ms": float(fields[4]),
                "median_ms": float(fields[5]),
                "frame_stddev_ms": float(fields[6]),
                "p95_ms": float(fields[7]),
                "p99_ms": float(fields[8]),
                "max_ms": float(fields[9]),
                "runs": int(fields[10]),
                "run_mean_stddev_ms": float(fields[11]),
            }
        )
    return parsed


def validate(text: str, rows: list[dict[str, Any]]) -> None:
    required_text = (
        "Resolution:   1920 x 1017",
        "Vsync:        OFF",
        "Fullscreen:   Windowed",
        "Scene: bistro.",
        "Candidate counter readback: disabled for timing isolation.",
        "repeats: 3, warm-up: 300 frames, measurement: 4800 frames per mode per repeat.",
        "Performance benchmark validation: PASS",
    )
    for token in required_text:
        if token not in text:
            raise RuntimeError(f"Missing required provenance: {token}")

    keyed = {(row["mode"], row["metric"]): row for row in rows}
    if len(keyed) != len(rows):
        raise RuntimeError("Duplicate mode/metric timing rows")
    for mode in MODES:
        for metric in METRICS:
            row = keyed.get((mode, metric))
            if row is None:
                raise RuntimeError(f"Missing {mode} / {metric}")
            if row["samples"] != 14400 or row["runs"] != 3:
                raise RuntimeError(f"Invalid sample count for {mode} / {metric}")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(
    path: Path,
    selected: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> None:
    lines = [
        "# Candidate edge-source 정식 성능 결과",
        "",
        "RTX 3060 Ti, 1920×1017 windowed visible, VSync Off, candidate readback Off, ",
        "300-frame warm-up, mode당 4,800-frame × 3회 결과다.",
        "",
        "| Mode | Metric | Mean ms | P95 ms | Run-mean stddev ms |",
        "|---|---|---:|---:|---:|",
    ]
    for row in selected:
        lines.append(
            f"| {row['mode']} | {row['metric']} | {row['mean_ms']:.6f} | "
            f"{row['p95_ms']:.6f} | {row['run_mean_stddev_ms']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## SMAAFirstPassEdges − LegacyLumaRedetect",
            "",
            "| Pair | Metric | Delta ms | Delta % |",
            "|---|---|---:|---:|",
        ]
    )
    for item in comparisons:
        lines.append(
            f"| {item['pair']} | {item['metric']} | {item['delta_ms']:+.6f} | "
            f"{item['delta_percent']:+.3f}% |"
        )
    lines.extend(
        [
            "",
            "Candidate resolve는 소폭 감소했지만 candidate extraction, SMAA total과 ",
            "WholeFrame은 증가했다. 따라서 현재 구현에서는 SMAA 1차 패스 edge 재사용을 ",
            "전체 성능 최적화로 판단하거나 기본값으로 승격하지 않는다.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    text = args.input.read_text(encoding="utf-8-sig")
    rows = parse_rows(text)
    validate(text, rows)
    selected = [row for row in rows if row["metric"] in METRICS]
    keyed = {(row["mode"], row["metric"]): row for row in rows}
    comparisons: list[dict[str, Any]] = []
    for pair in ("O-ET2X", "O-ET2X-R"):
        legacy_mode = f"{pair} / LegacyLumaRedetect"
        first_mode = f"{pair} / SMAAFirstPassEdges"
        for metric in METRICS:
            legacy = keyed[(legacy_mode, metric)]["mean_ms"]
            first = keyed[(first_mode, metric)]["mean_ms"]
            comparisons.append(
                {
                    "pair": pair,
                    "metric": metric,
                    "legacy_mean_ms": legacy,
                    "first_pass_mean_ms": first,
                    "delta_ms": first - legacy,
                    "delta_percent": percent_delta(first, legacy),
                }
            )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "candidate_edge_source_performance_selected.csv", selected)
    write_csv(args.output / "candidate_edge_source_performance_comparisons.csv", comparisons)
    payload = {
        "validation": "PASS",
        "input": str(args.input.resolve()),
        "rows": selected,
        "comparisons": comparisons,
    }
    (args.output / "candidate_edge_source_performance_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(
        args.output / "candidate_edge_source_performance_summary-ko.md",
        selected,
        comparisons,
    )
    print(
        f"VALIDATION=PASS rows={len(selected)} comparisons={len(comparisons)}"
    )


if __name__ == "__main__":
    main()
