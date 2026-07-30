import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_original_four_quality import aggregate, edge_strength, load_rgb
from analyze_temporal_stress_quality import (
    crop_half,
    ghost_trail_proxy,
    luma,
    object_screen_velocity,
    rgb_mae,
    roi_boxes,
)


MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("camera_only", "O-T2X-R-CameraOnly", "O_T2X_R_CameraOnly"),
    (
        "object_motion",
        "ABL-O-T2X-R-ObjectMotion",
        "ABL_O_T2X_R_ObjectMotion",
    ),
)

PAIRS = (
    ("camera_only_vs_1x", "o_1x", "camera_only"),
    ("object_motion_vs_1x", "o_1x", "object_motion"),
    ("object_motion_vs_camera_only", "camera_only", "object_motion"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze the controlled rigid opaque object-motion vector capture."
        )
    )
    parser.add_argument("capture_root", type=Path)
    parser.add_argument(
        "--scenario",
        choices=("object-motion", "combined"),
        default="object-motion",
    )
    parser.add_argument("--expected-frames", type=int, default=120)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def validate_inputs(
    capture_root: Path, expected_frames: int
) -> tuple[dict[str, list[Path]], tuple[int, int], dict[str, Any]]:
    paths: dict[str, list[Path]] = {}
    resolution: tuple[int, int] | None = None
    validation: dict[str, Any] = {"modes": {}}
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
                f"{semantic_id}: resolution {current_resolution} differs from "
                f"{resolution}"
            )
        hashes = {
            hashlib.sha256(path.read_bytes()).hexdigest() for path in frames
        }
        paths[key] = frames
        validation["modes"][semantic_id] = {
            "directory": directory,
            "frame_count": len(frames),
            "first_index": indices[0],
            "last_index": indices[-1],
            "unique_png_count": len(hashes),
        }
    assert resolution is not None
    validation["resolution"] = list(resolution)
    return paths, resolution, validation


def make_three_way_artifacts(
    output: Path,
    paths: dict[str, list[Path]],
    boxes: dict[str, tuple[int, int, int, int]],
    expected_frames: int,
) -> dict[str, dict[str, str]]:
    labels = {key: semantic_id for key, semantic_id, _ in MODES}
    artifacts: dict[str, dict[str, str]] = {}
    for roi_name, box in boxes.items():
        left, top, right, bottom = box
        representative = expected_frames // 2
        panels: list[Image.Image] = []
        for key, _, _ in MODES:
            with Image.open(paths[key][representative]) as source:
                panel = source.convert("RGB").crop((left, top, right, bottom))
            panels.append(panel)
        header_height = 28
        sheet = Image.new(
            "RGB",
            (sum(panel.width for panel in panels), panels[0].height + header_height),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        x = 0
        for (key, _, _), panel in zip(MODES, panels):
            sheet.paste(panel, (x, header_height))
            draw.text((x + 6, 7), labels[key], fill="black")
            x += panel.width
        sheet_name = f"object_motion_{roi_name}_frame_{representative:05d}.png"
        sheet.save(output / sheet_name)

        gif_frames: list[Image.Image] = []
        step = max(1, expected_frames // 60)
        for frame_index in range(0, expected_frames, step):
            current_panels: list[Image.Image] = []
            for key, _, _ in MODES:
                with Image.open(paths[key][frame_index]) as source:
                    current_panels.append(
                        source.convert("RGB").crop((left, top, right, bottom))
                    )
            frame_image = Image.new(
                "RGB",
                (
                    sum(panel.width for panel in current_panels),
                    current_panels[0].height + header_height,
                ),
                "white",
            )
            frame_draw = ImageDraw.Draw(frame_image)
            x = 0
            for (key, _, _), panel in zip(MODES, current_panels):
                frame_image.paste(panel, (x, header_height))
                frame_draw.text((x + 6, 7), labels[key], fill="black")
                x += panel.width
            gif_frames.append(frame_image)
        gif_name = f"object_motion_{roi_name}_three_way.gif"
        gif_frames[0].save(
            output / gif_name,
            save_all=True,
            append_images=gif_frames[1:],
            duration=max(17, int(round(1000.0 * step / 60.0))),
            loop=0,
        )
        artifacts[roi_name] = {
            "representative_sheet": sheet_name,
            "three_way_gif": gif_name,
        }
    return artifacts


def main() -> None:
    args = parse_args()
    capture_root = args.capture_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else capture_root / "ObjectMotionVectorAnalysis"
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
                    if previous_luma is None or previous2_luma is None:
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
                    "" if np.isnan(trail_mean) else trail_mean
                )
                row[f"occluder_path_{key}_ghost_trail_width_px"] = (
                    "" if np.isnan(trail_width) else trail_width
                )

        rows.append(row)
        previous_rgb = current_rgb
        previous2_luma = previous_luma
        previous_luma = current_luma
        if frame % 30 == 0 or frame == args.expected_frames - 1:
            print(f"Processed {frame + 1}/{args.expected_frames}", flush=True)

    csv_name = "object_motion_vector_metrics.csv"
    with (output / csv_name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        key: aggregate(rows, key)
        for key in rows[0]
        if key != "frame"
    }
    visual_artifacts = make_three_way_artifacts(
        output, paths, boxes, args.expected_frames
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
            "classification": "engineering controlled object-motion diagnostic",
            "scope": "rigid opaque mesh motion plus camera motion",
            "unsupported": [
                "skinned or deforming geometry",
                "transparent object motion",
                "disocclusion rejection",
            ],
        },
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "artifacts": {
            "metrics_csv": csv_name,
            "visuals": visual_artifacts,
        },
    }
    json_name = "object_motion_vector_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# SMAA rigid opaque object-motion vector 진단 분석",
        "",
        "## 범위",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 해상도: {resolution[0]}×{resolution[1]}",
        f"- mode별 warm-up {args.warmup_frames}프레임, 저장 {args.expected_frames}프레임",
        "- DirectX 11, Release x64, SMAA Ultra, fixed 60 Hz",
        "- `O-T2X-R-CameraOnly`와 객체 모션 진단은 jitter, sampler, clipping, history weight가 동일하다.",
        "- 새 진단은 rigid opaque mesh의 object transform motion만 추가한다.",
        "- disocclusion rejection, 투명 물체, skinning/deformation은 포함하지 않는다.",
        "- engineering 진단이며 최종 8-case 결론이나 일반 object-motion 지원 완료를 뜻하지 않는다.",
        "",
    ]
    for roi_name in boxes:
        report.extend(
            [
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
                "### Same-frame 차이",
                "",
                "| 비교 | RGB MAE |",
                "|---|---:|",
            ]
        )
        for pair_name, _, _ in PAIRS:
            key = f"{roi_name}_{pair_name}_same_frame_mae"
            report.append(f"| `{pair_name}` | {summary[key]['mean']:.6f} |")
        report.append("")

    if "occluder_path" in boxes:
        report.extend(
            [
                "## Occluder trail 휴리스틱",
                "",
                "| Mode | Mean darkness | Width (px) |",
                "|---|---:|---:|",
            ]
        )
        for key, semantic_id, _ in MODES:
            darkness = summary[
                f"occluder_path_{key}_ghost_trail_mean_darkness"
            ]["mean"]
            width = summary[f"occluder_path_{key}_ghost_trail_width_px"]["mean"]
            report.append(f"| `{semantic_id}` | {darkness:.6f} | {width:.6f} |")
        report.extend(
            [
                "",
                "이 값은 분석 휴리스틱이며 절대 ghosting ground truth가 아니다.",
                "",
            ]
        )

    report.extend(
        [
            "## 해석 제한",
            "",
            "- 움직이는 현재 물체 표면의 history 정렬과 새로 드러난 배경의 disocclusion rejection은 서로 다른 문제다.",
            "- 객체 모션 벡터가 rotor의 이중 잔상을 줄여도, occluder 뒤 배경에는 별도 depth/history rejection이 필요할 수 있다.",
            "- 시간 변화량 감소만으로 품질 우위를 주장하지 않는다. 잔상에 의한 blur도 같은 지표를 낮출 수 있다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 지표: `{csv_name}`",
            f"- 요약 JSON: `{json_name}`",
        ]
    )
    for roi_name, artifacts in visual_artifacts.items():
        report.append(
            f"- `{roi_name}` 대표 비교: `{artifacts['representative_sheet']}`"
        )
        report.append(
            f"- `{roi_name}` 3-way GIF: `{artifacts['three_way_gif']}`"
        )
    report_name = "SMAA-Object-Motion-Vector-Analysis-ko.md"
    (output / report_name).write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
