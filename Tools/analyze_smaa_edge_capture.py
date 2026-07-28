#!/usr/bin/env python3
"""Analyze deterministic SMAA V2 through V4b PNG sequences."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


MODE_DEFS = (
    ("V2", "V2_ReprojectedT2X", "V2 Reprojected T2X"),
    ("V3", "V3_StrictCurrentEdge", "V3 Strict Current Edge"),
    ("V3b", "V3b_StabilizedCurrentEdge", "V3b Stabilized Current Edge"),
    ("V3c", "V3c_StableEdgeUnion", "V3c Stable Edge Union"),
    ("V4", "V4_EdgeIntersection", "V4 Edge Intersection"),
    ("V4b", "V4b_ExpandedIntersection", "V4b Expanded Intersection"),
)


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32)


def list_frames(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.png"))


def parabolic_offset(left: float, center: float, right: float) -> float:
    denominator = left - 2.0 * center + right
    if abs(denominator) < 1e-12:
        return 0.0
    return float(np.clip(0.5 * (left - right) / denominator, -0.5, 0.5))


def phase_shift(reference: np.ndarray, candidate: np.ndarray, downsample: int = 4) -> tuple[float, float]:
    reference_gray = (
        reference[::downsample, ::downsample, 0] * 0.2126
        + reference[::downsample, ::downsample, 1] * 0.7152
        + reference[::downsample, ::downsample, 2] * 0.0722
    )
    candidate_gray = (
        candidate[::downsample, ::downsample, 0] * 0.2126
        + candidate[::downsample, ::downsample, 1] * 0.7152
        + candidate[::downsample, ::downsample, 2] * 0.0722
    )

    height, width = reference_gray.shape
    window = np.outer(np.hanning(height), np.hanning(width)).astype(np.float32)
    reference_windowed = (reference_gray - reference_gray.mean()) * window
    candidate_windowed = (candidate_gray - candidate_gray.mean()) * window

    reference_fft = np.fft.rfft2(reference_windowed)
    candidate_fft = np.fft.rfft2(candidate_windowed)
    cross_power = reference_fft * np.conj(candidate_fft)
    cross_power /= np.maximum(np.abs(cross_power), 1e-12)
    correlation = np.fft.irfft2(cross_power, s=reference_gray.shape)

    peak_y, peak_x = np.unravel_index(np.argmax(correlation), correlation.shape)
    y_offset = parabolic_offset(
        correlation[(peak_y - 1) % height, peak_x],
        correlation[peak_y, peak_x],
        correlation[(peak_y + 1) % height, peak_x],
    )
    x_offset = parabolic_offset(
        correlation[peak_y, (peak_x - 1) % width],
        correlation[peak_y, peak_x],
        correlation[peak_y, (peak_x + 1) % width],
    )

    shift_y = float(peak_y) + y_offset
    shift_x = float(peak_x) + x_offset
    if shift_y > height / 2:
        shift_y -= height
    if shift_x > width / 2:
        shift_x -= width
    return shift_x * downsample, shift_y * downsample


def temporal_metrics(frames: list[Path]) -> dict[str, float]:
    previous = load_rgb(frames[0])
    temporal_mae_sum = 0.0
    temporal_gt8_sum = 0.0
    temporal_count = 0
    second_difference_sum = 0.0
    second_difference_count = 0

    middle = load_rgb(frames[1]) if len(frames) > 1 else previous
    temporal_delta = np.abs(middle - previous)
    temporal_mae_sum += float(temporal_delta.mean())
    temporal_gt8_sum += float((temporal_delta > 8.0).mean() * 100.0)
    temporal_count += 1 if len(frames) > 1 else 0

    for index in range(2, len(frames)):
        current = load_rgb(frames[index])
        temporal_delta = np.abs(current - middle)
        temporal_mae_sum += float(temporal_delta.mean())
        temporal_gt8_sum += float((temporal_delta > 8.0).mean() * 100.0)
        temporal_count += 1

        second_difference = np.abs(middle - 0.5 * (previous + current))
        second_difference_sum += float(second_difference.mean())
        second_difference_count += 1

        previous, middle = middle, current

    return {
        "temporal_mae": temporal_mae_sum / max(temporal_count, 1),
        "temporal_pixels_gt8_percent": temporal_gt8_sum / max(temporal_count, 1),
        "second_difference_mae": second_difference_sum / max(second_difference_count, 1),
    }


def comparison_metrics(
    reference_frames: list[Path],
    candidate_frames: list[Path],
) -> tuple[dict[str, float], list[dict[str, float]]]:
    first_reference = load_rgb(reference_frames[0])
    alternating_residual = np.zeros_like(first_reference, dtype=np.float32)
    dc_residual = np.zeros_like(first_reference, dtype=np.float32)

    mae_values: list[float] = []
    gt8_values: list[float] = []
    shifts_x: list[float] = []
    shifts_y: list[float] = []
    per_frame: list[dict[str, float]] = []

    for index, (reference_path, candidate_path) in enumerate(zip(reference_frames, candidate_frames)):
        reference = first_reference if index == 0 else load_rgb(reference_path)
        candidate = load_rgb(candidate_path)
        residual = candidate - reference
        absolute_residual = np.abs(residual)
        mae = float(absolute_residual.mean())
        gt8 = float((absolute_residual > 8.0).mean() * 100.0)
        shift_x, shift_y = phase_shift(reference, candidate)

        phase = 1.0 if index % 2 == 0 else -1.0
        alternating_residual += phase * residual
        dc_residual += residual
        mae_values.append(mae)
        gt8_values.append(gt8)
        shifts_x.append(shift_x)
        shifts_y.append(shift_y)
        per_frame.append(
            {
                "frame": index,
                "mae_to_v2": mae,
                "pixels_gt8_percent_to_v2": gt8,
                "phase_shift_x_pixels": shift_x,
                "phase_shift_y_pixels": shift_y,
            }
        )

    frame_count = len(reference_frames)
    alternating_amplitude = float(np.abs(alternating_residual / frame_count).mean())
    dc_amplitude = float(np.abs(dc_residual / frame_count).mean())
    even_x = float(np.mean(shifts_x[0::2]))
    odd_x = float(np.mean(shifts_x[1::2]))
    even_y = float(np.mean(shifts_y[0::2]))
    odd_y = float(np.mean(shifts_y[1::2]))

    summary = {
        "corresponding_mae_to_v2": float(np.mean(mae_values)),
        "corresponding_pixels_gt8_percent_to_v2": float(np.mean(gt8_values)),
        "alternating_residual_amplitude_to_v2": alternating_amplitude,
        "dc_residual_amplitude_to_v2": dc_amplitude,
        "mean_phase_shift_x_pixels": float(np.mean(shifts_x)),
        "mean_phase_shift_y_pixels": float(np.mean(shifts_y)),
        "even_odd_shift_delta_x_pixels": even_x - odd_x,
        "even_odd_shift_delta_y_pixels": even_y - odd_y,
    }
    return summary, per_frame


def labeled_panel(image: Image.Image, label: str, width: int) -> Image.Image:
    ratio = width / image.width
    resized = image.resize((width, round(image.height * ratio)), Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (resized.width, resized.height + 28), "black")
    panel.paste(resized, (0, 28))
    ImageDraw.Draw(panel).text((8, 7), label, fill="white")
    return panel


def save_comparison_frame(
    frame_paths: dict[str, list[Path]],
    output_path: Path,
    index: int,
    modes: tuple[tuple[str, str, str], ...],
) -> None:
    panels = []
    panel_width = max(240, 2400 // len(modes))
    for key, _, label in modes:
        with Image.open(frame_paths[key][index]) as image:
            panels.append(labeled_panel(image.convert("RGB"), label, panel_width))
    canvas = Image.new("RGB", (sum(panel.width for panel in panels), panels[0].height), "black")
    x = 0
    for panel in panels:
        canvas.paste(panel, (x, 0))
        x += panel.width
    canvas.save(output_path)


def save_comparison_gif(
    frame_paths: dict[str, list[Path]],
    output_path: Path,
    modes: tuple[tuple[str, str, str], ...],
    stride: int,
) -> None:
    frames: list[Image.Image] = []
    panel_width = max(180, 1440 // len(modes))
    for index in range(0, len(frame_paths["V2"]), stride):
        panels = []
        for key, _, label in modes:
            with Image.open(frame_paths[key][index]) as image:
                panels.append(labeled_panel(image.convert("RGB"), label, panel_width))
        canvas = Image.new("RGB", (sum(panel.width for panel in panels), panels[0].height), "black")
        x = 0
        for panel in panels:
            canvas.paste(panel, (x, 0))
            x += panel.width
        frames.append(canvas)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=50 * stride,
        loop=0,
        optimize=False,
    )


def write_summary_csv(path: Path, summaries: dict[str, dict[str, float]]) -> None:
    fieldnames = ["mode"]
    for summary in summaries.values():
        for key in summary:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for mode, summary in summaries.items():
            writer.writerow({"mode": mode, **summary})


def write_per_frame_csv(path: Path, rows: list[dict[str, float | str]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_temporal_edge_stats(
    path: Path,
) -> tuple[dict[str, dict[str, float]], list[dict[str, str]]]:
    if not path.exists():
        return {}, []

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    pixel_fields = (
        "current_edge_pixels",
        "previous_edge_pixels",
        "union_pixels",
        "intersection_pixels",
        "history_applied_pixels",
    )
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["mode"], []).append(row)

    summaries: dict[str, dict[str, float]] = {}
    for mode, mode_rows in grouped.items():
        total_pixels = sum(int(row["total_pixels"]) for row in mode_rows)
        summary: dict[str, float] = {"candidate_frames": float(len(mode_rows))}
        for field in pixel_fields:
            total = sum(int(row[field]) for row in mode_rows)
            summary[f"{field}_mean"] = total / len(mode_rows)
            summary[f"{field}_percent"] = 100.0 * total / max(total_pixels, 1)
        summaries[mode] = summary
    return summaries, rows


def write_temporal_edge_stats_summary(
    path: Path,
    summaries: dict[str, dict[str, float]],
) -> None:
    if not summaries:
        return
    fieldnames = ["mode"]
    for summary in summaries.values():
        for key in summary:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for mode, summary in summaries.items():
            writer.writerow({"mode": mode, **summary})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument(
        "--gif-stride",
        type=int,
        default=1,
        help="Use every Nth captured frame in the comparison GIF.",
    )
    args = parser.parse_args()
    if args.gif_stride < 1:
        parser.error("--gif-stride must be at least 1")

    capture_root = args.capture_root.resolve()
    analysis_dir = capture_root / "Analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    frame_paths: dict[str, list[Path]] = {}
    available_modes = tuple(
        mode_def
        for mode_def in MODE_DEFS
        if list_frames(capture_root / mode_def[1])
    )
    if not available_modes or available_modes[0][0] != "V2":
        raise RuntimeError("V2 reference frames are required")
    if len(available_modes) < 2:
        raise RuntimeError("At least one candidate mode is required")

    expected_count: int | None = None
    expected_size: tuple[int, int] | None = None
    for key, directory_name, _ in available_modes:
        frames = list_frames(capture_root / directory_name)
        if expected_count is None:
            expected_count = len(frames)
        elif len(frames) != expected_count:
            raise RuntimeError(f"Frame count mismatch for {key}: {len(frames)} vs {expected_count}")
        with Image.open(frames[0]) as image:
            if expected_size is None:
                expected_size = image.size
            elif image.size != expected_size:
                raise RuntimeError(f"Frame size mismatch for {key}: {image.size} vs {expected_size}")
        frame_paths[key] = frames

    summaries: dict[str, dict[str, float]] = {}
    for key, _, _ in available_modes:
        summaries[key] = temporal_metrics(frame_paths[key])

    per_frame_rows: list[dict[str, float | str]] = []
    for key, _, _ in available_modes[1:]:
        comparison_summary, per_frame = comparison_metrics(frame_paths["V2"], frame_paths[key])
        summaries[key].update(comparison_summary)
        for row in per_frame:
            per_frame_rows.append({"mode": key, **row})

    stats_summaries, _ = load_temporal_edge_stats(capture_root / "temporal_edge_stats.csv")
    mode_key_by_directory = {directory: key for key, directory, _ in available_modes}
    for directory, stats_summary in stats_summaries.items():
        key = mode_key_by_directory.get(directory)
        if key is not None:
            summaries[key].update(stats_summary)

    write_summary_csv(analysis_dir / "edge_guided_metrics_summary.csv", summaries)
    write_per_frame_csv(analysis_dir / "edge_guided_per_frame_metrics.csv", per_frame_rows)
    write_temporal_edge_stats_summary(
        analysis_dir / "temporal_edge_stats_summary.csv",
        stats_summaries,
    )
    representative_index = min(30, expected_count - 1)
    save_comparison_frame(
        frame_paths,
        analysis_dir / f"edge_guided_comparison_frame_{representative_index:05d}.png",
        representative_index,
        available_modes,
    )
    save_comparison_gif(
        frame_paths,
        analysis_dir / "edge_guided_comparison_sequence.gif",
        available_modes,
        args.gif_stride,
    )

    print(f"capture_root={capture_root}")
    print(f"frames_per_mode={expected_count}")
    print(f"resolution={expected_size[0]}x{expected_size[1]}")
    for mode, summary in summaries.items():
        values = " ".join(f"{key}={value:.6f}" for key, value in summary.items())
        print(f"{mode}: {values}")


if __name__ == "__main__":
    main()
