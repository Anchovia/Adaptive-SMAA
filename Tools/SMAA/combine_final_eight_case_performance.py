#!/usr/bin/env python3
"""Combine validated per-scene final 8-case performance analyses."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


MODE_ORDER = (
    "O-T2X", "O-T2X-R", "O-ET2X", "O-ET2X-R",
    "A-T2X", "A-T2X-R", "A-ET2X", "A-ET2X-R",
)
METRICS = ("ApplicationFrameWall", "WholeFrame", "SMAA")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", nargs=2, action="append", required=True,
        metavar=("SCENE", "ANALYSIS_JSON"),
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_case(scene: str, path: Path) -> dict[str, Any]:
    data = json.loads(path.resolve().read_text(encoding="utf-8"))
    errors: list[str] = []
    if data.get("scene") != scene:
        errors.append(f"scene={data.get('scene')!r}")
    if data.get("classification") != "formal" or not data.get("formal_measurement"):
        errors.append("not a formal measurement")
    if data.get("window_state") != "visible":
        errors.append("window state is not visible")
    validation = data.get("validation", {})
    if not validation.get("pass") or validation.get("mode_count") != 8:
        errors.append("per-scene validation failed")
    metadata = data.get("metadata", {})
    if metadata.get("warmup_frames") != 300:
        errors.append("warmup_frames != 300")
    if metadata.get("measurement_frames") != 4800 or metadata.get("repeats") != 3:
        errors.append("measurement protocol != 4800x3")
    if not metadata.get("candidate_readback_disabled"):
        errors.append("candidate readback was not disabled")
    missing_modes = [mode for mode in MODE_ORDER if mode not in data.get("modes", {})]
    if missing_modes:
        errors.append(f"missing modes {missing_modes}")
    for mode in MODE_ORDER:
        for metric in METRICS:
            values = data.get("modes", {}).get(mode, {}).get(metric, {})
            if values.get("samples") != 14400 or values.get("runs") != 3:
                errors.append(f"{mode}/{metric} samples or runs invalid")
    if errors:
        raise RuntimeError(f"{path}: {'; '.join(errors)}")
    data["combined_source_json"] = str(path.resolve())
    return data


def write_markdown(path: Path, cases: dict[str, dict[str, Any]]) -> None:
    lines = [
        "# Final integrated 8-case 성능 통합 분석",
        "",
        "RTX 3060 Ti, DirectX 11, SMAA Ultra, 1920×1017, VSync Off, visible window에서",
        "각 mode를 300 frames warm-up 후 4,800 frames × 3회 측정했다. Candidate",
        "GPU→CPU readback은 비활성화했다.",
        "",
        "## Mode별 결과",
        "",
        "| Scene | Mode | Wall ms | Wall FPS | WholeFrame GPU ms | SMAA GPU ms | SMAA run-mean σ |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for scene, data in cases.items():
        for mode in MODE_ORDER:
            values = data["modes"][mode]
            wall = values["ApplicationFrameWall"]
            whole = values["WholeFrame"]
            smaa = values["SMAA"]
            lines.append(
                f"| {scene} | {mode} | {wall['mean_ms']:.6f} | "
                f"{1000.0 / wall['mean_ms']:.3f} | {whole['mean_ms']:.6f} | "
                f"{smaa['mean_ms']:.6f} | {smaa['run_mean_stddev_ms']:.6f} |"
            )
    lines.extend([
        "",
        "## 독립 축 효과",
        "",
        "음수는 variant가 더 빠르고, 양수는 variant가 더 느리다는 뜻이다.",
        "",
        "| Scene | Axis | Comparison | Metric | Δ ms | Δ % |",
        "|---|---|---|---|---:|---:|",
    ])
    for scene, data in cases.items():
        for row in data["comparisons"]:
            if row["metric"] not in ("WholeFrame", "SMAA"):
                continue
            lines.append(
                f"| {scene} | {row['axis']} | {row['baseline']} → {row['variant']} | "
                f"{row['metric']} | {row['delta_ms']:+.6f} | {row['delta_percent']:+.3f}% |"
            )
    lines.extend([
        "",
        "## 핵심 관찰",
        "",
        "- Adaptive 공간 탐색은 두 장면의 모든 대응 mode에서 SMAA GPU 시간을 줄였다.",
        "- 현재 integrated edge-selective 구현은 별도 full-screen edge 재판정을 제거했지만, 대응 Standard T2X보다 여전히 느렸다.",
        "- 따라서 현재 결과로는 candidate 감소를 성능 향상이라고 주장할 수 없으며, remaining compact/indirect/resolve overhead 최적화가 필요하다.",
        "- WholeFrame 차이는 SMAA pass 차이보다 장면·프레임 변동의 영향을 더 받으므로 반복 run-mean 분산과 함께 해석한다.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    cases: dict[str, dict[str, Any]] = {}
    for raw_scene, raw_path in args.case:
        scene = raw_scene.lower()
        if scene not in ("bistro", "minecraft"):
            raise ValueError(f"Unsupported scene: {scene}")
        if scene in cases:
            raise ValueError(f"Duplicate scene: {scene}")
        cases[scene] = load_case(scene, Path(raw_path))
    if set(cases) != {"bistro", "minecraft"}:
        raise RuntimeError("Formal combined report requires Bistro and Minecraft")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    mode_rows: list[dict[str, Any]] = []
    effect_rows: list[dict[str, Any]] = []
    for scene, data in cases.items():
        for mode in MODE_ORDER:
            row: dict[str, Any] = {"scene": scene, "mode": mode}
            for metric in METRICS:
                values = data["modes"][mode][metric]
                prefix = metric.lower()
                row[f"{prefix}_mean_ms"] = values["mean_ms"]
                row[f"{prefix}_median_ms"] = values["median_ms"]
                row[f"{prefix}_p95_ms"] = values["p95_ms"]
                row[f"{prefix}_p99_ms"] = values["p99_ms"]
                row[f"{prefix}_run_mean_stddev_ms"] = values["run_mean_stddev_ms"]
            row["wall_mean_fps"] = 1000.0 / row["applicationframewall_mean_ms"]
            mode_rows.append(row)
        for effect in data["comparisons"]:
            effect_rows.append({"scene": scene, **effect})

    modes_csv = output / "final_eight_performance_modes.csv"
    with modes_csv.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(mode_rows[0]))
        writer.writeheader()
        writer.writerows(mode_rows)
    effects_csv = output / "final_eight_performance_axis_effects.csv"
    with effects_csv.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(effect_rows[0]))
        writer.writeheader()
        writer.writerows(effect_rows)
    combined_json = output / "final_eight_performance_combined.json"
    combined_json.write_text(
        json.dumps({"validation": "PASS", "scenes": cases}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    report = output / "SMAA-Final-Eight-Case-Performance-Combined-ko.md"
    write_markdown(report, cases)
    print(f"MODES_CSV={modes_csv}")
    print(f"EFFECTS_CSV={effects_csv}")
    print(f"JSON={combined_json}")
    print(f"REPORT={report}")
    print("VALIDATION=PASS scenes=2 modes=8 samples_per_mode_metric=14400")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
