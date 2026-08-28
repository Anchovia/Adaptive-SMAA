#!/usr/bin/env python3
"""Run/resume the formal CGVQM-2 matrix for final 8-case wide captures.

Jobs are sequential because the official implementation holds complete clips
and error maps in CPU/GPU memory.  Completed result JSON files are resumable.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROFILE = "flythrough-wide-yaw-360"
WINDOWS = {
    "central_motion_00150_00329": (150, 180),
    "transition_00410_00439": (410, 30),
}
MODES = (
    ("O-1X", "O_1X"),
    ("O-T2X", "O_T2X"),
    ("O-T2X-R", "O_T2X_R"),
    ("O-ET2X", "O_ET2X"),
    ("O-ET2X-R", "O_ET2X_R"),
    ("A-1X", "A_1X"),
    ("A-T2X", "A_T2X"),
    ("A-T2X-R", "A_T2X_R"),
    ("A-ET2X", "A_ET2X"),
    ("A-ET2X-R", "A_ET2X_R"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", nargs=3, action="append", required=True,
        metavar=("SCENE", "CAPTURE_ROOT", "REFERENCE_ROOT"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-error-map-video", action="store_true")
    parser.add_argument(
        "--job-attempts", type=int, default=3,
        help="Fresh process/encode attempts per incomplete job.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.job_attempts <= 0:
        raise ValueError("--job-attempts must be positive")
    repo_root = Path(__file__).resolve().parents[2]
    runner = repo_root / "Tools" / "SMAA" / "run_cgvqm_png_sequences.py"
    cgvqm_root = repo_root / ".research-tools" / "CGVQM"
    if not cgvqm_root.is_dir():
        raise RuntimeError(f"Missing official CGVQM checkout: {cgvqm_root}")
    output = args.output.resolve()
    jobs: list[tuple[str, Path, Path, str, int, int, str, str]] = []
    seen: set[str] = set()
    for raw_scene, raw_capture, raw_reference in args.case:
        scene_key = raw_scene.lower()
        if scene_key not in {"bistro", "minecraft"}:
            raise RuntimeError(f"Unsupported scene: {raw_scene}")
        if scene_key in seen:
            raise RuntimeError(f"Duplicate scene: {raw_scene}")
        seen.add(scene_key)
        scene = "Bistro" if scene_key == "bistro" else "Minecraft"
        capture = Path(raw_capture).resolve()
        reference = Path(raw_reference).resolve() / "SS_Reference"
        for window, (start, count) in WINDOWS.items():
            for mode, directory in MODES:
                source = capture / directory
                if not source.is_dir() or not reference.is_dir():
                    raise RuntimeError(f"Missing input: {source} or {reference}")
                jobs.append((scene, source, reference, window, start, count, mode, directory))
    if seen != {"bistro", "minecraft"}:
        raise RuntimeError("Formal matrix requires Bistro and Minecraft")

    output.mkdir(parents=True, exist_ok=True)
    completed = 0
    for ordinal, (scene, source, reference, window, start, count, mode, directory) in enumerate(jobs, 1):
        destination = output / scene / window / directory
        result = destination / "CGVQM-Results.json"
        if result.is_file() and not args.force:
            print(f"[{ordinal}/{len(jobs)}] SKIP existing {scene}/{window}/{mode}", flush=True)
            completed += 1
            continue
        command = [
            sys.executable, str(runner),
            "--test-dir", str(source),
            "--reference-dir", str(reference),
            "--output-dir", str(destination),
            "--start-index", str(start),
            "--frames", str(count),
            "--model", "2",
            "--classification", "formal",
            "--scene", scene,
            "--camera-profile", PROFILE,
            "--test-mode", mode,
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
                f"[{ordinal}/{len(jobs)}] START {scene}/{window}/{mode} "
                f"attempt={attempt}/{args.job_attempts}",
                flush=True,
            )
            result_code = subprocess.run(command, cwd=repo_root, check=False).returncode
            if result_code == 0 and result.is_file():
                succeeded = True
                break
            print(
                f"[{ordinal}/{len(jobs)}] RETRY {scene}/{window}/{mode} "
                f"returncode={result_code}",
                flush=True,
            )
        if not succeeded:
            raise RuntimeError(
                f"Job failed after {args.job_attempts} fresh encode attempts: "
                f"{scene}/{window}/{mode}"
            )
        if not result.is_file():
            raise RuntimeError(f"Missing completed result: {result}")
        completed += 1
        print(f"[{ordinal}/{len(jobs)}] PASS {scene}/{window}/{mode}", flush=True)
    print(f"PASS: completed or validated {completed}/{len(jobs)} sequential CGVQM-2 jobs", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
