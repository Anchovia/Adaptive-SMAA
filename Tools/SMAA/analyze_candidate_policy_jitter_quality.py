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


CANDIDATE_POLICY_MODES = (
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

CANDIDATE_POLICY_COMPARISONS = (
    ("standard_vs_1x", "o_1x", "standard"),
    ("intel_vs_standard", "standard", "candidate_intel"),
    ("allbase_vs_standard", "standard", "candidate_allbase"),
    ("allbase_vs_intel", "candidate_intel", "candidate_allbase"),
)

JITTER_ISOLATION_MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("standard", "O-T2X-R", "O_T2X_R"),
    (
        "candidate_jitter",
        "ABL-Candidate-Jitter-R",
        "ABL_Candidate_Jitter_R",
    ),
    (
        "candidate_no_jitter",
        "ABL-Candidate-NoJitter-R",
        "ABL_Candidate_NoJitter_R",
    ),
)

JITTER_ISOLATION_COMPARISONS = (
    ("standard_vs_1x", "o_1x", "standard"),
    ("candidate_jitter_vs_standard", "standard", "candidate_jitter"),
    (
        "candidate_no_jitter_vs_standard",
        "standard",
        "candidate_no_jitter",
    ),
    (
        "no_jitter_vs_jitter",
        "candidate_jitter",
        "candidate_no_jitter",
    ),
)

HYBRID_RESOLVE_MODES = JITTER_ISOLATION_MODES + (
    (
        "candidate_dejitter",
        "ABL-Candidate-DeJitter-R",
        "ABL_Candidate_DeJitter_R",
    ),
)

HYBRID_RESOLVE_COMPARISONS = (
    ("standard_vs_1x", "o_1x", "standard"),
    ("candidate_jitter_vs_standard", "standard", "candidate_jitter"),
    (
        "candidate_no_jitter_vs_candidate_jitter",
        "candidate_jitter",
        "candidate_no_jitter",
    ),
    (
        "candidate_dejitter_vs_candidate_jitter",
        "candidate_jitter",
        "candidate_dejitter",
    ),
    (
        "candidate_dejitter_vs_candidate_no_jitter",
        "candidate_no_jitter",
        "candidate_dejitter",
    ),
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
    parser.add_argument(
        "--profile",
        choices=("candidate-policy", "jitter-isolation", "hybrid-resolve"),
        default="candidate-policy",
    )
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
    if args.profile == "hybrid-resolve":
        modes = HYBRID_RESOLVE_MODES
        comparisons = HYBRID_RESOLVE_COMPARISONS
        primary_key = "candidate_jitter"
        secondary_key = "candidate_dejitter"
        primary_label = "Jittered spatial base"
        secondary_label = "De-jittered spatial base"
        report_title = "SMAA candidate/noncandidate hybrid resolve 분석"
        controlled_difference = (
            "CurrentSpatial versus DeJitteredSpatial noncandidate base; "
            "both use SMAA T2X jitter/subsample, IntelFamilyNonDominant "
            "candidates, camera reprojection, bilinear history, clipping "
            "Off, and weight 0.5"
        )
        profile_lines = [
            "후보 temporal 경로의 jitter sample diversity를 유지하면서",
            "비후보의 current spatial base만 inverse-jitter 재구성했을 때",
            "전역 jitter와 후보 한정 resolve의 범위 불일치가 줄어드는지 검증한다.",
            "",
            "- `O-1X`: spatial-only 품질 control",
            "- `O-T2X-R`: 전체 화면 Standard T2X + camera reprojection",
            "- `ABL-Candidate-Jitter-R`: 후보 temporal + jittered current spatial base",
            "- `ABL-Candidate-NoJitter-R`: prior global no-jitter control",
            "- `ABL-Candidate-DeJitter-R`: 후보 jitter 유지 + 비후보 inverse-jitter base",
            "- Candidate Jitter와 Candidate DeJitter의 유일한 차이는 noncandidate base",
        ]
        profile_invariant_lines = [
            "- 두 matched candidate mode 모두 Intel-family 후보, T2X jitter/subsample,",
            "  camera reprojection, bilinear sampler, clipping Off, history weight 0.5를 유지",
        ]
        profile_limit_lines = [
            "- DeJitter는 현재 spatial SMAA 결과의 bilinear screen-space 재구성이며 별도 unjittered scene render가 아니다.",
            "- 이 hybrid는 Intel 공개 TSCMAA 필수 항목이 아닌 후속 연구용 ablation이다.",
        ]
        default_output_name = "HybridResolveAnalysis"
        artifact_prefix = "hybrid_resolve"
        report_name = "SMAA-Hybrid-Resolve-Analysis-ko.md"
    elif args.profile == "jitter-isolation":
        modes = JITTER_ISOLATION_MODES
        comparisons = JITTER_ISOLATION_COMPARISONS
        primary_key = "candidate_jitter"
        secondary_key = "candidate_no_jitter"
        primary_label = "Jitter On"
        secondary_label = "Jitter Off"
        report_title = "SMAA candidate-only projection jitter 분리 분석"
        controlled_difference = (
            "SMAAT2X deliberate projection jitter On versus Off; both use "
            "IntelFamilyNonDominant candidates, camera reprojection, "
            "bilinear history, clipping Off, and weight 0.5"
        )
        profile_lines = [
            "Intel-family candidate와 나머지 temporal 설정을 유지한 상태에서",
            "전역 SMAA T2X projection jitter만 끄면 비후보 픽셀의 temporal",
            "variation이 감소하는지 분리한다.",
            "",
            "- `O-1X`: spatial-only 품질 control",
            "- `O-T2X-R`: 전체 화면 Standard T2X + camera reprojection",
            "- `ABL-Candidate-Jitter-R`: 후보에만 temporal, projection jitter On",
            "- `ABL-Candidate-NoJitter-R`: 후보에만 temporal, projection jitter Off",
            "- 두 candidate mode의 유일한 설정 차이는 projection jitter",
        ]
        profile_invariant_lines = [
            "- 두 candidate mode 모두 Intel-family 후보, camera reprojection,",
            "  bilinear sampler, clipping Off, history weight 0.5를 동일하게 유지",
        ]
        profile_limit_lines = [
            "- Jitter Off는 candidate-aware jitter가 아니라 전역 deliberate jitter 비활성화 진단이다.",
            "- Jitter를 끄면 temporal subpixel sample diversity도 줄 수 있어 안정성만으로 품질 우위를 정할 수 없다.",
        ]
        default_output_name = "CandidateJitterIsolationAnalysis"
        artifact_prefix = "candidate_jitter_isolation"
        report_name = "SMAA-Candidate-Jitter-Isolation-Analysis-ko.md"
    else:
        modes = CANDIDATE_POLICY_MODES
        comparisons = CANDIDATE_POLICY_COMPARISONS
        primary_key = "candidate_intel"
        secondary_key = "candidate_allbase"
        primary_label = "Intel 후보"
        secondary_label = "AllBase 후보"
        report_title = "SMAA candidate 정책·T2X jitter 분리 분석"
        controlled_difference = (
            "IntelFamilyNonDominant versus AllBaseEdges candidate policy; "
            "both use O-T2X-R jitter, camera reprojection, bilinear "
            "history, clipping Off, and weight 0.5"
        )
        profile_lines = [
            "전역 SMAA T2X projection jitter를 유지한 상태에서 candidate 누락이",
            "Edge-selective temporal variation의 원인인지 분리한다.",
            "",
            "- `O-1X`: spatial-only 품질 control",
            "- `O-T2X-R`: 전체 화면 Standard T2X + camera reprojection",
            "- `ABL-Candidate-Intel-R`: Intel-family non-dominant 후보만 temporal 적용",
            "- `ABL-Candidate-AllBase-R`: 검출된 모든 base edge에 temporal 적용",
            "- 두 candidate mode의 유일한 설정 차이는 candidate policy",
        ]
        profile_invariant_lines = [
            "- 두 candidate mode 모두 jitter/subsample, reprojection, bilinear sampler,",
            "  clipping Off, history weight 0.5를 동일하게 유지",
        ]
        profile_limit_lines = [
            "- AllBase도 전체 화면이 아니라 검출된 base edge만 temporal 처리한다.",
        ]
        default_output_name = "CandidatePolicyJitterAnalysis"
        artifact_prefix = "candidate_policy_jitter"
        report_name = "SMAA-Candidate-Policy-Jitter-Analysis-ko.md"
    output = (
        args.output.resolve()
        if args.output is not None
        else root / default_output_name
    )
    output.mkdir(parents=True, exist_ok=True)
    paths, resolution, input_validation = validate_inputs(
        root, args.expected_frames, modes
    )
    boxes = roi_boxes(args.scenario, resolution)
    labels = {key: semantic_id for key, semantic_id, _ in modes}

    self_test = run_self_test()
    if not self_test["pass"]:
        raise RuntimeError("Synthetic optical-flow self-test failed")

    rows: list[dict[str, Any]] = []
    previous_full: dict[str, np.ndarray] | None = None
    diagnostic_names: list[str] = []
    center = visual_center_frame(args.scenario)

    for frame in range(args.expected_frames):
        current_full = {
            key: load_rgb(paths[key][frame]) for key, _, _ in modes
        }
        if previous_full is None:
            previous_full = current_full
            continue

        row: dict[str, Any] = {"frame": frame}
        for roi_name, box in boxes.items():
            previous_rois = {
                key: crop_half(previous_full[key], box) for key, _, _ in modes
            }
            current_rois = {
                key: crop_half(current_full[key], box) for key, _, _ in modes
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
            for key, _, _ in modes:
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

            for key in (primary_key, secondary_key):
                row[f"{roi_name}_{key}_same_frame_mae_vs_standard"] = rgb_mae(
                    current_rois[key], current_rois["standard"]
                )
            row[f"{roi_name}_{secondary_key}_same_frame_mae_vs_{primary_key}"] = rgb_mae(
                current_rois[secondary_key],
                current_rois[primary_key],
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

    csv_name = f"{artifact_prefix}_metrics.csv"
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
    isolated_effects: dict[str, Any] = {}
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
        primary = summary[
            f"{roi_name}_{primary_key}_flow_aligned_rgb_mae"
        ]["mean"]
        secondary = summary[
            f"{roi_name}_{secondary_key}_flow_aligned_rgb_mae"
        ]["mean"]
        primary_distance = abs(primary - standard)
        secondary_distance = abs(secondary - standard)
        isolated_effects[roi_name] = {
            "primary_key": primary_key,
            "secondary_key": secondary_key,
            "secondary_vs_primary_aligned_mae_percent": safe_percent_delta(
                secondary, primary
            ),
            "primary_distance_to_standard": primary_distance,
            "secondary_distance_to_standard": secondary_distance,
            "secondary_distance_reduction_vs_primary_percent": (
                100.0
                * (primary_distance - secondary_distance)
                / primary_distance
                if primary_distance > 0.0
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
                modes,
                artifact_prefix,
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
                modes,
                artifact_prefix,
            )
        )

    result = {
        "scenario": args.scenario,
        "profile": args.profile,
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
            "controlled_difference": controlled_difference,
        },
        "input_validation": input_validation,
        "synthetic_self_test": self_test,
        "flow_checks": flow_checks,
        "isolated_effects": isolated_effects,
        "roi_boxes": {name: list(box) for name, box in boxes.items()},
        "summary": summary,
        "artifacts": {
            "metrics_csv": csv_name,
            "diagnostics": diagnostic_names,
            "comparisons": artifact_names,
        },
    }
    json_name = f"{artifact_prefix}_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        f"# {report_title}",
        "",
        "## 목적",
        "",
        *profile_lines,
        *profile_invariant_lines,
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
        effect = isolated_effects[roi_name]
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
        for key, semantic_id, _ in modes:
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
        for _, baseline_key, current_key in comparisons:
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
                f"- {primary_label}의 Standard 거리: {effect['primary_distance_to_standard']:.6f}",
                f"- {secondary_label}의 Standard 거리: {effect['secondary_distance_to_standard']:.6f}",
                f"- {secondary_label} 전환에 따른 Standard 거리 감소율: "
                f"{effect['secondary_distance_reduction_vs_primary_percent']:+.3f}%",
                "",
            ]
        )

    report.extend(
        [
            "## 해석 제한",
            "",
            "- 이 결과는 한 설정 요소만 분리하는 진단 ablation이며 최종 8-case가 아니다.",
            *profile_limit_lines,
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

    (output / report_name).write_text(
        "\n".join(report), encoding="utf-8"
    )
    print(f"{report_title} complete: {output}", flush=True)


if __name__ == "__main__":
    main()
