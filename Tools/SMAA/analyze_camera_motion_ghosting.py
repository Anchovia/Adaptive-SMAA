#!/usr/bin/env python3
"""Analyze full-length deterministic camera-motion CGVQM captures.

This combines the official CGVQM result/error-map statistics with simple
same-frame and temporal pixel controls. None of the reported values is treated
as an absolute ghosting ground truth.
"""

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


FRAME_PATTERN = re.compile(r"(?:^|_)frame_(\d+)$", re.IGNORECASE)
ORIGINAL_MODES = (
    ("O-1X", "O_1X"),
    ("O-T2X", "O_T2X"),
    ("O-T2X-R", "O_T2X_R"),
    ("O-ET2X", "O_ET2X"),
    ("O-ET2X-R", "O_ET2X_R"),
)
ADAPTIVE_MODES = (
    ("A-1X", "A_1X"),
    ("A-T2X", "A_T2X"),
    ("A-T2X-R", "A_T2X_R"),
    ("A-ET2X", "A_ET2X"),
    ("A-ET2X-R", "A_ET2X_R"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze deterministic camera-motion CGVQM "
            "results and recovery behavior."
        )
    )
    parser.add_argument("cgvqm_root", type=Path)
    parser.add_argument("--pre-frames", type=int, default=60)
    parser.add_argument("--motion-frames", type=int, default=60)
    parser.add_argument("--post-frames", type=int, default=60)
    parser.add_argument("--stable-frames", type=int, default=5)
    parser.add_argument("--threshold-sigma", type=float, default=3.0)
    parser.add_argument(
        "--include-adaptive",
        action="store_true",
        help="Analyze A-1X plus the four Adaptive temporal cases as well.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


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


def frame_index(path: Path) -> int:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise RuntimeError(f"Invalid camera-motion PNG filename: {path.name}")
    return int(match.group(1))


def collect_frames(directory: Path, expected: int) -> list[Path]:
    frames = sorted(directory.glob("*.png"), key=frame_index)
    indices = [frame_index(path) for path in frames]
    if indices != list(range(expected)):
        raise RuntimeError(
            f"{directory}: expected contiguous frame indices 0..{expected - 1}, "
            f"found {len(indices)} frames"
        )
    return frames


def mean_or_nan(values: list[float]) -> float:
    return float(np.mean(values, dtype=np.float64)) if values else float("nan")


def region_summary(rows: list[dict[str, float]], start: int, end: int) -> dict[str, float]:
    selected = rows[start:end]
    return {
        "frame_count": len(selected),
        "cgvqm_error_mean": mean_or_nan([row["mean"] for row in selected]),
        "cgvqm_error_peak_frame_mean": max(row["mean"] for row in selected),
        "mean_of_frame_p95": mean_or_nan([row["p95"] for row in selected]),
        "rgb_mae_vs_spatial_1x": mean_or_nan(
            [row["rgb_mae_vs_spatial_1x"] for row in selected]
        ),
        "adjacent_rgb_mae": mean_or_nan(
            [row["adjacent_rgb_mae"] for row in selected if math.isfinite(row["adjacent_rgb_mae"])]
        ),
        "second_luma_difference": mean_or_nan(
            [
                row["second_luma_difference"]
                for row in selected
                if math.isfinite(row["second_luma_difference"])
            ]
        ),
    }


def recovery_frames(
    values: list[float], threshold: float, stable_frames: int
) -> int | None:
    for offset in range(0, len(values) - stable_frames + 1):
        if all(value <= threshold for value in values[offset : offset + stable_frames]):
            return offset
    return None


def fmt(value: float | int | None, digits: int = 6) -> str:
    if value is None:
        return "미회복"
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        return "N/A"
    return f"{value:.{digits}f}"


def resized_rgb(path: Path, width: int) -> Image.Image:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        height = max(1, round(rgb.height * width / rgb.width))
        return rgb.resize((width, height), Image.Resampling.LANCZOS)


def make_comparison_sheet(
    output: Path,
    selected_frames: list[int],
    sources: list[tuple[str, list[Path]]],
) -> None:
    tile_width = 300
    label_height = 24
    sample = resized_rgb(sources[0][1][selected_frames[0]], tile_width)
    tile_height = sample.height
    canvas = Image.new(
        "RGB",
        (tile_width * len(sources), label_height + len(selected_frames) * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, _) in enumerate(sources):
        draw.text((column * tile_width + 6, 6), label, fill="black")
    y = label_height
    for frame in selected_frames:
        for column, (_, paths) in enumerate(sources):
            tile = resized_rgb(paths[frame], tile_width)
            canvas.paste(tile, (column * tile_width, y))
        draw.text((6, y + tile_height + 5), f"frame {frame:05d}", fill="black")
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def make_motion_gif(
    output: Path,
    motion_start: int,
    motion_end: int,
    sources: list[tuple[str, list[Path]]],
) -> None:
    tile_width = 220
    label_height = 22
    sample = resized_rgb(sources[0][1][motion_start], tile_width)
    tile_height = sample.height
    gif_frames: list[Image.Image] = []
    for frame in range(motion_start, motion_end):
        canvas = Image.new(
            "RGB", (tile_width * len(sources), label_height + tile_height), "white"
        )
        draw = ImageDraw.Draw(canvas)
        for column, (label, paths) in enumerate(sources):
            draw.text(
                (column * tile_width + 5, 5),
                f"{label}  f{frame:03d}",
                fill="black",
            )
            canvas.paste(
                resized_rgb(paths[frame], tile_width),
                (column * tile_width, label_height),
            )
        gif_frames.append(canvas.quantize(colors=256))
    gif_frames[0].save(
        output,
        save_all=True,
        append_images=gif_frames[1:],
        duration=17,
        loop=0,
        disposal=2,
        optimize=False,
    )


def main() -> int:
    args = parse_args()
    if min(args.pre_frames, args.motion_frames, args.post_frames) <= 0:
        raise ValueError("All timeline frame counts must be positive")
    if args.stable_frames <= 0 or args.threshold_sigma < 0.0:
        raise ValueError("Invalid recovery threshold settings")

    root = args.cgvqm_root.resolve()
    output = (args.output or (root / "CameraMotionAnalysis")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    expected = args.pre_frames + args.motion_frames + args.post_frames
    modes = ORIGINAL_MODES + (ADAPTIVE_MODES if args.include_adaptive else ())
    motion_start = args.pre_frames
    post_start = args.pre_frames + args.motion_frames

    results: dict[str, dict[str, Any]] = {}
    frame_rows: dict[str, list[dict[str, float]]] = {}
    reference_hash: str | None = None
    provenance: dict[str, Any] | None = None

    for semantic_id, directory_name in modes:
        mode_root = root / directory_name
        result_path = mode_root / "CGVQM-Results.json"
        if not result_path.is_file():
            raise FileNotFoundError(f"Missing CGVQM result: {result_path}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        expected_classification = "formal" if args.include_adaptive else "engineering"
        if result["classification"] != expected_classification:
            raise RuntimeError(
                f"{semantic_id}: expected {expected_classification} classification"
            )
        if result["test_sequence"]["frame_count"] != expected:
            raise RuntimeError(f"{semantic_id}: unexpected test frame count")
        current_reference_hash = result["reference_sequence"]["pixel_sha256"]
        if reference_hash is None:
            reference_hash = current_reference_hash
            provenance = result["provenance"]
        elif current_reference_hash != reference_hash:
            raise RuntimeError(f"{semantic_id}: reference sequence hash differs")
        round_trip = result["test_round_trip"]
        reference_round_trip = result["reference_round_trip"]
        if (
            round_trip["mismatched_values"] != 0
            or reference_round_trip["mismatched_values"] != 0
        ):
            raise RuntimeError(f"{semantic_id}: lossless round-trip validation failed")

        model = result["results"]["CGVQM-2"]
        csv_path = Path(model["per_frame_csv"])
        rows: list[dict[str, float]] = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for ordinal, row in enumerate(csv.DictReader(handle)):
                if int(row["frame_index"]) != ordinal:
                    raise RuntimeError(f"{semantic_id}: non-contiguous per-frame CSV")
                rows.append(
                    {
                        "frame_index": float(ordinal),
                        "mean": float(row["mean"]),
                        "p95": float(row["p95"]),
                        "p99": float(row["p99"]),
                        "maximum": float(row["maximum"]),
                        "rgb_mae_vs_spatial_1x": float("nan"),
                        "adjacent_rgb_mae": float("nan"),
                        "second_luma_difference": float("nan"),
                    }
                )
        if len(rows) != expected:
            raise RuntimeError(f"{semantic_id}: unexpected per-frame CSV length")
        results[semantic_id] = {"json": result, "model": model}
        frame_rows[semantic_id] = rows

    base_frames_by_spatial: dict[str, list[Path]] = {}
    for base_id, prefix in (("O-1X", "O"), ("A-1X", "A")):
        if base_id in results:
            base_directory = Path(
                results[base_id]["json"]["test_sequence"]["directory"]
            )
            base_frames_by_spatial[prefix] = collect_frames(base_directory, expected)
    mode_frames: dict[str, list[Path]] = {}
    for semantic_id, _ in modes:
        directory = Path(results[semantic_id]["json"]["test_sequence"]["directory"])
        frames = collect_frames(directory, expected)
        mode_frames[semantic_id] = frames
        previous_luma: np.ndarray | None = None
        previous_previous_luma: np.ndarray | None = None
        previous_rgb: np.ndarray | None = None
        spatial_prefix = semantic_id[0]
        base_frames = base_frames_by_spatial[spatial_prefix]
        base_id = f"{spatial_prefix}-1X"
        for index, (path, base_path) in enumerate(zip(frames, base_frames, strict=True)):
            current = load_rgb(path)
            base = current if semantic_id == base_id else load_rgb(base_path)
            row = frame_rows[semantic_id][index]
            row["rgb_mae_vs_spatial_1x"] = float(
                np.abs(current.astype(np.int16) - base.astype(np.int16)).mean(
                    dtype=np.float64
                )
            )
            if previous_rgb is not None:
                row["adjacent_rgb_mae"] = float(
                    np.abs(
                        current.astype(np.int16) - previous_rgb.astype(np.int16)
                    ).mean(dtype=np.float64)
                )
            current_luma = luma(current)
            if previous_luma is not None and previous_previous_luma is not None:
                row["second_luma_difference"] = float(
                    np.abs(
                        current_luma - 2.0 * previous_luma + previous_previous_luma
                    ).mean(dtype=np.float64)
                )
            previous_rgb = current
            previous_previous_luma = previous_luma
            previous_luma = current_luma

    summaries: dict[str, Any] = {}
    for semantic_id, _ in modes:
        rows = frame_rows[semantic_id]
        base_id = f"{semantic_id[0]}-1X"
        base_pre = [row["mean"] for row in frame_rows[base_id][:motion_start]]
        base_limit = float(
            np.mean(base_pre) + args.threshold_sigma * np.std(base_pre)
        )
        pre_values = [row["mean"] for row in rows[:motion_start]]
        mode_limit = float(
            np.mean(pre_values) + args.threshold_sigma * np.std(pre_values)
        )
        threshold = max(base_limit, mode_limit)
        post_values = [row["mean"] for row in rows[post_start:expected]]
        summaries[semantic_id] = {
            "cgvqm_2_score": float(
                results[semantic_id]["model"]["score_higher_is_better"]
            ),
            "cgvqm_error_map": results[semantic_id]["model"]["error_map"],
            "pre_still": region_summary(rows, 0, motion_start),
            "motion": region_summary(rows, motion_start, post_start),
            "post_still": region_summary(rows, post_start, expected),
            "recovery_threshold": threshold,
            "recovery_threshold_definition": (
                f"max(mode pre mean + {args.threshold_sigma:g} sigma, "
                f"{base_id} pre mean + {args.threshold_sigma:g} sigma)"
            ),
            "recovery_frames_5_consecutive": recovery_frames(
                post_values, threshold, args.stable_frames
            ),
        }

    detailed_csv = output / "camera_motion_per_frame.csv"
    with detailed_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = (
            "mode",
            "frame_index",
            "phase",
            "cgvqm_error_mean",
            "cgvqm_error_p95",
            "cgvqm_error_p99",
            "cgvqm_error_maximum",
            "rgb_mae_vs_spatial_1x",
            "adjacent_rgb_mae",
            "second_luma_difference",
        )
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for semantic_id, _ in modes:
            for index, row in enumerate(frame_rows[semantic_id]):
                phase = "pre-still" if index < motion_start else (
                    "motion" if index < post_start else "post-still"
                )
                writer.writerow(
                    {
                        "mode": semantic_id,
                        "frame_index": index,
                        "phase": phase,
                        "cgvqm_error_mean": row["mean"],
                        "cgvqm_error_p95": row["p95"],
                        "cgvqm_error_p99": row["p99"],
                        "cgvqm_error_maximum": row["maximum"],
                        "rgb_mae_vs_spatial_1x": row["rgb_mae_vs_spatial_1x"],
                        "adjacent_rgb_mae": row["adjacent_rgb_mae"],
                        "second_luma_difference": row["second_luma_difference"],
                    }
                )

    summary_csv = output / "camera_motion_summary.csv"
    with summary_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = (
            "mode",
            "cgvqm_2_score",
            "error_map_mean",
            "motion_error_mean",
            "motion_rgb_mae_vs_spatial_1x",
            "motion_second_luma_difference",
            "post_peak_error",
            "recovery_threshold",
            "recovery_frames",
        )
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for semantic_id, _ in modes:
            summary = summaries[semantic_id]
            writer.writerow(
                {
                    "mode": semantic_id,
                    "cgvqm_2_score": summary["cgvqm_2_score"],
                    "error_map_mean": summary["cgvqm_error_map"]["mean"],
                    "motion_error_mean": summary["motion"]["cgvqm_error_mean"],
                    "motion_rgb_mae_vs_spatial_1x": summary["motion"]["rgb_mae_vs_spatial_1x"],
                    "motion_second_luma_difference": summary["motion"]["second_luma_difference"],
                    "post_peak_error": summary["post_still"]["cgvqm_error_peak_frame_mean"],
                    "recovery_threshold": summary["recovery_threshold"],
                    "recovery_frames": summary["recovery_frames_5_consecutive"],
                }
            )

    payload = {
        "classification": (
            "formal full-length final eight-case plus O/A 1X controls evaluation"
            if args.include_adaptive
            else "engineering full-length Original five-way evaluation"
        ),
        "interpretation_limit": (
            "CGVQM, RGB differences, and temporal differences are complementary "
            "signals, not absolute ghosting ground truth."
        ),
        "source_root": str(root),
        "provenance": provenance,
        "timeline": {
            "pre_still": [0, motion_start - 1],
            "motion": [motion_start, post_start - 1],
            "post_still": [post_start, expected - 1],
        },
        "reference_pixel_sha256": reference_hash,
        "summaries": summaries,
    }
    json_path = output / "camera_motion_analysis.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    reference_directory = Path(
        results["O-1X"]["json"]["reference_sequence"]["directory"]
    )
    reference_frames = collect_frames(reference_directory, expected)
    visual_sources = [("SS-Reference", reference_frames)] + [
        (semantic_id, mode_frames[semantic_id]) for semantic_id, _ in modes
    ]
    o_t2x_motion = frame_rows["O-T2X"][motion_start:post_start]
    o_et2x_r_motion = frame_rows["O-ET2X-R"][motion_start:post_start]
    selected_frames = sorted(
        {
            motion_start - 1,
            motion_start,
            motion_start
            + int(np.argmax([row["mean"] for row in o_t2x_motion])),
            motion_start
            + int(np.argmax([row["mean"] for row in o_et2x_r_motion])),
            post_start - 1,
            post_start,
            min(expected - 1, post_start + 2),
        }
    )
    sheet_path = output / "camera_motion_representative_sheet.png"
    gif_path = output / "camera_motion_rotation_comparison.gif"
    make_comparison_sheet(sheet_path, selected_frames, visual_sources)
    make_motion_gif(gif_path, motion_start, post_start, visual_sources)

    report_path = output / (
        "SMAA-Camera-Motion-Eight-Case-Analysis-ko.md"
        if args.include_adaptive
        else "SMAA-Camera-Motion-Original-Five-Analysis-ko.md"
    )
    lines = [
        (
            "# SMAA 급격한 카메라 회전 최종 8-case + O/A-1X 분석"
            if args.include_adaptive
            else "# SMAA 급격한 카메라 회전 Original 5-way 분석"
        ),
        "",
        "## 범위",
        "",
        f"- 장면: `{provenance.get('scene') if provenance else 'unknown'}`",
        f"- 카메라 profile: `{provenance.get('camera_profile') if provenance else 'unknown'}`",
        f"- timeline: pre-still 0~{motion_start - 1}, motion {motion_start}~{post_start - 1}, post-still {post_start}~{expected - 1}",
        (
            "- 분류: 전체 길이 최종 8-case + O/A-1X 품질 측정(formal)"
            if args.include_adaptive
            else "- 분류: 전체 길이 Original 5-way 평가 파이프라인 검증(engineering)"
        ),
        "- Reference: temporal history가 없는 supersample spatial-reference proxy",
        "",
        "## 결과 요약",
        "",
        "| Mode | CGVQM-2 ↑ | 전체 error mean ↓ | 회전 error mean ↓ | 회전 대응 1X MAE ↓ | 회전 2차 luma diff ↓ | post peak ↓ | recovery frame ↓ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for semantic_id, _ in modes:
        summary = summaries[semantic_id]
        lines.append(
            "| " + " | ".join(
                (
                    f"`{semantic_id}`",
                    fmt(summary["cgvqm_2_score"]),
                    fmt(summary["cgvqm_error_map"]["mean"]),
                    fmt(summary["motion"]["cgvqm_error_mean"]),
                    fmt(summary["motion"]["rgb_mae_vs_spatial_1x"]),
                    fmt(summary["motion"]["second_luma_difference"]),
                    fmt(summary["post_still"]["cgvqm_error_peak_frame_mean"]),
                    fmt(summary["recovery_frames_5_consecutive"]),
                )
            ) + " |"
        )
    lines += [
        "",
        "## Recovery 정의",
        "",
        f"각 mode의 pre-still CGVQM error mean + {args.threshold_sigma:g}σ와 대응 공간 control(O-1X/A-1X)의 pre-still mean + {args.threshold_sigma:g}σ 중 큰 값을 threshold로 고정했다.",
        f"post-still 시작 뒤 error가 threshold 이하로 {args.stable_frames}프레임 연속 유지되는 최초 offset을 recovery frame으로 기록했다.",
        "이 threshold는 post-still 결과를 보지 않고 pre-still control만으로 계산한다.",
        "",
        "## 해석 제한",
        "",
        "- CGVQM 점수가 높아도 temporal supersampling 유지 여부를 단독으로 증명하지 않는다.",
        "- 대응 공간 control(O-1X/A-1X)과의 same-frame MAE가 작으면 현재 형상에는 가깝지만 temporal 효과를 잃었을 수 있다.",
        "- 2차 시간 차분이 작아도 올바른 안정화가 아니라 blur/ghost smoothing일 수 있다.",
        (
            "- 이 결과는 최종 8-case와 O/A-1X control을 같은 profile에서 비교한다. 다른 camera profile과 thin-geometry ablation은 별도다."
            if args.include_adaptive
            else "- 이 결과는 Original 5-way 평가 경로 검증이며 최종 8-case 결론이 아니다."
        ),
        "",
        "## 대표 비교 자료",
        "",
        f"- 대표 프레임 시트: `{sheet_path.name}`",
        f"- 회전 구간 {len(visual_sources)}-way GIF: `{gif_path.name}`",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"REPORT={report_path}")
    print(f"SUMMARY_CSV={summary_csv}")
    print(f"PER_FRAME_CSV={detailed_csv}")
    print(f"JSON={json_path}")
    print(f"SHEET={sheet_path}")
    print(f"GIF={gif_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
