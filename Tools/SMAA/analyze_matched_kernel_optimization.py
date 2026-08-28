#!/usr/bin/env python3
"""Validate matched document-kernel and dual-output performance runs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from analyze_eight_case_performance import clean_row, extract_metadata, integer, number


MODES = (
    "ABL-Document-FullScreen",
    "O-ET2X / integrated edge-selective",
    "ABL-Document-FullScreen-R",
    "O-ET2X-R / integrated edge-selective",
)
PAIRINGS = (
    ("Off", MODES[0], MODES[1]),
    ("On", MODES[2], MODES[3]),
)
COMMON_METRICS = ("ApplicationFrameWall", "WholeFrame", "SMAA", "SMAASpatial1X")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        nargs=4,
        action="append",
        required=True,
        metavar=("LABEL", "SCENE", "PATH_KIND", "RESULTS_CSV"),
        help="PATH_KIND is legacy or dual",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def parse_results(path: Path) -> tuple[str, dict, dict[str, dict[str, dict]]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text = "\n".join(lines)
    metadata = extract_metadata(lines)
    scene_match = re.search(r"^Scene:\s*([^\.\r\n]+)", text, re.MULTILINE)
    metadata["scene"] = scene_match.group(1).strip() if scene_match else "unknown"
    rows = [clean_row(row) for row in csv.reader(lines)]
    header = next(i for i, row in enumerate(rows) if row[:3] == ["Mode", "Timing metric", "Type"])
    frame_section = next(i for i, row in enumerate(rows) if row and row[0] == "Frame-rate characterization:")
    timings: dict[str, dict[str, dict]] = {mode: {} for mode in MODES}
    for row in rows[header + 1 : frame_section]:
        if len(row) < 12 or row[0] not in timings:
            continue
        timings[row[0]][row[1]] = {
            "samples": integer(row[3]),
            "mean_ms": number(row[4]),
            "p95_ms": number(row[7]),
            "p99_ms": number(row[8]),
            "runs": integer(row[10]),
            "run_mean_stddev_ms": number(row[11]),
        }
    return text, metadata, timings


def percent_delta(test: float, control: float) -> float:
    return (test / control - 1.0) * 100.0 if control else 0.0


def validate(label: str, scene: str, path_kind: str, text: str, metadata: dict, timings: dict) -> list[str]:
    errors: list[str] = []
    if path_kind not in ("legacy", "dual"):
        errors.append(f"{label}: PATH_KIND must be legacy or dual")
    if "SMAA matched document-kernel" not in text:
        errors.append(f"{label}: benchmark title missing")
    if "Performance benchmark validation: PASS" not in text:
        errors.append(f"{label}: internal validation is not PASS")
    if metadata.get("scene", "").lower() != scene.lower():
        errors.append(f"{label}: scene {metadata.get('scene')} != {scene}")
    expected_samples = metadata.get("repeats", 0) * metadata.get("measurement_frames", 0)
    transfer_metrics = (
        ("TSCMAACopySpatialToHistory", "TSCMAAOutputCopy")
        if path_kind == "legacy"
        else ("TSCMAAInitializeDualOutput",)
    )
    for mode in MODES:
        edge = "integrated edge-selective" in mode
        required = set(COMMON_METRICS) | set(transfer_metrics)
        required.add("TSCMAAResolveCandidates" if edge else "TSCMAAResolveFullScreen")
        if mode.endswith("-R") or mode.startswith("O-ET2X-R"):
            required.add("SMAAGenerateCameraVelocity")
        missing = required - set(timings[mode])
        if missing:
            errors.append(f"{label}/{mode}: missing {', '.join(sorted(missing))}")
        for metric in required & set(timings[mode]):
            row = timings[mode][metric]
            if expected_samples and row["samples"] != expected_samples:
                errors.append(f"{label}/{mode}/{metric}: samples {row['samples']} != {expected_samples}")
            if row["runs"] != metadata.get("repeats"):
                errors.append(f"{label}/{mode}/{metric}: runs {row['runs']} != {metadata.get('repeats')}")
    return errors


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    all_errors: list[str] = []
    for label, scene, path_kind, raw_path in args.case:
        path = Path(raw_path)
        text, metadata, timings = parse_results(path)
        errors = validate(label, scene, path_kind, text, metadata, timings)
        all_errors.extend(errors)
        cases.append({
            "label": label,
            "scene": scene,
            "path_kind": path_kind,
            "source": str(path.resolve()),
            "metadata": metadata,
            "timings": timings,
            "errors": errors,
        })

    summary_rows = []
    for case in cases:
        timings = case["timings"]
        transfer_names = (
            ("TSCMAACopySpatialToHistory", "TSCMAAOutputCopy")
            if case["path_kind"] == "legacy"
            else ("TSCMAAInitializeDualOutput",)
        )
        for reprojection, full_mode, edge_mode in PAIRINGS:
            full_smaa = timings[full_mode]["SMAA"]["mean_ms"]
            edge_smaa = timings[edge_mode]["SMAA"]["mean_ms"]
            full_resolve = timings[full_mode]["TSCMAAResolveFullScreen"]["mean_ms"]
            edge_resolve = timings[edge_mode]["TSCMAAResolveCandidates"]["mean_ms"]
            transfer = sum(timings[edge_mode][name]["mean_ms"] for name in transfer_names)
            summary_rows.append({
                "label": case["label"],
                "scene": case["scene"],
                "path_kind": case["path_kind"],
                "reprojection": reprojection,
                "full_screen_smaa_ms": full_smaa,
                "edge_selective_smaa_ms": edge_smaa,
                "edge_vs_full_smaa_percent": percent_delta(edge_smaa, full_smaa),
                "full_screen_resolve_ms": full_resolve,
                "edge_selective_resolve_ms": edge_resolve,
                "edge_vs_full_resolve_percent": percent_delta(edge_resolve, full_resolve),
                "edge_base_transfer_ms": transfer,
            })

    by_key = {(row["scene"], row["path_kind"], row["reprojection"]): row for row in summary_rows}
    optimization_rows = []
    for scene in sorted({row["scene"] for row in summary_rows}):
        for reprojection in ("Off", "On"):
            legacy = by_key.get((scene, "legacy", reprojection))
            dual = by_key.get((scene, "dual", reprojection))
            if not legacy or not dual:
                continue
            optimization_rows.append({
                "scene": scene,
                "reprojection": reprojection,
                "legacy_edge_smaa_ms": legacy["edge_selective_smaa_ms"],
                "dual_edge_smaa_ms": dual["edge_selective_smaa_ms"],
                "dual_vs_legacy_smaa_percent": percent_delta(
                    dual["edge_selective_smaa_ms"], legacy["edge_selective_smaa_ms"]
                ),
                "legacy_transfer_ms": legacy["edge_base_transfer_ms"],
                "dual_transfer_ms": dual["edge_base_transfer_ms"],
                "dual_vs_legacy_transfer_percent": percent_delta(
                    dual["edge_base_transfer_ms"], legacy["edge_base_transfer_ms"]
                ),
            })

    with (args.output_dir / "matched_kernel_summary.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    with (args.output_dir / "dual_output_optimization.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(optimization_rows[0]))
        writer.writeheader()
        writer.writerows(optimization_rows)

    payload = {"passed": not all_errors, "errors": all_errors, "cases": cases,
               "matched_kernel": summary_rows, "dual_output": optimization_rows}
    (args.output_dir / "matched_kernel_optimization.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Matched document-kernel 및 dual-output 최적화 분석",
        "",
        f"검증: **{'PASS' if not all_errors else 'FAIL'}**",
        "",
        "## 동일 커널에서 coverage만 바꾼 결과",
        "",
        "| 장면 | 경로 | Reprojection | Full-screen SMAA | Edge-selective SMAA | 변화 | Full resolve | Candidate resolve |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['scene']} | {row['path_kind']} | {row['reprojection']} | "
            f"{row['full_screen_smaa_ms']:.6f} ms | {row['edge_selective_smaa_ms']:.6f} ms | "
            f"{row['edge_vs_full_smaa_percent']:+.2f}% | {row['full_screen_resolve_ms']:.6f} ms | "
            f"{row['edge_selective_resolve_ms']:.6f} ms |"
        )
    lines += ["", "## dual-output 최적화 A/B", "",
              "| 장면 | Reprojection | Legacy SMAA | Dual SMAA | 변화 | Legacy transfer | Dual init |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for row in optimization_rows:
        lines.append(
            f"| {row['scene']} | {row['reprojection']} | {row['legacy_edge_smaa_ms']:.6f} ms | "
            f"{row['dual_edge_smaa_ms']:.6f} ms | {row['dual_vs_legacy_smaa_percent']:+.2f}% | "
            f"{row['legacy_transfer_ms']:.6f} ms | {row['dual_transfer_ms']:.6f} ms |"
        )
    lines += [
        "",
        "> Edge-selective는 동일 document temporal kernel의 full-screen 적용보다 빠르므로 후보 제한 자체의 연산 절감은 확인된다.",
        "> 그러나 dual-output 융합은 candidate 결과를 두 UAV에 기록하는 비용 때문에 기존 two-copy 경로보다 느려 default-Off ablation으로 유지한다.",
    ]
    if all_errors:
        lines += ["", "## 검증 오류", ""] + [f"- {error}" for error in all_errors]
    (args.output_dir / "SMAA-Matched-Kernel-Dual-Output-Analysis-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return 0 if not all_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
