#!/usr/bin/env python3
"""Analyze the matched-kernel motion-to-still temporal-coverage gate.

The key comparison is FullScreenDocument-R versus O-ET2X-R.  Both use the
same spatial input, no deliberate jitter, camera/depth reprojection,
Catmull-Rom history sampling, YCoCg clipping, history weight, and history
lifecycle; only temporal coverage/execution differs.  The supersample input
is a same-pose spatial-reference proxy, not absolute temporal ground truth.
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
    percentile,
    resized,
    rgb_mae,
    rgb_psnr,
)


PROFILE = "flythrough-wide-yaw-360"
REFERENCE_DIRECTORY = "SS_Reference"
MODES = (
    ("o_1x", "O-1X", "O_1X", "spatial control"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R", "standard full-screen T2X"),
    (
        "document_fullscreen_r",
        "ABL-Document-FullScreen-R",
        "ABL_Document_FullScreen_R",
        "matched document kernel, full-screen coverage",
    ),
    (
        "o_et2x_r",
        "O-ET2X-R",
        "O_ET2X_R",
        "matched document kernel, edge-selective coverage",
    ),
)
WINDOWS = (
    ("full", "전체", 0, 480),
    ("pre_still", "초기 정지", 0, 60),
    ("motion", "카메라 이동", 60, 420),
    ("central_motion", "중앙 이동", 150, 330),
    ("transition", "이동→정지", 410, 440),
    ("post_still_early", "정지 직후", 420, 435),
    ("post_still", "후기 정지", 420, 480),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        required=True,
        metavar=("SCENE", "CAPTURE_ROOT", "REFERENCE_ROOT"),
    )
    parser.add_argument("--expected-frames", type=int, default=480)
    parser.add_argument("--ssim-stride", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reuse-summary",
        action="store_true",
        help="Revalidate inputs and recompute plateau diagnostics without rerunning full-frame metrics.",
    )
    return parser.parse_args()


def read_report(root: Path) -> str:
    reports = list(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(f"{root}: expected one results CSV, found {len(reports)}")
    return reports[0].read_text(encoding="utf-8", errors="replace")


def validate_capture_report(root: Path, scene: str, expected_frames: int) -> None:
    text = read_report(root)
    required = [
        "SMAA motion-to-still temporal-coverage isolation capture",
        f"Scene:           {scene}",
        f"Camera profile:  {PROFILE}",
        f"Profile frames:  480 total; capture [0, {expected_frames - 1}]",
        "API/preset:      DirectX 11, SMAA Ultra",
        "Changed axis:    temporal coverage/execution only",
        "FullScreenDocument-R and O-ET2X-R keep no deliberate jitter",
        "Classification:  complete camera profile quality capture",
    ]
    for _, label, directory, _ in MODES:
        required.append(f"{label}, {directory}")
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(f"{root}: capture report missing {missing}")


def validate_reference_report(root: Path, scene: str, expected_frames: int) -> None:
    text = read_report(root)
    required = [
        "supersample spatial-reference capture",
        f"Scene:           {scene}",
        f"Camera profile:  {PROFILE}",
        f"Profile frames:  480 total; capture [0, {expected_frames - 1}]",
        "Reference:       2x linear resolution, 3x3 within-frame subpixel grid, 8x MSAA",
        "Temporal state:  none; supersample spatial-reference proxy",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(f"{root}: reference report missing {missing}")


def pixel_hash(path: Path) -> str:
    with Image.open(path) as image:
        payload = np.asarray(image.convert("RGB"), dtype=np.uint8).tobytes()
    return hashlib.sha256(payload).hexdigest()


def relative_delta(before: float, after: float) -> float:
    if not math.isfinite(before) or abs(before) <= 1.0e-12:
        return float("nan")
    return (after - before) / before * 100.0


def summarize(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "mean_rgb_mae_to_reference": finite_mean(
            [float(row["rgb_mae_to_reference"]) for row in rows]
        ),
        "p95_rgb_mae_to_reference": percentile(
            [float(row["rgb_mae_to_reference"]) for row in rows], 95.0
        ),
        "mean_rgb_psnr_to_reference_db": finite_mean(
            [float(row["rgb_psnr_to_reference_db"]) for row in rows]
        ),
        "mean_luma_ssim_to_reference": finite_mean(
            [float(row["luma_ssim_to_reference"]) for row in rows]
        ),
        "mean_edge_strength_ratio_to_reference": finite_mean(
            [float(row["edge_strength_ratio_to_reference"]) for row in rows]
        ),
        "mean_adjacent_rgb_mae": finite_mean(
            [float(row["adjacent_rgb_mae"]) for row in rows]
        ),
        "mean_temporal_delta_residual_to_reference": finite_mean(
            [float(row["temporal_delta_residual_to_reference"]) for row in rows]
        ),
    }


def plateau_recovery(paths: list[Path], post_start: int = 420) -> dict[str, Any]:
    plateau_indices = list(range(len(paths) - 10, len(paths)))
    plateau = np.zeros_like(load_rgb(paths[plateau_indices[0]]), dtype=np.float32)
    for index in plateau_indices:
        plateau += load_rgb(paths[index]).astype(np.float32) / float(len(plateau_indices))
    distances = [
        float(
            np.abs(load_rgb(paths[index]).astype(np.float32) - plateau).mean(
                dtype=np.float64
            )
        )
        for index in range(post_start, len(paths))
    ]
    plateau_values = [
        distances[index - post_start] for index in plateau_indices
    ]
    threshold = max(
        finite_mean(plateau_values) + 3.0 * float(np.std(plateau_values)),
        0.01,
    )
    recovery_frame: int | None = None
    stable_frames = 5
    for index in range(post_start, len(paths) - stable_frames + 1):
        if all(
            distances[offset - post_start] <= threshold
            for offset in range(index, index + stable_frames)
        ):
            recovery_frame = index
            break
    return {
        "plateau_frames": plateau_indices,
        "threshold": threshold,
        "stable_frames": stable_frames,
        "recovery_profile_frame": recovery_frame,
        "recovery_offset_from_post_still": (
            None if recovery_frame is None else recovery_frame - post_start
        ),
        "post_still_distance_to_plateau": distances,
    }


def make_sheet(
    output: Path,
    frames: list[int],
    paths: dict[str, list[Path]],
    differences: bool,
) -> None:
    selected = (("SS-Ref", "reference"),) + tuple(
        (label, key) for key, label, _, _ in MODES
    )
    tile_width = 300
    label_height = 26
    tile_height = resized(paths["reference"][0], tile_width).height
    canvas = Image.new(
        "RGB",
        (tile_width * len(selected), label_height + len(frames) * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, key) in enumerate(selected):
        suffix = " |x4 error|" if differences and key != "reference" else ""
        draw.text((column * tile_width + 5, 7), label + suffix, fill="black")
    y = label_height
    for frame in frames:
        for column, (_, key) in enumerate(selected):
            if differences and key != "reference":
                image = difference_image(paths[key][frame], paths["reference"][frame], tile_width)
            else:
                image = resized(paths[key][frame], tile_width)
            canvas.paste(image, (column * tile_width, y))
        draw.text((5, y + tile_height + 6), f"profile frame {frame:05d}", fill="black")
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def analyze_case(
    scene: str,
    capture_root: Path,
    reference_root: Path,
    output_root: Path,
    expected_frames: int,
    ssim_stride: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    capture_root = capture_root.resolve()
    reference_root = reference_root.resolve()
    validate_capture_report(capture_root, scene, expected_frames)
    validate_reference_report(reference_root, scene, expected_frames)

    paths: dict[str, list[Path]] = {}
    resolutions: set[tuple[int, int]] = set()
    for key, _, directory, _ in MODES:
        frames, resolution = collect_frames(capture_root / directory, expected_frames, 0)
        paths[key] = frames
        resolutions.add(resolution)
    references, resolution = collect_frames(
        reference_root / REFERENCE_DIRECTORY, expected_frames, 0
    )
    paths["reference"] = references
    resolutions.add(resolution)
    if len(resolutions) != 1:
        raise RuntimeError(f"{scene}: sequence resolutions differ: {resolutions}")

    rows: list[dict[str, Any]] = []
    by_mode: dict[str, list[dict[str, Any]]] = {mode[0]: [] for mode in MODES}
    previous: dict[str, np.ndarray] = {}
    previous_reference: np.ndarray | None = None
    for frame in range(expected_frames):
        if frame % 60 == 0:
            print(f"[{scene}] frame {frame}/{expected_frames}", flush=True)
        reference = load_rgb(references[frame])
        reference_edge = edge_strength(reference)
        for key, label, _, description in MODES:
            image = load_rgb(paths[key][frame])
            adjacent = float("nan")
            delta_residual = float("nan")
            if key in previous and previous_reference is not None:
                adjacent = rgb_mae(image, previous[key])
                image_delta = image.astype(np.int16) - previous[key].astype(np.int16)
                reference_delta = (
                    reference.astype(np.int16) - previous_reference.astype(np.int16)
                )
                delta_residual = float(
                    np.abs(image_delta - reference_delta).mean(
                        dtype=np.float64
                    )
                )
            row = {
                "scene": scene,
                "profile": PROFILE,
                "frame": frame,
                "mode_key": key,
                "mode": label,
                "description": description,
                "rgb_mae_to_reference": rgb_mae(image, reference),
                "rgb_psnr_to_reference_db": rgb_psnr(image, reference),
                "luma_ssim_to_reference": (
                    luma_ssim(image, reference) if frame % ssim_stride == 0 else float("nan")
                ),
                "edge_strength_ratio_to_reference": (
                    edge_strength(image) / reference_edge
                    if reference_edge > 1.0e-12
                    else float("nan")
                ),
                "adjacent_rgb_mae": adjacent,
                "temporal_delta_residual_to_reference": delta_residual,
            }
            rows.append(row)
            by_mode[key].append(row)
            previous[key] = image
        previous_reference = reference

    windows: dict[str, Any] = {}
    for window_key, label, start, end in WINDOWS:
        if start >= expected_frames:
            continue
        bounded_end = min(end, expected_frames)
        modes: dict[str, Any] = {}
        for key, mode_label, directory, description in MODES:
            selected = [
                row for row in by_mode[key]
                if start <= int(row["frame"]) < bounded_end
            ]
            modes[key] = {
                "mode": mode_label,
                "directory": directory,
                "description": description,
                "frame_count": len(selected),
                **summarize(selected),
            }
        full = modes["document_fullscreen_r"]
        edge = modes["o_et2x_r"]
        windows[window_key] = {
            "label": label,
            "range_half_open": [start, bounded_end],
            "modes": modes,
            "coverage_effect_edge_vs_fullscreen_percent": {
                "rgb_mae_to_reference": relative_delta(
                    full["mean_rgb_mae_to_reference"], edge["mean_rgb_mae_to_reference"]
                ),
                "adjacent_rgb_mae": relative_delta(
                    full["mean_adjacent_rgb_mae"], edge["mean_adjacent_rgb_mae"]
                ),
                "temporal_delta_residual_to_reference": relative_delta(
                    full["mean_temporal_delta_residual_to_reference"],
                    edge["mean_temporal_delta_residual_to_reference"],
                ),
            },
        }

    plateau = {key: plateau_recovery(paths[key]) for key, *_ in MODES}
    visual_frames = [150, 240, 329, 410, 415, 419, 420, 421, 424, 429, 434, 449, 479]
    visual_frames = [frame for frame in visual_frames if frame < expected_frames]
    scene_output = output_root / scene
    scene_output.mkdir(parents=True, exist_ok=True)
    make_sheet(scene_output / "coverage_reference_comparison.png", visual_frames, paths, False)
    make_sheet(scene_output / "coverage_reference_difference_x4.png", visual_frames, paths, True)

    return rows, {
        "scene": scene,
        "profile": PROFILE,
        "classification": "formal" if expected_frames == 480 else "engineering",
        "capture_root": str(capture_root),
        "reference_root": str(reference_root),
        "resolution": list(next(iter(resolutions))),
        "frame_count": expected_frames,
        "o_1x_post_still_hashes": len(
            {pixel_hash(path) for path in paths["o_1x"][420:]}
        ),
        "windows": windows,
        "plateau_recovery": plateau,
        "visual_frames": visual_frames,
    }


def f(value: float, digits: int = 3) -> str:
    return "n/a" if not math.isfinite(value) else f"{value:.{digits}f}"


def write_report(path: Path, summaries: dict[str, Any]) -> None:
    lines = [
        "# SMAA Motion→Still Temporal Coverage Isolation 결과",
        "",
        "## 1. 비교 목적",
        "",
        "`ABL-Document-FullScreen-R`과 `O-ET2X-R`은 SMAA 1X spatial input, deliberate jitter Off,",
        "camera/depth reprojection, Catmull-Rom 5-tap, YCoCg clipping, history weight 0.8과 history lifecycle을",
        "동일하게 유지한다. 바뀌는 축은 temporal coverage/execution(full-screen 대 integrated first-pass edge candidate)뿐이다.",
        "따라서 이 pair가 motion→still 손실의 coverage 원인을 분리하는 핵심 비교다.",
        "",
        "`O-T2X-R`은 Standard control이지만 jitter, sampler, clipping, weight가 동시에 다르므로 coverage-only 비교로 사용하지 않는다.",
        "",
        "## 2. 입력 무결성",
        "",
    ]
    for scene, summary in summaries.items():
        lines.append(
            f"- {scene}: {summary['resolution'][0]}×{summary['resolution'][1]}, "
            f"{summary['frame_count']} frames, `{summary['profile']}`, `{summary['classification']}`"
        )
    lines.extend([
        "",
        "## 3. 구간별 spatial-reference 결과",
        "",
        "| Scene | Window | Mode | RGB MAE↓ | PSNR↑ | SSIM↑ | Edge/Ref | Δ-residual↓ |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ])
    for scene, summary in summaries.items():
        for window_key in ("central_motion", "transition", "post_still_early", "post_still"):
            window = summary["windows"][window_key]
            for key, label, _, _ in MODES:
                mode = window["modes"][key]
                lines.append(
                    f"| {scene} | {window['label']} | {label} | "
                    f"{mode['mean_rgb_mae_to_reference']:.6f} | "
                    f"{mode['mean_rgb_psnr_to_reference_db']:.4f} | "
                    f"{mode['mean_luma_ssim_to_reference']:.7f} | "
                    f"{mode['mean_edge_strength_ratio_to_reference']:.6f} | "
                    f"{mode['mean_temporal_delta_residual_to_reference']:.6f} |"
                )
    lines.extend([
        "",
        "## 4. Coverage-only 효과: Edge-selective 대 FullScreenDocument-R",
        "",
        "양수 값은 edge-selective에서 해당 오차/변화가 증가했다는 뜻이다.",
        "",
        "| Scene | Window | Ref MAE Δ | Adjacent Δ | Δ-residual Δ |",
        "|---|---|---:|---:|---:|",
    ])
    for scene, summary in summaries.items():
        for window_key in ("central_motion", "transition", "post_still_early", "post_still"):
            window = summary["windows"][window_key]
            effect = window["coverage_effect_edge_vs_fullscreen_percent"]
            lines.append(
                f"| {scene} | {window['label']} | "
                f"{f(effect['rgb_mae_to_reference'])}% | "
                f"{f(effect['adjacent_rgb_mae'])}% | "
                f"{f(effect['temporal_delta_residual_to_reference'])}% |"
            )
    lines.extend([
        "",
        "## 5. 정지 plateau 진입 진단",
        "",
        "마지막 10 frame의 평균 출력과의 거리가 plateau 내부 평균+3σ(최소 0.01 RGB code value) 이하로 5 frame 연속 들어오는 최초 시점이다.",
        "이는 절대 ghost trail 길이가 아니라 필터 상태 수렴 진단이다.",
        "",
        "| Scene | Mode | Post-still recovery offset |",
        "|---|---|---:|",
    ])
    for scene, summary in summaries.items():
        for key, label, _, _ in MODES:
            value = summary["plateau_recovery"][key]["recovery_offset_from_post_still"]
            lines.append(f"| {scene} | {label} | {value if value is not None else 'not reached'} |")

    lines.extend([
        "",
        "## 6. 판정 규칙",
        "",
        "- FullScreenDocument-R이 O-ET2X-R보다 post-still reference/temporal 지표를 개선하면 restricted coverage가 손실 원인이라는 가설을 지지한다.",
        "- 동시에 central-motion이 악화되면 full-screen history는 정지 품질을 회복하지만 움직임 중 오정렬을 다시 늘리는 trade-off다.",
        "- FullScreenDocument-R도 Standard T2X-R에 미치지 못하면 남은 차이는 coverage만이 아니라 jitter/sample diversity 또는 Standard kernel 차이도 포함한다.",
        "- Supersample 입력은 spatial-reference proxy다. 최종 판정에는 formal CGVQM과 연속 영상, 성능 결과를 함께 사용한다.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.expected_frames <= 0 or args.ssim_stride <= 0:
        raise ValueError("expected frames and SSIM stride must be positive")
    cases: dict[str, tuple[Path, Path]] = {}
    for raw_scene, raw_capture, raw_reference in args.case:
        scene = raw_scene.lower()
        if scene not in ("bistro", "minecraft"):
            raise ValueError(f"unsupported scene: {scene}")
        if scene in cases:
            raise ValueError(f"duplicate scene: {scene}")
        cases[scene] = (Path(raw_capture), Path(raw_reference))

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "motion_to_still_coverage_summary.json"
    report_path = output / "SMAA-Motion-To-Still-Coverage-Analysis-ko.md"
    if args.reuse_summary:
        if not json_path.is_file():
            raise RuntimeError(f"reuse summary does not exist: {json_path}")
        summaries = json.loads(json_path.read_text(encoding="utf-8"))
        if set(summaries) != set(cases):
            raise RuntimeError(
                f"reuse scenes {sorted(summaries)} do not match requested {sorted(cases)}"
            )
        for scene, (capture, reference) in cases.items():
            capture = capture.resolve()
            reference = reference.resolve()
            summary = summaries[scene]
            if (
                Path(summary["capture_root"]).resolve() != capture
                or Path(summary["reference_root"]).resolve() != reference
                or int(summary["frame_count"]) != args.expected_frames
            ):
                raise RuntimeError(f"{scene}: reuse provenance does not match request")
            validate_capture_report(capture, scene, args.expected_frames)
            validate_reference_report(reference, scene, args.expected_frames)
            mode_paths: dict[str, list[Path]] = {}
            resolutions: set[tuple[int, int]] = set()
            for key, _, directory, _ in MODES:
                frames, resolution = collect_frames(
                    capture / directory, args.expected_frames, 0
                )
                mode_paths[key] = frames
                resolutions.add(resolution)
            if len(resolutions) != 1 or list(next(iter(resolutions))) != summary["resolution"]:
                raise RuntimeError(f"{scene}: reuse resolution mismatch")
            summary["plateau_recovery"] = {
                key: plateau_recovery(mode_paths[key]) for key, *_ in MODES
            }
            summary["o_1x_post_still_hashes"] = len(
                {pixel_hash(path) for path in mode_paths["o_1x"][420:]}
            )
        json_path.write_text(
            json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_report(report_path, summaries)
        print(f"JSON={json_path}")
        print(f"REPORT={report_path}")
        print(
            f"VALIDATION=PASS reuse-summary scenes={len(summaries)} "
            f"modes={len(MODES)} frames={args.expected_frames}"
        )
        return 0

    all_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for scene, (capture, reference) in cases.items():
        rows, summary = analyze_case(
            scene, capture, reference, output, args.expected_frames, args.ssim_stride
        )
        all_rows.extend(rows)
        summaries[scene] = summary

    csv_path = output / "motion_to_still_coverage_per_frame.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    json_path.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(report_path, summaries)
    print(f"CSV={csv_path}")
    print(f"JSON={json_path}")
    print(f"REPORT={report_path}")
    print(
        f"VALIDATION=PASS scenes={len(summaries)} modes={len(MODES)} "
        f"frames={args.expected_frames}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
