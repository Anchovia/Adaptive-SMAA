#!/usr/bin/env python3
"""Analyze focused smooth camera-motion SMAA captures.

The three compared outputs are O-1X, O-T2X-R, and O-ET2X-R.  O-1X is a
same-pose spatial control, not a temporal ground truth.  Accordingly, the
reported differences are temporal-influence and recovery proxies rather than
absolute ghosting scores.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R"),
    ("o_et2x_r", "O-ET2X-R", "O_ET2X_R"),
)
SCENES = ("bistro", "minecraft")
PROFILES = (
    "yaw-smooth-360",
    "flythrough-smooth",
    "flythrough-smooth-yaw-360",
)
FRAME_PATTERN = re.compile(r"_profile_(\d+)_frame_(\d+)$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the 2-scene x 3-profile x 3-mode smooth-camera matrix."
    )
    parser.add_argument(
        "--capture",
        nargs=3,
        action="append",
        required=True,
        metavar=("SCENE", "PROFILE", "ROOT"),
        help="Repeat once for every scene/profile capture root.",
    )
    parser.add_argument(
        "--baseline-o1x",
        nargs=2,
        action="append",
        default=[],
        metavar=("SCENE", "DIRECTORY"),
        help="Optional prior combined-path O-1X directory for SHA-256 regression.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pre-frames", type=int, default=60)
    parser.add_argument("--motion-frames", type=int, default=360)
    parser.add_argument("--post-frames", type=int, default=60)
    parser.add_argument("--metric-stride", type=int, default=4)
    parser.add_argument("--recovery-stable-frames", type=int, default=5)
    parser.add_argument("--gif-step", type=int, default=3)
    return parser.parse_args()


def frame_indices(path: Path) -> tuple[int, int]:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise RuntimeError(f"Invalid camera-motion PNG filename: {path.name}")
    return int(match.group(1)), int(match.group(2))


def collect_frames(directory: Path, expected: int) -> list[Path]:
    frames = sorted(directory.glob("*.png"), key=lambda path: frame_indices(path)[1])
    profile_indices = [frame_indices(path)[0] for path in frames]
    capture_indices = [frame_indices(path)[1] for path in frames]
    expected_indices = list(range(expected))
    if profile_indices != expected_indices or capture_indices != expected_indices:
        raise RuntimeError(
            f"{directory}: expected profile/capture indices 0..{expected - 1}, "
            f"found {len(frames)} frames"
        )
    return frames


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def luma_sample(rgb: np.ndarray, stride: int) -> np.ndarray:
    sample = rgb[::stride, ::stride].astype(np.float32)
    return (
        sample[..., 0] * 0.2126
        + sample[..., 1] * 0.7152
        + sample[..., 2] * 0.0722
    )


def rgb_mae(a: np.ndarray, b: np.ndarray) -> float:
    return float(
        np.abs(a.astype(np.int16) - b.astype(np.int16)).mean(dtype=np.float64)
    )


def edge_strength(gray: np.ndarray) -> float:
    horizontal = np.abs(gray[:, 1:] - gray[:, :-1]).mean(dtype=np.float64)
    vertical = np.abs(gray[1:, :] - gray[:-1, :]).mean(dtype=np.float64)
    return float((horizontal + vertical) * 0.5)


def finite_mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.mean(finite, dtype=np.float64)) if finite else float("nan")


def finite_max(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return max(finite) if finite else float("nan")


def percent_ratio(value: float, denominator: float) -> float:
    return value / denominator * 100.0 if denominator > 1e-12 else float("nan")


def recovery_offset(
    values: list[float], plateau: float, tolerance: float, stable_frames: int
) -> int | None:
    for offset in range(0, len(values) - stable_frames + 1):
        if all(
            abs(value - plateau) <= tolerance
            for value in values[offset : offset + stable_frames]
        ):
            return offset
    return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resized(path: Path, width: int) -> Image.Image:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        height = max(1, round(rgb.height * width / rgb.width))
        return rgb.resize((width, height), Image.Resampling.LANCZOS)


def make_comparison_sheet(
    output: Path,
    frames: list[int],
    sources: list[tuple[str, list[Path]]],
) -> None:
    tile_width = 300
    label_height = 24
    tile_height = resized(sources[0][1][0], tile_width).height
    canvas = Image.new(
        "RGB",
        (
            tile_width * len(sources),
            label_height + len(frames) * (tile_height + label_height),
        ),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, _) in enumerate(sources):
        draw.text((column * tile_width + 6, 6), label, fill="black")
    y = label_height
    for frame in frames:
        for column, (_, paths) in enumerate(sources):
            canvas.paste(resized(paths[frame], tile_width), (column * tile_width, y))
        draw.text((6, y + tile_height + 5), f"frame {frame:05d}", fill="black")
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def difference_image(test: Path, control: Path, width: int) -> Image.Image:
    test_rgb = load_rgb(test)
    control_rgb = load_rgb(control)
    delta = np.abs(test_rgb.astype(np.int16) - control_rgb.astype(np.int16))
    amplified = np.clip(delta * 4, 0, 255).astype(np.uint8)
    image = Image.fromarray(amplified, "RGB")
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def make_difference_sheet(
    output: Path,
    frames: list[int],
    paths: dict[str, list[Path]],
) -> None:
    labels = ("O-1X", "O-T2X-R", "O-ET2X-R", "|T2X-R - 1X| x4", "|ET2X-R - 1X| x4")
    tile_width = 250
    label_height = 24
    tile_height = resized(paths["o_1x"][0], tile_width).height
    canvas = Image.new(
        "RGB",
        (tile_width * len(labels), label_height + len(frames) * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, label in enumerate(labels):
        draw.text((column * tile_width + 5, 6), label, fill="black")
    y = label_height
    for frame in frames:
        images = (
            resized(paths["o_1x"][frame], tile_width),
            resized(paths["o_t2x_r"][frame], tile_width),
            resized(paths["o_et2x_r"][frame], tile_width),
            difference_image(paths["o_t2x_r"][frame], paths["o_1x"][frame], tile_width),
            difference_image(paths["o_et2x_r"][frame], paths["o_1x"][frame], tile_width),
        )
        for column, image in enumerate(images):
            canvas.paste(image, (column * tile_width, y))
        draw.text((5, y + tile_height + 5), f"frame {frame:05d}", fill="black")
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def maximum_energy_crop(
    test: Path, control: Path, crop_width: int, crop_height: int
) -> tuple[int, int, int, int]:
    test_rgb = load_rgb(test)
    control_rgb = load_rgb(control)
    energy = np.abs(test_rgb.astype(np.float32) - control_rgb.astype(np.float32)).mean(
        axis=2, dtype=np.float32
    )
    height, width = energy.shape
    crop_width = min(crop_width, width)
    crop_height = min(crop_height, height)
    integral = np.pad(
        energy.cumsum(axis=0, dtype=np.float64).cumsum(axis=1, dtype=np.float64),
        ((1, 0), (1, 0)),
    )
    sums = (
        integral[crop_height:, crop_width:]
        - integral[:-crop_height, crop_width:]
        - integral[crop_height:, :-crop_width]
        + integral[:-crop_height, :-crop_width]
    )
    y, x = np.unravel_index(int(np.argmax(sums)), sums.shape)
    return int(x), int(y), int(x + crop_width), int(y + crop_height)


def cropped(path: Path, box: tuple[int, int, int, int], width: int) -> Image.Image:
    with Image.open(path) as image:
        rgb = image.convert("RGB").crop(box)
        height = max(1, round(rgb.height * width / rgb.width))
        return rgb.resize((width, height), Image.Resampling.LANCZOS)


def cropped_difference(
    test: Path,
    control: Path,
    box: tuple[int, int, int, int],
    width: int,
) -> Image.Image:
    test_rgb = load_rgb(test)[box[1] : box[3], box[0] : box[2]]
    control_rgb = load_rgb(control)[box[1] : box[3], box[0] : box[2]]
    delta = np.abs(test_rgb.astype(np.int16) - control_rgb.astype(np.int16))
    image = Image.fromarray(np.clip(delta * 4, 0, 255).astype(np.uint8), "RGB")
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def make_peak_crop_sheet(
    output: Path,
    rows: list[tuple[str, int, tuple[int, int, int, int]]],
    paths: dict[str, list[Path]],
) -> None:
    labels = (
        "O-1X",
        "O-T2X-R",
        "O-ET2X-R",
        "|T2X-R - 1X| x4",
        "|ET2X-R - 1X| x4",
    )
    tile_width = 300
    label_height = 26
    sample = cropped(paths["o_1x"][rows[0][1]], rows[0][2], tile_width)
    tile_height = sample.height
    canvas = Image.new(
        "RGB",
        (tile_width * len(labels), label_height + len(rows) * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, label in enumerate(labels):
        draw.text((column * tile_width + 5, 6), label, fill="black")
    y = label_height
    for row_label, frame, box in rows:
        images = (
            cropped(paths["o_1x"][frame], box, tile_width),
            cropped(paths["o_t2x_r"][frame], box, tile_width),
            cropped(paths["o_et2x_r"][frame], box, tile_width),
            cropped_difference(
                paths["o_t2x_r"][frame], paths["o_1x"][frame], box, tile_width
            ),
            cropped_difference(
                paths["o_et2x_r"][frame], paths["o_1x"][frame], box, tile_width
            ),
        )
        for column, image in enumerate(images):
            canvas.paste(image, (column * tile_width, y))
        draw.text(
            (5, y + tile_height + 5),
            f"{row_label}: frame {frame:05d}, crop {box}",
            fill="black",
        )
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def make_motion_gif(
    output: Path,
    start: int,
    end: int,
    step: int,
    sources: list[tuple[str, list[Path]]],
) -> None:
    tile_width = 220
    label_height = 22
    tile_height = resized(sources[0][1][0], tile_width).height
    gif_frames: list[Image.Image] = []
    for frame in range(start, end, step):
        canvas = Image.new(
            "RGB", (tile_width * len(sources), label_height + tile_height), "white"
        )
        draw = ImageDraw.Draw(canvas)
        for column, (label, paths) in enumerate(sources):
            draw.text((column * tile_width + 5, 5), f"{label} f{frame:03d}", fill="black")
            canvas.paste(resized(paths[frame], tile_width), (column * tile_width, label_height))
        gif_frames.append(canvas.quantize(colors=256))
    gif_frames[0].save(
        output,
        save_all=True,
        append_images=gif_frames[1:],
        duration=17 * step,
        loop=0,
        disposal=2,
        optimize=False,
    )


def summarize_region(rows: list[dict[str, float]], start: int, end: int) -> dict[str, Any]:
    selected = rows[start:end]
    summary: dict[str, Any] = {
        "frame_count": len(selected),
        "pair_rgb_mae_et2x_vs_t2x": finite_mean(
            [row["pair_rgb_mae_et2x_vs_t2x"] for row in selected]
        ),
    }
    for key, _, _ in MODES:
        values = {
            "rgb_mae_vs_o1x": finite_mean([row[f"{key}_rgb_mae_vs_o1x"] for row in selected]),
            "rgb_mae_vs_o1x_peak": finite_max([row[f"{key}_rgb_mae_vs_o1x"] for row in selected]),
            "adjacent_luma_mae_sampled": finite_mean([row[f"{key}_adjacent_luma_mae_sampled"] for row in selected]),
            "second_luma_difference_sampled": finite_mean([row[f"{key}_second_luma_difference_sampled"] for row in selected]),
            "edge_strength_sampled": finite_mean([row[f"{key}_edge_strength_sampled"] for row in selected]),
        }
        summary[key] = values
    standard = summary["o_t2x_r"]["rgb_mae_vs_o1x"]
    edge_selective = summary["o_et2x_r"]["rgb_mae_vs_o1x"]
    summary["et2x_temporal_influence_retention_percent"] = percent_ratio(
        edge_selective, standard
    )
    for key in ("o_t2x_r", "o_et2x_r"):
        summary[key]["adjacent_change_vs_o1x_percent"] = percent_ratio(
            summary[key]["adjacent_luma_mae_sampled"],
            summary["o_1x"]["adjacent_luma_mae_sampled"],
        )
        summary[key]["second_difference_vs_o1x_percent"] = percent_ratio(
            summary[key]["second_luma_difference_sampled"],
            summary["o_1x"]["second_luma_difference_sampled"],
        )
        summary[key]["edge_strength_vs_o1x_percent"] = percent_ratio(
            summary[key]["edge_strength_sampled"],
            summary["o_1x"]["edge_strength_sampled"],
        )
    return summary


def fmt(value: float | int | None, digits: int = 4) -> str:
    if value is None:
        return "미회복"
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        return "N/A"
    return f"{value:.{digits}f}"


def main() -> int:
    args = parse_args()
    expected = args.pre_frames + args.motion_frames + args.post_frames
    if expected <= 0 or args.metric_stride <= 0 or args.gif_step <= 0:
        raise ValueError("Invalid timeline or sampling settings")

    capture_map: dict[tuple[str, str], Path] = {}
    for scene, profile, root_text in args.capture:
        scene = scene.lower()
        profile = profile.lower()
        if scene not in SCENES or profile not in PROFILES:
            raise ValueError(f"Unsupported scene/profile: {scene}/{profile}")
        key = (scene, profile)
        if key in capture_map:
            raise ValueError(f"Duplicate capture: {scene}/{profile}")
        capture_map[key] = Path(root_text).resolve()
    expected_keys = {(scene, profile) for scene in SCENES for profile in PROFILES}
    if set(capture_map) != expected_keys:
        missing = sorted(expected_keys - set(capture_map))
        extra = sorted(set(capture_map) - expected_keys)
        raise RuntimeError(f"Capture matrix mismatch; missing={missing}, extra={extra}")

    baseline_map = {scene.lower(): Path(path).resolve() for scene, path in args.baseline_o1x}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "classification": "focused smooth-camera quality comparison",
        "not_absolute_ghosting_ground_truth": True,
        "timeline": {
            "pre_frames": args.pre_frames,
            "motion_frames": args.motion_frames,
            "post_frames": args.post_frames,
            "fixed_hz": 60,
        },
        "metric_stride": args.metric_stride,
        "captures": {},
        "o1x_regression": {},
    }
    dimensions: tuple[int, int] | None = None

    for scene in SCENES:
        for profile in PROFILES:
            capture_root = capture_map[(scene, profile)]
            key_name = f"{scene}/{profile}"
            paths = {
                key: collect_frames(capture_root / directory, expected)
                for key, _, directory in MODES
            }
            for mode_paths in paths.values():
                with Image.open(mode_paths[0]) as image:
                    current_dimensions = image.size
                if dimensions is None:
                    dimensions = current_dimensions
                elif current_dimensions != dimensions:
                    raise RuntimeError(
                        f"{key_name}: resolution {current_dimensions} differs from {dimensions}"
                    )

            rows: list[dict[str, float]] = []
            previous_luma: dict[str, np.ndarray] = {}
            previous2_luma: dict[str, np.ndarray] = {}
            for frame in range(expected):
                images = {key: load_rgb(mode_paths[frame]) for key, mode_paths in paths.items()}
                if any(image.shape != images["o_1x"].shape for image in images.values()):
                    raise RuntimeError(f"{key_name} frame {frame}: image shape mismatch")
                lumas = {
                    key: luma_sample(image, args.metric_stride)
                    for key, image in images.items()
                }
                row: dict[str, float] = {
                    "frame": float(frame),
                    "pair_rgb_mae_et2x_vs_t2x": rgb_mae(
                        images["o_et2x_r"], images["o_t2x_r"]
                    ),
                }
                for mode_key, _, _ in MODES:
                    current = lumas[mode_key]
                    row[f"{mode_key}_rgb_mae_vs_o1x"] = rgb_mae(
                        images[mode_key], images["o_1x"]
                    )
                    row[f"{mode_key}_edge_strength_sampled"] = edge_strength(current)
                    if mode_key in previous_luma:
                        row[f"{mode_key}_adjacent_luma_mae_sampled"] = float(
                            np.abs(current - previous_luma[mode_key]).mean(dtype=np.float64)
                        )
                    else:
                        row[f"{mode_key}_adjacent_luma_mae_sampled"] = float("nan")
                    if mode_key in previous2_luma:
                        row[f"{mode_key}_second_luma_difference_sampled"] = float(
                            np.abs(
                                current
                                - 2.0 * previous_luma[mode_key]
                                + previous2_luma[mode_key]
                            ).mean(dtype=np.float64)
                        )
                    else:
                        row[f"{mode_key}_second_luma_difference_sampled"] = float("nan")
                    previous2_luma[mode_key] = previous_luma.get(mode_key, current)
                    previous_luma[mode_key] = current
                rows.append(row)
                csv_row: dict[str, Any] = {
                    "scene": scene,
                    "profile": profile,
                    "frame": frame,
                }
                csv_row.update(row)
                all_rows.append(csv_row)

            regions = {
                "pre": summarize_region(rows, 0, args.pre_frames),
                "motion": summarize_region(
                    rows, args.pre_frames, args.pre_frames + args.motion_frames
                ),
                "post": summarize_region(rows, args.pre_frames + args.motion_frames, expected),
            }
            recovery: dict[str, Any] = {}
            for mode_key in ("o_t2x_r", "o_et2x_r"):
                pre_values = [row[f"{mode_key}_rgb_mae_vs_o1x"] for row in rows[: args.pre_frames]]
                baseline_mean = finite_mean(pre_values[-30:])
                baseline_std = float(np.std(pre_values[-30:], dtype=np.float64))
                post_values = [
                    row[f"{mode_key}_rgb_mae_vs_o1x"]
                    for row in rows[args.pre_frames + args.motion_frames :]
                ]
                plateau_mean = finite_mean(post_values[-10:])
                plateau_std = float(np.std(post_values[-10:], dtype=np.float64))
                plateau_tolerance = max(3.0 * plateau_std, 0.01)
                recovery[mode_key] = {
                    "pre_baseline_mean": baseline_mean,
                    "pre_baseline_std": baseline_std,
                    "post_plateau_mean": plateau_mean,
                    "post_plateau_std": plateau_std,
                    "post_plateau_tolerance": plateau_tolerance,
                    "stable_frames_required": args.recovery_stable_frames,
                    "post_plateau_recovery_offset_frames": recovery_offset(
                        post_values,
                        plateau_mean,
                        plateau_tolerance,
                        args.recovery_stable_frames,
                    ),
                }

            motion_rows = rows[args.pre_frames : args.pre_frames + args.motion_frames]
            peak_standard = args.pre_frames + int(
                np.argmax([row["o_t2x_r_rgb_mae_vs_o1x"] for row in motion_rows])
            )
            peak_edge = args.pre_frames + int(
                np.argmax([row["o_et2x_r_rgb_mae_vs_o1x"] for row in motion_rows])
            )
            peak_pair = args.pre_frames + int(
                np.argmax([row["pair_rgb_mae_et2x_vs_t2x"] for row in motion_rows])
            )
            selected = sorted(
                {
                    0,
                    args.pre_frames - 1,
                    args.pre_frames,
                    args.pre_frames + args.motion_frames // 4,
                    args.pre_frames + args.motion_frames // 2,
                    args.pre_frames + 3 * args.motion_frames // 4,
                    args.pre_frames + args.motion_frames - 1,
                    args.pre_frames + args.motion_frames,
                    expected - 1,
                    peak_standard,
                    peak_edge,
                    peak_pair,
                }
            )
            sources = [(label, paths[mode_key]) for mode_key, label, _ in MODES]
            base_name = f"{scene}_{profile}"
            make_comparison_sheet(
                output / f"{base_name}_comparison_sheet.png", selected, sources
            )
            make_difference_sheet(
                output / f"{base_name}_difference_sheet.png",
                sorted({peak_standard, peak_edge, peak_pair}),
                paths,
            )
            standard_box = maximum_energy_crop(
                paths["o_t2x_r"][peak_standard],
                paths["o_1x"][peak_standard],
                640,
                360,
            )
            pair_box = maximum_energy_crop(
                paths["o_et2x_r"][peak_pair],
                paths["o_t2x_r"][peak_pair],
                640,
                360,
            )
            crop_rows = [
                ("Standard peak vs O-1X", peak_standard, standard_box),
                ("ET2X vs Standard peak", peak_pair, pair_box),
            ]
            make_peak_crop_sheet(
                output / f"{base_name}_peak_crop_sheet.png", crop_rows, paths
            )
            make_motion_gif(
                output / f"{base_name}_motion_3way.gif",
                args.pre_frames,
                args.pre_frames + args.motion_frames,
                args.gif_step,
                sources,
            )
            result["captures"][key_name] = {
                "capture_root": str(capture_root),
                "frame_count_per_mode": expected,
                "resolution": list(dimensions),
                "regions": regions,
                "recovery": recovery,
                "peak_frames": {
                    "o_t2x_r_vs_o1x": peak_standard,
                    "o_et2x_r_vs_o1x": peak_edge,
                    "o_et2x_r_vs_o_t2x_r": peak_pair,
                },
                "peak_crop_rows": [
                    {"label": label, "frame": frame, "box": list(box)}
                    for label, frame, box in crop_rows
                ],
                "selected_sheet_frames": selected,
            }

            if profile == "flythrough-smooth-yaw-360" and scene in baseline_map:
                baseline_paths = collect_frames(baseline_map[scene], expected)
                mismatches = 0
                for current, baseline in zip(paths["o_1x"], baseline_paths):
                    if sha256(current) != sha256(baseline):
                        mismatches += 1
                result["o1x_regression"][scene] = {
                    "current_directory": str(capture_root / "O_1X"),
                    "baseline_directory": str(baseline_map[scene]),
                    "frame_count": expected,
                    "sha256_mismatch_count": mismatches,
                    "pass": mismatches == 0,
                }

    csv_path = output / "smooth_camera_focused_per_frame.csv"
    fieldnames = list(all_rows[0].keys())
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    json_path = output / "smooth_camera_focused_summary.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 부드러운 이동·회전 카메라 3-way 선행 비교",
        "",
        "## 범위",
        "",
        "- 장면: Bistro(저대비), Minecraft(고대비)",
        "- 카메라: 회전-only, 이동-only, 이동+360° 회전",
        "- 모드: `O-1X`, `O-T2X-R`, `O-ET2X-R`",
        f"- 각 sequence: {expected} frame ({args.pre_frames} pre + {args.motion_frames} motion + {args.post_frames} post), fixed 60 Hz",
        f"- RGB MAE는 원해상도, 시간·edge 지표는 {args.metric_stride}픽셀 간격 표본",
        "",
        "> O-1X는 같은 pose의 spatial control이지 temporal ground truth가 아니다. 따라서 O-1X와의 차이는 화면에 나타난 temporal 영향 대용값이며 절대 고스팅 점수가 아니다.",
        "",
        "## Motion 구간 요약",
        "",
        "| Scene | Profile | T2X-R→1X RGB MAE | ET2X-R→1X RGB MAE | ET2X temporal 영향 유지율 | T2X-R 인접 변화/1X | ET2X-R 인접 변화/1X | T2X-R edge/1X | ET2X-R edge/1X |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scene in SCENES:
        for profile in PROFILES:
            motion = result["captures"][f"{scene}/{profile}"]["regions"]["motion"]
            lines.append(
                f"| {scene} | `{profile}` | "
                f"{fmt(motion['o_t2x_r']['rgb_mae_vs_o1x'])} | "
                f"{fmt(motion['o_et2x_r']['rgb_mae_vs_o1x'])} | "
                f"{fmt(motion['et2x_temporal_influence_retention_percent'], 2)}% | "
                f"{fmt(motion['o_t2x_r']['adjacent_change_vs_o1x_percent'], 2)}% | "
                f"{fmt(motion['o_et2x_r']['adjacent_change_vs_o1x_percent'], 2)}% | "
                f"{fmt(motion['o_t2x_r']['edge_strength_vs_o1x_percent'], 2)}% | "
                f"{fmt(motion['o_et2x_r']['edge_strength_vs_o1x_percent'], 2)}% |"
            )
    lines.extend(
        [
            "",
            "## 정지 후 최종 plateau 안정화",
            "",
            "| Scene | Profile | O-T2X-R | O-ET2X-R |",
            "|---|---|---:|---:|",
        ]
    )
    for scene in SCENES:
        for profile in PROFILES:
            recovery = result["captures"][f"{scene}/{profile}"]["recovery"]
            lines.append(
                f"| {scene} | `{profile}` | "
                f"{fmt(recovery['o_t2x_r']['post_plateau_recovery_offset_frames'])} frame | "
                f"{fmt(recovery['o_et2x_r']['post_plateau_recovery_offset_frames'])} frame |"
            )
    if result["o1x_regression"]:
        lines.extend(["", "## O-1X 결정성 회귀", ""])
        for scene, regression in result["o1x_regression"].items():
            lines.append(
                f"- {scene}: {regression['frame_count']} frame 중 SHA-256 mismatch "
                f"{regression['sha256_mismatch_count']} — "
                f"{'PASS' if regression['pass'] else 'FAIL'}"
            )
    lines.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- O-1X와 가까운 결과는 고스팅 감소일 수도 있지만 temporal supersampling 손실일 수도 있다.",
            "- 낮은 인접 변화와 2차 차분은 안정화뿐 아니라 blur에서도 나타날 수 있다.",
            "- edge strength가 O-1X에 가까운 것은 선명도 유지 대용값이며 aliasing 감소를 직접 증명하지 않는다.",
            "- plateau 안정화 frame은 마지막 10 frame의 O-1X 대비 차이 수준으로 들어오는 시간이며 ghost trail 길이 자체가 아니다.",
            "- 따라서 비교 시트, 증폭 difference sheet와 3-way GIF를 수치와 함께 확인한다.",
            "- 새 결합 경로에서 의미 있는 차이가 확인된 뒤에만 supersample/CGVQM reference와 전체 8-case로 확대한다.",
        ]
    )
    report_path = output / "SMAA-Smooth-Camera-Focused-Analysis-ko.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PASS: analyzed {len(capture_map)} captures and {len(all_rows)} frame rows")
    print(f"Report: {report_path}")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
