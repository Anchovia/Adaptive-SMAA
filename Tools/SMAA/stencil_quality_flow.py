"""Unchanged flow helpers extracted from verified project commit 89d5378; imports only simplified."""
from __future__ import annotations
from typing import Any
import numpy as np
import cv2

DEFAULT_FARNEBACK = {
    "pyr_scale": 0.5,
    "levels": 3,
    "winsize": 15,
    "iterations": 3,
    "poly_n": 5,
    "poly_sigma": 1.2,
    "flags": 0,
}

def require_opencv() -> Any:
    if cv2 is None:
        raise RuntimeError(
            "OpenCV is required. Install Tools/SMAA/"
            "requirements-optical-flow.txt before running this analyzer."
        )
    return cv2

def to_gray(rgb: np.ndarray) -> np.ndarray:
    library = require_opencv()
    return library.cvtColor(rgb, library.COLOR_RGB2GRAY)

def calculate_flow(previous_gray: np.ndarray, current_gray: np.ndarray) -> np.ndarray:
    library = require_opencv()
    return library.calcOpticalFlowFarneback(
        previous_gray,
        current_gray,
        None,
        DEFAULT_FARNEBACK["pyr_scale"],
        DEFAULT_FARNEBACK["levels"],
        DEFAULT_FARNEBACK["winsize"],
        DEFAULT_FARNEBACK["iterations"],
        DEFAULT_FARNEBACK["poly_n"],
        DEFAULT_FARNEBACK["poly_sigma"],
        DEFAULT_FARNEBACK["flags"],
    )

def remap_array(
    source: np.ndarray,
    map_x: np.ndarray,
    map_y: np.ndarray,
    interpolation: int,
) -> np.ndarray:
    library = require_opencv()
    return library.remap(
        source,
        map_x,
        map_y,
        interpolation=interpolation,
        borderMode=library.BORDER_CONSTANT,
        borderValue=0,
    )

def alignment_map(
    previous_reference: np.ndarray,
    current_reference: np.ndarray,
    fb_threshold: float,
) -> dict[str, np.ndarray]:
    library = require_opencv()
    previous_gray = to_gray(previous_reference)
    current_gray = to_gray(current_reference)

    forward = calculate_flow(previous_gray, current_gray)
    backward = calculate_flow(current_gray, previous_gray)
    height, width = current_gray.shape
    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
    )
    map_x = grid_x + backward[..., 0]
    map_y = grid_y + backward[..., 1]

    sampled_forward = remap_array(
        forward,
        map_x,
        map_y,
        library.INTER_LINEAR,
    )
    forward_backward_error = np.linalg.norm(
        backward + sampled_forward, axis=2
    )
    inside = (
        (map_x >= 1.0)
        & (map_x <= float(width - 2))
        & (map_y >= 1.0)
        & (map_y <= float(height - 2))
    )
    finite = (
        np.isfinite(map_x)
        & np.isfinite(map_y)
        & np.isfinite(forward_backward_error)
    )
    valid = inside & finite & (forward_backward_error <= fb_threshold)
    return {
        "map_x": map_x,
        "map_y": map_y,
        "backward_flow": backward,
        "forward_backward_error": forward_backward_error,
        "valid": valid,
    }

def masked_error_metrics(
    current_rgb: np.ndarray,
    comparison_rgb: np.ndarray,
    valid: np.ndarray,
) -> tuple[float, float]:
    if not np.any(valid):
        return float("nan"), float("nan")
    per_pixel = np.abs(
        current_rgb.astype(np.float32) - comparison_rgb.astype(np.float32)
    ).mean(axis=2)
    values = per_pixel[valid]
    return (
        float(values.mean(dtype=np.float64)),
        float(np.percentile(values, 95.0)),
    )

def run_self_test() -> dict[str, Any]:
    library = require_opencv()
    rng = np.random.default_rng(20260730)
    previous = rng.integers(0, 256, size=(128, 160), dtype=np.uint8)
    previous = library.GaussianBlur(previous, (5, 5), 0.8)
    previous_rgb = np.repeat(previous[..., None], 3, axis=2)

    expected_forward = np.array((3.0, -2.0), dtype=np.float32)
    transform = np.array(
        ((1.0, 0.0, expected_forward[0]), (0.0, 1.0, expected_forward[1])),
        dtype=np.float32,
    )
    current_rgb = library.warpAffine(
        previous_rgb,
        transform,
        (previous_rgb.shape[1], previous_rgb.shape[0]),
        flags=library.INTER_LINEAR,
        borderMode=library.BORDER_REFLECT101,
    )

    fields = alignment_map(previous_rgb, current_rgb, fb_threshold=0.75)
    valid = fields["valid"]
    backward = fields["backward_flow"]
    warped = remap_array(
        previous_rgb.astype(np.float32),
        fields["map_x"],
        fields["map_y"],
        library.INTER_LINEAR,
    )
    unaligned_mean, _ = masked_error_metrics(current_rgb, previous_rgb, valid)
    aligned_mean, _ = masked_error_metrics(current_rgb, warped, valid)
    median_backward = np.median(backward[valid], axis=0)
    expected_backward = -expected_forward
    vector_error = float(np.linalg.norm(median_backward - expected_backward))
    valid_ratio = float(valid.mean(dtype=np.float64))
    reduction = (
        100.0 * (unaligned_mean - aligned_mean) / unaligned_mean
        if unaligned_mean > 0.0
        else 0.0
    )
    passed = (
        valid_ratio >= 0.80
        and vector_error <= 0.35
        and aligned_mean <= unaligned_mean * 0.20
    )
    return {
        "pass": passed,
        "known_forward_translation_px": expected_forward.tolist(),
        "expected_backward_flow_px": expected_backward.tolist(),
        "median_backward_flow_px": median_backward.tolist(),
        "vector_error_px": vector_error,
        "valid_ratio": valid_ratio,
        "unaligned_rgb_mae": unaligned_mean,
        "aligned_rgb_mae": aligned_mean,
        "alignment_reduction_percent": reduction,
    }
