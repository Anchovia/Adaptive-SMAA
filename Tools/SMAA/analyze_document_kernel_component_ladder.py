#!/usr/bin/env python3
"""Analyze the FullScreenDocument Pattern On/Off 2x4 component ladder."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from analyze_wide_camera_reference_quality import (
    collect_frames,
    difference_image,
    edge_strength,
    finite_mean,
    load_rgb,
    luma_ssim,
    resized,
    rgb_mae,
    rgb_psnr,
)


PROFILE = "flythrough-wide-yaw-360"
MODES = (
    ("standard_on", "Standard On", "O_T2X_R", "control", "on"),
    ("standard_off", "Standard Off", "ABL_Standard_PatternOff_R", "control", "off"),
    ("k0_on", "K0 Bilinear W0.5 On", "ABL_FS_K0_Bilinear_W05_PatternOn_R", "k0", "on"),
    ("k0_off", "K0 Bilinear W0.5 Off", "ABL_FS_K0_Bilinear_W05_PatternOff_R", "k0", "off"),
    ("k1_on", "K1 Catmull W0.5 On", "ABL_FS_K1_Catmull_W05_PatternOn_R", "k1", "on"),
    ("k1_off", "K1 Catmull W0.5 Off", "ABL_FS_K1_Catmull_W05_PatternOff_R", "k1", "off"),
    ("k2_on", "K2 Catmull Clip W0.5 On", "ABL_FS_K2_Catmull_Clip_W05_PatternOn_R", "k2", "on"),
    ("k2_off", "K2 Catmull Clip W0.5 Off", "ABL_FS_K2_Catmull_Clip_W05_PatternOff_R", "k2", "off"),
    ("k3_on", "K3 Document W0.8 On", "ABL_Document_FullScreen_PatternOn_R", "k3", "on"),
    ("k3_off", "K3 Document W0.8 Off", "ABL_Document_FullScreen_R", "k3", "off"),
)
WINDOWS = (
    ("full", "전체", 0, 480),
    ("central_motion", "중앙 이동", 150, 330),
    ("transition", "이동→정지", 410, 440),
    ("post_still", "후기 정지", 420, 480),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", nargs=4, action="append", required=True,
        metavar=("SCENE", "CAPTURE", "REFERENCE", "PRIOR_CAPTURE"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-frames", type=int, default=480)
    parser.add_argument("--ssim-stride", type=int, default=4)
    return parser.parse_args()


def report_text(root: Path) -> str:
    reports = list(root.glob("*_results.csv"))
    if len(reports) != 1:
        raise RuntimeError(f"{root}: expected one results CSV, found {len(reports)}")
    return reports[0].read_text(encoding="utf-8", errors="replace")


def validate_reports(capture: Path, reference: Path, scene: str, frames: int) -> None:
    capture_required = (
        "full-screen document-kernel component ladder capture",
        f"Scene:           {scene.lower()}",
        f"Camera profile:  {PROFILE}",
        f"Profile frames:  480 total; capture [0, {frames - 1}]",
        "two external Standard controls plus a FullScreenDocument paired Pattern On/Off 2x4 component ladder",
        "projection jitter and matching SMAA T2X subsample indices are enabled or disabled only as a coupled pair",
        "Classification:  complete camera profile quality capture",
    )
    reference_required = (
        "supersample spatial-reference capture",
        f"Scene:           {scene.lower()}",
        f"Camera profile:  {PROFILE}",
        "2x linear resolution, 3x3 within-frame subpixel grid, 8x MSAA",
    )
    missing = [value for value in capture_required if value not in report_text(capture)]
    missing += [value for value in reference_required if value not in report_text(reference)]
    if missing:
        raise RuntimeError(f"{scene}: report validation failed: {missing}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_bridge(scene: str, capture: Path, prior: Path, expected: int) -> list[dict[str, Any]]:
    directories = (
        "O_T2X_R", "ABL_Standard_PatternOff_R",
        "ABL_Document_FullScreen_PatternOn_R", "ABL_Document_FullScreen_R",
    )
    rows: list[dict[str, Any]] = []
    for directory in directories:
        new_files = sorted((capture / directory).glob("*.png"))
        old_files = sorted((prior / directory).glob("*.png"))
        if len(new_files) != expected or len(old_files) != expected:
            raise RuntimeError(f"{scene}/{directory}: bridge count mismatch")
        if [p.name for p in new_files] != [p.name for p in old_files]:
            raise RuntimeError(f"{scene}/{directory}: bridge filenames differ")
        mismatch = sum(sha256(a) != sha256(b) for a, b in zip(new_files, old_files))
        if mismatch:
            raise RuntimeError(f"{scene}/{directory}: {mismatch} hash mismatches")
        rows.append({
            "scene": scene, "mode_directory": directory,
            "frame_count": expected, "byte_hash_mismatches": mismatch,
            "prior_capture_root": str(prior),
        })
    return rows


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return finite_mean([float(row[key]) for row in rows])


def make_sheet(output: Path, paths: dict[str, list[Path]], frames: list[int], diff: bool) -> None:
    columns = (("SS-Ref", "reference"),) + tuple((label, key) for key, label, *_ in MODES)
    width, label_height = 160, 23
    tile_height = resized(paths["reference"][0], width).height
    canvas = Image.new("RGB", (width * len(columns), label_height + len(frames) * (tile_height + label_height)), "white")
    draw = ImageDraw.Draw(canvas)
    for column, (label, key) in enumerate(columns):
        suffix = " |x4|" if diff and key != "reference" else ""
        draw.text((column * width + 3, 5), label + suffix, fill="black")
    y = label_height
    for frame in frames:
        for column, (_, key) in enumerate(columns):
            image = difference_image(paths[key][frame], paths["reference"][frame], width) if diff and key != "reference" else resized(paths[key][frame], width)
            canvas.paste(image, (column * width, y))
        draw.text((3, y + tile_height + 4), f"frame {frame:05d}", fill="black")
        y += tile_height + label_height
    canvas.save(output, optimize=True)


def analyze_case(scene: str, capture: Path, reference: Path, expected: int, stride: int, output: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_reports(capture, reference, scene, expected)
    paths: dict[str, list[Path]] = {}
    resolutions: set[tuple[int, int]] = set()
    for key, _, directory, _, _ in MODES:
        paths[key], resolution = collect_frames(capture / directory, expected, 0)
        resolutions.add(resolution)
    paths["reference"], resolution = collect_frames(reference / "SS_Reference", expected, 0)
    resolutions.add(resolution)
    if len(resolutions) != 1:
        raise RuntimeError(f"{scene}: resolution mismatch {resolutions}")

    rows: list[dict[str, Any]] = []
    history: dict[str, list[np.ndarray]] = {key: [] for key, *_ in MODES}
    reference_history: list[np.ndarray] = []
    for frame in range(expected):
        if frame % 60 == 0:
            print(f"[{scene}] metrics {frame}/{expected}", flush=True)
        ref = load_rgb(paths["reference"][frame])
        ref_edge = edge_strength(ref)
        for key, label, _, stage, pattern in MODES:
            image = load_rgb(paths[key][frame])
            delta1 = float("nan")
            delta2 = float("nan")
            if len(history[key]) >= 1:
                delta1 = float(np.abs((image.astype(np.int16) - history[key][-1].astype(np.int16)) - (ref.astype(np.int16) - reference_history[-1].astype(np.int16))).mean(dtype=np.float64))
            if len(history[key]) >= 2:
                delta2 = float(np.abs((image.astype(np.int16) - history[key][-2].astype(np.int16)) - (ref.astype(np.int16) - reference_history[-2].astype(np.int16))).mean(dtype=np.float64))
            rows.append({
                "scene": scene, "frame": frame, "mode_key": key, "mode": label,
                "stage": stage, "pattern": pattern,
                "rgb_mae_to_reference": rgb_mae(image, ref),
                "rgb_psnr_to_reference_db": rgb_psnr(image, ref),
                "luma_ssim_to_reference": luma_ssim(image, ref) if frame % stride == 0 else float("nan"),
                "edge_strength_ratio_to_reference": edge_strength(image) / ref_edge if ref_edge > 1.0e-12 else float("nan"),
                "temporal_delta1_residual_to_reference": delta1,
                "temporal_delta2_residual_to_reference": delta2,
            })
            history[key].append(image)
            if len(history[key]) > 2:
                history[key].pop(0)
        reference_history.append(ref)
        if len(reference_history) > 2:
            reference_history.pop(0)

    summary: dict[str, Any] = {
        "scene": scene, "profile": PROFILE,
        "classification": "formal" if expected == 480 else "engineering",
        "resolution": list(next(iter(resolutions))), "capture_root": str(capture),
        "reference_root": str(reference), "windows": {},
    }
    for window_key, label, start, end in WINDOWS:
        modes: dict[str, Any] = {}
        for key, mode_label, directory, stage, pattern in MODES:
            selected = [r for r in rows if r["mode_key"] == key and start <= int(r["frame"]) < end]
            modes[key] = {
                "mode": mode_label, "directory": directory, "stage": stage, "pattern": pattern,
                "frame_count": len(selected),
                "mean_rgb_mae_to_reference": mean(selected, "rgb_mae_to_reference"),
                "mean_rgb_psnr_to_reference_db": mean(selected, "rgb_psnr_to_reference_db"),
                "mean_luma_ssim_to_reference": mean(selected, "luma_ssim_to_reference"),
                "mean_edge_strength_ratio_to_reference": mean(selected, "edge_strength_ratio_to_reference"),
                "mean_temporal_delta1_residual_to_reference": mean(selected, "temporal_delta1_residual_to_reference"),
                "mean_temporal_delta2_residual_to_reference": mean(selected, "temporal_delta2_residual_to_reference"),
            }
        pattern_deltas = {stage: modes[f"{stage}_off"]["mean_rgb_mae_to_reference"] - modes[f"{stage}_on"]["mean_rgb_mae_to_reference"] for stage in ("k0", "k1", "k2", "k3")}
        component_deltas = {
            pattern: {
                "catmull_k1_minus_k0": modes[f"k1_{pattern}"]["mean_rgb_mae_to_reference"] - modes[f"k0_{pattern}"]["mean_rgb_mae_to_reference"],
                "clipping_k2_minus_k1": modes[f"k2_{pattern}"]["mean_rgb_mae_to_reference"] - modes[f"k1_{pattern}"]["mean_rgb_mae_to_reference"],
                "weight08_k3_minus_k2": modes[f"k3_{pattern}"]["mean_rgb_mae_to_reference"] - modes[f"k2_{pattern}"]["mean_rgb_mae_to_reference"],
            } for pattern in ("on", "off")
        }
        summary["windows"][window_key] = {
            "label": label, "range_half_open": [start, end], "modes": modes,
            "pattern_off_minus_on_mae": pattern_deltas,
            "component_mae_deltas": component_deltas,
            "contextual_k0_minus_standard_mae": {
                "on": modes["k0_on"]["mean_rgb_mae_to_reference"] - modes["standard_on"]["mean_rgb_mae_to_reference"],
                "off": modes["k0_off"]["mean_rgb_mae_to_reference"] - modes["standard_off"]["mean_rgb_mae_to_reference"],
            },
        }

    scene_output = output / scene
    scene_output.mkdir(parents=True, exist_ok=True)
    visual_frames = [150, 240, 329, 410, 419, 420, 421, 422, 439, 479]
    make_sheet(scene_output / "kernel_ladder_reference_comparison.png", paths, visual_frames, False)
    make_sheet(scene_output / "kernel_ladder_reference_difference_x4.png", paths, visual_frames, True)
    return rows, summary


def write_report(path: Path, summaries: dict[str, Any], bridges: list[dict[str, Any]]) -> None:
    lines = [
        "# FullScreenDocument Sample-Pattern 2×4 Component Ladder 결과", "",
        "## 실험 정의", "",
        "8개 ladder cell은 모두 같은 FullScreenDocument compute resolve와 camera/depth reprojection을 사용한다.",
        "K0=bilinear/clip Off/W0.5, K1=Catmull/clip Off/W0.5, K2=Catmull/YCoCg clip/W0.5, K3=Catmull/YCoCg clip/W0.8이다.",
        "각 단계의 Pattern On/Off는 projection jitter와 대응 SMAA T2X subsample index를 한 쌍으로 전환한다.",
        "Standard On/Off는 공식 SMAA resolve의 point history sampling, velocity-alpha 기반 가변 history weight(0~0.5), 직전 spatial-frame history를 사용한다.",
        "반면 K0는 bilinear sampling, 고정 history weight 0.5, resolve-output feedback history를 사용하므로 Standard-K0 차이는 실행 경로만의 차이가 아니며 참고 control로만 해석한다.", "",
        "## 입력 무결성", "", f"- 기존 control hash bridge: {len(bridges)} sequences, mismatch 0", "",
        "## Window별 핵심 MAE", "",
        "| Scene | Window | K0 Off-On | K1 Off-On | K2 Off-On | K3 Off-On | On: K1-K0 | On: K2-K1 | On: K3-K2 | Off: K1-K0 | Off: K2-K1 | Off: K3-K2 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scene, summary in summaries.items():
        for window_key in ("central_motion", "transition", "post_still"):
            window = summary["windows"][window_key]
            p = window["pattern_off_minus_on_mae"]
            on = window["component_mae_deltas"]["on"]
            off = window["component_mae_deltas"]["off"]
            lines.append(
                f"| {scene} | {window['label']} | {p['k0']:+.6f} | {p['k1']:+.6f} | {p['k2']:+.6f} | {p['k3']:+.6f} | "
                f"{on['catmull_k1_minus_k0']:+.6f} | {on['clipping_k2_minus_k1']:+.6f} | {on['weight08_k3_minus_k2']:+.6f} | "
                f"{off['catmull_k1_minus_k0']:+.6f} | {off['clipping_k2_minus_k1']:+.6f} | {off['weight08_k3_minus_k2']:+.6f} |"
            )
    lines += ["", "## 후기 정지 2-phase 진단", "", "| Scene | Mode | Δ1 residual↓ | Δ2 residual↓ | Δ2/Δ1 |", "|---|---|---:|---:|---:|"]
    for scene, summary in summaries.items():
        modes = summary["windows"]["post_still"]["modes"]
        for key in ("k0_on", "k1_on", "k2_on", "k3_on", "k0_off", "k1_off", "k2_off", "k3_off"):
            mode = modes[key]
            d1 = mode["mean_temporal_delta1_residual_to_reference"]
            d2 = mode["mean_temporal_delta2_residual_to_reference"]
            lines.append(f"| {scene} | {mode['mode']} | {d1:.6f} | {d2:.6f} | {d2 / d1 if d1 else float('nan'):.6f} |")
    lines += ["", "## 해석 제한", "", "- supersample 입력은 동일 pose spatial-reference proxy이며 절대 temporal ground truth가 아니다.", "- 최종 component 판정은 공식 CGVQM-2 central-motion/transition 결과와 함께 내린다.", "- K0~K3 내부 비교는 같은 FullScreenDocument 경로의 직교 ladder이므로 유효하다.", "- Standard-K0 비교는 point/bilinear sampler, velocity-adaptive/fixed history weight, 직전 spatial/resolve-output feedback history가 함께 다르므로 경로 차이만으로 해석하지 않는다.", "- 이 ladder는 full-screen 원인 분리 진단이며 edge-selective 최종 8-case를 변경하지 않는다."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    bridges: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_scene, raw_capture, raw_reference, raw_prior in args.case:
        key = raw_scene.lower()
        if key not in {"bistro", "minecraft"} or key in seen:
            raise RuntimeError(f"invalid or duplicate scene: {raw_scene}")
        seen.add(key)
        scene = "Bistro" if key == "bistro" else "Minecraft"
        capture, reference, prior = map(lambda p: Path(p).resolve(), (raw_capture, raw_reference, raw_prior))
        bridges.extend(hash_bridge(scene, capture, prior, args.expected_frames))
        rows, summary = analyze_case(scene, capture, reference, args.expected_frames, args.ssim_stride, output)
        all_rows.extend(rows)
        summaries[scene] = summary
    if seen != {"bistro", "minecraft"}:
        raise RuntimeError("formal analysis requires Bistro and Minecraft")
    with (output / "document_kernel_ladder_per_frame.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0].keys()))
        writer.writeheader(); writer.writerows(all_rows)
    (output / "document_kernel_ladder_summary.json").write_text(json.dumps({"classification": "formal", "hash_bridges": bridges, "scenes": summaries}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(output / "SMAA-Document-Kernel-Component-Ladder-Results-ko.md", summaries, bridges)
    print(f"PASS: {len(all_rows)} frame-mode rows, {len(bridges)} hash bridges, output={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
