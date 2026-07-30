from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from analyze_optical_flow_temporal_quality import (
    DEFAULT_FARNEBACK,
    aggregate_alignment_gain,
    alignment_map,
    make_flow_diagnostic,
    masked_error_metrics,
    remap_array,
    require_opencv,
    run_self_test,
    safe_percent_delta,
    visual_center_frame,
)
from analyze_original_four_quality import aggregate, load_rgb
from analyze_smaa_1x_controls import (
    ALL_MODES,
    CONTROL_MODES,
    TEMPORAL_MODES,
    crop_half,
    validate_mode_paths,
)
from analyze_temporal_stress_quality import roi_boxes


MODE_REFERENCE = {
    key: ("o_1x" if key.startswith("o_") else "a_1x")
    for key, _, _ in ALL_MODES
}
REFERENCE_LABELS = {"o_1x": "O-1X", "a_1x": "A-1X"}

TEMPORAL_VS_CONTROL = (
    ("o_1x", "o_t2x"),
    ("o_1x", "o_t2x_r"),
    ("o_1x", "o_et2x"),
    ("o_1x", "o_et2x_r"),
    ("a_1x", "a_t2x"),
    ("a_1x", "a_t2x_r"),
    ("a_1x", "a_et2x"),
    ("a_1x", "a_et2x_r"),
)

FACTOR_COMPARISONS = (
    ("edge_selective_original_off", "o_t2x", "o_et2x"),
    ("edge_selective_original_on", "o_t2x_r", "o_et2x_r"),
    ("edge_selective_adaptive_off", "a_t2x", "a_et2x"),
    ("edge_selective_adaptive_on", "a_t2x_r", "a_et2x_r"),
    ("reprojection_original_standard", "o_t2x", "o_t2x_r"),
    ("reprojection_original_edge", "o_et2x", "o_et2x_r"),
    ("reprojection_adaptive_standard", "a_t2x", "a_t2x_r"),
    ("reprojection_adaptive_edge", "a_et2x", "a_et2x_r"),
    ("adaptive_standard_off", "o_t2x", "a_t2x"),
    ("adaptive_standard_on", "o_t2x_r", "a_t2x_r"),
    ("adaptive_edge_off", "o_et2x", "a_et2x"),
    ("adaptive_edge_on", "o_et2x_r", "a_et2x_r"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure motion-compensated temporal residuals for the final SMAA "
            "eight-case matrix using O-1X/A-1X reference flow."
        )
    )
    parser.add_argument("control_root", type=Path)
    parser.add_argument("temporal_root", type=Path)
    parser.add_argument(
        "--scenario",
        required=True,
        choices=("thin-lines", "object-motion", "combined"),
    )
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--fb-threshold", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    library = require_opencv()
    if args.fb_threshold <= 0.0:
        raise SystemExit("--fb-threshold must be positive")

    control_root = args.control_root.resolve()
    temporal_root = args.temporal_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else control_root / "EightCaseOpticalFlowAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)

    control_paths, resolution, control_validation = validate_mode_paths(
        control_root,
        CONTROL_MODES,
        args.expected_frames,
    )
    temporal_paths, _, temporal_validation = validate_mode_paths(
        temporal_root,
        TEMPORAL_MODES,
        args.expected_frames,
        resolution,
    )
    paths = {**control_paths, **temporal_paths}
    boxes = roi_boxes(args.scenario, resolution)
    labels = {key: semantic_id for key, semantic_id, _ in ALL_MODES}

    self_test = run_self_test()
    if not self_test["pass"]:
        raise RuntimeError("Synthetic optical-flow self-test failed")

    rows: list[dict[str, Any]] = []
    previous_full: dict[str, np.ndarray] | None = None
    diagnostic_names: list[str] = []
    center = visual_center_frame(args.scenario)

    for frame in range(args.expected_frames):
        current_full = {
            key: load_rgb(paths[key][frame]) for key, _, _ in ALL_MODES
        }
        if previous_full is None:
            previous_full = current_full
            continue

        row: dict[str, Any] = {"frame": frame}
        for roi_name, box in boxes.items():
            previous_rois = {
                key: crop_half(previous_full[key], box)
                for key, _, _ in ALL_MODES
            }
            current_rois = {
                key: crop_half(current_full[key], box)
                for key, _, _ in ALL_MODES
            }
            fields_by_reference = {
                reference: alignment_map(
                    previous_rois[reference],
                    current_rois[reference],
                    args.fb_threshold,
                )
                for reference in REFERENCE_LABELS
            }

            for reference, fields in fields_by_reference.items():
                valid = fields["valid"]
                flow_magnitude = np.linalg.norm(
                    fields["backward_flow"], axis=2
                )
                prefix = f"{roi_name}_{reference}_flow"
                row[f"{prefix}_valid_ratio"] = float(
                    valid.mean(dtype=np.float64)
                )
                row[f"{prefix}_magnitude_mean_px"] = (
                    float(flow_magnitude[valid].mean(dtype=np.float64))
                    if np.any(valid)
                    else float("nan")
                )
                row[f"{prefix}_fb_error_mean_px"] = (
                    float(
                        fields["forward_backward_error"][valid].mean(
                            dtype=np.float64
                        )
                    )
                    if np.any(valid)
                    else float("nan")
                )

            warped_by_mode: dict[str, np.ndarray] = {}
            for key, _, _ in ALL_MODES:
                reference = MODE_REFERENCE[key]
                fields = fields_by_reference[reference]
                valid = fields["valid"]
                warped = remap_array(
                    previous_rois[key].astype(np.float32),
                    fields["map_x"],
                    fields["map_y"],
                    library.INTER_LINEAR,
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

            for key, _, _ in ALL_MODES:
                reference = MODE_REFERENCE[key]
                aligned = row[f"{roi_name}_{key}_flow_aligned_rgb_mae"]
                reference_aligned = row[
                    f"{roi_name}_{reference}_flow_aligned_rgb_mae"
                ]
                row[f"{roi_name}_{key}_aligned_excess_vs_spatial_1x"] = (
                    aligned - reference_aligned
                )
                row[
                    f"{roi_name}_{key}_aligned_delta_vs_spatial_1x_percent"
                ] = safe_percent_delta(aligned, reference_aligned)

            if frame == center:
                for reference, reference_label in REFERENCE_LABELS.items():
                    diagnostic_names.append(
                        make_flow_diagnostic(
                            output,
                            f"{roi_name}_{reference.lower()}",
                            frame,
                            previous_rois[reference],
                            current_rois[reference],
                            warped_by_mode[reference],
                            fields_by_reference[reference],
                            reference_label,
                        )
                    )

        rows.append(row)
        previous_full = current_full
        if frame % 20 == 0 or frame == args.expected_frames - 1:
            print(
                f"Processed {frame}/{args.expected_frames - 1} frame pairs",
                flush=True,
            )

    csv_name = "eight_case_optical_flow_temporal_metrics.csv"
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
        flow_checks[roi_name] = {}
        for reference, reference_label in REFERENCE_LABELS.items():
            valid_ratio = summary[
                f"{roi_name}_{reference}_flow_valid_ratio"
            ]["mean"]
            reference_gain = aggregate_alignment_gain(
                summary,
                f"{roi_name}_{reference}",
            )
            flow_checks[roi_name][reference_label] = {
                "pass": valid_ratio >= 0.50 and reference_gain >= 0.0,
                "valid_ratio_mean": valid_ratio,
                "aggregate_alignment_gain_percent": reference_gain,
            }

    result = {
        "scenario": args.scenario,
        "conditions": {
            "resolution": list(resolution),
            "analysis_resolution": "each ROI at half width/height",
            "frame_rate": 60,
            "warmup_frames": args.warmup_frames,
            "capture_frames_per_mode": args.expected_frames,
            "flow_reference": {
                "Original": "O-1X",
                "Adaptive": "A-1X",
            },
            "flow_algorithm": "Farneback dense optical flow",
            "farneback_parameters": DEFAULT_FARNEBACK,
            "forward_backward_threshold_px": args.fb_threshold,
        },
        "input_validation": {
            "control": control_validation,
            "temporal": temporal_validation,
        },
        "synthetic_self_test": self_test,
        "flow_checks": flow_checks,
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "artifacts": {
            "metrics_csv": csv_name,
            "diagnostics": diagnostic_names,
        },
    }
    json_name = "eight_case_optical_flow_temporal_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# SMAA 최종 8-case optical-flow 정렬 품질 분석",
        "",
        "## 범위",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 원시 해상도: {resolution[0]}×{resolution[1]}",
        "- Flow와 지표는 각 ROI를 1/2 해상도로 축소해 계산",
        f"- mode별 warm-up {args.warmup_frames}프레임, 저장 {args.expected_frames}프레임",
        "- Original 4개 mode에는 O-1X flow를 공통 적용",
        "- Adaptive 4개 mode에는 A-1X flow를 공통 적용",
        "- Dense flow: Farneback, current→previous backward map",
        f"- Forward/backward consistency threshold: {args.fb_threshold:.3f} px",
        "- 불일치·화면 밖 픽셀은 aligned residual에서 제외",
        "",
        "두 1X control과 temporal 8-case는 별도 실행이지만 동일 fixed timeline이며,",
        "기존 검증에서 별도 순차 재실행과 최초 control PNG의 SHA-256 mismatch가 0이었다.",
        "이 분석은 motion-compensated 보조 지표이지 supersample ground truth나 절대",
        "ghosting 점수가 아니다.",
        "",
        "## 합성 이동 self-test",
        "",
        f"- 판정: `{'PASS' if self_test['pass'] else 'FAIL'}`",
        f"- vector error: {self_test['vector_error_px']:.6f} px",
        f"- 정렬 오차 감소: {self_test['alignment_reduction_percent']:.3f}%",
    ]

    for roi_name in boxes:
        report.extend(["", f"## `{roi_name}` flow 검증", ""])
        for reference_label, check in flow_checks[roi_name].items():
            report.append(
                f"- {reference_label}: valid {check['valid_ratio_mean']:.3%}, "
                f"전체 평균 MAE 정렬 감소 "
                f"{check['aggregate_alignment_gain_percent']:.3f}%, "
                f"`{'PASS' if check['pass'] else 'WARN'}`"
            )

        report.extend(
            [
                "",
                "| Mode | Flow 기준 | 정렬 전 RGB MAE | Flow 정렬 RGB MAE | 정렬 감소율 | Spatial 1X 대비 초과 | 정렬 P95 |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for key, semantic_id, _ in ALL_MODES:
            prefix = f"{roi_name}_{key}"
            report.append(
                f"| `{semantic_id}` | `{REFERENCE_LABELS[MODE_REFERENCE[key]]}` | "
                f"{summary[f'{prefix}_unaligned_rgb_mae']['mean']:.6f} | "
                f"{summary[f'{prefix}_flow_aligned_rgb_mae']['mean']:.6f} | "
                f"{aggregate_alignment_gain(summary, prefix):.3f}% | "
                f"{summary[f'{roi_name}_{key}_aligned_excess_vs_spatial_1x']['mean']:+.6f} | "
                f"{summary[f'{prefix}_flow_aligned_rgb_p95']['mean']:.6f} |"
            )

        report.extend(
            [
                "",
                "### Temporal mode와 대응 spatial 1X",
                "",
                "| 비교 | Flow 정렬 MAE 변화 |",
                "|---|---:|",
            ]
        )
        for control_key, temporal_key in TEMPORAL_VS_CONTROL:
            control_value = summary[
                f"{roi_name}_{control_key}_flow_aligned_rgb_mae"
            ]["mean"]
            temporal_value = summary[
                f"{roi_name}_{temporal_key}_flow_aligned_rgb_mae"
            ]["mean"]
            report.append(
                f"| `{labels[temporal_key]}` vs `{labels[control_key]}` | "
                f"{safe_percent_delta(temporal_value, control_value):+.3f}% |"
            )

        report.extend(
            [
                "",
                "### 최종 8-case factor pair",
                "",
                "| 축 | 비교 | Flow 정렬 MAE 변화 |",
                "|---|---|---:|",
            ]
        )
        for factor, first_key, second_key in FACTOR_COMPARISONS:
            first_value = summary[
                f"{roi_name}_{first_key}_flow_aligned_rgb_mae"
            ]["mean"]
            second_value = summary[
                f"{roi_name}_{second_key}_flow_aligned_rgb_mae"
            ]["mean"]
            report.append(
                f"| `{factor}` | `{labels[second_key]}` vs "
                f"`{labels[first_key]}` | "
                f"{safe_percent_delta(second_value, first_value):+.3f}% |"
            )

    report.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- Farneback flow는 추정치이며 가림·반사·저텍스처·회전 경계에서 오차가 생긴다.",
            "- Forward/backward 불일치 영역을 제외하므로 disocclusion ghosting을 완전히 평가하지 않는다.",
            "- O-1X/A-1X 자체 aliasing이 각 flow source에 포함된다.",
            "- 작은 aligned residual이 blur나 history 누적 때문일 수 있어 단독 품질 순위로 사용하지 않는다.",
            "- Original과 Adaptive는 서로 다른 1X flow를 사용하므로 공간 축의 아주 작은 차이는 주의해서 해석한다.",
            "- 기존 trailing-halo, 1X 비교, 연속 frame sheet와 함께 해석한다.",
            "- `-R`의 런타임 reprojection은 camera motion만 처리하고 object motion vector는 없다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 지표: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
        ]
    )
    report.extend(f"- Flow 진단: `{name}`" for name in diagnostic_names)
    report.append("")

    report_name = "SMAA-Eight-Case-Optical-Flow-Analysis-ko.md"
    (output / report_name).write_text(
        "\n".join(report), encoding="utf-8"
    )
    print(f"Eight-case optical-flow analysis complete: {output}", flush=True)


if __name__ == "__main__":
    main()
