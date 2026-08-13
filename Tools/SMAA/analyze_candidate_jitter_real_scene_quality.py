#!/usr/bin/env python3
"""Analyze Candidate-Jitter quality on aligned real-scene camera motion.

The supersample input is a temporal-history-free spatial reference proxy.  The
script therefore reports fidelity, edge retention, temporal variation, and
candidate-mask coverage as complementary evidence; no single value is treated
as an absolute ghosting or temporal-supersampling score.
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

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None


FRAME_PATTERN = re.compile(r"(?:^|_)frame_(\d+)$", re.IGNORECASE)
MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R"),
    (
        "candidate_jitter_r",
        "ABL-Candidate-Jitter-R",
        "ABL_Candidate_Jitter_R",
    ),
    (
        "candidate_no_jitter_r",
        "ABL-Candidate-NoJitter-R",
        "ABL_Candidate_NoJitter_R",
    ),
    (
        "o_et2x_r_document",
        "O-ET2X-R-Document",
        "O_ET2X_R_Document",
    ),
)
EDGE_SELECTIVE_KEYS = {
    "candidate_jitter_r",
    "candidate_no_jitter_r",
    "o_et2x_r_document",
}
DILATION_KERNELS = (3, 5, 7)
DEFAULT_ROIS = {
    "bistro": (
        {
            "name": "bar_bottles",
            "box": (60, 20, 700, 480),
            "frame_start": 0,
            "frame_end": 7,
            "reason": "thin bottle silhouettes, shelf lines, and wine-rack diagonals",
        },
        {
            "name": "windows_chairs",
            "box": (100, 150, 1700, 1000),
            "frame_start": 26,
            "frame_end": 38,
            "reason": "window muntins, chair/table legs, radiator fins, and lamp arms",
        },
    ),
    "minecraft": (
        {
            "name": "distant_city",
            "box": (250, 270, 1650, 1010),
            "frame_start": 0,
            "frame_end": 7,
            "reason": "distant high-contrast building silhouettes and narrow gaps",
        },
        {
            "name": "tree_ledge_silhouette",
            "box": (520, 60, 1840, 850),
            "frame_start": 23,
            "frame_end": 32,
            "reason": "tree alpha silhouettes and distant ledge edges; limited thin-line content",
        },
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare O-1X, O-T2X-R, Candidate-Jitter/NoJitter, and the "
            "document profile against an aligned supersample spatial reference."
        )
    )
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("reference_dir", type=Path)
    parser.add_argument("--scene", choices=tuple(DEFAULT_ROIS), required=True)
    parser.add_argument("--profile", default="yaw-fast-360")
    parser.add_argument("--expected-frames", type=int, default=60)
    parser.add_argument(
        "--reference-offset",
        type=int,
        default=60,
        help="Reference frame index corresponding to capture frame zero.",
    )
    parser.add_argument("--candidate-mask-root", type=Path)
    parser.add_argument(
        "--formal-o1x-dir",
        type=Path,
        help=(
            "Optional O-1X directory from the aligned formal capture. The "
            "capture subset must be byte-identical to frames selected by "
            "--reference-offset."
        ),
    )
    parser.add_argument(
        "--classification",
        choices=("engineering", "formal"),
        default="engineering",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def require_opencv() -> Any:
    if cv2 is None:
        raise RuntimeError(
            "OpenCV is required. Use Tools/SMAA/requirements-optical-flow.txt."
        )
    return cv2


def frame_index(path: Path) -> int:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise RuntimeError(f"Invalid PNG filename: {path.name}")
    return int(match.group(1))


def collect_capture(directory: Path, expected: int) -> list[Path]:
    frames = sorted(directory.glob("*.png"), key=frame_index)
    indices = [frame_index(path) for path in frames]
    if indices != list(range(expected)):
        raise RuntimeError(
            f"{directory}: expected capture indices 0..{expected - 1}, "
            f"found {len(indices)} frames"
        )
    return frames


def collect_reference(directory: Path, offset: int, expected: int) -> list[Path]:
    indexed = {frame_index(path): path for path in directory.glob("*.png")}
    wanted = list(range(offset, offset + expected))
    missing = [index for index in wanted if index not in indexed]
    if missing:
        raise RuntimeError(
            f"{directory}: missing reference frame indices {missing[:8]}"
        )
    return [indexed[index] for index in wanted]


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def luma(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.float32)
    return (
        values[..., 0] * 0.2126
        + values[..., 1] * 0.7152
        + values[..., 2] * 0.0722
    )


def crop(rgb: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    return rgb[y0:y1, x0:x1]


def rgb_mae(test: np.ndarray, reference: np.ndarray) -> float:
    return float(
        np.abs(test.astype(np.float32) - reference.astype(np.float32)).mean(
            dtype=np.float64
        )
    )


def psnr(test: np.ndarray, reference: np.ndarray) -> float:
    difference = test.astype(np.float64) - reference.astype(np.float64)
    mse = float(np.mean(difference * difference, dtype=np.float64))
    if mse == 0.0:
        return float("inf")
    return 10.0 * math.log10((255.0 * 255.0) / mse)


def sobel_magnitude(luma_image: np.ndarray) -> np.ndarray:
    library = require_opencv()
    sx = library.Sobel(luma_image, library.CV_32F, 1, 0, ksize=3)
    sy = library.Sobel(luma_image, library.CV_32F, 0, 1, ksize=3)
    return np.sqrt(sx * sx + sy * sy)


def structural_metrics(
    test: np.ndarray, reference: np.ndarray
) -> dict[str, float]:
    test_edge = sobel_magnitude(luma(test))
    reference_edge, structure = reference_structure(reference)
    if not np.any(structure):
        return {
            "reference_structure_ratio": 0.0,
            "reference_structure_rgb_mae": float("nan"),
            "edge_strength_ratio_vs_reference": float("nan"),
            "edge_magnitude_mae": float("nan"),
        }
    pixel_error = np.abs(
        test.astype(np.float32) - reference.astype(np.float32)
    ).mean(axis=2)
    return {
        "reference_structure_ratio": float(structure.mean(dtype=np.float64)),
        "reference_structure_rgb_mae": float(
            pixel_error[structure].mean(dtype=np.float64)
        ),
        "edge_strength_ratio_vs_reference": float(
            test_edge[structure].mean(dtype=np.float64)
            / max(reference_edge[structure].mean(dtype=np.float64), 1e-12)
        ),
        "edge_magnitude_mae": float(
            np.abs(test_edge - reference_edge)[structure].mean(dtype=np.float64)
        ),
    }


def reference_structure(reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    reference_edge = sobel_magnitude(luma(reference))
    reference_threshold = max(float(np.percentile(reference_edge, 75.0)), 8.0)
    return reference_edge, reference_edge >= reference_threshold


def mask_coverage_metrics(
    mask: np.ndarray, structure: np.ndarray
) -> dict[str, float]:
    library = require_opencv()

    def measure(selected: np.ndarray, prefix: str) -> dict[str, float]:
        overlap = np.logical_and(selected, structure)
        return {
            f"{prefix}_screen_ratio": float(selected.mean(dtype=np.float64)),
            f"{prefix}_structure_recall": float(
                overlap.sum(dtype=np.int64)
                / max(structure.sum(dtype=np.int64), 1)
            ),
            f"{prefix}_structure_precision": float(
                overlap.sum(dtype=np.int64)
                / max(selected.sum(dtype=np.int64), 1)
            ),
        }

    binary = mask.astype(np.uint8)
    result = measure(binary > 0, "base")
    for size in DILATION_KERNELS:
        kernel = np.ones((size, size), dtype=np.uint8)
        dilated = library.dilate(binary, kernel, iterations=1) > 0
        result.update(measure(dilated, f"dilate_{size}x{size}"))

    height, width = binary.shape
    small_width = max(1, (width + 3) // 4)
    small_height = max(1, (height + 3) // 4)
    downsampled = library.resize(
        binary.astype(np.float32),
        (small_width, small_height),
        interpolation=library.INTER_AREA,
    )
    upsampled = library.resize(
        downsampled,
        (width, height),
        interpolation=library.INTER_LINEAR,
    )
    result.update(measure(upsampled >= 0.25, "filtered_quarter_025"))
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.mean(finite, dtype=np.float64)) if finite else float("nan")


def summarize(rows: list[dict[str, Any]], field: str) -> float:
    return mean([float(row[field]) for row in rows])


def fmt(value: float, digits: int = 6) -> str:
    if not math.isfinite(value):
        return "N/A"
    return f"{value:.{digits}f}"


def resized_crop(
    path: Path, box: tuple[int, int, int, int], width: int
) -> Image.Image:
    with Image.open(path) as image:
        roi = image.convert("RGB").crop(box)
        height = max(1, round(roi.height * width / roi.width))
        return roi.resize((width, height), Image.Resampling.NEAREST)


def make_roi_sheet(
    output: Path,
    roi: dict[str, Any],
    frame: int,
    paths: dict[str, list[Path]],
    reference_paths: list[Path],
) -> None:
    sources = [("SS-Reference", reference_paths)] + [
        (label, paths[key]) for key, label, _ in MODES
    ]
    tile_width = 360
    header = 28
    sample = resized_crop(reference_paths[frame], roi["box"], tile_width)
    tile_height = sample.height
    canvas = Image.new(
        "RGB", (tile_width * 3, (tile_height + header) * 2), "black"
    )
    draw = ImageDraw.Draw(canvas)
    for index, (label, frames) in enumerate(sources):
        x = (index % 3) * tile_width
        y = (index // 3) * (tile_height + header)
        canvas.paste(resized_crop(frames[frame], roi["box"], tile_width), (x, y + header))
        draw.text((x + 5, y + 7), f"{label} f{frame:02d}", fill="white")
    canvas.save(output, compress_level=3)


def make_roi_gif(
    output: Path,
    roi: dict[str, Any],
    paths: dict[str, list[Path]],
    reference_paths: list[Path],
) -> None:
    sources = (
        ("SS-Reference", reference_paths),
        ("O-1X", paths["o_1x"]),
        ("O-T2X-R", paths["o_t2x_r"]),
        ("Candidate-Jitter", paths["candidate_jitter_r"]),
        ("Document", paths["o_et2x_r_document"]),
    )
    tile_width = 260
    header = 26
    frames_out: list[Image.Image] = []
    for frame in range(roi["frame_start"], roi["frame_end"] + 1):
        sample = resized_crop(reference_paths[frame], roi["box"], tile_width)
        canvas = Image.new(
            "RGB", (tile_width * len(sources), sample.height + header), "black"
        )
        draw = ImageDraw.Draw(canvas)
        for column, (label, frames) in enumerate(sources):
            canvas.paste(
                resized_crop(frames[frame], roi["box"], tile_width),
                (column * tile_width, header),
            )
            draw.text(
                (column * tile_width + 5, 6), f"{label} f{frame:02d}", fill="white"
            )
        frames_out.append(canvas.quantize(colors=256))
    frames_out[0].save(
        output,
        save_all=True,
        append_images=frames_out[1:],
        duration=100,
        loop=0,
        disposal=2,
        optimize=False,
    )


def main() -> int:
    args = parse_args()
    require_opencv()
    if args.expected_frames < 2:
        raise ValueError("--expected-frames must be at least 2")
    capture_root = args.capture_root.resolve()
    reference_dir = args.reference_dir.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else capture_root / "CandidateJitterRealSceneQuality"
    )
    output.mkdir(parents=True, exist_ok=True)

    paths = {
        key: collect_capture(capture_root / directory, args.expected_frames)
        for key, _, directory in MODES
    }
    reference_paths = collect_reference(
        reference_dir, args.reference_offset, args.expected_frames
    )
    formal_o1x_paths = None
    if args.formal_o1x_dir is not None:
        formal_o1x_paths = collect_reference(
            args.formal_o1x_dir.resolve(),
            args.reference_offset,
            args.expected_frames,
        )
    mask_paths = None
    if args.candidate_mask_root is not None:
        mask_root = args.candidate_mask_root.resolve()
        mask_paths = {
            key: collect_capture(mask_root / directory, args.expected_frames)
            for key, _, directory in MODES
            if key in EDGE_SELECTIVE_KEYS
        }

    resolution: tuple[int, int] | None = None
    for path in [reference_paths[0]] + [frames[0] for frames in paths.values()]:
        with Image.open(path) as image:
            if resolution is None:
                resolution = image.size
            elif image.size != resolution:
                raise RuntimeError(
                    f"Resolution mismatch: {path} is {image.size}, expected {resolution}"
                )
    assert resolution is not None

    roi_definitions = DEFAULT_ROIS[args.scene]
    for roi in roi_definitions:
        x0, y0, x1, y1 = roi["box"]
        if not (0 <= x0 < x1 <= resolution[0] and 0 <= y0 < y1 <= resolution[1]):
            raise RuntimeError(f"ROI outside image: {roi}")
        if not (
            0 <= roi["frame_start"] <= roi["frame_end"] < args.expected_frames
        ):
            raise RuntimeError(f"ROI frame range outside capture: {roi}")

    # O-1X is the deterministic bridge between the new subset and the existing
    # full formal capture/reference. Record all hashes so the alignment evidence
    # can be independently audited.
    bridge_rows = []
    formal_mismatches = 0
    for frame in range(args.expected_frames):
        capture_hash = sha256(paths["o_1x"][frame])
        row = {
            "capture_frame": frame,
            "reference_frame": args.reference_offset + frame,
            "o_1x_sha256": capture_hash,
            "reference_sha256": sha256(reference_paths[frame]),
        }
        if formal_o1x_paths is not None:
            formal_hash = sha256(formal_o1x_paths[frame])
            match = capture_hash == formal_hash
            formal_mismatches += 0 if match else 1
            row["formal_o_1x_sha256"] = formal_hash
            row["capture_matches_formal_o_1x"] = match
        bridge_rows.append(row)
    if formal_mismatches:
        raise RuntimeError(
            "O-1X subset does not match the aligned formal capture: "
            f"{formal_mismatches}/{args.expected_frames} mismatches"
        )
    bridge_csv = "reference_alignment_hashes.csv"
    with (output / bridge_csv).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(bridge_rows[0]))
        writer.writeheader()
        writer.writerows(bridge_rows)

    rows: list[dict[str, Any]] = []
    previous_luma: dict[tuple[str, str], np.ndarray] = {}
    previous2_luma: dict[tuple[str, str], np.ndarray] = {}
    previous_reference_luma: dict[str, np.ndarray] = {}
    previous2_reference_luma: dict[str, np.ndarray] = {}

    for frame in range(args.expected_frames):
        reference_full = load_rgb(reference_paths[frame])
        current_full = {
            key: load_rgb(paths[key][frame]) for key, _, _ in MODES
        }
        masks_full = (
            {key: load_rgb(mask_paths[key][frame]) for key in mask_paths}
            if mask_paths is not None
            else None
        )
        for roi in roi_definitions:
            if not (roi["frame_start"] <= frame <= roi["frame_end"]):
                continue
            roi_name = roi["name"]
            box = roi["box"]
            reference = crop(reference_full, box)
            reference_luma = luma(reference)
            _, structure = reference_structure(reference)
            row: dict[str, Any] = {
                "frame": frame,
                "profile_frame": args.reference_offset + frame,
                "roi": roi_name,
            }
            if roi_name in previous_reference_luma:
                row["reference_adjacent_luma_mae"] = float(
                    np.abs(reference_luma - previous_reference_luma[roi_name]).mean(
                        dtype=np.float64
                    )
                )
            else:
                row["reference_adjacent_luma_mae"] = float("nan")
            if roi_name in previous2_reference_luma:
                row["reference_second_luma_difference"] = float(
                    np.abs(
                        reference_luma
                        - 2.0 * previous_reference_luma[roi_name]
                        + previous2_reference_luma[roi_name]
                    ).mean(dtype=np.float64)
                )
            else:
                row["reference_second_luma_difference"] = float("nan")

            for key, _, _ in MODES:
                test = crop(current_full[key], box)
                test_luma = luma(test)
                prefix = key
                row[f"{prefix}_rgb_mae_vs_reference"] = rgb_mae(test, reference)
                row[f"{prefix}_psnr_vs_reference"] = psnr(test, reference)
                for name, value in structural_metrics(test, reference).items():
                    row[f"{prefix}_{name}"] = value
                history_key = (roi_name, key)
                if history_key in previous_luma:
                    row[f"{prefix}_adjacent_luma_mae"] = float(
                        np.abs(test_luma - previous_luma[history_key]).mean(
                            dtype=np.float64
                        )
                    )
                else:
                    row[f"{prefix}_adjacent_luma_mae"] = float("nan")
                if history_key in previous2_luma:
                    row[f"{prefix}_second_luma_difference"] = float(
                        np.abs(
                            test_luma
                            - 2.0 * previous_luma[history_key]
                            + previous2_luma[history_key]
                        ).mean(dtype=np.float64)
                    )
                else:
                    row[f"{prefix}_second_luma_difference"] = float("nan")
                previous2_luma[history_key] = previous_luma.get(history_key, test_luma)
                previous_luma[history_key] = test_luma
                if masks_full is not None and key in EDGE_SELECTIVE_KEYS:
                    mask = crop(masks_full[key], box).max(axis=2) > 127
                    for name, value in mask_coverage_metrics(
                        mask, structure
                    ).items():
                        row[f"{prefix}_{name}"] = value

            previous2_reference_luma[roi_name] = previous_reference_luma.get(
                roi_name, reference_luma
            )
            previous_reference_luma[roi_name] = reference_luma
            rows.append(row)

    if not rows:
        raise RuntimeError("ROI selection produced no rows")
    metrics_csv = "candidate_jitter_real_scene_roi_metrics.csv"
    with (output / metrics_csv).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summaries: dict[str, Any] = {}
    sheets: list[str] = []
    gifs: list[str] = []
    for roi in roi_definitions:
        roi_rows = [row for row in rows if row["roi"] == roi["name"]]
        roi_summary: dict[str, Any] = {
            "box": list(roi["box"]),
            "frame_start": roi["frame_start"],
            "frame_end": roi["frame_end"],
            "reason": roi["reason"],
            "reference_adjacent_luma_mae": summarize(
                roi_rows, "reference_adjacent_luma_mae"
            ),
            "reference_second_luma_difference": summarize(
                roi_rows, "reference_second_luma_difference"
            ),
            "modes": {},
        }
        for key, label, _ in MODES:
            mode_summary = {
                "semantic_id": label,
                "rgb_mae_vs_reference": summarize(
                    roi_rows, f"{key}_rgb_mae_vs_reference"
                ),
                "psnr_vs_reference": summarize(
                    roi_rows, f"{key}_psnr_vs_reference"
                ),
                "reference_structure_rgb_mae": summarize(
                    roi_rows, f"{key}_reference_structure_rgb_mae"
                ),
                "edge_strength_ratio_vs_reference": summarize(
                    roi_rows, f"{key}_edge_strength_ratio_vs_reference"
                ),
                "edge_magnitude_mae": summarize(
                    roi_rows, f"{key}_edge_magnitude_mae"
                ),
                "adjacent_luma_mae": summarize(
                    roi_rows, f"{key}_adjacent_luma_mae"
                ),
                "second_luma_difference": summarize(
                    roi_rows, f"{key}_second_luma_difference"
                ),
            }
            if mask_paths is not None and key in EDGE_SELECTIVE_KEYS:
                mode_summary["mask_coverage"] = {
                    prefix: {
                        metric: summarize(
                            roi_rows, f"{key}_{prefix}_{metric}"
                        )
                        for metric in (
                            "screen_ratio",
                            "structure_recall",
                            "structure_precision",
                        )
                    }
                    for prefix in (
                        "base",
                        "dilate_3x3",
                        "dilate_5x5",
                        "dilate_7x7",
                        "filtered_quarter_025",
                    )
                }
            roi_summary["modes"][key] = mode_summary
        summaries[roi["name"]] = roi_summary

        center = (roi["frame_start"] + roi["frame_end"]) // 2
        sheet_name = f"{args.scene}_{roi['name']}_frame_{center:05d}.png"
        gif_name = f"{args.scene}_{roi['name']}_{roi['frame_start']:05d}_{roi['frame_end']:05d}.gif"
        make_roi_sheet(output / sheet_name, roi, center, paths, reference_paths)
        make_roi_gif(output / gif_name, roi, paths, reference_paths)
        sheets.append(sheet_name)
        gifs.append(gif_name)

    result = {
        "scene": args.scene,
        "profile": args.profile,
        "classification": args.classification,
        "capture_root": str(capture_root),
        "reference_dir": str(reference_dir),
        "formal_o1x_dir": (
            str(args.formal_o1x_dir.resolve())
            if args.formal_o1x_dir is not None
            else None
        ),
        "formal_o1x_hash_mismatches": (
            formal_mismatches if formal_o1x_paths is not None else None
        ),
        "candidate_mask_root": (
            str(args.candidate_mask_root.resolve())
            if args.candidate_mask_root is not None
            else None
        ),
        "resolution": list(resolution),
        "capture_frames": args.expected_frames,
        "reference_offset": args.reference_offset,
        "reference_scope": (
            "2x linear resolution, 3x3 subpixel grid, 8xMSAA spatial proxy; "
            "no temporal history and not absolute temporal ground truth"
        ),
        "summaries": summaries,
        "artifacts": {
            "metrics_csv": metrics_csv,
            "alignment_hashes_csv": bridge_csv,
            "sheets": sheets,
            "gifs": gifs,
        },
    }
    summary_json = "candidate_jitter_real_scene_quality_summary.json"
    (output / summary_json).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# Candidate-Jitter 실제 장면 ROI 품질 분석",
        "",
        "## 범위",
        "",
        f"- 장면/profile: `{args.scene}` / `{args.profile}`",
        f"- 분류: `{args.classification}`",
        f"- 해상도: {resolution[0]}×{resolution[1]}",
        f"- capture {args.expected_frames} frame과 reference frame "
        f"{args.reference_offset}~{args.reference_offset + args.expected_frames - 1} 대응",
        *(
            [
                "- O-1X subset과 기존 formal O-1X 대응 구간의 SHA-256 mismatch: "
                f"{formal_mismatches}/{args.expected_frames} (PASS)"
            ]
            if formal_o1x_paths is not None
            else []
        ),
        "- reference는 spatial proxy이며 절대 temporal ground truth가 아님",
        "- CGVQM, 전체 화면 temporal-retention, 후보 내부 history 영향 결과와 함께 해석",
    ]
    for roi in roi_definitions:
        summary = summaries[roi["name"]]
        report.extend(
            [
                "",
                f"## `{roi['name']}`",
                "",
                f"- box: `{roi['box']}`",
                f"- capture frame: {roi['frame_start']}~{roi['frame_end']}",
                f"- 선정 이유: {roi['reason']}",
                "",
                "| Mode | Reference RGB MAE ↓ | PSNR ↑ | Reference 구조 MAE ↓ | Edge/reference 비율 | 인접 luma MAE | 2차 luma diff | 후보 비율 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for key, label, _ in MODES:
            values = summary["modes"][key]
            mask_coverage = values.get("mask_coverage")
            candidate_ratio = (
                None
                if mask_coverage is None
                else mask_coverage["base"]["screen_ratio"]
            )
            report.append(
                f"| `{label}` | {fmt(values['rgb_mae_vs_reference'])} | "
                f"{fmt(values['psnr_vs_reference'], 3)} | "
                f"{fmt(values['reference_structure_rgb_mae'])} | "
                f"{fmt(values['edge_strength_ratio_vs_reference'], 4)} | "
                f"{fmt(values['adjacent_luma_mae'])} | "
                f"{fmt(values['second_luma_difference'])} | "
                f"{('N/A' if candidate_ratio is None else f'{candidate_ratio:.3%}')} |"
            )
        if mask_paths is not None:
            report.extend(
                [
                    "",
                    "### Offline 후보 확장 coverage 시뮬레이션",
                    "",
                    "| Mode | 방식 | 화면 비율 | Reference 구조 recall | 구조 precision |",
                    "|---|---|---:|---:|---:|",
                ]
            )
            for key, label, _ in MODES:
                coverage = summary["modes"][key].get("mask_coverage")
                if coverage is None:
                    continue
                for prefix, method in (
                    ("base", "Base"),
                    ("dilate_3x3", "3x3 dilation"),
                    ("dilate_5x5", "5x5 dilation"),
                    ("dilate_7x7", "7x7 dilation"),
                    ("filtered_quarter_025", "1/4 area + bilinear, threshold 0.25"),
                ):
                    values = coverage[prefix]
                    report.append(
                        f"| `{label}` | {method} | "
                        f"{values['screen_ratio']:.3%} | "
                        f"{values['structure_recall']:.3%} | "
                        f"{values['structure_precision']:.3%} |"
                    )

    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- 낮은 reference MAE는 spatial fidelity이며 temporal supersampling 유지 자체를 증명하지 않는다.",
            "- 낮은 시간 변화량은 올바른 안정화뿐 아니라 blur/ghost blending으로도 생길 수 있다.",
            "- 높은 edge/reference 비율은 선명함뿐 아니라 aliasing/oversharpening일 수 있다.",
            "- Minecraft는 실제 고대비 장면이지만 thin-line geometry가 적어 보조 high-contrast 근거로 사용한다.",
            "- Bistro ROI는 실제 asset의 병, 창틀, 의자/테이블 다리와 radiator를 포함한다.",
            "- current-edge dilation 필요성은 ROI에서 Candidate-Jitter의 구조 미복구가 반복 확인될 때만 판단한다.",
            "- Offline dilation/down-up 결과는 mask coverage와 예상 작업량만 보여주며 실제 resolve 품질·GPU 비용 결과가 아니다.",
            "- 1/4 filtered proxy는 area downsample, bilinear upsample, 0.25 threshold라는 명시적 구현 가정을 사용한다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 ROI 지표: `{metrics_csv}`",
            f"- 정렬 hash: `{bridge_csv}`",
            f"- 기계 판독 요약: `{summary_json}`",
        ]
    )
    report.extend(f"- 비교 시트: `{name}`" for name in sheets)
    report.extend(f"- 연속 비교 GIF: `{name}`" for name in gifs)
    report.append("")
    report_name = "SMAA-Candidate-Jitter-Real-Scene-Quality-ko.md"
    (output / report_name).write_text("\n".join(report), encoding="utf-8")
    print(f"Candidate-Jitter real-scene analysis complete: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
