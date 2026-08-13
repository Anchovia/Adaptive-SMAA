#!/usr/bin/env python3
"""Measure observed temporal contribution in aligned real-scene captures.

The final-output capture is paired with an otherwise identical capture made
with ``-smaaTemporalDebugView 3``.  That debug view exposes the current spatial
AA input before temporal resolve.  Their difference is therefore an observed
output contribution from temporal history, not merely a candidate count.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_optical_flow_temporal_quality import (
    alignment_map,
    masked_error_metrics,
    remap_array,
    require_opencv,
    run_self_test,
)


FRAME_PATTERN = re.compile(r"(?:^|_)frame_(\d+)$", re.IGNORECASE)
MODES = (
    ("o_1x", "O-1X", "O_1X"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R"),
    (
        "candidate_jitter_r",
        "ABL-Candidate-Jitter-R",
        "ABL_Candidate_Jitter_R",
    ),
    (
        "candidate_no_jitter_r",
        "ABL-Candidate-NoJitter-R",
        "ABL_Candidate_NoJitter_R",
    ),
    (
        "o_et2x_r_document",
        "O-ET2X-R-Document",
        "O_ET2X_R_Document",
    ),
)
EDGE_SELECTIVE_KEYS = {
    "candidate_jitter_r",
    "candidate_no_jitter_r",
    "o_et2x_r_document",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze real-scene O-1X/Standard/candidate jitter isolation/"
            "document-profile captures and their current-spatial debug pair."
        )
    )
    parser.add_argument("final_capture_root", type=Path)
    parser.add_argument("spatial_capture_root", type=Path)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--expected-frames", type=int, required=True)
    parser.add_argument(
        "--candidate-mask-root",
        type=Path,
        help=(
            "Optional matching -smaaTemporalDebugView 2 capture. When present, "
            "history-output differences are also measured inside the candidate mask."
        ),
    )
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--analysis-scale", type=float, default=0.5)
    parser.add_argument("--fb-threshold", type=float, default=1.0)
    parser.add_argument(
        "--classification",
        choices=("engineering", "formal"),
        default="engineering",
    )
    parser.add_argument("--representative-frame", type=int)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def frame_index(path: Path) -> int:
    match = FRAME_PATTERN.search(path.stem)
    if match is None:
        raise RuntimeError(f"Invalid capture filename: {path.name}")
    return int(match.group(1))


def collect_frames(root: Path, expected: int) -> tuple[dict[str, list[Path]], tuple[int, int]]:
    paths: dict[str, list[Path]] = {}
    resolution: tuple[int, int] | None = None
    for key, _, directory_name in MODES:
        directory = root / directory_name
        frames = sorted(directory.glob("*.png"), key=frame_index)
        indices = [frame_index(path) for path in frames]
        if indices != list(range(expected)):
            raise RuntimeError(
                f"{directory}: expected contiguous 0..{expected - 1}, "
                f"found {len(indices)} frames"
            )
        with Image.open(frames[0]) as image:
            current_resolution = image.size
        if resolution is None:
            resolution = current_resolution
        elif current_resolution != resolution:
            raise RuntimeError(
                f"Resolution mismatch: {directory} has {current_resolution}, "
                f"expected {resolution}"
            )
        paths[key] = frames
    assert resolution is not None
    return paths, resolution


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def scaled_rgb(rgb: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return rgb
    library = require_opencv()
    width = max(2, round(rgb.shape[1] * scale))
    height = max(2, round(rgb.shape[0] * scale))
    return library.resize(rgb, (width, height), interpolation=library.INTER_AREA)


def luma(rgb: np.ndarray) -> np.ndarray:
    value = rgb.astype(np.float32)
    return value[..., 0] * 0.2126 + value[..., 1] * 0.7152 + value[..., 2] * 0.0722


def rgb_mae(first: np.ndarray, second: np.ndarray) -> float:
    return float(
        np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(
            dtype=np.float64
        )
    )


def contribution_metrics(final: np.ndarray, spatial: np.ndarray) -> dict[str, float]:
    delta = np.abs(final.astype(np.int16) - spatial.astype(np.int16))
    pixel_delta = delta.max(axis=2)
    return {
        "history_output_rgb_mae": float(delta.mean(dtype=np.float64)),
        "history_output_pixel_ratio_gt1": float((pixel_delta > 1).mean(dtype=np.float64)),
        "history_output_pixel_ratio_gt2": float((pixel_delta > 2).mean(dtype=np.float64)),
        "history_output_pixel_ratio_gt8": float((pixel_delta > 8).mean(dtype=np.float64)),
    }


def masked_contribution_metrics(
    final: np.ndarray, spatial: np.ndarray, mask_rgb: np.ndarray
) -> dict[str, float]:
    mask = mask_rgb.max(axis=2) > 127
    if not np.any(mask):
        return {
            "candidate_mask_ratio": 0.0,
            "candidate_history_output_rgb_mae": float("nan"),
            "candidate_history_changed_ratio_gt2": float("nan"),
        }
    delta = np.abs(final.astype(np.int16) - spatial.astype(np.int16))
    pixel_delta = delta.max(axis=2)
    return {
        "candidate_mask_ratio": float(mask.mean(dtype=np.float64)),
        "candidate_history_output_rgb_mae": float(
            delta[mask].mean(dtype=np.float64)
        ),
        "candidate_history_changed_ratio_gt2": float(
            (pixel_delta[mask] > 2).mean(dtype=np.float64)
        ),
    }


def mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return float(np.mean(finite, dtype=np.float64)) if finite else float("nan")


def relative_percent(value: float, baseline: float) -> float:
    if not math.isfinite(value) or not math.isfinite(baseline) or baseline == 0.0:
        return float("nan")
    return 100.0 * value / baseline


def stabilization_retention(value: float, spatial: float, standard: float) -> float:
    denominator = spatial - standard
    if not all(math.isfinite(item) for item in (value, spatial, standard)):
        return float("nan")
    if denominator <= 1e-6:
        return float("nan")
    return 100.0 * (spatial - value) / denominator


def fmt(value: float, digits: int = 6) -> str:
    return "N/A" if not math.isfinite(value) else f"{value:.{digits}f}"


def make_sheet(
    output: Path,
    frame: int,
    final_paths: dict[str, list[Path]],
    spatial_paths: dict[str, list[Path]],
) -> None:
    tile_width = 300
    header = 26
    row_label = 24
    with Image.open(final_paths["o_1x"][frame]) as sample_image:
        sample = sample_image.convert("RGB")
        tile_height = max(1, round(sample.height * tile_width / sample.width))
    canvas = Image.new(
        "RGB",
        (tile_width * len(MODES), header + 3 * (tile_height + row_label)),
        "black",
    )
    draw = ImageDraw.Draw(canvas)
    for column, (key, label, _) in enumerate(MODES):
        draw.text((column * tile_width + 5, 7), label, fill="white")
        final = load_rgb(final_paths[key][frame])
        spatial = load_rgb(spatial_paths[key][frame])
        difference = np.clip(
            np.abs(final.astype(np.float32) - spatial.astype(np.float32)) * 8.0,
            0.0,
            255.0,
        ).astype(np.uint8)
        for row, (row_name, image) in enumerate(
            (("final", final), ("current spatial", spatial), ("|final-spatial| x8", difference))
        ):
            tile = Image.fromarray(image).resize(
                (tile_width, tile_height), Image.Resampling.LANCZOS
            )
            y = header + row * (tile_height + row_label)
            canvas.paste(tile, (column * tile_width, y))
            if column == 0:
                draw.text((5, y + tile_height + 5), row_name, fill="white")
    canvas.save(output, compress_level=3)


def main() -> int:
    args = parse_args()
    require_opencv()
    if args.expected_frames < 2:
        raise ValueError("--expected-frames must be at least 2")
    if not 0.1 <= args.analysis_scale <= 1.0:
        raise ValueError("--analysis-scale must be within [0.1, 1.0]")
    if args.fb_threshold <= 0.0:
        raise ValueError("--fb-threshold must be positive")

    final_root = args.final_capture_root.resolve()
    spatial_root = args.spatial_capture_root.resolve()
    output = (args.output or (final_root / "TemporalRetentionAnalysis")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    final_paths, resolution = collect_frames(final_root, args.expected_frames)
    spatial_paths, spatial_resolution = collect_frames(
        spatial_root, args.expected_frames
    )
    if spatial_resolution != resolution:
        raise RuntimeError(
            f"Final/spatial resolution mismatch: {resolution} vs {spatial_resolution}"
        )
    mask_paths: dict[str, list[Path]] | None = None
    if args.candidate_mask_root is not None:
        mask_paths, mask_resolution = collect_frames(
            args.candidate_mask_root.resolve(), args.expected_frames
        )
        if mask_resolution != resolution:
            raise RuntimeError(
                f"Final/mask resolution mismatch: {resolution} vs {mask_resolution}"
            )

    self_test = run_self_test()
    if not self_test["pass"]:
        raise RuntimeError("Optical-flow synthetic self-test failed")

    rows: list[dict[str, Any]] = []
    previous_scaled: dict[str, np.ndarray] | None = None
    previous_luma: dict[str, np.ndarray] | None = None
    previous2_luma: dict[str, np.ndarray] | None = None

    for frame in range(args.expected_frames):
        current_full = {
            key: load_rgb(final_paths[key][frame]) for key, _, _ in MODES
        }
        spatial_full = {
            key: load_rgb(spatial_paths[key][frame]) for key, _, _ in MODES
        }
        mask_full = (
            {key: load_rgb(mask_paths[key][frame]) for key, _, _ in MODES}
            if mask_paths is not None
            else None
        )
        current_scaled = {
            key: scaled_rgb(current_full[key], args.analysis_scale)
            for key, _, _ in MODES
        }
        current_luma = {
            key: luma(current_scaled[key]) for key, _, _ in MODES
        }
        row: dict[str, Any] = {"frame": frame}

        for key, _, _ in MODES:
            for name, value in contribution_metrics(
                current_full[key], spatial_full[key]
            ).items():
                row[f"{key}_{name}"] = value
            if mask_full is not None and key in EDGE_SELECTIVE_KEYS:
                for name, value in masked_contribution_metrics(
                    current_full[key], spatial_full[key], mask_full[key]
                ).items():
                    row[f"{key}_{name}"] = value
            row[f"{key}_same_frame_rgb_mae_vs_o_1x"] = rgb_mae(
                current_full[key], current_full["o_1x"]
            )
            if previous_scaled is None:
                row[f"{key}_adjacent_luma_mae"] = float("nan")
                row[f"{key}_flow_aligned_rgb_mae"] = float("nan")
            else:
                row[f"{key}_adjacent_luma_mae"] = float(
                    np.abs(current_luma[key] - previous_luma[key]).mean(
                        dtype=np.float64
                    )
                )
            if previous2_luma is None:
                row[f"{key}_second_luma_difference"] = float("nan")
            else:
                row[f"{key}_second_luma_difference"] = float(
                    np.abs(
                        current_luma[key]
                        - 2.0 * previous_luma[key]
                        + previous2_luma[key]
                    ).mean(dtype=np.float64)
                )

        if previous_scaled is not None:
            fields = alignment_map(
                previous_scaled["o_1x"],
                current_scaled["o_1x"],
                args.fb_threshold,
            )
            valid = fields["valid"]
            row["flow_valid_ratio"] = float(valid.mean(dtype=np.float64))
            for key, _, _ in MODES:
                warped = remap_array(
                    previous_scaled[key].astype(np.float32),
                    fields["map_x"],
                    fields["map_y"],
                    require_opencv().INTER_LINEAR,
                )
                aligned, _ = masked_error_metrics(
                    current_scaled[key], warped, valid
                )
                row[f"{key}_flow_aligned_rgb_mae"] = aligned
        else:
            row["flow_valid_ratio"] = float("nan")

        rows.append(row)
        previous2_luma = previous_luma
        previous_luma = current_luma
        previous_scaled = current_scaled
        print(f"Processed frame {frame + 1}/{args.expected_frames}", flush=True)

    csv_name = "real_scene_temporal_retention_metrics.csv"
    with (output / csv_name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary: dict[str, dict[str, float]] = {}
    for key, label, _ in MODES:
        summary[key] = {
            "history_output_rgb_mae": mean(
                [row[f"{key}_history_output_rgb_mae"] for row in rows]
            ),
            "history_output_pixel_ratio_gt1": mean(
                [row[f"{key}_history_output_pixel_ratio_gt1"] for row in rows]
            ),
            "history_output_pixel_ratio_gt2": mean(
                [row[f"{key}_history_output_pixel_ratio_gt2"] for row in rows]
            ),
            "history_output_pixel_ratio_gt8": mean(
                [row[f"{key}_history_output_pixel_ratio_gt8"] for row in rows]
            ),
            "same_frame_rgb_mae_vs_o_1x": mean(
                [row[f"{key}_same_frame_rgb_mae_vs_o_1x"] for row in rows]
            ),
            "adjacent_luma_mae": mean(
                [row[f"{key}_adjacent_luma_mae"] for row in rows]
            ),
            "second_luma_difference": mean(
                [row[f"{key}_second_luma_difference"] for row in rows]
            ),
            "flow_aligned_rgb_mae": mean(
                [row[f"{key}_flow_aligned_rgb_mae"] for row in rows]
            ),
        }
        if mask_paths is not None and key in EDGE_SELECTIVE_KEYS:
            summary[key].update(
                {
                    "candidate_mask_ratio": mean(
                        [row[f"{key}_candidate_mask_ratio"] for row in rows]
                    ),
                    "candidate_history_output_rgb_mae": mean(
                        [
                            row[f"{key}_candidate_history_output_rgb_mae"]
                            for row in rows
                        ]
                    ),
                    "candidate_history_changed_ratio_gt2": mean(
                        [
                            row[f"{key}_candidate_history_changed_ratio_gt2"]
                            for row in rows
                        ]
                    ),
                }
            )
        summary[key]["semantic_id"] = label  # type: ignore[assignment]

    standard = summary["o_t2x_r"]
    spatial = summary["o_1x"]
    for key, _, _ in MODES:
        values = summary[key]
        values["history_contribution_vs_standard_percent"] = relative_percent(
            values["history_output_rgb_mae"],
            standard["history_output_rgb_mae"],
        )
        values["changed_coverage_vs_standard_percent"] = relative_percent(
            values["history_output_pixel_ratio_gt2"],
            standard["history_output_pixel_ratio_gt2"],
        )
        values["one_x_output_effect_vs_standard_percent"] = relative_percent(
            values["same_frame_rgb_mae_vs_o_1x"],
            standard["same_frame_rgb_mae_vs_o_1x"],
        )
        values["flow_stabilization_retention_vs_standard_percent"] = (
            stabilization_retention(
                values["flow_aligned_rgb_mae"],
                spatial["flow_aligned_rgb_mae"],
                standard["flow_aligned_rgb_mae"],
            )
        )
        if mask_paths is not None and key in EDGE_SELECTIVE_KEYS:
            values["candidate_history_mae_vs_candidate_jitter_percent"] = (
                relative_percent(
                    values["candidate_history_output_rgb_mae"],
                    summary["candidate_jitter_r"][
                        "candidate_history_output_rgb_mae"
                    ],
                )
            )

    representative = (
        args.representative_frame
        if args.representative_frame is not None
        else args.expected_frames // 2
    )
    representative = max(0, min(representative, args.expected_frames - 1))
    sheet_name = f"temporal_retention_frame_{representative:05d}.png"
    make_sheet(
        output / sheet_name,
        representative,
        final_paths,
        spatial_paths,
    )

    result = {
        "scene": args.scene,
        "profile": args.profile,
        "classification": args.classification,
        "dilation_enabled": False,
        "resolution": list(resolution),
        "analysis_scale": args.analysis_scale,
        "capture_frames_per_mode": args.expected_frames,
        "warmup_frames_per_mode": args.warmup_frames,
        "final_capture_root": str(final_root),
        "current_spatial_capture_root": str(spatial_root),
        "candidate_mask_capture_root": (
            str(args.candidate_mask_root.resolve())
            if args.candidate_mask_root is not None
            else None
        ),
        "flow_reference": "O-1X",
        "flow_valid_ratio_mean": mean([row["flow_valid_ratio"] for row in rows]),
        "optical_flow_self_test": self_test,
        "summary": summary,
        "artifacts": {
            "metrics_csv": csv_name,
            "representative_sheet": sheet_name,
        },
    }
    json_name = "real_scene_temporal_retention_summary.json"
    (output / json_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# 실제 장면 SMAA temporal 유지율 기준선",
        "",
        "## 범위",
        "",
        f"- 장면/카메라 경로: `{args.scene}` / `{args.profile}`",
        f"- 분류: `{args.classification}`",
        f"- 해상도: {resolution[0]}×{resolution[1]}",
        f"- mode별 warm-up {args.warmup_frames}프레임, 저장 {args.expected_frames}프레임",
        "- current-edge dilation: 비활성화",
        "- final 출력과 별도 `CurrentSpatial` debug capture를 동일 프레임끼리 비교",
        "",
        "`final - CurrentSpatial` 차이는 candidate 수가 아니라 화면 출력에 실제로 나타난",
        "history 기여의 대용값이다. 다만 history 색과 현재 색이 같은 픽셀은 기여가 있어도",
        "차이가 0일 수 있으므로 정확한 shader sample 횟수로 해석하지 않는다.",
        "",
        "## 요약",
        "",
        "| Mode | history 출력 MAE | 변경 픽셀 >2 | O-1X 출력 거리 | Standard 대비 출력 효과 | Flow 정렬 MAE | Standard 안정화 유지율 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, label, _ in MODES:
        values = summary[key]
        report.append(
            f"| `{label}` | {fmt(values['history_output_rgb_mae'])} | "
            f"{values['history_output_pixel_ratio_gt2']:.3%} | "
            f"{fmt(values['same_frame_rgb_mae_vs_o_1x'])} | "
            f"{fmt(values['one_x_output_effect_vs_standard_percent'], 2)}% | "
            f"{fmt(values['flow_aligned_rgb_mae'])} | "
            f"{fmt(values['flow_stabilization_retention_vs_standard_percent'], 2)}% |"
        )

    report.extend(
        [
            "",
            "## 해석 규칙",
            "",
            "- `history 출력 MAE/변경 픽셀`이 작으면 최종 화면에 나타난 history 영향 범위가 작다.",
            "- `Standard 대비 출력 효과`는 O-1X와의 same-frame 거리를 O-T2X-R=100%로 정규화한 값이다. 0%에 가까우면 최종 출력이 O-1X에 가까워졌다는 뜻이며, 정확한 history sample count는 아니다.",
            "- `Flow 정렬 MAE`는 O-1X에서 구한 동일한 Farneback flow로 camera motion을 보정한 보조 지표다.",
            "- `Standard 안정화 유지율` 100%는 O-T2X-R과 같은 감소, 0%는 O-1X와 같은 시간 변화량을 뜻한다.",
            "- 안정화 유지율은 blur도 낮은 잔차로 만들 수 있으므로 품질 점수가 아니다.",
            "- Candidate-Jitter/NoJitter 차이는 후보 선택을 유지한 채 projection jitter 효과를 분리한다.",
            "- O-ET2X-R-Document에는 candidate selection 외에 Catmull-Rom, clipping, history weight 0.8이 포함된다.",
            "- 이 결과와 기존 CGVQM/reference 비교를 함께 본 뒤에만 dilation 필요성을 결정한다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 측정: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
            f"- 대표 5-way final/spatial/difference: `{sheet_name}`",
            "",
        ]
    )
    if mask_paths is not None:
        report.extend(
            [
                "",
                "## Candidate mask 내부 history 출력 기여",
                "",
                "| Mode | 후보 화면 비율 | 후보 내부 final-spatial MAE | 후보 내부 >2 변경률 | Candidate-Jitter 대비 MAE |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for key, label, _ in MODES:
            if key not in EDGE_SELECTIVE_KEYS:
                continue
            values = summary[key]
            report.append(
                f"| `{label}` | {values['candidate_mask_ratio']:.3%} | "
                f"{fmt(values['candidate_history_output_rgb_mae'])} | "
                f"{values['candidate_history_changed_ratio_gt2']:.3%} | "
                f"{fmt(values['candidate_history_mae_vs_candidate_jitter_percent'], 2)}% |"
            )
        report.extend(
            [
                "",
                "이 표는 후보 픽셀에 한정한 관측 출력 차이다. Candidate-Jitter와 NoJitter의",
                "projection sample 위치가 서로 다르므로 두 final-spatial 값은 각 mode 내부의",
                "history 영향 대용값으로만 사용하고 정확한 sample 수로 표현하지 않는다.",
            ]
        )
    report_name = "SMAA-Real-Scene-Temporal-Retention-ko.md"
    (output / report_name).write_text("\n".join(report), encoding="utf-8")
    print(f"Temporal-retention analysis complete: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
