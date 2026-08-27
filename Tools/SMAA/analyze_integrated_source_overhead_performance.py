#!/usr/bin/env python3
"""Validate and analyze Standard/Legacy/Post-pass/Integrated SMAA timing."""

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
    ("O-T2X", "Standard", False, False),
    ("O-ET2X / LegacyLumaRedetect", "LegacyLumaRedetect", False, True),
    ("O-ET2X / SMAAFirstPassEdges", "SMAAFirstPassEdges", False, True),
    (
        "O-ET2X / SMAAFirstPassIntegratedCandidates",
        "SMAAFirstPassIntegratedCandidates",
        False,
        True,
    ),
    ("O-T2X-R", "Standard", True, False),
    ("O-ET2X-R / LegacyLumaRedetect", "LegacyLumaRedetect", True, True),
    ("O-ET2X-R / SMAAFirstPassEdges", "SMAAFirstPassEdges", True, True),
    (
        "O-ET2X-R / SMAAFirstPassIntegratedCandidates",
        "SMAAFirstPassIntegratedCandidates",
        True,
        True,
    ),
)
MODES = tuple(spec[0] for spec in MODE_SPECS)
SOURCES = (
    "LegacyLumaRedetect",
    "SMAAFirstPassEdges",
    "SMAAFirstPassIntegratedCandidates",
)
COMMON_METRICS = ("ApplicationFrameWall", "WholeFrame", "SMAA")
EDGE_COMMON_METRICS = (
    "SMAASpatial1X",
    "TSCMAACopySpatialToHistory",
    "TSCMAAComputeDispatchArgs",
    "TSCMAAResolveCandidates",
    "TSCMAAOutputCopy",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the 8-configuration integrated source-overhead benchmark."
    )
    parser.add_argument(
        "--case",
        nargs=2,
        action="append",
        required=True,
        metavar=("SCENE", "RESULTS_CSV"),
    )
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


def source_mode(reprojected: bool, source: str) -> str:
    prefix = "O-ET2X-R" if reprojected else "O-ET2X"
    return f"{prefix} / {source}"


def standard_mode(reprojected: bool) -> str:
    return "O-T2X-R" if reprojected else "O-T2X"


def parse_results(
    path: Path,
) -> tuple[
    str,
    dict[str, Any],
    dict[str, dict[str, dict[str, Any]]],
    dict[str, dict[str, float]],
    dict[str, dict[str, float]],
]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text = "\n".join(lines)
    metadata = extract_metadata(lines)
    scene_match = re.search(r"^Scene:\s*([^\.\r\n]+)", text, re.MULTILINE)
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
    counter_headers = [
        index for index, row in enumerate(rows) if row[:2] == ["Mode", "Counter samples"]
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
            field: number(value)
            for field, value in zip(FRAME_RATE_FIELDS, row[1:5])
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


def required_metrics(source: str, reprojected: bool, edge_selective: bool) -> set[str]:
    required = set(COMMON_METRICS)
    if reprojected:
        required.add("SMAAGenerateCameraVelocity")
    if not edge_selective:
        required.update(("SMAAStandardSpatialT2X", "SMAAStandardTemporalResolve"))
        return required
    required.update(EDGE_COMMON_METRICS)
    if source == "SMAAFirstPassIntegratedCandidates":
        required.add("TSCMAAClearIntegratedCandidateBuffers")
    else:
        required.update(("TSCMAAPrepareCandidates", "TSCMAAExtractCandidates"))
    return required


def validate_case(
    expected_scene: str,
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
    expected_title = "SMAA integrated source-overhead"
    if expected_title not in text:
        errors.append("missing integrated source-overhead benchmark title")
    if metadata.get("scene", "").lower() != expected_scene.lower():
        errors.append(f"scene {metadata.get('scene')} != {expected_scene}")
    for mode, source, reprojected, edge_selective in MODE_SPECS:
        present = set(timings[mode])
        required = required_metrics(source, reprojected, edge_selective)
        missing = sorted(required - present)
        if missing:
            errors.append(f"{mode}: missing {', '.join(missing)}")
        for metric in required & present:
            row = timings[mode][metric]
            if expected_samples and row["samples"] != expected_samples:
                errors.append(f"{mode}/{metric}: samples {row['samples']} != {expected_samples}")
            if row["runs"] != metadata.get("repeats"):
                errors.append(f"{mode}/{metric}: runs {row['runs']} != {metadata.get('repeats')}")
        if mode not in frame_rates:
            errors.append(f"{mode}: missing frame-rate characterization")

    readback_on = metadata.get("candidate_readback_enabled", False)
    readback_off = metadata.get("candidate_readback_disabled", False)
    if expect_readback == "on" and not readback_on:
        errors.append("candidate readback was not reported enabled")
    if expect_readback == "off" and not readback_off:
        errors.append("candidate readback was not reported disabled")
    if readback_on:
        for mode, source, reprojected, edge_selective in MODE_SPECS:
            if not edge_selective:
                if mode in counters:
                    errors.append(f"{mode}: unexpected candidate counter row")
                continue
            counter = counters.get(mode)
            if counter is None:
                errors.append(f"{mode}: missing candidate counter row")
                continue
            if counter["samples"] <= 0:
                errors.append(f"{mode}: empty candidate counter samples")
            if abs(counter["candidates"] - counter["process_count"]) > 0.001:
                errors.append(f"{mode}: candidate/process mismatch")
        for reprojected in (False, True):
            post = counters.get(source_mode(reprojected, "SMAAFirstPassEdges"))
            integrated = counters.get(
                source_mode(reprojected, "SMAAFirstPassIntegratedCandidates")
            )
            if post and integrated:
                for field in ("base_edges", "candidates", "process_count"):
                    if abs(post[field] - integrated[field]) > 0.001:
                        errors.append(
                            f"{'On' if reprojected else 'Off'}: post/integrated {field} mismatch"
                        )
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


def comparison(
    scene: str,
    axis: str,
    reprojection: str,
    baseline: str,
    variant: str,
    metric: str,
    timings: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    base_row = timings[baseline][metric]
    variant_row = timings[variant][metric]
    base = base_row["mean_ms"]
    value = variant_row["mean_ms"]
    combined_stddev = math.hypot(
        base_row["run_mean_stddev_ms"], variant_row["run_mean_stddev_ms"]
    )
    return {
        "scene": scene,
        "axis": axis,
        "reprojection": reprojection,
        "baseline": baseline,
        "variant": variant,
        "metric": metric,
        "baseline_mean_ms": base,
        "variant_mean_ms": value,
        "delta_ms": value - base,
        "delta_percent": percent_delta(value, base),
        "combined_run_mean_stddev_ms": combined_stddev,
        "absolute_delta_to_combined_run_stddev": (
            abs(value - base) / combined_stddev if combined_stddev > 0.0 else 0.0
        ),
    }


def make_comparisons(
    scene: str, timings: dict[str, dict[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for reprojected in (False, True):
        reprojection = "On" if reprojected else "Off"
        legacy = source_mode(reprojected, "LegacyLumaRedetect")
        post = source_mode(reprojected, "SMAAFirstPassEdges")
        integrated = source_mode(reprojected, "SMAAFirstPassIntegratedCandidates")
        standard = standard_mode(reprojected)
        for baseline, variant, axis in (
            (legacy, post, "Post-pass vs Legacy"),
            (legacy, integrated, "Integrated vs Legacy"),
            (post, integrated, "Integrated vs Post-pass"),
        ):
            for metric in (*COMMON_METRICS, *EDGE_COMMON_METRICS):
                rows.append(
                    comparison(
                        scene, axis, reprojection, baseline, variant, metric, timings
                    )
                )
        for metric in COMMON_METRICS:
            rows.append(
                comparison(
                    scene,
                    "Integrated vs Standard semantic",
                    reprojection,
                    standard,
                    integrated,
                    metric,
                    timings,
                )
            )
    return rows


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
    lookup = {
        (row["scene"], row["axis"], row["reprojection"], row["metric"]): row
        for row in result["comparisons"]
    }
    lines = [
        "# Integrated source-overhead 반복 성능 결과",
        "",
        "Standard T2X와 edge-selective의 Legacy/Post-pass/Integrated source를 같은 실행 조건에서 비교한다.",
        "세 edge-selective source 사이에서는 source만 바뀐다. Standard와 integrated 비교는 실제 semantic pipeline 비교이며 jitter/sampler/clipping/weight 차이도 포함하므로 candidate-only 효과가 아니다.",
        "",
    ]
    for case in result["cases"]:
        scene = case["scene"]
        timings = case["timings"]
        rates = case["frame_rates"]
        lines.extend(
            [
                f"## {scene}",
                "",
                "| Mode | Wall FPS | WholeFrame ms | SMAA ms | SMAA run σ ms |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for mode, _, _, _ in MODE_SPECS:
            lines.append(
                f"| `{mode}` | {rates[mode]['wall_average_fps']:.3f} "
                f"| {timings[mode]['WholeFrame']['mean_ms']:.6f} "
                f"| {timings[mode]['SMAA']['mean_ms']:.6f} "
                f"| {timings[mode]['SMAA']['run_mean_stddev_ms']:.6f} |"
            )
        lines.extend(
            [
                "",
                "### 핵심 효과",
                "",
                "| Reprojection | 비교 | WholeFrame | SMAA | Resolve |",
                "|---|---|---:|---:|---:|",
            ]
        )
        for reprojection in ("Off", "On"):
            for axis in (
                "Integrated vs Legacy",
                "Integrated vs Post-pass",
                "Integrated vs Standard semantic",
            ):
                whole = lookup[(scene, axis, reprojection, "WholeFrame")]
                smaa = lookup[(scene, axis, reprojection, "SMAA")]
                resolve_row = (
                    lookup.get((scene, axis, reprojection, "TSCMAAResolveCandidates"))
                )
                resolve_text = (
                    f"{resolve_row['delta_percent']:+.3f}%" if resolve_row else "-"
                )
                lines.append(
                    f"| {reprojection} | {axis} | {whole['delta_percent']:+.3f}% "
                    f"| {smaa['delta_percent']:+.3f}% | {resolve_text} |"
                )
        lines.append("")
    lines.extend(
        [
            "## 해석 규칙",
            "",
            "- Integrated vs Legacy/Post-pass는 candidate source 구조 변경 효과다.",
            "- Integrated vs Standard는 전체 semantic pipeline 차이이며 candidate selection 단독 효과로 표현하지 않는다.",
            "- candidate resolve 감소만으로 성공을 판정하지 않고 SMAA total과 WholeFrame의 방향·run 변동을 함께 본다.",
            "- 이 gate는 Original SMAA core 성능 판정이며 final Adaptive-inclusive 8-case 결과가 아니다.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    seen: set[str] = set()
    for scene, input_path in args.case:
        scene_key = scene.lower()
        if scene_key not in {"bistro", "minecraft"}:
            raise RuntimeError(f"unsupported scene: {scene}")
        if scene_key in seen:
            raise RuntimeError(f"duplicate scene: {scene}")
        seen.add(scene_key)
        source = Path(input_path).resolve()
        text, metadata, timings, frame_rates, counters = parse_results(source)
        validation = validate_case(
            scene_key,
            text,
            metadata,
            timings,
            frame_rates,
            counters,
            args.classification,
            args.expect_readback,
        )
        if not validation["pass"]:
            raise RuntimeError(f"{scene} validation failed: {validation['errors']}")
        label = "Bistro" if scene_key == "bistro" else "Minecraft"
        comparisons.extend(make_comparisons(label, timings))
        cases.append(
            {
                "scene": label,
                "source": str(source),
                "metadata": metadata,
                "validation": validation,
                "timings": timings,
                "frame_rates": frame_rates,
                "candidate_counters": counters,
            }
        )

    mode_rows: list[dict[str, Any]] = []
    for case in cases:
        for mode, source, reprojected, edge_selective in MODE_SPECS:
            timings = case["timings"]
            rate = case["frame_rates"][mode]
            row = {
                "scene": case["scene"],
                "mode": mode,
                "source": source,
                "reprojection": "On" if reprojected else "Off",
                "edge_selective": edge_selective,
                "wall_fps": rate["wall_average_fps"],
                "wall_1pct_low_fps": rate["wall_1pct_low_fps"],
                "whole_frame_ms": timings[mode]["WholeFrame"]["mean_ms"],
                "smaa_ms": timings[mode]["SMAA"]["mean_ms"],
                "smaa_run_mean_stddev_ms": timings[mode]["SMAA"][
                    "run_mean_stddev_ms"
                ],
                "samples": timings[mode]["SMAA"]["samples"],
                "runs": timings[mode]["SMAA"]["runs"],
            }
            for metric in required_metrics(source, reprojected, edge_selective):
                if metric in COMMON_METRICS:
                    continue
                row[f"{metric}_ms"] = timings[mode][metric]["mean_ms"]
            mode_rows.append(row)

    result = {
        "classification": args.classification,
        "window_state": args.window_state,
        "case_count": len(cases),
        "cases": cases,
        "comparisons": comparisons,
    }
    write_csv(output / "integrated_source_overhead_modes.csv", mode_rows)
    write_csv(output / "integrated_source_overhead_effects.csv", comparisons)
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "SMAA-Integrated-Source-Overhead-Performance-ko.md").write_text(
        build_markdown(result), encoding="utf-8"
    )
    print(
        f"VALIDATION=PASS cases={len(cases)} modes={len(mode_rows)} comparisons={len(comparisons)}"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
