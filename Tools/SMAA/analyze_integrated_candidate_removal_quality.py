#!/usr/bin/env python3
"""Analyze the integrated first-pass candidate-removal quality gate.

This is a parameter-screening tool, not an automatic optimum selector.  It
keeps O-1X and O-T2X-R controls beside four O-ET2X-R removal values and reports
both same-pose spatial-reference error and unaligned temporal change.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_wide_camera_reference_quality import (
    collect_frames,
    edge_strength,
    load_rgb,
    luma_ssim,
    parse_frame_indices,
    rgb_mae,
    rgb_psnr,
)


PROFILE = "flythrough-wide-yaw-360"
MODES = (
    ("o_1x", "O-1X", "O_1X", None),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R", None),
    ("o_et2x_r_050", "O-ET2X-R [removal=0.50]", "O_ET2X_R_Removal_050", 0.50),
    ("o_et2x_r_065", "O-ET2X-R [removal=0.65]", "O_ET2X_R_Removal_065", 0.65),
    ("o_et2x_r_070", "O-ET2X-R [removal=0.70]", "O_ET2X_R_Removal_070", 0.70),
    ("o_et2x_r_075", "O-ET2X-R [removal=0.75]", "O_ET2X_R_Removal_075", 0.75),
)
REFERENCE_DIRECTORY = "SS_Reference"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare O-1X, O-T2X-R and integrated O-ET2X-R removal "
            "0.50/0.65/0.70/0.75 against a same-pose SS reference."
        )
    )
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        required=True,
        metavar=("SCENE", "CAPTURE_ROOT", "REFERENCE_ROOT"),
    )
    parser.add_argument("--expected-frames", type=int, required=True)
    parser.add_argument("--first-profile-frame", type=int, required=True)
    parser.add_argument("--ssim-stride", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_report(root: Path) -> str:
    reports = list(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(f"{root}: expected one results CSV, found {len(reports)}")
    return reports[0].read_text(encoding="utf-8", errors="replace")


def validate_capture_report(
    root: Path, scene: str, first_profile_frame: int, expected_frames: int
) -> dict[str, Any]:
    text = read_report(root)
    last_profile_frame = first_profile_frame + expected_frames - 1
    required = (
        "SMAA integrated candidate-removal wide camera-motion quality gate",
        f"Scene:           {scene}",
        f"Camera profile:  {PROFILE}",
        f"capture [{first_profile_frame}, {last_profile_frame}]",
        "API/preset:      DirectX 11, SMAA Ultra",
        "Motion scope:    camera motion only; object motion vectors are not connected",
        "O-ET2X-R [removal=0.50], O_ET2X_R_Removal_050",
        "O-ET2X-R [removal=0.65], O_ET2X_R_Removal_065",
        "O-ET2X-R [removal=0.70], O_ET2X_R_Removal_070",
        "O-ET2X-R [removal=0.75], O_ET2X_R_Removal_075",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"{root}: report is missing {token!r}")
    return {
        "root": str(root.resolve()),
        "scene": scene,
        "profile": PROFILE,
        "first_profile_frame": first_profile_frame,
        "last_profile_frame": last_profile_frame,
        "frame_count": expected_frames,
        "classification": "engineering_parameter_quality_gate",
        "motion_scope": "camera/depth reprojection; no object motion vectors",
    }


def validate_reference_report(
    root: Path, scene: str, first_profile_frame: int, expected_frames: int
) -> dict[str, Any]:
    text = read_report(root)
    last_profile_frame = first_profile_frame + expected_frames - 1
    required = (
        "supersample spatial-reference capture",
        f"Scene:           {scene}",
        f"Camera profile:  {PROFILE}",
        "API/preset:      DirectX 11, SMAA Ultra",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"{root}: reference report is missing {token!r}")
    return {
        "root": str(root.resolve()),
        "requested_profile_range": [first_profile_frame, last_profile_frame],
        "classification": "supersample_spatial_reference_proxy",
        "temporal_history": False,
    }


def collect_reference_range(
    directory: Path, expected_frames: int, first_profile_frame: int
) -> tuple[list[Path], tuple[int, int]]:
    requested = set(range(first_profile_frame, first_profile_frame + expected_frames))
    all_frames = sorted(directory.glob("*.png"), key=lambda path: parse_frame_indices(path)[0])
    selected = [
        path for path in all_frames if parse_frame_indices(path)[0] in requested
    ]
    profile_indices = [parse_frame_indices(path)[0] for path in selected]
    expected_indices = list(
        range(first_profile_frame, first_profile_frame + expected_frames)
    )
    if profile_indices != expected_indices:
        raise RuntimeError(
            f"{directory}: reference does not contain requested profile range "
            f"{first_profile_frame}..{first_profile_frame + expected_frames - 1}"
        )
    with Image.open(selected[0]) as image:
        resolution = image.size
    for path in selected[1:]:
        with Image.open(path) as image:
            if image.size != resolution:
                raise RuntimeError(f"{path}: inconsistent reference resolution")
    return selected, resolution


def mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.mean(finite, dtype=np.float64)) if finite else float("nan")


def percent_change(value: float, baseline: float) -> float:
    if not math.isfinite(value) or not math.isfinite(baseline) or baseline == 0.0:
        return float("nan")
    return (value / baseline - 1.0) * 100.0


def temporal_second_difference(
    current: np.ndarray, previous: np.ndarray, previous_previous: np.ndarray
) -> float:
    values = (
        current.astype(np.float32)
        - 2.0 * previous.astype(np.float32)
        + previous_previous.astype(np.float32)
    )
    return float(np.abs(values).mean(dtype=np.float64))


def make_sheet(
    path: Path,
    frame_indices: list[int],
    mode_frames: dict[str, list[Path]],
    reference_frames: list[Path],
) -> None:
    entries = [(key, label) for key, label, _, _ in MODES] + [("reference", "SS-Reference")]
    cell_width = 300
    header = 32
    images: list[list[Image.Image]] = []
    for frame_index in frame_indices:
        row: list[Image.Image] = []
        paths = [mode_frames[key][frame_index] for key, _, _, _ in MODES]
        paths.append(reference_frames[frame_index])
        for source in paths:
            with Image.open(source) as image:
                copy = image.convert("RGB")
                height = max(1, round(copy.height * cell_width / copy.width))
                row.append(copy.resize((cell_width, height), Image.Resampling.LANCZOS))
        images.append(row)
    cell_height = images[0][0].height
    sheet = Image.new(
        "RGB",
        (cell_width * len(entries), (cell_height + header) * len(frame_indices)),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    for row_index, frame_index in enumerate(frame_indices):
        top = row_index * (cell_height + header)
        for column, ((_, label), image) in enumerate(zip(entries, images[row_index])):
            left = column * cell_width
            sheet.paste(image, (left, top + header))
            draw.text((left + 5, top + 7), f"{label} | capture {frame_index}", fill="black")
    sheet.save(path)


def make_difference_sheet(
    path: Path,
    frame_index: int,
    mode_frames: dict[str, list[Path]],
    reference_frames: list[Path],
) -> None:
    reference = load_rgb(reference_frames[frame_index]).astype(np.int16)
    cell_width = 320
    header = 34
    cells: list[tuple[str, Image.Image]] = []
    for key, label, _, _ in MODES:
        test = load_rgb(mode_frames[key][frame_index]).astype(np.int16)
        difference = np.clip(np.abs(test - reference) * 4, 0, 255).astype(np.uint8)
        image = Image.fromarray(difference, mode="RGB")
        height = max(1, round(image.height * cell_width / image.width))
        cells.append((label, image.resize((cell_width, height), Image.Resampling.LANCZOS)))
    cell_height = cells[0][1].height
    sheet = Image.new("RGB", (cell_width * len(cells), cell_height + header), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(cells):
        left = index * cell_width
        sheet.paste(image, (left, header))
        draw.text((left + 5, 8), f"{label} | |test-ref| x4", fill="black")
    sheet.save(path)


def analyze_case(
    scene: str,
    capture_root: Path,
    reference_root: Path,
    expected_frames: int,
    first_profile_frame: int,
    ssim_stride: int,
    output: Path,
) -> dict[str, Any]:
    provenance = validate_capture_report(
        capture_root, scene, first_profile_frame, expected_frames
    )
    reference_provenance = validate_reference_report(
        reference_root, scene, first_profile_frame, expected_frames
    )
    mode_frames: dict[str, list[Path]] = {}
    resolution: tuple[int, int] | None = None
    for key, _, directory, _ in MODES:
        frames, current_resolution = collect_frames(
            capture_root / directory, expected_frames, first_profile_frame
        )
        if resolution is None:
            resolution = current_resolution
        elif current_resolution != resolution:
            raise RuntimeError(f"{capture_root}: inconsistent mode resolution")
        mode_frames[key] = frames
    reference_frames, reference_resolution = collect_reference_range(
        reference_root / REFERENCE_DIRECTORY,
        expected_frames,
        first_profile_frame,
    )
    if reference_resolution != resolution:
        raise RuntimeError(
            f"{reference_root}: reference resolution {reference_resolution} != {resolution}"
        )

    metrics: dict[str, dict[str, list[float]]] = {
        key: {
            "rgb_mae_reference": [],
            "psnr_reference": [],
            "luma_ssim_reference": [],
            "edge_strength": [],
            "same_frame_mae_o1x": [],
            "adjacent_rgb_mae": [],
            "second_temporal_difference": [],
        }
        for key, _, _, _ in MODES
    }
    rows: list[dict[str, Any]] = []
    previous: dict[str, np.ndarray] = {}
    previous_previous: dict[str, np.ndarray] = {}
    for frame_index in range(expected_frames):
        reference = load_rgb(reference_frames[frame_index])
        current_images = {
            key: load_rgb(mode_frames[key][frame_index]) for key, _, _, _ in MODES
        }
        o1x = current_images["o_1x"]
        for key, label, _, removal in MODES:
            current = current_images[key]
            mae = rgb_mae(current, reference)
            psnr = rgb_psnr(current, reference)
            ssim = (
                luma_ssim(current, reference)
                if frame_index % max(1, ssim_stride) == 0
                else float("nan")
            )
            edge = edge_strength(current)
            o1x_mae = rgb_mae(current, o1x)
            adjacent = (
                rgb_mae(current, previous[key]) if key in previous else float("nan")
            )
            second = (
                temporal_second_difference(current, previous[key], previous_previous[key])
                if key in previous_previous
                else float("nan")
            )
            values = metrics[key]
            values["rgb_mae_reference"].append(mae)
            values["psnr_reference"].append(psnr)
            values["luma_ssim_reference"].append(ssim)
            values["edge_strength"].append(edge)
            values["same_frame_mae_o1x"].append(o1x_mae)
            values["adjacent_rgb_mae"].append(adjacent)
            values["second_temporal_difference"].append(second)
            rows.append(
                {
                    "scene": scene,
                    "capture_frame": frame_index,
                    "profile_frame": first_profile_frame + frame_index,
                    "mode": label,
                    "removal": "" if removal is None else f"{removal:.2f}",
                    "rgb_mae_reference": mae,
                    "psnr_reference": psnr,
                    "luma_ssim_reference": ssim,
                    "edge_strength": edge,
                    "same_frame_mae_o1x": o1x_mae,
                    "adjacent_rgb_mae": adjacent,
                    "second_temporal_difference": second,
                }
            )
            if key in previous:
                previous_previous[key] = previous[key]
            previous[key] = current

    scene_output = output / scene.lower()
    scene_output.mkdir(parents=True, exist_ok=True)
    with (scene_output / "per_frame_metrics.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summaries: dict[str, Any] = {}
    reference_edge_values = [edge_strength(load_rgb(path)) for path in reference_frames]
    reference_edge_mean = mean(reference_edge_values)
    for key, label, _, removal in MODES:
        values = metrics[key]
        summaries[key] = {
            "label": label,
            "removal": removal,
            "rgb_mae_reference_mean": mean(values["rgb_mae_reference"]),
            "psnr_reference_mean": mean(values["psnr_reference"]),
            "luma_ssim_reference_mean": mean(values["luma_ssim_reference"]),
            "edge_strength_mean": mean(values["edge_strength"]),
            "edge_to_reference_ratio": mean(values["edge_strength"]) / reference_edge_mean,
            "same_frame_mae_o1x_mean": mean(values["same_frame_mae_o1x"]),
            "adjacent_rgb_mae_mean": mean(values["adjacent_rgb_mae"]),
            "second_temporal_difference_mean": mean(values["second_temporal_difference"]),
        }

    visual_frames = sorted({0, expected_frames // 2, expected_frames - 1})
    make_sheet(
        scene_output / "comparison_sheet.png",
        visual_frames,
        mode_frames,
        reference_frames,
    )
    make_difference_sheet(
        scene_output / "reference_difference_x4_sheet.png",
        expected_frames // 2,
        mode_frames,
        reference_frames,
    )
    result = {
        "provenance": provenance,
        "reference": reference_provenance,
        "resolution": list(resolution or (0, 0)),
        "ssim_stride": ssim_stride,
        "summary": summaries,
        "selection_policy": (
            "No automatic winner. Keep the public 0.50 control and shortlist only "
            "values whose spatial-reference, temporal-change and visual evidence are "
            "jointly acceptable before repeated readback-Off performance testing."
        ),
    }
    (scene_output / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result


def write_markdown(output: Path, results: dict[str, Any]) -> None:
    lines = [
        "# SMAA Integrated Candidate Removal 품질 Gate",
        "",
        "이 결과는 removal 파라미터 선별용 engineering gate이며 최종 8-case 결과가 아니다.",
        "SS-Reference는 동일 pose의 spatial proxy이고 temporal/ghosting 절대 ground truth가 아니다.",
        "Unaligned adjacent/second difference에는 장면 motion이 포함되므로 상대값으로만 사용한다.",
        "",
    ]
    for scene, result in results.items():
        lines.extend(
            [
                f"## {scene}",
                "",
                "| Mode | Ref RGB MAE ↓ | PSNR ↑ | Luma SSIM ↑ | Edge/ref | O-1X same-frame MAE | Adjacent MAE | 2차 시간 차분 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for key, _, _, _ in MODES:
            summary = result["summary"][key]
            lines.append(
                f"| `{summary['label']}` | {summary['rgb_mae_reference_mean']:.6f} "
                f"| {summary['psnr_reference_mean']:.4f} "
                f"| {summary['luma_ssim_reference_mean']:.6f} "
                f"| {summary['edge_to_reference_ratio']:.6f} "
                f"| {summary['same_frame_mae_o1x_mean']:.6f} "
                f"| {summary['adjacent_rgb_mae_mean']:.6f} "
                f"| {summary['second_temporal_difference_mean']:.6f} |"
            )
        baseline = result["summary"]["o_et2x_r_050"]
        baseline_edge_distance = abs(baseline["edge_to_reference_ratio"] - 1.0)
        lines.extend(
            [
                "",
                "### removal=0.50 대비 변화율",
                "",
                "음수 Ref MAE는 spatial reference 오차 감소를, 음수 O-1X 거리는 1X 출력에 더 가까워졌음을 뜻한다. "
                "양수 시간 변화량은 smoothing이 줄었을 가능성을 나타내지만 motion-compensated 지표는 아니다.",
                "",
                "| Removal | Ref MAE | O-1X 거리 | Adjacent MAE | 2차 시간 차분 | Edge/ref의 1.0 거리 |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for key in ("o_et2x_r_065", "o_et2x_r_070", "o_et2x_r_075"):
            summary = result["summary"][key]
            lines.append(
                f"| {summary['removal']:.2f} "
                f"| {percent_change(summary['rgb_mae_reference_mean'], baseline['rgb_mae_reference_mean']):+.3f}% "
                f"| {percent_change(summary['same_frame_mae_o1x_mean'], baseline['same_frame_mae_o1x_mean']):+.3f}% "
                f"| {percent_change(summary['adjacent_rgb_mae_mean'], baseline['adjacent_rgb_mae_mean']):+.3f}% "
                f"| {percent_change(summary['second_temporal_difference_mean'], baseline['second_temporal_difference_mean']):+.3f}% "
                f"| {percent_change(abs(summary['edge_to_reference_ratio'] - 1.0), baseline_edge_distance):+.3f}% |"
            )
        lines.extend(
            [
                "",
                f"- 비교 시트: `{scene.lower()}/comparison_sheet.png`",
                f"- reference 차이 ×4: `{scene.lower()}/reference_difference_x4_sheet.png`",
                f"- 프레임별 값: `{scene.lower()}/per_frame_metrics.csv`",
                "",
            ]
        )
    lines.extend(
        [
            "## 판정 규칙",
            "",
            "후보 비율이나 단일 지표만으로 최적값을 자동 선택하지 않는다. 공개 기본값 0.50을 control로 유지하고, 두 장면의 reference 오차·temporal 변화·대표 연속 프레임을 함께 통과한 값만 readback-Off 반복 성능 측정으로 올린다.",
        ]
    )
    (output / "SMAA-Integrated-Candidate-Removal-Quality-Gate-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.expected_frames < 3:
        raise RuntimeError("At least three frames are required for second difference")
    if args.ssim_stride < 1:
        raise RuntimeError("--ssim-stride must be at least 1")
    args.output.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    for scene, capture_root, reference_root in args.case:
        scene_key = scene.lower()
        if scene_key not in {"bistro", "minecraft"}:
            raise RuntimeError(f"Unsupported scene: {scene}")
        if scene_key in results:
            raise RuntimeError(f"Duplicate scene: {scene}")
        results[scene_key] = analyze_case(
            scene_key,
            Path(capture_root),
            Path(reference_root),
            args.expected_frames,
            args.first_profile_frame,
            args.ssim_stride,
            args.output,
        )
    (args.output / "summary.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_markdown(args.output, results)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
