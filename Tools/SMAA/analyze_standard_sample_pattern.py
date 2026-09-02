#!/usr/bin/env python3
"""Analyze the valid paired SMAA T2X sample-pattern isolation gate.

O-T2X-R and ABL-Standard-PatternOff-R share the Standard full-screen resolve,
bilinear history sampler, 0.5 history weight, camera/depth reprojection and
history lifecycle.  The changed factor is the complete valid SMAA T2X
subpixel pattern: projection jitter plus its matching subsample indices.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_wide_camera_reference_quality import (
    collect_frames,
    difference_image,
    edge_strength,
    finite_mean,
    load_rgb,
    luma_ssim,
    resized,
    rgb_mae,
    rgb_psnr,
)


PROFILE = "flythrough-wide-yaw-360"
MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("standard", "O-T2X-R", "O_T2X_R"),
    ("pattern_off", "ABL-Standard-PatternOff-R", "ABL_Standard_PatternOff_R"),
    ("document_full", "ABL-Document-FullScreen-R", "ABL_Document_FullScreen_R"),
    ("edge", "O-ET2X-R", "O_ET2X_R"),
)
WINDOWS = (
    ("full", "전체", 0, 480),
    ("central_motion", "중앙 이동", 150, 330),
    ("transition", "이동→정지", 410, 440),
    ("post_still", "후기 정지", 420, 480),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        nargs=5,
        action="append",
        required=True,
        metavar=("SCENE", "CAPTURE", "REFERENCE", "FORMAL_BASE", "COVERAGE_BASE"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-frames", type=int, default=480)
    parser.add_argument("--ssim-stride", type=int, default=4)
    return parser.parse_args()


def report_text(root: Path) -> str:
    reports = list(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(f"{root}: expected one results CSV, found {len(reports)}")
    return reports[0].read_text(encoding="utf-8", errors="replace")


def validate_reports(capture: Path, reference: Path, scene: str, frames: int) -> None:
    capture_required = (
        "SMAA Standard temporal sample-pattern isolation capture",
        f"Scene:           {scene.lower()}",
        f"Camera profile:  {PROFILE}",
        f"Profile frames:  480 total; capture [0, {frames - 1}]",
        "Primary axis:    O-T2X-R versus Pattern-Off-R changes only the valid paired SMAA T2X temporal subpixel pattern",
        "projection jitter is not disabled independently from SMAA T2X subsample indices",
        "Classification:  complete camera profile quality capture",
    )
    reference_required = (
        "supersample spatial-reference capture",
        f"Scene:           {scene.lower()}",
        f"Camera profile:  {PROFILE}",
        "2x linear resolution, 3x3 within-frame subpixel grid, 8x MSAA",
        "supersample spatial-reference proxy",
    )
    capture_text = report_text(capture)
    reference_text = report_text(reference)
    missing = [value for value in capture_required if value not in capture_text]
    missing += [value for value in reference_required if value not in reference_text]
    if missing:
        raise RuntimeError(f"{scene}: report validation failed: {missing}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_bridge(
    scene: str,
    capture: Path,
    formal_base: Path,
    coverage_base: Path,
    expected: int,
) -> list[dict[str, Any]]:
    sources = {
        "O_1X": formal_base,
        "O_T2X_R": formal_base,
        "O_ET2X_R": formal_base,
        "ABL_Document_FullScreen_R": coverage_base,
    }
    rows: list[dict[str, Any]] = []
    for directory, old_root in sources.items():
        new_files = sorted((capture / directory).glob("*.png"))
        old_files = sorted((old_root / directory).glob("*.png"))
        if len(new_files) != expected or len(old_files) != expected:
            raise RuntimeError(
                f"{scene}/{directory}: hash counts new={len(new_files)}, old={len(old_files)}"
            )
        if [path.name for path in new_files] != [path.name for path in old_files]:
            raise RuntimeError(f"{scene}/{directory}: filenames differ")
        mismatches = sum(
            file_sha256(new_path) != file_sha256(old_path)
            for new_path, old_path in zip(new_files, old_files)
        )
        if mismatches:
            raise RuntimeError(f"{scene}/{directory}: {mismatches} byte-hash mismatches")
        rows.append(
            {
                "scene": scene,
                "mode_directory": directory,
                "frame_count": expected,
                "byte_hash_mismatches": mismatches,
                "prior_capture_root": str(old_root),
            }
        )
    return rows


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return finite_mean([float(row[key]) for row in rows])


def make_sheet(output: Path, paths: dict[str, list[Path]], frames: list[int], diff: bool) -> None:
    columns = (("SS-Ref", "reference"),) + tuple((label, key) for key, label, _ in MODES)
    width = 240
    label_height = 25
    tile_height = resized(paths["reference"][0], width).height
    canvas = Image.new(
        "RGB",
        (width * len(columns), label_height + len(frames) * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, key) in enumerate(columns):
        suffix = " |x4 error|" if diff and key != "reference" else ""
        draw.text((column * width + 4, 6), label + suffix, fill="black")
    y = label_height
    for frame in frames:
        for column, (_, key) in enumerate(columns):
            image = (
                difference_image(paths[key][frame], paths["reference"][frame], width)
                if diff and key != "reference"
                else resized(paths[key][frame], width)
            )
            canvas.paste(image, (column * width, y))
        draw.text((4, y + tile_height + 5), f"profile frame {frame:05d}", fill="black")
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def analyze_case(
    scene: str,
    capture: Path,
    reference: Path,
    expected: int,
    ssim_stride: int,
    output: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_reports(capture, reference, scene, expected)
    paths: dict[str, list[Path]] = {}
    resolutions: set[tuple[int, int]] = set()
    for key, _, directory in MODES:
        frames, resolution = collect_frames(capture / directory, expected, 0)
        paths[key] = frames
        resolutions.add(resolution)
    paths["reference"], resolution = collect_frames(reference / "SS_Reference", expected, 0)
    resolutions.add(resolution)
    if len(resolutions) != 1:
        raise RuntimeError(f"{scene}: resolution mismatch {resolutions}")

    rows: list[dict[str, Any]] = []
    previous: dict[str, np.ndarray] = {}
    previous_reference: np.ndarray | None = None
    for frame in range(expected):
        if frame % 60 == 0:
            print(f"[{scene}] metrics {frame}/{expected}", flush=True)
        reference_rgb = load_rgb(paths["reference"][frame])
        reference_edge = edge_strength(reference_rgb)
        for key, label, _ in MODES:
            image = load_rgb(paths[key][frame])
            temporal_residual = float("nan")
            if key in previous and previous_reference is not None:
                current_delta = image.astype(np.int16) - previous[key].astype(np.int16)
                reference_delta = reference_rgb.astype(np.int16) - previous_reference.astype(np.int16)
                temporal_residual = float(
                    np.abs(current_delta - reference_delta).mean(dtype=np.float64)
                )
            rows.append(
                {
                    "scene": scene,
                    "frame": frame,
                    "mode_key": key,
                    "mode": label,
                    "rgb_mae_to_reference": rgb_mae(image, reference_rgb),
                    "rgb_psnr_to_reference_db": rgb_psnr(image, reference_rgb),
                    "luma_ssim_to_reference": (
                        luma_ssim(image, reference_rgb)
                        if frame % ssim_stride == 0
                        else float("nan")
                    ),
                    "edge_strength_ratio_to_reference": (
                        edge_strength(image) / reference_edge
                        if reference_edge > 1.0e-12
                        else float("nan")
                    ),
                    "temporal_delta_residual_to_reference": temporal_residual,
                }
            )
            previous[key] = image
        previous_reference = reference_rgb

    summary: dict[str, Any] = {
        "scene": scene,
        "profile": PROFILE,
        "classification": "formal" if expected == 480 else "engineering",
        "resolution": list(next(iter(resolutions))),
        "capture_root": str(capture),
        "reference_root": str(reference),
        "windows": {},
    }
    for window_key, label, start, end in WINDOWS:
        modes: dict[str, Any] = {}
        for key, mode_label, directory in MODES:
            selected = [
                row for row in rows
                if row["mode_key"] == key and start <= int(row["frame"]) < end
            ]
            modes[key] = {
                "mode": mode_label,
                "directory": directory,
                "frame_count": len(selected),
                "mean_rgb_mae_to_reference": mean(selected, "rgb_mae_to_reference"),
                "mean_rgb_psnr_to_reference_db": mean(selected, "rgb_psnr_to_reference_db"),
                "mean_luma_ssim_to_reference": mean(selected, "luma_ssim_to_reference"),
                "mean_edge_strength_ratio_to_reference": mean(
                    selected, "edge_strength_ratio_to_reference"
                ),
                "mean_temporal_delta_residual_to_reference": mean(
                    selected, "temporal_delta_residual_to_reference"
                ),
            }
        summary["windows"][window_key] = {
            "label": label,
            "range_half_open": [start, end],
            "modes": modes,
            "pattern_off_minus_standard_mae": (
                modes["pattern_off"]["mean_rgb_mae_to_reference"]
                - modes["standard"]["mean_rgb_mae_to_reference"]
            ),
            "document_minus_pattern_off_mae": (
                modes["document_full"]["mean_rgb_mae_to_reference"]
                - modes["pattern_off"]["mean_rgb_mae_to_reference"]
            ),
            "edge_minus_document_mae": (
                modes["edge"]["mean_rgb_mae_to_reference"]
                - modes["document_full"]["mean_rgb_mae_to_reference"]
            ),
        }

    scene_output = output / scene
    scene_output.mkdir(parents=True, exist_ok=True)
    visual_frames = [150, 240, 329, 410, 419, 420, 429, 439, 479]
    make_sheet(scene_output / "sample_pattern_reference_comparison.png", paths, visual_frames, False)
    make_sheet(scene_output / "sample_pattern_reference_difference_x4.png", paths, visual_frames, True)
    return rows, summary


def write_report(path: Path, summaries: dict[str, Any], bridges: list[dict[str, Any]]) -> None:
    lines = [
        "# SMAA Standard Temporal Sample-Pattern Isolation 결과",
        "",
        "## 비교 정의",
        "",
        "`O-T2X-R`과 `ABL-Standard-PatternOff-R`은 full-screen Standard resolve, bilinear history sampling,",
        "history weight 0.5, camera/depth reprojection과 history lifecycle을 동일하게 유지한다.",
        "바뀌는 축은 공식 SMAA T2X의 유효한 temporal subpixel pattern 전체다:",
        "projection jitter와 대응 subsample index를 함께 On/Off 한다.",
        "",
        "projection jitter만 끄고 T2X subsample index를 유지하는 조합은 공식 SMAA의 짝을 깨므로 만들지 않았다.",
        "이 진단군은 최종 8-case를 늘리지 않는다.",
        "",
        "## 입력 무결성",
        "",
        f"- Hash bridge: {len(bridges)} sequences, byte mismatch 0",
    ]
    for scene, summary in summaries.items():
        lines.append(
            f"- {scene}: {summary['resolution'][0]}×{summary['resolution'][1]}, 480 frames, `{PROFILE}`, formal"
        )
    lines.extend(
        [
            "",
            "## Spatial-reference 및 시간 변화 대용값",
            "",
            "| Scene | Window | Mode | RGB MAE↓ | PSNR↑ | SSIM↑ | Edge/Ref | Δ-residual↓ |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for scene, summary in summaries.items():
        for window_key in ("central_motion", "transition", "post_still"):
            window = summary["windows"][window_key]
            for key, mode_label, _ in MODES:
                mode = window["modes"][key]
                lines.append(
                    f"| {scene} | {window['label']} | {mode_label} | "
                    f"{mode['mean_rgb_mae_to_reference']:.6f} | "
                    f"{mode['mean_rgb_psnr_to_reference_db']:.4f} | "
                    f"{mode['mean_luma_ssim_to_reference']:.6f} | "
                    f"{mode['mean_edge_strength_ratio_to_reference']:.6f} | "
                    f"{mode['mean_temporal_delta_residual_to_reference']:.6f} |"
                )
    lines.extend(
        [
            "",
            "## 분리 비교",
            "",
            "양수 MAE 차이는 뒤쪽 방식의 spatial-reference 오차가 더 큼을 뜻한다.",
            "",
            "| Scene | Window | PatternOff − Standard | DocumentFull − PatternOff | Edge − DocumentFull |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for scene, summary in summaries.items():
        for window_key in ("central_motion", "transition", "post_still"):
            window = summary["windows"][window_key]
            lines.append(
                f"| {scene} | {window['label']} | "
                f"{window['pattern_off_minus_standard_mae']:+.6f} | "
                f"{window['document_minus_pattern_off_mae']:+.6f} | "
                f"{window['edge_minus_document_mae']:+.6f} |"
            )
    lines.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- supersample 입력은 동일 pose의 spatial-reference proxy이며 절대 temporal ground truth가 아니다.",
            "- 최종 판단은 공식 CGVQM-2 central-motion 및 motion→still transition 결과와 함께 내린다.",
            "- `Pattern-Off-R`은 원본 SMAA T2X가 아니라 샘플 패턴 원인을 분리하는 진단군이다.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    bridges: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_scene, raw_capture, raw_reference, raw_formal, raw_coverage in args.case:
        scene_key = raw_scene.lower()
        if scene_key not in {"bistro", "minecraft"} or scene_key in seen:
            raise RuntimeError(f"invalid or duplicate scene: {raw_scene}")
        seen.add(scene_key)
        scene = "Bistro" if scene_key == "bistro" else "Minecraft"
        capture = Path(raw_capture).resolve()
        reference = Path(raw_reference).resolve()
        formal = Path(raw_formal).resolve()
        coverage = Path(raw_coverage).resolve()
        bridges.extend(hash_bridge(scene, capture, formal, coverage, args.expected_frames))
        rows, summary = analyze_case(
            scene, capture, reference, args.expected_frames, args.ssim_stride, output
        )
        all_rows.extend(rows)
        summaries[scene] = summary
    if seen != {"bistro", "minecraft"}:
        raise RuntimeError("formal analysis requires Bistro and Minecraft")

    with (output / "standard_sample_pattern_per_frame.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    (output / "standard_sample_pattern_summary.json").write_text(
        json.dumps(
            {"classification": "formal", "hash_bridges": bridges, "scenes": summaries},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_report(output / "SMAA-Standard-Sample-Pattern-Results-ko.md", summaries, bridges)
    print(
        f"PASS: {len(all_rows)} frame-mode rows, {len(bridges)} hash bridges, output={output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
