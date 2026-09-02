#!/usr/bin/env python3
"""Analyze the controlled O-ET2X-R history-feedback topology gate.

The two ET2X modes differ only in the texture written to the next frame's
history: the current resolved output or the current spatial SMAA frame.  The
supersample sequence is a same-pose spatial-reference proxy, not an absolute
temporal ground truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_wide_camera_reference_quality import (
    collect_frames,
    difference_image,
    edge_strength,
    finite_mean,
    load_rgb,
    luma_ssim,
    parse_frame_indices,
    resized,
    rgb_mae,
    rgb_psnr,
)


PROFILE = "flythrough-wide-yaw-360"
FORMAL_SCENES = {"bistro": "Bistro", "minecraft": "Minecraft"}
FORMAL_RESOLUTION = (1920, 1017)
MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R"),
    (
        "resolved_feedback",
        "O-ET2X-R / ResolvedOutput",
        "O_ET2X_R_ResolvedFeedback",
    ),
    (
        "spatial_feedback",
        "ABL-ET2X-R / SpatialFrame",
        "ABL_ET2X_R_SpatialFeedback",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        nargs=4,
        action="append",
        required=True,
        metavar=("SCENE", "CAPTURE", "REFERENCE", "PRIOR_CONTROL_CAPTURE"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-frames", type=int, required=True)
    parser.add_argument("--first-profile-frame", type=int, required=True)
    parser.add_argument("--ssim-stride", type=int, default=4)
    parser.add_argument(
        "--classification",
        choices=("engineering", "formal-window"),
        default="formal-window",
    )
    return parser.parse_args()


def report_text(root: Path) -> str:
    reports = list(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(f"{root}: expected one results CSV, found {len(reports)}")
    return reports[0].read_text(encoding="utf-8", errors="replace")


def validate_reports(
    capture: Path,
    reference: Path,
    prior: Path,
    scene: str,
    first: int,
    frames: int,
    classification: str,
) -> None:
    capture_end = first + frames - 1
    capture_required = (
        "API:  DirectX11",
        "Resolution:   1920 x 1017",
        "integrated ET2X history-feedback topology isolation capture",
        f"Scene:           {scene.lower()}",
        f"Camera profile:  {PROFILE}",
        f"capture [{first}, {capture_end}]",
        "API/preset:      DirectX 11, SMAA Ultra",
        "only history feedback topology",
        "integrated first-pass candidates",
        "fixed history weight 0.8",
    )
    reference_required = (
        "API:  DirectX11",
        "Resolution:   1920 x 1017",
        "supersample spatial-reference capture",
        f"Scene:           {scene.lower()}",
        f"Camera profile:  {PROFILE}",
        "API/preset:      DirectX 11, SMAA Ultra",
        "Classification:  complete camera profile quality capture",
        "2x linear resolution, 3x3 within-frame subpixel grid, 8x MSAA",
    )
    prior_required = (
        "API:  DirectX11",
        "Resolution:   1920 x 1017",
        f"Scene:           {scene.lower()}",
        f"Camera profile:  {PROFILE}",
        f"capture [{first}, {capture_end}]",
        "API/preset:      DirectX 11, SMAA Ultra",
        "O-T2X-R",
    )
    if classification == "formal-window":
        formal_tokens = (
            "Classification:  formal diagnostic window with full-profile temporal pre-roll",
            (
                f"Pre-roll:        profile frames 0..{first - 1} rendered without PNG output "
                "so temporal history matches a full-profile capture"
            ),
        )
        capture_required += formal_tokens
        prior_required += formal_tokens

    capture_report = report_text(capture)
    reference_report = report_text(reference)
    prior_report = report_text(prior)
    missing = [token for token in capture_required if token not in capture_report]
    missing += [
        token for token in reference_required if token not in reference_report
    ]
    missing += [token for token in prior_required if token not in prior_report]
    if missing:
        raise RuntimeError(f"{scene}: report validation failed: {missing}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_reference_slice(
    directory: Path, first: int, expected: int
) -> tuple[list[Path], tuple[int, int]]:
    all_frames = sorted(
        directory.glob("*.png"), key=lambda path: parse_frame_indices(path)[0]
    )
    by_profile: dict[int, Path] = {}
    by_capture: dict[int, Path] = {}
    duplicate_profiles: list[int] = []
    duplicate_captures: list[int] = []
    for path in all_frames:
        profile_index, capture_index = parse_frame_indices(path)
        if profile_index in by_profile:
            duplicate_profiles.append(profile_index)
        else:
            by_profile[profile_index] = path
        if capture_index in by_capture:
            duplicate_captures.append(capture_index)
        else:
            by_capture[capture_index] = path
    if duplicate_profiles or duplicate_captures:
        raise RuntimeError(
            f"{directory}: duplicate reference indices: "
            f"profile={sorted(set(duplicate_profiles))[:8]}, "
            f"capture={sorted(set(duplicate_captures))[:8]}"
        )
    requested = list(range(first, first + expected))
    missing = [index for index in requested if index not in by_profile]
    if missing:
        raise RuntimeError(f"{directory}: missing reference profile frames {missing[:8]}")
    frames = [by_profile[index] for index in requested]
    misaligned = [
        path.name
        for path in frames
        if parse_frame_indices(path)[0] != parse_frame_indices(path)[1]
    ]
    if misaligned:
        raise RuntimeError(
            f"{directory}: reference profile/capture indices differ: "
            f"{misaligned[:4]}"
        )
    with Image.open(frames[0]) as image:
        resolution = image.size
    for path in frames[1:]:
        with Image.open(path) as image:
            if image.size != resolution:
                raise RuntimeError(f"{path}: resolution mismatch")
    return frames, resolution


def hash_bridge_standard(
    scene: str, capture: Path, prior: Path, first: int, expected: int
) -> dict[str, Any]:
    current, _ = collect_frames(capture / "O_T2X_R", expected, first)
    prior_all = sorted(
        (prior / "O_T2X_R").glob("*.png"),
        key=lambda path: parse_frame_indices(path)[0],
    )
    prior_by_profile: dict[int, Path] = {}
    duplicates: list[int] = []
    for path in prior_all:
        profile_index = parse_frame_indices(path)[0]
        if profile_index in prior_by_profile:
            duplicates.append(profile_index)
        else:
            prior_by_profile[profile_index] = path
    if duplicates:
        raise RuntimeError(
            f"{scene}: duplicate prior-control profile indices "
            f"{sorted(set(duplicates))[:8]}"
        )
    requested = list(range(first, first + expected))
    if any(index not in prior_by_profile for index in requested):
        raise RuntimeError(f"{scene}: prior O-T2X-R control range is incomplete")
    previous = [prior_by_profile[index] for index in requested]
    mismatches = sum(sha256(a) != sha256(b) for a, b in zip(current, previous))
    if mismatches:
        raise RuntimeError(f"{scene}: O-T2X-R hash bridge mismatches={mismatches}")
    return {
        "scene": scene,
        "frame_count": expected,
        "byte_hash_mismatches": mismatches,
        "prior_capture_root": str(prior),
    }


def analysis_windows(first: int, expected: int) -> tuple[tuple[str, str, int, int], ...]:
    end = first + expected
    result: list[tuple[str, str, int, int]] = []
    for key, label, global_start, global_end in (
        ("central_motion", "중앙 이동", 150, 330),
        ("transition", "이동→정지", 410, 440),
        ("post_still", "후기 정지", 420, 480),
    ):
        overlap_start = max(first, global_start)
        overlap_end = min(end, global_end)
        if overlap_start < overlap_end:
            result.append(
                (key, label, overlap_start - first, overlap_end - first)
            )
    if not result:
        result.append(("capture", f"profile {first}~{end - 1}", 0, expected))
    return tuple(result)


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return finite_mean([float(row[key]) for row in rows])


def make_sheet(
    output: Path,
    paths: dict[str, list[Path]],
    local_frames: list[int],
    first: int,
    differences: bool,
) -> None:
    columns = (("SS-Ref", "reference"),) + tuple(
        (label, key) for key, label, _ in MODES
    )
    width, label_height = 260, 25
    tile_height = resized(paths["reference"][0], width).height
    canvas = Image.new(
        "RGB",
        (width * len(columns), label_height + len(local_frames) * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, key) in enumerate(columns):
        suffix = " |x4 diff|" if differences and key != "reference" else ""
        draw.text((column * width + 4, 6), label + suffix, fill="black")
    y = label_height
    for local_frame in local_frames:
        for column, (_, key) in enumerate(columns):
            image = (
                difference_image(
                    paths[key][local_frame], paths["reference"][local_frame], width
                )
                if differences and key != "reference"
                else resized(paths[key][local_frame], width)
            )
            canvas.paste(image, (column * width, y))
        draw.text(
            (4, y + tile_height + 5),
            f"profile frame {first + local_frame:05d}",
            fill="black",
        )
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def analyze_case(
    scene: str,
    capture: Path,
    reference: Path,
    first: int,
    expected: int,
    ssim_stride: int,
    output: Path,
    prior: Path,
    classification: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_reports(
        capture,
        reference,
        prior,
        scene,
        first,
        expected,
        classification,
    )
    paths: dict[str, list[Path]] = {}
    resolutions: set[tuple[int, int]] = set()
    for key, _, directory in MODES:
        paths[key], resolution = collect_frames(capture / directory, expected, first)
        resolutions.add(resolution)
    paths["reference"], resolution = collect_reference_slice(
        reference / "SS_Reference", first, expected
    )
    resolutions.add(resolution)
    if len(resolutions) != 1:
        raise RuntimeError(f"{scene}: resolution mismatch {resolutions}")
    if next(iter(resolutions)) != FORMAL_RESOLUTION:
        raise RuntimeError(
            f"{scene}: expected formal resolution {FORMAL_RESOLUTION}, "
            f"got {next(iter(resolutions))}"
        )

    rows: list[dict[str, Any]] = []
    previous: dict[str, np.ndarray] = {}
    previous_reference: np.ndarray | None = None
    for local_frame in range(expected):
        if local_frame % 30 == 0:
            print(f"[{scene}] metrics {local_frame}/{expected}", flush=True)
        reference_rgb = load_rgb(paths["reference"][local_frame])
        reference_edge = edge_strength(reference_rgb)
        resolved = load_rgb(paths["resolved_feedback"][local_frame])
        spatial = load_rgb(paths["spatial_feedback"][local_frame])
        topology_difference = np.abs(
            spatial.astype(np.int16) - resolved.astype(np.int16)
        )
        for key, label, directory in MODES:
            image = (
                resolved
                if key == "resolved_feedback"
                else spatial
                if key == "spatial_feedback"
                else load_rgb(paths[key][local_frame])
            )
            temporal_residual = float("nan")
            if key in previous and previous_reference is not None:
                temporal_residual = float(
                    np.abs(
                        (image.astype(np.int16) - previous[key].astype(np.int16))
                        - (
                            reference_rgb.astype(np.int16)
                            - previous_reference.astype(np.int16)
                        )
                    ).mean(dtype=np.float64)
                )
            rows.append(
                {
                    "scene": scene,
                    "profile_frame": first + local_frame,
                    "local_frame": local_frame,
                    "key": key,
                    "label": label,
                    "directory": directory,
                    "rgb_mae_to_reference": rgb_mae(image, reference_rgb),
                    "rgb_psnr_to_reference_db": rgb_psnr(image, reference_rgb),
                    "luma_ssim_to_reference": (
                        luma_ssim(image, reference_rgb)
                        if local_frame % ssim_stride == 0
                        else float("nan")
                    ),
                    "edge_strength_ratio_to_reference": (
                        edge_strength(image) / reference_edge
                        if reference_edge > 1.0e-12
                        else float("nan")
                    ),
                    "temporal_delta_residual_to_reference": temporal_residual,
                    "spatial_vs_resolved_rgb_mae": float(
                        topology_difference.mean(dtype=np.float64)
                    ),
                    "spatial_vs_resolved_pixel_mismatch_fraction": float(
                        np.any(topology_difference > 0, axis=2).mean()
                    ),
                    "spatial_vs_resolved_max_channel_error": int(
                        topology_difference.max()
                    ),
                }
            )
            previous[key] = image
        previous_reference = reference_rgb

    summary: dict[str, Any] = {
        "scene": scene,
        "profile": PROFILE,
        "profile_frame_range_inclusive": [first, first + expected - 1],
        "resolution": list(next(iter(resolutions))),
        "capture_root": str(capture),
        "reference_root": str(reference),
        "windows": {},
    }
    for window_key, label, start, end in analysis_windows(first, expected):
        mode_summaries: dict[str, Any] = {}
        for key, mode_label, directory in MODES:
            selected = [
                row
                for row in rows
                if row["key"] == key and start <= int(row["local_frame"]) < end
            ]
            mode_summaries[key] = {
                "label": mode_label,
                "directory": directory,
                "frame_count": len(selected),
                "mean_rgb_mae_to_reference": mean(selected, "rgb_mae_to_reference"),
                "mean_rgb_psnr_to_reference_db": mean(
                    selected, "rgb_psnr_to_reference_db"
                ),
                "mean_luma_ssim_to_reference": mean(
                    selected, "luma_ssim_to_reference"
                ),
                "mean_edge_strength_ratio_to_reference": mean(
                    selected, "edge_strength_ratio_to_reference"
                ),
                "mean_temporal_delta_residual_to_reference": mean(
                    selected, "temporal_delta_residual_to_reference"
                ),
            }
        resolved_summary = mode_summaries["resolved_feedback"]
        spatial_summary = mode_summaries["spatial_feedback"]
        topology_rows = [
            row
            for row in rows
            if row["key"] == "spatial_feedback"
            and start <= int(row["local_frame"]) < end
        ]
        summary["windows"][window_key] = {
            "label": label,
            "profile_range_half_open": [first + start, first + end],
            "modes": mode_summaries,
            "spatial_minus_resolved": {
                "rgb_mae_to_reference": (
                    spatial_summary["mean_rgb_mae_to_reference"]
                    - resolved_summary["mean_rgb_mae_to_reference"]
                ),
                "luma_ssim_to_reference": (
                    spatial_summary["mean_luma_ssim_to_reference"]
                    - resolved_summary["mean_luma_ssim_to_reference"]
                ),
                "temporal_delta_residual_to_reference": (
                    spatial_summary["mean_temporal_delta_residual_to_reference"]
                    - resolved_summary["mean_temporal_delta_residual_to_reference"]
                ),
                "mean_pair_rgb_mae": mean(
                    topology_rows, "spatial_vs_resolved_rgb_mae"
                ),
                "mean_pair_pixel_mismatch_fraction": mean(
                    topology_rows,
                    "spatial_vs_resolved_pixel_mismatch_fraction",
                ),
                "max_pair_channel_error": max(
                    int(row["spatial_vs_resolved_max_channel_error"])
                    for row in topology_rows
                ),
            },
        }

    scene_output = output / scene
    scene_output.mkdir(parents=True, exist_ok=True)
    visual_frames = sorted({0, expected // 3, 2 * expected // 3, expected - 1})
    make_sheet(
        scene_output / "et2x_feedback_topology_comparison.png",
        paths,
        visual_frames,
        first,
        False,
    )
    make_sheet(
        scene_output / "et2x_feedback_topology_difference_x4.png",
        paths,
        visual_frames,
        first,
        True,
    )
    return rows, summary


def write_report(
    path: Path, summaries: dict[str, Any], bridges: list[dict[str, Any]]
) -> None:
    lines = [
        "# O-ET2X-R History Feedback Topology Gate 결과",
        "",
        "## 목적",
        "",
        "통합 1차 edge 후보, Intel-family removal 0.50, 확장 None, Pattern Off, Catmull-Rom 5-tap, YCoCg clipping, fixed history weight 0.8 및 camera/depth reprojection을 고정했다.",
        "비교 축은 다음 history에 resolved output을 재귀적으로 저장하는지, 현재 spatial SMAA frame을 저장하는지뿐이다.",
        "SpatialFrame은 final 8-case를 변경하지 않는 진단 ablation이다.",
        "",
        "## 입력 무결성",
        "",
        f"- 기존 O-T2X-R control hash bridge: {len(bridges)} sequences, mismatch 0",
        "- supersample 입력은 동일 pose의 spatial-reference proxy이며 temporal ground truth가 아니다.",
        "",
        "## 품질 결과",
        "",
        "음수 MAE/temporal-residual 차이는 SpatialFrame이 ResolvedOutput보다 낮은 오차를 보였다는 뜻이다.",
        "",
        "| Scene | Window | Resolved MAE | Spatial MAE | Spatial−Resolved MAE | SSIM Δ | Temporal residual Δ | Pair mismatch |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for scene, summary in summaries.items():
        for window in summary["windows"].values():
            resolved = window["modes"]["resolved_feedback"]
            spatial = window["modes"]["spatial_feedback"]
            delta = window["spatial_minus_resolved"]
            lines.append(
                f"| {scene} | {window['label']} | "
                f"{resolved['mean_rgb_mae_to_reference']:.6f} | "
                f"{spatial['mean_rgb_mae_to_reference']:.6f} | "
                f"{delta['rgb_mae_to_reference']:+.6f} | "
                f"{delta['luma_ssim_to_reference']:+.6f} | "
                f"{delta['temporal_delta_residual_to_reference']:+.6f} | "
                f"{delta['mean_pair_pixel_mismatch_fraction'] * 100.0:.4f}% |"
            )
    lines += [
        "",
        "## 해석 제한",
        "",
        "- 이 gate는 feedback topology 한 축의 인과 비교이며 candidate coverage나 sample pattern의 우열을 다시 측정하는 실험이 아니다.",
        "- spatial-reference 지표는 동일 pose의 공간 오차를 측정한다. 최종 temporal 판정에는 CGVQM-2와 연속 영상 검사를 함께 사용해야 한다.",
        "- engineering smoke 결과는 정식 수치에 포함하지 않는다.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def normalize_cases(
    raw_cases: list[list[str]],
) -> list[tuple[str, Path, Path, Path]]:
    cases: list[tuple[str, Path, Path, Path]] = []
    seen: set[str] = set()
    for raw_scene, capture_text, reference_text, prior_text in raw_cases:
        scene_key = raw_scene.strip().lower()
        if scene_key not in FORMAL_SCENES:
            raise RuntimeError(f"unsupported formal scene: {raw_scene}")
        if scene_key in seen:
            raise RuntimeError(f"duplicate formal scene: {raw_scene}")
        seen.add(scene_key)
        cases.append(
            (
                FORMAL_SCENES[scene_key],
                Path(capture_text).resolve(),
                Path(reference_text).resolve(),
                Path(prior_text).resolve(),
            )
        )
    if seen != set(FORMAL_SCENES):
        raise RuntimeError("formal matrix requires Bistro and Minecraft exactly once")
    return cases


def preflight_case(
    scene: str,
    capture: Path,
    reference: Path,
    prior: Path,
    first: int,
    expected: int,
    classification: str,
) -> dict[str, Any]:
    validate_reports(
        capture,
        reference,
        prior,
        scene,
        first,
        expected,
        classification,
    )
    resolutions: set[tuple[int, int]] = set()
    for _, _, directory in MODES:
        _, resolution = collect_frames(capture / directory, expected, first)
        resolutions.add(resolution)
    _, reference_resolution = collect_reference_slice(
        reference / "SS_Reference", first, expected
    )
    resolutions.add(reference_resolution)
    if resolutions != {FORMAL_RESOLUTION}:
        raise RuntimeError(
            f"{scene}: formal input resolution mismatch: {sorted(resolutions)}"
        )
    return hash_bridge_standard(scene, capture, prior, first, expected)


def main() -> int:
    args = parse_args()
    try:
        if args.expected_frames <= 0:
            raise RuntimeError("--expected-frames must be positive")
        if args.first_profile_frame < 0:
            raise RuntimeError("--first-profile-frame must be non-negative")
        if args.classification == "formal-window" and args.first_profile_frame == 0:
            raise RuntimeError(
                "formal-window captures must have a positive first profile frame "
                "and full-profile temporal pre-roll"
            )
        if args.ssim_stride <= 0:
            raise RuntimeError("--ssim-stride must be positive")
        cases = normalize_cases(args.case)
        bridges = [
            preflight_case(
                scene,
                capture,
                reference,
                prior,
                args.first_profile_frame,
                args.expected_frames,
                args.classification,
            )
            for scene, capture, reference, prior in cases
        ]
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL: ET2X feedback-topology input validation: {exc}", file=sys.stderr)
        return 1

    args.output.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    try:
        for scene, capture, reference, prior in cases:
            rows, summary = analyze_case(
                scene,
                capture,
                reference,
                args.first_profile_frame,
                args.expected_frames,
                args.ssim_stride,
                args.output,
                prior,
                args.classification,
            )
            all_rows.extend(rows)
            summaries[scene] = summary
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL: ET2X feedback-topology analysis: {exc}", file=sys.stderr)
        return 1

    if not all_rows or set(summaries) != set(FORMAL_SCENES.values()):
        print("FAIL: no complete formal quality matrix was produced", file=sys.stderr)
        return 1

    with (args.output / "et2x_feedback_topology_per_frame.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    payload = {
        "classification": args.classification,
        "hash_bridges": bridges,
        "scenes": summaries,
    }
    (args.output / "et2x_feedback_topology_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(
        args.output / "SMAA-ET2X-Feedback-Topology-Results-ko.md",
        summaries,
        bridges,
    )
    print(f"PASS: analyzed {len(summaries)} scenes and {len(all_rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
