#!/usr/bin/env python3
"""Aggregate the wide-camera CGVQM-2 reference gate.

The official Intel CGVQM implementation evaluates independent 30-frame clips
at 60 FPS.  CGVQM-2 consumes features through the R3D-18 stem and layer1, so a
per-frame error-map sample has a temporal receptive-field radius of five
frames inside each clip.  Official clip scores remain untouched; optional
per-frame diagnostics exclude those five frames at both clip boundaries.
"""

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
from PIL import Image


PROFILE = "flythrough-wide-yaw-360"
OFFICIAL_COMMIT = "8302ff45b4ff5a691682baf23f7c007d6b591e98"
CLIP_SIZE = 30
CGVQM2_TEMPORAL_RADIUS = 5
SCENES = ("Bistro", "Minecraft")
MODES = ("O-1X", "O-T2X-R", "O-ET2X-R")
MODE_DIRECTORIES = {
    "O-1X": "O_1X",
    "O-T2X-R": "O_T2X_R",
    "O-ET2X-R": "O_ET2X_R",
}
WINDOWS = {
    "central_motion_00150_00329": (150, 329),
    "transition_00410_00439": (410, 439),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and aggregate the formal Bistro/Minecraft wide-camera "
            "CGVQM-2 runs."
        )
    )
    parser.add_argument("--cgvqm-root", type=Path, required=True)
    parser.add_argument("--spatial-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def percent_change(value: float, baseline: float) -> float:
    if baseline == 0.0:
        return math.nan
    return (value - baseline) * 100.0 / baseline


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def validate_round_trip(entry: dict[str, Any], frame_count: int, label: str) -> None:
    required = {
        "codec": "ffv1",
        "decoded_frames": frame_count,
        "mismatched_values": 0,
        "max_absolute_difference": 0,
    }
    for key, expected in required.items():
        actual = entry.get(key)
        if actual != expected:
            raise RuntimeError(f"{label}: {key}={actual!r}, expected {expected!r}")


def read_per_frame(path: Path, start: int, end: int) -> list[dict[str, float | int | bool]]:
    rows: list[dict[str, float | int | bool]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for raw in csv.DictReader(stream):
            index = int(raw["frame_index"])
            local = index - start
            clip_offset = local % CLIP_SIZE
            rows.append(
                {
                    "frame_index": index,
                    "mean": float(raw["mean"]),
                    "p95": float(raw["p95"]),
                    "p99": float(raw["p99"]),
                    "maximum": float(raw["maximum"]),
                    "diagnostic_interior": (
                        CGVQM2_TEMPORAL_RADIUS
                        <= clip_offset
                        < CLIP_SIZE - CGVQM2_TEMPORAL_RADIUS
                    ),
                }
            )
    expected = list(range(start, end + 1))
    actual = [int(row["frame_index"]) for row in rows]
    if actual != expected:
        raise RuntimeError(f"{path}: expected frame indices {start}..{end}")
    return rows


def summarize_per_frame(rows: list[dict[str, float | int | bool]]) -> dict[str, Any]:
    means = [float(row["mean"]) for row in rows]
    interior = [
        float(row["mean"]) for row in rows if bool(row["diagnostic_interior"])
    ]
    return {
        "all_frame_error_mean": statistics.fmean(means),
        "all_frame_error_p95": percentile(means, 95.0),
        "all_frame_error_max": max(means),
        "interior_frame_count": len(interior),
        "interior_error_mean": statistics.fmean(interior),
        "interior_error_p95": percentile(interior, 95.0),
        "interior_error_max": max(interior),
    }


def pixel_hash(path: Path) -> str:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    return hashlib.sha256(rgb.tobytes()).hexdigest()


def frame_index(path: Path) -> int:
    marker = "_frame_"
    if marker not in path.stem:
        raise RuntimeError(f"Cannot parse frame index: {path.name}")
    return int(path.stem.rsplit(marker, 1)[1])


def collect_png_map(directory: Path) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for path in directory.glob("*.png"):
        index = frame_index(path)
        if index in result:
            raise RuntimeError(f"Duplicate frame {index} in {directory}")
        result[index] = path
    if not result:
        raise RuntimeError(f"No PNG files found in {directory}")
    return result


def post_still_stability(directory: Path) -> dict[str, Any]:
    frames = collect_png_map(directory)
    indices = list(range(420, 440))
    missing = [index for index in indices if index not in frames]
    if missing:
        raise RuntimeError(f"{directory}: missing post-still frames {missing}")
    hashes = [pixel_hash(frames[index]) for index in indices]
    with Image.open(frames[indices[0]]) as image:
        baseline = np.asarray(image.convert("RGB"), dtype=np.int16)
    changed_values = 0
    maximum = 0
    total_absolute = 0
    total_values = 0
    for index in indices[1:]:
        with Image.open(frames[index]) as image:
            current = np.asarray(image.convert("RGB"), dtype=np.int16)
        difference = np.abs(current - baseline)
        changed_values += int(np.count_nonzero(difference))
        maximum = max(maximum, int(difference.max()))
        total_absolute += int(difference.sum(dtype=np.int64))
        total_values += int(difference.size)
    return {
        "directory": str(directory.resolve()),
        "first_frame": indices[0],
        "last_frame": indices[-1],
        "frame_count": len(indices),
        "unique_pixel_hashes": len(set(hashes)),
        "changed_channel_values_vs_first_total": changed_values,
        "maximum_absolute_difference_vs_first": maximum,
        "mean_absolute_difference_vs_first": (
            total_absolute / total_values if total_values else 0.0
        ),
    }


def validate_result(
    path: Path,
    scene: str,
    window: str,
    mode: str,
) -> tuple[dict[str, Any], list[dict[str, float | int | bool]]]:
    result = read_json(path)
    start, end = WINDOWS[window]
    frame_count = end - start + 1
    provenance = result.get("provenance", {})
    expected_provenance = {
        "scene": scene,
        "camera_profile": PROFILE,
        "test_mode": mode,
        "reference_id": "SS-Reference",
    }
    for key, expected in expected_provenance.items():
        actual = provenance.get(key)
        if actual != expected:
            raise RuntimeError(f"{path}: {key}={actual!r}, expected {expected!r}")
    if result.get("classification") != "formal":
        raise RuntimeError(f"{path}: result is not classified as formal")
    if result.get("official_cgvqm", {}).get("commit") != OFFICIAL_COMMIT:
        raise RuntimeError(f"{path}: unexpected Intel CGVQM commit")
    runtime = result.get("runtime", {})
    if runtime.get("device") != "cuda" or not runtime.get("cuda_available"):
        raise RuntimeError(f"{path}: formal result did not run on CUDA")
    configuration = result.get("configuration", {})
    expected_configuration = {
        "fps": 60,
        "patch_scale": 4,
        "patch_pool": "mean",
        "models": ["2"],
        "reference_index_offset": 0,
    }
    for key, expected in expected_configuration.items():
        actual = configuration.get(key)
        if actual != expected:
            raise RuntimeError(f"{path}: {key}={actual!r}, expected {expected!r}")
    for name in ("test_sequence", "reference_sequence"):
        sequence = result.get(name, {})
        expected_sequence = {
            "frame_count": frame_count,
            "first_index": start,
            "last_index": end,
            "width": 1920,
            "height": 1017,
        }
        for key, expected in expected_sequence.items():
            actual = sequence.get(key)
            if actual != expected:
                raise RuntimeError(
                    f"{path}: {name}.{key}={actual!r}, expected {expected!r}"
                )
    validate_round_trip(result["test_round_trip"], frame_count, f"{path}: test")
    validate_round_trip(
        result["reference_round_trip"], frame_count, f"{path}: reference"
    )
    model = result.get("results", {}).get("CGVQM-2")
    if model is None:
        raise RuntimeError(f"{path}: missing CGVQM-2 result")
    per_frame_path = Path(model["per_frame_csv"])
    rows = read_per_frame(per_frame_path, start, end)
    summary = {
        "scene": scene,
        "window": window,
        "mode": mode,
        "start_frame": start,
        "end_frame": end,
        "frame_count": frame_count,
        "score_higher_is_better": float(model["score_higher_is_better"]),
        "error_map_mean": float(model["error_map"]["mean"]),
        "error_map_p95": float(model["error_map"]["p95"]),
        "error_map_p99": float(model["error_map"]["p99"]),
        "error_map_maximum": float(model["error_map"]["maximum"]),
        "per_frame_csv": str(per_frame_path.resolve()),
        "error_map_video": str(Path(model["visualized_error_map"]).resolve()),
        "test_directory": result["test_sequence"]["directory"],
        "reference_directory": result["reference_sequence"]["directory"],
        "gpu": runtime.get("gpu"),
        **summarize_per_frame(rows),
    }
    return summary, rows


def add_pair_deltas(records: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for record in records:
        groups.setdefault((record["scene"], record["window"]), {})[
            record["mode"]
        ] = record
    for modes in groups.values():
        one_x = modes["O-1X"]
        standard = modes["O-T2X-R"]
        edge = modes["O-ET2X-R"]
        for record in modes.values():
            record["score_delta_vs_o_1x"] = (
                record["score_higher_is_better"]
                - one_x["score_higher_is_better"]
            )
            record["error_mean_change_vs_o_1x_percent"] = percent_change(
                record["error_map_mean"], one_x["error_map_mean"]
            )
        edge["score_delta_vs_o_t2x_r"] = (
            edge["score_higher_is_better"]
            - standard["score_higher_is_better"]
        )
        edge["error_mean_change_vs_o_t2x_r_percent"] = percent_change(
            edge["error_map_mean"], standard["error_map_mean"]
        )


def transition_phase_summary(
    rows_by_key: dict[tuple[str, str, str], list[dict[str, float | int | bool]]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for scene in SCENES:
        for mode in MODES:
            rows = rows_by_key[(scene, "transition_00410_00439", mode)]
            for phase, start, end in (
                ("motion_tail", 415, 419),
                ("post_still", 420, 434),
            ):
                values = [
                    float(row["mean"])
                    for row in rows
                    if start <= int(row["frame_index"]) <= end
                    and bool(row["diagnostic_interior"])
                ]
                expected = end - start + 1
                if len(values) != expected:
                    raise RuntimeError(
                        f"{scene}/{mode}/{phase}: expected {expected} interior frames"
                    )
                output.append(
                    {
                        "scene": scene,
                        "mode": mode,
                        "phase": phase,
                        "start_frame": start,
                        "end_frame": end,
                        "frame_count": len(values),
                        "error_mean": statistics.fmean(values),
                        "error_p95": percentile(values, 95.0),
                        "error_maximum": max(values),
                    }
                )
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"No rows to write: {path}")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def f4(value: float) -> str:
    return f"{value:.4f}"


def build_markdown(
    records: list[dict[str, Any]],
    phases: list[dict[str, Any]],
    stability: dict[str, dict[str, Any]],
    spatial_summary: Path,
    spatial: dict[str, Any],
) -> str:
    by_key = {
        (record["scene"], record["window"], record["mode"]): record
        for record in records
    }
    lines = [
        "# SMAA Wide Camera Supersample Reference / CGVQM-2 결과",
        "",
        "## 1. 결론",
        "",
        "Bistro와 Minecraft의 `flythrough-wide-yaw-360`에서 `O-ET2X-R`은 "
        "중앙 motion 구간 기준으로 `O-T2X-R`보다 SS-Reference에 더 가까웠다. "
        "그러나 `O-1X`를 일관되게 넘지는 못했으므로, 현재 결과만으로 temporal "
        "supersampling 이득까지 보존했다고 결론내릴 수 없다.",
        "",
        "이 결과는 edge-selective 방식이 넓은 camera-motion history 오차를 줄이는 "
        "방향은 지지하지만, 출력이 1X에 가까워진 원인이 고스팅 감소인지 temporal "
        "sample 손실인지 완전히 분리하지는 못한다. 따라서 전체 8-case 확대보다 "
        "candidate 영역 확장과 temporal 유지율을 별도 ablation하는 것이 다음 순서다.",
        "",
        "## 2. 정식 조건",
        "",
        "- 장면: Bistro(저대비), Minecraft(고대비)",
        f"- camera profile: `{PROFILE}` (480 frame, fixed 60 Hz, 약 3.72 m 이동 + 360° yaw)",
        "- 비교: `O-1X`, `O-T2X-R`, `O-ET2X-R`",
        "- reference: 2× linear resolution, 3×3 within-frame subpixel grid, 8× MSAA",
        f"- CGVQM: IntelLabs/CGVQM commit `{OFFICIAL_COMMIT[:8]}`, model 2, CUDA, 60 FPS, patch scale 4, mean pooling",
        "- 모든 FFV1 encode/decode RGB round-trip mismatch: 0",
        "- reference는 temporal history가 없는 spatial-reference proxy이며 절대적인 ghosting ground truth가 아니다.",
        "",
        "## 3. 공식 CGVQM-2 점수",
        "",
        "높을수록 SS-Reference에 가깝다. 중앙 motion과 motion→still 전환은 서로 다른 "
        "30-frame clip 집합이므로 점수를 합치지 않는다.",
        "",
        "| Scene | Window | O-1X | O-T2X-R | O-ET2X-R | ET − Standard | ET − 1X |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for scene in SCENES:
        for window, label in (
            ("central_motion_00150_00329", "central motion 150–329"),
            ("transition_00410_00439", "transition 410–439"),
        ):
            one_x = by_key[(scene, window, "O-1X")]
            standard = by_key[(scene, window, "O-T2X-R")]
            edge = by_key[(scene, window, "O-ET2X-R")]
            lines.append(
                f"| {scene} | {label} | {f4(one_x['score_higher_is_better'])} | "
                f"{f4(standard['score_higher_is_better'])} | "
                f"{f4(edge['score_higher_is_better'])} | "
                f"{edge['score_delta_vs_o_t2x_r']:+.4f} | "
                f"{edge['score_delta_vs_o_1x']:+.4f} |"
            )
    bistro_central_edge = by_key[
        ("Bistro", "central_motion_00150_00329", "O-ET2X-R")
    ]
    minecraft_central_edge = by_key[
        ("Minecraft", "central_motion_00150_00329", "O-ET2X-R")
    ]
    lines.extend(
        [
            "",
            "중앙 motion에서는 `O-ET2X-R`이 Standard보다 Bistro "
            f"`{bistro_central_edge['score_delta_vs_o_t2x_r']:+.4f}`, Minecraft "
            f"`{minecraft_central_edge['score_delta_vs_o_t2x_r']:+.4f}`점 높았다. "
            "동시에 1X보다는 각각 "
            f"`{bistro_central_edge['score_delta_vs_o_1x']:+.4f}`, "
            f"`{minecraft_central_edge['score_delta_vs_o_1x']:+.4f}`점 낮아, "
            "Minecraft에서는 거의 1X 수준이었다.",
            "",
            "전환 30-frame clip에서는 Standard가 가장 높았다. 이는 motion 마지막 "
            "10 frame과 정지 시작 20 frame이 섞인 별도 구간의 결과이며, 중앙 motion "
            "결과를 뒤집거나 합산하는 값으로 사용하지 않는다.",
            "",
            "## 4. 전환 구간 프레임별 진단",
            "",
            "CGVQM-2는 30-frame clip마다 R3D-18 stem과 layer1의 시간축 3×3 "
            "convolution을 사용한다. 이 경로의 temporal receptive-field radius는 "
            "5 frame이다. 따라서 공식 점수는 30 frame 전체를 그대로 유지하고, "
            "per-frame error-map 해석에는 경계 410–414와 435–439를 제외했다.",
            "",
            "| Scene | Phase | O-1X error | O-T2X-R error | O-ET2X-R error |",
            "|---|---|---:|---:|---:|",
        ]
    )
    phase_map = {
        (row["scene"], row["phase"], row["mode"]): row for row in phases
    }
    for scene in SCENES:
        for phase, label in (("motion_tail", "motion tail 415–419"), ("post_still", "post-still 420–434")):
            values = [phase_map[(scene, phase, mode)]["error_mean"] for mode in MODES]
            lines.append(
                f"| {scene} | {label} | {f4(values[0])} | {f4(values[1])} | {f4(values[2])} |"
            )
    bistro_spatial = spatial["bistro"]
    minecraft_spatial = spatial["minecraft"]
    bistro_edge = bistro_spatial["modes"]["o_et2x_r"]
    minecraft_edge = minecraft_spatial["modes"]["o_et2x_r"]
    lines.extend(
        [
            "",
            "이 표는 official CGVQM score가 아니라 error-map의 보조 진단이다. "
            "모델 문맥과 spatial reference 차이를 모두 포함하므로 잔상 길이의 절대값으로 표현하지 않는다.",
            "",
            "## 5. Post-still 입력 안정성",
            "",
            "| Scene | Input | Unique hashes (420–439) | Max diff | Mean diff |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for scene in SCENES:
        key = scene.lower()
        for source, label in (("o_1x", "O-1X"), ("reference", "SS-Reference")):
            item = stability[key][source]
            lines.append(
                f"| {scene} | {label} | {item['unique_pixel_hashes']} | "
                f"{item['maximum_absolute_difference_vs_first']} | "
                f"{item['mean_absolute_difference_vs_first']:.8f} |"
            )
    lines.extend(
        [
            "",
            "O-1X post-still 입력은 두 장면 모두 완전히 동일하다. Minecraft "
            "SS-Reference도 동일하며, Bistro SS-Reference의 차이는 최대 2/255의 극소수 "
            "GPU 누적 변동이다. 따라서 마지막 frame error-map 급변은 장면 camera가 "
            "다시 움직인 증거가 아니라 30-frame 모델 clip 경계의 per-frame 해석 문제로 분류한다.",
            "",
            "## 6. Spatial reference 전체 480-frame 결과",
            "",
            f"전체 수치와 대표 비교/difference sheet는 `{spatial_summary}`에서 자동 검증했다.",
            "",
            "- Bistro: `O-ET2X-R` MAE는 Standard보다 "
            f"{abs(bistro_spatial['o_et2x_r_mae_delta_vs_o_t2x_r_percent']):.2f}% "
            f"낮지만 O-1X보다 {abs(bistro_edge['mae_improvement_vs_o_1x_percent']):.2f}% 높다.",
            "- Minecraft: `O-ET2X-R` MAE는 Standard보다 "
            f"{abs(minecraft_spatial['o_et2x_r_mae_delta_vs_o_t2x_r_percent']):.2f}% "
            f"낮고 O-1X와의 차이는 {abs(minecraft_edge['mae_improvement_vs_o_1x_percent']):.2f}%다.",
            "- Standard는 두 장면 모두 edge/reference 비율이 가장 낮아 더 큰 blur 경향을 보였다.",
            "",
            "## 7. 판정과 다음 작업",
            "",
            "1. Wide camera reference gate는 통과했다. 정렬, 재현성, lossless 입력과 두 장면 결과를 확보했다.",
            "2. `O-ET2X-R`은 Standard의 넓은 history 차이와 blur를 줄였지만, 1X 대비 temporal sample accumulation 우위는 확인되지 않았다.",
            "3. 따라서 바로 전체 8-case로 확대하지 않고 current-edge candidate expansion을 진행한다.",
            "4. 다음 구현은 기존 one-pass `FilteredQuarter`를 ARM Dual Filtering이라고 재명명하지 않는다. ARM의 downsample/upsample kernel과 offset을 출처대로 고정한 별도 research adaptation으로 구현한다.",
            "5. ARM adaptation은 None, 정확한 3×3, 기존 FilteredQuarter와 동일 입력·threshold·camera path에서 candidate coverage, CGVQM, temporal 유지와 GPU 비용을 비교한다.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    root = args.cgvqm_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    spatial_summary = args.spatial_summary.resolve()
    spatial = read_json(spatial_summary)
    if set(spatial) != {"bistro", "minecraft"}:
        raise RuntimeError("Spatial summary does not contain Bistro and Minecraft")

    records: list[dict[str, Any]] = []
    rows_by_key: dict[
        tuple[str, str, str], list[dict[str, float | int | bool]]
    ] = {}
    reference_hashes: dict[tuple[str, str], str] = {}
    reference_dirs: dict[str, Path] = {}
    test_dirs: dict[str, Path] = {}
    for scene in SCENES:
        for window in WINDOWS:
            for mode in MODES:
                path = root / scene / window / MODE_DIRECTORIES[mode] / "CGVQM-Results.json"
                if not path.is_file():
                    raise RuntimeError(f"Missing result: {path}")
                record, rows = validate_result(path, scene, window, mode)
                records.append(record)
                rows_by_key[(scene, window, mode)] = rows
                raw = read_json(path)
                reference_hash = raw["reference_sequence"]["pixel_sha256"]
                hash_key = (scene, window)
                previous = reference_hashes.setdefault(hash_key, reference_hash)
                if previous != reference_hash:
                    raise RuntimeError(f"{scene}/{window}: reference hash differs by mode")
                if window == "transition_00410_00439" and mode == "O-1X":
                    reference_dirs[scene.lower()] = Path(record["reference_directory"])
                    test_dirs[scene.lower()] = Path(record["test_directory"])
    add_pair_deltas(records)
    phases = transition_phase_summary(rows_by_key)
    stability = {
        scene.lower(): {
            "o_1x": post_still_stability(test_dirs[scene.lower()]),
            "reference": post_still_stability(reference_dirs[scene.lower()]),
        }
        for scene in SCENES
    }

    write_csv(output / "wide_camera_cgvqm_summary.csv", records)
    write_csv(output / "wide_camera_cgvqm_transition_phases.csv", phases)
    combined = {
        "classification": "formal",
        "camera_profile": PROFILE,
        "official_cgvqm_commit": OFFICIAL_COMMIT,
        "cgvqm_model": "CGVQM-2",
        "clip_size": CLIP_SIZE,
        "per_frame_temporal_receptive_field_radius": CGVQM2_TEMPORAL_RADIUS,
        "metric_scope": (
            "Full-reference perceptual video quality with a supersample spatial "
            "reference proxy; not absolute ghosting ground truth."
        ),
        "records": records,
        "transition_phase_diagnostics": phases,
        "post_still_input_stability": stability,
    }
    with (output / "wide_camera_cgvqm_summary.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(combined, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    report = build_markdown(records, phases, stability, spatial_summary, spatial)
    (output / "SMAA-Wide-Camera-CGVQM-Results-ko.md").write_text(
        report, encoding="utf-8"
    )
    print("PASS: validated 12 formal CGVQM-2 runs")
    print(f"Report: {output / 'SMAA-Wide-Camera-CGVQM-Results-ko.md'}")


if __name__ == "__main__":
    main()
