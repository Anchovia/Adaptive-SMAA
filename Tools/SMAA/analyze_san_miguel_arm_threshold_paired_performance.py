#!/usr/bin/env python3
"""Validate the single-process paired ARM-threshold performance matrix."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


MODES = {
    "3x3": "ABL-Document-Dilate3x3-R",
    "ARM-0.10": "ABL-Document-ArmDual-R [threshold=0.10]",
    "ARM-0.15": "ABL-Document-ArmDual-R [threshold=0.15]",
    "ARM-0.20": "ABL-Document-ArmDual-R [threshold=0.20]",
    "ARM-0.25": "ABL-Document-ArmDual-R [threshold=0.25]",
}
ARM_PASSES = (
    "TSCMAAArmDualDownsampleHalf",
    "TSCMAAArmDualDownsampleQuarter",
    "TSCMAAArmDualUpsampleHalf",
    "TSCMAAArmDualUpsampleFull",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def percent(value: float, baseline: float) -> float:
    return (value / baseline - 1.0) * 100.0


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    expected_runs = int(manifest["repeats"])
    expected_samples = int(manifest["measure_frames"]) * expected_runs
    result_path = Path(manifest["result_csv"])
    rows = [
        [cell.strip() for cell in row]
        for row in csv.reader(result_path.open("r", encoding="utf-8-sig", newline=""))
    ]
    header = next(i for i, row in enumerate(rows) if row[:3] == ["Mode", "Timing metric", "Type"])
    timing: dict[str, dict[str, dict[str, float | int]]] = {
        mode_id: {} for mode_id in MODES.values()
    }
    for row in rows[header + 1:]:
        if row[:2] == ["Mode", "Counter samples"]:
            break
        if len(row) < 12 or row[0] not in timing:
            continue
        timing[row[0]][row[1]] = {
            "samples": int(row[3]),
            "mean_ms": float(row[4]),
            "runs": int(row[10]),
            "run_stddev_ms": float(row[11]),
        }

    for label, mode_id in MODES.items():
        required = {"WholeFrame", "SMAA", "TSCMAAResolveCandidates"}
        if label == "3x3":
            required.add("TSCMAADilateCandidates3x3")
        else:
            required.update(ARM_PASSES)
        if missing := sorted(required - set(timing[mode_id])):
            raise RuntimeError(f"{mode_id}: missing metrics {missing}")
        for metric in required:
            item = timing[mode_id][metric]
            if item["samples"] != expected_samples or item["runs"] != expected_runs:
                raise RuntimeError(f"{mode_id}/{metric}: invalid samples or runs")

    text = "\n".join(",".join(row) for row in rows)
    if "Candidate counter readback: disabled for timing isolation." not in text:
        raise RuntimeError("Candidate readback was not disabled")
    if "Performance benchmark validation: PASS" not in text:
        raise RuntimeError("Internal validation did not report PASS")

    baseline = timing[MODES["3x3"]]
    baseline_smaa = float(baseline["SMAA"]["mean_ms"])
    baseline_whole = float(baseline["WholeFrame"]["mean_ms"])
    results: list[dict[str, object]] = []
    for label, mode_id in MODES.items():
        mode = timing[mode_id]
        mask_ms = (
            float(mode["TSCMAADilateCandidates3x3"]["mean_ms"])
            if label == "3x3"
            else sum(float(mode[metric]["mean_ms"]) for metric in ARM_PASSES)
        )
        smaa = float(mode["SMAA"]["mean_ms"])
        whole = float(mode["WholeFrame"]["mean_ms"])
        results.append({
            "mode": label,
            "smaa_ms": smaa,
            "smaa_run_mean_stddev_ms": float(mode["SMAA"]["run_stddev_ms"]),
            "mask_ms": mask_ms,
            "candidate_resolve_ms": float(mode["TSCMAAResolveCandidates"]["mean_ms"]),
            "whole_frame_ms": whole,
            "smaa_vs_3x3_percent": 0.0 if label == "3x3" else percent(smaa, baseline_smaa),
            "whole_frame_vs_3x3_percent": 0.0 if label == "3x3" else percent(whole, baseline_whole),
        })

    output = (args.output or manifest_path.parent / "Analysis").resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "arm_threshold_paired_performance.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    validation = {
        "classification": manifest["classification"],
        "source": str(result_path),
        "samples_per_mode": expected_samples,
        "repeats": expected_runs,
        "candidate_statistics_readback": False,
        "internal_validation": "PASS",
        "mode_order_control": "alternating forward/reverse traversal inside one process",
    }
    (output / "arm_threshold_paired_performance_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# San Miguel ARM threshold single-process paired performance",
        "",
        f"- 분류: `{manifest['classification']}`",
        f"- 표본: mode당 `{expected_samples}` frames, `{expected_runs}` repeats",
        "- 3×3과 ARM 0.10/0.15/0.20/0.25를 한 프로세스에서 정방향/역방향 교차 순회",
        "- candidate statistics readback: `Off`",
        "- 내부 benchmark validation: `PASS`",
        "",
        "| Mode | SMAA ms | run-mean stddev | Mask ms | Resolve ms | vs 3×3 SMAA | WholeFrame ms | vs 3×3 WholeFrame |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            f"| {row['mode']} | {row['smaa_ms']:.6f} | {row['smaa_run_mean_stddev_ms']:.6f} | "
            f"{row['mask_ms']:.6f} | {row['candidate_resolve_ms']:.6f} | "
            f"{row['smaa_vs_3x3_percent']:+.3f}% | {row['whole_frame_ms']:.6f} | "
            f"{row['whole_frame_vs_3x3_percent']:+.3f}% |"
        )
    (output / "SMAA-SanMiguel-ARM-Threshold-Paired-Performance-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
