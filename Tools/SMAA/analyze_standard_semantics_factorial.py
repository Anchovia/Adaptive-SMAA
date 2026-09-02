#!/usr/bin/env python3
"""Analyze the Standard-semantics compute-mirror 2x2x2 factorial gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
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
    parse_frame_indices,
    resized,
    rgb_mae,
    rgb_psnr,
)


PROFILE = "flythrough-wide-yaw-360"
FACTORS = (
    ("point", "adaptive", "spatial"),
    ("point", "adaptive", "resolved"),
    ("point", "fixed", "spatial"),
    ("point", "fixed", "resolved"),
    ("bilinear", "adaptive", "spatial"),
    ("bilinear", "adaptive", "resolved"),
    ("bilinear", "fixed", "spatial"),
    ("bilinear", "fixed", "resolved"),
)


def cell_key(pattern: str, sampler: str, weight: str, feedback: str) -> str:
    return f"{pattern}_{sampler}_{weight}_{feedback}"


def cell_directory(pattern: str, sampler: str, weight: str, feedback: str) -> str:
    return (
        f"ABL_FS_{sampler.title()}_{weight.title()}_{feedback.title()}_"
        f"Pattern{pattern.title()}_R"
    )


MODES: list[dict[str, str]] = [
    {
        "key": "official_on",
        "label": "Official Standard On",
        "directory": "O_T2X_R",
        "pattern": "on",
        "sampler": "official",
        "weight": "official",
        "feedback": "official",
    },
    {
        "key": "official_off",
        "label": "Official Standard Off",
        "directory": "ABL_Standard_PatternOff_R",
        "pattern": "off",
        "sampler": "official",
        "weight": "official",
        "feedback": "official",
    },
]
for pattern_name in ("on", "off"):
    for sampler_name, weight_name, feedback_name in FACTORS:
        MODES.append(
            {
                "key": cell_key(
                    pattern_name, sampler_name, weight_name, feedback_name
                ),
                "label": (
                    f"{sampler_name.title()} / {weight_name.title()} / "
                    f"{feedback_name.title()} / Pattern {pattern_name.title()}"
                ),
                "directory": cell_directory(
                    pattern_name, sampler_name, weight_name, feedback_name
                ),
                "pattern": pattern_name,
                "sampler": sampler_name,
                "weight": weight_name,
                "feedback": feedback_name,
            }
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        nargs=4,
        action="append",
        required=True,
        metavar=("SCENE", "CAPTURE", "REFERENCE", "PRIOR_CONTROL_CAPTURE"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-frames", type=int, default=480)
    parser.add_argument("--first-profile-frame", type=int, default=0)
    parser.add_argument(
        "--classification",
        choices=("engineering", "formal-window", "formal-full"),
        default="engineering",
    )
    parser.add_argument("--ssim-stride", type=int, default=4)
    return parser.parse_args()


def report_text(root: Path) -> str:
    reports = list(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(f"{root}: expected one results CSV, found {len(reports)}")
    return reports[0].read_text(encoding="utf-8", errors="replace")


def validate_reports(
    capture: Path, reference: Path, scene: str, first: int, frames: int
) -> None:
    required = (
        "Standard-semantics compute-mirror 2x2x2 factorial capture",
        f"Scene:           {scene.lower()}",
        f"Camera profile:  {PROFILE}",
        f"capture [{first}, {first + frames - 1}]",
        "point versus bilinear history sampling",
        "official velocity-alpha adaptive 0..0.5 versus fixed 0.5",
        "previous spatial-frame history versus resolved-output recursive feedback",
        "clamp history bounds",
    )
    reference_required = (
        "supersample spatial-reference capture",
        f"Scene:           {scene.lower()}",
        f"Camera profile:  {PROFILE}",
        "2x linear resolution, 3x3 within-frame subpixel grid, 8x MSAA",
    )
    missing = [value for value in required if value not in report_text(capture)]
    missing += [
        value for value in reference_required if value not in report_text(reference)
    ]
    if missing:
        raise RuntimeError(f"{scene}: report validation failed: {missing}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_frame_slice(
    directory: Path, first: int, expected: int
) -> tuple[list[Path], tuple[int, int]]:
    """Read a profile-frame slice from a full prior/reference capture."""
    all_frames = sorted(
        directory.glob("*.png"), key=lambda path: parse_frame_indices(path)[0]
    )
    by_profile = {parse_frame_indices(path)[0]: path for path in all_frames}
    indices = list(range(first, first + expected))
    if any(index not in by_profile for index in indices):
        raise RuntimeError(
            f"{directory}: missing profile-frame range "
            f"[{first}, {first + expected - 1}]"
        )
    frames = [by_profile[index] for index in indices]
    with Image.open(frames[0]) as image:
        resolution = image.size
    for path in frames[1:]:
        with Image.open(path) as image:
            if image.size != resolution:
                raise RuntimeError(f"{path}: resolution {image.size} != {resolution}")
    return frames, resolution


def hash_bridge(
    scene: str, capture: Path, prior: Path, first: int, expected: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for directory in ("O_T2X_R", "ABL_Standard_PatternOff_R"):
        current = sorted(
            (capture / directory).glob("*.png"),
            key=lambda path: parse_frame_indices(path)[0],
        )
        previous_all = sorted(
            (prior / directory).glob("*.png"),
            key=lambda path: parse_frame_indices(path)[0],
        )
        previous_by_profile = {
            parse_frame_indices(path)[0]: path for path in previous_all
        }
        requested = list(range(first, first + expected))
        if len(current) != expected or any(
            index not in previous_by_profile for index in requested
        ):
            raise RuntimeError(
                f"{scene}/{directory}: incomplete bridge range "
                f"[{first}, {first + expected - 1}]"
            )
        if [parse_frame_indices(path)[0] for path in current] != requested:
            raise RuntimeError(f"{scene}/{directory}: current profile indices differ")
        previous = [previous_by_profile[index] for index in requested]
        mismatches = sum(
            sha256(new) != sha256(old) for new, old in zip(current, previous)
        )
        if mismatches:
            raise RuntimeError(
                f"{scene}/{directory}: {mismatches} prior-control hash mismatches"
            )
        rows.append(
            {
                "scene": scene,
                "mode_directory": directory,
                "frame_count": expected,
                "byte_hash_mismatches": mismatches,
                "prior_capture_root": str(prior),
            }
        )
    return rows


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return finite_mean([float(row[key]) for row in rows])


def windows(first: int, expected: int) -> tuple[tuple[str, str, int, int], ...]:
    last = first + expected
    result: list[tuple[str, str, int, int]] = [
        ("capture", f"profile {first}~{last - 1}", 0, expected)
    ]
    for window in (
        ("central_motion", "중앙 이동", 150, 330),
        ("transition", "이동→정지", 410, 440),
        ("post_still", "후기 정지", 420, 480),
    ):
        key, label, global_start, global_end = window
        overlap_start = max(first, global_start)
        overlap_end = min(last, global_end)
        if overlap_start < overlap_end:
            result.append(
                (key, label, overlap_start - first, overlap_end - first)
            )
    return tuple(result)


def factor_effects(mode_summaries: dict[str, Any], pattern: str) -> dict[str, float]:
    def average(keys: list[str]) -> float:
        return finite_mean(
            [float(mode_summaries[key]["mean_rgb_mae_to_reference"]) for key in keys]
        )

    def matching(**values: str) -> list[str]:
        result: list[str] = []
        for sampler, weight, feedback in FACTORS:
            factors = {
                "sampler": sampler,
                "weight": weight,
                "feedback": feedback,
            }
            if all(factors[name] == value for name, value in values.items()):
                result.append(cell_key(pattern, sampler, weight, feedback))
        return result

    sampler = average(matching(sampler="bilinear")) - average(
        matching(sampler="point")
    )
    weight = average(matching(weight="fixed")) - average(
        matching(weight="adaptive")
    )
    feedback = average(matching(feedback="resolved")) - average(
        matching(feedback="spatial")
    )

    def interaction(first: str, a0: str, a1: str, second: str, b0: str, b1: str) -> float:
        return (
            average(matching(**{first: a1, second: b1}))
            - average(matching(**{first: a0, second: b1}))
            - average(matching(**{first: a1, second: b0}))
            + average(matching(**{first: a0, second: b0}))
        )

    return {
        "bilinear_minus_point_mae": sampler,
        "fixed_minus_adaptive_mae": weight,
        "resolved_minus_spatial_mae": feedback,
        "sampler_x_weight_mae": interaction(
            "sampler", "point", "bilinear", "weight", "adaptive", "fixed"
        ),
        "sampler_x_feedback_mae": interaction(
            "sampler", "point", "bilinear", "feedback", "spatial", "resolved"
        ),
        "weight_x_feedback_mae": interaction(
            "weight", "adaptive", "fixed", "feedback", "spatial", "resolved"
        ),
    }


def make_mirror_sheet(
    output: Path, paths: dict[str, list[Path]], frames: list[int], diff: bool
) -> None:
    columns = (
        ("SS-Ref", "reference", "reference"),
        ("Official On", "official_on", "reference"),
        ("Compute Mirror On", "on_point_adaptive_spatial", "official_on"),
        ("Official Off", "official_off", "reference"),
        ("Compute Mirror Off", "off_point_adaptive_spatial", "official_off"),
    )
    width, label_height = 260, 25
    tile_height = resized(paths["reference"][0], width).height
    canvas = Image.new(
        "RGB",
        (width * len(columns), label_height + len(frames) * (tile_height + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (label, key, comparison) in enumerate(columns):
        suffix = " |x4 diff|" if diff and key != "reference" else ""
        draw.text((column * width + 4, 6), label + suffix, fill="black")
    y = label_height
    for frame in frames:
        for column, (_, key, comparison) in enumerate(columns):
            image = (
                difference_image(paths[key][frame], paths[comparison][frame], width)
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
    first: int,
    expected: int,
    stride: int,
    output: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_reports(capture, reference, scene, first, expected)
    paths: dict[str, list[Path]] = {}
    resolutions: set[tuple[int, int]] = set()
    for mode in MODES:
        paths[mode["key"]], resolution = collect_frames(
            capture / mode["directory"], expected, first
        )
        resolutions.add(resolution)
    paths["reference"], resolution = collect_frame_slice(
        reference / "SS_Reference", first, expected
    )
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
        official = {
            "on": load_rgb(paths["official_on"][frame]),
            "off": load_rgb(paths["official_off"][frame]),
        }
        for mode in MODES:
            key = mode["key"]
            image = official[mode["pattern"]] if key.startswith("official_") else load_rgb(paths[key][frame])
            temporal_residual = float("nan")
            if key in previous and previous_reference is not None:
                temporal_residual = float(
                    np.abs(
                        (image.astype(np.int16) - previous[key].astype(np.int16))
                        - (reference_rgb.astype(np.int16) - previous_reference.astype(np.int16))
                    ).mean(dtype=np.float64)
                )
            control = official[mode["pattern"]]
            absolute_control_difference = np.abs(
                image.astype(np.int16) - control.astype(np.int16)
            )
            rows.append(
                {
                    "scene": scene,
                    "frame": frame,
                    **mode,
                    "rgb_mae_to_reference": rgb_mae(image, reference_rgb),
                    "rgb_psnr_to_reference_db": rgb_psnr(image, reference_rgb),
                    "luma_ssim_to_reference": (
                        luma_ssim(image, reference_rgb)
                        if frame % stride == 0
                        else float("nan")
                    ),
                    "edge_strength_ratio_to_reference": (
                        edge_strength(image) / reference_edge
                        if reference_edge > 1.0e-12
                        else float("nan")
                    ),
                    "temporal_delta_residual_to_reference": temporal_residual,
                    "rgb_mae_to_official_control": float(
                        absolute_control_difference.mean(dtype=np.float64)
                    ),
                    "pixel_mismatch_fraction_to_official_control": float(
                        np.any(absolute_control_difference > 0, axis=2).mean()
                    ),
                    "max_channel_error_to_official_control": int(
                        absolute_control_difference.max()
                    ),
                }
            )
            previous[key] = image
        previous_reference = reference_rgb

    summary: dict[str, Any] = {
        "scene": scene,
        "profile": PROFILE,
        "profile_frame_range_inclusive": [first, first + expected - 1],
        "resolution": list(next(iter(resolutions))),
        "capture_root": str(capture),
        "reference_root": str(reference),
        "windows": {},
    }
    for window_key, label, start, end in windows(first, expected):
        mode_summaries: dict[str, Any] = {}
        for mode in MODES:
            selected = [
                row
                for row in rows
                if row["key"] == mode["key"] and start <= int(row["frame"]) < end
            ]
            mode_summaries[mode["key"]] = {
                **mode,
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
                "mean_rgb_mae_to_official_control": mean(
                    selected, "rgb_mae_to_official_control"
                ),
                "mean_pixel_mismatch_fraction_to_official_control": mean(
                    selected, "pixel_mismatch_fraction_to_official_control"
                ),
                "max_channel_error_to_official_control": max(
                    int(row["max_channel_error_to_official_control"])
                    for row in selected
                ),
            }
        cells = [mode for mode in MODES if not mode["key"].startswith("official_")]
        best = {
            pattern: min(
                [mode for mode in cells if mode["pattern"] == pattern],
                key=lambda mode: mode_summaries[mode["key"]]["mean_rgb_mae_to_reference"],
            )["key"]
            for pattern in ("on", "off")
        }
        summary["windows"][window_key] = {
            "label": label,
            "range_half_open": [start, end],
            "modes": mode_summaries,
            "factor_effects": {
                pattern: factor_effects(mode_summaries, pattern)
                for pattern in ("on", "off")
            },
            "best_factorial_cell": best,
        }

    scene_output = output / scene
    scene_output.mkdir(parents=True, exist_ok=True)
    visual_frames = sorted(
        {0, expected // 3, (2 * expected) // 3, expected - 1}
    )
    make_mirror_sheet(
        scene_output / "standard_compute_mirror_comparison.png",
        paths,
        visual_frames,
        False,
    )
    make_mirror_sheet(
        scene_output / "standard_compute_mirror_difference_x4.png",
        paths,
        visual_frames,
        True,
    )
    return rows, summary


def write_report(path: Path, summaries: dict[str, Any], bridges: list[dict[str, Any]]) -> None:
    lines = [
        "# Standard Temporal Semantics 2×2×2 Factorial 결과",
        "",
        "## 목적",
        "",
        "공식 SMAA Standard T2X-R과 FullScreenDocument compute 경로의 차이를 sampler, history weight 정책, history feedback topology의 세 축으로 분해했다.",
        "Point + velocity-alpha adaptive weight + spatial-frame feedback cell은 공식 Standard 의미를 common compute 경로에서 재현하는 mirror다.",
        "Pattern On/Off는 projection jitter와 대응 subsample index를 항상 한 쌍으로 전환했다.",
        "",
        "## 입력 무결성",
        "",
        f"- 기존 공식 Standard control hash bridge: {len(bridges)} sequences, mismatch 0",
        "- supersample 입력은 동일 pose의 spatial-reference proxy이며 temporal ground truth로 표현하지 않는다.",
        "",
        "## 공식 경로와 compute mirror 차이",
        "",
        "| Scene | Window | Pattern | Mirror MAE→official | Pixel mismatch | Max channel error | Mirror MAE→reference − official |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for scene, summary in summaries.items():
        for window_key, window in summary["windows"].items():
            for pattern in ("on", "off"):
                mirror = window["modes"][f"{pattern}_point_adaptive_spatial"]
                official = window["modes"][f"official_{pattern}"]
                lines.append(
                    f"| {scene} | {window['label']} | {pattern} | "
                    f"{mirror['mean_rgb_mae_to_official_control']:.6f} | "
                    f"{mirror['mean_pixel_mismatch_fraction_to_official_control'] * 100.0:.6f}% | "
                    f"{mirror['max_channel_error_to_official_control']} | "
                    f"{mirror['mean_rgb_mae_to_reference'] - official['mean_rgb_mae_to_reference']:+.6f} |"
                )

    lines += [
        "",
        "## Factorial main effects",
        "",
        "양수는 해당 두 번째 수준이 supersample spatial-reference RGB MAE를 증가시켰음을 뜻한다.",
        "",
        "| Scene | Window | Pattern | Bilinear−Point | Fixed−Adaptive | Resolved−Spatial | Best cell |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for scene, summary in summaries.items():
        for window in summary["windows"].values():
            for pattern in ("on", "off"):
                effects = window["factor_effects"][pattern]
                lines.append(
                    f"| {scene} | {window['label']} | {pattern} | "
                    f"{effects['bilinear_minus_point_mae']:+.6f} | "
                    f"{effects['fixed_minus_adaptive_mae']:+.6f} | "
                    f"{effects['resolved_minus_spatial_mae']:+.6f} | "
                    f"{window['best_factorial_cell'][pattern]} |"
                )

    lines += [
        "",
        "## 해석 제한",
        "",
        "- 공식 pixel-shader 경로와 compute mirror의 비영(非零) 차이는 실행 경로, resource view 및 저장 반올림을 포함하므로 수치로 먼저 경계한다.",
        "- factorial 효과는 같은 compute 경로 안의 controlled comparison이다.",
        "- 이 gate는 TSCMAA candidate coverage 효과가 아니라 Standard/document temporal 의미 차이를 분해하는 진단이다.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    bridges: list[dict[str, Any]] = []
    for scene, capture_text, reference_text, prior_text in args.case:
        capture = Path(capture_text)
        reference = Path(reference_text)
        prior = Path(prior_text)
        rows, summary = analyze_case(
            scene,
            capture,
            reference,
            args.first_profile_frame,
            args.expected_frames,
            args.ssim_stride,
            args.output,
        )
        all_rows.extend(rows)
        summaries[scene] = summary
        bridges.extend(
            hash_bridge(
                scene,
                capture,
                prior,
                args.first_profile_frame,
                args.expected_frames,
            )
        )

    with (args.output / "standard_semantics_factorial_per_frame.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    payload = {
        "classification": args.classification,
        "hash_bridges": bridges,
        "scenes": summaries,
    }
    (args.output / "standard_semantics_factorial_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(
        args.output / "SMAA-Standard-Semantics-Factorial-Results-ko.md",
        summaries,
        bridges,
    )
    print(f"PASS: analyzed {len(summaries)} scenes and {len(all_rows)} rows")


if __name__ == "__main__":
    main()
