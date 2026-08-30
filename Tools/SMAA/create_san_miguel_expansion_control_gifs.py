#!/usr/bin/env python3
"""Create slow visual-inspection GIFs for the San Miguel expansion controls."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


FRAME_PATTERN = re.compile(r"(?:^|_)frame_(\d+)$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("control_capture_root", type=Path)
    parser.add_argument("reference_capture_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-frames", type=int, default=60)
    parser.add_argument("--roi", type=int, nargs=4, default=(0, 500, 1050, 1017))
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--tile-width", type=int, default=420)
    parser.add_argument("--diff-gain", type=float, default=4.0)
    parser.add_argument("--arm-threshold", type=float, default=0.25)
    return parser.parse_args()


def frame_index(path: Path) -> int:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise RuntimeError(f"Invalid PNG filename: {path.name}")
    return int(match.group(1))


def collect(directory: Path, expected: int) -> list[Path]:
    paths = sorted(directory.glob("*.png"), key=frame_index)
    indices = [frame_index(path) for path in paths]
    if indices != list(range(expected)):
        raise RuntimeError(f"{directory}: expected 0..{expected - 1}, got {indices}")
    return paths


def load_crop(path: Path, roi: tuple[int, int, int, int]) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB").crop(roi)


def make_row(
    entries: list[tuple[str, Image.Image]], frame: int, tile_width: int,
) -> Image.Image:
    tile_height = max(2, round(entries[0][1].height * tile_width / entries[0][1].width))
    label_height = 40
    output = Image.new("RGB", (tile_width * len(entries), tile_height + label_height), "black")
    draw = ImageDraw.Draw(output)
    for column, (label, image) in enumerate(entries):
        tile = image.resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        x = column * tile_width
        output.paste(tile, (x, label_height))
        draw.text((x + 8, 8), label, fill="white")
    draw.text((output.width - 108, 23), f"frame {frame:05d}", fill=(255, 220, 80))
    return output


def save_gif(path: Path, frames: list[Image.Image], fps: int) -> None:
    duration = max(1, round(1000 / fps))
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )
    with Image.open(path) as image:
        if image.n_frames != len(frames):
            raise RuntimeError(f"GIF frame validation failed: {image.n_frames} != {len(frames)}")


def main() -> int:
    args = parse_args()
    if args.expected_frames < 1 or args.fps < 1 or args.tile_width < 1:
        raise RuntimeError("Frame count, FPS, and tile width must be positive")
    if not 0.0 <= args.arm_threshold <= 1.0:
        raise RuntimeError("--arm-threshold must be in [0,1]")
    roi = tuple(args.roi)
    control = args.control_capture_root.resolve()
    reference_root = args.reference_capture_root.resolve()
    reference_dir = reference_root / "SS_Reference"
    if not reference_dir.is_dir() and reference_root.name == "SS_Reference":
        reference_dir = reference_root
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    arm_label = f"O-ET2X-R ARM {args.arm_threshold:.2f}"
    paths = {
        "SS spatial reference": collect(reference_dir, args.expected_frames),
        "O-1X": collect(control / "O_1X", args.expected_frames),
        "O-T2X-R": collect(control / "O_T2X_R", args.expected_frames),
        "O-ET2X-R None": collect(control / "O_ET2X_R_Document", args.expected_frames),
        "O-ET2X-R 3x3": collect(control / "ABL_Document_Dilate3x3_R", args.expected_frames),
        arm_label: collect(control / "ABL_Document_ArmDual_R", args.expected_frames),
    }

    temporal_frames: list[Image.Image] = []
    expansion_frames: list[Image.Image] = []
    difference_frames: list[Image.Image] = []
    for frame in range(args.expected_frames):
        crops = {label: load_crop(sequence[frame], roi) for label, sequence in paths.items()}
        temporal_frames.append(make_row([
            ("O-1X", crops["O-1X"]),
            ("O-T2X-R", crops["O-T2X-R"]),
            ("O-ET2X-R None", crops["O-ET2X-R None"]),
        ], frame, args.tile_width))
        expansion_frames.append(make_row([
            ("SS spatial reference", crops["SS spatial reference"]),
            ("ET2X-R None", crops["O-ET2X-R None"]),
            ("ET2X-R 3x3", crops["O-ET2X-R 3x3"]),
            (f"ET2X-R ARM {args.arm_threshold:.2f}", crops[arm_label]),
        ], frame, args.tile_width))

        reference = np.asarray(crops["SS spatial reference"], dtype=np.int16)
        difference_entries: list[tuple[str, Image.Image]] = []
        for label in ("O-ET2X-R None", "O-ET2X-R 3x3", arm_label):
            current = np.asarray(crops[label], dtype=np.int16)
            difference = np.clip(np.abs(current - reference) * args.diff_gain, 0, 255).astype(np.uint8)
            difference_entries.append((f"{label} | diff x{args.diff_gain:g}", Image.fromarray(difference)))
        difference_frames.append(make_row(difference_entries, frame, args.tile_width))

    files = {
        "temporal_control": output / "sanmiguel_O1X_T2XR_ET2XNone_10fps.gif",
        "candidate_expansion": output / "sanmiguel_reference_None_3x3_ARM_10fps.gif",
        "reference_difference": output / "sanmiguel_reference_difference_x4_None_3x3_ARM_10fps.gif",
    }
    save_gif(files["temporal_control"], temporal_frames, args.fps)
    save_gif(files["candidate_expansion"], expansion_frames, args.fps)
    save_gif(files["reference_difference"], difference_frames, args.fps)
    manifest = {
        "classification": "slow visual-inspection media; not a replacement for formal metrics",
        "control_capture_root": str(control),
        "reference_capture_root": str(reference_root),
        "frames": args.expected_frames,
        "fps": args.fps,
        "duration_seconds": args.expected_frames / args.fps,
        "roi": roi,
        "arm_threshold": args.arm_threshold,
        "files": {key: str(path) for key, path in files.items()},
    }
    (output / "sanmiguel_expansion_control_gifs.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
