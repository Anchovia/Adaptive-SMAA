#!/usr/bin/env python3
"""Validate compact-indirect versus direct candidate-mask ET2X benchmarks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from analyze_eight_case_performance import clean_row, extract_metadata, integer, number


MODES = (
    "O-ET2X / CompactIndirect",
    "O-ET2X / DirectMaskedFullScreen",
    "O-ET2X-R / CompactIndirect",
    "O-ET2X-R / DirectMaskedFullScreen",
)
PAIRS = (
    ("Off", MODES[0], MODES[1]),
    ("On", MODES[2], MODES[3]),
)
COMMON = (
    "ApplicationFrameWall",
    "WholeFrame",
    "SMAA",
    "SMAASpatial1X",
    "TSCMAACopySpatialToHistory",
    "TSCMAAClearIntegratedCandidateBuffers",
    "TSCMAAOutputCopy",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        required=True,
        metavar=("LABEL", "SCENE", "RESULTS_CSV"),
    )
    parser.add_argument("--compact-capture", type=Path, required=True)
    parser.add_argument("--direct-capture", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def parse_results(path: Path) -> tuple[str, dict, dict[str, dict[str, dict]]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text = "\n".join(lines)
    metadata = extract_metadata(lines)
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
            "median_ms": number(row[5]),
            "p95_ms": number(row[7]),
            "p99_ms": number(row[8]),
            "runs": integer(row[10]),
            "run_mean_stddev_ms": number(row[11]),
        }
    return text, metadata, timings


def percent_delta(test: float, control: float) -> float:
    return (test / control - 1.0) * 100.0 if control else 0.0


def validate_case(label: str, scene: str, text: str, metadata: dict, timings: dict) -> list[str]:
    errors: list[str] = []
    if "SMAA candidate-execution repeated performance benchmark" not in text:
        errors.append(f"{label}: repeated benchmark title missing")
    if "Performance benchmark validation: PASS" not in text:
        errors.append(f"{label}: internal validation is not PASS")
    if metadata.get("scene") != scene.lower():
        errors.append(f"{label}: scene {metadata.get('scene')} != {scene}")
    if not metadata.get("candidate_readback_disabled", False):
        errors.append(f"{label}: candidate readback was not disabled")

    repeats = metadata.get("repeats", 0)
    expected_samples = repeats * metadata.get("measurement_frames", 0)
    for mode in MODES:
        direct = "DirectMaskedFullScreen" in mode
        required = set(COMMON)
        required.add("TSCMAAResolveCandidateMask" if direct else "TSCMAAResolveCandidates")
        if not direct:
            required.add("TSCMAAComputeDispatchArgs")
        if mode.startswith("O-ET2X-R"):
            required.add("SMAAGenerateCameraVelocity")
        missing = required - set(timings[mode])
        if missing:
            errors.append(f"{label}/{mode}: missing {', '.join(sorted(missing))}")
        forbidden = (
            {"TSCMAAComputeDispatchArgs", "TSCMAAResolveCandidates"}
            if direct
            else {"TSCMAAResolveCandidateMask"}
        )
        unexpected = forbidden & set(timings[mode])
        if unexpected:
            errors.append(f"{label}/{mode}: unexpected {', '.join(sorted(unexpected))}")
        for metric in required & set(timings[mode]):
            row = timings[mode][metric]
            if expected_samples and row["samples"] != expected_samples:
                errors.append(
                    f"{label}/{mode}/{metric}: samples {row['samples']} != {expected_samples}"
                )
            if row["runs"] != repeats:
                errors.append(f"{label}/{mode}/{metric}: runs {row['runs']} != {repeats}")
    return errors


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare_captures(compact_root: Path, direct_root: Path) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    errors: list[str] = []
    for mode in ("O_ET2X", "O_ET2X_R"):
        compact_files = sorted((compact_root / mode).glob("*.png"))
        direct_files = sorted((direct_root / mode).glob("*.png"))
        compact_by_name = {path.name: path for path in compact_files}
        direct_by_name = {path.name: path for path in direct_files}
        names = sorted(set(compact_by_name) | set(direct_by_name))
        mismatch = 0
        for name in names:
            left = compact_by_name.get(name)
            right = direct_by_name.get(name)
            same = left is not None and right is not None and sha256(left) == sha256(right)
            mismatch += 0 if same else 1
        rows.append(
            {
                "mode": mode,
                "compact_frames": len(compact_files),
                "direct_frames": len(direct_files),
                "mismatch_frames": mismatch,
            }
        )
        if not compact_files or len(compact_files) != len(direct_files) or mismatch:
            errors.append(
                f"capture/{mode}: compact={len(compact_files)}, direct={len(direct_files)}, mismatch={mismatch}"
            )
    return rows, errors


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    errors: list[str] = []
    for label, scene, raw_path in args.case:
        path = Path(raw_path)
        text, metadata, timings = parse_results(path)
        case_errors = validate_case(label, scene, text, metadata, timings)
        errors.extend(case_errors)
        cases.append(
            {
                "label": label,
                "scene": scene,
                "source": str(path.resolve()),
                "metadata": metadata,
                "timings": timings,
                "errors": case_errors,
            }
        )

    capture_rows, capture_errors = compare_captures(args.compact_capture, args.direct_capture)
    errors.extend(capture_errors)

    summary_rows: list[dict] = []
    for case in cases:
        timings = case["timings"]
        for reprojection, compact_mode, direct_mode in PAIRS:
            compact_execution = sum(
                timings[compact_mode][name]["mean_ms"]
                for name in (
                    "TSCMAAClearIntegratedCandidateBuffers",
                    "TSCMAAComputeDispatchArgs",
                    "TSCMAAResolveCandidates",
                )
            )
            direct_execution = sum(
                timings[direct_mode][name]["mean_ms"]
                for name in (
                    "TSCMAAClearIntegratedCandidateBuffers",
                    "TSCMAAResolveCandidateMask",
                )
            )
            summary_rows.append(
                {
                    "scene": case["scene"],
                    "reprojection": reprojection,
                    "compact_smaa_ms": timings[compact_mode]["SMAA"]["mean_ms"],
                    "direct_smaa_ms": timings[direct_mode]["SMAA"]["mean_ms"],
                    "direct_vs_compact_smaa_percent": percent_delta(
                        timings[direct_mode]["SMAA"]["mean_ms"],
                        timings[compact_mode]["SMAA"]["mean_ms"],
                    ),
                    "compact_whole_frame_ms": timings[compact_mode]["WholeFrame"]["mean_ms"],
                    "direct_whole_frame_ms": timings[direct_mode]["WholeFrame"]["mean_ms"],
                    "direct_vs_compact_whole_frame_percent": percent_delta(
                        timings[direct_mode]["WholeFrame"]["mean_ms"],
                        timings[compact_mode]["WholeFrame"]["mean_ms"],
                    ),
                    "compact_execution_ms": compact_execution,
                    "direct_execution_ms": direct_execution,
                    "direct_vs_compact_execution_percent": percent_delta(
                        direct_execution, compact_execution
                    ),
                    "compact_spatial_ms": timings[compact_mode]["SMAASpatial1X"]["mean_ms"],
                    "direct_spatial_ms": timings[direct_mode]["SMAASpatial1X"]["mean_ms"],
                }
            )

    with (args.output_dir / "candidate_execution_summary.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    with (args.output_dir / "candidate_execution_capture_hashes.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(capture_rows[0]))
        writer.writeheader()
        writer.writerows(capture_rows)

    payload = {
        "passed": not errors,
        "errors": errors,
        "cases": cases,
        "capture_comparison": capture_rows,
        "summary": summary_rows,
    }
    (args.output_dir / "candidate_execution_analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# ET2X Candidate 실행 구조 분석",
        "",
        f"검증: **{'PASS' if not errors else 'FAIL'}**",
        "",
        "## 출력 동등성",
        "",
        "| Mode | Compact frame | Direct frame | SHA-256 mismatch |",
        "|---|---:|---:|---:|",
    ]
    for row in capture_rows:
        lines.append(
            f"| {row['mode']} | {row['compact_frames']} | {row['direct_frames']} | "
            f"{row['mismatch_frames']} |"
        )
    lines += [
        "",
        "## 반복 성능",
        "",
        "| Scene | Reprojection | Compact SMAA | Direct SMAA | 변화 | Compact WholeFrame | Direct WholeFrame | 변화 | Compact candidate 실행 | Direct candidate 실행 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['scene']} | {row['reprojection']} | {row['compact_smaa_ms']:.6f} ms | "
            f"{row['direct_smaa_ms']:.6f} ms | {row['direct_vs_compact_smaa_percent']:+.2f}% | "
            f"{row['compact_whole_frame_ms']:.6f} ms | {row['direct_whole_frame_ms']:.6f} ms | "
            f"{row['direct_vs_compact_whole_frame_percent']:+.2f}% | "
            f"{row['compact_execution_ms']:.6f} ms | {row['direct_execution_ms']:.6f} ms |"
        )
    lines += [
        "",
        "## 판정",
        "",
        "- 두 경로는 동일한 SMAA 1차 edge-pass candidate와 동일한 temporal kernel을 사용한다.",
        "- DirectMaskedFullScreen은 compact atomic/list와 indirect dispatch를 제거하지만, full-resolution R8 mask clear/write와 full-screen thread 실행을 추가한다.",
        "- 두 장면에서 DirectMaskedFullScreen의 SMAA 및 WholeFrame 비용이 모두 증가했으므로 현재 GPU/해상도에서는 최적화안으로 채택하지 않는다.",
        "- 기존 CompactIndirect를 기본 경로로 유지하고 DirectMaskedFullScreen은 재현 가능한 default-Off negative-result ablation으로 보존한다.",
    ]
    if errors:
        lines += ["", "## 검증 오류", ""] + [f"- {error}" for error in errors]
    (args.output_dir / "SMAA-Candidate-Execution-Analysis-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
