#!/usr/bin/env python3
"""Analyze the final integrated 8-case wide-camera capture plus 1X controls.

The supersample sequence is a same-pose spatial-reference proxy, not temporal
ground truth.  Temporal-difference metrics also contain real camera/scene
motion and are reported as diagnostics rather than absolute ghosting scores.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
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
    luma,
    luma_ssim,
    parse_frame_indices,
    percentile,
    resized,
    rgb_mae,
    rgb_psnr,
)


PROFILE = "flythrough-wide-yaw-360"
REFERENCE = ("ss_reference", "SS-Reference", "SS_Reference")
MODES = (
    ("o_1x", "O-1X", "O_1X", "Original", "Control", "Off"),
    ("o_t2x", "O-T2X", "O_T2X", "Original", "Standard", "Off"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R", "Original", "Standard", "On"),
    ("o_et2x", "O-ET2X", "O_ET2X", "Original", "Edge-selective", "Off"),
    ("o_et2x_r", "O-ET2X-R", "O_ET2X_R", "Original", "Edge-selective", "On"),
    ("a_1x", "A-1X", "A_1X", "Adaptive", "Control", "Off"),
    ("a_t2x", "A-T2X", "A_T2X", "Adaptive", "Standard", "Off"),
    ("a_t2x_r", "A-T2X-R", "A_T2X_R", "Adaptive", "Standard", "On"),
    ("a_et2x", "A-ET2X", "A_ET2X", "Adaptive", "Edge-selective", "Off"),
    ("a_et2x_r", "A-ET2X-R", "A_ET2X_R", "Adaptive", "Edge-selective", "On"),
)
MODE_BY_KEY = {mode[0]: mode for mode in MODES}
WINDOWS = (
    ("full", "전체", 0, 480),
    ("pre_still", "초기 정지", 0, 60),
    ("motion", "카메라 이동", 60, 420),
    ("central_motion", "중앙 이동", 150, 330),
    ("transition", "이동-정지 전환", 410, 440),
    ("post_still", "후기 정지", 420, 480),
)
AXIS_PAIRS = (
    ("spatial", "O-T2X -> A-T2X", "o_t2x", "a_t2x"),
    ("spatial", "O-T2X-R -> A-T2X-R", "o_t2x_r", "a_t2x_r"),
    ("spatial", "O-ET2X -> A-ET2X", "o_et2x", "a_et2x"),
    ("spatial", "O-ET2X-R -> A-ET2X-R", "o_et2x_r", "a_et2x_r"),
    ("temporal_coverage", "O-T2X -> O-ET2X", "o_t2x", "o_et2x"),
    ("temporal_coverage", "O-T2X-R -> O-ET2X-R", "o_t2x_r", "o_et2x_r"),
    ("temporal_coverage", "A-T2X -> A-ET2X", "a_t2x", "a_et2x"),
    ("temporal_coverage", "A-T2X-R -> A-ET2X-R", "a_t2x_r", "a_et2x_r"),
    ("reprojection", "O-T2X -> O-T2X-R", "o_t2x", "o_t2x_r"),
    ("reprojection", "O-ET2X -> O-ET2X-R", "o_et2x", "o_et2x_r"),
    ("reprojection", "A-T2X -> A-T2X-R", "a_t2x", "a_t2x_r"),
    ("reprojection", "A-ET2X -> A-ET2X-R", "a_et2x", "a_et2x_r"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", nargs=3, action="append", required=True,
        metavar=("SCENE", "CAPTURE_ROOT", "REFERENCE_ROOT"),
    )
    parser.add_argument("--expected-frames", type=int, default=480)
    parser.add_argument("--first-profile-frame", type=int, default=0)
    parser.add_argument("--ssim-stride", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_single_report(root: Path) -> str:
    reports = list(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(f"{root}: expected one results CSV, found {len(reports)}")
    return reports[0].read_text(encoding="utf-8", errors="replace")


def validate_report(
    root: Path, scene: str, first_frame: int, frame_count: int, reference: bool
) -> dict[str, Any]:
    text = read_single_report(root)
    last_frame = first_frame + frame_count - 1
    required = [
        f"Scene:           {scene}",
        f"Camera profile:  {PROFILE}",
        f"capture [{first_frame}, {last_frame}]",
        "API/preset:      DirectX 11, SMAA Ultra",
        "Classification:  complete camera profile quality capture",
    ]
    if reference:
        required.extend([
            "supersample spatial-reference capture",
            "Reference:       2x linear resolution, 3x3 within-frame subpixel grid, 8x MSAA",
            "Temporal state:  none; supersample spatial-reference proxy",
        ])
    else:
        required.extend([
            "final eight-case plus O/A 1X controls capture",
            "Motion scope:    camera motion only; object motion vectors are not connected",
        ])
        for _, label, directory, *_ in MODES:
            required.append(f"{label}, {directory}")
    missing = [token for token in required if token not in text]
    if missing:
        raise RuntimeError(f"{root}: report missing {missing}")
    return {
        "root": str(root.resolve()),
        "scene": scene,
        "camera_profile": PROFILE,
        "capture_range": [first_frame, last_frame],
        "frame_count": frame_count,
        "classification": "formal" if first_frame == 0 and frame_count == 480 else "engineering",
        "reference_type": "supersample_spatial_proxy" if reference else None,
    }


def relative_delta(before: float, after: float) -> float:
    if not math.isfinite(before) or abs(before) <= 1.0e-12:
        return float("nan")
    return (after - before) / before * 100.0


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    maes = [float(row["rgb_mae_to_reference"]) for row in rows]
    return {
        "mean_rgb_mae_to_reference": finite_mean(maes),
        "median_rgb_mae_to_reference": percentile(maes, 50),
        "p95_rgb_mae_to_reference": percentile(maes, 95),
        "mean_rgb_psnr_to_reference_db": finite_mean(
            [float(row["rgb_psnr_to_reference_db"]) for row in rows]
        ),
        "mean_luma_ssim_to_reference": finite_mean(
            [float(row["luma_ssim_to_reference"]) for row in rows]
        ),
        "mean_edge_strength_ratio_to_reference": finite_mean(
            [float(row["edge_strength_ratio_to_reference"]) for row in rows]
        ),
        "mean_rgb_mae_to_spatial_1x": finite_mean(
            [float(row["rgb_mae_to_spatial_1x"]) for row in rows]
        ),
        "mean_adjacent_rgb_mae": finite_mean(
            [float(row["adjacent_rgb_mae"]) for row in rows]
        ),
        "mean_second_luma_difference": finite_mean(
            [float(row["second_luma_difference"]) for row in rows]
        ),
    }


def make_sheet(
    output: Path, frame_indices: list[int], paths: dict[str, list[Path]], differences: bool
) -> None:
    selected = (
        ("SS-Ref", "ss_reference"),
        ("O-1X", "o_1x"),
        ("O-T2X-R", "o_t2x_r"),
        ("O-ET2X-R", "o_et2x_r"),
        ("A-1X", "a_1x"),
        ("A-T2X-R", "a_t2x_r"),
        ("A-ET2X-R", "a_et2x_r"),
    )
    tile_width = 230
    label_height = 24
    tile_height = resized(paths["ss_reference"][0], tile_width).height
    canvas = Image.new(
        "RGB",
        (tile_width * len(selected), label_height + len(frame_indices) * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, _) in enumerate(selected):
        suffix = " |x4 error|" if differences and column > 0 else ""
        draw.text((column * tile_width + 5, 6), label + suffix, fill="black")
    y = label_height
    reference_paths = paths["ss_reference"]
    for frame in frame_indices:
        for column, (_, key) in enumerate(selected):
            if differences and key != "ss_reference":
                image = difference_image(paths[key][frame], reference_paths[frame], tile_width)
            else:
                image = resized(paths[key][frame], tile_width)
            canvas.paste(image, (column * tile_width, y))
        profile_frame = parse_frame_indices(reference_paths[frame])[0]
        draw.text((5, y + tile_height + 5), f"capture {frame:05d} / profile {profile_frame:05d}", fill="black")
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def analyze_case(
    scene: str,
    capture_root: Path,
    reference_root: Path,
    output_root: Path,
    expected_frames: int,
    first_profile_frame: int,
    ssim_stride: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    capture_root = capture_root.resolve()
    reference_root = reference_root.resolve()
    provenance = {
        "capture": validate_report(capture_root, scene, first_profile_frame, expected_frames, False),
        "reference": validate_report(reference_root, scene, first_profile_frame, expected_frames, True),
    }
    paths: dict[str, list[Path]] = {}
    resolutions: set[tuple[int, int]] = set()
    for key, _, directory, *_ in MODES:
        frames, resolution = collect_frames(capture_root / directory, expected_frames, first_profile_frame)
        paths[key] = frames
        resolutions.add(resolution)
    reference_frames, resolution = collect_frames(
        reference_root / REFERENCE[2], expected_frames, first_profile_frame
    )
    paths[REFERENCE[0]] = reference_frames
    resolutions.add(resolution)
    if len(resolutions) != 1:
        raise RuntimeError(f"{scene}: sequence resolutions differ: {resolutions}")

    rows: list[dict[str, Any]] = []
    by_mode: dict[str, list[dict[str, Any]]] = {mode[0]: [] for mode in MODES}
    previous_rgb: dict[str, np.ndarray] = {}
    previous_luma: dict[str, np.ndarray] = {}
    previous_previous_luma: dict[str, np.ndarray] = {}
    for frame in range(expected_frames):
        if frame % 60 == 0:
            print(f"[{scene}] frame {frame}/{expected_frames}", flush=True)
        reference_rgb = load_rgb(reference_frames[frame])
        reference_edge = edge_strength(reference_rgb)
        current_images = {key: load_rgb(paths[key][frame]) for key, *_ in MODES}
        for key, label, _, spatial, temporal, reprojection in MODES:
            test_rgb = current_images[key]
            control_key = "o_1x" if spatial == "Original" else "a_1x"
            current_luma = luma(test_rgb)
            adjacent = (
                rgb_mae(test_rgb, previous_rgb[key]) if key in previous_rgb else float("nan")
            )
            second = float("nan")
            if key in previous_previous_luma:
                second = float(
                    np.abs(current_luma - 2.0 * previous_luma[key] + previous_previous_luma[key]).mean(
                        dtype=np.float64
                    )
                )
            row: dict[str, Any] = {
                "scene": scene,
                "camera_profile": PROFILE,
                "capture_frame": frame,
                "profile_frame": first_profile_frame + frame,
                "mode_key": key,
                "mode": label,
                "spatial_smaa": spatial,
                "temporal_coverage": temporal,
                "reprojection": reprojection,
                "rgb_mae_to_reference": rgb_mae(test_rgb, reference_rgb),
                "rgb_psnr_to_reference_db": rgb_psnr(test_rgb, reference_rgb),
                "luma_ssim_to_reference": (
                    luma_ssim(test_rgb, reference_rgb) if frame % ssim_stride == 0 else float("nan")
                ),
                "edge_strength": edge_strength(test_rgb),
                "reference_edge_strength": reference_edge,
                "rgb_mae_to_spatial_1x": rgb_mae(test_rgb, current_images[control_key]),
                "adjacent_rgb_mae": adjacent,
                "second_luma_difference": second,
            }
            row["edge_strength_ratio_to_reference"] = (
                row["edge_strength"] / reference_edge if reference_edge > 1.0e-12 else float("nan")
            )
            rows.append(row)
            by_mode[key].append(row)
            previous_rgb[key] = test_rgb
            if key in previous_luma:
                previous_previous_luma[key] = previous_luma[key]
            previous_luma[key] = current_luma

    windows: dict[str, Any] = {}
    for window_key, window_label, start, end in WINDOWS:
        if start >= expected_frames:
            continue
        bounded_end = min(end, expected_frames)
        mode_summaries: dict[str, Any] = {}
        for key, label, directory, spatial, temporal, reprojection in MODES:
            selected_rows = [row for row in by_mode[key] if start <= int(row["capture_frame"]) < bounded_end]
            mode_summaries[key] = {
                "mode": label,
                "directory": directory,
                "spatial_smaa": spatial,
                "temporal_coverage": temporal,
                "reprojection": reprojection,
                "frame_count": len(selected_rows),
                **summarize_rows(selected_rows),
            }
        axis_effects = []
        for axis, label, before_key, after_key in AXIS_PAIRS:
            before = mode_summaries[before_key]
            after = mode_summaries[after_key]
            axis_effects.append({
                "axis": axis,
                "comparison": label,
                "before": MODE_BY_KEY[before_key][1],
                "after": MODE_BY_KEY[after_key][1],
                "rgb_mae_to_reference_delta_percent": relative_delta(
                    before["mean_rgb_mae_to_reference"], after["mean_rgb_mae_to_reference"]
                ),
                "adjacent_rgb_mae_delta_percent": relative_delta(
                    before["mean_adjacent_rgb_mae"], after["mean_adjacent_rgb_mae"]
                ),
                "second_luma_difference_delta_percent": relative_delta(
                    before["mean_second_luma_difference"], after["mean_second_luma_difference"]
                ),
                "edge_strength_ratio_delta_percent": relative_delta(
                    before["mean_edge_strength_ratio_to_reference"],
                    after["mean_edge_strength_ratio_to_reference"],
                ),
            })
        windows[window_key] = {
            "label": window_label,
            "capture_range_half_open": [start, bounded_end],
            "modes": mode_summaries,
            "axis_effects": axis_effects,
        }

    scene_output = output_root / scene
    scene_output.mkdir(parents=True, exist_ok=True)
    visual_frames = [0, 59, 60, 150, 240, 330, 419, 420, 479]
    visual_frames = [frame for frame in visual_frames if frame < expected_frames]
    make_sheet(scene_output / "final_eight_reference_comparison_sheet.png", visual_frames, paths, False)
    make_sheet(scene_output / "final_eight_reference_difference_x4_sheet.png", visual_frames, paths, True)
    summary = {
        "scene": scene,
        "camera_profile": PROFILE,
        "classification": provenance["capture"]["classification"],
        "resolution": list(next(iter(resolutions))),
        "frame_count": expected_frames,
        "ssim_stride": ssim_stride,
        "provenance": provenance,
        "windows": windows,
        "visual_frames": visual_frames,
    }
    return rows, summary


def metric_text(value: float, digits: int = 3) -> str:
    return "n/a" if not math.isfinite(value) else f"{value:+.{digits}f}%"


def write_markdown(path: Path, summaries: dict[str, Any]) -> None:
    lines = [
        "# Final integrated 8-case wide-camera 품질 분석",
        "",
        "Original/Adaptive SMAA, Standard/edge-selective temporal coverage, camera/depth",
        "reprojection Off/On의 최종 8개 case와 O-1X/A-1X control을 같은 pose의",
        "2× linear·3×3 subpixel·8×MSAA supersample spatial-reference proxy와 비교했다.",
        "",
        "## 측정 무결성",
        "",
    ]
    for scene, summary in summaries.items():
        lines.append(
            f"- {scene}: {summary['resolution'][0]}×{summary['resolution'][1]}, "
            f"{summary['frame_count']} frames, profile `{PROFILE}`, classification "
            f"`{summary['classification']}`"
        )
    lines.extend([
        "",
        "## 전체 480-frame 결과",
        "",
        "| Scene | Mode | RGB MAE↓ | PSNR↑ | Luma SSIM↑ | Edge/Ref | vs spatial 1X MAE | Adjacent MAE | 2nd luma diff |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for scene, summary in summaries.items():
        for key, label, *_ in MODES:
            mode = summary["windows"]["full"]["modes"][key]
            lines.append(
                f"| {scene} | {label} | {mode['mean_rgb_mae_to_reference']:.6f} | "
                f"{mode['mean_rgb_psnr_to_reference_db']:.4f} | "
                f"{mode['mean_luma_ssim_to_reference']:.7f} | "
                f"{mode['mean_edge_strength_ratio_to_reference']:.6f} | "
                f"{mode['mean_rgb_mae_to_spatial_1x']:.6f} | "
                f"{mode['mean_adjacent_rgb_mae']:.6f} | "
                f"{mode['mean_second_luma_difference']:.6f} |"
            )
    lines.extend([
        "",
        "## 독립 축 효과: 중앙 이동 구간 150–329",
        "",
        "양수 MAE delta는 reference 오차 증가, 음수 adjacent/2nd delta는 화면 공간 시간 변화 감소를 뜻한다.",
        "",
        "| Scene | Axis | Comparison | Ref MAE Δ | Adjacent Δ | 2nd diff Δ | Edge/Ref Δ |",
        "|---|---|---|---:|---:|---:|---:|",
    ])
    for scene, summary in summaries.items():
        for effect in summary["windows"]["central_motion"]["axis_effects"]:
            lines.append(
                f"| {scene} | {effect['axis']} | {effect['comparison']} | "
                f"{metric_text(effect['rgb_mae_to_reference_delta_percent'])} | "
                f"{metric_text(effect['adjacent_rgb_mae_delta_percent'])} | "
                f"{metric_text(effect['second_luma_difference_delta_percent'])} | "
                f"{metric_text(effect['edge_strength_ratio_delta_percent'])} |"
            )
    lines.extend([
        "",
        "## 해석 제한",
        "",
        "- Supersample reference는 한 프레임 내부의 spatial-reference proxy이며 temporal ground truth가 아니다.",
        "- Adjacent MAE와 2차 luma 차분에는 실제 카메라·장면 움직임이 포함되므로 값 감소만으로 ghosting 개선을 주장하지 않는다.",
        "- Edge/Ref 증가는 선명도 대용값일 뿐 aliasing 감소 또는 품질 향상과 동의어가 아니다.",
        "- 카메라 경로에는 object motion vector가 연결되지 않았으며 `-R`은 camera/depth reprojection을 뜻한다.",
        "- 최종 해석은 연속 영상, difference sheet, formal CGVQM과 성능 측정을 함께 사용한다.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.expected_frames <= 0 or args.first_profile_frame < 0 or args.ssim_stride <= 0:
        raise ValueError("frame counts and SSIM stride must be positive")
    cases: dict[str, tuple[Path, Path]] = {}
    for raw_scene, raw_capture, raw_reference in args.case:
        scene = raw_scene.lower()
        if scene not in ("bistro", "minecraft"):
            raise ValueError(f"Unsupported scene: {scene}")
        if scene in cases:
            raise ValueError(f"Duplicate scene: {scene}")
        cases[scene] = (Path(raw_capture), Path(raw_reference))

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for scene, (capture, reference) in cases.items():
        rows, summary = analyze_case(
            scene, capture, reference, output, args.expected_frames,
            args.first_profile_frame, args.ssim_stride,
        )
        all_rows.extend(rows)
        summaries[scene] = summary

    csv_path = output / "final_eight_wide_quality_per_frame.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    json_path = output / "final_eight_wide_quality_summary.json"
    json_path.write_text(json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path = output / "SMAA-Final-Eight-Case-Wide-Quality-Analysis-ko.md"
    write_markdown(report_path, summaries)
    print(f"CSV={csv_path}")
    print(f"JSON={json_path}")
    print(f"REPORT={report_path}")
    print(f"VALIDATION=PASS scenes={len(summaries)} modes={len(MODES)} frames={args.expected_frames}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
