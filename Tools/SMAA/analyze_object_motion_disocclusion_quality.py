from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_candidate_only_ablation import crop_half, validate_inputs
from analyze_object_motion_reprojection_quality import (
    luma_edge_strength,
    luma_ssim,
)
from analyze_original_four_quality import aggregate, load_rgb, percent_delta
from analyze_supersample_reference_quality import (
    read_reference_provenance,
    rgb_mae,
    rgb_psnr,
    validate_reference,
)
from analyze_temporal_stress_quality import (
    ghost_trail_proxy,
    object_screen_velocity,
    roi_boxes,
    visual_center_frame,
    visual_regions,
)


MODES = (
    ("o_1x", "O-1X", "O_1X"),
    (
        "standard_camera_depth_off",
        "O-T2X-R / camera-only / depth Off",
        "O_T2X_R_CameraOnly_DepthOff",
    ),
    (
        "standard_camera_depth_on",
        "O-T2X-R / camera-only / depth On",
        "O_T2X_R_CameraOnly_DepthOn",
    ),
    (
        "standard_rigid_depth_off",
        "O-T2X-R / camera+rigid / depth Off",
        "O_T2X_R_Rigid_DepthOff",
    ),
    (
        "standard_rigid_depth_on",
        "O-T2X-R / camera+rigid / depth On",
        "O_T2X_R_Rigid_DepthOn",
    ),
    (
        "edge_camera_depth_off",
        "O-ET2X-R / camera-only / depth Off",
        "O_ET2X_R_CameraOnly_DepthOff",
    ),
    (
        "edge_camera_depth_on",
        "O-ET2X-R / camera-only / depth On",
        "O_ET2X_R_CameraOnly_DepthOn",
    ),
    (
        "edge_rigid_depth_off",
        "O-ET2X-R / camera+rigid / depth Off",
        "O_ET2X_R_Rigid_DepthOff",
    ),
    (
        "edge_rigid_depth_on",
        "O-ET2X-R / camera+rigid / depth On",
        "O_ET2X_R_Rigid_DepthOn",
    ),
)

REFERENCE_KEY = "ss_reference"
REFERENCE_LABEL = "SS-Reference"

# Cell order is (rigid-object velocity, previous-depth rejection).
PROFILE_CELLS = {
    "Standard": {
        (False, False): "standard_camera_depth_off",
        (False, True): "standard_camera_depth_on",
        (True, False): "standard_rigid_depth_off",
        (True, True): "standard_rigid_depth_on",
    },
    "ET2X": {
        (False, False): "edge_camera_depth_off",
        (False, True): "edge_camera_depth_on",
        (True, False): "edge_rigid_depth_off",
        (True, True): "edge_rigid_depth_on",
    },
}

METRICS = {
    "rgb_mae_vs_reference": "lower spatial-reference proxy error is better",
    "rgb_psnr_vs_reference": "higher spatial-reference proxy similarity is better",
    "luma_ssim_vs_reference": "higher spatial-reference proxy similarity is better",
    "edge_ratio_vs_reference": "descriptive ratio; the target is 1.0",
    "adjacent_rgb_mae": "descriptive temporal change; lower can also indicate blur",
    "ghost_trail_mean_darkness": "lower trailing-halo heuristic is better",
    "ghost_trail_width_px": "lower trailing-halo heuristic is better",
}

EFFECTS = (
    (
        "rigid_effect_depth_off",
        (False, False),
        (True, False),
        "Rigid On - Off, depth Off",
    ),
    (
        "rigid_effect_depth_on",
        (False, True),
        (True, True),
        "Rigid On - Off, depth On",
    ),
    (
        "depth_effect_camera_only",
        (False, False),
        (False, True),
        "Depth On - Off, camera-only",
    ),
    (
        "depth_effect_rigid",
        (True, False),
        (True, True),
        "Depth On - Off, rigid On",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze the 2x2 rigid-object velocity and previous-depth rejection "
            "matrix for Standard SMAA T2X-R and edge-selective ET2X-R on the "
            "generated checker texture on deterministic procedural rigid geometry "
            "engineering fixture."
        )
    )
    parser.add_argument(
        "capture_root",
        type=Path,
        help="Root containing the nine named capture directories.",
    )
    parser.add_argument(
        "reference_root",
        type=Path,
        help="Supersample capture root containing SS_Reference.",
    )
    parser.add_argument(
        "--scenario",
        choices=("object-motion", "combined"),
        default="object-motion",
    )
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def safe_percent_delta(value: float, baseline: float) -> float:
    if not math.isfinite(value) or not math.isfinite(baseline) or baseline == 0.0:
        return float("nan")
    return percent_delta(value, baseline)


def numeric(value: Any) -> float | None:
    if value == "" or value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def sequence_hash_validation(
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    expected_resolution: tuple[int, int],
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Decode every frame and record stable file/pixel sequence hashes."""
    validation: dict[str, Any] = {}
    pixel_hashes: dict[str, list[str]] = {}
    for key, frames in paths.items():
        file_sequence = hashlib.sha256()
        pixel_sequence = hashlib.sha256()
        current_pixel_hashes: list[str] = []
        current_file_hashes: list[str] = []
        for frame, path in enumerate(frames):
            payload = path.read_bytes()
            file_hash = hashlib.sha256(payload).hexdigest()
            with Image.open(path) as source:
                source.load()
                if source.size != expected_resolution:
                    raise RuntimeError(
                        f"{labels[key]} frame {frame}: resolution {source.size} "
                        f"differs from {expected_resolution}"
                    )
                rgb = source.convert("RGB")
                pixel_hash = hashlib.sha256(rgb.tobytes()).hexdigest()
            current_file_hashes.append(file_hash)
            current_pixel_hashes.append(pixel_hash)
            identity = f"{frame}:{path.name}:{file_hash}\n".encode("utf-8")
            file_sequence.update(identity)
            pixel_sequence.update(
                f"{frame}:{expected_resolution[0]}x{expected_resolution[1]}:"
                f"{pixel_hash}\n".encode("ascii")
            )
        validation[labels[key]] = {
            "all_frames_decoded": True,
            "all_frame_resolutions_match": True,
            "unique_file_hashes": len(set(current_file_hashes)),
            "unique_pixel_hashes": len(set(current_pixel_hashes)),
            "sequence_file_sha256": file_sequence.hexdigest(),
            "sequence_pixel_sha256": pixel_sequence.hexdigest(),
            "first_pixel_sha256": current_pixel_hashes[0],
            "last_pixel_sha256": current_pixel_hashes[-1],
        }
        pixel_hashes[key] = current_pixel_hashes
    return validation, pixel_hashes


def paired_hash_checks(pixel_hashes: dict[str, list[str]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for profile, cells in PROFILE_CELLS.items():
        pairs = (
            ("rigid_effect_depth_off", cells[(False, False)], cells[(True, False)]),
            ("rigid_effect_depth_on", cells[(False, True)], cells[(True, True)]),
            ("depth_effect_camera_only", cells[(False, False)], cells[(False, True)]),
            ("depth_effect_rigid", cells[(True, False)], cells[(True, True)]),
        )
        for effect, baseline, treatment in pairs:
            mismatches = sum(
                first != second
                for first, second in zip(
                    pixel_hashes[baseline], pixel_hashes[treatment]
                )
            )
            checks.append(
                {
                    "profile": profile,
                    "effect": effect,
                    "baseline": baseline,
                    "treatment": treatment,
                    "frame_count": len(pixel_hashes[baseline]),
                    "pixel_hash_mismatch_frames": mismatches,
                    "pixel_hash_match_frames": len(pixel_hashes[baseline]) - mismatches,
                }
            )
    return checks


def metric_value(
    row: dict[str, Any], roi_name: str, mode_key: str, metric: str
) -> float | None:
    return numeric(row.get(f"{roi_name}_{mode_key}_{metric}"))


def build_effect_rows(
    frame_rows: list[dict[str, Any]], roi_names: tuple[str, ...]
) -> list[dict[str, Any]]:
    effect_rows: list[dict[str, Any]] = []
    for frame_row in frame_rows:
        frame = int(frame_row["frame"])
        for profile, cells in PROFILE_CELLS.items():
            for roi_name in roi_names:
                for metric, interpretation in METRICS.items():
                    values = {
                        cell: metric_value(frame_row, roi_name, key, metric)
                        for cell, key in cells.items()
                    }
                    for effect, baseline_cell, treatment_cell, label in EFFECTS:
                        baseline = values[baseline_cell]
                        treatment = values[treatment_cell]
                        if baseline is None or treatment is None:
                            continue
                        effect_rows.append(
                            {
                                "frame": frame,
                                "profile": profile,
                                "roi": roi_name,
                                "metric": metric,
                                "interpretation": interpretation,
                                "effect": effect,
                                "effect_label": label,
                                "baseline_mode": cells[baseline_cell],
                                "treatment_mode": cells[treatment_cell],
                                "baseline_value": baseline,
                                "treatment_value": treatment,
                                "delta_treatment_minus_baseline": treatment - baseline,
                                # Keep the per-frame percentage for raw diagnostics only.
                                # The summary must derive its percentage from the two cell
                                # means; averaging frame percentages can reverse direction
                                # when a frame has a near-zero baseline.
                                "frame_percent_delta": safe_percent_delta(treatment, baseline),
                                "r0_d0": values[(False, False)],
                                "r0_d1": values[(False, True)],
                                "r1_d0": values[(True, False)],
                                "r1_d1": values[(True, True)],
                            }
                        )

                    if all(value is not None for value in values.values()):
                        r0d0 = float(values[(False, False)])
                        r0d1 = float(values[(False, True)])
                        r1d0 = float(values[(True, False)])
                        r1d1 = float(values[(True, True)])
                        interaction = (r1d1 - r1d0) - (r0d1 - r0d0)
                        effect_rows.append(
                            {
                                "frame": frame,
                                "profile": profile,
                                "roi": roi_name,
                                "metric": metric,
                                "interpretation": interpretation,
                                "effect": "rigid_by_depth_interaction",
                                "effect_label": (
                                    "(Depth On-Off with rigid On) - "
                                    "(Depth On-Off with rigid Off)"
                                ),
                                "baseline_mode": "difference-in-differences",
                                "treatment_mode": "difference-in-differences",
                                "baseline_value": "",
                                "treatment_value": "",
                                "delta_treatment_minus_baseline": interaction,
                                "frame_percent_delta": "",
                                "r0_d0": r0d0,
                                "r0_d1": r0d1,
                                "r1_d0": r1d0,
                                "r1_d1": r1d1,
                            }
                        )
    return effect_rows


def summarize_effects(effect_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in effect_rows:
        groups[(row["profile"], row["roi"], row["metric"], row["effect"])].append(row)

    result: list[dict[str, Any]] = []
    for (profile, roi_name, metric, effect), rows in sorted(groups.items()):
        delta_key = "delta_treatment_minus_baseline"
        item: dict[str, Any] = {
            "profile": profile,
            "roi": roi_name,
            "metric": metric,
            "interpretation": rows[0]["interpretation"],
            "effect": effect,
            "effect_label": rows[0]["effect_label"],
            "paired_frame_count": len(rows),
            "paired_delta": aggregate(rows, delta_key),
        }
        baseline_values = [
            float(row["baseline_value"])
            for row in rows
            if numeric(row["baseline_value"]) is not None
        ]
        treatment_values = [
            float(row["treatment_value"])
            for row in rows
            if numeric(row["treatment_value"]) is not None
        ]
        if baseline_values and len(baseline_values) == len(treatment_values):
            baseline_mean = statistics.fmean(baseline_values)
            treatment_mean = statistics.fmean(treatment_values)
            item["baseline_mean"] = baseline_mean
            item["treatment_mean"] = treatment_mean
            item["aggregate_percent_delta"] = safe_percent_delta(
                treatment_mean, baseline_mean
            )
        result.append(item)
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_profile_gif(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    profile: str,
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
) -> str:
    keys = (REFERENCE_KEY, "o_1x") + tuple(PROFILE_CELLS[profile].values())
    count = min(24, expected_frames)
    start = min(max(center_frame - count // 2, 0), max(0, expected_frames - count))
    end = start + count
    width = box[2] - box[0]
    height = box[3] - box[1]
    frames: list[Image.Image] = []
    for frame in range(start, end):
        canvas = Image.new("RGB", (width * len(keys), height + 35), "black")
        draw = ImageDraw.Draw(canvas)
        for column, key in enumerate(keys):
            with Image.open(paths[key][frame]) as source:
                crop = source.convert("RGB").crop(box)
            x = column * width
            canvas.paste(crop, (x, 35))
            draw.text((x + 6, 10), labels[key], fill="white")
        frames.append(canvas.quantize(colors=192, method=Image.Quantize.MEDIANCUT))
    name = (
        f"object_motion_disocclusion_{profile.lower()}_{roi_name}_"
        f"{start:05d}_{end - 1:05d}.gif"
    )
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


def make_profile_sheet(
    output: Path,
    paths: dict[str, list[Path]],
    labels: dict[str, str],
    profile: str,
    roi_name: str,
    box: tuple[int, int, int, int],
    center_frame: int,
    expected_frames: int,
) -> str:
    keys = (REFERENCE_KEY, "o_1x") + tuple(PROFILE_CELLS[profile].values())
    sampled = [
        min(max(center_frame + offset, 0), expected_frames - 1)
        for offset in (-12, -8, -4, 0, 4, 8)
    ]
    width = box[2] - box[0]
    height = box[3] - box[1]
    row_height = height + 35
    canvas = Image.new("RGB", (width * len(keys), row_height * len(sampled)), "black")
    draw = ImageDraw.Draw(canvas)
    for row, frame in enumerate(sampled):
        y = row * row_height
        for column, key in enumerate(keys):
            with Image.open(paths[key][frame]) as source:
                crop = source.convert("RGB").crop(box)
            x = column * width
            canvas.paste(crop, (x, y + 35))
            draw.text((x + 6, y + 10), f"{frame:05d} {labels[key]}", fill="white")
    name = (
        f"object_motion_disocclusion_sheet_{profile.lower()}_{roi_name}_"
        f"{sampled[0]:05d}_{sampled[-1]:05d}.png"
    )
    canvas.save(output / name, compress_level=3)
    return name


def format_value(value: float) -> str:
    if not math.isfinite(value):
        return "n/a"
    return f"{value:.6f}"


def main() -> None:
    args = parse_args()
    if args.expected_frames < 2:
        raise SystemExit("--expected-frames must be at least 2")
    if args.warmup_frames < 0:
        raise SystemExit("--warmup-frames must be non-negative")

    capture_root = args.capture_root.resolve()
    reference_root = args.reference_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else capture_root / "ObjectMotionDisocclusionAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)

    reference_paths, reference_resolution, reference_validation = validate_reference(
        reference_root, args.expected_frames
    )
    capture_paths, capture_resolution, capture_validation = validate_inputs(
        capture_root, args.expected_frames, MODES
    )
    if reference_resolution != capture_resolution:
        raise RuntimeError(
            f"Reference resolution {reference_resolution} differs from "
            f"capture resolution {capture_resolution}"
        )

    provenance = read_reference_provenance(reference_root)
    boxes = roi_boxes(args.scenario, reference_resolution)
    paths = {REFERENCE_KEY: reference_paths, **capture_paths}
    labels = {
        REFERENCE_KEY: REFERENCE_LABEL,
        **{key: semantic_id for key, semantic_id, _ in MODES},
    }
    hash_validation, pixel_hashes = sequence_hash_validation(
        paths, labels, reference_resolution
    )
    hash_pairs = paired_hash_checks(pixel_hashes)

    all_keys = (REFERENCE_KEY,) + tuple(key for key, _, _ in MODES)
    frame_rows: list[dict[str, Any]] = []
    previous_rois: dict[str, dict[str, np.ndarray]] | None = None
    for frame in range(args.expected_frames):
        full = {key: load_rgb(paths[key][frame]) for key in all_keys}
        rois = {
            roi_name: {key: crop_half(full[key], box) for key in all_keys}
            for roi_name, box in boxes.items()
        }
        row: dict[str, Any] = {"frame": frame}
        for roi_name, values in rois.items():
            reference = values[REFERENCE_KEY]
            reference_edge = luma_edge_strength(reference)
            row[f"{roi_name}_reference_edge_strength"] = reference_edge
            for key, _, _ in MODES:
                current = values[key]
                prefix = f"{roi_name}_{key}"
                current_edge = luma_edge_strength(current)
                row[f"{prefix}_rgb_mae_vs_reference"] = rgb_mae(current, reference)
                row[f"{prefix}_rgb_psnr_vs_reference"] = rgb_psnr(current, reference)
                row[f"{prefix}_luma_ssim_vs_reference"] = luma_ssim(current, reference)
                row[f"{prefix}_edge_ratio_vs_reference"] = (
                    current_edge / reference_edge
                    if reference_edge > 0.0
                    else float("nan")
                )
                if previous_rois is not None:
                    row[f"{prefix}_adjacent_rgb_mae"] = rgb_mae(
                        current, previous_rois[roi_name][key]
                    )

            for profile, cells in PROFILE_CELLS.items():
                prefix = f"{roi_name}_{profile.lower()}"
                for effect, baseline_cell, treatment_cell, _ in EFFECTS:
                    row[f"{prefix}_{effect}_output_rgb_mae"] = rgb_mae(
                        values[cells[baseline_cell]], values[cells[treatment_cell]]
                    )

        if "occluder_path" in boxes:
            velocity = object_screen_velocity(args.scenario, frame / 60.0)
            for key, _, _ in MODES:
                trail_mean, trail_width = ghost_trail_proxy(
                    full[key], boxes["occluder_path"], velocity
                )
                row[f"occluder_path_{key}_ghost_trail_mean_darkness"] = (
                    "" if math.isnan(trail_mean) else trail_mean
                )
                row[f"occluder_path_{key}_ghost_trail_width_px"] = (
                    "" if math.isnan(trail_width) else trail_width
                )

        frame_rows.append(row)
        previous_rois = rois
        if frame % 20 == 0 or frame == args.expected_frames - 1:
            print(f"Processed {frame + 1}/{args.expected_frames} frames", flush=True)

    frame_csv_name = "object_motion_disocclusion_frame_metrics.csv"
    write_csv(output / frame_csv_name, frame_rows)

    fieldnames: list[str] = []
    for row in frame_rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    metric_summary = {
        key: aggregate(frame_rows, key)
        for key in fieldnames
        if key != "frame" and any(numeric(row.get(key)) is not None for row in frame_rows)
    }

    effect_rows = build_effect_rows(frame_rows, tuple(boxes))
    effects_csv_name = "object_motion_disocclusion_paired_effects.csv"
    write_csv(output / effects_csv_name, effect_rows)
    effect_summary = summarize_effects(effect_rows)

    center = visual_center_frame(args.scenario)
    artifact_names: list[str] = []
    for profile in PROFILE_CELLS:
        for roi_name in visual_regions(args.scenario):
            if roi_name not in boxes:
                continue
            artifact_names.append(
                make_profile_gif(
                    output,
                    paths,
                    labels,
                    profile,
                    roi_name,
                    boxes[roi_name],
                    center,
                    args.expected_frames,
                )
            )
            artifact_names.append(
                make_profile_sheet(
                    output,
                    paths,
                    labels,
                    profile,
                    roi_name,
                    boxes[roi_name],
                    center,
                    args.expected_frames,
                )
            )

    result = {
        "validation_status": "PASS",
        "scenario": args.scenario,
        "classification": (
            "generated checker texture on deterministic procedural rigid geometry"
        ),
        "temporal_ground_truth": False,
        "reference_role": "within-frame supersample spatial-reference proxy",
        "fixture_material_scope": {
            "rotor": "generated 32x32 checker texture applied",
            "dark_occluder": "existing dark material retained; generated checker texture not applied",
        },
        "conditions": {
            "resolution": list(reference_resolution),
            "analysis_resolution": "each ROI at half width/height",
            "frame_rate": 60,
            "warmup_frames": args.warmup_frames,
            "capture_frames": args.expected_frames,
            "factorial_axes": [
                "rigid-object velocity Off/On",
                "previous-depth disocclusion rejection Off/On",
            ],
            "profiles": ["Standard T2X-R", "edge-selective ET2X-R"],
        },
        "reference_provenance": provenance,
        "reference_validation": reference_validation,
        "capture_validation": capture_validation,
        "full_sequence_hash_validation": hash_validation,
        "paired_pixel_hash_checks": hash_pairs,
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "metric_summary": metric_summary,
        "factorial_effect_definition": (
            "paired delta is treatment minus baseline; interaction is "
            "(R1D1-R1D0)-(R0D1-R0D0)"
        ),
        "paired_effect_summary": effect_summary,
        "artifacts": artifact_names,
    }
    json_name = "object_motion_disocclusion_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    effect_lookup = {
        (item["profile"], item["roi"], item["metric"], item["effect"]): item
        for item in effect_summary
    }
    report = [
        "# SMAA previous-depth disocclusion engineering 품질 gate",
        "",
        "## 범위와 판정 지위",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 해상도: {reference_resolution[0]}×{reference_resolution[1]}",
        f"- warm-up/capture: {args.warmup_frames}/{args.expected_frames} frames per mode",
        "- 입력: O-1X와 Standard/ET2X의 rigid Off/On × previous-depth Off/On 8개 cell",
        "- 분류: 결정적 procedural rigid geometry와 generated checker texture를 사용한 engineering fixture",
        "- 재질 범위: rotor에만 generated checker texture를 적용했고 dark occluder는 기존 재질을 유지함",
        "- reference: within-frame supersample spatial proxy이며 temporal ground truth가 아님",
        "- paired delta는 enabled 값에서 disabled 값을 뺀 값이다.",
        "- interaction은 (R1D1-R1D0)-(R0D1-R0D0) difference-in-differences다.",
    ]

    for roi_name in boxes:
        report.extend(
            [
                "",
                f"## `{roi_name}` cell 지표",
                "",
                "| Mode | Reference RGB MAE | PSNR | Luma SSIM | Edge/reference | Adjacent MAE |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for key, semantic_id, _ in MODES:
            prefix = f"{roi_name}_{key}"
            adjacent = metric_summary.get(
                f"{prefix}_adjacent_rgb_mae", {"mean": float("nan")}
            )["mean"]
            report.append(
                f"| `{semantic_id}` | "
                f"{format_value(metric_summary[f'{prefix}_rgb_mae_vs_reference']['mean'])} | "
                f"{format_value(metric_summary[f'{prefix}_rgb_psnr_vs_reference']['mean'])} | "
                f"{format_value(metric_summary[f'{prefix}_luma_ssim_vs_reference']['mean'])} | "
                f"{format_value(metric_summary[f'{prefix}_edge_ratio_vs_reference']['mean'])} | "
                f"{format_value(adjacent)} |"
            )

        for metric, title in (
            ("rgb_mae_vs_reference", "Spatial-reference RGB MAE"),
            ("adjacent_rgb_mae", "Adjacent-frame RGB MAE"),
        ):
            report.extend(
                [
                    "",
                    f"### {title} paired 효과",
                    "",
                    "| Profile | Effect | Paired frames | Mean delta | Aggregate % delta |",
                    "|---|---|---:|---:|---:|",
                ]
            )
            for profile in PROFILE_CELLS:
                for effect in tuple(item[0] for item in EFFECTS) + (
                    "rigid_by_depth_interaction",
                ):
                    item = effect_lookup.get((profile, roi_name, metric, effect))
                    if item is None:
                        continue
                    percent = item.get("aggregate_percent_delta", float("nan"))
                    report.append(
                        f"| {profile} | `{effect}` | {item['paired_frame_count']} | "
                        f"{format_value(item['paired_delta']['mean'])} | "
                        f"{format_value(percent)} |"
                    )

    if "occluder_path" in boxes:
        report.extend(
            [
                "",
                "## Occluder trailing-halo 대용 지표",
                "",
                "| Mode | Mean darkness | Width px |",
                "|---|---:|---:|",
            ]
        )
        for key, semantic_id, _ in MODES:
            darkness = metric_summary.get(
                f"occluder_path_{key}_ghost_trail_mean_darkness"
            )
            width = metric_summary.get(
                f"occluder_path_{key}_ghost_trail_width_px"
            )
            report.append(
                f"| `{semantic_id}` | "
                f"{format_value(darkness['mean'] if darkness else float('nan'))} | "
                f"{format_value(width['mean'] if width else float('nan'))} |"
            )
        report.extend(
            [
                "",
                "이 darkness/width 값은 알려진 occluder 이동 방향 뒤를 검사하는 휴리스틱이다.",
                "절대 ghosting 또는 temporal ground truth로 해석하지 않는다.",
            ]
        )
        for metric, title in (
            ("ghost_trail_mean_darkness", "Trail mean darkness"),
            ("ghost_trail_width_px", "Trail width"),
        ):
            report.extend(
                [
                    "",
                    f"### {title} paired 효과",
                    "",
                    "| Profile | Effect | Paired frames | Mean delta | Aggregate % delta |",
                    "|---|---|---:|---:|---:|",
                ]
            )
            for profile in PROFILE_CELLS:
                for effect in tuple(item[0] for item in EFFECTS) + (
                    "rigid_by_depth_interaction",
                ):
                    item = effect_lookup.get(
                        (profile, "occluder_path", metric, effect)
                    )
                    if item is None:
                        continue
                    percent = item.get("aggregate_percent_delta", float("nan"))
                    report.append(
                        f"| {profile} | `{effect}` | {item['paired_frame_count']} | "
                        f"{format_value(item['paired_delta']['mean'])} | "
                        f"{format_value(percent)} |"
                    )

    report.extend(
        [
            "",
            "## Paired pixel-hash 확인",
            "",
            "| Profile | Pair | Frames | Hash mismatch | Hash match |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for check in hash_pairs:
        report.append(
            f"| {check['profile']} | `{check['effect']}` | "
            f"{check['frame_count']} | {check['pixel_hash_mismatch_frames']} | "
            f"{check['pixel_hash_match_frames']} |"
        )

    report.extend(
        [
            "",
            "## 검증과 해석 제한",
            "",
            "- 9개 sequence의 frame 수, index, 모든 PNG 해상도와 file/pixel SHA-256을 검증·기록했다.",
            "- paired hash mismatch 수는 toggle이 실제 출력을 바꾼 frame 수를 보여 주며 품질 우열은 뜻하지 않는다.",
            "- supersample reference는 동일 pose의 고품질 spatial proxy다.",
            "- adjacent-frame 변화가 작다는 사실만으로 ghosting 감소를 단정할 수 없다.",
            "- generated checker texture는 rotor에만 적용되며 dark occluder는 기존 어두운 재질을 유지한다.",
            "- rotor/occluder ROI와 trail 지표는 이 결정적 procedural fixture에 고정된 진단 범위다.",
            "- skinned/deforming/transparent motion은 이 gate의 범위에 포함하지 않는다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 cell 지표: `{frame_csv_name}`",
            f"- 프레임별 paired 효과와 interaction: `{effects_csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
        ]
    )
    report.extend(f"- 비교 자료: `{name}`" for name in artifact_names)
    report.append("")
    report_name = "SMAA-Object-Motion-Disocclusion-Quality-ko.md"
    (output / report_name).write_text("\n".join(report), encoding="utf-8")
    print(f"Object-motion disocclusion analysis complete: {output}")


if __name__ == "__main__":
    main()
