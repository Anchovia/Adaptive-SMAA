#!/usr/bin/env python3
"""Analyze the controlled current-edge 3x3 dilation ablation.

The supersample input is a temporal-history-free spatial reference proxy.  The
script therefore keeps spatial fidelity, temporal variation, observed history
contribution, and candidate coverage as separate measurements.  None of them
is presented as an absolute ghosting ground truth.
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


FRAME_PATTERN = re.compile(r"(?:^|_)frame_(\d+)$", re.IGNORECASE)
MODES = (
    (
        "candidate_jitter",
        "ABL-Candidate-Jitter-R",
        "ABL_Candidate_Jitter_R",
    ),
    (
        "candidate_jitter_dilate3x3",
        "ABL-Candidate-Jitter-Dilate3x3-R",
        "ABL_Candidate_Jitter_Dilate3x3_R",
    ),
    (
        "document",
        "O-ET2X-R-Document",
        "O_ET2X_R_Document",
    ),
    (
        "document_dilate3x3",
        "ABL-Document-Dilate3x3-R",
        "ABL_Document_Dilate3x3_R",
    ),
)
PAIRS = (
    (
        "candidate_jitter",
        "candidate_jitter_dilate3x3",
        "Candidate-Jitter",
    ),
    ("document", "document_dilate3x3", "Document"),
)
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
            "reason": "distant high-contrast silhouettes and narrow gaps",
        },
        {
            "name": "tree_ledge_silhouette",
            "box": (520, 60, 1840, 850),
            "frame_start": 23,
            "frame_end": 32,
            "reason": "tree alpha silhouettes and distant ledge edges",
        },
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Candidate-Jitter and the document profile with current-edge "
            "dilation None versus 3x3."
        )
    )
    parser.add_argument("final_capture_root", type=Path)
    parser.add_argument("spatial_capture_root", type=Path)
    parser.add_argument("candidate_mask_root", type=Path)
    parser.add_argument("reference_dir", type=Path)
    parser.add_argument("--scene", choices=tuple(DEFAULT_ROIS), required=True)
    parser.add_argument("--profile", default="yaw-fast-360")
    parser.add_argument("--expected-frames", type=int, default=60)
    parser.add_argument("--reference-offset", type=int, default=60)
    parser.add_argument(
        "--baseline-capture-root",
        type=Path,
        help=(
            "Optional repeat capture made with the same four-way command. "
            "The two unchanged base modes must be byte-identical."
        ),
    )
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
        raise RuntimeError(f"{directory}: missing reference frames {missing[:8]}")
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


def crop(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    return image[y0:y1, x0:x1]


def rgb_mae(first: np.ndarray, second: np.ndarray) -> float:
    return float(
        np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(
            dtype=np.float64
        )
    )


def psnr(test: np.ndarray, reference: np.ndarray) -> float:
    difference = test.astype(np.float64) - reference.astype(np.float64)
    mse = float(np.mean(difference * difference, dtype=np.float64))
    return float("inf") if mse == 0.0 else 10.0 * math.log10(255.0**2 / mse)


def sobel_magnitude(luma_image: np.ndarray) -> np.ndarray:
    padded = np.pad(luma_image.astype(np.float32), 1, mode="edge")
    sx = (
        padded[:-2, 2:]
        + 2.0 * padded[1:-1, 2:]
        + padded[2:, 2:]
        - padded[:-2, :-2]
        - 2.0 * padded[1:-1, :-2]
        - padded[2:, :-2]
    )
    sy = (
        padded[2:, :-2]
        + 2.0 * padded[2:, 1:-1]
        + padded[2:, 2:]
        - padded[:-2, :-2]
        - 2.0 * padded[:-2, 1:-1]
        - padded[:-2, 2:]
    )
    return np.sqrt(sx * sx + sy * sy)


def dilate3x3(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="edge")
    result = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape
    for y in range(3):
        for x in range(3):
            result |= padded[y : y + height, x : x + width]
    return result


def reference_structure(reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    edge = sobel_magnitude(luma(reference))
    threshold = max(float(np.percentile(edge, 75.0)), 8.0)
    return edge, edge >= threshold


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.mean(finite, dtype=np.float64)) if finite else float("nan")


def fmt(value: float, digits: int = 6) -> str:
    return "N/A" if not math.isfinite(value) else f"{value:.{digits}f}"


def relative_change(value: float, baseline: float) -> float:
    if not math.isfinite(value) or not math.isfinite(baseline) or baseline == 0.0:
        return float("nan")
    return 100.0 * (value / baseline - 1.0)


def resized_crop(path: Path, box: tuple[int, int, int, int], width: int) -> Image.Image:
    with Image.open(path) as image:
        roi = image.convert("RGB").crop(box)
        height = max(1, round(roi.height * width / roi.width))
        return roi.resize((width, height), Image.Resampling.NEAREST)


def make_sheet(
    output: Path,
    roi: dict[str, Any],
    frame: int,
    paths: dict[str, list[Path]],
    reference: list[Path],
) -> None:
    sources = [("SS-Reference", reference)] + [
        (label, paths[key]) for key, label, _ in MODES
    ]
    tile_width = 300
    header = 28
    sample = resized_crop(reference[frame], roi["box"], tile_width)
    canvas = Image.new(
        "RGB", (tile_width * len(sources), sample.height + header), "black"
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, frames) in enumerate(sources):
        canvas.paste(
            resized_crop(frames[frame], roi["box"], tile_width),
            (column * tile_width, header),
        )
        draw.text((column * tile_width + 5, 7), f"{label} f{frame:02d}", fill="white")
    canvas.save(output, compress_level=3)


def make_gif(
    output: Path,
    roi: dict[str, Any],
    paths: dict[str, list[Path]],
    reference: list[Path],
) -> None:
    sources = [("SS-Reference", reference)] + [
        (label, paths[key]) for key, label, _ in MODES
    ]
    tile_width = 240
    header = 26
    frames_out: list[Image.Image] = []
    for frame in range(roi["frame_start"], roi["frame_end"] + 1):
        sample = resized_crop(reference[frame], roi["box"], tile_width)
        canvas = Image.new(
            "RGB", (tile_width * len(sources), sample.height + header), "black"
        )
        draw = ImageDraw.Draw(canvas)
        for column, (label, frames) in enumerate(sources):
            canvas.paste(
                resized_crop(frames[frame], roi["box"], tile_width),
                (column * tile_width, header),
            )
            draw.text((column * tile_width + 5, 6), label, fill="white")
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
    if args.expected_frames < 3:
        raise ValueError("--expected-frames must be at least 3")

    final_root = args.final_capture_root.resolve()
    spatial_root = args.spatial_capture_root.resolve()
    mask_root = args.candidate_mask_root.resolve()
    reference_dir = args.reference_dir.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else final_root / "CurrentEdgeDilationQuality"
    )
    output.mkdir(parents=True, exist_ok=True)

    final_paths = {
        key: collect_capture(final_root / directory, args.expected_frames)
        for key, _, directory in MODES
    }
    spatial_paths = {
        key: collect_capture(spatial_root / directory, args.expected_frames)
        for key, _, directory in MODES
    }
    mask_paths = {
        key: collect_capture(mask_root / directory, args.expected_frames)
        for key, _, directory in MODES
    }
    reference_paths = collect_reference(
        reference_dir, args.reference_offset, args.expected_frames
    )

    with Image.open(reference_paths[0]) as image:
        resolution = image.size
    for collection in (final_paths, spatial_paths, mask_paths):
        for frames in collection.values():
            with Image.open(frames[0]) as image:
                if image.size != resolution:
                    raise RuntimeError(
                        f"Resolution mismatch: {frames[0]} is {image.size}, "
                        f"expected {resolution}"
                    )

    baseline_mismatches: dict[str, int] = {}
    if args.baseline_capture_root is not None:
        baseline_root = args.baseline_capture_root.resolve()
        for key in ("candidate_jitter", "document"):
            directory = next(item[2] for item in MODES if item[0] == key)
            baseline = collect_capture(baseline_root / directory, args.expected_frames)
            mismatches = sum(
                sha256(current) != sha256(previous)
                for current, previous in zip(final_paths[key], baseline)
            )
            baseline_mismatches[key] = mismatches
            if mismatches:
                raise RuntimeError(
                    f"Repeat capture for unchanged base mode {key} is not deterministic: "
                    f"{mismatches}/{args.expected_frames} PNG mismatches"
                )

    dilation_validation: dict[str, Any] = {}
    for base_key, dilated_key, label in PAIRS:
        frame_rows = []
        total_mismatch = 0
        for frame in range(args.expected_frames):
            base = load_rgb(mask_paths[base_key][frame]).max(axis=2) > 127
            dilated = load_rgb(mask_paths[dilated_key][frame]).max(axis=2) > 127
            expected = dilate3x3(base)
            mismatch = int(np.count_nonzero(dilated != expected))
            total_mismatch += mismatch
            frame_rows.append(
                {
                    "frame": frame,
                    "base_pixels": int(base.sum(dtype=np.int64)),
                    "dilated_pixels": int(dilated.sum(dtype=np.int64)),
                    "candidate_ratio": float(
                        dilated.sum(dtype=np.int64)
                        / max(base.sum(dtype=np.int64), 1)
                    ),
                    "mismatch_pixels": mismatch,
                }
            )
        dilation_validation[label] = {
            "total_mismatch_pixels": total_mismatch,
            "mean_candidate_ratio": mean(
                [row["candidate_ratio"] for row in frame_rows]
            ),
            "frames": frame_rows,
        }
        if total_mismatch:
            raise RuntimeError(
                f"GPU {label} dilation differs from exact 3x3 max filter: "
                f"{total_mismatch} pixels"
            )

    rows: list[dict[str, Any]] = []
    previous: dict[tuple[str, str], np.ndarray] = {}
    previous2: dict[tuple[str, str], np.ndarray] = {}
    for frame in range(args.expected_frames):
        reference_full = load_rgb(reference_paths[frame])
        finals = {key: load_rgb(final_paths[key][frame]) for key, _, _ in MODES}
        spatials = {
            key: load_rgb(spatial_paths[key][frame]) for key, _, _ in MODES
        }
        masks = {key: load_rgb(mask_paths[key][frame]) for key, _, _ in MODES}
        for roi in DEFAULT_ROIS[args.scene]:
            if not (roi["frame_start"] <= frame <= roi["frame_end"]):
                continue
            reference = crop(reference_full, roi["box"])
            reference_edge, structure = reference_structure(reference)
            row: dict[str, Any] = {
                "frame": frame,
                "profile_frame": args.reference_offset + frame,
                "roi": roi["name"],
            }
            for key, _, _ in MODES:
                final = crop(finals[key], roi["box"])
                spatial = crop(spatials[key], roi["box"])
                mask = crop(masks[key], roi["box"]).max(axis=2) > 127
                final_luma = luma(final)
                final_edge = sobel_magnitude(final_luma)
                delta = np.abs(final.astype(np.int16) - spatial.astype(np.int16))
                history_key = (roi["name"], key)
                row[f"{key}_rgb_mae_vs_reference"] = rgb_mae(final, reference)
                row[f"{key}_psnr_vs_reference"] = psnr(final, reference)
                row[f"{key}_edge_strength_ratio_vs_reference"] = float(
                    final_edge[structure].mean(dtype=np.float64)
                    / max(reference_edge[structure].mean(dtype=np.float64), 1e-12)
                )
                row[f"{key}_history_output_rgb_mae"] = float(
                    delta.mean(dtype=np.float64)
                )
                row[f"{key}_candidate_history_output_rgb_mae"] = float(
                    delta[mask].mean(dtype=np.float64)
                ) if np.any(mask) else float("nan")
                overlap = np.logical_and(mask, structure)
                row[f"{key}_candidate_screen_ratio"] = float(
                    mask.mean(dtype=np.float64)
                )
                row[f"{key}_reference_structure_recall"] = float(
                    overlap.sum(dtype=np.int64)
                    / max(structure.sum(dtype=np.int64), 1)
                )
                row[f"{key}_reference_structure_precision"] = float(
                    overlap.sum(dtype=np.int64) / max(mask.sum(dtype=np.int64), 1)
                )
                if history_key in previous:
                    row[f"{key}_adjacent_luma_mae"] = float(
                        np.abs(final_luma - previous[history_key]).mean(
                            dtype=np.float64
                        )
                    )
                else:
                    row[f"{key}_adjacent_luma_mae"] = float("nan")
                if history_key in previous2:
                    row[f"{key}_second_luma_difference"] = float(
                        np.abs(
                            final_luma
                            - 2.0 * previous[history_key]
                            + previous2[history_key]
                        ).mean(dtype=np.float64)
                    )
                else:
                    row[f"{key}_second_luma_difference"] = float("nan")
                previous2[history_key] = previous.get(history_key, final_luma)
                previous[history_key] = final_luma
            rows.append(row)

    if not rows:
        raise RuntimeError("ROI selection produced no rows")
    metrics_csv = "current_edge_dilation_roi_metrics.csv"
    with (output / metrics_csv).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summaries: dict[str, Any] = {}
    sheets: list[str] = []
    gifs: list[str] = []
    metric_names = (
        "rgb_mae_vs_reference",
        "psnr_vs_reference",
        "edge_strength_ratio_vs_reference",
        "adjacent_luma_mae",
        "second_luma_difference",
        "history_output_rgb_mae",
        "candidate_history_output_rgb_mae",
        "candidate_screen_ratio",
        "reference_structure_recall",
        "reference_structure_precision",
    )
    for roi in DEFAULT_ROIS[args.scene]:
        roi_rows = [row for row in rows if row["roi"] == roi["name"]]
        mode_summaries = {}
        for key, label, _ in MODES:
            mode_summaries[key] = {
                "semantic_id": label,
                **{
                    metric: mean([float(row[f"{key}_{metric}"]) for row in roi_rows])
                    for metric in metric_names
                },
            }
        pair_summaries = {}
        for base_key, dilated_key, label in PAIRS:
            base = mode_summaries[base_key]
            dilated = mode_summaries[dilated_key]
            pair_summaries[label] = {
                "candidate_multiplier": (
                    dilated["candidate_screen_ratio"]
                    / max(base["candidate_screen_ratio"], 1e-12)
                ),
                "structure_recall_change_pp": 100.0
                * (
                    dilated["reference_structure_recall"]
                    - base["reference_structure_recall"]
                ),
                "reference_rgb_mae_change_percent": relative_change(
                    dilated["rgb_mae_vs_reference"],
                    base["rgb_mae_vs_reference"],
                ),
                "second_luma_difference_change_percent": relative_change(
                    dilated["second_luma_difference"],
                    base["second_luma_difference"],
                ),
                "history_output_change_percent": relative_change(
                    dilated["history_output_rgb_mae"],
                    base["history_output_rgb_mae"],
                ),
            }
        summaries[roi["name"]] = {
            "box": list(roi["box"]),
            "frame_start": roi["frame_start"],
            "frame_end": roi["frame_end"],
            "reason": roi["reason"],
            "modes": mode_summaries,
            "dilation_effects": pair_summaries,
        }
        center = (roi["frame_start"] + roi["frame_end"]) // 2
        sheet_name = f"{args.scene}_{roi['name']}_frame_{center:05d}.png"
        gif_name = (
            f"{args.scene}_{roi['name']}_{roi['frame_start']:05d}_"
            f"{roi['frame_end']:05d}.gif"
        )
        make_sheet(output / sheet_name, roi, center, final_paths, reference_paths)
        make_gif(output / gif_name, roi, final_paths, reference_paths)
        sheets.append(sheet_name)
        gifs.append(gif_name)

    result = {
        "scene": args.scene,
        "profile": args.profile,
        "classification": args.classification,
        "final_capture_root": str(final_root),
        "spatial_capture_root": str(spatial_root),
        "candidate_mask_root": str(mask_root),
        "reference_dir": str(reference_dir),
        "baseline_capture_root": (
            str(args.baseline_capture_root.resolve())
            if args.baseline_capture_root is not None
            else None
        ),
        "baseline_hash_mismatches": baseline_mismatches,
        "resolution": list(resolution),
        "capture_frames": args.expected_frames,
        "reference_offset": args.reference_offset,
        "reference_scope": (
            "2x linear resolution, 3x3 subpixel grid, 8xMSAA spatial proxy; "
            "no temporal history and not absolute temporal ground truth"
        ),
        "gpu_dilation_validation": dilation_validation,
        "summaries": summaries,
        "artifacts": {
            "metrics_csv": metrics_csv,
            "sheets": sheets,
            "gifs": gifs,
        },
    }
    summary_json = "current_edge_dilation_quality_summary.json"
    (output / summary_json).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# Current-edge 3×3 dilation 실제 장면 분석",
        "",
        "## 범위",
        "",
        f"- 장면/profile: `{args.scene}` / `{args.profile}`",
        f"- 분류: `{args.classification}`",
        f"- 해상도: {resolution[0]}×{resolution[1]}",
        f"- capture frame: {args.expected_frames}",
        "- 비교: Candidate-Jitter와 document profile 각각 dilation None / 3×3",
        "- 최종 8개 연구 mode는 변경하지 않은 직교 ablation",
        "- supersample reference는 spatial proxy이며 절대 temporal ground truth가 아님",
        "",
        "## 자동 검증",
        "",
    ]
    if baseline_mismatches:
        for key, mismatches in baseline_mismatches.items():
            report.append(
                f"- 독립 반복 `{key}` 출력 SHA-256 mismatch: "
                f"{mismatches}/{args.expected_frames} (PASS)"
            )
    for label, validation in dilation_validation.items():
        report.append(
            f"- `{label}` GPU mask와 정확한 3×3 max-filter mismatch: "
            f"{validation['total_mismatch_pixels']} pixels (PASS); "
            f"전체 화면 후보 배수 {validation['mean_candidate_ratio']:.3f}×"
        )

    for roi in DEFAULT_ROIS[args.scene]:
        summary = summaries[roi["name"]]
        report.extend(
            [
                "",
                f"## `{roi['name']}`",
                "",
                f"- box: `{roi['box']}`",
                f"- frame: {roi['frame_start']}~{roi['frame_end']}",
                f"- 구조: {roi['reason']}",
                "",
                "| Mode | Reference RGB MAE ↓ | PSNR ↑ | Edge/reference | 2차 luma diff | History output MAE | 후보 비율 | 구조 recall |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for key, label, _ in MODES:
            values = summary["modes"][key]
            report.append(
                f"| `{label}` | {fmt(values['rgb_mae_vs_reference'])} | "
                f"{fmt(values['psnr_vs_reference'], 3)} | "
                f"{fmt(values['edge_strength_ratio_vs_reference'], 4)} | "
                f"{fmt(values['second_luma_difference'])} | "
                f"{fmt(values['history_output_rgb_mae'])} | "
                f"{values['candidate_screen_ratio']:.3%} | "
                f"{values['reference_structure_recall']:.3%} |"
            )
        report.extend(
            [
                "",
                "| Pair | 후보 배수 | 구조 recall 변화 | Reference MAE 변화 | 2차 luma 변화 | History 영향 변화 |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for label, values in summary["dilation_effects"].items():
            report.append(
                f"| {label} | {values['candidate_multiplier']:.3f}× | "
                f"{values['structure_recall_change_pp']:+.3f}%p | "
                f"{values['reference_rgb_mae_change_percent']:+.3f}% | "
                f"{values['second_luma_difference_change_percent']:+.3f}% | "
                f"{values['history_output_change_percent']:+.3f}% |"
            )

    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- 낮은 reference MAE는 spatial fidelity이며 temporal 품질 전체를 뜻하지 않는다.",
            "- 낮은 시간 변화량은 올바른 안정화뿐 아니라 blur/ghosting으로도 생길 수 있다.",
            "- 높은 edge 비율은 선명함뿐 아니라 aliasing일 수 있다.",
            "- history output MAE는 final과 current spatial의 관측 차이이며 정확한 sample 수가 아니다.",
            "- 3×3이 후보를 크게 늘리므로 품질 이득과 candidate/resolve GPU 비용을 함께 판단해야 한다.",
        ]
    )
    report_path = output / "Current-Edge-Dilation-Quality-Report-ko.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(report_path)
    print(output / summary_json)
    print(output / metrics_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
