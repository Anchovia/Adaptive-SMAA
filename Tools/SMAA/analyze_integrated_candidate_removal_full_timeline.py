#!/usr/bin/env python3
"""Analyze the full wide-camera integrated candidate-removal matrix.

The matrix keeps reprojection Off and On separate.  O-1X is a shared spatial
control; each temporal group contains its matched Standard T2X control and
integrated edge-selective removal 0.50/0.70/0.75.  The supersample sequence is
a same-pose spatial-reference proxy, not temporal ground truth.
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
REFERENCE_DIRECTORY = "SS_Reference"
EXPECTED_FULL_FRAMES = 480
WINDOWS = {
    "full": (0, 479),
    "pre_still": (0, 59),
    "motion": (60, 419),
    "central_motion": (150, 329),
    "motion_to_still": (410, 439),
    "post_still": (420, 479),
}
MODES = (
    ("o_1x", "O-1X", "O_1X", "control", None),
    ("o_t2x", "O-T2X", "O_T2X", "off", None),
    ("o_et2x_050", "O-ET2X [removal=0.50]", "O_ET2X_Removal_050", "off", 0.50),
    ("o_et2x_070", "O-ET2X [removal=0.70]", "O_ET2X_Removal_070", "off", 0.70),
    ("o_et2x_075", "O-ET2X [removal=0.75]", "O_ET2X_Removal_075", "off", 0.75),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R", "on", None),
    ("o_et2x_r_050", "O-ET2X-R [removal=0.50]", "O_ET2X_R_Removal_050", "on", 0.50),
    ("o_et2x_r_070", "O-ET2X-R [removal=0.70]", "O_ET2X_R_Removal_070", "on", 0.70),
    ("o_et2x_r_075", "O-ET2X-R [removal=0.75]", "O_ET2X_R_Removal_075", "on", 0.75),
)
GROUPS = {
    "off": ("o_1x", "o_t2x", "o_et2x_050", "o_et2x_070", "o_et2x_075"),
    "on": ("o_1x", "o_t2x_r", "o_et2x_r_050", "o_et2x_r_070", "o_et2x_r_075"),
}
MODE_BY_KEY = {entry[0]: entry for entry in MODES}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare full-timeline O-1X, Standard T2X and integrated "
            "edge-selective removal 0.50/0.70/0.75 with reprojection Off/On."
        )
    )
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        required=True,
        metavar=("SCENE", "CAPTURE_ROOT", "REFERENCE_ROOT"),
    )
    parser.add_argument("--expected-frames", type=int, default=EXPECTED_FULL_FRAMES)
    parser.add_argument("--ssim-stride", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_report(root: Path) -> str:
    reports = list(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(f"{root}: expected one results CSV, found {len(reports)}")
    return reports[0].read_text(encoding="utf-8", errors="replace")


def validate_reports(
    capture_root: Path, reference_root: Path, scene: str, expected_frames: int
) -> dict[str, Any]:
    capture = read_report(capture_root)
    reference = read_report(reference_root)
    end = expected_frames - 1
    capture_tokens = (
        "integrated candidate-removal full-timeline matched quality capture",
        f"Scene:           {scene}",
        f"Camera profile:  {PROFILE}",
        f"capture [0, {end}]",
        "API/preset:      DirectX 11, SMAA Ultra",
        "Motion scope:    camera motion only; object motion vectors are not connected",
        "O-ET2X [removal=0.50], O_ET2X_Removal_050",
        "O-ET2X [removal=0.70], O_ET2X_Removal_070",
        "O-ET2X [removal=0.75], O_ET2X_Removal_075",
        "O-ET2X-R [removal=0.50], O_ET2X_R_Removal_050",
        "O-ET2X-R [removal=0.70], O_ET2X_R_Removal_070",
        "O-ET2X-R [removal=0.75], O_ET2X_R_Removal_075",
    )
    for token in capture_tokens:
        if token not in capture:
            raise RuntimeError(f"{capture_root}: report is missing {token!r}")
    for token in (
        "supersample spatial-reference capture",
        f"Scene:           {scene}",
        f"Camera profile:  {PROFILE}",
        "API/preset:      DirectX 11, SMAA Ultra",
    ):
        if token not in reference:
            raise RuntimeError(f"{reference_root}: report is missing {token!r}")
    classification = "formal_parameter_quality_gate" if expected_frames == 480 else "engineering_smoke"
    return {
        "scene": scene,
        "profile": PROFILE,
        "capture_root": str(capture_root.resolve()),
        "reference_root": str(reference_root.resolve()),
        "profile_frame_range": [0, end],
        "frame_count": expected_frames,
        "classification": classification,
        "spatial_aa": "Original SMAA Ultra",
        "motion_scope": "camera/depth reprojection only; no object motion vectors",
        "candidate_source": "SMAAFirstPassIntegratedCandidates",
        "candidate_policy": "IntelFamilyNonDominant adaptation",
        "candidate_expansion": "None",
    }


def collect_reference(directory: Path, expected_frames: int) -> tuple[list[Path], tuple[int, int]]:
    frames = sorted(directory.glob("*.png"), key=lambda path: parse_frame_indices(path)[0])
    selected = [path for path in frames if 0 <= parse_frame_indices(path)[0] < expected_frames]
    indices = [parse_frame_indices(path)[0] for path in selected]
    if indices != list(range(expected_frames)):
        raise RuntimeError(f"{directory}: reference does not contain profile frames 0..{expected_frames - 1}")
    with Image.open(selected[0]) as image:
        resolution = image.size
    for path in selected[1:]:
        with Image.open(path) as image:
            if image.size != resolution:
                raise RuntimeError(f"{path}: inconsistent reference resolution")
    return selected, resolution


def finite_mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.mean(finite, dtype=np.float64)) if finite else math.nan


def percent_change(value: float, baseline: float) -> float:
    if not math.isfinite(value) or not math.isfinite(baseline) or baseline == 0.0:
        return math.nan
    return (value / baseline - 1.0) * 100.0


def temporal_second_difference(current: np.ndarray, previous: np.ndarray, older: np.ndarray) -> float:
    value = current.astype(np.float32) - 2.0 * previous.astype(np.float32) + older.astype(np.float32)
    return float(np.abs(value).mean(dtype=np.float64))


def make_group_sheet(
    path: Path,
    keys: tuple[str, ...],
    frame_indices: list[int],
    mode_frames: dict[str, list[Path]],
    reference_frames: list[Path],
) -> None:
    entries = [(key, MODE_BY_KEY[key][1]) for key in keys] + [("reference", "SS-Reference")]
    width = 260
    header = 30
    rows: list[list[Image.Image]] = []
    for frame_index in frame_indices:
        images: list[Image.Image] = []
        paths = [mode_frames[key][frame_index] for key in keys] + [reference_frames[frame_index]]
        for source in paths:
            with Image.open(source) as image:
                rgb = image.convert("RGB")
                height = max(1, round(rgb.height * width / rgb.width))
                images.append(rgb.resize((width, height), Image.Resampling.LANCZOS))
        rows.append(images)
    height = rows[0][0].height
    sheet = Image.new("RGB", (width * len(entries), (height + header) * len(rows)), "white")
    draw = ImageDraw.Draw(sheet)
    for row_index, (frame_index, images) in enumerate(zip(frame_indices, rows)):
        top = row_index * (height + header)
        for column, ((_, label), image) in enumerate(zip(entries, images)):
            left = column * width
            sheet.paste(image, (left, top + header))
            draw.text((left + 4, top + 7), f"{label} | profile {frame_index}", fill="black")
    sheet.save(path)


def summarize_window(values: dict[str, list[float]], start: int, end: int) -> dict[str, float]:
    return {name: finite_mean(samples[start : end + 1]) for name, samples in values.items()}


def analyze_case(
    scene: str,
    capture_root: Path,
    reference_root: Path,
    expected_frames: int,
    ssim_stride: int,
    output: Path,
) -> dict[str, Any]:
    provenance = validate_reports(capture_root, reference_root, scene, expected_frames)
    mode_frames: dict[str, list[Path]] = {}
    resolution: tuple[int, int] | None = None
    for key, _, directory, _, _ in MODES:
        frames, current_resolution = collect_frames(capture_root / directory, expected_frames, 0)
        if resolution is None:
            resolution = current_resolution
        elif resolution != current_resolution:
            raise RuntimeError(f"{capture_root}: mode resolution mismatch")
        mode_frames[key] = frames
    reference_frames, reference_resolution = collect_reference(
        reference_root / REFERENCE_DIRECTORY, expected_frames
    )
    if reference_resolution != resolution:
        raise RuntimeError(f"{reference_root}: reference resolution mismatch")

    metric_names = (
        "rgb_mae_reference",
        "psnr_reference",
        "luma_ssim_reference",
        "edge_strength",
        "same_frame_mae_o1x",
        "adjacent_rgb_mae",
        "second_temporal_difference",
    )
    metrics = {key: {name: [] for name in metric_names} for key, *_ in MODES}
    rows: list[dict[str, Any]] = []
    previous: dict[str, np.ndarray] = {}
    older: dict[str, np.ndarray] = {}
    reference_edge: list[float] = []
    for frame_index in range(expected_frames):
        reference = load_rgb(reference_frames[frame_index])
        reference_edge.append(edge_strength(reference))
        images = {key: load_rgb(mode_frames[key][frame_index]) for key, *_ in MODES}
        o1x = images["o_1x"]
        for key, label, _, reprojection, removal in MODES:
            current = images[key]
            values = {
                "rgb_mae_reference": rgb_mae(current, reference),
                "psnr_reference": rgb_psnr(current, reference),
                "luma_ssim_reference": (
                    luma_ssim(current, reference)
                    if frame_index % ssim_stride == 0
                    else math.nan
                ),
                "edge_strength": edge_strength(current),
                "same_frame_mae_o1x": rgb_mae(current, o1x),
                "adjacent_rgb_mae": rgb_mae(current, previous[key]) if key in previous else math.nan,
                "second_temporal_difference": (
                    temporal_second_difference(current, previous[key], older[key])
                    if key in older
                    else math.nan
                ),
            }
            for name, value in values.items():
                metrics[key][name].append(value)
            rows.append(
                {
                    "scene": scene,
                    "profile_frame": frame_index,
                    "mode": label,
                    "reprojection": reprojection,
                    "removal": "" if removal is None else f"{removal:.2f}",
                    **values,
                }
            )
            if key in previous:
                older[key] = previous[key]
            previous[key] = current

    scene_output = output / scene.lower()
    scene_output.mkdir(parents=True, exist_ok=True)
    with (scene_output / "per_frame_metrics.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    window_summaries: dict[str, Any] = {}
    for window, (start, configured_end) in WINDOWS.items():
        end = expected_frames - 1 if window == "full" else configured_end
        if end >= expected_frames:
            continue
        reference_edge_mean = finite_mean(reference_edge[start : end + 1])
        modes: dict[str, Any] = {}
        for key, label, _, reprojection, removal in MODES:
            summary = summarize_window(metrics[key], start, end)
            summary.update(
                {
                    "label": label,
                    "reprojection": reprojection,
                    "removal": removal,
                    "edge_to_reference_ratio": summary["edge_strength"] / reference_edge_mean,
                }
            )
            modes[key] = summary
        for group, standard_key in (("off", "o_t2x"), ("on", "o_t2x_r")):
            standard_distance = modes[standard_key]["same_frame_mae_o1x"]
            for key in GROUPS[group][1:]:
                modes[key]["o1x_distance_retention_proxy_percent"] = (
                    modes[key]["same_frame_mae_o1x"] / standard_distance * 100.0
                    if standard_distance > 0.0
                    else math.nan
                )
        window_summaries[window] = {
            "profile_frame_range": [start, end],
            "modes": modes,
        }

    visual_frames = [30, 90, 180, 300, 415, 430]
    visual_frames = [index for index in visual_frames if index < expected_frames]
    if visual_frames:
        make_group_sheet(
            scene_output / "reprojection_off_sequence_sheet.png",
            GROUPS["off"], visual_frames, mode_frames, reference_frames,
        )
        make_group_sheet(
            scene_output / "reprojection_on_sequence_sheet.png",
            GROUPS["on"], visual_frames, mode_frames, reference_frames,
        )

    result = {
        "provenance": provenance,
        "resolution": list(resolution or (0, 0)),
        "ssim_stride": ssim_stride,
        "windows": window_summaries,
        "interpretation_limits": {
            "reference": "within-frame supersample spatial proxy, not temporal ground truth",
            "temporal_change": "unaligned screen-space metric containing scene/camera motion",
            "retention_proxy": (
                "same-frame distance from O-1X normalized by the matched Standard T2X; "
                "not a direct measurement of history sample usage"
            ),
        },
    }
    (scene_output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def write_markdown(output: Path, results: dict[str, Any]) -> None:
    lines = [
        "# Integrated Candidate Removal Full-Timeline Matched 품질 분석",
        "",
        "이 gate는 Original SMAA에서 reprojection Off/On을 분리하고, 각 Standard T2X control과 integrated edge-selective removal 0.50/0.70/0.75를 전체 480-frame wide 경로에서 비교한다.",
        "각 edge-selective 3개 값 안에서는 removal만 바뀐다. 다만 Standard와 document profile 사이에는 candidate coverage뿐 아니라 deliberate jitter, history sampler, clipping과 weight 차이도 있으므로 candidate 선택 단독 효과로 표현하지 않는다.",
        "SS-Reference는 동일 pose spatial proxy이며 temporal ground truth가 아니다. O-1X-distance retention proxy도 실제 history 사용률이 아니라 출력 거리 대용값이다.",
        "",
    ]
    for scene, result in results.items():
        lines.extend([f"## {scene.capitalize()}", ""])
        for window in ("full", "motion", "central_motion", "motion_to_still", "post_still"):
            if window not in result["windows"]:
                continue
            entry = result["windows"][window]
            start, end = entry["profile_frame_range"]
            lines.extend(
                [
                    f"### {window} ({start}~{end})",
                    "",
                    "| Mode | Ref MAE ↓ | PSNR ↑ | SSIM ↑ | Edge/ref | O-1X 거리 ↓ | Standard 대비 O-1X-distance retention proxy | Adjacent MAE | 2차 시간 차분 |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
                ]
            )
            for key, label, _, _, _ in MODES:
                summary = entry["modes"][key]
                retention = summary.get("o1x_distance_retention_proxy_percent", math.nan)
                retention_text = f"{retention:.3f}%" if math.isfinite(retention) else "-"
                lines.append(
                    f"| `{label}` | {summary['rgb_mae_reference']:.6f} | {summary['psnr_reference']:.4f} "
                    f"| {summary['luma_ssim_reference']:.6f} | {summary['edge_to_reference_ratio']:.6f} "
                    f"| {summary['same_frame_mae_o1x']:.6f} | {retention_text} "
                    f"| {summary['adjacent_rgb_mae']:.6f} | {summary['second_temporal_difference']:.6f} |"
                )
            lines.append("")

        comparison_window = "motion" if "motion" in result["windows"] else "full"
        motion = result["windows"][comparison_window]["modes"]
        lines.extend(
            [
                f"### removal=0.50 대비 {comparison_window} 구간 변화",
                "",
                "| Reprojection | Removal | Ref MAE | O-1X 거리 | Adjacent MAE | 2차 시간 차분 |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for group, prefix in (("Off", "o_et2x"), ("On", "o_et2x_r")):
            baseline = motion[f"{prefix}_050"]
            for suffix, removal in (("070", 0.70), ("075", 0.75)):
                current = motion[f"{prefix}_{suffix}"]
                lines.append(
                    f"| {group} | {removal:.2f} "
                    f"| {percent_change(current['rgb_mae_reference'], baseline['rgb_mae_reference']):+.3f}% "
                    f"| {percent_change(current['same_frame_mae_o1x'], baseline['same_frame_mae_o1x']):+.3f}% "
                    f"| {percent_change(current['adjacent_rgb_mae'], baseline['adjacent_rgb_mae']):+.3f}% "
                    f"| {percent_change(current['second_temporal_difference'], baseline['second_temporal_difference']):+.3f}% |"
                )
        lines.extend(
            [
                "",
                f"- Reprojection Off 연속 시트: `{scene.lower()}/reprojection_off_sequence_sheet.png`",
                f"- Reprojection On 연속 시트: `{scene.lower()}/reprojection_on_sequence_sheet.png`",
                f"- 프레임별 값: `{scene.lower()}/per_frame_metrics.csv`",
                "",
            ]
        )
    lines.extend(
        [
            "## 판정 원칙",
            "",
            "- removal의 최종값은 두 장면과 reprojection Off/On에서 spatial-reference, CGVQM-2, temporal 변화와 연속 프레임이 함께 허용될 때만 고정한다.",
            "- 출력이 O-1X에 가까워지는 현상을 자동으로 품질 개선이라고 해석하지 않는다. 고스팅 감소와 temporal supersampling 손실을 함께 구분한다.",
            "- 이 분석 뒤 같은 사전 고정 window에 Intel CGVQM-2를 순차 실행하고, 공식 점수와 error-map을 보조 근거로 추가한다.",
        ]
    )
    (output / "SMAA-Integrated-Candidate-Removal-Full-Timeline-Analysis-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.expected_frames < 3:
        raise RuntimeError("At least three frames are required")
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
            args.ssim_stride,
            args.output,
        )
    (args.output / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(args.output, results)
    print(f"PASS: validated {len(results)} scene(s) and {len(MODES)} modes")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
