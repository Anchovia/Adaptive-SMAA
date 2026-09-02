#!/usr/bin/env python3
"""Run formal CGVQM-2 for the controlled ET2X feedback-topology gate."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


PROFILE = "flythrough-wide-yaw-360"
MODES = (
    (
        "O-ET2X-R-ResolvedFeedback",
        "O_ET2X_R_ResolvedFeedback",
    ),
    (
        "ABL-ET2X-R-SpatialFeedback",
        "ABL_ET2X_R_SpatialFeedback",
    ),
)
WINDOWS = (
    ("central_motion_00150_00329", "central", 150, 180),
    ("transition_00410_00439", "transition", 410, 30),
)

EXPECTED_CONFIGURATION = {
    "fps": 60,
    "patch_scale": 4,
    "patch_pool": "mean",
    "models": ["2"],
}
EXPECTED_METRIC_SCOPE = (
    "Full-reference perceptual video quality; not an absolute ghosting "
    "ground truth."
)


def load_sequence_helpers():
    """Load the canonical PNG inspection helpers without affecting --help."""

    tools_dir = str(Path(__file__).resolve().parent)
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from run_cgvqm_png_sequences import (  # pylint: disable=import-outside-toplevel
        collect_frames,
        git_commit,
        inspect_sequence,
        select_offset_aligned_frames,
    )

    return collect_frames, git_commit, inspect_sequence, select_offset_aligned_frames


def compare_exact(
    reasons: list[str], label: str, actual: Any, expected: Any
) -> None:
    if actual != expected:
        reasons.append(f"{label} mismatch: actual={actual!r}, expected={expected!r}")


def expected_sequence_info(
    source: Path,
    reference: Path,
    reference_offset: int,
    frame_count: int,
    frame_cache: dict[Path, dict[int, Path]],
    info_cache: dict[tuple[Path, tuple[int, ...]], dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Inspect the exact frames using run_cgvqm_png_sequences.py semantics."""

    collect_frames, _, inspect_sequence, select_frames = load_sequence_helpers()
    source = source.resolve()
    reference = reference.resolve()
    if source not in frame_cache:
        frame_cache[source] = collect_frames(source)
    if reference not in frame_cache:
        frame_cache[reference] = collect_frames(reference)
    indices, reference_indices, test_paths, reference_paths = select_frames(
        frame_cache[source],
        frame_cache[reference],
        0,
        frame_count,
        reference_offset,
    )

    def inspect_cached(
        directory: Path, paths: list[Path], selected_indices: list[int]
    ) -> dict[str, Any]:
        cache_key = (directory, tuple(selected_indices))
        if cache_key not in info_cache:
            info_cache[cache_key] = asdict(
                inspect_sequence(directory, paths, selected_indices)
            )
        return info_cache[cache_key]

    test_info = inspect_cached(source, test_paths, indices)
    reference_info = inspect_cached(
        reference, reference_paths, reference_indices
    )
    if (test_info["width"], test_info["height"]) != (
        reference_info["width"],
        reference_info["height"],
    ):
        raise RuntimeError(
            "test/reference resolution mismatch while validating resume: "
            f"{test_info['width']}x{test_info['height']} != "
            f"{reference_info['width']}x{reference_info['height']}"
        )
    return test_info, reference_info


def validate_round_trip(
    reasons: list[str],
    label: str,
    value: Any,
    expected_frames: int,
    expected_video: Path,
) -> None:
    if not isinstance(value, dict):
        reasons.append(f"{label} is missing or malformed")
        return
    compare_exact(
        reasons, f"{label}.video", value.get("video"), str(expected_video)
    )
    compare_exact(reasons, f"{label}.codec", value.get("codec"), "ffv1")
    compare_exact(reasons, f"{label}.pixel_format", value.get("pixel_format"), "bgr0")
    compare_exact(
        reasons,
        f"{label}.decoded_frames",
        value.get("decoded_frames"),
        expected_frames,
    )
    compare_exact(
        reasons,
        f"{label}.mismatched_values",
        value.get("mismatched_values"),
        0,
    )
    compare_exact(
        reasons,
        f"{label}.max_absolute_difference",
        value.get("max_absolute_difference"),
        0,
    )
    if not expected_video.is_file():
        reasons.append(f"{label} video is missing: {expected_video}")


def validate_existing_result(
    result_path: Path,
    destination: Path,
    scene: str,
    mode: str,
    source: Path,
    reference: Path,
    reference_offset: int,
    frame_count: int,
    cgvqm_root: Path,
    skip_error_map_video: bool,
    frame_cache: dict[Path, dict[int, Path]],
    info_cache: dict[tuple[Path, tuple[int, ...]], dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Return true only when an existing result exactly matches this job."""

    reasons: list[str] = []
    try:
        value = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return False, [f"result JSON cannot be read: {error}"]
    if not isinstance(value, dict):
        return False, ["result JSON root is not an object"]

    test_info, reference_info = expected_sequence_info(
        source,
        reference,
        reference_offset,
        frame_count,
        frame_cache,
        info_cache,
    )
    compare_exact(reasons, "classification", value.get("classification"), "formal")
    compare_exact(
        reasons,
        "metric_scope",
        value.get("metric_scope"),
        EXPECTED_METRIC_SCOPE,
    )
    compare_exact(
        reasons,
        "provenance",
        value.get("provenance"),
        {
            "scene": scene,
            "camera_profile": PROFILE,
            "test_mode": mode,
            "reference_id": "SS-Reference",
        },
    )
    expected_configuration = dict(EXPECTED_CONFIGURATION)
    expected_configuration["reference_index_offset"] = reference_offset
    compare_exact(
        reasons,
        "configuration",
        value.get("configuration"),
        expected_configuration,
    )
    compare_exact(reasons, "test_sequence", value.get("test_sequence"), test_info)
    compare_exact(
        reasons,
        "reference_sequence",
        value.get("reference_sequence"),
        reference_info,
    )

    _, git_commit, _, _ = load_sequence_helpers()
    current_commit = git_commit(cgvqm_root)
    if current_commit == "unknown":
        reasons.append("current official CGVQM commit cannot be determined")
    compare_exact(
        reasons,
        "official_cgvqm",
        value.get("official_cgvqm"),
        {"root": str(cgvqm_root), "commit": current_commit},
    )
    runtime = value.get("runtime")
    if not isinstance(runtime, dict):
        reasons.append("runtime is missing or malformed")
    else:
        compare_exact(reasons, "runtime.device", runtime.get("device"), "cuda")
        compare_exact(
            reasons, "runtime.cuda_available", runtime.get("cuda_available"), True
        )

    validate_round_trip(
        reasons,
        "test_round_trip",
        value.get("test_round_trip"),
        frame_count,
        destination / "LosslessInputs" / "test_ffv1.mkv",
    )
    validate_round_trip(
        reasons,
        "reference_round_trip",
        value.get("reference_round_trip"),
        frame_count,
        destination / "LosslessInputs" / "reference_ffv1.mkv",
    )

    results = value.get("results")
    if not isinstance(results, dict) or set(results) != {"CGVQM-2"}:
        reasons.append("results must contain exactly CGVQM-2")
    else:
        model = results["CGVQM-2"]
        if not isinstance(model, dict):
            reasons.append("CGVQM-2 result is malformed")
        else:
            score = model.get("score_higher_is_better")
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
            ):
                reasons.append("CGVQM-2 score is missing or non-finite")
            error_stats = model.get("error_map")
            expected_stat_names = {"mean", "p95", "p99", "maximum"}
            if (
                not isinstance(error_stats, dict)
                or set(error_stats) != expected_stat_names
                or any(
                    isinstance(stat, bool)
                    or not isinstance(stat, (int, float))
                    or not math.isfinite(stat)
                    for stat in (
                        error_stats.values()
                        if isinstance(error_stats, dict)
                        else ()
                    )
                )
            ):
                reasons.append("CGVQM-2 error-map statistics are malformed")
            expected_csv = destination / "CGVQM-2-PerFrame.csv"
            compare_exact(
                reasons,
                "CGVQM-2.per_frame_csv",
                model.get("per_frame_csv"),
                str(expected_csv),
            )
            if not expected_csv.is_file():
                reasons.append(f"CGVQM-2 per-frame CSV is missing: {expected_csv}")
            error_map = model.get("visualized_error_map")
            expected_error_map = destination / "CGVQM-2-ErrorMap.mkv"
            if skip_error_map_video:
                if error_map is not None:
                    compare_exact(
                        reasons,
                        "CGVQM-2.visualized_error_map",
                        error_map,
                        str(expected_error_map),
                    )
                    if not expected_error_map.is_file():
                        reasons.append(
                            "CGVQM-2 JSON names an error-map video that is "
                            f"missing: {expected_error_map}"
                        )
            else:
                compare_exact(
                    reasons,
                    "CGVQM-2.visualized_error_map",
                    error_map,
                    str(expected_error_map),
                )
                if not expected_error_map.is_file():
                    reasons.append(
                        f"CGVQM-2 visualized error map is missing: {expected_error_map}"
                    )

    return not reasons, reasons


def summarize_reasons(reasons: list[str], limit: int = 5) -> str:
    shown = reasons[:limit]
    suffix = f"; ... (+{len(reasons) - limit} more)" if len(reasons) > limit else ""
    return "; ".join(shown) + suffix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        nargs=4,
        action="append",
        required=True,
        metavar=(
            "SCENE",
            "CENTRAL_CAPTURE_ROOT",
            "TRANSITION_CAPTURE_ROOT",
            "REFERENCE_ROOT",
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--job-attempts", type=int, default=1)
    parser.add_argument("--skip-error-map-video", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.job_attempts <= 0:
        raise ValueError("--job-attempts must be positive")
    repo_root = Path(__file__).resolve().parents[2]
    runner = repo_root / "Tools" / "SMAA" / "run_cgvqm_png_sequences.py"
    cgvqm_root = repo_root / ".research-tools" / "CGVQM"
    if not cgvqm_root.is_dir():
        raise RuntimeError(f"missing official CGVQM checkout: {cgvqm_root}")

    cases: list[tuple[str, Path, Path, Path]] = []
    seen: set[str] = set()
    for raw_scene, raw_central, raw_transition, raw_reference in args.case:
        scene_key = raw_scene.lower()
        if scene_key not in {"bistro", "minecraft"} or scene_key in seen:
            raise RuntimeError(f"invalid or duplicate scene: {raw_scene}")
        seen.add(scene_key)
        scene = "Bistro" if scene_key == "bistro" else "Minecraft"
        cases.append(
            (
                scene,
                Path(raw_central).resolve(),
                Path(raw_transition).resolve(),
                Path(raw_reference).resolve(),
            )
        )
    if seen != {"bistro", "minecraft"}:
        raise RuntimeError("formal matrix requires Bistro and Minecraft")

    jobs: list[tuple[str, str, Path, Path, str, int, int]] = []
    for scene, central, transition, reference_root in cases:
        roots = {"central": central, "transition": transition}
        reference = reference_root / "SS_Reference"
        if not reference.is_dir():
            raise RuntimeError(f"missing reference input: {reference}")
        for window, root_key, reference_offset, frame_count in WINDOWS:
            capture_root = roots[root_key]
            for mode, directory in MODES:
                source = capture_root / directory
                if not source.is_dir():
                    raise RuntimeError(f"missing test input: {source}")
                jobs.append(
                    (
                        scene,
                        mode,
                        source,
                        reference,
                        window,
                        reference_offset,
                        frame_count,
                    )
                )

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    frame_cache: dict[Path, dict[int, Path]] = {}
    info_cache: dict[tuple[Path, tuple[int, ...]], dict[str, Any]] = {}
    for ordinal, (
        scene,
        mode,
        source,
        reference,
        window,
        reference_offset,
        frame_count,
    ) in enumerate(jobs, 1):
        destination = output / scene / window / mode
        result = destination / "CGVQM-Results.json"
        if result.is_file() and not args.force:
            valid, reasons = validate_existing_result(
                result,
                destination,
                scene,
                mode,
                source,
                reference,
                reference_offset,
                frame_count,
                cgvqm_root,
                args.skip_error_map_video,
                frame_cache,
                info_cache,
            )
            if valid:
                print(
                    f"[{ordinal}/{len(jobs)}] SKIP validated "
                    f"{scene}/{window}/{mode}",
                    flush=True,
                )
                continue
            print(
                f"[{ordinal}/{len(jobs)}] RERUN stale/malformed "
                f"{scene}/{window}/{mode}: {summarize_reasons(reasons)}",
                flush=True,
            )
        elif result.is_file():
            print(
                f"[{ordinal}/{len(jobs)}] RERUN --force "
                f"{scene}/{window}/{mode}",
                flush=True,
            )
        else:
            print(
                f"[{ordinal}/{len(jobs)}] RUN missing result "
                f"{scene}/{window}/{mode}",
                flush=True,
            )
        command = [
            sys.executable,
            str(runner),
            "--test-dir",
            str(source),
            "--reference-dir",
            str(reference),
            "--output-dir",
            str(destination),
            "--start-index",
            "0",
            "--reference-index-offset",
            str(reference_offset),
            "--frames",
            str(frame_count),
            "--model",
            "2",
            "--classification",
            "formal",
            "--scene",
            scene,
            "--camera-profile",
            PROFILE,
            "--test-mode",
            mode,
            "--reference-id",
            "SS-Reference",
            "--device",
            "cuda",
            "--patch-scale",
            "4",
            "--patch-pool",
            "mean",
        ]
        if args.skip_error_map_video:
            command.append("--skip-error-map-video")
        succeeded = False
        for attempt in range(1, args.job_attempts + 1):
            print(
                f"[{ordinal}/{len(jobs)}] START {scene}/{window}/{mode} "
                f"attempt={attempt}/{args.job_attempts}",
                flush=True,
            )
            return_code = subprocess.run(
                command, cwd=repo_root, check=False
            ).returncode
            if return_code == 0 and result.is_file():
                valid, reasons = validate_existing_result(
                    result,
                    destination,
                    scene,
                    mode,
                    source,
                    reference,
                    reference_offset,
                    frame_count,
                    cgvqm_root,
                    args.skip_error_map_video,
                    frame_cache,
                    info_cache,
                )
                if valid:
                    succeeded = True
                    break
                print(
                    f"[{ordinal}/{len(jobs)}] INVALID generated result "
                    f"{scene}/{window}/{mode}: {summarize_reasons(reasons)}",
                    flush=True,
                )
            if attempt < args.job_attempts:
                print(
                    f"[{ordinal}/{len(jobs)}] RETRY {scene}/{window}/{mode} "
                    f"returncode={return_code}",
                    flush=True,
                )
        if not succeeded:
            raise RuntimeError(
                f"job failed after {args.job_attempts} attempts: "
                f"{scene}/{window}/{mode}"
            )
        print(f"[{ordinal}/{len(jobs)}] PASS {scene}/{window}/{mode}", flush=True)
    print(f"PASS: completed or validated {len(jobs)}/{len(jobs)} CGVQM-2 jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
