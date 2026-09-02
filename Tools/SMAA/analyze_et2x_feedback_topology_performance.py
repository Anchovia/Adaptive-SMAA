#!/usr/bin/env python3
"""Validate and summarize formal ET2X feedback-topology GPU benchmarks."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from analyze_eight_case_performance import clean_row, extract_metadata, integer, number


RESOLVED = "O-ET2X-R / ResolvedOutput"
SPATIAL = "ABL-ET2X-SpatialFeedback-R"
MODES = (RESOLVED, SPATIAL)
FORMAL_SCENES = {"bistro": "Bistro", "minecraft": "Minecraft"}
FORMAL_GPU = "NVIDIA GeForce RTX 3060 Ti"
FORMAL_API = "DirectX11"
FORMAL_RESOLUTION = "1920 x 1017"
COMMON = (
    "ApplicationFrameWall",
    "WholeFrame",
    "SMAA",
    "SMAAGenerateCameraVelocity",
    "SMAASpatial1X",
    "TSCMAACopySpatialToHistory",
    "TSCMAAClearIntegratedCandidateBuffers",
    "TSCMAAComputeDispatchArgs",
    "TSCMAAResolveCandidates",
    "TSCMAAOutputCopy",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        required=True,
        metavar=("LABEL", "SCENE", "RESULTS_CSV"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def parse_results(path: Path) -> tuple[str, dict, dict[str, dict[str, dict]]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text = "\n".join(lines)
    metadata = extract_metadata(lines)
    rows = [clean_row(row) for row in csv.reader(lines)]
    header = next(
        index
        for index, row in enumerate(rows)
        if row[:3] == ["Mode", "Timing metric", "Type"]
    )
    frame_section = next(
        index
        for index, row in enumerate(rows)
        if row and row[0] == "Frame-rate characterization:"
    )
    timings: dict[str, dict[str, dict]] = {mode: {} for mode in MODES}
    for row in rows[header + 1 : frame_section]:
        if len(row) < 12 or row[0] not in timings:
            continue
        timings[row[0]][row[1]] = {
            "samples": integer(row[3]),
            "mean_ms": number(row[4]),
            "median_ms": number(row[5]),
            "frame_stddev_ms": number(row[6]),
            "p95_ms": number(row[7]),
            "p99_ms": number(row[8]),
            "runs": integer(row[10]),
            "run_mean_stddev_ms": number(row[11]),
        }
    return text, metadata, timings


def percent_delta(test: float, control: float) -> float:
    return (test / control - 1.0) * 100.0 if control else 0.0


def validate_case(
    label: str, scene: str, text: str, metadata: dict, timings: dict
) -> list[str]:
    errors: list[str] = []
    if "SMAA integrated ET2X feedback-topology repeated performance benchmark" not in text:
        errors.append(f"{label}: repeated benchmark title missing")
    if "Performance benchmark validation: PASS" not in text:
        errors.append(f"{label}: internal validation is not PASS")
    if metadata.get("scene") != scene.lower():
        errors.append(f"{label}: scene {metadata.get('scene')} != {scene}")
    if FORMAL_GPU not in str(metadata.get("system_info", "")):
        errors.append(
            f"{label}: expected GPU {FORMAL_GPU}, got "
            f"{metadata.get('system_info', 'missing system info')}"
        )
    if metadata.get("api") != FORMAL_API:
        errors.append(
            f"{label}: API {metadata.get('api')!r} != {FORMAL_API!r}"
        )
    resolution = " ".join(str(metadata.get("resolution", "")).split())
    if resolution != FORMAL_RESOLUTION:
        errors.append(
            f"{label}: resolution {resolution!r} != {FORMAL_RESOLUTION!r}"
        )
    if str(metadata.get("vsync", "")).upper() != "OFF":
        errors.append(f"{label}: VSync is not Off ({metadata.get('vsync')!r})")
    if "Release x64, DirectX 11, SMAA Ultra, VSync Off" not in text:
        errors.append(f"{label}: Release x64 / DirectX 11 / SMAA Ultra provenance missing")
    if not metadata.get("candidate_readback_disabled", False):
        errors.append(f"{label}: candidate readback was not disabled")
    repeats = metadata.get("repeats", 0)
    warmup_frames = metadata.get("warmup_frames", 0)
    measure_frames = metadata.get("measurement_frames", 0)
    expected_samples = repeats * measure_frames
    if warmup_frames != 300 or repeats != 3 or measure_frames != 4800:
        errors.append(
            f"{label}: expected warmup 300, 3 repeats x 4800 frames; got "
            f"warmup {warmup_frames}, {repeats} x {measure_frames}"
        )
    for mode in MODES:
        required = set(COMMON)
        if mode == SPATIAL:
            required.add("TSCMAARestoreSpatialHistory")
        missing = required - set(timings[mode])
        if missing:
            errors.append(f"{label}/{mode}: missing {', '.join(sorted(missing))}")
        if mode == RESOLVED and "TSCMAARestoreSpatialHistory" in timings[mode]:
            errors.append(f"{label}/{mode}: unexpected spatial-history restore")
        for metric in required & set(timings[mode]):
            row = timings[mode][metric]
            if expected_samples and row["samples"] != expected_samples:
                errors.append(
                    f"{label}/{mode}/{metric}: samples {row['samples']} "
                    f"!= {expected_samples}"
                )
            if row["runs"] != repeats:
                errors.append(
                    f"{label}/{mode}/{metric}: runs {row['runs']} != {repeats}"
                )
    return errors


def normalize_cases(
    raw_cases: list[list[str]],
) -> list[tuple[str, str, Path]]:
    cases: list[tuple[str, str, Path]] = []
    seen_scenes: set[str] = set()
    seen_labels: set[str] = set()
    for raw_label, raw_scene, raw_path in raw_cases:
        label = raw_label.strip()
        scene_key = raw_scene.strip().lower()
        if not label:
            raise RuntimeError("performance case label must not be empty")
        if label in seen_labels:
            raise RuntimeError(f"duplicate performance case label: {label}")
        if scene_key not in FORMAL_SCENES:
            raise RuntimeError(f"unsupported formal scene: {raw_scene}")
        if scene_key in seen_scenes:
            raise RuntimeError(f"duplicate formal scene: {raw_scene}")
        seen_labels.add(label)
        seen_scenes.add(scene_key)
        cases.append((label, FORMAL_SCENES[scene_key], Path(raw_path).resolve()))
    if seen_scenes != set(FORMAL_SCENES):
        raise RuntimeError("formal matrix requires Bistro and Minecraft exactly once")
    return cases


def main() -> int:
    args = parse_args()
    cases: list[dict] = []
    errors: list[str] = []
    try:
        normalized_cases = normalize_cases(args.case)
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    for label, scene, path in normalized_cases:
        try:
            text, metadata, timings = parse_results(path)
            case_errors = validate_case(label, scene, text, metadata, timings)
        except (OSError, StopIteration, ValueError, KeyError) as exc:
            text, metadata, timings = "", {}, {mode: {} for mode in MODES}
            case_errors = [f"{label}: cannot parse {path}: {exc}"]
        errors.extend(case_errors)
        cases.append(
            {
                "label": label,
                "scene": scene,
                "source": str(path),
                "metadata": metadata,
                "timings": timings,
                "errors": case_errors,
            }
        )

    if errors:
        print("FAIL: ET2X feedback-topology performance validation", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    summary_rows: list[dict] = []
    for case in cases:
        resolved = case["timings"][RESOLVED]
        spatial = case["timings"][SPATIAL]
        summary_rows.append(
            {
                "scene": case["scene"],
                "resolved_smaa_ms": resolved["SMAA"]["mean_ms"],
                "spatial_smaa_ms": spatial["SMAA"]["mean_ms"],
                "spatial_minus_resolved_smaa_ms": (
                    spatial["SMAA"]["mean_ms"] - resolved["SMAA"]["mean_ms"]
                ),
                "spatial_vs_resolved_smaa_percent": percent_delta(
                    spatial["SMAA"]["mean_ms"], resolved["SMAA"]["mean_ms"]
                ),
                "resolved_whole_frame_ms": resolved["WholeFrame"]["mean_ms"],
                "spatial_whole_frame_ms": spatial["WholeFrame"]["mean_ms"],
                "spatial_minus_resolved_whole_frame_ms": (
                    spatial["WholeFrame"]["mean_ms"]
                    - resolved["WholeFrame"]["mean_ms"]
                ),
                "spatial_vs_resolved_whole_frame_percent": percent_delta(
                    spatial["WholeFrame"]["mean_ms"],
                    resolved["WholeFrame"]["mean_ms"],
                ),
                "restore_spatial_history_ms": spatial[
                    "TSCMAARestoreSpatialHistory"
                ]["mean_ms"],
                "resolved_candidate_resolve_ms": resolved[
                    "TSCMAAResolveCandidates"
                ]["mean_ms"],
                "spatial_candidate_resolve_ms": spatial[
                    "TSCMAAResolveCandidates"
                ]["mean_ms"],
                "resolved_smaa_run_mean_stddev_ms": resolved["SMAA"][
                    "run_mean_stddev_ms"
                ],
                "spatial_smaa_run_mean_stddev_ms": spatial["SMAA"][
                    "run_mean_stddev_ms"
                ],
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "et2x_feedback_topology_performance_summary.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    payload = {
        "passed": not errors,
        "errors": errors,
        "cases": cases,
        "summary": summary_rows,
    }
    (args.output_dir / "et2x_feedback_topology_performance_analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# O-ET2X-R History Feedback Topology 성능 결과",
        "",
        f"검증: **{'PASS' if not errors else 'FAIL'}**",
        "",
        "Candidate source/policy/coverage, temporal sampling, clipping, weight, reprojection과 two-copy resolve 경로를 고정했다. SpatialFrame만 visible output 복사 후 current spatial SMAA frame을 history에 복원하는 복사 1회를 추가한다.",
        "",
        "| Scene | Resolved SMAA | Spatial SMAA | Δ ms | Δ % | Resolved frame | Spatial frame | Frame Δ % | Restore copy |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['scene']} | {row['resolved_smaa_ms']:.6f} | "
            f"{row['spatial_smaa_ms']:.6f} | "
            f"{row['spatial_minus_resolved_smaa_ms']:+.6f} | "
            f"{row['spatial_vs_resolved_smaa_percent']:+.3f}% | "
            f"{row['resolved_whole_frame_ms']:.6f} | "
            f"{row['spatial_whole_frame_ms']:.6f} | "
            f"{row['spatial_vs_resolved_whole_frame_percent']:+.3f}% | "
            f"{row['restore_spatial_history_ms']:.6f} |"
        )
    lines += [
        "",
        "## 해석 제한",
        "",
        "- 300 warm-up, 4,800 measurement frames, 3 repeats, candidate readback Off 결과만 사용한다.",
        "- 두 mode 순서는 repeat마다 정방향/역방향으로 교차한다.",
        "- 이 실험은 feedback topology 비용만 측정하며 Standard T2X 대비 전체 ET2X 오버헤드를 다시 판정하지 않는다.",
    ]
    if errors:
        lines += ["", "## 검증 오류", ""] + [f"- {error}" for error in errors]
    (args.output_dir / "SMAA-ET2X-Feedback-Topology-Performance-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"{'PASS' if not errors else 'FAIL'}: analyzed {len(cases)} cases")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
