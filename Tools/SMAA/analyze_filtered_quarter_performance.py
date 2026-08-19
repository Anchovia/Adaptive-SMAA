#!/usr/bin/env python3
"""Validate and summarize the filtered-quarter candidate-expansion benchmark."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


MODES = (
    "O-ET2X-R-Document",
    "ABL-Document-Dilate3x3-R",
    "ABL-Document-FilteredQuarter-R",
    "ABL-Candidate-Jitter-R",
    "ABL-Candidate-Jitter-Dilate3x3-R",
    "ABL-Candidate-Jitter-FilteredQuarter-R",
)
PROFILES = {
    "Document": MODES[0:3],
    "Candidate-Jitter": MODES[3:6],
}
COMMON_METRICS = (
    "ApplicationFrameWall",
    "WholeFrame",
    "SMAA",
    "SMAAGenerateCameraVelocity",
    "SMAASpatial1X",
    "TSCMAACopySpatialToHistory",
    "TSCMAAPrepareCandidates",
    "TSCMAAExtractCandidates",
    "TSCMAAComputeDispatchArgs",
    "TSCMAAResolveCandidates",
    "TSCMAAOutputCopy",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_csv", type=Path)
    parser.add_argument("--expected-frames", type=int, required=True)
    parser.add_argument("--expected-repeats", type=int, required=True)
    parser.add_argument(
        "--classification", choices=("engineering", "formal"), default="engineering"
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def percent(value: float, baseline: float) -> float:
    return (value / baseline - 1.0) * 100.0


def main() -> int:
    args = parse_args()
    source = args.result_csv.resolve()
    rows = [
        [cell.strip() for cell in row]
        for row in csv.reader(source.open("r", encoding="utf-8-sig", newline=""))
    ]
    timing_header = next(
        i for i, row in enumerate(rows) if row[:3] == ["Mode", "Timing metric", "Type"]
    )
    timing: dict[str, dict[str, dict[str, float | int]]] = {mode: {} for mode in MODES}
    index = timing_header + 1
    while index < len(rows) and rows[index] and rows[index][0] in timing:
        row = rows[index]
        timing[row[0]][row[1]] = {
            "samples": int(row[3]),
            "mean_ms": float(row[4]),
            "run_count": int(row[10]),
            "run_mean_stddev_ms": float(row[11]),
        }
        index += 1

    expected_samples = args.expected_frames * args.expected_repeats
    for mode in MODES:
        required = list(COMMON_METRICS)
        if "Dilate3x3" in mode:
            required.append("TSCMAADilateCandidates3x3")
        if "FilteredQuarter" in mode:
            required.extend(
                (
                    "TSCMAAFilteredQuarterDownsample",
                    "TSCMAAFilteredQuarterUpsample",
                )
            )
        missing = [metric for metric in required if metric not in timing[mode]]
        if missing:
            raise RuntimeError(f"{mode}: missing timing metrics {missing}")
        for metric in required:
            item = timing[mode][metric]
            if item["samples"] != expected_samples:
                raise RuntimeError(
                    f"{mode}/{metric}: expected {expected_samples} samples, "
                    f"found {item['samples']}"
                )
            if item["run_count"] != args.expected_repeats:
                raise RuntimeError(
                    f"{mode}/{metric}: expected {args.expected_repeats} runs, "
                    f"found {item['run_count']}"
                )

    candidate_header = next(
        (i for i, row in enumerate(rows) if row[:2] == ["Mode", "Counter samples"]),
        None,
    )
    candidates: dict[str, dict[str, float | int]] = {}
    if candidate_header is not None:
        index = candidate_header + 1
        while index < len(rows) and rows[index] and rows[index][0] in MODES:
            row = rows[index]
            candidates[row[0]] = {
                "samples": int(row[1]),
                "base_edges": float(row[2]),
                "candidates": float(row[3]),
                "process_count": float(row[4]),
                "candidate_per_base": float(row[5]),
            }
            index += 1

    flat_text = "\n".join(",".join(row) for row in rows)
    if "Performance benchmark validation: PASS" not in flat_text:
        raise RuntimeError("Internal benchmark validation did not report PASS")

    comparisons: list[dict[str, float | str]] = []
    for profile, (base, dilated, filtered) in PROFILES.items():
        base_smaa = float(timing[base]["SMAA"]["mean_ms"])
        dilated_smaa = float(timing[dilated]["SMAA"]["mean_ms"])
        filtered_smaa = float(timing[filtered]["SMAA"]["mean_ms"])
        dilate_cost = float(
            timing[dilated]["TSCMAADilateCandidates3x3"]["mean_ms"]
        )
        filtered_down = float(
            timing[filtered]["TSCMAAFilteredQuarterDownsample"]["mean_ms"]
        )
        filtered_up = float(
            timing[filtered]["TSCMAAFilteredQuarterUpsample"]["mean_ms"]
        )
        item: dict[str, float | str] = {
            "profile": profile,
            "base_smaa_ms": base_smaa,
            "dilate3x3_smaa_ms": dilated_smaa,
            "filtered_smaa_ms": filtered_smaa,
            "dilate3x3_vs_base_smaa_percent": percent(dilated_smaa, base_smaa),
            "filtered_vs_base_smaa_percent": percent(filtered_smaa, base_smaa),
            "filtered_vs_dilate3x3_smaa_percent": percent(
                filtered_smaa, dilated_smaa
            ),
            "dilate3x3_mask_ms": dilate_cost,
            "filtered_downsample_ms": filtered_down,
            "filtered_upsample_ms": filtered_up,
            "filtered_mask_total_ms": filtered_down + filtered_up,
            "filtered_vs_dilate3x3_mask_percent": percent(
                filtered_down + filtered_up, dilate_cost
            ),
        }
        if candidates:
            raw_count = float(candidates[base]["candidates"])
            item.update(
                {
                    "raw_candidates": raw_count,
                    "dilate3x3_candidates": float(candidates[dilated]["candidates"]),
                    "filtered_candidates": float(candidates[filtered]["candidates"]),
                    "dilate3x3_candidate_multiplier": float(
                        candidates[dilated]["candidates"]
                    )
                    / raw_count,
                    "filtered_candidate_multiplier": float(
                        candidates[filtered]["candidates"]
                    )
                    / raw_count,
                }
            )
        comparisons.append(item)

    output = (args.output or source.parent / "Analysis-FilteredQuarter-Performance").resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "filtered_quarter_performance.json").write_text(
        json.dumps(
            {
                "source": str(source),
                "classification": args.classification,
                "expected_frames": args.expected_frames,
                "expected_repeats": args.expected_repeats,
                "internal_validation": "PASS",
                "comparisons": comparisons,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (output / "filtered_quarter_performance.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)

    lines = [
        "# Filtered 1/4 후보 확장 성능 분석",
        "",
        f"- 분류: `{args.classification}`",
        f"- 표본: mode당 {expected_samples} frame, {args.expected_repeats}회 반복",
        "- 내부 benchmark validation: `PASS`",
        "",
        "| Profile | 3×3 후보 배수 | Filtered 후보 배수 | 3×3 mask ms | Filtered mask ms | 3×3 SMAA 변화 | Filtered SMAA 변화 | Filtered vs 3×3 SMAA |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in comparisons:
        lines.append(
            "| {profile} | {dilate:.3f}× | {filtered:.3f}× | {dmask:.6f} | "
            "{fmask:.6f} | {dsmaa:+.3f}% | {fsmaa:+.3f}% | {fd:+.3f}% |".format(
                profile=item["profile"],
                dilate=item.get("dilate3x3_candidate_multiplier", float("nan")),
                filtered=item.get("filtered_candidate_multiplier", float("nan")),
                dmask=item["dilate3x3_mask_ms"],
                fmask=item["filtered_mask_total_ms"],
                dsmaa=item["dilate3x3_vs_base_smaa_percent"],
                fsmaa=item["filtered_vs_base_smaa_percent"],
                fd=item["filtered_vs_dilate3x3_smaa_percent"],
            )
        )
    lines.extend(
        (
            "",
            "## 해석 제한",
            "",
            "이 도구는 구현·engineering 성능을 검증한다. 단일 smoke 수치는 정식 성능 우열이나 통계적 유의성을 의미하지 않는다.",
        )
    )
    (output / "SMAA-Filtered-Quarter-Performance-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
