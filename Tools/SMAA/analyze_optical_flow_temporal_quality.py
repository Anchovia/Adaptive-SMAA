from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None

from analyze_candidate_only_ablation import (
    COMPONENT_COMPARISONS,
    COMPONENT_MODES,
    crop_half,
    validate_inputs,
)
from analyze_original_four_quality import aggregate, load_rgb, percent_delta
from analyze_temporal_stress_quality import roi_boxes


FLOW_REFERENCE_KEY = "o_1x"
DEFAULT_FARNEBACK = {
    "pyr_scale": 0.5,
    "levels": 3,
    "winsize": 15,
    "iterations": 3,
    "poly_n": 5,
    "poly_sigma": 1.2,
    "flags": 0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure motion-compensated SMAA temporal residuals using O-1X "
            "Farneback flow and forward/backward consistency."
        )
    )
    parser.add_argument("capture_root", type=Path, nargs="?")
    parser.add_argument(
        "--scenario",
        choices=("thin-lines", "object-motion", "combined"),
    )
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--fb-threshold", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run a synthetic known-translation reference test and exit.",
    )
    return parser.parse_args()


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


def safe_percent_delta(current: float, baseline: float) -> float:
    if not math.isfinite(current) or not math.isfinite(baseline) or baseline == 0:
        return float("nan")
    return percent_delta(current, baseline)


def make_flow_diagnostic(
    output: Path,
    roi_name: str,
    frame: int,
    previous_reference: np.ndarray,
    current_reference: np.ndarray,
    warped_reference: np.ndarray,
    fields: dict[str, np.ndarray],
) -> str:
    library = require_opencv()
    valid = fields["valid"]
    magnitude = np.linalg.norm(fields["backward_flow"], axis=2)
    scale = max(float(np.percentile(magnitude[valid], 95.0)), 0.25)
    magnitude_u8 = np.clip(magnitude * (255.0 / scale), 0.0, 255.0).astype(
        np.uint8
    )
    magnitude_color = library.applyColorMap(
        magnitude_u8, library.COLORMAP_TURBO
    )[..., ::-1]
    valid_rgb = np.repeat((valid.astype(np.uint8) * 255)[..., None], 3, axis=2)
    difference = np.clip(
        np.abs(
            current_reference.astype(np.float32)
            - warped_reference.astype(np.float32)
        )
        * 4.0,
        0.0,
        255.0,
    ).astype(np.uint8)

    panels = (
        ("previous O-1X", previous_reference),
        ("current O-1X", current_reference),
        ("warped previous", np.clip(warped_reference, 0, 255).astype(np.uint8)),
        ("aligned difference x4", difference),
        ("backward flow magnitude", magnitude_color),
        ("FB-consistent valid mask", valid_rgb),
    )
    height, width = current_reference.shape[:2]
    header = 28
    canvas = Image.new("RGB", (width * len(panels), height + header), "black")
    draw = ImageDraw.Draw(canvas)
    for column, (label, image) in enumerate(panels):
        x = column * width
        canvas.paste(Image.fromarray(image), (x, header))
        draw.text((x + 5, 8), label, fill="white")
    name = f"optical_flow_diagnostic_{roi_name}_{frame:05d}.png"
    canvas.save(output / name, compress_level=3)
    return name


def visual_center_frame(scenario: str) -> int:
    return 120 if scenario == "thin-lines" else 90


def main() -> None:
    args = parse_args()
    require_opencv()
    if args.self_test:
        result = run_self_test()
        print(json.dumps(result, indent=2), flush=True)
        if not result["pass"]:
            raise SystemExit(1)
        return

    if args.capture_root is None or args.scenario is None:
        raise SystemExit("capture_root and --scenario are required without --self-test")
    if args.fb_threshold <= 0.0:
        raise SystemExit("--fb-threshold must be positive")

    root = args.capture_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else root / "OpticalFlowTemporalAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)
    paths, resolution, input_validation = validate_inputs(
        root, args.expected_frames, COMPONENT_MODES
    )
    boxes = roi_boxes(args.scenario, resolution)
    labels = {
        key: semantic_id for key, semantic_id, _ in COMPONENT_MODES
    }

    self_test = run_self_test()
    if not self_test["pass"]:
        raise RuntimeError("Synthetic optical-flow self-test failed")

    rows: list[dict[str, Any]] = []
    previous_full: dict[str, np.ndarray] | None = None
    diagnostic_names: list[str] = []
    center = visual_center_frame(args.scenario)

    for frame in range(args.expected_frames):
        current_full = {
            key: load_rgb(paths[key][frame]) for key, _, _ in COMPONENT_MODES
        }
        if previous_full is None:
            previous_full = current_full
            continue

        row: dict[str, Any] = {"frame": frame}
        for roi_name, box in boxes.items():
            previous_rois = {
                key: crop_half(previous_full[key], box)
                for key, _, _ in COMPONENT_MODES
            }
            current_rois = {
                key: crop_half(current_full[key], box)
                for key, _, _ in COMPONENT_MODES
            }
            previous_reference = previous_rois[FLOW_REFERENCE_KEY]
            current_reference = current_rois[FLOW_REFERENCE_KEY]
            fields = alignment_map(
                previous_reference,
                current_reference,
                args.fb_threshold,
            )
            valid = fields["valid"]
            valid_ratio = float(valid.mean(dtype=np.float64))
            flow_magnitude = np.linalg.norm(fields["backward_flow"], axis=2)
            row[f"{roi_name}_flow_valid_ratio"] = valid_ratio
            row[f"{roi_name}_flow_magnitude_mean_px"] = (
                float(flow_magnitude[valid].mean(dtype=np.float64))
                if np.any(valid)
                else float("nan")
            )
            row[f"{roi_name}_flow_fb_error_mean_px"] = (
                float(
                    fields["forward_backward_error"][valid].mean(
                        dtype=np.float64
                    )
                )
                if np.any(valid)
                else float("nan")
            )

            warped_by_mode: dict[str, np.ndarray] = {}
            for key, _, _ in COMPONENT_MODES:
                warped = remap_array(
                    previous_rois[key].astype(np.float32),
                    fields["map_x"],
                    fields["map_y"],
                    require_opencv().INTER_LINEAR,
                )
                warped_by_mode[key] = warped
                unaligned_mean, unaligned_p95 = masked_error_metrics(
                    current_rois[key],
                    previous_rois[key],
                    valid,
                )
                aligned_mean, aligned_p95 = masked_error_metrics(
                    current_rois[key],
                    warped,
                    valid,
                )
                prefix = f"{roi_name}_{key}"
                row[f"{prefix}_unaligned_rgb_mae"] = unaligned_mean
                row[f"{prefix}_unaligned_rgb_p95"] = unaligned_p95
                row[f"{prefix}_flow_aligned_rgb_mae"] = aligned_mean
                row[f"{prefix}_flow_aligned_rgb_p95"] = aligned_p95
                row[f"{prefix}_alignment_gain_percent"] = (
                    100.0 * (unaligned_mean - aligned_mean) / unaligned_mean
                    if unaligned_mean > 0.0
                    else 0.0
                )

            reference_aligned = row[
                f"{roi_name}_{FLOW_REFERENCE_KEY}_flow_aligned_rgb_mae"
            ]
            for key, _, _ in COMPONENT_MODES:
                aligned = row[f"{roi_name}_{key}_flow_aligned_rgb_mae"]
                row[f"{roi_name}_{key}_aligned_excess_vs_1x"] = (
                    aligned - reference_aligned
                )
                row[f"{roi_name}_{key}_aligned_delta_vs_1x_percent"] = (
                    safe_percent_delta(aligned, reference_aligned)
                )

            if frame == center:
                diagnostic_names.append(
                    make_flow_diagnostic(
                        output,
                        roi_name,
                        frame,
                        previous_reference,
                        current_reference,
                        warped_by_mode[FLOW_REFERENCE_KEY],
                        fields,
                    )
                )

        rows.append(row)
        previous_full = current_full
        if frame % 20 == 0 or frame == args.expected_frames - 1:
            print(
                f"Processed {frame}/{args.expected_frames - 1} frame pairs",
                flush=True,
            )

    if not rows:
        raise RuntimeError("At least two frames are required")

    csv_name = "optical_flow_temporal_metrics.csv"
    with (output / csv_name).open(
        "w", newline="", encoding="utf-8-sig"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        key: aggregate(rows, key) for key in rows[0] if key != "frame"
    }
    flow_checks: dict[str, Any] = {}
    for roi_name in boxes:
        valid_ratio = summary[f"{roi_name}_flow_valid_ratio"]["mean"]
        reference_gain = summary[
            f"{roi_name}_{FLOW_REFERENCE_KEY}_alignment_gain_percent"
        ]["mean"]
        flow_checks[roi_name] = {
            "pass": valid_ratio >= 0.50 and reference_gain >= 0.0,
            "valid_ratio_mean": valid_ratio,
            "o_1x_alignment_gain_percent_mean": reference_gain,
        }

    result = {
        "scenario": args.scenario,
        "conditions": {
            "resolution": list(resolution),
            "analysis_resolution": "each ROI at half width/height",
            "frame_rate": 60,
            "warmup_frames": args.warmup_frames,
            "capture_frames_per_mode": args.expected_frames,
            "flow_reference": "O-1X",
            "flow_algorithm": "Farneback dense optical flow",
            "farneback_parameters": DEFAULT_FARNEBACK,
            "forward_backward_threshold_px": args.fb_threshold,
            "history_reprojection_scope": (
                "Mode -R uses camera motion only; analysis flow is independent "
                "and estimated from O-1X images"
            ),
        },
        "input_validation": input_validation,
        "synthetic_self_test": self_test,
        "flow_checks": flow_checks,
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "artifacts": {
            "metrics_csv": csv_name,
            "diagnostics": diagnostic_names,
        },
    }
    json_name = "optical_flow_temporal_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# SMAA optical-flow 정렬 temporal 품질 분석",
        "",
        "## 범위",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 원시 해상도: {resolution[0]}×{resolution[1]}",
        "- Flow와 지표는 각 ROI를 1/2 해상도로 축소해 계산",
        f"- mode별 warm-up {args.warmup_frames}프레임, 저장 {args.expected_frames}프레임",
        "- Flow source: 같은 capture의 `O-1X`",
        "- Dense flow: Farneback, current→previous backward map",
        f"- Forward/backward consistency threshold: {args.fb_threshold:.3f} px",
        "- 불일치·화면 밖 픽셀은 aligned residual에서 제외",
        "",
        "이 분석은 장면 움직임을 보정한 보조 지표이며 supersample ground truth나",
        "절대 ghosting 점수가 아니다. O-1X에서 flow를 한 번 추정해 모든 Original",
        "temporal mode에 동일하게 적용하므로 각 mode의 history blur가 flow 추정을",
        "직접 바꾸지 않게 했다.",
        "",
        "## 합성 이동 self-test",
        "",
        f"- 판정: `{'PASS' if self_test['pass'] else 'FAIL'}`",
        f"- 알려진 forward 이동: {self_test['known_forward_translation_px']} px",
        f"- 측정 backward flow 중앙값: {self_test['median_backward_flow_px']} px",
        f"- vector error: {self_test['vector_error_px']:.6f} px",
        f"- 정렬 오차 감소: {self_test['alignment_reduction_percent']:.3f}%",
    ]

    for roi_name in boxes:
        check = flow_checks[roi_name]
        report.extend(
            [
                "",
                f"## `{roi_name}` flow 검증",
                "",
                f"- 유효 픽셀 비율 평균: {check['valid_ratio_mean']:.3%}",
                f"- O-1X 정렬 오차 감소 평균: {check['o_1x_alignment_gain_percent_mean']:.3f}%",
                f"- 보조 검증 판정: `{'PASS' if check['pass'] else 'WARN'}`",
                "",
                "| Mode | 정렬 전 RGB MAE | Flow 정렬 RGB MAE | 정렬 감소율 | O-1X 대비 초과 | 정렬 P95 |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for key, semantic_id, _ in COMPONENT_MODES:
            prefix = f"{roi_name}_{key}"
            report.append(
                f"| `{semantic_id}` | "
                f"{summary[f'{prefix}_unaligned_rgb_mae']['mean']:.6f} | "
                f"{summary[f'{prefix}_flow_aligned_rgb_mae']['mean']:.6f} | "
                f"{summary[f'{prefix}_alignment_gain_percent']['mean']:.3f}% | "
                f"{summary[f'{roi_name}_{key}_aligned_excess_vs_1x']['mean']:+.6f} | "
                f"{summary[f'{prefix}_flow_aligned_rgb_p95']['mean']:.6f} |"
            )

        report.extend(
            [
                "",
                "| 인접 구성요소 비교 | Flow 정렬 MAE 변화 |",
                "|---|---:|",
            ]
        )
        for _, first_key, second_key in COMPONENT_COMPARISONS:
            first_value = summary[
                f"{roi_name}_{first_key}_flow_aligned_rgb_mae"
            ]["mean"]
            second_value = summary[
                f"{roi_name}_{second_key}_flow_aligned_rgb_mae"
            ]["mean"]
            report.append(
                f"| `{labels[second_key]}` vs `{labels[first_key]}` | "
                f"{safe_percent_delta(second_value, first_value):+.3f}% |"
            )

    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- Farneback flow는 추정치이며 가림·반사·저텍스처·회전 경계에서 오차가 생긴다.",
            "- Forward/backward 불일치 영역을 제외하므로 disocclusion ghosting을 완전히 평가하지 않는다.",
            "- O-1X 자체 aliasing이 flow source에 포함된다.",
            "- 작은 aligned residual이 blur나 history 누적 때문일 수 있으므로 단독 품질 순위로 사용하지 않는다.",
            "- 기존 trailing-halo, 1X 비교, 연속 frame sheet와 함께 해석한다.",
            "- `-R` mode의 런타임 reprojection은 camera motion만 처리하고 object motion vector는 없다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 지표: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
        ]
    )
    report.extend(f"- Flow 진단: `{name}`" for name in diagnostic_names)
    report.append("")

    report_name = "SMAA-Optical-Flow-Temporal-Analysis-ko.md"
    (output / report_name).write_text(
        "\n".join(report), encoding="utf-8"
    )
    print(f"Optical-flow temporal analysis complete: {output}", flush=True)


if __name__ == "__main__":
    main()
