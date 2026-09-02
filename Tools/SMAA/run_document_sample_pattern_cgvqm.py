#!/usr/bin/env python3
"""Run/resume formal CGVQM-2 for the full-screen document Pattern-On control."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROFILE = "flythrough-wide-yaw-360"
MODE = "ABL-Document-FullScreen-PatternOn-R"
DIRECTORY = "ABL_Document_FullScreen_PatternOn_R"
WINDOWS = {
    "central_motion_00150_00329": (150, 180),
    "transition_00410_00439": (410, 30),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        required=True,
        metavar=("SCENE", "CAPTURE_ROOT", "REFERENCE_ROOT"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--job-attempts", type=int, default=3)
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

    jobs: list[tuple[str, Path, Path, str, int, int]] = []
    seen: set[str] = set()
    for raw_scene, raw_capture, raw_reference in args.case:
        scene_key = raw_scene.lower()
        if scene_key not in {"bistro", "minecraft"} or scene_key in seen:
            raise RuntimeError(f"invalid or duplicate scene: {raw_scene}")
        seen.add(scene_key)
        scene = "Bistro" if scene_key == "bistro" else "Minecraft"
        source = Path(raw_capture).resolve() / DIRECTORY
        reference = Path(raw_reference).resolve() / "SS_Reference"
        if not source.is_dir() or not reference.is_dir():
            raise RuntimeError(f"missing input: {source} or {reference}")
        for window, (start, count) in WINDOWS.items():
            jobs.append((scene, source, reference, window, start, count))
    if seen != {"bistro", "minecraft"}:
        raise RuntimeError("formal matrix requires Bistro and Minecraft")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for ordinal, (scene, source, reference, window, start, count) in enumerate(jobs, 1):
        destination = output / scene / window / DIRECTORY
        result = destination / "CGVQM-Results.json"
        if result.is_file() and not args.force:
            print(f"[{ordinal}/{len(jobs)}] SKIP existing {scene}/{window}/{MODE}", flush=True)
            continue
        command = [
            sys.executable,
            str(runner),
            "--test-dir", str(source),
            "--reference-dir", str(reference),
            "--output-dir", str(destination),
            "--start-index", str(start),
            "--frames", str(count),
            "--model", "2",
            "--classification", "formal",
            "--scene", scene,
            "--camera-profile", PROFILE,
            "--test-mode", MODE,
            "--reference-id", "SS-Reference",
            "--device", "cuda",
            "--patch-scale", "4",
            "--patch-pool", "mean",
        ]
        if args.skip_error_map_video:
            command.append("--skip-error-map-video")
        succeeded = False
        for attempt in range(1, args.job_attempts + 1):
            print(
                f"[{ordinal}/{len(jobs)}] START {scene}/{window}/{MODE} "
                f"attempt={attempt}/{args.job_attempts}",
                flush=True,
            )
            return_code = subprocess.run(command, cwd=repo_root, check=False).returncode
            if return_code == 0 and result.is_file():
                succeeded = True
                break
            print(
                f"[{ordinal}/{len(jobs)}] RETRY {scene}/{window}/{MODE} "
                f"returncode={return_code}",
                flush=True,
            )
        if not succeeded:
            raise RuntimeError(
                f"job failed after {args.job_attempts} attempts: {scene}/{window}/{MODE}"
            )
        print(f"[{ordinal}/{len(jobs)}] PASS {scene}/{window}/{MODE}", flush=True)
    print(f"PASS: completed or validated {len(jobs)}/{len(jobs)} CGVQM-2 jobs", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
