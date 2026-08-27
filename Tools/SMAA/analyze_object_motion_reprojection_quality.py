from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_candidate_only_ablation import crop_half, validate_inputs
from analyze_original_four_quality import aggregate, load_rgb, percent_delta
from analyze_supersample_reference_quality import (
    luma,
    read_reference_provenance,
    rgb_mae,
    rgb_psnr,
    validate_reference,
)
from analyze_temporal_stress_quality import (
    ghost_trail_proxy,
    object_screen_velocity,
    roi_boxes,
    visual_center_frame,
    visual_regions,
)


MODES = (
    ("o_1x", "O-1X", "O_1X"),
    (
        "standard_camera",
        "O-T2X-R / camera-only",
        "O_T2X_R_CameraOnly",
    ),
    (
        "standard_rigid",
        "O-T2X-R / camera+rigid",
        "O_T2X_R_Rigid",
    ),
    (
        "edge_camera",
        "O-ET2X-R / camera-only",
        "O_ET2X_R_CameraOnly",
    ),
    (
        "edge_rigid",
        "O-ET2X-R / camera+rigid",
        "O_ET2X_R_Rigid",
    ),
)

REFERENCE_KEY = "ss_reference"
REFERENCE_LABEL = "SS-Reference"


def gaussian_blur_11x11(values: np.ndarray) -> np.ndarray:
    """Separable 11x11 Gaussian blur matching the recorded sigma=1.5 SSIM."""
    radius = 5
    coordinates = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-(coordinates * coordinates) / (2.0 * 1.5 * 1.5))
    kernel /= kernel.sum(dtype=np.float64)
    horizontal_source = np.pad(
        values.astype(np.float32), ((0, 0), (radius, radius)), mode="reflect"
    )
    horizontal_windows = np.lib.stride_tricks.sliding_window_view(
        horizontal_source, 11, axis=1
    )
    horizontal = np.tensordot(
        horizontal_windows, kernel, axes=([-1], [0])
    ).astype(np.float32)
    vertical_source = np.pad(
        horizontal, ((radius, radius), (0, 0)), mode="reflect"
    )
    vertical_windows = np.lib.stride_tricks.sliding_window_view(
        vertical_source, 11, axis=0
    )
    return np.tensordot(
        vertical_windows, kernel, axes=([-1], [0])
    ).astype(np.float32)


def luma_ssim(first: np.ndarray, second: np.ndarray) -> float:
    first_luma = luma(first)
    second_luma = luma(second)
    constant_1 = (0.01 * 255.0) ** 2
    constant_2 = (0.03 * 255.0) ** 2
    mean_first = gaussian_blur_11x11(first_luma)
    mean_second = gaussian_blur_11x11(second_luma)
    mean_first_sq = mean_first * mean_first
    mean_second_sq = mean_second * mean_second
    mean_product = mean_first * mean_second
    variance_first = gaussian_blur_11x11(first_luma * first_luma) - mean_first_sq
    variance_second = (
        gaussian_blur_11x11(second_luma * second_luma) - mean_second_sq
    )
    covariance = (
        gaussian_blur_11x11(first_luma * second_luma) - mean_product
    )
    numerator = (2.0 * mean_product + constant_1) * (
        2.0 * covariance + constant_2
    )
    denominator = (mean_first_sq + mean_second_sq + constant_1) * (
        variance_first + variance_second + constant_2
    )
    values = numerator / np.maximum(denominator, 1.0e-12)
    if values.shape[0] > 10 and values.shape[1] > 10:
        values = values[5:-5, 5:-5]
    return float(values.mean(dtype=np.float64))


def luma_edge_strength(rgb: np.ndarray) -> float:
    values = luma(rgb).astype(np.float32)
    padded = np.pad(values, ((1, 1), (1, 1)), mode="reflect")
    windows = np.lib.stride_tricks.sliding_window_view(padded, (3, 3))
    sobel_x = np.asarray(
        ((-1.0, 0.0, 1.0), (-2.0, 0.0, 2.0), (-1.0, 0.0, 1.0)),
        dtype=np.float32,
    )
    sobel_y = sobel_x.T
    gradient_x = np.einsum("ijkl,kl->ij", windows, sobel_x, optimize=True)
    gradient_y = np.einsum("ijkl,kl->ij", windows, sobel_y, optimize=True)
    return float(np.hypot(gradient_x, gradient_y).mean(dtype=np.float64))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze camera-only versus camera+rigid SMAA reprojection on "
            "the deterministic object-motion engineering fixture."
        )
    )
    parser.add_argument("reference_root", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument(
        "--scenario",
        required=True,
        choices=("object-motion", "combined"),
    )
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def safe_delta(value: float, baseline: float) -> float:
    if not math.isfinite(value) or not math.isfinite(baseline) or baseline == 0.0:
        return float("nan")
    return percent_delta(value, baseline)


def make_comparison_gif(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
) -> str:
    keys = (REFERENCE_KEY,) + tuple(key for key, _, _ in MODES)
    count = min(24, expected_frames)
    start = min(
        max(center_frame - count // 2, 0),
        max(0, expected_frames - count),
    )
    end = start + count
    width = box[2] - box[0]
    height = box[3] - box[1]
    frames: list[Image.Image] = []
    for frame in range(start, end):
        canvas = Image.new("RGB", (width * len(keys), height + 35), "black")
        draw = ImageDraw.Draw(canvas)
        for column, key in enumerate(keys):
            with Image.open(paths[key][frame]) as source:
                crop = source.convert("RGB").crop(box)
            x = column * width
            canvas.paste(crop, (x, 35))
            draw.text((x + 6, 10), labels[key], fill="white")
        frames.append(
            canvas.quantize(colors=192, method=Image.Quantize.MEDIANCUT)
        )
    name = f"object_motion_{roi_name}_{start:05d}_{end - 1:05d}.gif"
    frames[0].save(
        output / name,
        save_all=True,
        append_images=frames[1:],
        duration=60,
        loop=0,
        optimize=False,
        disposal=2,
    )
    return name


def make_comparison_sheet(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
) -> str:
    keys = (REFERENCE_KEY,) + tuple(key for key, _, _ in MODES)
    sampled = [
        min(max(center_frame + offset, 0), expected_frames - 1)
        for offset in (-12, -8, -4, 0, 4, 8)
    ]
    width = box[2] - box[0]
    height = box[3] - box[1]
    row_height = height + 35
    canvas = Image.new(
        "RGB", (width * len(keys), row_height * len(sampled)), "black"
    )
    draw = ImageDraw.Draw(canvas)
    for row, frame in enumerate(sampled):
        y = row * row_height
        for column, key in enumerate(keys):
            with Image.open(paths[key][frame]) as source:
                crop = source.convert("RGB").crop(box)
            x = column * width
            canvas.paste(crop, (x, y + 35))
            draw.text(
                (x + 6, y + 10),
                f"{frame:05d} {labels[key]}",
                fill="white",
            )
    name = (
        f"object_motion_sheet_{roi_name}_"
        f"{sampled[0]:05d}_{sampled[-1]:05d}.png"
    )
    canvas.save(output / name, compress_level=3)
    return name


def main() -> None:
    args = parse_args()
    if args.expected_frames < 2:
        raise SystemExit("--expected-frames must be at least 2")

    reference_root = args.reference_root.resolve()
    capture_root = args.capture_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else capture_root / "ObjectMotionReprojectionAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)

    reference_paths, reference_resolution, reference_validation = (
        validate_reference(reference_root, args.expected_frames)
    )
    capture_paths, capture_resolution, capture_validation = validate_inputs(
        capture_root, args.expected_frames, MODES
    )
    if reference_resolution != capture_resolution:
        raise RuntimeError(
            f"Reference resolution {reference_resolution} differs from "
            f"capture resolution {capture_resolution}"
        )

    provenance = read_reference_provenance(reference_root)
    boxes = roi_boxes(args.scenario, reference_resolution)
    paths = {REFERENCE_KEY: reference_paths, **capture_paths}
    labels = {
        REFERENCE_KEY: REFERENCE_LABEL,
        **{key: semantic_id for key, semantic_id, _ in MODES},
    }
    all_keys = (REFERENCE_KEY,) + tuple(key for key, _, _ in MODES)

    rows: list[dict[str, Any]] = []
    previous_rois: dict[str, dict[str, np.ndarray]] | None = None
    for frame in range(args.expected_frames):
        full = {key: load_rgb(paths[key][frame]) for key in all_keys}
        rois = {
            roi_name: {
                key: crop_half(full[key], box) for key in all_keys
            }
            for roi_name, box in boxes.items()
        }
        row: dict[str, Any] = {"frame": frame}
        for roi_name, values in rois.items():
            reference = values[REFERENCE_KEY]
            reference_edge = luma_edge_strength(reference)
            row[f"{roi_name}_reference_edge_strength"] = reference_edge
            for key, _, _ in MODES:
                current = values[key]
                prefix = f"{roi_name}_{key}"
                edge = luma_edge_strength(current)
                row[f"{prefix}_rgb_mae_vs_reference"] = rgb_mae(
                    current, reference
                )
                row[f"{prefix}_rgb_psnr_vs_reference"] = rgb_psnr(
                    current, reference
                )
                row[f"{prefix}_luma_ssim_vs_reference"] = luma_ssim(
                    current, reference
                )
                row[f"{prefix}_edge_ratio_vs_reference"] = (
                    edge / reference_edge
                    if reference_edge > 0.0
                    else float("nan")
                )
                if previous_rois is not None:
                    row[f"{prefix}_adjacent_rgb_mae"] = rgb_mae(
                        current, previous_rois[roi_name][key]
                    )

            row[f"{roi_name}_standard_rigid_vs_camera_rgb_mae"] = rgb_mae(
                values["standard_rigid"], values["standard_camera"]
            )
            row[f"{roi_name}_edge_rigid_vs_camera_rgb_mae"] = rgb_mae(
                values["edge_rigid"], values["edge_camera"]
            )

        if "occluder_path" in boxes:
            velocity = object_screen_velocity(
                args.scenario, frame / 60.0
            )
            for key, _, _ in MODES:
                trail_mean, trail_width = ghost_trail_proxy(
                    full[key], boxes["occluder_path"], velocity
                )
                row[f"occluder_path_{key}_ghost_trail_mean_darkness"] = (
                    "" if math.isnan(trail_mean) else trail_mean
                )
                row[f"occluder_path_{key}_ghost_trail_width_px"] = (
                    "" if math.isnan(trail_width) else trail_width
                )

        rows.append(row)
        previous_rois = rois
        if frame % 20 == 0 or frame == args.expected_frames - 1:
            print(
                f"Processed {frame + 1}/{args.expected_frames} frames",
                flush=True,
            )

    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    csv_name = "object_motion_reprojection_metrics.csv"
    with (output / csv_name).open(
        "w", newline="", encoding="utf-8-sig"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        key: aggregate(rows, key)
        for key in fieldnames
        if key != "frame" and any(row.get(key, "") != "" for row in rows)
    }
    comparisons: dict[str, Any] = {}
    for roi_name in boxes:
        standard_camera = summary[
            f"{roi_name}_standard_camera_rgb_mae_vs_reference"
        ]["mean"]
        standard_rigid = summary[
            f"{roi_name}_standard_rigid_rgb_mae_vs_reference"
        ]["mean"]
        edge_camera = summary[
            f"{roi_name}_edge_camera_rgb_mae_vs_reference"
        ]["mean"]
        edge_rigid = summary[
            f"{roi_name}_edge_rigid_rgb_mae_vs_reference"
        ]["mean"]
        comparisons[roi_name] = {
            "standard_rigid_vs_camera_reference_mae_percent": safe_delta(
                standard_rigid, standard_camera
            ),
            "edge_rigid_vs_camera_reference_mae_percent": safe_delta(
                edge_rigid, edge_camera
            ),
            "standard_rigid_vs_camera_output_mae": summary[
                f"{roi_name}_standard_rigid_vs_camera_rgb_mae"
            ]["mean"],
            "edge_rigid_vs_camera_output_mae": summary[
                f"{roi_name}_edge_rigid_vs_camera_rgb_mae"
            ]["mean"],
        }

    center = visual_center_frame(args.scenario)
    artifact_names: list[str] = []
    for roi_name in visual_regions(args.scenario):
        if roi_name not in boxes:
            continue
        artifact_names.append(
            make_comparison_gif(
                output,
                paths,
                labels,
                roi_name,
                boxes[roi_name],
                center,
                args.expected_frames,
            )
        )
        artifact_names.append(
            make_comparison_sheet(
                output,
                paths,
                labels,
                roi_name,
                boxes[roi_name],
                center,
                args.expected_frames,
            )
        )

    result = {
        "scenario": args.scenario,
        "classification": "procedural engineering quality gate",
        "conditions": {
            "resolution": list(reference_resolution),
            "analysis_resolution": "each ROI at half width/height",
            "frame_rate": 60,
            "warmup_frames": args.warmup_frames,
            "capture_frames": args.expected_frames,
            "candidate_source": "SMAAFirstPassIntegratedCandidates",
            "candidate_policy": "IntelFamilyNonDominant",
            "non_dominant_removal": 0.5,
            "candidate_expansion": "None",
        },
        "reference_provenance": provenance,
        "reference_validation": reference_validation,
        "capture_validation": capture_validation,
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "comparisons": comparisons,
        "artifacts": artifact_names,
    }
    json_name = "object_motion_reprojection_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# SMAA rigid-object reprojection engineering 품질 gate",
        "",
        "## 범위",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 해상도: {reference_resolution[0]}×{reference_resolution[1]}",
        f"- warm-up/capture: {args.warmup_frames}/{args.expected_frames} frames per mode",
        "- ET2X: integrated first-pass candidates, removal 0.50, expansion None",
        "- 비교: O-1X, Standard/ET2X camera-only 및 camera+rigid",
        "- reference: within-frame supersample spatial proxy; temporal ground truth 아님",
        "- 분류: procedural engineering fixture이며 논문용 실제 장면 결과가 아님",
    ]
    for roi_name in boxes:
        comparison = comparisons[roi_name]
        report.extend(
            [
                "",
                f"## `{roi_name}`",
                "",
                "| Mode | Reference RGB MAE | PSNR | Luma SSIM | Edge/reference | Adjacent MAE |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for key, semantic_id, _ in MODES:
            prefix = f"{roi_name}_{key}"
            adjacent_key = f"{prefix}_adjacent_rgb_mae"
            adjacent = summary.get(adjacent_key, {"mean": float("nan")})[
                "mean"
            ]
            report.append(
                f"| `{semantic_id}` | "
                f"{summary[f'{prefix}_rgb_mae_vs_reference']['mean']:.6f} | "
                f"{summary[f'{prefix}_rgb_psnr_vs_reference']['mean']:.4f} dB | "
                f"{summary[f'{prefix}_luma_ssim_vs_reference']['mean']:.6f} | "
                f"{summary[f'{prefix}_edge_ratio_vs_reference']['mean']:.6f} | "
                f"{adjacent:.6f} |"
            )
        report.extend(
            [
                "",
                "- Standard camera+rigid vs camera-only reference MAE: "
                f"{comparison['standard_rigid_vs_camera_reference_mae_percent']:+.3f}%",
                "- ET2X camera+rigid vs camera-only reference MAE: "
                f"{comparison['edge_rigid_vs_camera_reference_mae_percent']:+.3f}%",
                "- Standard rigid toggle output difference MAE: "
                f"{comparison['standard_rigid_vs_camera_output_mae']:.6f}",
                "- ET2X rigid toggle output difference MAE: "
                f"{comparison['edge_rigid_vs_camera_output_mae']:.6f}",
            ]
        )

    if "occluder_path" in boxes:
        report.extend(
            [
                "",
                "## Occluder trailing-halo 대용 지표",
                "",
                "| Mode | Mean darkness | Width px |",
                "|---|---:|---:|",
            ]
        )
        for key, semantic_id, _ in MODES:
            darkness = summary.get(
                f"occluder_path_{key}_ghost_trail_mean_darkness"
            )
            width = summary.get(
                f"occluder_path_{key}_ghost_trail_width_px"
            )
            report.append(
                f"| `{semantic_id}` | "
                f"{darkness['mean'] if darkness else float('nan'):.6f} | "
                f"{width['mean'] if width else float('nan'):.6f} |"
            )
        report.extend(
            [
                "",
                "이 지표는 알려진 occluder 이동 방향 뒤의 darkness/연속 폭 휴리스틱이며",
                "절대 ghosting ground truth로 표현하지 않는다.",
            ]
        )

    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- Rigid velocity는 움직이는 opaque rigid surface만 보정한다.",
            "- 새로 드러난 배경의 previous-depth disocclusion rejection은 아직 없다.",
            "- skinned/deforming/transparent motion은 지원하지 않는다.",
            "- 실제 textured dynamic scene gate 전에는 기존 8-case `-R` 의미를 변경하지 않는다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 지표: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
        ]
    )
    report.extend(f"- 비교 자료: `{name}`" for name in artifact_names)
    report.append("")
    report_name = "SMAA-Object-Motion-Reprojection-Quality-ko.md"
    (output / report_name).write_text(
        "\n".join(report), encoding="utf-8"
    )
    print(f"Object-motion reprojection analysis complete: {output}")


if __name__ == "__main__":
    main()
