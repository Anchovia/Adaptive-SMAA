from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_original_four_quality import aggregate, edge_strength, load_rgb, percent_delta
from analyze_temporal_stress_quality import (
    MODES as TEMPORAL_MODES,
    ghost_trail_proxy,
    object_screen_velocity,
    rgb_mae,
    roi_boxes,
)


CONTROL_MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("a_1x", "A-1X", "A_1X"),
)
ALL_MODES = CONTROL_MODES + TEMPORAL_MODES

COMPARISONS = (
    ("o_1x_to_o_t2x", "o_1x", "o_t2x"),
    ("o_1x_to_o_t2x_r", "o_1x", "o_t2x_r"),
    ("o_1x_to_o_et2x", "o_1x", "o_et2x"),
    ("o_1x_to_o_et2x_r", "o_1x", "o_et2x_r"),
    ("a_1x_to_a_t2x", "a_1x", "a_t2x"),
    ("a_1x_to_a_t2x_r", "a_1x", "a_t2x_r"),
    ("a_1x_to_a_et2x", "a_1x", "a_et2x"),
    ("a_1x_to_a_et2x_r", "a_1x", "a_et2x_r"),
    ("original_to_adaptive_1x", "o_1x", "a_1x"),
)

VISUAL_GROUPS = (
    ("original_no_reprojection", ("o_1x", "o_t2x", "o_et2x")),
    ("original_reprojected", ("o_1x", "o_t2x_r", "o_et2x_r")),
    ("adaptive_no_reprojection", ("a_1x", "a_t2x", "a_et2x")),
    ("adaptive_reprojected", ("a_1x", "a_t2x_r", "a_et2x_r")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare SMAA O-1X/A-1X controls with the temporal eight-case stress captures."
    )
    parser.add_argument("control_root", type=Path)
    parser.add_argument("temporal_root", type=Path)
    parser.add_argument(
        "--scenario",
        required=True,
        choices=("thin-lines", "object-motion", "combined"),
    )
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def frame_index(path: Path) -> int:
    return int(path.stem.rsplit("_", 1)[1])


def validate_mode_paths(
    root: Path,
    modes: tuple[tuple[str, str, str], ...],
    expected_frames: int,
    expected_resolution: tuple[int, int] | None = None,
) -> tuple[dict[str, list[Path]], tuple[int, int], dict[str, Any]]:
    paths: dict[str, list[Path]] = {}
    validation: dict[str, Any] = {"root": str(root), "modes": {}}
    resolution = expected_resolution
    for key, semantic_id, directory in modes:
        frames = sorted((root / directory).glob("*.png"))
        if len(frames) != expected_frames:
            raise RuntimeError(
                f"{semantic_id}: expected {expected_frames} PNGs, found {len(frames)}"
            )
        indices = [frame_index(path) for path in frames]
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
    return paths, resolution, validation


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


def visual_groups(
    scenario: str,
) -> tuple[tuple[str, tuple[str, str, str]], ...]:
    if scenario == "object-motion":
        return (VISUAL_GROUPS[0], VISUAL_GROUPS[2])
    return VISUAL_GROUPS


def visual_regions(scenario: str) -> tuple[str, ...]:
    if scenario == "thin-lines":
        return ("thin_line_field",)
    if scenario == "object-motion":
        return ("rotor", "occluder_path")
    return ("thin_line_field", "occluder_path")


def visual_center_frame(scenario: str) -> int:
    return 120 if scenario == "thin-lines" else 90


def make_three_mode_gif(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    group_name: str,
    keys: tuple[str, str, str],
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
    frames: list[Image.Image] = []
    for frame in range(start, end):
        canvas = Image.new("RGB", (width * 3, height + 35), "black")
        draw = ImageDraw.Draw(canvas)
        for column, key in enumerate(keys):
            with Image.open(paths[key][frame]) as source:
                cropped = source.convert("RGB").crop(box)
            x = column * width
            canvas.paste(cropped, (x, 35))
            draw.text(
                (x + 8, 10),
                f"Frame {frame:05d} - {labels[key]}",
                fill="white",
            )
        frames.append(canvas.quantize(colors=192, method=Image.Quantize.MEDIANCUT))

    name = f"control_{roi_name}_{group_name}_{start:05d}_{end - 1:05d}.gif"
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


def make_three_mode_sheet(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    group_name: str,
    keys: tuple[str, str, str],
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
) -> str:
    sampled = [
        min(max(center_frame + offset, 0), expected_frames - 1)
        for offset in (-12, -8, -4, 0, 4, 8)
    ]
    width = box[2] - box[0]
    height = box[3] - box[1]
    row_height = height + 35
    canvas = Image.new("RGB", (width * 3, row_height * len(sampled)), "black")
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
                f"Frame {frame:05d} - {labels[key]}",
                fill="white",
            )
    name = (
        f"control_sheet_{roi_name}_{group_name}_"
        f"{sampled[0]:05d}_{sampled[-1]:05d}.png"
    )
    canvas.save(output / name, compress_level=3)
    return name


def main() -> None:
    args = parse_args()
    control_root = args.control_root.resolve()
    temporal_root = args.temporal_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else control_root / "ControlAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)

    control_paths, resolution, control_validation = validate_mode_paths(
        control_root, CONTROL_MODES, args.expected_frames
    )
    temporal_paths, _, temporal_validation = validate_mode_paths(
        temporal_root,
        TEMPORAL_MODES,
        args.expected_frames,
        resolution,
    )
    paths = {**control_paths, **temporal_paths}
    boxes = roi_boxes(args.scenario, resolution)
    labels = {key: semantic_id for key, semantic_id, _ in ALL_MODES}

    rows: list[dict[str, Any]] = []
    previous_rgb: dict[str, dict[str, np.ndarray]] | None = None
    previous_luma: dict[str, dict[str, np.ndarray]] | None = None
    previous2_luma: dict[str, dict[str, np.ndarray]] | None = None

    for frame in range(args.expected_frames):
        full_rgb = {key: load_rgb(paths[key][frame]) for key, _, _ in ALL_MODES}
        current_rgb = {
            roi_name: {
                key: crop_half(full_rgb[key], box) for key, _, _ in ALL_MODES
            }
            for roi_name, box in boxes.items()
        }
        current_luma = {
            roi_name: {
                key: luma(current_rgb[roi_name][key]) for key, _, _ in ALL_MODES
            }
            for roi_name in boxes
        }
        row: dict[str, Any] = {"frame": frame}

        for roi_name in boxes:
            for key, _, _ in ALL_MODES:
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
            for comparison_name, first_key, second_key in COMPARISONS:
                row[f"{roi_name}_{comparison_name}_same_frame_mae"] = rgb_mae(
                    current_rgb[roi_name][first_key],
                    current_rgb[roi_name][second_key],
                )

        if "occluder_path" in boxes:
            velocity = object_screen_velocity(args.scenario, frame / 60.0)
            for key, _, _ in ALL_MODES:
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

    csv_name = "smaa_1x_control_metrics.csv"
    with (output / csv_name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        key: aggregate(rows, key)
        for key in rows[0]
        if key != "frame"
    }
    center_frame = visual_center_frame(args.scenario)
    gifs: list[str] = []
    sheets: list[str] = []
    for roi_name in visual_regions(args.scenario):
        for group_name, keys in visual_groups(args.scenario):
            gifs.append(
                make_three_mode_gif(
                    output,
                    paths,
                    labels,
                    group_name,
                    keys,
                    roi_name,
                    boxes[roi_name],
                    center_frame,
                    args.expected_frames,
                )
            )
            sheets.append(
                make_three_mode_sheet(
                    output,
                    paths,
                    labels,
                    group_name,
                    keys,
                    roi_name,
                    boxes[roi_name],
                    center_frame,
                    args.expected_frames,
                )
            )

    result = {
        "scenario": args.scenario,
        "conditions": {
            "resolution": list(resolution),
            "frame_rate": 60,
            "warmup_frames": args.warmup_frames,
            "capture_frames_per_mode": args.expected_frames,
            "smaa_preset": "Ultra",
            "one_x_controls": "spatial-only; no jitter, history, or reprojection",
            "temporal_reprojection": "camera motion only; object motion vectors unavailable",
        },
        "control_validation": control_validation,
        "temporal_validation": temporal_validation,
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "artifacts": {
            "metrics_csv": csv_name,
            "comparison_gifs": gifs,
            "sequence_sheets": sheets,
        },
    }
    json_name = "smaa_1x_control_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# SMAA 1X control과 temporal 8-case 비교",
        "",
        "## 범위",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 해상도: {resolution[0]}×{resolution[1]}",
        f"- mode별 warm-up {args.warmup_frames}프레임, 저장 {args.expected_frames}프레임",
        "- DirectX 11, Release x64, SMAA Ultra, fixed 60 Hz",
        "- `O-1X`와 `A-1X`는 jitter/history/reprojection이 없는 spatial-only control",
        "- `-R` temporal mode도 camera motion만 처리하며 object motion vector는 없음",
    ]

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
        for key, semantic_id, _ in ALL_MODES:
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
                f"## `{roi_name}` 1X 기준 비교",
                "",
                "| 비교 | Same-frame MAE | Temporal MAE 변화 | 2차 차분 변화 | Edge strength 변화 |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for comparison_name, first_key, second_key in COMPARISONS:
            first_prefix = f"{roi_name}_{first_key}"
            second_prefix = f"{roi_name}_{second_key}"
            report.append(
                f"| `{labels[second_key]}` vs `{labels[first_key]}` | "
                f"{summary[f'{roi_name}_{comparison_name}_same_frame_mae']['mean']:.6f} | "
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
        for key, semantic_id, _ in ALL_MODES:
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
            "## 해석 제한",
            "",
            "- 1X는 temporal history가 없으므로 낮은 ghosting과 높은 frame 변화가 함께 나타날 수 있다.",
            "- ET2X가 1X에 가까우면 ghosting 감소뿐 아니라 temporal supersampling 효과 상실 가능성도 확인해야 한다.",
            "- 인접 frame과 2차 차분은 실제 camera/object motion을 포함하며 단독 품질 순위가 아니다.",
            "- trailing-halo는 장면 전용 휴리스틱이며 ground-truth ghosting metric이 아니다.",
            "- 최종 판단은 ROI GIF·sequence sheet와 구성요소별 ablation을 함께 사용한다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 지표: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
        ]
    )
    report.extend(f"- 3-way 비교 GIF: `{name}`" for name in gifs)
    report.extend(f"- 3-way 연속 frame sheet: `{name}`" for name in sheets)
    report.append("")

    report_name = "SMAA-1X-Control-Analysis-ko.md"
    (output / report_name).write_text("\n".join(report), encoding="utf-8")
    print(f"SMAA 1X control analysis complete: {output}", flush=True)


if __name__ == "__main__":
    main()
