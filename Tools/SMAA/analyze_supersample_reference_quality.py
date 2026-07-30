from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_candidate_only_ablation import (
    crop_half,
    validate_inputs,
    visual_center_frame,
    visual_regions,
)
from analyze_optical_flow_temporal_quality import require_opencv
from analyze_original_four_quality import aggregate, load_rgb, percent_delta
from analyze_temporal_stress_quality import roi_boxes


BASE_MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("standard", "O-T2X-R", "O_T2X_R"),
    (
        "candidate_jitter",
        "ABL-Candidate-Jitter-R",
        "ABL_Candidate_Jitter_R",
    ),
    (
        "candidate_no_jitter",
        "ABL-Candidate-NoJitter-R",
        "ABL_Candidate_NoJitter_R",
    ),
)

HYBRID_MODE = (
    "candidate_dejitter",
    "ABL-Candidate-DeJitter-R",
    "ABL_Candidate_DeJitter_R",
)

MODES = BASE_MODES

REFERENCE_KEY = "ss_reference"
REFERENCE_LABEL = "SS-Reference"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare controlled SMAA candidate/jitter modes against the "
            "within-frame CMAA2 supersample spatial reference."
        )
    )
    parser.add_argument("reference_root", type=Path)
    parser.add_argument("comparison_root", type=Path)
    parser.add_argument(
        "--scenario",
        required=True,
        choices=("thin-lines", "object-motion", "combined"),
    )
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--reference-warmup-frames", type=int, default=10)
    parser.add_argument("--comparison-warmup-frames", type=int, default=60)
    parser.add_argument(
        "--include-hybrid",
        action="store_true",
        help="Include ABL-Candidate-DeJitter-R from a hybrid capture root.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def frame_index(path: Path) -> int:
    return int(path.stem.rsplit("_", 1)[1])


def validate_reference(
    root: Path,
    expected_frames: int,
) -> tuple[list[Path], tuple[int, int], dict[str, Any]]:
    directory = root / "SS_Reference"
    frames = sorted(directory.glob("*.png"))
    if len(frames) != expected_frames:
        raise RuntimeError(
            f"{REFERENCE_LABEL}: expected {expected_frames} PNGs, found {len(frames)}"
        )
    indices = [frame_index(path) for path in frames]
    if indices != list(range(expected_frames)):
        raise RuntimeError(f"{REFERENCE_LABEL}: missing or reordered frame indices")
    with Image.open(frames[0]) as image:
        resolution = image.size
    validation = {
        "root": str(root),
        "directory": "SS_Reference",
        "frame_count": len(frames),
        "first_index": indices[0],
        "last_index": indices[-1],
        "resolution": list(resolution),
    }
    return frames, resolution, validation


def read_reference_provenance(root: Path) -> dict[str, Any]:
    reports = sorted(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(
            f"Expected one reference results CSV in {root}, found {len(reports)}"
        )
    text = reports[0].read_text(encoding="utf-8", errors="replace")
    reference_match = re.search(
        r"Reference:\s+(\d+)x linear resolution, "
        r"(\d+)x(\d+) within-frame subpixel grid, (\d+)x MSAA",
        text,
    )
    tune_match = re.search(
        r"Reference tune:\s+MIP bias ([\d.+-]+), "
        r"sharpen ([\d.+-]+), ddx/ddy bias ([\d.+-]+)",
        text,
    )
    if reference_match is None or tune_match is None:
        raise RuntimeError("Reference CSV is missing supersample provenance")
    return {
        "results_csv": reports[0].name,
        "linear_resolution_scale": int(reference_match.group(1)),
        "subpixel_grid": [
            int(reference_match.group(2)),
            int(reference_match.group(3)),
        ],
        "msaa_samples": int(reference_match.group(4)),
        "mip_bias": float(tune_match.group(1)),
        "sharpen": float(tune_match.group(2)),
        "ddx_ddy_bias": float(tune_match.group(3)),
        "temporal_history": False,
        "classification": "high-quality spatial reference proxy",
    }


def luma(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.float32)
    return (
        values[..., 0] * 0.2126
        + values[..., 1] * 0.7152
        + values[..., 2] * 0.0722
    )


def rgb_mae(first: np.ndarray, second: np.ndarray) -> float:
    return float(
        np.abs(first.astype(np.int16) - second.astype(np.int16)).mean(
            dtype=np.float64
        )
    )


def rgb_psnr(first: np.ndarray, second: np.ndarray) -> float:
    difference = first.astype(np.float64) - second.astype(np.float64)
    mse = float(np.square(difference).mean(dtype=np.float64))
    if mse == 0.0:
        return float("inf")
    return 20.0 * math.log10(255.0 / math.sqrt(mse))


def luma_ssim(first: np.ndarray, second: np.ndarray) -> float:
    library = require_opencv()
    first_luma = luma(first)
    second_luma = luma(second)
    constant_1 = (0.01 * 255.0) ** 2
    constant_2 = (0.03 * 255.0) ** 2
    mean_first = library.GaussianBlur(first_luma, (11, 11), 1.5)
    mean_second = library.GaussianBlur(second_luma, (11, 11), 1.5)
    mean_first_sq = mean_first * mean_first
    mean_second_sq = mean_second * mean_second
    mean_product = mean_first * mean_second
    variance_first = (
        library.GaussianBlur(first_luma * first_luma, (11, 11), 1.5)
        - mean_first_sq
    )
    variance_second = (
        library.GaussianBlur(second_luma * second_luma, (11, 11), 1.5)
        - mean_second_sq
    )
    covariance = (
        library.GaussianBlur(first_luma * second_luma, (11, 11), 1.5)
        - mean_product
    )
    numerator = (
        (2.0 * mean_product + constant_1)
        * (2.0 * covariance + constant_2)
    )
    denominator = (
        (mean_first_sq + mean_second_sq + constant_1)
        * (variance_first + variance_second + constant_2)
    )
    values = numerator / np.maximum(denominator, 1.0e-12)
    if values.shape[0] > 10 and values.shape[1] > 10:
        values = values[5:-5, 5:-5]
    return float(values.mean(dtype=np.float64))


def luma_edge_strength(rgb: np.ndarray) -> float:
    library = require_opencv()
    values = luma(rgb)
    gradient_x = library.Sobel(
        values, library.CV_32F, 1, 0, ksize=3
    )
    gradient_y = library.Sobel(
        values, library.CV_32F, 0, 1, ksize=3
    )
    magnitude = library.magnitude(gradient_x, gradient_y)
    return float(magnitude.mean(dtype=np.float64))


def safe_percent_delta(current: float, baseline: float) -> float:
    if not math.isfinite(current) or not math.isfinite(baseline) or baseline == 0:
        return float("nan")
    return percent_delta(current, baseline)


def make_reference_gif(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
) -> str:
    keys = (REFERENCE_KEY,) + tuple(key for key, _, _ in MODES)
    frame_count = min(24, expected_frames)
    start = min(
        max(center_frame - frame_count // 2, 0),
        max(0, expected_frames - frame_count),
    )
    end = start + frame_count
    width = box[2] - box[0]
    height = box[3] - box[1]
    frames: list[Image.Image] = []
    for frame in range(start, end):
        canvas = Image.new("RGB", (width * len(keys), height + 35), "black")
        draw = ImageDraw.Draw(canvas)
        for column, key in enumerate(keys):
            with Image.open(paths[key][frame]) as source:
                cropped = source.convert("RGB").crop(box)
            x = column * width
            canvas.paste(cropped, (x, 35))
            draw.text(
                (x + 8, 10),
                f"{frame:05d} - {labels[key]}",
                fill="white",
            )
        frames.append(canvas.quantize(colors=192, method=Image.Quantize.MEDIANCUT))
    name = f"supersample_reference_{roi_name}_{start:05d}_{end - 1:05d}.gif"
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


def make_reference_sheet(
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
                cropped = source.convert("RGB").crop(box)
            x = column * width
            canvas.paste(cropped, (x, y + 35))
            draw.text(
                (x + 8, y + 10),
                f"{frame:05d} - {labels[key]}",
                fill="white",
            )
    name = (
        f"supersample_reference_sheet_{roi_name}_"
        f"{sampled[0]:05d}_{sampled[-1]:05d}.png"
    )
    canvas.save(output / name, compress_level=3)
    return name


def make_difference_sheet(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    roi_name: str,
    box: tuple[int, int, int, int],
    frame: int,
) -> str:
    keys = (REFERENCE_KEY,) + tuple(key for key, _, _ in MODES)
    width = box[2] - box[0]
    height = box[3] - box[1]
    header = 35
    row_height = height + header
    canvas = Image.new(
        "RGB", (width * len(keys), row_height * 2), "black"
    )
    draw = ImageDraw.Draw(canvas)
    images: dict[str, np.ndarray] = {}
    for column, key in enumerate(keys):
        with Image.open(paths[key][frame]) as source:
            crop = source.convert("RGB").crop(box)
        images[key] = np.asarray(crop)
        x = column * width
        canvas.paste(crop, (x, header))
        draw.text((x + 8, 10), labels[key], fill="white")

    reference = images[REFERENCE_KEY].astype(np.int16)
    for column, key in enumerate(keys):
        x = column * width
        y = row_height
        if key == REFERENCE_KEY:
            draw.text((x + 8, y + 10), "reference", fill="white")
            continue
        difference = np.clip(
            np.abs(images[key].astype(np.int16) - reference) * 4,
            0,
            255,
        ).astype(np.uint8)
        canvas.paste(Image.fromarray(difference), (x, y + header))
        draw.text((x + 8, y + 10), "abs difference x4", fill="white")
    name = f"supersample_reference_difference_{roi_name}_{frame:05d}.png"
    canvas.save(output / name, compress_level=3)
    return name


def main() -> None:
    global MODES
    args = parse_args()
    MODES = BASE_MODES + ((HYBRID_MODE,) if args.include_hybrid else ())
    require_opencv()
    if args.expected_frames < 2:
        raise SystemExit("--expected-frames must be at least 2")

    reference_root = args.reference_root.resolve()
    comparison_root = args.comparison_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else reference_root / "SupersampleReferenceAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)

    reference_frames, reference_resolution, reference_validation = (
        validate_reference(reference_root, args.expected_frames)
    )
    comparison_paths, comparison_resolution, comparison_validation = (
        validate_inputs(comparison_root, args.expected_frames, MODES)
    )
    if comparison_resolution != reference_resolution:
        raise RuntimeError(
            f"Reference resolution {reference_resolution} differs from "
            f"comparison resolution {comparison_resolution}"
        )
    provenance = read_reference_provenance(reference_root)
    boxes = roi_boxes(args.scenario, reference_resolution)
    paths = {REFERENCE_KEY: reference_frames, **comparison_paths}
    labels = {
        REFERENCE_KEY: REFERENCE_LABEL,
        **{key: semantic_id for key, semantic_id, _ in MODES},
    }

    rows: list[dict[str, Any]] = []
    previous_rois: dict[str, dict[str, np.ndarray]] | None = None
    all_keys = (REFERENCE_KEY,) + tuple(key for key, _, _ in MODES)

    for frame in range(args.expected_frames):
        current_full = {
            key: load_rgb(paths[key][frame]) for key in all_keys
        }
        current_rois = {
            roi_name: {
                key: crop_half(current_full[key], box) for key in all_keys
            }
            for roi_name, box in boxes.items()
        }
        row: dict[str, Any] = {"frame": frame}
        for roi_name, roi_values in current_rois.items():
            reference = roi_values[REFERENCE_KEY]
            reference_edge = luma_edge_strength(reference)
            row[f"{roi_name}_reference_edge_strength"] = reference_edge
            for key, _, _ in MODES:
                current = roi_values[key]
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
                row[f"{prefix}_edge_strength"] = edge
                row[f"{prefix}_edge_ratio_vs_reference"] = (
                    edge / reference_edge if reference_edge > 0.0 else float("nan")
                )

            if previous_rois is not None:
                for key in all_keys:
                    row[f"{roi_name}_{key}_adjacent_rgb_mae"] = rgb_mae(
                        roi_values[key], previous_rois[roi_name][key]
                    )
        rows.append(row)
        previous_rois = current_rois
        if frame % 20 == 0 or frame == args.expected_frames - 1:
            print(
                f"Processed {frame + 1}/{args.expected_frames} frames",
                flush=True,
            )

    csv_name = "supersample_reference_quality_metrics.csv"
    fieldnames = list(rows[-1])
    with (output / csv_name).open(
        "w", newline="", encoding="utf-8-sig"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    summary = {
        key: aggregate(rows, key)
        for key in fieldnames
        if key != "frame"
    }

    comparisons: dict[str, Any] = {}
    for roi_name in boxes:
        mode_errors = {
            key: summary[f"{roi_name}_{key}_rgb_mae_vs_reference"]["mean"]
            for key, _, _ in MODES
        }
        comparison = {
            "mae_rank_best_to_worst": sorted(
                mode_errors, key=mode_errors.get
            ),
            "mode_mae": mode_errors,
            "standard_vs_o_1x_percent": safe_percent_delta(
                mode_errors["standard"], mode_errors["o_1x"]
            ),
            "candidate_jitter_vs_o_1x_percent": safe_percent_delta(
                mode_errors["candidate_jitter"], mode_errors["o_1x"]
            ),
            "candidate_no_jitter_vs_o_1x_percent": safe_percent_delta(
                mode_errors["candidate_no_jitter"], mode_errors["o_1x"]
            ),
            "candidate_no_jitter_vs_candidate_jitter_percent": (
                safe_percent_delta(
                    mode_errors["candidate_no_jitter"],
                    mode_errors["candidate_jitter"],
                )
            ),
        }
        if args.include_hybrid:
            comparison["candidate_dejitter_vs_o_1x_percent"] = (
                safe_percent_delta(
                    mode_errors["candidate_dejitter"],
                    mode_errors["o_1x"],
                )
            )
            comparison[
                "candidate_dejitter_vs_candidate_jitter_percent"
            ] = safe_percent_delta(
                mode_errors["candidate_dejitter"],
                mode_errors["candidate_jitter"],
            )
            comparison[
                "candidate_dejitter_vs_candidate_no_jitter_percent"
            ] = safe_percent_delta(
                mode_errors["candidate_dejitter"],
                mode_errors["candidate_no_jitter"],
            )
        comparisons[roi_name] = comparison

    center = visual_center_frame(args.scenario)
    artifact_names: list[str] = []
    for roi_name in visual_regions(args.scenario):
        if roi_name not in boxes:
            continue
        artifact_names.append(
            make_reference_gif(
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
            make_reference_sheet(
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
            make_difference_sheet(
                output,
                paths,
                labels,
                roi_name,
                boxes[roi_name],
                min(center, args.expected_frames - 1),
            )
        )

    result = {
        "scenario": args.scenario,
        "conditions": {
            "resolution": list(reference_resolution),
            "analysis_resolution": "each ROI at half width/height",
            "frame_rate": 60,
            "reference_warmup_frames": args.reference_warmup_frames,
            "comparison_warmup_frames": args.comparison_warmup_frames,
            "capture_frames": args.expected_frames,
            "same_frame_metric_frames": args.expected_frames,
            "adjacent_metric_frames": max(0, args.expected_frames - 1),
            "hybrid_mode_included": args.include_hybrid,
            "ssim": (
                "luma SSIM, 11x11 Gaussian window, sigma 1.5, "
                "K1 0.01, K2 0.03, data range 255"
            ),
        },
        "reference_provenance": provenance,
        "reference_validation": reference_validation,
        "comparison_validation": comparison_validation,
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "comparisons": comparisons,
        "artifacts": artifact_names,
    }
    json_name = "supersample_reference_quality_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# SMAA supersample spatial-reference 품질 분석",
        "",
        "## 범위",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 해상도: {reference_resolution[0]}×{reference_resolution[1]}",
        f"- reference warm-up {args.reference_warmup_frames}프레임, comparison warm-up {args.comparison_warmup_frames}프레임",
        f"- 저장 프레임: mode별 {args.expected_frames}",
        f"- same-frame reference 지표: {args.expected_frames}프레임 전체, "
        f"adjacent-frame 지표: {max(0, args.expected_frames - 1)}쌍",
        f"- reference: {provenance['linear_resolution_scale']}× 선형 해상도, "
        f"{provenance['subpixel_grid'][0]}×{provenance['subpixel_grid'][1]} "
        f"within-frame grid, {provenance['msaa_samples']}×MSAA",
        f"- reference tuning: MIP bias {provenance['mip_bias']:.3f}, "
        f"sharpen {provenance['sharpen']:.3f}, "
        f"ddx/ddy bias {provenance['ddx_ddy_bias']:.3f}",
        "- reference는 temporal history 없이 한 출력 프레임의 장면 상태를 고정해 생성",
        "- 지표는 각 ROI를 1/2 해상도로 축소해 계산",
        "",
        "이 reference는 CMAA2 데모의 고품질 spatial supersample proxy다. Path-traced",
        "절대 ground truth가 아니며 demo 고유의 MIP·sharpen·ddx/ddy 보정이 포함된다.",
        "따라서 작은 차이만으로 절대 품질 우위를 주장하지 않고 sequence와 difference",
        "sheet를 함께 확인한다.",
    ]

    for roi_name in boxes:
        comparison = comparisons[roi_name]
        report.extend(
            [
                "",
                f"## `{roi_name}`",
                "",
                "| Mode | Reference RGB MAE | PSNR | Luma SSIM | Edge/reference |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for key, semantic_id, _ in MODES:
            prefix = f"{roi_name}_{key}"
            report.append(
                f"| `{semantic_id}` | "
                f"{summary[f'{prefix}_rgb_mae_vs_reference']['mean']:.6f} | "
                f"{summary[f'{prefix}_rgb_psnr_vs_reference']['mean']:.4f} dB | "
                f"{summary[f'{prefix}_luma_ssim_vs_reference']['mean']:.6f} | "
                f"{summary[f'{prefix}_edge_ratio_vs_reference']['mean']:.6f} |"
            )
        report.extend(
            [
                "",
                "- MAE 순위: "
                + " < ".join(
                    f"`{labels[key]}`"
                    for key in comparison["mae_rank_best_to_worst"]
                ),
                f"- `O-T2X-R` vs `O-1X`: {comparison['standard_vs_o_1x_percent']:+.3f}%",
                f"- Jitter On candidate vs `O-1X`: {comparison['candidate_jitter_vs_o_1x_percent']:+.3f}%",
                f"- Jitter Off candidate vs `O-1X`: {comparison['candidate_no_jitter_vs_o_1x_percent']:+.3f}%",
                f"- Jitter Off vs Jitter On candidate: {comparison['candidate_no_jitter_vs_candidate_jitter_percent']:+.3f}%",
            ]
        )
        if args.include_hybrid:
            report.extend(
                [
                    f"- DeJitter candidate vs `O-1X`: {comparison['candidate_dejitter_vs_o_1x_percent']:+.3f}%",
                    f"- DeJitter vs Jitter On candidate: {comparison['candidate_dejitter_vs_candidate_jitter_percent']:+.3f}%",
                    f"- DeJitter vs Jitter Off candidate: {comparison['candidate_dejitter_vs_candidate_no_jitter_percent']:+.3f}%",
                ]
            )

    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- Reference 내부 3×3 offset은 한 프레임 안의 spatial sampling이며 temporal history가 아니다.",
            "- Reference의 sharpen와 MIP·ddx/ddy 보정 때문에 완전한 물리적 ground truth는 아니다.",
            "- 같은 프레임 reference 오차는 blur와 ghost 모두 벌점으로 반영하지만 원인을 자동 분류하지 않는다.",
            "- SSIM과 PSNR은 ROI 1/2 해상도에서 계산했다.",
            "- `-R` mode는 camera-motion reprojection만 사용하고 object motion vector는 없다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 지표: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
        ]
    )
    report.extend(f"- 비교 자료: `{name}`" for name in artifact_names)
    report.append("")
    report_name = "SMAA-Supersample-Reference-Analysis-ko.md"
    (output / report_name).write_text(
        "\n".join(report), encoding="utf-8"
    )
    print(f"Supersample reference analysis complete: {output}", flush=True)


if __name__ == "__main__":
    main()
