from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from analyze_candidate_only_ablation import (
    crop_half,
    make_four_mode_gif,
    make_four_mode_sheet,
    validate_inputs,
    visual_center_frame,
    visual_regions,
)
from analyze_optical_flow_temporal_quality import (
    DEFAULT_FARNEBACK,
    alignment_map,
    make_flow_diagnostic,
    masked_error_metrics,
    remap_array,
    require_opencv,
    run_self_test,
)
from analyze_original_four_quality import aggregate, load_rgb, percent_delta
from analyze_temporal_stress_quality import roi_boxes


MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("standard", "O-T2X-R", "O_T2X_R"),
    (
        "candidate_intel",
        "ABL-Candidate-Intel-R",
        "ABL_Candidate_Intel_R",
    ),
    (
        "candidate_allbase",
        "ABL-Candidate-AllBase-R",
        "ABL_Candidate_AllBase_R",
    ),
)

COMPARISONS = (
    ("standard_vs_1x", "o_1x", "standard"),
    ("intel_vs_standard", "standard", "candidate_intel"),
    ("allbase_vs_standard", "standard", "candidate_allbase"),
    ("allbase_vs_intel", "candidate_intel", "candidate_allbase"),
)

FLOW_REFERENCE_KEY = "o_1x"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze Intel-family versus AllBase candidate coverage while "
            "preserving the O-T2X-R jitter and temporal settings."
        )
    )
    parser.add_argument("capture_root", type=Path)
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


def safe_percent_delta(current: float, baseline: float) -> float:
    if not math.isfinite(current) or not math.isfinite(baseline) or baseline == 0:
        return float("nan")
    return percent_delta(current, baseline)


def rgb_mae(first: np.ndarray, second: np.ndarray) -> float:
    return float(
        np.abs(first.astype(np.int16) - second.astype(np.int16)).mean(
            dtype=np.float64
        )
    )


def main() -> None:
    args = parse_args()
    library = require_opencv()
    if args.fb_threshold <= 0.0:
        raise SystemExit("--fb-threshold must be positive")

    root = args.capture_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else root / "CandidatePolicyJitterAnalysis"
    )
    output.mkdir(parents=True, exist_ok=True)
    paths, resolution, input_validation = validate_inputs(
        root, args.expected_frames, MODES
    )
    boxes = roi_boxes(args.scenario, resolution)
    labels = {key: semantic_id for key, semantic_id, _ in MODES}

    self_test = run_self_test()
    if not self_test["pass"]:
        raise RuntimeError("Synthetic optical-flow self-test failed")

    rows: list[dict[str, Any]] = []
    previous_full: dict[str, np.ndarray] | None = None
    diagnostic_names: list[str] = []
    center = visual_center_frame(args.scenario)

    for frame in range(args.expected_frames):
        current_full = {
            key: load_rgb(paths[key][frame]) for key, _, _ in MODES
        }
        if previous_full is None:
            previous_full = current_full
            continue

        row: dict[str, Any] = {"frame": frame}
        for roi_name, box in boxes.items():
            previous_rois = {
                key: crop_half(previous_full[key], box) for key, _, _ in MODES
            }
            current_rois = {
                key: crop_half(current_full[key], box) for key, _, _ in MODES
            }
            previous_reference = previous_rois[FLOW_REFERENCE_KEY]
            current_reference = current_rois[FLOW_REFERENCE_KEY]
            fields = alignment_map(
                previous_reference,
                current_reference,
                args.fb_threshold,
            )
            valid = fields["valid"]
            flow_magnitude = np.linalg.norm(fields["backward_flow"], axis=2)
            row[f"{roi_name}_flow_valid_ratio"] = float(
                valid.mean(dtype=np.float64)
            )
            row[f"{roi_name}_flow_magnitude_mean_px"] = (
                float(flow_magnitude[valid].mean(dtype=np.float64))
                if np.any(valid)
                else float("nan")
            )

            warped_reference: np.ndarray | None = None
            for key, _, _ in MODES:
                warped = remap_array(
                    previous_rois[key].astype(np.float32),
                    fields["map_x"],
                    fields["map_y"],
                    library.INTER_LINEAR,
                )
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
                if key == FLOW_REFERENCE_KEY:
                    warped_reference = warped

            for key in ("candidate_intel", "candidate_allbase"):
                row[f"{roi_name}_{key}_same_frame_mae_vs_standard"] = rgb_mae(
                    current_rois[key], current_rois["standard"]
                )
            row[f"{roi_name}_allbase_same_frame_mae_vs_intel"] = rgb_mae(
                current_rois["candidate_allbase"],
                current_rois["candidate_intel"],
            )

            if frame == min(center, args.expected_frames - 1):
                assert warped_reference is not None
                diagnostic_names.append(
                    make_flow_diagnostic(
                        output,
                        roi_name,
                        frame,
                        previous_reference,
                        current_reference,
                        warped_reference,
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

    csv_name = "candidate_policy_jitter_metrics.csv"
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
    policy_effects: dict[str, Any] = {}
    for roi_name in boxes:
        valid_ratio = summary[f"{roi_name}_flow_valid_ratio"]["mean"]
        o1x_unaligned = summary[
            f"{roi_name}_o_1x_unaligned_rgb_mae"
        ]["mean"]
        o1x_aligned = summary[
            f"{roi_name}_o_1x_flow_aligned_rgb_mae"
        ]["mean"]
        alignment_gain = (
            100.0 * (o1x_unaligned - o1x_aligned) / o1x_unaligned
            if o1x_unaligned > 0.0
            else 0.0
        )
        flow_checks[roi_name] = {
            "pass": valid_ratio >= 0.50 and alignment_gain >= 0.0,
            "valid_ratio_mean": valid_ratio,
            "o_1x_alignment_gain_percent": alignment_gain,
        }

        standard = summary[
            f"{roi_name}_standard_flow_aligned_rgb_mae"
        ]["mean"]
        intel = summary[
            f"{roi_name}_candidate_intel_flow_aligned_rgb_mae"
        ]["mean"]
        allbase = summary[
            f"{roi_name}_candidate_allbase_flow_aligned_rgb_mae"
        ]["mean"]
        intel_distance = abs(intel - standard)
        allbase_distance = abs(allbase - standard)
        policy_effects[roi_name] = {
            "allbase_vs_intel_aligned_mae_percent": safe_percent_delta(
                allbase, intel
            ),
            "intel_distance_to_standard": intel_distance,
            "allbase_distance_to_standard": allbase_distance,
            "allbase_distance_reduction_vs_intel_percent": (
                100.0 * (intel_distance - allbase_distance) / intel_distance
                if intel_distance > 0.0
                else float("nan")
            ),
        }

    artifact_names: list[str] = []
    for roi_name in visual_regions(args.scenario):
        if roi_name not in boxes:
            continue
        artifact_names.append(
            make_four_mode_gif(
                output,
                paths,
                labels,
                roi_name,
                boxes[roi_name],
                center,
                args.expected_frames,
                MODES,
                "candidate_policy_jitter",
            )
        )
        artifact_names.append(
            make_four_mode_sheet(
                output,
                paths,
                labels,
                roi_name,
                boxes[roi_name],
                center,
                args.expected_frames,
                MODES,
                "candidate_policy_jitter",
            )
        )

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
            "controlled_difference": (
                "IntelFamilyNonDominant versus AllBaseEdges candidate policy; "
                "both use O-T2X-R jitter, camera reprojection, bilinear "
                "history, clipping Off, and weight 0.5"
            ),
        },
        "input_validation": input_validation,
        "synthetic_self_test": self_test,
        "flow_checks": flow_checks,
        "policy_effects": policy_effects,
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "artifacts": {
            "metrics_csv": csv_name,
            "diagnostics": diagnostic_names,
            "comparisons": artifact_names,
        },
    }
    json_name = "candidate_policy_jitter_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# SMAA candidate 정책·T2X jitter 분리 분석",
        "",
        "## 목적",
        "",
        "전역 SMAA T2X projection jitter를 유지한 상태에서 candidate 누락이",
        "Edge-selective temporal variation의 원인인지 분리한다.",
        "",
        "- `O-1X`: spatial-only 품질 control",
        "- `O-T2X-R`: 전체 화면 Standard T2X + camera reprojection",
        "- `ABL-Candidate-Intel-R`: Intel-family non-dominant 후보만 temporal 적용",
        "- `ABL-Candidate-AllBase-R`: 검출된 모든 base edge에 temporal 적용",
        "- 두 candidate mode의 유일한 설정 차이는 candidate policy",
        "- 두 candidate mode 모두 jitter/subsample, reprojection, bilinear sampler,",
        "  clipping Off, history weight 0.5를 동일하게 유지",
        "",
        "## 입력 및 검증",
        "",
        f"- 시나리오: `{args.scenario}`",
        f"- 해상도: {resolution[0]}×{resolution[1]}",
        f"- mode별 warm-up {args.warmup_frames}프레임, 저장 {args.expected_frames}프레임",
        f"- 합성 flow self-test: `{'PASS' if self_test['pass'] else 'FAIL'}`",
        f"- self-test vector error: {self_test['vector_error_px']:.6f} px",
        "",
    ]

    for roi_name in boxes:
        check = flow_checks[roi_name]
        effect = policy_effects[roi_name]
        report.extend(
            [
                f"## `{roi_name}`",
                "",
                f"- Flow 유효 픽셀 비율: {check['valid_ratio_mean']:.3%}",
                f"- O-1X 정렬 오차 감소: {check['o_1x_alignment_gain_percent']:.3f}%",
                f"- Flow 보조 검증: `{'PASS' if check['pass'] else 'WARN'}`",
                "",
                "| Mode | 정렬 전 RGB MAE | Flow 정렬 RGB MAE | 정렬 P95 |",
                "|---|---:|---:|---:|",
            ]
        )
        for key, semantic_id, _ in MODES:
            prefix = f"{roi_name}_{key}"
            report.append(
                f"| `{semantic_id}` | "
                f"{summary[f'{prefix}_unaligned_rgb_mae']['mean']:.6f} | "
                f"{summary[f'{prefix}_flow_aligned_rgb_mae']['mean']:.6f} | "
                f"{summary[f'{prefix}_flow_aligned_rgb_p95']['mean']:.6f} |"
            )
        report.extend(
            [
                "",
                "| 비교 | Flow 정렬 MAE 변화 |",
                "|---|---:|",
            ]
        )
        for _, baseline_key, current_key in COMPARISONS:
            baseline = summary[
                f"{roi_name}_{baseline_key}_flow_aligned_rgb_mae"
            ]["mean"]
            current = summary[
                f"{roi_name}_{current_key}_flow_aligned_rgb_mae"
            ]["mean"]
            report.append(
                f"| `{labels[current_key]}` vs `{labels[baseline_key]}` | "
                f"{safe_percent_delta(current, baseline):+.3f}% |"
            )
        report.extend(
            [
                "",
                f"- Intel 후보의 Standard 거리: {effect['intel_distance_to_standard']:.6f}",
                f"- AllBase 후보의 Standard 거리: {effect['allbase_distance_to_standard']:.6f}",
                "- AllBase 전환에 따른 Standard 거리 감소율: "
                f"{effect['allbase_distance_reduction_vs_intel_percent']:+.3f}%",
                "",
            ]
        )

    report.extend(
        [
            "## 해석 제한",
            "",
            "- 이 결과는 candidate coverage의 효과만 분리하는 ablation이며 최종 8-case가 아니다.",
            "- AllBase도 전체 화면이 아니라 검출된 base edge만 temporal 처리한다.",
            "- 작은 optical-flow residual은 blur로도 발생할 수 있어 단독 품질 순위가 아니다.",
            "- Forward/backward 불일치 영역은 제외되어 disocclusion ghost를 완전히 재지 않는다.",
            "- `-R`은 camera-motion reprojection이며 object motion vector는 연결되지 않았다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 지표: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
        ]
    )
    report.extend(f"- Flow 진단: `{name}`" for name in diagnostic_names)
    report.extend(f"- 비교 자료: `{name}`" for name in artifact_names)
    report.append("")

    report_name = "SMAA-Candidate-Policy-Jitter-Analysis-ko.md"
    (output / report_name).write_text(
        "\n".join(report), encoding="utf-8"
    )
    print(f"Candidate-policy jitter analysis complete: {output}", flush=True)


if __name__ == "__main__":
    main()
