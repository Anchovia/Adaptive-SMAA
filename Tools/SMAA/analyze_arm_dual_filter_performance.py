#!/usr/bin/env python3
"""Validate and summarize the ARM Dual Filtering performance gate."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


MODES = (
    "O-ET2X-R-Document",
    "ABL-Document-Dilate3x3-R",
    "ABL-Document-FilteredQuarter-R",
    "ABL-Document-ArmDual-R",
    "ABL-Candidate-Jitter-R",
    "ABL-Candidate-Jitter-Dilate3x3-R",
    "ABL-Candidate-Jitter-FilteredQuarter-R",
    "ABL-Candidate-Jitter-ArmDual-R",
)
PROFILES = {"Document": MODES[0:4], "Candidate-Jitter": MODES[4:8]}
COMMON = (
    "ApplicationFrameWall", "WholeFrame", "SMAA", "SMAAGenerateCameraVelocity",
    "SMAASpatial1X", "TSCMAACopySpatialToHistory", "TSCMAAPrepareCandidates",
    "TSCMAAExtractCandidates", "TSCMAAComputeDispatchArgs",
    "TSCMAAResolveCandidates", "TSCMAAOutputCopy",
)
ARM_METRICS = (
    "TSCMAAArmDualDownsampleHalf", "TSCMAAArmDualDownsampleQuarter",
    "TSCMAAArmDualUpsampleHalf", "TSCMAAArmDualUpsampleFull",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_csv", type=Path)
    parser.add_argument("--expected-frames", type=int, required=True)
    parser.add_argument("--expected-repeats", type=int, required=True)
    parser.add_argument("--classification", choices=("engineering", "formal"), default="engineering")
    parser.add_argument("--candidate-result-csv", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def percent(value: float, baseline: float) -> float:
    return (value / baseline - 1.0) * 100.0


def main() -> int:
    args = parse_args()
    source = args.result_csv.resolve()
    rows = [[cell.strip() for cell in row] for row in csv.reader(source.open("r", encoding="utf-8-sig", newline=""))]
    header = next(i for i, row in enumerate(rows) if row[:3] == ["Mode", "Timing metric", "Type"])
    timing: dict[str, dict[str, dict[str, float | int]]] = {mode: {} for mode in MODES}
    index = header + 1
    while index < len(rows) and rows[index] and rows[index][0] in timing:
        row = rows[index]
        timing[row[0]][row[1]] = {
            "samples": int(row[3]), "mean_ms": float(row[4]),
            "runs": int(row[10]), "run_stddev_ms": float(row[11]),
        }
        index += 1
    expected_samples = args.expected_frames * args.expected_repeats
    for mode in MODES:
        required = list(COMMON)
        if "Dilate3x3" in mode:
            required.append("TSCMAADilateCandidates3x3")
        if "FilteredQuarter" in mode:
            required.extend(("TSCMAAFilteredQuarterDownsample", "TSCMAAFilteredQuarterUpsample"))
        if "ArmDual" in mode:
            required.extend(ARM_METRICS)
        missing = [metric for metric in required if metric not in timing[mode]]
        if missing:
            raise RuntimeError(f"{mode}: missing metrics {missing}")
        for metric in required:
            item = timing[mode][metric]
            if item["samples"] != expected_samples or item["runs"] != args.expected_repeats:
                raise RuntimeError(f"{mode}/{metric}: invalid sample or run count")

    candidate_rows = rows
    if args.candidate_result_csv is not None:
        candidate_rows = [
            [cell.strip() for cell in row]
            for row in csv.reader(
                args.candidate_result_csv.resolve().open(
                    "r", encoding="utf-8-sig", newline=""
                )
            )
        ]
    candidate_header = next(i for i, row in enumerate(candidate_rows) if row[:2] == ["Mode", "Counter samples"])
    candidates: dict[str, dict[str, float]] = {}
    index = candidate_header + 1
    while index < len(candidate_rows) and candidate_rows[index] and candidate_rows[index][0] in timing:
        row = candidate_rows[index]
        candidates[row[0]] = {
            "samples": float(row[1]), "base": float(row[2]),
            "candidate": float(row[3]), "process": float(row[4]),
        }
        index += 1
    if set(candidates) != set(MODES):
        raise RuntimeError("Candidate readback rows are incomplete")
    if "Performance benchmark validation: PASS" not in "\n".join(",".join(row) for row in rows):
        raise RuntimeError("Internal validation did not report PASS")

    comparisons = []
    for profile, (base, dilated, filtered, arm) in PROFILES.items():
        base_smaa = float(timing[base]["SMAA"]["mean_ms"])
        dilated_smaa = float(timing[dilated]["SMAA"]["mean_ms"])
        filtered_smaa = float(timing[filtered]["SMAA"]["mean_ms"])
        arm_smaa = float(timing[arm]["SMAA"]["mean_ms"])
        dilated_mask = float(timing[dilated]["TSCMAADilateCandidates3x3"]["mean_ms"])
        filtered_mask = sum(float(timing[filtered][metric]["mean_ms"]) for metric in ("TSCMAAFilteredQuarterDownsample", "TSCMAAFilteredQuarterUpsample"))
        arm_passes = {metric: float(timing[arm][metric]["mean_ms"]) for metric in ARM_METRICS}
        arm_mask = sum(arm_passes.values())
        raw_candidates = candidates[base]["candidate"]
        if any(abs(item["candidate"] - item["process"]) > 0.001 for item in candidates.values()):
            raise RuntimeError("Candidate/process counter mismatch")
        comparisons.append({
            "profile": profile,
            "raw_candidates": raw_candidates,
            "dilate3x3_candidate_multiplier": candidates[dilated]["candidate"] / raw_candidates,
            "filtered_candidate_multiplier": candidates[filtered]["candidate"] / raw_candidates,
            "arm_dual_candidate_multiplier": candidates[arm]["candidate"] / raw_candidates,
            "base_smaa_ms": base_smaa,
            "dilate3x3_smaa_ms": dilated_smaa,
            "filtered_smaa_ms": filtered_smaa,
            "arm_dual_smaa_ms": arm_smaa,
            "dilate3x3_vs_base_smaa_percent": percent(dilated_smaa, base_smaa),
            "filtered_vs_base_smaa_percent": percent(filtered_smaa, base_smaa),
            "arm_dual_vs_base_smaa_percent": percent(arm_smaa, base_smaa),
            "arm_dual_vs_dilate3x3_smaa_percent": percent(arm_smaa, dilated_smaa),
            "arm_dual_vs_filtered_smaa_percent": percent(arm_smaa, filtered_smaa),
            "dilate3x3_mask_ms": dilated_mask,
            "filtered_mask_ms": filtered_mask,
            "arm_dual_mask_ms": arm_mask,
            **{metric: value for metric, value in arm_passes.items()},
        })

    output = (args.output or source.parent / "Analysis-ARM-Dual-Performance").resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "arm_dual_performance.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    (output / "arm_dual_performance.json").write_text(json.dumps({
        "source": str(source), "classification": args.classification,
        "expected_frames": args.expected_frames, "expected_repeats": args.expected_repeats,
        "candidate_readback": "separate characterization" if args.candidate_result_csv else "enabled",
        "candidate_result_csv": str(args.candidate_result_csv.resolve()) if args.candidate_result_csv else str(source),
        "internal_validation": "PASS",
        "comparisons": comparisons,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# ARM Dual Filtering 후보 확장 성능 분석",
        "",
        f"- 분류: `{args.classification}`",
        f"- 표본: mode당 {expected_samples} frame, {args.expected_repeats}회",
        "- timing 실행의 candidate readback: `Off`; 후보 배수는 별도 readback-On characterization에서 결합" if args.candidate_result_csv else "- candidate readback: `On`; 정식 timing 결과가 아닌 engineering smoke",
        "- 내부 benchmark validation: `PASS`",
        "",
        "| Profile | 3×3 후보 배수 | Filtered 후보 배수 | ARM 후보 배수 | 3×3 mask ms | Filtered mask ms | ARM mask ms | 3×3 SMAA 변화 | Filtered SMAA 변화 | ARM SMAA 변화 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in comparisons:
        lines.append(
            f"| {item['profile']} | {item['dilate3x3_candidate_multiplier']:.3f}× | "
            f"{item['filtered_candidate_multiplier']:.3f}× | {item['arm_dual_candidate_multiplier']:.3f}× | "
            f"{item['dilate3x3_mask_ms']:.6f} | {item['filtered_mask_ms']:.6f} | {item['arm_dual_mask_ms']:.6f} | "
            f"{item['dilate3x3_vs_base_smaa_percent']:+.3f}% | {item['filtered_vs_base_smaa_percent']:+.3f}% | "
            f"{item['arm_dual_vs_base_smaa_percent']:+.3f}% |"
        )
    lines.extend((
        "", "## 해석 제한", "",
        f"{expected_samples}-frame engineering 측정이며 반복은 {args.expected_repeats}회다. "
        "pass 실행과 상대 비용 구조를 확인하는 결과일 뿐 정식 성능 우열이나 "
        "통계적 유의성을 뜻하지 않는다."
    ))
    (output / "SMAA-ARM-Dual-Performance-Smoke-ko.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
