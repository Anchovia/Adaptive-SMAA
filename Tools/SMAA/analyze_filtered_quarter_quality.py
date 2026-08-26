#!/usr/bin/env python3
"""Analyze the six-mode filtered-quarter candidate-expansion quality smoke."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


FRAME_PATTERN = re.compile(r"(?:^|_)frame_(\d+)$", re.IGNORECASE)
MODES = (
    ("document", "O-ET2X-R-Document", "O_ET2X_R_Document"),
    (
        "document_dilate3x3",
        "ABL-Document-Dilate3x3-R",
        "ABL_Document_Dilate3x3_R",
    ),
    (
        "document_filtered_quarter",
        "ABL-Document-FilteredQuarter-R",
        "ABL_Document_FilteredQuarter_R",
    ),
    ("candidate_jitter", "ABL-Candidate-Jitter-R", "ABL_Candidate_Jitter_R"),
    (
        "candidate_jitter_dilate3x3",
        "ABL-Candidate-Jitter-Dilate3x3-R",
        "ABL_Candidate_Jitter_Dilate3x3_R",
    ),
    (
        "candidate_jitter_filtered_quarter",
        "ABL-Candidate-Jitter-FilteredQuarter-R",
        "ABL_Candidate_Jitter_FilteredQuarter_R",
    ),
)
PROFILES = {
    "Document": (
        "document",
        "document_dilate3x3",
        "document_filtered_quarter",
    ),
    "Candidate-Jitter": (
        "candidate_jitter",
        "candidate_jitter_dilate3x3",
        "candidate_jitter_filtered_quarter",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("final_capture_root", type=Path)
    parser.add_argument("candidate_mask_root", type=Path)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--profile", default="yaw-fast-360")
    parser.add_argument("--expected-frames", type=int, required=True)
    parser.add_argument("--baseline-capture-root", type=Path)
    parser.add_argument(
        "--classification", choices=("engineering", "formal"), default="engineering"
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def frame_index(path: Path) -> int:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise RuntimeError(f"Invalid PNG filename: {path.name}")
    return int(match.group(1))


def collect(root: Path, directory: str, expected: int) -> list[Path]:
    paths = sorted((root / directory).glob("*.png"), key=frame_index)
    if [frame_index(path) for path in paths] != list(range(expected)):
        raise RuntimeError(f"{root / directory}: expected frames 0..{expected - 1}")
    return paths


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dilate3x3(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="edge")
    output = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape
    for y in range(3):
        for x in range(3):
            output |= padded[y : y + height, x : x + width]
    return output


def filtered_quarter(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mirror the documented GPU path with float32 arithmetic.

    The R8 conversion and GPU fused arithmetic can move pixels immediately next
    to the 0.25 threshold.  The caller records that boundary mismatch instead of
    claiming bit identity for the filtered path.
    """

    height, width = mask.shape
    quarter_height = (height + 3) // 4
    quarter_width = (width + 3) // 4
    quarter = np.empty((quarter_height, quarter_width), dtype=np.float32)
    for y in range(quarter_height):
        for x in range(quarter_width):
            quarter[y, x] = mask[
                y * 4 : min((y + 1) * 4, height),
                x * 4 : min((x + 1) * 4, width),
            ].mean(dtype=np.float64)
    quarter = np.rint(quarter * np.float32(255.0)).astype(np.uint8)
    quarter_float = quarter.astype(np.float32) / np.float32(255.0)

    ratio_x = np.float32(quarter_width) / np.float32(width)
    ratio_y = np.float32(quarter_height) / np.float32(height)
    source_x = (
        (np.arange(width, dtype=np.float32) + np.float32(0.5)) * ratio_x
        - np.float32(0.5)
    )
    source_y = (
        (np.arange(height, dtype=np.float32) + np.float32(0.5)) * ratio_y
        - np.float32(0.5)
    )
    base_x = np.floor(source_x).astype(np.int32)
    base_y = np.floor(source_y).astype(np.int32)
    fraction_x = source_x - base_x
    fraction_y = source_y - base_y
    x0 = np.clip(base_x, 0, quarter_width - 1)
    x1 = np.clip(base_x + 1, 0, quarter_width - 1)
    y0 = np.clip(base_y, 0, quarter_height - 1)
    y1 = np.clip(base_y + 1, 0, quarter_height - 1)
    top = quarter_float[y0[:, None], x0[None, :]] + (
        quarter_float[y0[:, None], x1[None, :]]
        - quarter_float[y0[:, None], x0[None, :]]
    ) * fraction_x[None, :]
    bottom = quarter_float[y1[:, None], x0[None, :]] + (
        quarter_float[y1[:, None], x1[None, :]]
        - quarter_float[y1[:, None], x0[None, :]]
    ) * fraction_x[None, :]
    reconstructed = top + (bottom - top) * fraction_y[:, None]
    return mask | (reconstructed >= np.float32(0.25)), reconstructed


def rgb_mae(first: np.ndarray, second: np.ndarray) -> float:
    return float(
        np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(
            dtype=np.float64
        )
    )


def make_sheet(paths: dict[str, list[Path]], output: Path, frame: int) -> None:
    images = [Image.open(paths[key][frame]).convert("RGB") for key, _, _ in MODES]
    width, height = images[0].size
    thumb_width = 480
    thumb_height = max(1, round(height * thumb_width / width))
    label_height = 32
    sheet = Image.new("RGB", (thumb_width * 3, (thumb_height + label_height) * 2), "white")
    draw = ImageDraw.Draw(sheet)
    for index, ((_, label, _), image) in enumerate(zip(MODES, images)):
        x = index % 3 * thumb_width
        y = index // 3 * (thumb_height + label_height)
        sheet.paste(image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS), (x, y))
        draw.text((x + 8, y + thumb_height + 8), label, fill="black")
        image.close()
    sheet.save(output)


def main() -> int:
    args = parse_args()
    final_root = args.final_capture_root.resolve()
    mask_root = args.candidate_mask_root.resolve()
    paths = {key: collect(final_root, directory, args.expected_frames) for key, _, directory in MODES}
    masks = {key: collect(mask_root, directory, args.expected_frames) for key, _, directory in MODES}

    deterministic_mismatches = None
    deterministic_pixel_mismatches = None
    deterministic_max_channel_delta = None
    if args.baseline_capture_root:
        baseline_root = args.baseline_capture_root.resolve()
        deterministic_mismatches = 0
        deterministic_pixel_mismatches = 0
        deterministic_max_channel_delta = 0
        deterministic_total_pixels = 0
        for key, _, directory in MODES:
            baseline = collect(baseline_root, directory, args.expected_frames)
            for first, second in zip(paths[key], baseline):
                deterministic_mismatches += sha256(first) != sha256(second)
                first_rgb = load_rgb(first)
                second_rgb = load_rgb(second)
                difference = np.abs(
                    first_rgb.astype(np.int16) - second_rgb.astype(np.int16)
                )
                deterministic_pixel_mismatches += int(
                    np.any(difference != 0, axis=2).sum(dtype=np.int64)
                )
                deterministic_max_channel_delta = max(
                    deterministic_max_channel_delta, int(difference.max())
                )
                deterministic_total_pixels += first_rgb.shape[0] * first_rgb.shape[1]
        deterministic_pixel_mismatch_rate = (
            deterministic_pixel_mismatches / deterministic_total_pixels
        )
        if (
            deterministic_pixel_mismatch_rate > 0.00001
            or deterministic_max_channel_delta > 1
        ):
            raise RuntimeError(
                "Repeat capture exceeds the engineering pixel tolerance: "
                f"rate={deterministic_pixel_mismatch_rate:.9f}, "
                f"max delta={deterministic_max_channel_delta}"
            )

    mask_rows: list[dict[str, float | int | str]] = []
    final_rows: list[dict[str, float | int | str]] = []
    for profile, (base_key, dilated_key, filtered_key) in PROFILES.items():
        for frame in range(args.expected_frames):
            base = load_rgb(masks[base_key][frame]).max(axis=2) > 127
            gpu_dilated = load_rgb(masks[dilated_key][frame]).max(axis=2) > 127
            gpu_filtered = load_rgb(masks[filtered_key][frame]).max(axis=2) > 127
            cpu_dilated = dilate3x3(base)
            cpu_filtered, reconstructed = filtered_quarter(base)
            boundary = np.abs(reconstructed - np.float32(0.25)) <= np.float32(0.002)
            mask_rows.append(
                {
                    "profile": profile,
                    "frame": frame,
                    "raw_candidates": int(base.sum(dtype=np.int64)),
                    "dilate3x3_candidates": int(gpu_dilated.sum(dtype=np.int64)),
                    "filtered_candidates": int(gpu_filtered.sum(dtype=np.int64)),
                    "dilate3x3_multiplier": float(gpu_dilated.sum() / max(base.sum(), 1)),
                    "filtered_multiplier": float(gpu_filtered.sum() / max(base.sum(), 1)),
                    "dilate3x3_cpu_mismatch": int(np.count_nonzero(cpu_dilated != gpu_dilated)),
                    "filtered_cpu_mismatch": int(np.count_nonzero(cpu_filtered != gpu_filtered)),
                    "filtered_cpu_mismatch_rate": float(np.mean(cpu_filtered != gpu_filtered)),
                    "filtered_boundary_pixels": int(boundary.sum(dtype=np.int64)),
                    "filtered_erased_raw_candidates": int(
                        np.count_nonzero(base & ~gpu_filtered)
                    ),
                }
            )
            base_final = load_rgb(paths[base_key][frame])
            dilated_final = load_rgb(paths[dilated_key][frame])
            filtered_final = load_rgb(paths[filtered_key][frame])
            final_rows.append(
                {
                    "profile": profile,
                    "frame": frame,
                    "dilate3x3_vs_none_rgb_mae": rgb_mae(dilated_final, base_final),
                    "filtered_vs_none_rgb_mae": rgb_mae(filtered_final, base_final),
                    "filtered_vs_dilate3x3_rgb_mae": rgb_mae(
                        filtered_final, dilated_final
                    ),
                }
            )

    if any(row["dilate3x3_cpu_mismatch"] != 0 for row in mask_rows):
        raise RuntimeError("GPU 3x3 mask does not match the exact CPU max filter")
    maximum_filtered_erased_raw = max(
        int(row["filtered_erased_raw_candidates"]) for row in mask_rows
    )
    if maximum_filtered_erased_raw != 0:
        raise RuntimeError(
            "Filtered-quarter expansion erased raw candidates: "
            f"{maximum_filtered_erased_raw}"
        )
    maximum_filtered_mismatch_rate = max(
        float(row["filtered_cpu_mismatch_rate"]) for row in mask_rows
    )
    if maximum_filtered_mismatch_rate > 0.0005:
        raise RuntimeError(
            "Filtered-quarter GPU/CPU mismatch exceeds the 0.05% engineering tolerance"
        )

    output = (
        args.output or final_root / "Analysis-FilteredQuarter-Quality"
    ).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for filename, rows in (
        ("filtered_quarter_mask_metrics.csv", mask_rows),
        ("filtered_quarter_final_metrics.csv", final_rows),
    ):
        with (output / filename).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    make_sheet(paths, output / "comparison_frame_00000.png", 0)
    make_sheet(masks, output / "candidate_masks_frame_00000.png", 0)

    summaries = []
    for profile in PROFILES:
        selected = [row for row in mask_rows if row["profile"] == profile]
        quality = [row for row in final_rows if row["profile"] == profile]
        summaries.append(
            {
                "profile": profile,
                "dilate3x3_candidate_multiplier": float(
                    np.mean([row["dilate3x3_multiplier"] for row in selected])
                ),
                "filtered_candidate_multiplier": float(
                    np.mean([row["filtered_multiplier"] for row in selected])
                ),
                "filtered_cpu_mismatch_rate": float(
                    np.mean([row["filtered_cpu_mismatch_rate"] for row in selected])
                ),
                "dilate3x3_vs_none_rgb_mae": float(
                    np.mean([row["dilate3x3_vs_none_rgb_mae"] for row in quality])
                ),
                "filtered_vs_none_rgb_mae": float(
                    np.mean([row["filtered_vs_none_rgb_mae"] for row in quality])
                ),
            }
        )
    result = {
        "final_capture_root": str(final_root),
        "candidate_mask_root": str(mask_root),
        "scene": args.scene,
        "profile": args.profile,
        "classification": args.classification,
        "expected_frames": args.expected_frames,
        "deterministic_repeat_hash_mismatches": deterministic_mismatches,
        "deterministic_repeat_pixel_mismatches": deterministic_pixel_mismatches,
        "deterministic_repeat_max_channel_delta": deterministic_max_channel_delta,
        "maximum_filtered_cpu_mismatch_rate": maximum_filtered_mismatch_rate,
        "maximum_filtered_erased_raw_candidates": maximum_filtered_erased_raw,
        "summaries": summaries,
    }
    (output / "filtered_quarter_quality.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Filtered 1/4 후보 확장 품질 smoke",
        "",
        f"- 장면/경로: `{args.scene}` / `{args.profile}`",
        f"- 분류: `{args.classification}`; mode당 {args.expected_frames} frame",
        "- 3×3 GPU mask와 CPU max-filter: 모든 frame 0 pixel mismatch",
        "- Filtered 경로는 raw current-edge candidate와 복원 mask를 합집합으로 보존함",
        f"- Filtered raw 후보 유실 최대값: {maximum_filtered_erased_raw} pixel",
        f"- Filtered GPU/CPU 최대 mismatch 비율: {maximum_filtered_mismatch_rate * 100:.6f}%",
    ]
    if deterministic_mismatches is not None:
        lines.append(
            f"- 독립 반복: PNG hash mismatch {deterministic_mismatches}장, "
            f"실제 불일치 픽셀 {deterministic_pixel_mismatches}개, "
            f"최대 채널 차이 {deterministic_max_channel_delta}"
        )
    lines.extend(
        (
            "",
            "| Profile | 3×3 후보 배수 | Filtered 후보 배수 | 3×3 vs None RGB MAE | Filtered vs None RGB MAE |",
            "|---|---:|---:|---:|---:|",
        )
    )
    for item in summaries:
        lines.append(
            f"| {item['profile']} | {item['dilate3x3_candidate_multiplier']:.3f}× | "
            f"{item['filtered_candidate_multiplier']:.3f}× | "
            f"{item['dilate3x3_vs_none_rgb_mae']:.6f} | "
            f"{item['filtered_vs_none_rgb_mae']:.6f} |"
        )
    lines.extend(
        (
            "",
            "## 해석 제한",
            "",
            "이 결과는 축소 engineering smoke다. Filtered 경로의 소수 mismatch는 R8 양자화와 0.25 임계값 경계의 GPU 부동소수점 분류 차이로 별도 기록하며, bit-identical이라고 표현하지 않는다. 이 수치만으로 품질 또는 고스팅 우위를 주장하지 않는다.",
        )
    )
    (output / "SMAA-Filtered-Quarter-Quality-Smoke-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
