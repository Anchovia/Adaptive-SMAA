#!/usr/bin/env python3
"""Analyze an ARM reconstruction-threshold sweep against a spatial reference."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image


FRAME_PATTERN = re.compile(r"(?:^|_)frame_(\d+)$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sweep_manifest", type=Path)
    parser.add_argument("reference_capture_root", type=Path)
    parser.add_argument("--control-capture-root", type=Path)
    parser.add_argument("--roi", type=int, nargs=4, default=(0, 500, 1050, 1017))
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


def load_rgb(path: Path, roi: tuple[int, int, int, int] | None) -> np.ndarray:
    with Image.open(path) as image:
        image = image.convert("RGB")
        if roi is not None:
            image = image.crop(roi)
        return np.asarray(image, dtype=np.float32)


def load_mask(path: Path, roi: tuple[int, int, int, int] | None) -> np.ndarray:
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


def main() -> int:
    args = parse_args()
    manifest_path = args.sweep_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    expected = int(manifest["capture_frames"])
    entries = sorted(manifest["thresholds"], key=lambda item: float(item["threshold"]))
    thresholds = [float(item["threshold"]) for item in entries]
    if len(thresholds) != len(set(thresholds)):
        raise RuntimeError("Sweep manifest contains duplicate thresholds")
    reference_root = args.reference_capture_root.resolve()
    reference_dir = reference_root / "SS_Reference"
    if not reference_dir.is_dir() and reference_root.name == "SS_Reference":
        reference_dir = reference_root
    references = collect(reference_dir, expected)
    output = (args.output or manifest_path.parent / "Analysis").resolve()
    roi = tuple(args.roi)

    sequences: dict[float, tuple[list[Path], list[Path]]] = {}
    for entry in entries:
        threshold = float(entry["threshold"])
        final_root = Path(entry["final_capture_root"])
        mask_root = Path(entry["candidate_mask_root"])
        sequences[threshold] = (
            collect(final_root / "O_ET2X_R", expected),
            collect(mask_root / "O_ET2X_R", expected),
        )

    with Image.open(references[0]) as image:
        width, height = image.size
    if not (0 <= roi[0] < roi[2] <= width and 0 <= roi[1] < roi[3] <= height):
        raise RuntimeError(f"Invalid ROI {roi} for {width}x{height}")

    rows: list[dict[str, object]] = []
    regions = (("full", None), ("thin_roi", roi))
    monotonic_violations = 0
    monotonic_pixels = 0
    previous_threshold_masks: list[np.ndarray] | None = None
    for threshold in thresholds:
        finals, masks = sequences[threshold]
        previous_current: dict[str, np.ndarray] = {}
        previous_reference: dict[str, np.ndarray] = {}
        current_threshold_masks: list[np.ndarray] = []
        for frame in range(expected):
            reference_full = load_rgb(references[frame], None)
            current_full = load_rgb(finals[frame], None)
            mask_full = load_mask(masks[frame], None)
            current_threshold_masks.append(mask_full)
            if previous_threshold_masks is not None:
                violation = mask_full & ~previous_threshold_masks[frame]
                monotonic_violations += int(violation.sum(dtype=np.int64))
                monotonic_pixels += violation.size
            for region_name, region in regions:
                if region is None:
                    reference = reference_full
                    current = current_full
                    mask = mask_full
                else:
                    x0, y0, x1, y1 = region
                    reference = reference_full[y0:y1, x0:x1]
                    current = current_full[y0:y1, x0:x1]
                    mask = mask_full[y0:y1, x0:x1]
                adjacent = math.nan
                delta_residual = math.nan
                if region_name in previous_current:
                    adjacent = mae(current, previous_current[region_name])
                    delta_residual = mae(
                        current - previous_current[region_name],
                        reference - previous_reference[region_name],
                    )
                rows.append({
                    "threshold": threshold,
                    "region": region_name,
                    "frame": frame,
                    "candidate_pixels": int(mask.sum(dtype=np.int64)),
                    "candidate_coverage": float(mask.mean()),
                    "rgb_mae_vs_spatial_reference": mae(current, reference),
                    "psnr_vs_spatial_reference": psnr(current, reference),
                    "adjacent_frame_rgb_mae": adjacent,
                    "temporal_delta_residual_vs_reference": delta_residual,
                })
                previous_current[region_name] = current
                previous_reference[region_name] = reference
        previous_threshold_masks = current_threshold_masks

    summaries: list[dict[str, object]] = []
    for threshold in thresholds:
        for region_name, _ in regions:
            selected = [
                row for row in rows
                if float(row["threshold"]) == threshold and row["region"] == region_name
            ]
            adjacent = [float(row["adjacent_frame_rgb_mae"]) for row in selected if math.isfinite(float(row["adjacent_frame_rgb_mae"]))]
            residual = [float(row["temporal_delta_residual_vs_reference"]) for row in selected if math.isfinite(float(row["temporal_delta_residual_vs_reference"]))]
            summaries.append({
                "threshold": threshold,
                "region": region_name,
                "candidate_coverage": float(np.mean([float(row["candidate_coverage"]) for row in selected])),
                "rgb_mae_vs_spatial_reference": float(np.mean([float(row["rgb_mae_vs_spatial_reference"]) for row in selected])),
                "psnr_vs_spatial_reference": float(np.mean([float(row["psnr_vs_spatial_reference"]) for row in selected])),
                "adjacent_frame_rgb_mae": float(np.mean(adjacent)) if adjacent else math.nan,
                "temporal_delta_residual_vs_reference": float(np.mean(residual)) if residual else math.nan,
            })

    controls: dict[str, dict[str, float]] = {}
    if args.control_capture_root is not None:
        control_root = args.control_capture_root.resolve()
        control_modes = {
            "O-1X": "O_1X",
            "O-T2X-R": "O_T2X_R",
            "O-ET2X-R-None": "O_ET2X_R_Document",
            "O-ET2X-R-3x3": "ABL_Document_Dilate3x3_R",
        }
        for label, directory in control_modes.items():
            frames = collect(control_root / directory, expected)
            values_by_region: dict[str, list[float]] = {name: [] for name, _ in regions}
            for frame in range(expected):
                reference_full = load_rgb(references[frame], None)
                current_full = load_rgb(frames[frame], None)
                values_by_region["full"].append(mae(current_full, reference_full))
                x0, y0, x1, y1 = roi
                values_by_region["thin_roi"].append(
                    mae(current_full[y0:y1, x0:x1], reference_full[y0:y1, x0:x1])
                )
            controls[label] = {
                region_name: float(np.mean(values))
                for region_name, values in values_by_region.items()
            }

    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "arm_threshold_sweep_per_frame.csv", rows)
    write_csv(output / "arm_threshold_sweep_summary.csv", summaries)
    result = {
        "classification": "ARM threshold ablation against a same-pose supersample spatial-reference proxy",
        "manifest": str(manifest_path),
        "reference_root": str(reference_root),
        "frames": expected,
        "resolution": [width, height],
        "thin_roi": roi,
        "thresholds": thresholds,
        "candidate_mask_monotonic_violations": monotonic_violations,
        "candidate_mask_monotonic_tested_pixels": monotonic_pixels,
        "controls_rgb_mae": controls,
    }
    (output / "arm_threshold_sweep_validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# San Miguel ARM reconstruction threshold sweep",
        "",
        f"- threshold: `{thresholds[0]:.2f}~{thresholds[-1]:.2f}`; {len(thresholds)}개 설정",
        f"- candidate-mask monotonic violation: `{monotonic_violations}` pixels",
        "- supersample sequence는 spatial-reference proxy이며 temporal ground truth가 아니다.",
        "- threshold `0.00`은 reconstructed mask의 0까지 포함해 사실상 full-screen diagnostic이므로 실용 후보로 해석하지 않는다.",
        "",
    ]
    for region_name, _ in regions:
        lines.extend([
            f"## {region_name}",
            "",
            "| Threshold | Candidate coverage | RGB MAE | PSNR | Adjacent MAE | Temporal delta residual |",
            "|---:|---:|---:|---:|---:|---:|",
        ])
        for row in summaries:
            if row["region"] != region_name:
                continue
            lines.append(
                f"| {row['threshold']:.2f} | {100.0 * row['candidate_coverage']:.3f}% | "
                f"{row['rgb_mae_vs_spatial_reference']:.6f} | {row['psnr_vs_spatial_reference']:.6f} | "
                f"{row['adjacent_frame_rgb_mae']:.6f} | {row['temporal_delta_residual_vs_reference']:.6f} |"
            )
        if controls:
            lines.extend(["", "Control RGB MAE:"])
            for label, values in controls.items():
                lines.append(f"- `{label}`: `{values[region_name]:.6f}`")
        lines.append("")
    (output / "SMAA-SanMiguel-ARM-Threshold-Sweep-ko.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
