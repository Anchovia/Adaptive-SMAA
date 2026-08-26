#!/usr/bin/env python3
"""Analyze the wide smooth-camera three-way capture against SS-Reference.

The supersample sequence is a within-frame spatial-reference proxy.  It does
not contain temporal history and is therefore used together with, rather than
as a replacement for, temporal evidence such as CGVQM and sequence inspection.
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

PROFILE = "flythrough-wide-yaw-360"
REFERENCE = ("ss_reference", "SS-Reference", "SS_Reference")
MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R"),
    ("o_et2x_r", "O-ET2X-R", "O_ET2X_R"),
)
FRAME_PATTERN = re.compile(
    r"_profile_(\d+)_frame_(\d+)$", re.IGNORECASE
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Bistro/Minecraft wide smooth-camera O-1X, O-T2X-R, "
            "and O-ET2X-R captures with the same-pose SS-Reference."
        )
    )
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        required=True,
        metavar=("SCENE", "COMPARISON_ROOT", "REFERENCE_ROOT"),
    )
    parser.add_argument("--expected-frames", type=int, required=True)
    parser.add_argument("--first-profile-frame", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--baseline-o1x",
        nargs=2,
        action="append",
        default=[],
        metavar=("SCENE", "O1X_DIRECTORY"),
        help="Optional prior visible-window O-1X sequence for SHA-256 regression.",
    )
    parser.add_argument(
        "--ssim-stride",
        type=int,
        default=1,
        help="Evaluate SSIM every N frames; MAE and PSNR always use every frame.",
    )
    return parser.parse_args()


def parse_frame_indices(path: Path) -> tuple[int, int]:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise RuntimeError(f"Invalid camera-motion PNG name: {path.name}")
    return int(match.group(1)), int(match.group(2))


def collect_frames(
    directory: Path,
    expected_frames: int,
    first_profile_frame: int,
) -> tuple[list[Path], tuple[int, int]]:
    frames = sorted(
        directory.glob("*.png"), key=lambda path: parse_frame_indices(path)[1]
    )
    if len(frames) != expected_frames:
        raise RuntimeError(
            f"{directory}: expected {expected_frames} PNGs, found {len(frames)}"
        )
    profile_indices = [parse_frame_indices(path)[0] for path in frames]
    capture_indices = [parse_frame_indices(path)[1] for path in frames]
    if capture_indices != list(range(expected_frames)):
        raise RuntimeError(f"{directory}: non-contiguous capture indices")
    if profile_indices != list(
        range(first_profile_frame, first_profile_frame + expected_frames)
    ):
        raise RuntimeError(f"{directory}: profile indices do not match the request")
    with Image.open(frames[0]) as image:
        resolution = image.size
    for path in frames[1:]:
        with Image.open(path) as image:
            if image.size != resolution:
                raise RuntimeError(
                    f"{path}: resolution {image.size} != {resolution}"
                )
    return frames, resolution


def read_report(root: Path) -> str:
    reports = list(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(f"{root}: expected one results CSV, found {len(reports)}")
    return reports[0].read_text(encoding="utf-8", errors="replace")


def validate_report(
    root: Path,
    scene: str,
    first_profile_frame: int,
    expected_frames: int,
    reference: bool,
) -> dict[str, Any]:
    text = read_report(root)
    expected_end = first_profile_frame + expected_frames - 1
    required = (
        f"Scene:           {scene}",
        f"Camera profile:  {PROFILE}",
        f"capture [{first_profile_frame}, {expected_end}]",
        "API/preset:      DirectX 11, SMAA Ultra",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"{root}: report is missing '{token}'")
    expected_title = (
        "supersample spatial-reference capture"
        if reference
        else "focused three-way quality capture"
    )
    if expected_title not in text:
        raise RuntimeError(f"{root}: unexpected capture type")
    classification = (
        "formal" if first_profile_frame == 0 and expected_frames == 480
        else "engineering"
    )
    output: dict[str, Any] = {
        "root": str(root.resolve()),
        "scene": scene,
        "camera_profile": PROFILE,
        "first_profile_frame": first_profile_frame,
        "last_profile_frame": expected_end,
        "frame_count": expected_frames,
        "classification": classification,
    }
    if reference:
        match = re.search(
            r"Reference:\s+(\d+)x linear resolution, "
            r"(\d+)x(\d+) within-frame subpixel grid, (\d+)x MSAA",
            text,
        )
        if match is None:
            raise RuntimeError(f"{root}: missing supersample provenance")
        output["reference"] = {
            "linear_resolution_scale": int(match.group(1)),
            "subpixel_grid": [int(match.group(2)), int(match.group(3))],
            "msaa_samples": int(match.group(4)),
            "temporal_history": False,
            "classification": "supersample_spatial_reference_proxy",
        }
    return output


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def luma(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.float32)
    return (
        values[..., 0] * 0.2126
        + values[..., 1] * 0.7152
        + values[..., 2] * 0.0722
    )


def rgb_mae(test: np.ndarray, reference: np.ndarray) -> float:
    return float(
        np.abs(test.astype(np.int16) - reference.astype(np.int16)).mean(
            dtype=np.float64
        )
    )


def rgb_psnr(test: np.ndarray, reference: np.ndarray) -> float:
    difference = test.astype(np.float64) - reference.astype(np.float64)
    mse = float(np.square(difference).mean(dtype=np.float64))
    return float("inf") if mse == 0.0 else 20.0 * math.log10(255.0 / math.sqrt(mse))


def luma_ssim(test: np.ndarray, reference: np.ndarray) -> float:
    test_luma = luma(test)
    reference_luma = luma(reference)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    mean_test = gaussian_blur(test_luma)
    mean_reference = gaussian_blur(reference_luma)
    variance_test = gaussian_blur(test_luma * test_luma) - mean_test * mean_test
    variance_reference = (
        gaussian_blur(reference_luma * reference_luma)
        - mean_reference * mean_reference
    )
    covariance = (
        gaussian_blur(test_luma * reference_luma)
        - mean_test * mean_reference
    )
    numerator = (2.0 * mean_test * mean_reference + c1) * (2.0 * covariance + c2)
    denominator = (
        (mean_test * mean_test + mean_reference * mean_reference + c1)
        * (variance_test + variance_reference + c2)
    )
    values = numerator / np.maximum(denominator, 1.0e-12)
    if values.shape[0] > 10 and values.shape[1] > 10:
        values = values[5:-5, 5:-5]
    return float(values.mean(dtype=np.float64))


def gaussian_blur(values: np.ndarray) -> np.ndarray:
    coordinates = np.arange(-5, 6, dtype=np.float32)
    kernel = np.exp(-(coordinates * coordinates) / (2.0 * 1.5 * 1.5))
    kernel /= kernel.sum(dtype=np.float64)
    horizontal_source = np.pad(values, ((0, 0), (5, 5)), mode="reflect")
    horizontal = np.zeros_like(values, dtype=np.float32)
    for offset, weight in enumerate(kernel):
        horizontal += horizontal_source[:, offset : offset + values.shape[1]] * weight
    vertical_source = np.pad(horizontal, ((5, 5), (0, 0)), mode="reflect")
    result = np.zeros_like(values, dtype=np.float32)
    for offset, weight in enumerate(kernel):
        result += vertical_source[offset : offset + values.shape[0], :] * weight
    return result


def edge_strength(rgb: np.ndarray) -> float:
    values = luma(rgb)
    padded = np.pad(values, ((1, 1), (1, 1)), mode="reflect")
    top_left = padded[:-2, :-2]
    top = padded[:-2, 1:-1]
    top_right = padded[:-2, 2:]
    left = padded[1:-1, :-2]
    right = padded[1:-1, 2:]
    bottom_left = padded[2:, :-2]
    bottom = padded[2:, 1:-1]
    bottom_right = padded[2:, 2:]
    gx = (
        -top_left + top_right - 2.0 * left + 2.0 * right
        - bottom_left + bottom_right
    )
    gy = (
        -top_left - 2.0 * top - top_right
        + bottom_left + 2.0 * bottom + bottom_right
    )
    return float(np.hypot(gx, gy).mean(dtype=np.float64))


def finite_mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.mean(finite, dtype=np.float64)) if finite else float("nan")


def percentile(values: list[float], value: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), value))


def resized(path: Path, width: int) -> Image.Image:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        height = max(1, round(rgb.height * width / rgb.width))
        return rgb.resize((width, height), Image.Resampling.LANCZOS)


def difference_image(test: Path, reference: Path, width: int) -> Image.Image:
    delta = np.abs(
        load_rgb(test).astype(np.int16) - load_rgb(reference).astype(np.int16)
    )
    amplified = np.clip(delta * 4, 0, 255).astype(np.uint8)
    image = Image.fromarray(amplified, "RGB")
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def make_sheet(
    output: Path,
    frame_indices: list[int],
    paths: dict[str, list[Path]],
    differences: bool,
) -> None:
    tile_width = 300 if not differences else 260
    label_height = 26
    reference_paths = paths[REFERENCE[0]]
    if differences:
        columns = [
            ("SS-Reference", REFERENCE[0], False),
            ("|O-1X - Ref| x4", "o_1x", True),
            ("|O-T2X-R - Ref| x4", "o_t2x_r", True),
            ("|O-ET2X-R - Ref| x4", "o_et2x_r", True),
        ]
    else:
        columns = [
            ("SS-Reference", REFERENCE[0], False),
            ("O-1X", "o_1x", False),
            ("O-T2X-R", "o_t2x_r", False),
            ("O-ET2X-R", "o_et2x_r", False),
        ]
    tile_height = resized(reference_paths[0], tile_width).height
    canvas = Image.new(
        "RGB",
        (
            tile_width * len(columns),
            label_height + len(frame_indices) * (tile_height + label_height),
        ),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, _, _) in enumerate(columns):
        draw.text((column * tile_width + 6, 7), label, fill="black")
    y = label_height
    for frame in frame_indices:
        for column, (_, key, is_difference) in enumerate(columns):
            image = (
                difference_image(paths[key][frame], reference_paths[frame], tile_width)
                if is_difference
                else resized(paths[key][frame], tile_width)
            )
            canvas.paste(image, (column * tile_width, y))
        profile_index = parse_frame_indices(reference_paths[frame])[0]
        draw.text(
            (6, y + tile_height + 6),
            f"capture {frame:05d} / profile {profile_index:05d}",
            fill="black",
        )
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def default_visual_frames(expected_frames: int) -> list[int]:
    if expected_frames >= 480:
        return [0, 59, 60, 150, 240, 330, 419, 420, 479]
    if expected_frames <= 9:
        return list(range(expected_frames))
    return sorted({0, expected_frames // 4, expected_frames // 2, expected_frames - 1})


def analyze_case(
    scene: str,
    comparison_root: Path,
    reference_root: Path,
    output: Path,
    expected_frames: int,
    first_profile_frame: int,
    ssim_stride: int,
    baseline_o1x: Path | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    comparison_root = comparison_root.resolve()
    reference_root = reference_root.resolve()
    provenance = {
        "comparison": validate_report(
            comparison_root, scene, first_profile_frame, expected_frames, False
        ),
        "reference": validate_report(
            reference_root, scene, first_profile_frame, expected_frames, True
        ),
    }
    paths: dict[str, list[Path]] = {}
    resolutions: set[tuple[int, int]] = set()
    for key, _, directory in MODES:
        frames, resolution = collect_frames(
            comparison_root / directory, expected_frames, first_profile_frame
        )
        paths[key] = frames
        resolutions.add(resolution)
    reference_frames, reference_resolution = collect_frames(
        reference_root / REFERENCE[2], expected_frames, first_profile_frame
    )
    paths[REFERENCE[0]] = reference_frames
    resolutions.add(reference_resolution)
    if len(resolutions) != 1:
        raise RuntimeError(f"{scene}: sequence resolutions differ: {resolutions}")

    rows: list[dict[str, Any]] = []
    by_mode: dict[str, list[dict[str, Any]]] = {key: [] for key, _, _ in MODES}
    for frame in range(expected_frames):
        reference_rgb = load_rgb(reference_frames[frame])
        reference_edge = edge_strength(reference_rgb)
        for key, label, _ in MODES:
            test_rgb = load_rgb(paths[key][frame])
            row = {
                "scene": scene,
                "camera_profile": PROFILE,
                "capture_frame": frame,
                "profile_frame": first_profile_frame + frame,
                "mode_key": key,
                "mode": label,
                "rgb_mae_to_reference": rgb_mae(test_rgb, reference_rgb),
                "rgb_psnr_to_reference_db": rgb_psnr(test_rgb, reference_rgb),
                "luma_ssim_to_reference": (
                    luma_ssim(test_rgb, reference_rgb)
                    if frame % ssim_stride == 0
                    else float("nan")
                ),
                "edge_strength": edge_strength(test_rgb),
                "reference_edge_strength": reference_edge,
            }
            row["edge_strength_ratio_to_reference"] = (
                row["edge_strength"] / reference_edge
                if reference_edge > 1.0e-12
                else float("nan")
            )
            rows.append(row)
            by_mode[key].append(row)

    summaries: dict[str, dict[str, Any]] = {}
    for key, label, directory in MODES:
        mode_rows = by_mode[key]
        maes = [float(row["rgb_mae_to_reference"]) for row in mode_rows]
        summaries[key] = {
            "mode": label,
            "directory": directory,
            "frame_count": len(mode_rows),
            "mean_rgb_mae_to_reference": finite_mean(maes),
            "median_rgb_mae_to_reference": percentile(maes, 50),
            "p95_rgb_mae_to_reference": percentile(maes, 95),
            "mean_rgb_psnr_to_reference_db": finite_mean(
                [float(row["rgb_psnr_to_reference_db"]) for row in mode_rows]
            ),
            "mean_luma_ssim_to_reference": finite_mean(
                [float(row["luma_ssim_to_reference"]) for row in mode_rows]
            ),
            "mean_edge_strength_ratio_to_reference": finite_mean(
                [float(row["edge_strength_ratio_to_reference"]) for row in mode_rows]
            ),
        }
    control_mae = summaries["o_1x"]["mean_rgb_mae_to_reference"]
    for key in ("o_t2x_r", "o_et2x_r"):
        current = summaries[key]["mean_rgb_mae_to_reference"]
        summaries[key]["mae_improvement_vs_o_1x_percent"] = (
            (control_mae - current) / control_mae * 100.0
            if control_mae > 1.0e-12
            else float("nan")
        )
    standard_mae = summaries["o_t2x_r"]["mean_rgb_mae_to_reference"]
    edge_selective_mae = summaries["o_et2x_r"]["mean_rgb_mae_to_reference"]
    et_vs_standard = (
        (edge_selective_mae - standard_mae) / standard_mae * 100.0
        if standard_mae > 1.0e-12
        else float("nan")
    )

    baseline_validation: dict[str, Any] | None = None
    if baseline_o1x is not None:
        baseline_frames, baseline_resolution = collect_frames(
            baseline_o1x.resolve(), expected_frames, first_profile_frame
        )
        if baseline_resolution != next(iter(resolutions)):
            raise RuntimeError(
                f"{scene}: baseline O-1X resolution {baseline_resolution} differs"
            )
        mismatches = sum(
            sha256(current) != sha256(baseline)
            for current, baseline in zip(paths["o_1x"], baseline_frames)
        )
        baseline_validation = {
            "directory": str(baseline_o1x.resolve()),
            "frame_count": expected_frames,
            "sha256_mismatches": mismatches,
            "result": "PASS" if mismatches == 0 else "FAIL",
        }
        if mismatches != 0:
            raise RuntimeError(
                f"{scene}: O-1X regression has {mismatches} SHA-256 mismatches"
            )

    scene_output = output / scene
    scene_output.mkdir(parents=True, exist_ok=True)
    visual_frames = default_visual_frames(expected_frames)
    make_sheet(scene_output / "reference_comparison_sheet.png", visual_frames, paths, False)
    make_sheet(scene_output / "reference_difference_x4_sheet.png", visual_frames, paths, True)
    summary = {
        "scene": scene,
        "camera_profile": PROFILE,
        "classification": provenance["comparison"]["classification"],
        "resolution": list(next(iter(resolutions))),
        "first_profile_frame": first_profile_frame,
        "last_profile_frame": first_profile_frame + expected_frames - 1,
        "frame_count": expected_frames,
        "ssim_stride": ssim_stride,
        "provenance": provenance,
        "modes": summaries,
        "o_et2x_r_mae_delta_vs_o_t2x_r_percent": et_vs_standard,
        "visual_frames": visual_frames,
        "baseline_o1x_regression": baseline_validation,
    }
    return rows, summary


def write_markdown(output: Path, summaries: dict[str, Any]) -> None:
    lines = [
        "# Wide smooth-camera supersample reference 분석",
        "",
        "`flythrough-wide-yaw-360`의 동일 pose에서 O-1X, O-T2X-R,",
        "O-ET2X-R을 CMAA2 supersample spatial-reference proxy와 비교한다.",
        "Reference는 temporal ground truth가 아니므로 CGVQM/error-map 및 연속 영상과",
        "함께 해석해야 한다.",
        "",
        "| Scene | Mode | Mean RGB MAE | PSNR dB | Luma SSIM | Edge/Ref | MAE improvement vs O-1X |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for scene, summary in summaries.items():
        for key, label, _ in MODES:
            mode = summary["modes"][key]
            improvement = mode.get("mae_improvement_vs_o_1x_percent")
            improvement_text = "control" if improvement is None else f"{improvement:+.3f}%"
            lines.append(
                f"| {scene} | {label} | {mode['mean_rgb_mae_to_reference']:.6f} | "
                f"{mode['mean_rgb_psnr_to_reference_db']:.4f} | "
                f"{mode['mean_luma_ssim_to_reference']:.7f} | "
                f"{mode['mean_edge_strength_ratio_to_reference']:.6f} | "
                f"{improvement_text} |"
            )
    lines.extend(["", "## 무결성", ""])
    for scene, summary in summaries.items():
        regression = summary["baseline_o1x_regression"]
        if regression is not None:
            lines.append(
                f"- {scene}: prior visible-window O-1X 대비 SHA-256 mismatch "
                f"{regression['sha256_mismatches']}/{regression['frame_count']} "
                f"=> {regression['result']}"
            )
    lines.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- RGB MAE가 낮다는 것은 이 spatial-reference proxy에 더 가깝다는 뜻이다.",
            "- 단일 지표만으로 ghosting 감소나 temporal supersampling 유지를 확정하지 않는다.",
            "- 전체-frame 분석과 별도로 사전 고정한 구간의 CGVQM-2/error-map을 기록한다.",
            "- PNG 품질 캡처는 성능 측정으로 사용하지 않는다.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.expected_frames <= 0 or args.first_profile_frame < 0:
        raise ValueError("expected-frames must be positive and first-profile-frame non-negative")
    if args.ssim_stride <= 0:
        raise ValueError("ssim-stride must be positive")
    cases: dict[str, tuple[Path, Path]] = {}
    for raw_scene, raw_comparison, raw_reference in args.case:
        scene = raw_scene.lower()
        if scene not in ("bistro", "minecraft"):
            raise ValueError(f"Unsupported scene: {raw_scene}")
        if scene in cases:
            raise ValueError(f"Duplicate scene: {scene}")
        cases[scene] = (Path(raw_comparison), Path(raw_reference))
    baselines: dict[str, Path] = {}
    for raw_scene, raw_directory in args.baseline_o1x:
        scene = raw_scene.lower()
        if scene in baselines:
            raise ValueError(f"Duplicate O-1X baseline scene: {scene}")
        baselines[scene] = Path(raw_directory)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for scene, (comparison, reference) in cases.items():
        rows, summary = analyze_case(
            scene,
            comparison,
            reference,
            output,
            args.expected_frames,
            args.first_profile_frame,
            args.ssim_stride,
            baselines.get(scene),
        )
        all_rows.extend(rows)
        summaries[scene] = summary

    csv_path = output / "wide_camera_reference_per_frame.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    json_path = output / "wide_camera_reference_summary.json"
    json_path.write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report_path = output / "SMAA-Wide-Camera-Reference-Analysis-ko.md"
    write_markdown(report_path, summaries)
    print(f"CSV={csv_path}")
    print(f"JSON={json_path}")
    print(f"REPORT={report_path}")
    print(
        f"VALIDATION=PASS scenes={len(summaries)} frames={args.expected_frames} "
        f"profile={PROFILE}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
