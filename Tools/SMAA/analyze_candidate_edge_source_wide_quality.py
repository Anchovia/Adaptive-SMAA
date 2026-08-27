#!/usr/bin/env python3
"""Analyze LegacyLumaRedetect versus SMAAFirstPassEdges on the wide camera path.

The supersample input is a same-pose spatial-reference proxy, not temporal ground
truth.  Source-to-source and O-1X distances are reported alongside reference
metrics so that a result merely becoming closer to spatial 1X is not mislabeled
as temporal quality improvement.
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

import analyze_wide_camera_reference_quality as wide


PROFILE = "flythrough-wide-yaw-360"
SOURCE_MODES = (
    ("legacy", "O-ET2X-R / LegacyLumaRedetect", "O_ET2X_R_LegacyLuma"),
    ("first_pass", "O-ET2X-R / SMAAFirstPassEdges", "O_ET2X_R_SMAAEdges"),
)
WINDOWS = {
    "full_00000_00479": (0, 479),
    "central_motion_00150_00329": (150, 329),
    "transition_00410_00439": (410, 439),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare paired O-ET2X-R candidate edge sources on Bistro and "
            "Minecraft wide camera-motion captures."
        )
    )
    parser.add_argument(
        "--case",
        nargs=5,
        action="append",
        required=True,
        metavar=(
            "SCENE", "FORWARD_ROOT", "REVERSE_ROOT", "BASELINE_ROOT",
            "REFERENCE_ROOT",
        ),
    )
    parser.add_argument("--expected-frames", type=int, default=480)
    parser.add_argument("--first-profile-frame", type=int, default=0)
    parser.add_argument("--ssim-stride", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def validate_source_report(
    root: Path,
    scene: str,
    first_profile_frame: int,
    expected_frames: int,
    reverse_order: bool,
) -> dict[str, Any]:
    text = wide.read_report(root)
    last_profile_frame = first_profile_frame + expected_frames - 1
    required = (
        "SMAA candidate edge-source wide camera-motion quality capture",
        f"Scene:           {scene}",
        f"Camera profile:  {PROFILE}",
        f"capture [{first_profile_frame}, {last_profile_frame}]",
        "API/preset:      DirectX 11, SMAA Ultra",
        "O-ET2X-R with LegacyLumaRedetect versus SMAAFirstPassEdges",
        "identical camera reprojection, candidate policy, expansion, history sampling, clipping, weight, and camera path",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"{root}: report is missing '{token}'")
    order_token = (
        "Capture order:  SMAAFirstPassEdges, then LegacyLumaRedetect"
        if reverse_order else
        "Capture order:  LegacyLumaRedetect, then SMAAFirstPassEdges"
    )
    order_explicit = order_token in text
    first_label = (
        "O-ET2X-R-SMAAEdges" if reverse_order else "O-ET2X-R-LegacyLuma"
    )
    second_label = (
        "O-ET2X-R-LegacyLuma" if reverse_order else "O-ET2X-R-SMAAEdges"
    )
    if not order_explicit:
        first_position = text.find(first_label)
        second_position = text.find(second_label)
        if first_position < 0 or second_position < 0 or first_position >= second_position:
            raise RuntimeError(f"{root}: mode rows do not prove the expected order")
    return {
        "root": str(root.resolve()),
        "scene": scene,
        "camera_profile": PROFILE,
        "first_profile_frame": first_profile_frame,
        "last_profile_frame": last_profile_frame,
        "frame_count": expected_frames,
        "classification": (
            "formal" if first_profile_frame == 0 and expected_frames == 480
            else "engineering"
        ),
        "window_state": "visible",
        "capture_order": (
            "SMAAFirstPassEdges_then_LegacyLumaRedetect"
            if reverse_order else
            "LegacyLumaRedetect_then_SMAAFirstPassEdges"
        ),
        "capture_order_explicit_in_report": order_explicit,
    }


def mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.mean(finite, dtype=np.float64)) if finite else float("nan")


def changed_pixel_percent(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.any(first != second, axis=2).mean(dtype=np.float64) * 100.0)


def temporal_mae(current: np.ndarray, previous: np.ndarray | None) -> float:
    if previous is None:
        return float("nan")
    return wide.rgb_mae(current, previous)


def summarize_window(
    rows: list[dict[str, Any]], start: int, end: int
) -> dict[str, Any]:
    selected = [row for row in rows if start <= row["capture_frame"] <= end]
    output: dict[str, Any] = {
        "first_capture_frame": start,
        "last_capture_frame": end,
        "frame_count": len(selected),
        "source_changed_pixels_percent": mean(
            [row["source_changed_pixels_percent"] for row in selected]
        ),
        "source_rgb_mae": mean([row["source_rgb_mae"] for row in selected]),
    }
    for key, _, _ in SOURCE_MODES:
        prefix = f"{key}_"
        output[key] = {
            "mean_rgb_mae_to_reference": mean(
                [row[prefix + "rgb_mae_to_reference"] for row in selected]
            ),
            "mean_rgb_psnr_to_reference_db": mean(
                [row[prefix + "rgb_psnr_to_reference_db"] for row in selected]
            ),
            "mean_luma_ssim_to_reference": mean(
                [row[prefix + "luma_ssim_to_reference"] for row in selected]
            ),
            "mean_edge_ratio_to_reference": mean(
                [row[prefix + "edge_ratio_to_reference"] for row in selected]
            ),
            "mean_rgb_mae_to_o1x": mean(
                [row[prefix + "rgb_mae_to_o1x"] for row in selected]
            ),
            "mean_adjacent_frame_rgb_mae": mean(
                [row[prefix + "adjacent_frame_rgb_mae"] for row in selected]
            ),
        }
    legacy = output["legacy"]
    first_pass = output["first_pass"]
    legacy_mae = legacy["mean_rgb_mae_to_reference"]
    output["first_pass_reference_mae_delta_vs_legacy_percent"] = (
        (first_pass["mean_rgb_mae_to_reference"] - legacy_mae) / legacy_mae * 100.0
        if legacy_mae > 1.0e-12 else float("nan")
    )
    legacy_o1x = legacy["mean_rgb_mae_to_o1x"]
    output["first_pass_o1x_distance_delta_vs_legacy_percent"] = (
        (first_pass["mean_rgb_mae_to_o1x"] - legacy_o1x) / legacy_o1x * 100.0
        if legacy_o1x > 1.0e-12 else float("nan")
    )
    return output


def make_peak_sheet(
    output: Path,
    frame_indices: list[int],
    paths: dict[str, list[Path]],
) -> None:
    tile_width = 280
    label_height = 26
    columns = (
        ("SS-Reference", "reference"),
        ("O-1X", "o1x"),
        ("Legacy luma", "legacy"),
        ("SMAA pass-1", "first_pass"),
        ("|Pass-1 - Legacy| x16", "difference"),
    )
    with Image.open(paths["reference"][0]) as sample:
        tile_height = round(sample.height * tile_width / sample.width)
    canvas = Image.new(
        "RGB",
        (tile_width * len(columns), label_height + len(frame_indices) * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, _) in enumerate(columns):
        draw.text((column * tile_width + 6, 7), label, fill="black")
    y = label_height
    for frame in frame_indices:
        legacy = wide.load_rgb(paths["legacy"][frame])
        first_pass = wide.load_rgb(paths["first_pass"][frame])
        difference = np.clip(
            np.abs(first_pass.astype(np.int16) - legacy.astype(np.int16)) * 16,
            0,
            255,
        ).astype(np.uint8)
        for column, (_, key) in enumerate(columns):
            if key == "difference":
                image = Image.fromarray(difference, "RGB")
                image = image.resize((tile_width, tile_height), Image.Resampling.LANCZOS)
            else:
                image = wide.resized(paths[key][frame], tile_width)
            canvas.paste(image, (column * tile_width, y))
        draw.text(
            (6, y + tile_height + 6),
            f"capture/profile {frame:05d}",
            fill="black",
        )
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def analyze_case(
    scene: str,
    forward_root: Path,
    reverse_root: Path,
    baseline_root: Path,
    reference_root: Path,
    output: Path,
    expected_frames: int,
    first_profile_frame: int,
    ssim_stride: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    forward_root = forward_root.resolve()
    reverse_root = reverse_root.resolve()
    baseline_root = baseline_root.resolve()
    reference_root = reference_root.resolve()
    provenance = {
        "source_capture_forward": validate_source_report(
            forward_root, scene, first_profile_frame, expected_frames, False
        ),
        "source_capture_reverse": validate_source_report(
            reverse_root, scene, first_profile_frame, expected_frames, True
        ),
        "reference_capture": wide.validate_report(
            reference_root, scene, first_profile_frame, expected_frames, True
        ),
        "baseline_capture_root": str(baseline_root),
    }

    paths_by_order: dict[str, dict[str, list[Path]]] = {
        "forward": {}, "reverse": {}
    }
    resolutions: set[tuple[int, int]] = set()
    for order, root in (("forward", forward_root), ("reverse", reverse_root)):
        for key, _, directory in SOURCE_MODES:
            frames, resolution = wide.collect_frames(
                root / directory, expected_frames, first_profile_frame
            )
            paths_by_order[order][key] = frames
            resolutions.add(resolution)
    shared_paths: dict[str, list[Path]] = {}
    for key, directory in (("o1x", "O_1X"), ("legacy_baseline", "O_ET2X_R")):
        frames, resolution = wide.collect_frames(
            baseline_root / directory, expected_frames, first_profile_frame
        )
        shared_paths[key] = frames
        resolutions.add(resolution)
    reference_frames, reference_resolution = wide.collect_frames(
        reference_root / "SS_Reference", expected_frames, first_profile_frame
    )
    shared_paths["reference"] = reference_frames
    resolutions.add(reference_resolution)
    if len(resolutions) != 1:
        raise RuntimeError(f"{scene}: sequence resolutions differ: {resolutions}")

    legacy_baseline_mismatches = {
        order: sum(
            wide.sha256(current) != wide.sha256(baseline)
            for current, baseline in zip(
                paths_by_order[order]["legacy"],
                shared_paths["legacy_baseline"],
            )
        )
        for order in ("forward", "reverse")
    }
    order_mismatch_frames: dict[str, list[int]] = {}
    for key, _, _ in SOURCE_MODES:
        order_mismatch_frames[key] = [
            frame for frame, (forward, reverse) in enumerate(zip(
                paths_by_order["forward"][key],
                paths_by_order["reverse"][key],
            ))
            if wide.sha256(forward) != wide.sha256(reverse)
        ]
    stable_start = max(
        [frames[-1] + 1 for frames in order_mismatch_frames.values() if frames]
        or [0]
    )

    rows: list[dict[str, Any]] = []
    for order in ("forward", "reverse"):
        previous: dict[str, np.ndarray | None] = {
            "legacy": None, "first_pass": None
        }
        for frame in range(expected_frames):
            reference = wide.load_rgb(shared_paths["reference"][frame])
            o1x = wide.load_rgb(shared_paths["o1x"][frame])
            legacy = wide.load_rgb(paths_by_order[order]["legacy"][frame])
            first_pass = wide.load_rgb(paths_by_order[order]["first_pass"][frame])
            reference_edge = wide.edge_strength(reference)
            row: dict[str, Any] = {
                "scene": scene,
                "camera_profile": PROFILE,
                "capture_order": order,
                "capture_frame": frame,
                "profile_frame": first_profile_frame + frame,
                "order_stable": frame >= stable_start,
                "source_changed_pixels_percent": changed_pixel_percent(
                    legacy, first_pass
                ),
                "source_rgb_mae": wide.rgb_mae(legacy, first_pass),
            }
            for key, image in (("legacy", legacy), ("first_pass", first_pass)):
                row[f"{key}_rgb_mae_to_reference"] = wide.rgb_mae(image, reference)
                row[f"{key}_rgb_psnr_to_reference_db"] = wide.rgb_psnr(image, reference)
                row[f"{key}_luma_ssim_to_reference"] = (
                    wide.luma_ssim(image, reference)
                    if frame % ssim_stride == 0 else float("nan")
                )
                row[f"{key}_edge_ratio_to_reference"] = (
                    wide.edge_strength(image) / reference_edge
                    if reference_edge > 1.0e-12 else float("nan")
                )
                row[f"{key}_rgb_mae_to_o1x"] = wide.rgb_mae(image, o1x)
                row[f"{key}_adjacent_frame_rgb_mae"] = temporal_mae(
                    image, previous[key]
                )
                previous[key] = image
            rows.append(row)

    window_ranges = dict(WINDOWS)
    if stable_start < expected_frames:
        window_ranges[f"order_stable_{stable_start:05d}_{expected_frames - 1:05d}"] = (
            stable_start, expected_frames - 1
        )
    windows = {
        name: summarize_window(rows, start, end)
        for name, (start, end) in window_ranges.items()
        if end < expected_frames
    }
    order_windows = {
        order: {
            name: summarize_window(
                [row for row in rows if row["capture_order"] == order], start, end
            )
            for name, (start, end) in window_ranges.items()
            if end < expected_frames
        }
        for order in ("forward", "reverse")
    }
    forward_rows = [row for row in rows if row["capture_order"] == "forward"]
    peak_frames = sorted(
        range(stable_start, expected_frames),
        key=lambda frame: forward_rows[frame]["source_rgb_mae"],
        reverse=True,
    )[:6]
    scene_output = output / scene
    scene_output.mkdir(parents=True, exist_ok=True)
    visual_paths = dict(paths_by_order["forward"])
    visual_paths["o1x"] = shared_paths["o1x"]
    visual_paths["reference"] = shared_paths["reference"]
    make_peak_sheet(
        scene_output / "candidate_edge_source_peak_difference_x16.png",
        sorted(peak_frames),
        visual_paths,
    )
    summary = {
        "scene": scene,
        "camera_profile": PROFILE,
        "classification": provenance["source_capture_forward"]["classification"],
        "resolution": list(next(iter(resolutions))),
        "frame_count": expected_frames,
        "ssim_stride": ssim_stride,
        "provenance": provenance,
        "legacy_baseline_sha256_mismatches": legacy_baseline_mismatches,
        "order_control": {
            "stable_from_capture_frame": stable_start,
            "mismatch_count": {
                key: len(frames) for key, frames in order_mismatch_frames.items()
            },
            "mismatch_first_last": {
                key: ([frames[0], frames[-1]] if frames else None)
                for key, frames in order_mismatch_frames.items()
            },
        },
        "unique_png_hashes": {
            order: {
                key: len({wide.sha256(path) for path in paths_by_order[order][key]})
                for key, _, _ in SOURCE_MODES
            }
            for order in ("forward", "reverse")
        },
        "windows": windows,
        "order_windows": order_windows,
        "peak_source_difference_frames": sorted(peak_frames),
    }
    return rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError("No per-frame rows")
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, summaries: dict[str, Any]) -> None:
    lines = [
        "# SMAA candidate edge-source wide-camera 품질 분석",
        "",
        "`O-ET2X-R`의 downstream temporal 설정을 동일하게 유지하고 temporal base edge의",
        "출처만 Legacy luminance 재검출과 SMAA 1차 패스 edge 재사용으로 바꿔 비교한다.",
        "SS-Reference는 동일 pose spatial-reference proxy이며 temporal ground truth가 아니다.",
        "",
        "## 검증",
        "",
        "| Scene | Frames/order | Legacy baseline mismatch F/R | Order mismatch Legacy/Pass-1 | Stable from |",
        "|---|---:|---:|---:|---:|",
    ]
    for scene, summary in summaries.items():
        baseline = summary["legacy_baseline_sha256_mismatches"]
        order = summary["order_control"]
        lines.append(
            f"| {scene} | {summary['frame_count']} | "
            f"{baseline['forward']}/{baseline['reverse']} | "
            f"{order['mismatch_count']['legacy']}/"
            f"{order['mismatch_count']['first_pass']} | "
            f"{order['stable_from_capture_frame']} |"
        )
    lines.extend([
        "",
        "## Reference 및 temporal 보조 지표",
        "",
        "아래 값은 정방향과 역방향 capture의 동일 source 표본을 함께 평균한다.",
        "",
        "| Scene | Window | Source | Ref RGB MAE ↓ | PSNR ↑ | SSIM ↑ | Edge/Ref | O-1X distance | Adjacent MAE |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ])
    for scene, summary in summaries.items():
        for window_name, window in summary["windows"].items():
            for key, label, _ in SOURCE_MODES:
                metrics = window[key]
                lines.append(
                    f"| {scene} | {window_name} | {label} | "
                    f"{metrics['mean_rgb_mae_to_reference']:.6f} | "
                    f"{metrics['mean_rgb_psnr_to_reference_db']:.6f} | "
                    f"{metrics['mean_luma_ssim_to_reference']:.9f} | "
                    f"{metrics['mean_edge_ratio_to_reference']:.9f} | "
                    f"{metrics['mean_rgb_mae_to_o1x']:.6f} | "
                    f"{metrics['mean_adjacent_frame_rgb_mae']:.6f} |"
                )
    lines.extend([
        "",
        "## Source 교체 효과",
        "",
        "| Scene | Window | Changed pixels | Source MAE | First-pass ref MAE delta | First-pass O-1X-distance delta |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for scene, summary in summaries.items():
        for window_name, window in summary["windows"].items():
            lines.append(
                f"| {scene} | {window_name} | "
                f"{window['source_changed_pixels_percent']:.6f}% | "
                f"{window['source_rgb_mae']:.9f} | "
                f"{window['first_pass_reference_mae_delta_vs_legacy_percent']:+.6f}% | "
                f"{window['first_pass_o1x_distance_delta_vs_legacy_percent']:+.6f}% |"
            )
    lines.extend([
        "",
        "## 순서별 source delta",
        "",
        "| Scene | Order | Window | First-pass ref MAE delta | First-pass O-1X-distance delta |",
        "|---|---|---|---:|---:|",
    ])
    for scene, summary in summaries.items():
        for order, windows in summary["order_windows"].items():
            for window_name, window in windows.items():
                lines.append(
                    f"| {scene} | {order} | {window_name} | "
                    f"{window['first_pass_reference_mae_delta_vs_legacy_percent']:+.6f}% | "
                    f"{window['first_pass_o1x_distance_delta_vs_legacy_percent']:+.6f}% |"
                )
    lines.extend([
        "",
        "양의 reference MAE delta는 first-pass가 spatial reference에서 더 멀어진 것이고,",
        "음의 O-1X-distance delta는 first-pass가 temporal history가 없는 O-1X에 더 가까워진",
        "것이다. 어느 한 지표만으로 고스팅 감소나 temporal supersampling 유지를 단정하지 않는다.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.expected_frames <= 0:
        raise RuntimeError("--expected-frames must be positive")
    if args.ssim_stride <= 0:
        raise RuntimeError("--ssim-stride must be positive")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for scene, forward_root, reverse_root, baseline_root, reference_root in args.case:
        rows, summary = analyze_case(
            scene,
            Path(forward_root),
            Path(reverse_root),
            Path(baseline_root),
            Path(reference_root),
            output,
            args.expected_frames,
            args.first_profile_frame,
            args.ssim_stride,
        )
        all_rows.extend(rows)
        summaries[scene] = summary
    write_csv(output / "candidate_edge_source_wide_per_frame.csv", all_rows)
    (output / "candidate_edge_source_wide_summary.json").write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    write_markdown(output / "candidate_edge_source_wide_analysis-ko.md", summaries)
    print(f"PASS: analyzed {len(all_rows)} scene-frames into {output}")


if __name__ == "__main__":
    main()
