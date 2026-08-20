#!/usr/bin/env python3
"""Create constant-frame-rate playback videos from camera-motion PNG captures.

The PNG capture path intentionally advances a fixed 60 Hz simulation while
writing each frame synchronously.  The live application window can therefore
look much slower than the recorded sequence.  This tool reconstructs the
recorded timeline as a presentation-oriented H.264/MP4 at exactly 60 fps.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable

import av
import numpy as np
from PIL import Image, ImageDraw


FRAME_PATTERN = re.compile(r"_frame_(\d+)\.png$", re.IGNORECASE)
MODE_LABELS = {
    "O_1X": "O-1X",
    "O_T2X": "O-T2X",
    "O_T2X_R": "O-T2X-R",
    "O_ET2X": "O-ET2X",
    "O_ET2X_R": "O-ET2X-R",
    "A_1X": "A-1X",
    "A_T2X": "A-T2X",
    "A_T2X_R": "A-T2X-R",
    "A_ET2X": "A-ET2X",
    "A_ET2X_R": "A-ET2X-R",
}


@dataclass(frozen=True)
class Sequence:
    mode: str
    label: str
    paths: list[Path]
    indices: list[int]
    width: int
    height: int


@dataclass(frozen=True)
class VideoValidation:
    path: str
    codec: str
    pixel_format: str
    width: int
    height: int
    frame_count: int
    average_rate: str
    time_base: str
    pts_step: int
    pts_step_seconds: float
    duration_seconds: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a single-mode and a labeled comparison MP4 from a "
            "deterministic SMAA camera-motion PNG capture."
        )
    )
    parser.add_argument("capture_root", type=Path)
    parser.add_argument(
        "--single-mode",
        default="O_1X",
        choices=sorted(MODE_LABELS),
        help="Mode used for the full-resolution camera-path playback.",
    )
    parser.add_argument(
        "--compare-modes",
        nargs="+",
        default=["O_1X", "O_T2X", "O_ET2X_R"],
        choices=sorted(MODE_LABELS),
        help="Modes shown left-to-right in the comparison playback.",
    )
    parser.add_argument(
        "--single-only",
        action="store_true",
        help="Create and validate only the full-resolution single-mode playback.",
    )
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--tile-width", type=int, default=640)
    parser.add_argument("--crf", type=int, default=16)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing output videos and refresh metadata without encoding.",
    )
    return parser.parse_args()


def frame_index(path: Path) -> int:
    match = FRAME_PATTERN.search(path.name)
    if match is None:
        raise ValueError(f"Invalid camera-motion PNG filename: {path.name}")
    return int(match.group(1))


def load_sequence(root: Path, mode: str) -> Sequence:
    directory = root / mode
    if not directory.is_dir():
        raise FileNotFoundError(f"Missing mode directory: {directory}")
    indexed = sorted(
        ((frame_index(path), path) for path in directory.glob("*.png")),
        key=lambda item: item[0],
    )
    if not indexed:
        raise ValueError(f"No PNG frames found in {directory}")
    indices = [index for index, _ in indexed]
    expected = list(range(indices[0], indices[0] + len(indices)))
    if indices != expected:
        raise ValueError(
            f"Non-contiguous frame indices in {directory}: "
            f"{indices[0]}..{indices[-1]} over {len(indices)} files"
        )
    paths = [path for _, path in indexed]
    with Image.open(paths[0]) as image:
        width, height = image.size
    for path in paths[1:]:
        with Image.open(path) as image:
            if image.size != (width, height):
                raise ValueError(
                    f"Resolution changed at {path.name}: "
                    f"{image.size} != {(width, height)}"
                )
    return Sequence(
        mode=mode,
        label=MODE_LABELS[mode],
        paths=paths,
        indices=indices,
        width=width,
        height=height,
    )


def even(value: int) -> int:
    return value if value % 2 == 0 else value + 1


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def pad_even_rgb(pixels: np.ndarray) -> np.ndarray:
    height, width = pixels.shape[:2]
    target_height = even(height)
    target_width = even(width)
    if (target_width, target_height) == (width, height):
        return pixels
    padded = np.empty((target_height, target_width, 3), dtype=np.uint8)
    padded[:height, :width] = pixels
    if target_width != width:
        padded[:height, width:] = pixels[:, width - 1 : width]
    if target_height != height:
        padded[height:, :] = padded[height - 1 : height, :]
    return padded


def render_single(sequence: Sequence, ordinal: int) -> np.ndarray:
    return pad_even_rgb(load_rgb(sequence.paths[ordinal]))


def make_comparison_renderer(
    sequences: list[Sequence], tile_width: int
) -> tuple[Callable[[int], np.ndarray], int, int]:
    source_width = sequences[0].width
    source_height = sequences[0].height
    tile_height = max(1, round(source_height * tile_width / source_width))
    label_height = 30
    output_width = even(tile_width * len(sequences))
    output_height = even(label_height + tile_height)

    def render(ordinal: int) -> np.ndarray:
        canvas = Image.new("RGB", (output_width, output_height), "black")
        draw = ImageDraw.Draw(canvas)
        for column, sequence in enumerate(sequences):
            x = column * tile_width
            draw.text(
                (x + 8, 8),
                f"{sequence.label}  frame {sequence.indices[ordinal]:05d}",
                fill="white",
            )
            with Image.open(sequence.paths[ordinal]) as image:
                tile = image.convert("RGB").resize(
                    (tile_width, tile_height), Image.Resampling.LANCZOS
                )
            canvas.paste(tile, (x, label_height))
        return np.asarray(canvas, dtype=np.uint8)

    return render, output_width, output_height


def encode_h264(
    output: Path,
    frame_count: int,
    fps: int,
    width: int,
    height: int,
    render: Callable[[int], np.ndarray],
    crf: int,
    preset: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(output), mode="w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=Fraction(fps, 1))
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"
        stream.time_base = Fraction(1, fps)
        stream.options = {
            "crf": str(crf),
            "preset": preset,
            "movflags": "+faststart",
        }
        for ordinal in range(frame_count):
            pixels = render(ordinal)
            if pixels.shape != (height, width, 3) or pixels.dtype != np.uint8:
                raise ValueError(
                    f"Rendered frame {ordinal} has invalid shape/type: "
                    f"{pixels.shape}, {pixels.dtype}"
                )
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = ordinal
            frame.time_base = Fraction(1, fps)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def validate_video(path: Path, expected_frames: int, expected_fps: int) -> VideoValidation:
    decoded_frames = 0
    previous_pts: int | None = None
    pts_steps: set[int] = set()
    first_pts: int | None = None
    last_pts: int | None = None
    with av.open(str(path), mode="r") as container:
        stream = container.streams.video[0]
        average_rate = stream.average_rate
        if average_rate is None or Fraction(average_rate) != Fraction(expected_fps, 1):
            raise ValueError(
                f"Unexpected average rate in {path}: {average_rate} != {expected_fps}"
            )
        for frame in container.decode(video=0):
            if frame.pts is None:
                raise ValueError(f"Decoded frame has no PTS in {path}")
            if previous_pts is not None and frame.pts <= previous_pts:
                raise ValueError(f"Non-increasing PTS in {path}")
            if previous_pts is not None:
                pts_steps.add(frame.pts - previous_pts)
            first_pts = frame.pts if first_pts is None else first_pts
            last_pts = frame.pts
            previous_pts = frame.pts
            decoded_frames += 1
        if decoded_frames != expected_frames:
            raise ValueError(
                f"Decoded frame count {decoded_frames} != {expected_frames}: {path}"
            )
        if first_pts is None or last_pts is None:
            raise ValueError(f"No decoded frames in {path}")
        if expected_frames > 1:
            if len(pts_steps) != 1:
                raise ValueError(
                    f"Non-constant PTS step in {path}: {sorted(pts_steps)}"
                )
            pts_step = next(iter(pts_steps))
            pts_step_seconds = float(pts_step * stream.time_base)
            if abs(pts_step_seconds - 1.0 / expected_fps) > 1e-9:
                raise ValueError(
                    f"PTS step in {path} is {pts_step_seconds:.12f}s, "
                    f"expected {1.0 / expected_fps:.12f}s"
                )
        else:
            pts_step = 0
            pts_step_seconds = 0.0
        duration_seconds = decoded_frames / float(expected_fps)
        return VideoValidation(
            path=str(path.resolve()),
            codec=stream.codec_context.name,
            pixel_format=stream.codec_context.pix_fmt,
            width=stream.codec_context.width,
            height=stream.codec_context.height,
            frame_count=decoded_frames,
            average_rate=str(average_rate),
            time_base=str(stream.time_base),
            pts_step=pts_step,
            pts_step_seconds=pts_step_seconds,
            duration_seconds=duration_seconds,
        )


def validate_aligned(sequences: Iterable[Sequence]) -> tuple[int, list[int]]:
    sequences = list(sequences)
    reference = sequences[0]
    for sequence in sequences[1:]:
        if sequence.indices != reference.indices:
            raise ValueError(
                f"Frame indices differ: {sequence.mode} != {reference.mode}"
            )
        if (sequence.width, sequence.height) != (
            reference.width,
            reference.height,
        ):
            raise ValueError(
                f"Resolution differs: {sequence.mode} != {reference.mode}"
            )
    return len(reference.paths), reference.indices


def main() -> int:
    args = parse_args()
    if args.fps <= 0 or args.tile_width <= 0:
        raise ValueError("fps and tile width must be positive")
    if not 0 <= args.crf <= 51:
        raise ValueError("CRF must be between 0 and 51")

    capture_root = args.capture_root.resolve()
    output = (args.output or (capture_root / "Playback60fps")).resolve()
    requested_modes = list(
        dict.fromkeys(
            [args.single_mode]
            if args.single_only
            else [args.single_mode, *args.compare_modes]
        )
    )
    loaded = {mode: load_sequence(capture_root, mode) for mode in requested_modes}
    frame_count, indices = validate_aligned(loaded.values())

    single = loaded[args.single_mode]
    single_width = even(single.width)
    single_height = even(single.height)
    single_path = output / f"{single.mode}_camera_path_60fps.mp4"

    comparison: list[Sequence] = []
    comparison_path: Path | None = None
    if not args.single_only:
        comparison = [loaded[mode] for mode in args.compare_modes]
        comparison_render, comparison_width, comparison_height = (
            make_comparison_renderer(comparison, args.tile_width)
        )
        comparison_name = "_vs_".join(sequence.mode for sequence in comparison)
        comparison_path = output / f"{comparison_name}_comparison_60fps.mp4"
    if args.validate_only:
        expected_paths = [single_path]
        if comparison_path is not None:
            expected_paths.append(comparison_path)
        for path in expected_paths:
            if not path.is_file():
                raise FileNotFoundError(f"Missing playback video: {path}")
    else:
        encode_h264(
            single_path,
            frame_count,
            args.fps,
            single_width,
            single_height,
            lambda ordinal: render_single(single, ordinal),
            args.crf,
            args.preset,
        )
        if comparison_path is not None:
            encode_h264(
                comparison_path,
                frame_count,
                args.fps,
                comparison_width,
                comparison_height,
                comparison_render,
                args.crf,
                args.preset,
            )

    validations = [validate_video(single_path, frame_count, args.fps)]
    if comparison_path is not None:
        validations.append(validate_video(comparison_path, frame_count, args.fps))
    metadata = {
        "classification": "presentation_playback_not_quality_measurement",
        "capture_root": str(capture_root),
        "source_frame_count": frame_count,
        "source_first_index": indices[0],
        "source_last_index": indices[-1],
        "fps": args.fps,
        "single_mode": single.label,
        "comparison_modes": [sequence.label for sequence in comparison],
        "h264": {"crf": args.crf, "preset": args.preset, "pixel_format": "yuv420p"},
        "videos": [validation.__dict__ for validation in validations],
        "note": (
            "These MP4 files are for real-time visual inspection. Formal metrics "
            "continue to use the original PNG/FFV1 sequences."
        ),
    }
    metadata_path = output / "camera_motion_playback.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"SINGLE={single_path}")
    if comparison_path is not None:
        print(f"COMPARISON={comparison_path}")
    print(f"METADATA={metadata_path}")
    print(
        f"VALIDATION=PASS frames={frame_count} fps={args.fps} "
        f"duration={frame_count / args.fps:.3f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
