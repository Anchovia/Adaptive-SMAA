#!/usr/bin/env python3
"""Measure the ARM candidate-expansion ablation in a San Miguel thin-chair ROI."""

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
    parser.add_argument("reference_dir", type=Path)
    parser.add_argument("--expected-frames", type=int, default=60)
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=9)
    parser.add_argument("--roi", type=int, nargs=4, default=(0, 500, 1050, 1017))
    parser.add_argument("--representative-frame", type=int, default=3)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def frame_index(path: Path) -> int:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise RuntimeError(f"Invalid PNG filename: {path.name}")
    return int(match.group(1))


def collect(directory: Path, expected: int) -> list[Path]:
    paths = sorted(directory.glob("*.png"), key=frame_index)
    indices = [frame_index(path) for path in paths]
    if indices != list(range(expected)):
        raise RuntimeError(f"{directory}: expected 0..{expected - 1}, got {indices}")
    return paths


def load_rgb(path: Path, roi: tuple[int, int, int, int]) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB").crop(roi), dtype=np.float32)


def load_mask(path: Path, roi: tuple[int, int, int, int]) -> np.ndarray:
    return load_rgb(path, roi).max(axis=2) > 127.0


def mae(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.mean(np.abs(first - second)))


def psnr(first: np.ndarray, second: np.ndarray) -> float:
    mse = float(np.mean((first - second) ** 2))
    return math.inf if mse == 0.0 else 10.0 * math.log10((255.0 * 255.0) / mse)


def mean(values: list[float]) -> float:
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_sheet(
    finals: dict[str, list[Path]], references: list[Path], roi: tuple[int, int, int, int],
    frame: int, output: Path,
) -> None:
    entries = [("SS-Reference", references[frame])]
    entries.extend((label, finals[key][frame]) for key, label, _ in MODES)
    columns = 3
    thumb_width = 500
    roi_width = roi[2] - roi[0]
    roi_height = roi[3] - roi[1]
    thumb_height = max(1, round(roi_height * thumb_width / roi_width))
    label_height = 30
    rows = math.ceil(len(entries) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, path) in enumerate(entries):
        with Image.open(path) as source:
            crop = source.convert("RGB").crop(roi)
            crop = crop.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + label_height)
        sheet.paste(crop, (x, y))
        draw.text((x + 8, y + thumb_height + 7), label, fill="black")
    sheet.save(output)


def make_difference_sheet(
    finals: dict[str, list[Path]], references: list[Path], roi: tuple[int, int, int, int],
    frame: int, output: Path,
) -> None:
    reference = load_rgb(references[frame], roi)
    columns = 4
    thumb_width = 375
    roi_width = roi[2] - roi[0]
    roi_height = roi[3] - roi[1]
    thumb_height = max(1, round(roi_height * thumb_width / roi_width))
    label_height = 30
    sheet = Image.new("RGB", (columns * thumb_width, 2 * (thumb_height + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (key, label, _) in enumerate(MODES):
        current = load_rgb(finals[key][frame], roi)
        difference = np.clip(np.abs(current - reference) * 4.0, 0.0, 255.0).astype(np.uint8)
        image = Image.fromarray(difference, mode="RGB")
        image = image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + label_height)
        sheet.paste(image, (x, y))
        draw.text((x + 8, y + thumb_height + 7), f"{label} | abs diff x4", fill="black")
    sheet.save(output)


def main() -> int:
    args = parse_args()
    final_root = args.final_capture_root.resolve()
    mask_root = args.candidate_mask_root.resolve()
    reference_dir = args.reference_dir.resolve()
    output = (args.output or final_root / "Analysis-ARM-Dual-SanMiguel-Thin-ROI").resolve()
    roi = tuple(args.roi)
    if not (0 <= args.frame_start <= args.frame_end < args.expected_frames):
        raise RuntimeError("Invalid frame range")
    if not (args.frame_start <= args.representative_frame <= args.frame_end):
        raise RuntimeError("Representative frame must be inside the ROI frame range")
    if not (0 <= roi[0] < roi[2] <= 1920 and 0 <= roi[1] < roi[3] <= 1017):
        raise RuntimeError(f"Invalid 1920x1017 ROI: {roi}")

    finals = {key: collect(final_root / directory, args.expected_frames) for key, _, directory in MODES}
    masks = {key: collect(mask_root / directory, args.expected_frames) for key, _, directory in MODES}
    references = collect(reference_dir, args.expected_frames)
    selected_frames = range(args.frame_start, args.frame_end + 1)

    reference_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []
    previous: dict[str, np.ndarray] = {}
    roi_pixels = (roi[2] - roi[0]) * (roi[3] - roi[1])
    for frame in selected_frames:
        reference = load_rgb(references[frame], roi)
        for key, label, _ in MODES:
            current = load_rgb(finals[key][frame], roi)
            reference_rows.append({
                "mode": label,
                "frame": frame,
                "rgb_mae_vs_reference": mae(current, reference),
                "psnr_vs_reference": psnr(current, reference),
                "adjacent_frame_rgb_mae": math.nan if key not in previous else mae(current, previous[key]),
            })
            previous[key] = current

        for profile, (base, dilate, filtered, arm) in PROFILES.items():
            raw = load_mask(masks[base][frame], roi)
            raw_count = int(raw.sum(dtype=np.int64))
            row: dict[str, object] = {
                "profile": profile,
                "frame": frame,
                "roi_pixels": roi_pixels,
                "raw_candidates": raw_count,
                "raw_coverage": raw_count / roi_pixels,
            }
            for name, key in (("dilate3x3", dilate), ("filtered", filtered), ("arm_dual", arm)):
                expanded = load_mask(masks[key][frame], roi)
                count = int(expanded.sum(dtype=np.int64))
                row[f"{name}_candidates"] = count
                row[f"{name}_coverage"] = count / roi_pixels
                row[f"{name}_multiplier"] = count / max(raw_count, 1)
            candidate_rows.append(row)

    mode_summaries = []
    for _, label, _ in MODES:
        rows = [row for row in reference_rows if row["mode"] == label]
        temporal = [float(row["adjacent_frame_rgb_mae"]) for row in rows if math.isfinite(float(row["adjacent_frame_rgb_mae"]))]
        mode_summaries.append({
            "mode": label,
            "rgb_mae_vs_reference": mean([float(row["rgb_mae_vs_reference"]) for row in rows]),
            "psnr_vs_reference": mean([float(row["psnr_vs_reference"]) for row in rows]),
            "adjacent_frame_rgb_mae": mean(temporal),
        })

    candidate_summaries = []
    for profile in PROFILES:
        rows = [row for row in candidate_rows if row["profile"] == profile]
        candidate_summaries.append({
            "profile": profile,
            "raw_coverage": mean([float(row["raw_coverage"]) for row in rows]),
            "dilate3x3_coverage": mean([float(row["dilate3x3_coverage"]) for row in rows]),
            "filtered_coverage": mean([float(row["filtered_coverage"]) for row in rows]),
            "arm_dual_coverage": mean([float(row["arm_dual_coverage"]) for row in rows]),
        })

    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "sanmiguel_thin_roi_reference_metrics.csv", reference_rows)
    write_csv(output / "sanmiguel_thin_roi_candidate_metrics.csv", candidate_rows)
    result = {
        "classification": "engineering screen-space ROI; not object tracked",
        "scene": "sanmiguel",
        "profile": "yaw-fast-360",
        "roi": roi,
        "frame_range": [args.frame_start, args.frame_end],
        "mode_summaries": mode_summaries,
        "candidate_summaries": candidate_summaries,
    }
    (output / "sanmiguel_thin_roi_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    make_sheet(finals, references, roi, args.representative_frame,
               output / f"sanmiguel_thin_chairs_roi_frame_{args.representative_frame:05d}.png")
    make_difference_sheet(
        finals, references, roi, args.representative_frame,
        output / f"sanmiguel_thin_chairs_roi_difference_x4_frame_{args.representative_frame:05d}.png",
    )

    summary_by_mode = {row["mode"]: row for row in mode_summaries}
    base_for_mode = {
        label: ("O-ET2X-R-Document" if key.startswith("document") else "ABL-Candidate-Jitter-R")
        for key, label, _ in MODES
    }

    lines = [
        "# San Miguel 얇은 의자 ROI ARM 후보 확장 분석",
        "",
        f"- 화면 ROI: `{roi}`; frame `{args.frame_start}~{args.frame_end}`",
        "- 실제 의자·테이블 다리와 식생 가지가 지속적으로 보이는 구간을 수동 선정",
        "- 360° 회전의 screen-space ROI이며 object tracking/절대 temporal ground truth가 아님",
        "",
        "| Mode | Reference RGB MAE | vs None | Reference PSNR | Adjacent-frame RGB MAE |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in mode_summaries:
        base = summary_by_mode[base_for_mode[str(row["mode"])]]
        change = 100.0 * (
            float(row["rgb_mae_vs_reference"]) - float(base["rgb_mae_vs_reference"])
        ) / float(base["rgb_mae_vs_reference"])
        lines.append(
            f"| {row['mode']} | {row['rgb_mae_vs_reference']:.6f} | {change:+.3f}% | "
            f"{row['psnr_vs_reference']:.6f} | {row['adjacent_frame_rgb_mae']:.6f} |"
        )
    lines.extend(["", "| Profile | Raw coverage | 3×3 | Filtered | ARM |", "|---|---:|---:|---:|---:|"])
    for row in candidate_summaries:
        lines.append(
            f"| {row['profile']} | {100.0 * row['raw_coverage']:.3f}% | "
            f"{100.0 * row['dilate3x3_coverage']:.3f}% | "
            f"{100.0 * row['filtered_coverage']:.3f}% | "
            f"{100.0 * row['arm_dual_coverage']:.3f}% |"
        )
    (output / "SMAA-ARM-Dual-SanMiguel-Thin-ROI-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
