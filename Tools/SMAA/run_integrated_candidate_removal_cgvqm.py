#!/usr/bin/env python3
"""Run the formal CGVQM-2 matrix for integrated candidate removal.

Runs are deliberately sequential because the official CGVQM implementation
loads complete clips into memory.  Existing completed result JSON files can be
resumed without rerunning earlier modes.
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
    ("O-ET2X [removal=0.50]", "O_ET2X_Removal_050"),
    ("O-ET2X [removal=0.70]", "O_ET2X_Removal_070"),
    ("O-ET2X [removal=0.75]", "O_ET2X_Removal_075"),
    ("O-T2X-R", "O_T2X_R"),
    ("O-ET2X-R [removal=0.50]", "O_ET2X_R_Removal_050"),
    ("O-ET2X-R [removal=0.70]", "O_ET2X_R_Removal_070"),
    ("O-ET2X-R [removal=0.75]", "O_ET2X_R_Removal_075"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 36 formal sequential CGVQM-2 jobs")
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        required=True,
        metavar=("SCENE", "CAPTURE_ROOT", "REFERENCE_ROOT"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-error-map-video", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    runner = repo_root / "Tools" / "SMAA" / "run_cgvqm_png_sequences.py"
    output = args.output.resolve()
    jobs: list[tuple[str, Path, Path, str, int, int, str, str]] = []
    seen: set[str] = set()
    for scene, capture_root, reference_root in args.case:
        scene_key = scene.lower()
        if scene_key not in {"bistro", "minecraft"}:
            raise RuntimeError(f"Unsupported scene: {scene}")
        if scene_key in seen:
            raise RuntimeError(f"Duplicate scene: {scene}")
        seen.add(scene_key)
        scene_label = "Bistro" if scene_key == "bistro" else "Minecraft"
        capture = Path(capture_root).resolve()
        reference = Path(reference_root).resolve() / "SS_Reference"
        for window, (start, count) in WINDOWS.items():
            for mode_label, directory in MODES:
                jobs.append(
                    (scene_label, capture, reference, window, start, count, mode_label, directory)
                )

    output.mkdir(parents=True, exist_ok=True)
    for index, (scene, capture, reference, window, start, count, mode, directory) in enumerate(jobs, 1):
        destination = output / scene / window / directory
        result = destination / "CGVQM-Results.json"
        if result.is_file() and not args.force:
            print(f"[{index}/{len(jobs)}] SKIP existing {scene}/{window}/{mode}", flush=True)
            continue
        command = [
            sys.executable,
            str(runner),
            "--test-dir", str(capture / directory),
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
        print(f"[{index}/{len(jobs)}] START {scene}/{window}/{mode}", flush=True)
        subprocess.run(command, cwd=repo_root, check=True)
        if not result.is_file():
            raise RuntimeError(f"Missing completed result: {result}")
        print(f"[{index}/{len(jobs)}] PASS {scene}/{window}/{mode}", flush=True)
    print(f"PASS: completed or validated {len(jobs)} sequential CGVQM-2 jobs", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
