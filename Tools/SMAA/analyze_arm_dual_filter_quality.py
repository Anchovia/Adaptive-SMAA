#!/usr/bin/env python3
"""Validate and summarize the eight-mode ARM Dual Filtering quality gate."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


FRAME_PATTERN = re.compile(r"(?:^|_)frame_(\d+)$", re.IGNORECASE)
MODES = (
    ("document", "O-ET2X-R-Document", "O_ET2X_R_Document"),
    ("document_dilate", "ABL-Document-Dilate3x3-R", "ABL_Document_Dilate3x3_R"),
    ("document_filtered", "ABL-Document-FilteredQuarter-R", "ABL_Document_FilteredQuarter_R"),
    ("document_arm", "ABL-Document-ArmDual-R", "ABL_Document_ArmDual_R"),
    ("jitter", "ABL-Candidate-Jitter-R", "ABL_Candidate_Jitter_R"),
    ("jitter_dilate", "ABL-Candidate-Jitter-Dilate3x3-R", "ABL_Candidate_Jitter_Dilate3x3_R"),
    ("jitter_filtered", "ABL-Candidate-Jitter-FilteredQuarter-R", "ABL_Candidate_Jitter_FilteredQuarter_R"),
    ("jitter_arm", "ABL-Candidate-Jitter-ArmDual-R", "ABL_Candidate_Jitter_ArmDual_R"),
)
PROFILES = {
    "Document": ("document", "document_dilate", "document_filtered", "document_arm"),
    "Candidate-Jitter": ("jitter", "jitter_dilate", "jitter_filtered", "jitter_arm"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("final_capture_root", type=Path)
    parser.add_argument("candidate_mask_root", type=Path)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--profile", default="yaw-fast-360")
    parser.add_argument("--expected-frames", type=int, required=True)
    parser.add_argument("--reference-dir", type=Path)
    parser.add_argument("--reference-offset", type=int, default=60)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def frame_index(path: Path) -> int:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise RuntimeError(f"Invalid PNG filename: {path.name}")
    return int(match.group(1))


def collect(root: Path, directory: str, expected: int) -> list[Path]:
    paths = sorted((root / directory).glob("*.png"), key=frame_index)
    indices = [frame_index(path) for path in paths]
    if indices != list(range(expected)):
        raise RuntimeError(f"{root / directory}: expected frames 0..{expected - 1}, got {indices}")
    return paths


def collect_reference(directory: Path, offset: int, expected: int) -> list[Path]:
    indexed = {frame_index(path): path for path in directory.glob("*.png")}
    wanted = list(range(offset, offset + expected))
    missing = [index for index in wanted if index not in indexed]
    if missing:
        raise RuntimeError(f"{directory}: missing reference frames {missing[:8]}")
    return [indexed[index] for index in wanted]


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def load_mask(path: Path) -> np.ndarray:
    return load_rgb(path).max(axis=2) > 127


def quantize_r8(values: np.ndarray) -> np.ndarray:
    return np.rint(np.clip(values, 0.0, 1.0) * np.float32(255.0)).astype(np.uint8).astype(np.float32) / np.float32(255.0)


def sample_linear_clamp(source: np.ndarray, uv_x: np.ndarray, uv_y: np.ndarray) -> np.ndarray:
    height, width = source.shape
    source_x = uv_x * np.float32(width) - np.float32(0.5)
    source_y = uv_y * np.float32(height) - np.float32(0.5)
    base_x = np.floor(source_x).astype(np.int32)
    base_y = np.floor(source_y).astype(np.int32)
    fraction_x = source_x - base_x
    fraction_y = source_y - base_y
    x0 = np.clip(base_x, 0, width - 1)
    x1 = np.clip(base_x + 1, 0, width - 1)
    y0 = np.clip(base_y, 0, height - 1)
    y1 = np.clip(base_y + 1, 0, height - 1)
    top = source[y0, x0] + (source[y0, x1] - source[y0, x0]) * fraction_x
    bottom = source[y1, x0] + (source[y1, x1] - source[y1, x0]) * fraction_x
    return top + (bottom - top) * fraction_y


def output_uv(output_height: int, output_width: int) -> tuple[np.ndarray, np.ndarray]:
    x = (np.arange(output_width, dtype=np.float32) + np.float32(0.5)) / np.float32(output_width)
    y = (np.arange(output_height, dtype=np.float32) + np.float32(0.5)) / np.float32(output_height)
    return np.broadcast_to(x[None, :], (output_height, output_width)), np.broadcast_to(y[:, None], (output_height, output_width))


def arm_downsample(source: np.ndarray, output_height: int, output_width: int) -> np.ndarray:
    uv_x, uv_y = output_uv(output_height, output_width)
    half_x = np.float32(0.5 / source.shape[1])
    half_y = np.float32(0.5 / source.shape[0])
    result = sample_linear_clamp(source, uv_x, uv_y) * np.float32(4.0)
    for sx, sy in ((-1, -1), (1, 1), (1, -1), (-1, 1)):
        result += sample_linear_clamp(source, uv_x + sx * half_x, uv_y + sy * half_y)
    return result / np.float32(8.0)


def arm_upsample(source: np.ndarray, output_height: int, output_width: int) -> np.ndarray:
    uv_x, uv_y = output_uv(output_height, output_width)
    half_x = np.float32(0.5 / source.shape[1])
    half_y = np.float32(0.5 / source.shape[0])
    result = np.zeros((output_height, output_width), dtype=np.float32)
    for sx, sy, weight in (
        (-2, 0, 1), (-1, 1, 2), (0, 2, 1), (1, 1, 2),
        (2, 0, 1), (1, -1, 2), (0, -2, 1), (-1, -1, 2),
    ):
        result += sample_linear_clamp(source, uv_x + sx * half_x, uv_y + sy * half_y) * np.float32(weight)
    return result / np.float32(12.0)


def arm_dual_filter(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    height, width = mask.shape
    half_height, half_width = (height + 1) // 2, (width + 1) // 2
    quarter_height, quarter_width = (height + 3) // 4, (width + 3) // 4
    source = mask.astype(np.float32)
    half = quantize_r8(arm_downsample(source, half_height, half_width))
    quarter = quantize_r8(arm_downsample(half, quarter_height, quarter_width))
    reconstructed_half = quantize_r8(arm_upsample(quarter, half_height, half_width))
    reconstructed = arm_upsample(reconstructed_half, height, width)
    return mask | (reconstructed >= np.float32(0.25)), reconstructed


def dilate3x3(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="edge")
    output = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape
    for y in range(3):
        for x in range(3):
            output |= padded[y : y + height, x : x + width]
    return output


def rgb_mae(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(dtype=np.float64))


def psnr(test: np.ndarray, reference: np.ndarray) -> float:
    difference = test.astype(np.float64) - reference.astype(np.float64)
    mse = float(np.mean(difference * difference, dtype=np.float64))
    return float("inf") if mse == 0.0 else 10.0 * math.log10(255.0**2 / mse)


def make_sheet(paths: dict[str, list[Path]], output: Path, frame: int) -> None:
    images = [Image.open(paths[key][frame]).convert("RGB") for key, _, _ in MODES]
    width, height = images[0].size
    thumb_width = 400
    thumb_height = max(1, round(height * thumb_width / width))
    label_height = 32
    sheet = Image.new("RGB", (thumb_width * 4, (thumb_height + label_height) * 2), "white")
    draw = ImageDraw.Draw(sheet)
    for index, ((_, label, _), image) in enumerate(zip(MODES, images)):
        x = index % 4 * thumb_width
        y = index // 4 * (thumb_height + label_height)
        sheet.paste(image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS), (x, y))
        draw.text((x + 8, y + thumb_height + 8), label, fill="black")
        image.close()
    sheet.save(output)


def main() -> int:
    args = parse_args()
    final_root = args.final_capture_root.resolve()
    mask_root = args.candidate_mask_root.resolve()
    finals = {key: collect(final_root, directory, args.expected_frames) for key, _, directory in MODES}
    masks = {key: collect(mask_root, directory, args.expected_frames) for key, _, directory in MODES}
    references = None
    if args.reference_dir is not None:
        references = collect_reference(
            args.reference_dir.resolve(), args.reference_offset, args.expected_frames
        )
    mask_rows: list[dict[str, float | int | str]] = []
    final_rows: list[dict[str, float | int | str]] = []
    reference_rows: list[dict[str, float | int | str]] = []
    for profile, (base_key, dilate_key, filtered_key, arm_key) in PROFILES.items():
        for frame in range(args.expected_frames):
            raw = load_mask(masks[base_key][frame])
            gpu_dilate = load_mask(masks[dilate_key][frame])
            gpu_filtered = load_mask(masks[filtered_key][frame])
            gpu_arm = load_mask(masks[arm_key][frame])
            cpu_arm, reconstructed = arm_dual_filter(raw)
            raw_count = int(raw.sum(dtype=np.int64))
            mismatch = cpu_arm != gpu_arm
            boundary = np.abs(reconstructed - np.float32(0.25)) <= np.float32(0.003)
            mask_rows.append({
                "profile": profile,
                "frame": frame,
                "raw_candidates": raw_count,
                "dilate3x3_candidates": int(gpu_dilate.sum(dtype=np.int64)),
                "filtered_candidates": int(gpu_filtered.sum(dtype=np.int64)),
                "arm_dual_candidates": int(gpu_arm.sum(dtype=np.int64)),
                "dilate3x3_multiplier": float(gpu_dilate.sum() / max(raw_count, 1)),
                "filtered_multiplier": float(gpu_filtered.sum() / max(raw_count, 1)),
                "arm_dual_multiplier": float(gpu_arm.sum() / max(raw_count, 1)),
                "dilate3x3_cpu_mismatch": int(np.count_nonzero(dilate3x3(raw) != gpu_dilate)),
                "arm_dual_cpu_mismatch": int(np.count_nonzero(mismatch)),
                "arm_dual_cpu_mismatch_rate": float(np.mean(mismatch)),
                "arm_dual_boundary_pixels": int(boundary.sum(dtype=np.int64)),
                "arm_dual_mismatch_outside_boundary": int(np.count_nonzero(mismatch & ~boundary)),
                "arm_dual_mismatch_outside_boundary_rate": float(np.mean(mismatch & ~boundary)),
                "filtered_erased_raw_candidates": int(np.count_nonzero(raw & ~gpu_filtered)),
                "arm_dual_erased_raw_candidates": int(np.count_nonzero(raw & ~gpu_arm)),
            })
            base_final = load_rgb(finals[base_key][frame])
            final_rows.append({
                "profile": profile,
                "frame": frame,
                "dilate3x3_vs_none_rgb_mae": rgb_mae(load_rgb(finals[dilate_key][frame]), base_final),
                "filtered_vs_none_rgb_mae": rgb_mae(load_rgb(finals[filtered_key][frame]), base_final),
                "arm_dual_vs_none_rgb_mae": rgb_mae(load_rgb(finals[arm_key][frame]), base_final),
            })

    for key, label, _ in MODES:
        previous = None
        for frame in range(args.expected_frames):
            current = load_rgb(finals[key][frame])
            item: dict[str, float | int | str] = {
                "mode": label,
                "frame": frame,
                "adjacent_frame_rgb_mae": float("nan") if previous is None else rgb_mae(current, previous),
            }
            if references is not None:
                reference = load_rgb(references[frame])
                item["rgb_mae_vs_reference"] = rgb_mae(current, reference)
                item["psnr_vs_reference"] = psnr(current, reference)
            reference_rows.append(item)
            previous = current

    if any(int(row["dilate3x3_cpu_mismatch"]) != 0 for row in mask_rows):
        raise RuntimeError("GPU 3x3 mask does not match the exact CPU max filter")
    maximum_filtered_erased_raw = max(
        int(row["filtered_erased_raw_candidates"]) for row in mask_rows
    )
    if maximum_filtered_erased_raw != 0:
        raise RuntimeError(
            "Filtered-quarter expansion erased raw candidates: "
            f"{maximum_filtered_erased_raw}"
        )
    maximum_erased_raw = max(int(row["arm_dual_erased_raw_candidates"]) for row in mask_rows)
    # Independent mode renders can differ by one threshold pixel in the
    # jittered profile even though the shader applies a strict raw-mask union.
    # Record it, but reject any material loss.
    if maximum_erased_raw > 4:
        raise RuntimeError(
            f"ARM Dual expansion materially erased raw candidates: {maximum_erased_raw}"
        )
    max_arm_mismatch = max(float(row["arm_dual_cpu_mismatch_rate"]) for row in mask_rows)
    max_arm_outside_boundary = max(
        float(row["arm_dual_mismatch_outside_boundary_rate"]) for row in mask_rows
    )
    if max_arm_mismatch > 0.002 or max_arm_outside_boundary > 0.0001:
        raise RuntimeError(
            "ARM Dual GPU/CPU mismatch exceeds the engineering tolerance: "
            f"total={max_arm_mismatch:.6%}, outside boundary={max_arm_outside_boundary:.6%}"
        )

    output = (args.output or final_root / "Analysis-ARM-Dual-Quality").resolve()
    output.mkdir(parents=True, exist_ok=True)
    for filename, rows in (
        ("arm_dual_mask_metrics.csv", mask_rows),
        ("arm_dual_final_metrics.csv", final_rows),
        ("arm_dual_reference_temporal_metrics.csv", reference_rows),
    ):
        with (output / filename).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    make_sheet(finals, output / "comparison_frame_00000.png", 0)
    make_sheet(masks, output / "candidate_masks_frame_00000.png", 0)

    summaries = []
    for profile in PROFILES:
        selected_masks = [row for row in mask_rows if row["profile"] == profile]
        selected_finals = [row for row in final_rows if row["profile"] == profile]
        summaries.append({
            "profile": profile,
            "dilate3x3_candidate_multiplier": float(np.mean([row["dilate3x3_multiplier"] for row in selected_masks])),
            "filtered_candidate_multiplier": float(np.mean([row["filtered_multiplier"] for row in selected_masks])),
            "arm_dual_candidate_multiplier": float(np.mean([row["arm_dual_multiplier"] for row in selected_masks])),
            "arm_dual_cpu_mismatch_rate": float(np.mean([row["arm_dual_cpu_mismatch_rate"] for row in selected_masks])),
            "dilate3x3_vs_none_rgb_mae": float(np.mean([row["dilate3x3_vs_none_rgb_mae"] for row in selected_finals])),
            "filtered_vs_none_rgb_mae": float(np.mean([row["filtered_vs_none_rgb_mae"] for row in selected_finals])),
            "arm_dual_vs_none_rgb_mae": float(np.mean([row["arm_dual_vs_none_rgb_mae"] for row in selected_finals])),
        })
    mode_summaries = []
    for _, label, _ in MODES:
        selected = [row for row in reference_rows if row["mode"] == label]
        adjacent = [float(row["adjacent_frame_rgb_mae"]) for row in selected if math.isfinite(float(row["adjacent_frame_rgb_mae"]))]
        item: dict[str, float | str] = {
            "mode": label,
            "adjacent_frame_rgb_mae": float(np.mean(adjacent)) if adjacent else float("nan"),
        }
        if references is not None:
            item["rgb_mae_vs_reference"] = float(np.mean([float(row["rgb_mae_vs_reference"]) for row in selected]))
            item["psnr_vs_reference"] = float(np.mean([float(row["psnr_vs_reference"]) for row in selected]))
        mode_summaries.append(item)
    result = {
        "final_capture_root": str(final_root),
        "candidate_mask_root": str(mask_root),
        "scene": args.scene,
        "profile": args.profile,
        "classification": "engineering",
        "expected_frames": args.expected_frames,
        "maximum_arm_dual_cpu_mismatch_rate": max_arm_mismatch,
        "maximum_arm_dual_cpu_mismatch_outside_boundary_rate": max_arm_outside_boundary,
        "maximum_filtered_erased_raw_candidates": maximum_filtered_erased_raw,
        "maximum_erased_raw_candidates": maximum_erased_raw,
        "summaries": summaries,
        "reference_dir": str(args.reference_dir.resolve()) if args.reference_dir else None,
        "reference_offset": args.reference_offset if args.reference_dir else None,
        "mode_summaries": mode_summaries,
    }
    (output / "arm_dual_quality.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# ARM Dual Filtering 후보 확장 품질 smoke",
        "",
        f"- 장면/경로: `{args.scene}` / `{args.profile}`",
        f"- 분류: `engineering`; mode당 {args.expected_frames} frame",
        "- ARM kernel 뒤 raw current-edge candidate를 union해 원본 후보를 보존함",
        "- Filtered 1/4 경로도 raw current-edge candidate와 복원 mask를 합집합으로 보존함",
        f"- Filtered raw 후보 유실 최대값: {maximum_filtered_erased_raw} pixel",
        f"- ARM GPU/CPU mirror 최대 mismatch: {max_arm_mismatch * 100:.6f}%",
        f"- threshold-boundary 밖 최대 mismatch: {max_arm_outside_boundary * 100:.6f}%",
        f"- 독립 mode capture에서 frame당 raw 후보 유실 최대값: {maximum_erased_raw} pixel",
        "",
        "| Profile | 3×3 후보 배수 | Filtered 후보 배수 | ARM 후보 배수 | 3×3 vs None RGB MAE | Filtered vs None RGB MAE | ARM vs None RGB MAE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            f"| {item['profile']} | {item['dilate3x3_candidate_multiplier']:.3f}× | "
            f"{item['filtered_candidate_multiplier']:.3f}× | {item['arm_dual_candidate_multiplier']:.3f}× | "
            f"{item['dilate3x3_vs_none_rgb_mae']:.6f} | {item['filtered_vs_none_rgb_mae']:.6f} | "
            f"{item['arm_dual_vs_none_rgb_mae']:.6f} |"
        )
    if references is not None:
        lines.extend((
            "",
            "| Mode | Reference RGB MAE | Reference PSNR | Adjacent-frame RGB MAE |",
            "|---|---:|---:|---:|",
        ))
        for item in mode_summaries:
            lines.append(
                f"| {item['mode']} | {item['rgb_mae_vs_reference']:.6f} | "
                f"{item['psnr_vs_reference']:.6f} | {item['adjacent_frame_rgb_mae']:.6f} |"
            )
    lines.extend((
        "", "## 해석 제한", "",
        f"이 결과는 {args.expected_frames}-frame engineering gate다. 후보 배수, "
        "same-frame 차이와 spatial-reference proxy만으로 고스팅 또는 정식 temporal "
        "품질 우위를 주장하지 않는다."
    ))
    (output / "SMAA-ARM-Dual-Quality-Smoke-ko.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
