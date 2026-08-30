#!/usr/bin/env python3
"""Compare San Miguel 1X/T2X controls and ET2X candidate expansions.

The supersample sequence is a same-pose spatial reference proxy.  It is not a
temporal ground truth, so the report keeps spatial-reference and temporal-change
metrics separate.
"""

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
    ("O-1X", "O_1X"),
    ("O-T2X-R", "O_T2X_R"),
    ("O-ET2X-R-None", "O_ET2X_R_Document"),
    ("O-ET2X-R-3x3", "ABL_Document_Dilate3x3_R"),
    ("O-ET2X-R-ARM", "ABL_Document_ArmDual_R"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("control_capture_root", type=Path)
    parser.add_argument("reference_capture_root", type=Path)
    parser.add_argument("--expected-frames", type=int, default=60)
    parser.add_argument("--roi", type=int, nargs=4, default=(0, 500, 1050, 1017))
    parser.add_argument("--representative-frame", type=int, default=3)
    parser.add_argument("--candidate-mask-root", type=Path)
    parser.add_argument("--arm-threshold", type=float, default=0.25)
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


def load_rgb(path: Path, roi: tuple[int, int, int, int] | None = None) -> np.ndarray:
    with Image.open(path) as image:
        image = image.convert("RGB")
        if roi is not None:
            image = image.crop(roi)
        return np.asarray(image, dtype=np.float32)


def load_mask(path: Path, roi: tuple[int, int, int, int] | None = None) -> np.ndarray:
    with Image.open(path) as image:
        image = image.convert("RGB")
        if roi is not None:
            image = image.crop(roi)
        return np.asarray(image, dtype=np.uint8).max(axis=2) > 127


def mae(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.mean(np.abs(first - second)))


def psnr(first: np.ndarray, second: np.ndarray) -> float:
    mse = float(np.mean((first - second) ** 2))
    return math.inf if mse == 0.0 else 10.0 * math.log10((255.0 * 255.0) / mse)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_sheet(
    modes: dict[str, list[Path]], references: list[Path], roi: tuple[int, int, int, int],
    frame: int, output: Path, difference: bool,
) -> None:
    reference = load_rgb(references[frame], roi)
    entries: list[tuple[str, Image.Image]] = []
    if not difference:
        entries.append(("SS spatial reference", Image.fromarray(reference.astype(np.uint8))))
    for label, paths in modes.items():
        current = load_rgb(paths[frame], roi)
        if difference:
            current = np.clip(np.abs(current - reference) * 4.0, 0.0, 255.0)
            label = f"{label} | abs diff x4"
        entries.append((label, Image.fromarray(current.astype(np.uint8))))

    columns = 3
    tile_width = 500
    roi_width = roi[2] - roi[0]
    roi_height = roi[3] - roi[1]
    tile_height = max(1, round(roi_height * tile_width / roi_width))
    label_height = 30
    rows = math.ceil(len(entries) / columns)
    sheet = Image.new("RGB", (columns * tile_width, rows * (tile_height + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(entries):
        image = image.resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        x = (index % columns) * tile_width
        y = (index // columns) * (tile_height + label_height)
        sheet.paste(image, (x, y))
        draw.text((x + 8, y + tile_height + 7), label, fill="black")
    sheet.save(output)


def main() -> int:
    args = parse_args()
    control_root = args.control_capture_root.resolve()
    reference_root = args.reference_capture_root.resolve()
    reference_dir = reference_root / "SS_Reference"
    if not reference_dir.is_dir() and reference_root.name == "SS_Reference":
        reference_dir = reference_root
    output = (args.output or control_root / "Analysis-Expansion-Controls").resolve()
    roi = tuple(args.roi)
    if args.expected_frames < 1:
        raise RuntimeError("--expected-frames must be positive")
    if not 0.0 <= args.arm_threshold <= 1.0:
        raise RuntimeError("--arm-threshold must be in [0,1]")
    if not (0 <= args.representative_frame < args.expected_frames):
        raise RuntimeError("Representative frame is outside the capture range")

    modes = {label: collect(control_root / directory, args.expected_frames) for label, directory in MODES}
    references = collect(reference_dir, args.expected_frames)
    with Image.open(references[0]) as image:
        width, height = image.size
    if not (0 <= roi[0] < roi[2] <= width and 0 <= roi[1] < roi[3] <= height):
        raise RuntimeError(f"Invalid ROI {roi} for {width}x{height}")

    rows: list[dict[str, object]] = []
    previous: dict[tuple[str, str], np.ndarray] = {}
    previous_reference: dict[str, np.ndarray] = {}
    regions = (("full", None), ("thin_roi", roi))
    for frame in range(args.expected_frames):
        for region_name, region in regions:
            reference = load_rgb(references[frame], region)
            for label, paths in modes.items():
                current = load_rgb(paths[frame], region)
                key = (label, region_name)
                adjacent = math.nan
                delta_residual = math.nan
                if key in previous:
                    adjacent = mae(current, previous[key])
                    reference_delta = reference - previous_reference[region_name]
                    current_delta = current - previous[key]
                    delta_residual = float(np.mean(np.abs(current_delta - reference_delta)))
                rows.append({
                    "mode": label,
                    "region": region_name,
                    "frame": frame,
                    "rgb_mae_vs_spatial_reference": mae(current, reference),
                    "psnr_vs_spatial_reference": psnr(current, reference),
                    "adjacent_frame_rgb_mae": adjacent,
                    "temporal_delta_residual_vs_reference": delta_residual,
                })
                previous[key] = current
            previous_reference[region_name] = reference

    summaries: list[dict[str, object]] = []
    for region_name, _ in regions:
        for label, _ in MODES:
            selected = [row for row in rows if row["mode"] == label and row["region"] == region_name]
            temporal = [float(row["adjacent_frame_rgb_mae"]) for row in selected if math.isfinite(float(row["adjacent_frame_rgb_mae"]))]
            residual = [float(row["temporal_delta_residual_vs_reference"]) for row in selected if math.isfinite(float(row["temporal_delta_residual_vs_reference"]))]
            summaries.append({
                "mode": label,
                "region": region_name,
                "rgb_mae_vs_spatial_reference": float(np.mean([float(row["rgb_mae_vs_spatial_reference"]) for row in selected])),
                "psnr_vs_spatial_reference": float(np.mean([float(row["psnr_vs_spatial_reference"]) for row in selected])),
                "adjacent_frame_rgb_mae": float(np.mean(temporal)) if temporal else math.nan,
                "temporal_delta_residual_vs_reference": float(np.mean(residual)) if residual else math.nan,
            })

    mask_summaries: list[dict[str, object]] = []
    raw_preservation_violations = 0
    if args.candidate_mask_root is not None:
        mask_root = args.candidate_mask_root.resolve()
        mask_modes = {
            "None": collect(mask_root / "O_ET2X_R_Document", args.expected_frames),
            "3x3": collect(mask_root / "ABL_Document_Dilate3x3_R", args.expected_frames),
            "ARM": collect(mask_root / "ABL_Document_ArmDual_R", args.expected_frames),
        }
        coverage: dict[tuple[str, str], list[float]] = {
            (mode, region_name): []
            for mode in mask_modes for region_name, _ in regions
        }
        for frame in range(args.expected_frames):
            full_masks = {
                mode: load_mask(paths[frame]) for mode, paths in mask_modes.items()
            }
            raw = full_masks["None"]
            raw_preservation_violations += int((raw & ~full_masks["3x3"]).sum(dtype=np.int64))
            raw_preservation_violations += int((raw & ~full_masks["ARM"]).sum(dtype=np.int64))
            for mode, mask in full_masks.items():
                coverage[(mode, "full")].append(float(mask.mean()))
                x0, y0, x1, y1 = roi
                coverage[(mode, "thin_roi")].append(float(mask[y0:y1, x0:x1].mean()))
        for mode in mask_modes:
            for region_name, _ in regions:
                mask_summaries.append({
                    "mode": mode,
                    "region": region_name,
                    "candidate_coverage": float(np.mean(coverage[(mode, region_name)])),
                })

    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "sanmiguel_expansion_control_per_frame.csv", rows)
    write_csv(output / "sanmiguel_expansion_control_summary.csv", summaries)
    if mask_summaries:
        write_csv(output / "sanmiguel_expansion_control_candidate_coverage.csv", mask_summaries)
    metadata = {
        "classification": "same-pose supersample spatial-reference comparison; not temporal ground truth",
        "control_capture_root": str(control_root),
        "reference_capture_root": str(reference_root),
        "frames": args.expected_frames,
        "resolution": [width, height],
        "thin_roi": roi,
        "modes": [label for label, _ in MODES],
        "candidate_mask_root": str(args.candidate_mask_root.resolve()) if args.candidate_mask_root else None,
        "arm_threshold": args.arm_threshold if args.candidate_mask_root else None,
        "raw_preservation_violations": raw_preservation_violations if args.candidate_mask_root else None,
    }
    (output / "sanmiguel_expansion_control_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    make_sheet(modes, references, roi, args.representative_frame,
               output / f"sanmiguel_expansion_controls_frame_{args.representative_frame:05d}.png", False)
    make_sheet(modes, references, roi, args.representative_frame,
               output / f"sanmiguel_expansion_controls_difference_x4_frame_{args.representative_frame:05d}.png", True)

    lookup = {(str(row["region"]), str(row["mode"])): row for row in summaries}
    lines = [
        "# San Miguel candidate expansion control 분석",
        "",
        "- 비교: `SS spatial reference | O-1X | O-T2X-R | O-ET2X-R None | 3x3 | ARM`",
        "- supersample 자료는 동일 pose의 spatial-reference proxy이며 temporal ground truth가 아니다.",
        "- `temporal delta residual`은 test와 reference의 인접 프레임 변화량 차이를 나타내는 보조 지표다.",
    ]
    if args.candidate_mask_root is not None:
        lines.append(f"- ARM final/mask reconstruction threshold: `{args.arm_threshold:.2f}`")
    lines.append("")
    for region_name, _ in regions:
        lines.extend([
            f"## {region_name}",
            "",
            "| Mode | RGB MAE vs reference | PSNR | Adjacent-frame MAE | Temporal delta residual |",
            "|---|---:|---:|---:|---:|",
        ])
        for label, _ in MODES:
            row = lookup[(region_name, label)]
            lines.append(
                f"| {label} | {row['rgb_mae_vs_spatial_reference']:.6f} | "
                f"{row['psnr_vs_spatial_reference']:.6f} | {row['adjacent_frame_rgb_mae']:.6f} | "
                f"{row['temporal_delta_residual_vs_reference']:.6f} |"
            )
        lines.append("")
    if mask_summaries:
        lines.extend([
            "## Candidate coverage",
            "",
            f"- ARM reconstruction threshold: `{args.arm_threshold:.2f}`",
            f"- raw candidate preservation violations: `{raw_preservation_violations}` pixels",
            "",
            "| Expansion | Full coverage | Thin ROI coverage |",
            "|---|---:|---:|",
        ])
        mask_lookup = {
            (str(row["mode"]), str(row["region"])): float(row["candidate_coverage"])
            for row in mask_summaries
        }
        for mode in ("None", "3x3", "ARM"):
            lines.append(
                f"| {mode} | {100.0 * mask_lookup[(mode, 'full')]:.3f}% | "
                f"{100.0 * mask_lookup[(mode, 'thin_roi')]:.3f}% |"
            )
        lines.append("")
    (output / "SMAA-SanMiguel-Expansion-Controls-ko.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
