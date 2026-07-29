import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_original_four_quality import (
    ADAPTIVE_MODES,
    MODES as ORIGINAL_MODES,
    aggregate,
    edge_strength,
    load_rgb,
    percent_delta,
)


MODES = ORIGINAL_MODES + ADAPTIVE_MODES
PAIRS = (
    ("original_edge_no_reprojection", "o_t2x", "o_et2x"),
    ("original_edge_reprojected", "o_t2x_r", "o_et2x_r"),
    ("adaptive_edge_no_reprojection", "a_t2x", "a_et2x"),
    ("adaptive_edge_reprojected", "a_t2x_r", "a_et2x_r"),
    ("original_standard_reprojection", "o_t2x", "o_t2x_r"),
    ("original_edge_reprojection", "o_et2x", "o_et2x_r"),
    ("adaptive_standard_reprojection", "a_t2x", "a_t2x_r"),
    ("adaptive_edge_reprojection", "a_et2x", "a_et2x_r"),
)
EDGE_VISUAL_PAIRS = (
    ("original_edge_no_reprojection", "o_t2x", "o_et2x"),
    ("original_edge_reprojected", "o_t2x_r", "o_et2x_r"),
    ("adaptive_edge_no_reprojection", "a_t2x", "a_et2x"),
    ("adaptive_edge_reprojected", "a_t2x_r", "a_et2x_r"),
)

ROI_FRACTIONS = {
    "thin-lines": {
        "thin_line_field": (0.36, 0.30, 0.61, 0.71),
    },
    "object-motion": {
        "occluder_path": (0.30, 0.45, 0.70, 0.73),
        "rotor": (0.30, 0.24, 0.46, 0.48),
    },
    "combined": {
        "thin_line_field": (0.36, 0.30, 0.61, 0.71),
        "occluder_path": (0.30, 0.45, 0.70, 0.73),
        "rotor": (0.30, 0.24, 0.46, 0.48),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze dedicated SMAA temporal stress-scene ROIs."
    )
    parser.add_argument("capture_root", type=Path)
    parser.add_argument(
        "--scenario",
        required=True,
        choices=("thin-lines", "object-motion", "combined"),
    )
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def validate_inputs(
    capture_root: Path, expected_frames: int
) -> tuple[dict[str, list[Path]], tuple[int, int], dict[str, Any]]:
    paths: dict[str, list[Path]] = {}
    validation: dict[str, Any] = {"modes": {}}
    resolution: tuple[int, int] | None = None
    for key, semantic_id, directory in MODES:
        frames = sorted((capture_root / directory).glob("*.png"))
        if len(frames) != expected_frames:
            raise RuntimeError(
                f"{semantic_id}: expected {expected_frames} PNGs, found {len(frames)}"
            )
        indices = [int(path.stem.rsplit("_", 1)[1]) for path in frames]
        if indices != list(range(expected_frames)):
            raise RuntimeError(f"{semantic_id}: missing or reordered frame indices")
        with Image.open(frames[0]) as image:
            current_resolution = image.size
        if resolution is None:
            resolution = current_resolution
        elif current_resolution != resolution:
            raise RuntimeError(
                f"{semantic_id}: resolution {current_resolution} differs from {resolution}"
            )
        paths[key] = frames
        validation["modes"][semantic_id] = {
            "directory": directory,
            "frame_count": len(frames),
            "first_index": indices[0],
            "last_index": indices[-1],
        }
    assert resolution is not None
    validation["resolution"] = list(resolution)
    validation["frame_count_per_mode"] = expected_frames
    return paths, resolution, validation


def roi_boxes(
    scenario: str, resolution: tuple[int, int]
) -> dict[str, tuple[int, int, int, int]]:
    width, height = resolution
    return {
        name: (
            int(round(left * width)),
            int(round(top * height)),
            int(round(right * width)),
            int(round(bottom * height)),
        )
        for name, (left, top, right, bottom) in ROI_FRACTIONS[scenario].items()
    }


def crop_half(rgb: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    left, top, right, bottom = box
    return rgb[top:bottom:2, left:right:2]


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


def longest_true_run(mask: np.ndarray) -> tuple[int, int] | None:
    best: tuple[int, int] | None = None
    start: int | None = None
    for index, value in enumerate(mask.tolist() + [False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            if best is None or index - start > best[1] - best[0]:
                best = (start, index)
            start = None
    return best


def object_screen_velocity(scenario: str, time_seconds: float) -> float:
    object_velocity = (
        2.75
        * (2.0 * math.pi / 3.0)
        * math.cos(time_seconds * (2.0 * math.pi / 3.0))
    )
    if scenario == "combined":
        camera_velocity = (
            0.42
            * (2.0 * math.pi / 4.0)
            * math.cos(time_seconds * (2.0 * math.pi / 4.0))
        )
        return object_velocity - camera_velocity
    return object_velocity


def ghost_trail_proxy(
    rgb: np.ndarray,
    box: tuple[int, int, int, int],
    velocity: float,
) -> tuple[float, float]:
    left, top, right, bottom = box
    crop = luma(rgb[top:bottom, left:right])
    band_top = int(crop.shape[0] * 0.32)
    band_bottom = int(crop.shape[0] * 0.68)
    profile = np.median(crop[band_top:band_bottom], axis=0)
    baseline = float(np.percentile(profile, 70.0))
    darkness = np.maximum(baseline - profile, 0.0)
    core = longest_true_run(darkness > 24.0)
    if core is None or core[1] - core[0] < 24:
        return float("nan"), float("nan")

    search = 36
    if velocity >= 0.0:
        trail = darkness[max(0, core[0] - search) : core[0]]
        trail = trail[::-1]
    else:
        trail = darkness[core[1] : min(darkness.shape[0], core[1] + search)]
    if trail.size == 0:
        return float("nan"), float("nan")

    active = trail > 2.0
    width = 0
    for value in active:
        if not value:
            break
        width += 1
    return float(trail.mean(dtype=np.float64)), float(width)


def annotate_rois(
    output: Path,
    image_path: Path,
    boxes: dict[str, tuple[int, int, int, int]],
) -> str:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    colors = ("#ff4040", "#40ff80", "#40a0ff")
    for color, (name, box) in zip(colors, boxes.items()):
        draw.rectangle(box, outline=color, width=3)
        draw.text((box[0] + 8, box[1] + 8), name, fill=color)
    name = "stress_roi_map.png"
    image.save(output / name, compress_level=3)
    return name


def visual_pair_definitions(
    scenario: str,
) -> tuple[tuple[str, str, str], ...]:
    if scenario == "object-motion":
        # With the camera fixed, corresponding reprojection Off/On modes should
        # be identical. Keep the visual set focused on the two independent
        # Standard-vs-Edge comparisons instead of duplicating the same frames.
        return (EDGE_VISUAL_PAIRS[0], EDGE_VISUAL_PAIRS[2])
    return EDGE_VISUAL_PAIRS


def visual_regions(scenario: str) -> tuple[str, ...]:
    if scenario == "thin-lines":
        return ("thin_line_field",)
    if scenario == "object-motion":
        return ("occluder_path", "rotor")
    return ("thin_line_field", "occluder_path")


def visual_center_frame(scenario: str) -> int:
    # At frame 120 the 4 s camera sine path crosses the center at maximum
    # velocity. At frame 90 the 3 s object path does the same.
    return 120 if scenario == "thin-lines" else 90


def make_pair_gif(
    output: Path,
    paths: dict[str, list[Path]],
    pair_name: str,
    first_key: str,
    second_key: str,
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
) -> str:
    frame_count = min(24, expected_frames)
    start = min(
        max(center_frame - frame_count // 2, 0),
        max(0, expected_frames - frame_count),
    )
    end = start + frame_count
    width = box[2] - box[0]
    height = box[3] - box[1]
    labels = {key: semantic_id for key, semantic_id, _ in MODES}
    gif_frames: list[Image.Image] = []
    for frame in range(start, end):
        canvas = Image.new("RGB", (width * 2, height + 35), "black")
        draw = ImageDraw.Draw(canvas)
        for column, key in enumerate((first_key, second_key)):
            with Image.open(paths[key][frame]) as source:
                cropped = source.convert("RGB").crop(box)
            x = column * width
            canvas.paste(cropped, (x, 35))
            draw.text(
                (x + 8, 10),
                f"Frame {frame:05d} - {labels[key]}",
                fill="white",
            )
        gif_frames.append(
            canvas.quantize(colors=192, method=Image.Quantize.MEDIANCUT)
        )

    name = (
        f"stress_{roi_name}_{pair_name}_{start:05d}_{end - 1:05d}.gif"
    )
    gif_frames[0].save(
        output / name,
        save_all=True,
        append_images=gif_frames[1:],
        duration=60,
        loop=0,
        optimize=False,
        disposal=2,
    )
    return name


def make_pair_sequence_sheet(
    output: Path,
    paths: dict[str, list[Path]],
    pair_name: str,
    first_key: str,
    second_key: str,
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
) -> str:
    offsets = (-12, -8, -4, 0, 4, 8)
    sampled = [
        min(max(center_frame + offset, 0), expected_frames - 1)
        for offset in offsets
    ]
    width = box[2] - box[0]
    height = box[3] - box[1]
    row_height = height + 35
    labels = {key: semantic_id for key, semantic_id, _ in MODES}
    canvas = Image.new("RGB", (width * 3, row_height * len(sampled)), "black")
    draw = ImageDraw.Draw(canvas)

    for row, frame in enumerate(sampled):
        first = load_rgb(paths[first_key][frame])
        second = load_rgb(paths[second_key][frame])
        difference = np.clip(
            np.abs(first.astype(np.int16) - second.astype(np.int16)) * 4,
            0,
            255,
        ).astype(np.uint8)
        images = (
            Image.fromarray(first).crop(box),
            Image.fromarray(second).crop(box),
            Image.fromarray(difference).crop(box),
        )
        row_labels = (
            labels[first_key],
            labels[second_key],
            "absolute difference x4",
        )
        y = row * row_height
        for column, (image, label) in enumerate(zip(images, row_labels)):
            x = column * width
            canvas.paste(image, (x, y + 35))
            draw.text(
                (x + 8, y + 10),
                f"Frame {frame:05d} - {label}",
                fill="white",
            )

    name = (
        f"stress_sheet_{roi_name}_{pair_name}_"
        f"{sampled[0]:05d}_{sampled[-1]:05d}.png"
    )
    canvas.save(output / name, compress_level=3)
    return name


def make_visual_artifacts(
    output: Path,
    paths: dict[str, list[Path]],
    boxes: dict[str, tuple[int, int, int, int]],
    scenario: str,
    expected_frames: int,
) -> tuple[list[str], list[str]]:
    center_frame = visual_center_frame(scenario)
    gifs: list[str] = []
    sheets: list[str] = []
    for roi_name in visual_regions(scenario):
        for pair_name, first_key, second_key in visual_pair_definitions(scenario):
            gifs.append(
                make_pair_gif(
                    output,
                    paths,
                    pair_name,
                    first_key,
                    second_key,
                    roi_name,
                    boxes[roi_name],
                    center_frame,
                    expected_frames,
                )
            )
            sheets.append(
                make_pair_sequence_sheet(
                    output,
                    paths,
                    pair_name,
                    first_key,
                    second_key,
                    roi_name,
                    boxes[roi_name],
                    center_frame,
                    expected_frames,
                )
            )
    return gifs, sheets


def main() -> None:
    args = parse_args()
    capture_root = args.capture_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else capture_root / "StressAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)
    paths, resolution, validation = validate_inputs(
        capture_root, args.expected_frames
    )
    boxes = roi_boxes(args.scenario, resolution)

    rows: list[dict[str, Any]] = []
    previous_rgb: dict[str, dict[str, np.ndarray]] | None = None
    previous_luma: dict[str, dict[str, np.ndarray]] | None = None
    previous2_luma: dict[str, dict[str, np.ndarray]] | None = None

    for frame in range(args.expected_frames):
        full_rgb = {key: load_rgb(paths[key][frame]) for key, _, _ in MODES}
        current_rgb = {
            roi_name: {
                key: crop_half(full_rgb[key], box) for key, _, _ in MODES
            }
            for roi_name, box in boxes.items()
        }
        current_luma = {
            roi_name: {
                key: luma(current_rgb[roi_name][key]) for key, _, _ in MODES
            }
            for roi_name in boxes
        }
        row: dict[str, Any] = {"frame": frame}

        for roi_name in boxes:
            for key, _, _ in MODES:
                prefix = f"{roi_name}_{key}"
                row[f"{prefix}_edge_strength"] = edge_strength(
                    current_luma[roi_name][key]
                )
                if previous_rgb is None:
                    row[f"{prefix}_temporal_mae"] = ""
                    row[f"{prefix}_second_difference_mae"] = ""
                else:
                    row[f"{prefix}_temporal_mae"] = rgb_mae(
                        current_rgb[roi_name][key],
                        previous_rgb[roi_name][key],
                    )
                    if previous2_luma is None or previous_luma is None:
                        row[f"{prefix}_second_difference_mae"] = ""
                    else:
                        row[f"{prefix}_second_difference_mae"] = float(
                            np.abs(
                                current_luma[roi_name][key]
                                - 2.0 * previous_luma[roi_name][key]
                                + previous2_luma[roi_name][key]
                            ).mean(dtype=np.float64)
                        )

            for pair_name, first_key, second_key in PAIRS:
                row[f"{roi_name}_{pair_name}_same_frame_mae"] = rgb_mae(
                    current_rgb[roi_name][first_key],
                    current_rgb[roi_name][second_key],
                )

        if "occluder_path" in boxes:
            velocity = object_screen_velocity(args.scenario, frame / 60.0)
            for key, _, _ in MODES:
                trail_mean, trail_width = ghost_trail_proxy(
                    full_rgb[key], boxes["occluder_path"], velocity
                )
                row[f"occluder_path_{key}_ghost_trail_mean_darkness"] = (
                    "" if math.isnan(trail_mean) else trail_mean
                )
                row[f"occluder_path_{key}_ghost_trail_width_px"] = (
                    "" if math.isnan(trail_width) else trail_width
                )

        rows.append(row)
        previous_rgb = current_rgb
        previous2_luma = previous_luma
        previous_luma = current_luma
        if frame % 25 == 0 or frame == args.expected_frames - 1:
            print(f"Processed {frame + 1}/{args.expected_frames}", flush=True)

    csv_name = "stress_roi_metrics.csv"
    with (output / csv_name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        key: aggregate(rows, key)
        for key in rows[0]
        if key != "frame"
    }
    roi_map = annotate_rois(output, paths["o_t2x"][0], boxes)
    comparison_gifs, sequence_sheets = make_visual_artifacts(
        output,
        paths,
        boxes,
        args.scenario,
        args.expected_frames,
    )

    result = {
        "scenario": args.scenario,
        "validation": validation,
        "conditions": {
            "resolution": list(resolution),
            "frame_rate": 60,
            "warmup_frames": args.warmup_frames,
            "capture_frames_per_mode": args.expected_frames,
            "smaa_preset": "Ultra",
            "motion_reprojection": "camera motion only; object motion vectors unavailable",
        },
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "artifacts": {
            "metrics_csv": csv_name,
            "roi_map": roi_map,
            "comparison_gifs": comparison_gifs,
            "sequence_sheets": sequence_sheets,
        },
    }
    json_name = "stress_roi_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    labels = {key: semantic_id for key, semantic_id, _ in MODES}
    report = [
        "# SMAA temporal stress ROI 분석",
        "",
        "## 범위",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 해상도: {resolution[0]}×{resolution[1]}",
        f"- mode별 warm-up {args.warmup_frames}프레임, 저장 {args.expected_frames}프레임",
        "- DirectX 11, Release x64, SMAA Ultra, fixed 60 Hz",
        "- 전체 8개 semantic case 비교",
        "- reprojection On도 camera motion만 처리하며 object motion vector는 없음",
        "",
        "## ROI",
        "",
    ]
    for name, box in boxes.items():
        report.append(f"- `{name}`: `{box}`")

    for roi_name in boxes:
        report.extend(
            [
                "",
                f"## `{roi_name}` mode별 지표",
                "",
                "| Mode | 인접 frame RGB MAE | 2차 시간 차분 Luma MAE | Edge strength |",
                "|---|---:|---:|---:|",
            ]
        )
        for key, semantic_id, _ in MODES:
            prefix = f"{roi_name}_{key}"
            report.append(
                f"| `{semantic_id}` | "
                f"{summary[f'{prefix}_temporal_mae']['mean']:.6f} | "
                f"{summary[f'{prefix}_second_difference_mae']['mean']:.6f} | "
                f"{summary[f'{prefix}_edge_strength']['mean']:.6f} |"
            )

        report.extend(
            [
                "",
                f"## `{roi_name}` 대응 비교",
                "",
                "| 비교 | Same-frame MAE | Temporal MAE 변화 | 2차 차분 변화 | Edge strength 변화 |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for pair_name, first_key, second_key in PAIRS:
            first_prefix = f"{roi_name}_{first_key}"
            second_prefix = f"{roi_name}_{second_key}"
            report.append(
                f"| `{labels[second_key]}` vs `{labels[first_key]}` | "
                f"{summary[f'{roi_name}_{pair_name}_same_frame_mae']['mean']:.6f} | "
                f"{percent_delta(summary[f'{second_prefix}_temporal_mae']['mean'], summary[f'{first_prefix}_temporal_mae']['mean']):+.3f}% | "
                f"{percent_delta(summary[f'{second_prefix}_second_difference_mae']['mean'], summary[f'{first_prefix}_second_difference_mae']['mean']):+.3f}% | "
                f"{percent_delta(summary[f'{second_prefix}_edge_strength']['mean'], summary[f'{first_prefix}_edge_strength']['mean']):+.3f}% |"
            )

    if "occluder_path" in boxes:
        report.extend(
            [
                "",
                "## Object-motion trailing-halo 대용 지표",
                "",
                "| Mode | Trail mean darkness | Trail width | 유효 frame |",
                "|---|---:|---:|---:|",
            ]
        )
        for key, semantic_id, _ in MODES:
            darkness_key = f"occluder_path_{key}_ghost_trail_mean_darkness"
            width_key = f"occluder_path_{key}_ghost_trail_width_px"
            valid_frames = sum(row[darkness_key] != "" for row in rows)
            report.append(
                f"| `{semantic_id}` | {summary[darkness_key]['mean']:.6f} | "
                f"{summary[width_key]['mean']:.3f} px | {valid_frames} |"
            )
        report.extend(
            [
                "",
                "이 값은 현재 occluder의 어두운 core 뒤 36픽셀에서 배경 대비 잔여 darkness와",
                "연속 halo 폭을 재는 휴리스틱이다. supersample ground truth나 optical-flow",
                "보정 지표가 아니므로 절대 ghosting 점수로 사용하지 않고 대응 case 비교에만 사용한다.",
            ]
        )

    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- 인접 frame과 2차 차분은 실제 camera/object motion을 포함한다.",
            "- 값이 작아도 blur 때문에 작을 수 있으므로 단독 품질 순위가 아니다.",
            "- edge strength는 선명도와 aliasing을 함께 포함한다.",
            "- ROI map, 기존 8-case GIF/sequence sheet와 함께 판단한다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 ROI 지표: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
            f"- ROI 위치: `{roi_map}`",
        ]
    )
    report.extend(f"- 비교 GIF: `{name}`" for name in comparison_gifs)
    report.extend(f"- 연속 frame sheet: `{name}`" for name in sequence_sheets)
    report.append("")
    report_name = "SMAA-Temporal-Stress-ROI-Analysis-ko.md"
    (output / report_name).write_text("\n".join(report), encoding="utf-8")
    print(f"Stress analysis complete: {output}", flush=True)


if __name__ == "__main__":
    main()
