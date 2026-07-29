from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


MODES = (
    ("o_t2x", "O-T2X", "O_T2X"),
    ("o_t2x_r", "O-T2X-R", "O_T2X_R"),
    ("o_et2x", "O-ET2X", "O_ET2X"),
    ("o_et2x_r", "O-ET2X-R", "O_ET2X_R"),
)
PAIRS = (
    ("edge_vs_standard_no_reprojection", "o_t2x", "o_et2x"),
    ("edge_vs_standard_reprojected", "o_t2x_r", "o_et2x_r"),
    ("standard_reprojection_effect", "o_t2x", "o_t2x_r"),
    ("edge_reprojection_effect", "o_et2x", "o_et2x_r"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze aligned O-T2X/O-T2X-R/O-ET2X/O-ET2X-R PNG sequences."
    )
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-frames", type=int, default=300)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--start-time", type=float, default=1.0)
    return parser.parse_args()


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def half_luma(rgb: np.ndarray) -> np.ndarray:
    small = rgb[::2, ::2].astype(np.float32)
    return small[..., 0] * 0.2126 + small[..., 1] * 0.7152 + small[..., 2] * 0.0722


def edge_strength(gray: np.ndarray) -> float:
    dx = np.abs(gray[:, 1:] - gray[:, :-1]).mean(dtype=np.float64)
    dy = np.abs(gray[1:, :] - gray[:-1, :]).mean(dtype=np.float64)
    return float((dx + dy) * 0.5)


def difference_metrics(first: np.ndarray, second: np.ndarray) -> dict[str, float]:
    difference = np.abs(first.astype(np.int16) - second.astype(np.int16))
    maximum_channel = difference.max(axis=2)
    return {
        "mae": float(difference.mean(dtype=np.float64)),
        "rmse": float(
            np.sqrt(np.square(difference.astype(np.float32)).mean(dtype=np.float64))
        ),
        "pixels_gt2_pct": float(np.mean(maximum_channel > 2) * 100.0),
        "pixels_gt8_pct": float(np.mean(maximum_channel > 8) * 100.0),
    }


def add_metrics(row: dict[str, Any], prefix: str, values: dict[str, float]) -> None:
    for key, value in values.items():
        row[f"{prefix}_{key}"] = value


def aggregate(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    values = [float(row[key]) for row in rows if row.get(key, "") != ""]
    ordered = sorted(values)
    return {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "p95": ordered[min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)],
        "max": ordered[-1],
    }


def percent_delta(value: float, baseline: float) -> float:
    return (value - baseline) / baseline * 100.0 if baseline != 0.0 else 0.0


def separated_top_frames(
    rows: list[dict[str, Any]], key: str, count: int = 2, spacing: int = 45
) -> list[int]:
    candidates = sorted(
        (row for row in rows if row.get(key, "") != ""),
        key=lambda row: float(row[key]),
        reverse=True,
    )
    selected: list[int] = []
    for row in candidates:
        frame = int(row["frame"])
        if all(abs(frame - existing) >= spacing for existing in selected):
            selected.append(frame)
            if len(selected) == count:
                break
    return selected


def validate_inputs(
    capture_root: Path, expected_frames: int
) -> tuple[dict[str, list[Path]], tuple[int, int], dict[str, Any]]:
    paths: dict[str, list[Path]] = {}
    resolution: tuple[int, int] | None = None
    validation: dict[str, Any] = {"modes": {}}

    for key, semantic_id, directory_name in MODES:
        mode_paths = sorted((capture_root / directory_name).glob("*.png"))
        if len(mode_paths) != expected_frames:
            raise RuntimeError(
                f"{semantic_id}: expected {expected_frames} PNGs, found {len(mode_paths)}"
            )

        indices = [int(path.stem.rsplit("_", 1)[1]) for path in mode_paths]
        if indices != list(range(expected_frames)):
            raise RuntimeError(f"{semantic_id}: missing or reordered frame indices")

        hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in mode_paths]
        with Image.open(mode_paths[0]) as image:
            mode_resolution = image.size
        if resolution is None:
            resolution = mode_resolution
        elif resolution != mode_resolution:
            raise RuntimeError(
                f"{semantic_id}: resolution {mode_resolution} differs from {resolution}"
            )

        paths[key] = mode_paths
        validation["modes"][semantic_id] = {
            "directory": directory_name,
            "frame_count": len(mode_paths),
            "first_index": indices[0],
            "last_index": indices[-1],
            "unique_file_hashes": len(set(hashes)),
        }

    assert resolution is not None
    validation["resolution"] = list(resolution)
    validation["frame_count_per_mode"] = expected_frames
    return paths, resolution, validation


def find_roi(
    paths: dict[str, list[Path]],
    resolution: tuple[int, int],
    frame: int,
    first_key: str,
    second_key: str,
) -> tuple[int, int, int, int]:
    first = load_rgb(paths[first_key][frame])
    second = load_rgb(paths[second_key][frame])
    energy = (
        np.abs(first.astype(np.int16) - second.astype(np.int16))
        .max(axis=2)
        .astype(np.uint8)
    )
    heat = Image.fromarray(energy).resize((16, 9), Image.Resampling.BOX)
    block_y, block_x = np.unravel_index(np.asarray(heat).argmax(), (9, 16))
    center_x = int((block_x + 0.5) * resolution[0] / 16)
    center_y = int((block_y + 0.5) * resolution[1] / 9)
    width = min(480, resolution[0])
    height = min(270, resolution[1])
    left = min(max(center_x - width // 2, 0), resolution[0] - width)
    top = min(max(center_y - height // 2, 0), resolution[1] - height)
    return left, top, left + width, top + height


def make_four_mode_comparison(
    output: Path,
    paths: dict[str, list[Path]],
    frame: int,
    box: tuple[int, int, int, int],
) -> str:
    width = box[2] - box[0]
    height = box[3] - box[1]
    canvas = Image.new("RGB", (width * 4, height + 35), "black")
    draw = ImageDraw.Draw(canvas)
    for index, (key, semantic_id, _) in enumerate(MODES):
        image = Image.fromarray(load_rgb(paths[key][frame])).crop(box)
        x = index * width
        canvas.paste(image, (x, 35))
        draw.text((x + 8, 10), f"Frame {frame:05d} - {semantic_id}", fill="white")
    name = f"comparison_frame_{frame:05d}.png"
    canvas.save(output / name, compress_level=3)
    return name


def make_pair_gif(
    output: Path,
    paths: dict[str, list[Path]],
    expected_frames: int,
    pair_name: str,
    first_key: str,
    second_key: str,
    center_frame: int,
    box: tuple[int, int, int, int],
) -> str:
    start = min(max(center_frame - 15, 0), max(0, expected_frames - 30))
    end = min(start + 30, expected_frames)
    width = box[2] - box[0]
    height = box[3] - box[1]
    labels = {
        key: semantic_id for key, semantic_id, _ in MODES
    }
    frames: list[Image.Image] = []
    for frame in range(start, end):
        canvas = Image.new("RGB", (width * 2, height + 35), "black")
        draw = ImageDraw.Draw(canvas)
        for index, key in enumerate((first_key, second_key)):
            image = Image.fromarray(load_rgb(paths[key][frame])).crop(box)
            x = index * width
            canvas.paste(image, (x, 35))
            draw.text((x + 8, 10), f"Frame {frame:05d} - {labels[key]}", fill="white")
        frames.append(
            canvas.quantize(colors=192, method=Image.Quantize.MEDIANCUT)
        )

    name = f"comparison_{pair_name}_{start:05d}_{end - 1:05d}.gif"
    frames[0].save(
        output / name,
        save_all=True,
        append_images=frames[1:],
        duration=50,
        loop=0,
        optimize=False,
        disposal=2,
    )
    return name


def make_contact_sheet(
    output: Path,
    paths: dict[str, list[Path]],
    resolution: tuple[int, int],
    expected_frames: int,
) -> str:
    sampled = sorted(
        set(
            int(round(index * (expected_frames - 1) / 5.0))
            for index in range(6)
        )
    )
    thumb_width = 400
    thumb_height = max(1, int(thumb_width * resolution[1] / resolution[0]))
    row_height = thumb_height + 30
    canvas = Image.new("RGB", (thumb_width * 4, row_height * len(sampled)), "black")
    draw = ImageDraw.Draw(canvas)
    for row_index, frame in enumerate(sampled):
        y = row_index * row_height
        for mode_index, (key, semantic_id, _) in enumerate(MODES):
            image = Image.fromarray(load_rgb(paths[key][frame])).resize(
                (thumb_width, thumb_height), Image.Resampling.LANCZOS
            )
            x = mode_index * thumb_width
            canvas.paste(image, (x, y + 30))
            draw.text((x + 8, y + 8), f"{frame:05d} - {semantic_id}", fill="white")
    name = "contact_sheet_original_four.png"
    canvas.save(output / name, compress_level=3)
    return name


def main() -> None:
    args = parse_args()
    capture_root = args.capture_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else capture_root / "Analysis"
    )
    output.mkdir(parents=True, exist_ok=True)

    paths, resolution, validation = validate_inputs(
        capture_root, args.expected_frames
    )
    rows: list[dict[str, Any]] = []
    previous_rgb: dict[str, np.ndarray] | None = None
    previous2_luma: dict[str, np.ndarray] | None = None
    previous_luma: dict[str, np.ndarray] | None = None
    thumbnails: dict[str, list[np.ndarray]] = {key: [] for key, _, _ in MODES}

    for frame in range(args.expected_frames):
        current_rgb = {key: load_rgb(paths[key][frame]) for key, _, _ in MODES}
        current_luma = {key: half_luma(current_rgb[key]) for key, _, _ in MODES}
        row: dict[str, Any] = {"frame": frame}

        for key, _, _ in MODES:
            row[f"{key}_edge_strength"] = edge_strength(current_luma[key])
            thumbnails[key].append(
                np.asarray(
                    Image.fromarray(current_luma[key].astype(np.uint8)).resize(
                        (320, 180), Image.Resampling.BOX
                    ),
                    dtype=np.uint8,
                )
            )
            if previous_rgb is None:
                for metric in ("mae", "rmse", "pixels_gt2_pct", "pixels_gt8_pct"):
                    row[f"{key}_temporal_{metric}"] = ""
                row[f"{key}_second_difference_mae"] = ""
                row[f"{key}_two_frame_mae"] = ""
            else:
                add_metrics(
                    row,
                    f"{key}_temporal",
                    difference_metrics(current_rgb[key], previous_rgb[key]),
                )
                if previous2_luma is None or previous_luma is None:
                    row[f"{key}_second_difference_mae"] = ""
                    row[f"{key}_two_frame_mae"] = ""
                else:
                    row[f"{key}_second_difference_mae"] = float(
                        np.abs(
                            current_luma[key]
                            - 2.0 * previous_luma[key]
                            + previous2_luma[key]
                        ).mean(dtype=np.float64)
                    )
                    row[f"{key}_two_frame_mae"] = float(
                        np.abs(current_luma[key] - previous2_luma[key]).mean(
                            dtype=np.float64
                        )
                    )

        for pair_name, first_key, second_key in PAIRS:
            add_metrics(
                row,
                pair_name,
                difference_metrics(current_rgb[first_key], current_rgb[second_key]),
            )
            if previous_rgb is None:
                row[f"{pair_name}_temporal_mae_delta"] = ""
                row[f"{pair_name}_second_difference_delta"] = ""
            else:
                row[f"{pair_name}_temporal_mae_delta"] = (
                    float(row[f"{second_key}_temporal_mae"])
                    - float(row[f"{first_key}_temporal_mae"])
                )
                if previous2_luma is None:
                    row[f"{pair_name}_second_difference_delta"] = ""
                else:
                    row[f"{pair_name}_second_difference_delta"] = (
                        float(row[f"{second_key}_second_difference_mae"])
                        - float(row[f"{first_key}_second_difference_mae"])
                    )

        rows.append(row)
        previous_rgb = current_rgb
        previous2_luma = previous_luma
        previous_luma = current_luma
        if frame % 25 == 0 or frame == args.expected_frames - 1:
            print(f"Processed {frame + 1}/{args.expected_frames}", flush=True)

    alignment: dict[str, dict[str, Any]] = {}
    for pair_name, first_key, second_key in PAIRS:
        offsets: list[int] = []
        for frame in range(args.expected_frames):
            candidates: list[tuple[float, int]] = []
            for offset in range(-2, 3):
                other = frame + offset
                if 0 <= other < args.expected_frames:
                    mae = float(
                        np.abs(
                            thumbnails[first_key][frame].astype(np.int16)
                            - thumbnails[second_key][other].astype(np.int16)
                        ).mean(dtype=np.float64)
                    )
                    candidates.append((mae, offset))
            offsets.append(min(candidates)[1])
        alignment[pair_name] = {
            "same_index_best": offsets.count(0),
            "offset_counts": {
                str(offset): offsets.count(offset) for offset in range(-2, 3)
            },
        }

    csv_name = "temporal_metrics_original_four.csv"
    with (output / csv_name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary: dict[str, Any] = {}
    for key in rows[0]:
        if key != "frame":
            summary[key] = aggregate(rows, key)

    parity: dict[str, Any] = {}
    for key, semantic_id, _ in MODES:
        for metric in ("temporal_mae", "second_difference_mae"):
            column = f"{key}_{metric}"
            even_values = [
                float(row[column])
                for row in rows
                if row.get(column, "") != "" and int(row["frame"]) % 2 == 0
            ]
            odd_values = [
                float(row[column])
                for row in rows
                if row.get(column, "") != "" and int(row["frame"]) % 2 == 1
            ]
            parity[column] = {
                "semantic_id": semantic_id,
                "even_mean": statistics.fmean(even_values),
                "odd_mean": statistics.fmean(odd_values),
                "absolute_gap": abs(
                    statistics.fmean(even_values) - statistics.fmean(odd_values)
                ),
            }

    representative_frames: dict[str, int] = {}
    comparison_pngs: list[str] = []
    comparison_gifs: list[str] = []
    for pair_name, first_key, second_key in PAIRS[:2]:
        frame = separated_top_frames(
            rows, f"{pair_name}_pixels_gt8_pct", count=1
        )[0]
        representative_frames[pair_name] = frame
        box = find_roi(paths, resolution, frame, first_key, second_key)
        comparison_pngs.append(
            make_four_mode_comparison(output, paths, frame, box)
        )
        comparison_gifs.append(
            make_pair_gif(
                output,
                paths,
                args.expected_frames,
                pair_name,
                first_key,
                second_key,
                frame,
                box,
            )
        )
    comparison_pngs = list(dict.fromkeys(comparison_pngs))
    contact_sheet = make_contact_sheet(
        output, paths, resolution, args.expected_frames
    )

    machine_summary = {
        "validation": validation,
        "capture_conditions": {
            "resolution": list(resolution),
            "frame_rate": 60,
            "capture_frames_per_mode": args.expected_frames,
            "warmup_frames": args.warmup_frames,
            "smaa_preset": "Ultra",
            "vsync": "Off",
            "scene": "Lumberyard Bistro flythrough",
            "start_time_seconds": args.start_time,
        },
        "summary": summary,
        "parity": parity,
        "alignment": alignment,
        "representative_frames": representative_frames,
        "artifacts": {
            "metrics_csv": csv_name,
            "contact_sheet": contact_sheet,
            "comparison_pngs": comparison_pngs,
            "comparison_gifs": comparison_gifs,
        },
    }
    json_name = "analysis_summary_original_four.json"
    (output / json_name).write_text(
        json.dumps(machine_summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    temporal_rows = []
    for key, semantic_id, _ in MODES:
        temporal_rows.append(
            (
                semantic_id,
                summary[f"{key}_temporal_mae"]["mean"],
                summary[f"{key}_second_difference_mae"]["mean"],
                summary[f"{key}_edge_strength"]["mean"],
                parity[f"{key}_temporal_mae"]["absolute_gap"],
            )
        )

    pair_rows = []
    for pair_name, first_key, second_key in PAIRS:
        first_label = next(item[1] for item in MODES if item[0] == first_key)
        second_label = next(item[1] for item in MODES if item[0] == second_key)
        pair_rows.append(
            (
                f"{second_label} vs {first_label}",
                summary[f"{pair_name}_mae"]["mean"],
                summary[f"{pair_name}_pixels_gt8_pct"]["mean"],
                percent_delta(
                    summary[f"{second_key}_temporal_mae"]["mean"],
                    summary[f"{first_key}_temporal_mae"]["mean"],
                ),
                percent_delta(
                    summary[f"{second_key}_second_difference_mae"]["mean"],
                    summary[f"{first_key}_second_difference_mae"]["mean"],
                ),
                percent_delta(
                    summary[f"{second_key}_edge_strength"]["mean"],
                    summary[f"{first_key}_edge_strength"]["mean"],
                ),
            )
        )

    report_lines = [
        "# Original SMAA temporal 4-case 연속 프레임 품질 분석",
        "",
        "## 범위",
        "",
        "Original SMAA의 `O-T2X`, `O-T2X-R`, `O-ET2X`, `O-ET2X-R`를 동일한",
        "Lumberyard Bistro camera path에서 비교한다. 이 분석은 Adaptive 4개를 포함하지 않으며,",
        "Intel 공식 TSCMAA 포팅이 아니라 공개 문서 기반 SMAA adaptation의 중간 품질 결과다.",
        "",
        "## 측정 조건",
        "",
        f"- 해상도: {resolution[0]}×{resolution[1]}",
        "- DirectX 11, Release x64, SMAA Ultra, VSync Off",
        f"- 시작 시간: {args.start_time:.3f}초",
        f"- mode별 warm-up: {args.warmup_frames}프레임",
        f"- mode별 저장: {args.expected_frames}프레임",
        "- 동일 camera path, fixed 60 Hz simulation",
        "- PNG 저장 중 FPS는 capture overhead가 포함되므로 성능 결과로 사용하지 않음",
        "",
        "## 데이터 무결성",
        "",
    ]
    for _, semantic_id, _ in MODES:
        mode_validation = validation["modes"][semantic_id]
        report_lines.append(
            f"- `{semantic_id}`: {mode_validation['frame_count']}프레임, "
            f"{mode_validation['first_index']:05d}~{mode_validation['last_index']:05d}, "
            f"고유 파일 hash {mode_validation['unique_file_hashes']}개"
        )

    report_lines.extend(
        [
            "",
            "## 시간·공간 대용 지표",
            "",
            "| Mode | 인접 프레임 RGB MAE | 2차 시간 차분 Luma MAE | 공간 edge strength | 짝·홀 temporal MAE gap |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for semantic_id, temporal_mae, second_mae, spatial_edge, parity_gap in temporal_rows:
        report_lines.append(
            f"| `{semantic_id}` | {temporal_mae:.6f} | {second_mae:.6f} | "
            f"{spatial_edge:.6f} | {parity_gap:.6f} |"
        )

    report_lines.extend(
        [
            "",
            "## 대응 mode 차이",
            "",
            "| 비교 | 동일 frame RGB MAE | 최대 채널 차이 >8 픽셀 | temporal MAE 변화 | 2차 차분 변화 | edge strength 변화 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for label, pair_mae, gt8, temporal_delta, second_delta, edge_delta in pair_rows:
        report_lines.append(
            f"| {label} | {pair_mae:.6f} | {gt8:.6f}% | "
            f"{temporal_delta:+.3f}% | {second_delta:+.3f}% | {edge_delta:+.3f}% |"
        )

    report_lines.extend(
        [
            "",
            "## 해석 제한",
            "",
            "- optical-flow 보정 없는 인접 프레임 차이는 camera·object motion을 포함한다.",
            "- temporal MAE가 작아도 blur/history 누적 때문일 수 있으므로 안정성 향상으로 단정하지 않는다.",
            "- 2차 시간 차분은 불규칙 변화의 대용 지표이며 ghosting 길이를 직접 측정하지 않는다.",
            "- edge strength 증감은 선명도와 aliasing을 함께 포함하므로 단독 품질 순위가 아니다.",
            "- 대표 PNG/GIF에서 ghosting, shimmer, crawling, flicker, blur와 disocclusion을 눈으로 함께 확인해야 한다.",
            "- 현재 camera-motion reprojection은 object motion vector를 처리하지 않는다.",
            "",
            "## 산출물",
            "",
            f"- 프레임별 지표: `{csv_name}`",
            f"- 기계 판독 요약: `{json_name}`",
            f"- contact sheet: `{contact_sheet}`",
        ]
    )
    report_lines.extend(f"- 대표 비교 PNG: `{name}`" for name in comparison_pngs)
    report_lines.extend(f"- 비교 GIF: `{name}`" for name in comparison_gifs)
    report_lines.extend(
        [
            "",
            "## 결론 범위",
            "",
            "이 결과는 한 개의 Bistro flythrough 구간에 대한 Original 4-case 품질 기준선이다.",
            "얇은 선, 독립적으로 움직이는 물체와 명시적 disocclusion 장면의 수동 확인 전에는",
            "고스팅·shimmer 개선의 최종 결론으로 사용하지 않는다.",
            "",
        ]
    )
    report_name = "SMAA-Original-Four-Quality-Analysis-ko.md"
    (output / report_name).write_text(
        "\n".join(report_lines), encoding="utf-8"
    )
    print(f"Analysis complete: {output}", flush=True)


if __name__ == "__main__":
    main()
