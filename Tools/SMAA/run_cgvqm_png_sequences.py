#!/usr/bin/env python3
"""Run Intel CGVQM on two frame-aligned PNG sequences.

The official CGVQM implementation currently accepts video files. This adapter
validates CMAA2 PNG captures, converts the selected frames to lossless
RGB-preserving FFV1/Matroska videos, verifies the decoded pixels, and then calls
the unmodified official CGVQM implementation.

CGVQM is a full-reference perceptual video metric. Its result must be reported
with the supersample-reference definition and other temporal/visual evidence;
it is not an absolute ghosting ground truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import chain
from pathlib import Path
from typing import Iterable

import av
import numpy as np
from PIL import Image
import torch


FRAME_PATTERN = re.compile(r"(?:^|_)frame_(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class SequenceInfo:
    directory: str
    frame_count: int
    first_index: int
    last_index: int
    width: int
    height: int
    pixel_sha256: str


@dataclass(frozen=True)
class RoundTripInfo:
    video: str
    codec: str
    pixel_format: str
    decoded_frames: int
    mismatched_values: int
    max_absolute_difference: int


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description=(
            "Validate two aligned PNG sequences, encode losslessly, and run "
            "the official Intel CGVQM implementation."
        )
    )
    parser.add_argument("--test-dir", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--cgvqm-root",
        type=Path,
        default=repo_root / ".research-tools" / "CGVQM",
        help="Path to a clone of https://github.com/IntelLabs/CGVQM.",
    )
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--start-index", type=int)
    parser.add_argument(
        "--frames",
        type=int,
        help="Limit the aligned sequence to this many frames after start-index.",
    )
    parser.add_argument(
        "--model",
        choices=("2", "5", "both"),
        default="2",
        help="CGVQM model depth. CGVQM-2 is the default integration smoke.",
    )
    parser.add_argument(
        "--classification",
        choices=("engineering", "formal"),
        default="engineering",
        help="Research classification recorded in the result provenance.",
    )
    parser.add_argument("--scene", help="Scene provenance, for example Bistro.")
    parser.add_argument(
        "--camera-profile",
        help="Camera-path provenance, for example yaw-fast-360.",
    )
    parser.add_argument("--test-mode", help="Semantic SMAA test ID.")
    parser.add_argument(
        "--reference-id",
        default="SS-Reference",
        help="Reference profile ID recorded in the result provenance.",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
    )
    parser.add_argument("--patch-scale", type=int, default=4)
    parser.add_argument("--patch-pool", choices=("mean", "max"), default="mean")
    parser.add_argument(
        "--skip-error-map-video",
        action="store_true",
        help="Do not write the official-colorized lossless error-map MKV.",
    )
    return parser.parse_args()


def frame_index(path: Path) -> int:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise ValueError(
            f"PNG filename does not end in '_frame_<index>': {path.name}"
        )
    return int(match.group(1))


def collect_frames(directory: Path) -> dict[int, Path]:
    if not directory.is_dir():
        raise FileNotFoundError(f"Frame directory does not exist: {directory}")
    indexed: dict[int, Path] = {}
    for path in directory.glob("*.png"):
        index = frame_index(path)
        if index in indexed:
            raise ValueError(
                f"Duplicate frame index {index}: {indexed[index]} and {path}"
            )
        indexed[index] = path
    if not indexed:
        raise ValueError(f"No PNG frames found in: {directory}")
    return indexed


def select_aligned_frames(
    test_frames: dict[int, Path],
    reference_frames: dict[int, Path],
    start_index: int | None,
    count: int | None,
) -> tuple[list[int], list[Path], list[Path]]:
    test_indices = set(test_frames)
    reference_indices = set(reference_frames)
    if test_indices != reference_indices:
        test_only = sorted(test_indices - reference_indices)[:8]
        reference_only = sorted(reference_indices - test_indices)[:8]
        raise ValueError(
            "Test/reference frame indices differ: "
            f"test-only={test_only}, reference-only={reference_only}"
        )

    indices = sorted(test_indices)
    if start_index is not None:
        indices = [index for index in indices if index >= start_index]
    if count is not None:
        if count <= 0:
            raise ValueError("--frames must be positive")
        indices = indices[:count]
    if not indices:
        raise ValueError("Frame selection is empty")

    expected = list(range(indices[0], indices[-1] + 1))
    if indices != expected:
        missing = sorted(set(expected) - set(indices))[:8]
        raise ValueError(f"Selected frame indices are not contiguous: {missing}")

    return (
        indices,
        [test_frames[index] for index in indices],
        [reference_frames[index] for index in indices],
    )


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"Expected RGB image: {path}")
    return rgb


def inspect_sequence(directory: Path, paths: list[Path], indices: list[int]) -> SequenceInfo:
    digest = hashlib.sha256()
    width = -1
    height = -1
    for index, path in zip(indices, paths, strict=True):
        pixels = load_rgb(path)
        current_height, current_width = pixels.shape[:2]
        if width < 0:
            width = current_width
            height = current_height
        elif (current_width, current_height) != (width, height):
            raise ValueError(
                f"Resolution changed at frame {index}: "
                f"{current_width}x{current_height} != {width}x{height}"
            )
        digest.update(index.to_bytes(8, "little", signed=False))
        digest.update(pixels.tobytes())
    return SequenceInfo(
        directory=str(directory.resolve()),
        frame_count=len(paths),
        first_index=indices[0],
        last_index=indices[-1],
        width=width,
        height=height,
        pixel_sha256=digest.hexdigest(),
    )


def encode_ffv1(paths: Iterable[Path], output: Path, fps: int) -> tuple[str, str]:
    paths = list(paths)
    first = load_rgb(paths[0])
    height, width = first.shape[:2]
    output.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(output), mode="w", format="matroska") as container:
        stream = container.add_stream("ffv1", rate=fps)
        stream.width = width
        stream.height = height
        # FFV1 with BGR0 stays in an RGB-family pixel format and avoids a
        # lossy RGB<->limited-range YUV conversion.
        stream.pix_fmt = "bgr0"
        stream.time_base = Fraction(1, fps)
        for ordinal, path in enumerate(paths):
            pixels = first if ordinal == 0 else load_rgb(path)
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = ordinal
            frame.time_base = Fraction(1, fps)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return "ffv1", "bgr0"


def encode_rgb_arrays_ffv1(
    frames: Iterable[np.ndarray],
    output: Path,
    fps: int,
) -> tuple[str, str]:
    iterator = iter(frames)
    try:
        first = next(iterator)
    except StopIteration as error:
        raise ValueError("Cannot encode an empty frame sequence") from error
    if first.dtype != np.uint8 or first.ndim != 3 or first.shape[2] != 3:
        raise ValueError("Expected uint8 RGB frames")
    height, width = first.shape[:2]
    output.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(output), mode="w", format="matroska") as container:
        stream = container.add_stream("ffv1", rate=fps)
        stream.width = width
        stream.height = height
        stream.pix_fmt = "bgr0"
        stream.time_base = Fraction(1, fps)
        for ordinal, pixels in enumerate(chain((first,), iterator)):
            if pixels.dtype != np.uint8 or pixels.shape != first.shape:
                raise ValueError(
                    f"RGB frame {ordinal} shape/type differs from the first frame"
                )
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = ordinal
            frame.time_base = Fraction(1, fps)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return "ffv1", "bgr0"


def verify_round_trip(
    paths: list[Path],
    video_path: Path,
    codec: str,
    pixel_format: str,
) -> RoundTripInfo:
    mismatched_values = 0
    max_absolute_difference = 0
    decoded_frames = 0
    with av.open(str(video_path), mode="r") as container:
        for ordinal, frame in enumerate(container.decode(video=0)):
            if ordinal >= len(paths):
                raise ValueError(f"Encoded video has extra frame {ordinal}: {video_path}")
            decoded = frame.to_ndarray(format="rgb24")
            expected = load_rgb(paths[ordinal])
            if decoded.shape != expected.shape:
                raise ValueError(
                    f"Decoded shape mismatch at {ordinal}: "
                    f"{decoded.shape} != {expected.shape}"
                )
            difference = np.abs(decoded.astype(np.int16) - expected.astype(np.int16))
            mismatched_values += int(np.count_nonzero(difference))
            max_absolute_difference = max(
                max_absolute_difference, int(difference.max(initial=0))
            )
            decoded_frames += 1
    if decoded_frames != len(paths):
        raise ValueError(
            f"Decoded frame count {decoded_frames} != expected {len(paths)}"
        )
    if mismatched_values != 0:
        raise ValueError(
            "Lossless round-trip validation failed: "
            f"{mismatched_values} channel values differ, "
            f"max difference={max_absolute_difference}"
        )
    return RoundTripInfo(
        video=str(video_path.resolve()),
        codec=codec,
        pixel_format=pixel_format,
        decoded_frames=decoded_frames,
        mismatched_values=mismatched_values,
        max_absolute_difference=max_absolute_difference,
    )


def git_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={root.resolve().as_posix()}",
                "-C",
                str(root),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def import_cgvqm(root: Path):
    if not (root / "cgvqm.py").is_file():
        raise FileNotFoundError(f"CGVQM root is invalid: {root}")
    sys.path.insert(0, str(root.resolve()))
    return importlib.import_module("cgvqm")


def write_error_map_video(
    cgvqm_root: Path,
    emap: torch.Tensor,
    test_paths: list[Path],
    output_path: Path,
    fps: int,
) -> None:
    # Reuse the official CGVQM/FovVideoVDP color mapping, but encode it as
    # RGB-family FFV1. The official helper forces libx264/yuv420p, which rejects
    # CMAA2's 1920x1017 capture size because its height is odd.
    sys.path.insert(0, str(cgvqm_root.resolve()))
    utils_module = importlib.import_module("utils.utils")
    context = torch.from_numpy(
        np.stack([load_rgb(path) for path in test_paths], axis=0)
    ).permute(0, 3, 1, 2)
    normalized = torch.clamp(emap.detach().float().cpu() / 100.0, 0.0, 1.0)
    heatmap = utils_module.visualize_diff_map(
        normalized.unsqueeze(1),
        context_image=context,
        type="pmap",
        colormap_type="threshold",
    )
    heatmap_rgb = (
        (heatmap.clamp(0.0, 1.0) * 255.0)
        .to(torch.uint8)
        .permute(0, 2, 3, 1)
        .contiguous()
        .numpy()
    )
    encode_rgb_arrays_ffv1(heatmap_rgb, output_path, fps)


def error_map_stats(emap: torch.Tensor) -> tuple[dict[str, float], list[dict[str, float]]]:
    values = emap.detach().float().cpu().numpy()
    aggregate = {
        "mean": float(np.mean(values)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "maximum": float(np.max(values)),
    }
    per_frame: list[dict[str, float]] = []
    for ordinal, frame_values in enumerate(values):
        per_frame.append(
            {
                "ordinal": ordinal,
                "mean": float(np.mean(frame_values)),
                "p95": float(np.percentile(frame_values, 95)),
                "p99": float(np.percentile(frame_values, 99)),
                "maximum": float(np.max(frame_values)),
            }
        )
    return aggregate, per_frame


def write_frame_stats(
    path: Path,
    frame_indices: list[int],
    rows: list[dict[str, float]],
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("frame_index", "mean", "p95", "p99", "maximum"),
        )
        writer.writeheader()
        for frame_index_value, row in zip(frame_indices, rows, strict=True):
            writer.writerow(
                {
                    "frame_index": frame_index_value,
                    "mean": row["mean"],
                    "p95": row["p95"],
                    "p99": row["p99"],
                    "maximum": row["maximum"],
                }
            )


def main() -> int:
    args = parse_args()
    if args.fps <= 0:
        raise ValueError("--fps must be positive")
    if args.patch_scale <= 0:
        raise ValueError("--patch-scale must be positive")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    input_dir = output_dir / "LosslessInputs"
    input_dir.mkdir(parents=True, exist_ok=True)

    test_by_index = collect_frames(args.test_dir.resolve())
    reference_by_index = collect_frames(args.reference_dir.resolve())
    indices, test_paths, reference_paths = select_aligned_frames(
        test_by_index,
        reference_by_index,
        args.start_index,
        args.frames,
    )
    test_info = inspect_sequence(args.test_dir, test_paths, indices)
    reference_info = inspect_sequence(args.reference_dir, reference_paths, indices)
    if (test_info.width, test_info.height) != (
        reference_info.width,
        reference_info.height,
    ):
        raise ValueError(
            "Test/reference resolutions differ: "
            f"{test_info.width}x{test_info.height} != "
            f"{reference_info.width}x{reference_info.height}"
        )

    test_video = input_dir / "test_ffv1.mkv"
    reference_video = input_dir / "reference_ffv1.mkv"
    test_codec, test_pixel_format = encode_ffv1(test_paths, test_video, args.fps)
    ref_codec, ref_pixel_format = encode_ffv1(
        reference_paths, reference_video, args.fps
    )
    test_round_trip = verify_round_trip(
        test_paths, test_video, test_codec, test_pixel_format
    )
    reference_round_trip = verify_round_trip(
        reference_paths, reference_video, ref_codec, ref_pixel_format
    )

    cgvqm_module = import_cgvqm(args.cgvqm_root.resolve())
    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")

    models = ("2", "5") if args.model == "both" else (args.model,)
    model_results: dict[str, object] = {}
    for model in models:
        model_type = (
            cgvqm_module.CGVQM_TYPE.CGVQM_2
            if model == "2"
            else cgvqm_module.CGVQM_TYPE.CGVQM_5
        )
        score, emap = cgvqm_module.run_cgvqm(
            str(test_video),
            str(reference_video),
            cgvqm_type=model_type,
            device=device,
            patch_pool=args.patch_pool,
            patch_scale=args.patch_scale,
        )
        aggregate_stats, per_frame_stats = error_map_stats(emap)
        model_name = f"CGVQM-{model}"
        stats_path = output_dir / f"{model_name}-PerFrame.csv"
        write_frame_stats(stats_path, indices, per_frame_stats)
        error_map_video = output_dir / f"{model_name}-ErrorMap.mkv"
        if not args.skip_error_map_video:
            write_error_map_video(
                args.cgvqm_root.resolve(),
                emap,
                test_paths,
                error_map_video,
                args.fps,
            )
        model_results[model_name] = {
            "score_higher_is_better": float(score.detach().cpu().item()),
            "error_map": aggregate_stats,
            "per_frame_csv": str(stats_path),
            "visualized_error_map": (
                None if args.skip_error_map_video else str(error_map_video)
            ),
        }

    result = {
        "classification": args.classification,
        "metric_scope": (
            "Full-reference perceptual video quality; not an absolute ghosting "
            "ground truth."
        ),
        "provenance": {
            "scene": args.scene,
            "camera_profile": args.camera_profile,
            "test_mode": args.test_mode,
            "reference_id": args.reference_id,
        },
        "official_cgvqm": {
            "root": str(args.cgvqm_root.resolve()),
            "commit": git_commit(args.cgvqm_root.resolve()),
        },
        "runtime": {
            "python": sys.version,
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_runtime": torch.version.cuda,
            "device": device,
            "gpu": (
                torch.cuda.get_device_name(0)
                if device == "cuda" and torch.cuda.is_available()
                else None
            ),
        },
        "configuration": {
            "fps": args.fps,
            "patch_scale": args.patch_scale,
            "patch_pool": args.patch_pool,
            "models": list(models),
        },
        "test_sequence": asdict(test_info),
        "reference_sequence": asdict(reference_info),
        "test_round_trip": asdict(test_round_trip),
        "reference_round_trip": asdict(reference_round_trip),
        "results": model_results,
    }
    result_path = output_dir / "CGVQM-Results.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"RESULT_JSON={result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
