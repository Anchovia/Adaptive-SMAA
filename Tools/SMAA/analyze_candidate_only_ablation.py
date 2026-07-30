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
    ghost_trail_proxy,
    object_screen_velocity,
    rgb_mae,
    roi_boxes,
)


CANDIDATE_ONLY_MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R"),
    (
        "candidate_only_r",
        "ABL-CandidateOnly-R",
        "ABL_CandidateOnly_R",
    ),
    (
        "document_r",
        "O-ET2X-R-Document",
        "O_ET2X_R_Document",
    ),
)

CANDIDATE_ONLY_COMPARISONS = (
    ("standard_vs_1x", "o_1x", "o_t2x_r"),
    ("candidate_vs_1x", "o_1x", "candidate_only_r"),
    ("document_vs_1x", "o_1x", "document_r"),
    ("candidate_vs_standard", "o_t2x_r", "candidate_only_r"),
    ("document_vs_candidate", "candidate_only_r", "document_r"),
    ("document_vs_standard", "o_t2x_r", "document_r"),
)

COMPONENT_MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R"),
    ("candidate_only_r", "ABL-CandidateOnly-R", "ABL_CandidateOnly_R"),
    (
        "candidate_catmull_r",
        "ABL-Candidate+Catmull-R",
        "ABL_Candidate_Catmull_R",
    ),
    (
        "candidate_catmull_clip_r",
        "ABL-Candidate+Catmull+Clip-R",
        "ABL_Candidate_Catmull_Clip_R",
    ),
    (
        "candidate_catmull_clip_weight08_r",
        "ABL-Candidate+Catmull+Clip+W0.8-R",
        "ABL_Candidate_Catmull_Clip_Weight08_R",
    ),
    ("document_r", "O-ET2X-R-Document", "O_ET2X_R_Document"),
)

COMPONENT_COMPARISONS = (
    ("standard_vs_1x", "o_1x", "o_t2x_r"),
    ("candidate_vs_standard", "o_t2x_r", "candidate_only_r"),
    (
        "catmull_vs_candidate",
        "candidate_only_r",
        "candidate_catmull_r",
    ),
    (
        "clipping_vs_catmull",
        "candidate_catmull_r",
        "candidate_catmull_clip_r",
    ),
    (
        "weight08_vs_clipping",
        "candidate_catmull_clip_r",
        "candidate_catmull_clip_weight08_r",
    ),
    (
        "no_jitter_document_vs_weight08",
        "candidate_catmull_clip_weight08_r",
        "document_r",
    ),
    ("document_vs_standard", "o_t2x_r", "document_r"),
    ("document_vs_1x", "o_1x", "document_r"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the controlled SMAA Candidate-only temporal ablation."
    )
    parser.add_argument("capture_root", type=Path)
    parser.add_argument(
        "--scenario",
        required=True,
        choices=("thin-lines", "object-motion", "combined"),
    )
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument(
        "--full-components",
        action="store_true",
        help="Analyze the full cumulative Catmull/clipping/weight/jitter matrix.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def frame_index(path: Path) -> int:
    return int(path.stem.rsplit("_", 1)[1])


def validate_inputs(
    root: Path,
    expected_frames: int,
    modes: tuple[tuple[str, str, str], ...],
) -> tuple[dict[str, list[Path]], tuple[int, int], dict[str, Any]]:
    paths: dict[str, list[Path]] = {}
    resolution: tuple[int, int] | None = None
    validation: dict[str, Any] = {"root": str(root), "modes": {}}
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
    validation["frame_count_per_mode"] = expected_frames
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


def visual_regions(scenario: str) -> tuple[str, ...]:
    if scenario == "thin-lines":
        return ("thin_line_field",)
    if scenario == "object-motion":
        return ("rotor", "occluder_path")
    return ("thin_line_field", "occluder_path")


def visual_center_frame(scenario: str) -> int:
    return 120 if scenario == "thin-lines" else 90


def make_four_mode_gif(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
    modes: tuple[tuple[str, str, str], ...],
    artifact_prefix: str,
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
    keys = tuple(key for key, _, _ in modes)
    for frame in range(start, end):
        canvas = Image.new("RGB", (width * len(keys), height + 35), "black")
        draw = ImageDraw.Draw(canvas)
        for column, key in enumerate(keys):
            with Image.open(paths[key][frame]) as source:
                cropped = source.convert("RGB").crop(box)
            x = column * width
            canvas.paste(cropped, (x, 35))
            draw.text((x + 8, 10), f"{frame:05d} - {labels[key]}", fill="white")
        frames.append(canvas.quantize(colors=192, method=Image.Quantize.MEDIANCUT))

    name = f"{artifact_prefix}_{roi_name}_{start:05d}_{end - 1:05d}.gif"
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


def make_four_mode_sheet(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
    modes: tuple[tuple[str, str, str], ...],
    artifact_prefix: str,
) -> str:
    sampled = [
        min(max(center_frame + offset, 0), expected_frames - 1)
        for offset in (-12, -8, -4, 0, 4, 8)
    ]
    keys = tuple(key for key, _, _ in modes)
    width = box[2] - box[0]
    height = box[3] - box[1]
    row_height = height + 35
    canvas = Image.new(
        "RGB", (width * len(keys), row_height * len(sampled)), "black"
    )
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
                f"{frame:05d} - {labels[key]}",
                fill="white",
            )
    name = (
        f"{artifact_prefix}_sheet_{roi_name}_"
        f"{sampled[0]:05d}_{sampled[-1]:05d}.png"
    )
    canvas.save(output / name, compress_level=3)
    return name


def main() -> None:
    args = parse_args()
    modes = COMPONENT_MODES if args.full_components else CANDIDATE_ONLY_MODES
    comparisons = (
        COMPONENT_COMPARISONS
        if args.full_components
        else CANDIDATE_ONLY_COMPARISONS
    )
    artifact_prefix = (
        "component_ablation" if args.full_components else "candidate_ablation"
    )
    root = args.capture_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else root
        / ("ComponentAblationAnalysis" if args.full_components else "CandidateOnlyAnalysis")
    )
    output.mkdir(parents=True, exist_ok=True)

    paths, resolution, validation = validate_inputs(
        root, args.expected_frames, modes
    )
    boxes = roi_boxes(args.scenario, resolution)
    labels = {key: semantic_id for key, semantic_id, _ in modes}

    rows: list[dict[str, Any]] = []
    previous_rgb: dict[str, dict[str, np.ndarray]] | None = None
    previous_luma: dict[str, dict[str, np.ndarray]] | None = None
    previous2_luma: dict[str, dict[str, np.ndarray]] | None = None

    for frame in range(args.expected_frames):
        full_rgb = {key: load_rgb(paths[key][frame]) for key, _, _ in modes}
        current_rgb = {
            roi_name: {
                key: crop_half(full_rgb[key], box) for key, _, _ in modes
            }
            for roi_name, box in boxes.items()
        }
        current_luma = {
            roi_name: {
                key: luma(current_rgb[roi_name][key]) for key, _, _ in modes
            }
            for roi_name in boxes
        }
        row: dict[str, Any] = {"frame": frame}

        for roi_name in boxes:
            for key, _, _ in modes:
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
            for comparison_name, first_key, second_key in comparisons:
                row[f"{roi_name}_{comparison_name}_same_frame_mae"] = rgb_mae(
                    current_rgb[roi_name][first_key],
                    current_rgb[roi_name][second_key],
                )

        if "occluder_path" in boxes:
            velocity = object_screen_velocity(args.scenario, frame / 60.0)
            for key, _, _ in modes:
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

    csv_name = (
        "temporal_component_ablation_metrics.csv"
        if args.full_components
        else "candidate_only_ablation_metrics.csv"
    )
    with (output / csv_name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        key: aggregate(rows, key) for key in rows[0] if key != "frame"
    }
    center_frame = visual_center_frame(args.scenario)
    gifs: list[str] = []
    sheets: list[str] = []
    for roi_name in visual_regions(args.scenario):
        gifs.append(
            make_four_mode_gif(
                output,
                paths,
                labels,
                roi_name,
                boxes[roi_name],
                center_frame,
                args.expected_frames,
                modes,
                artifact_prefix,
            )
        )
        sheets.append(
            make_four_mode_sheet(
                output,
                paths,
                labels,
                roi_name,
                boxes[roi_name],
                center_frame,
                args.expected_frames,
                modes,
                artifact_prefix,
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
            "candidate_only_control": {
                "same_as": "O-T2X-R",
                "only_change": "FullScreen coverage -> IntelFamilyNonDominant edge candidates",
                "reprojection": "camera depth/matrices; object motion vectors unavailable",
                "jitter": "SMAA T2X",
                "history_sampler": "Bilinear",
                "history_clipping": "Off",
                "history_weight": 0.5,
            },
            "full_component_matrix": args.full_components,
        },
        "validation": validation,
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "artifacts": {
            "metrics_csv": csv_name,
            "comparison_gifs": gifs,
            "sequence_sheets": sheets,
        },
    }
    json_name = (
        "temporal_component_ablation_summary.json"
        if args.full_components
        else "candidate_only_ablation_summary.json"
    )
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        (
            "# SMAA Edge-selective temporal 구성요소 누적 ablation 분석"
            if args.full_components
            else "# SMAA Candidate-only 구성요소 ablation 분석"
        ),
        "",
        "## 범위",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 해상도: {resolution[0]}×{resolution[1]}",
        f"- mode별 warm-up {args.warmup_frames}프레임, 저장 {args.expected_frames}프레임",
        "- DirectX 11, Release x64, SMAA Ultra, fixed 60 Hz",
        "- `ABL-CandidateOnly-R`은 `O-T2X-R`과 camera reprojection, T2X jitter/subsample, bilinear sampling, clipping Off, history weight 0.5가 같다.",
        "- 유일한 temporal 변경은 full-screen resolve를 IntelFamilyNonDominant edge candidate resolve로 제한한 것이다.",
        "- `O-ET2X-R-Document`는 no-jitter, Catmull-Rom, YCoCg clipping, history 0.8이 함께 적용된 복합 endpoint다.",
    ]
    if args.full_components:
        report.append(
            "- 누적 단계는 Candidate → Catmull-Rom → YCoCg clipping → history 0.8 → no-jitter 순이며 인접 단계는 한 요소만 다르다."
        )

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
        for key, semantic_id, _ in modes:
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
        for comparison_key, first_key, second_key in comparisons:
            first_prefix = f"{roi_name}_{first_key}"
            second_prefix = f"{roi_name}_{second_key}"
            report.append(
                f"| `{labels[second_key]}` vs `{labels[first_key]}` | "
                f"{summary[f'{roi_name}_{comparison_key}_same_frame_mae']['mean']:.6f} | "
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
        for key, semantic_id, _ in modes:
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
            "- Candidate-only와 Standard의 차이만 candidate coverage의 통제 효과로 해석한다.",
            "- document endpoint와의 차이는 jitter, sampler, clipping, weight가 함께 달라 단일 요소 효과가 아니다.",
            "- 인접 frame/2차 차분은 실제 camera/object motion을 포함하며 단독 품질 순위가 아니다.",
            "- trailing-halo는 장면 전용 휴리스틱이며 ground-truth ghosting metric이 아니다.",
            "- object motion vector가 없으므로 `-R`은 camera motion만 보정한다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 지표: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
        ]
    )
    visual_mode_count = len(modes)
    report.extend(
        f"- {visual_mode_count}-way 비교 GIF: `{name}`" for name in gifs
    )
    report.extend(
        f"- {visual_mode_count}-way sequence sheet: `{name}`" for name in sheets
    )
    report.append("")

    report_name = (
        "SMAA-Temporal-Component-Ablation-Analysis-ko.md"
        if args.full_components
        else "SMAA-Candidate-Only-Ablation-Analysis-ko.md"
    )
    (output / report_name).write_text("\n".join(report), encoding="utf-8")
    analysis_name = (
        "Temporal component ablation"
        if args.full_components
        else "Candidate-only ablation"
    )
    print(f"{analysis_name} analysis complete: {output}", flush=True)


if __name__ == "__main__":
    main()
