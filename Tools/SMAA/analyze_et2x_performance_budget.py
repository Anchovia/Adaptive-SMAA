"""Reconcile measured ET2X costs and derive conditional break-even budgets.

No GPU execution and no claim that subtracting a timer predicts a new runtime.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from analyze_eight_case_performance import clean_row, extract_metadata
from analyze_matched_kernel_optimization import parse_results, validate

ROOT = Path(__file__).resolve().parents[2]
STANDARD = "O-T2X-R"
SELECTIVE = "O-ET2X-R-DocCandidate-DocKernel"
PARTS = {
    STANDARD: ("SMAAGenerateCameraVelocity", "SMAAStandardSpatialT2X",
               "SMAAStandardTemporalResolve"),
    SELECTIVE: ("SMAAGenerateCameraVelocity", "SMAASpatial1X",
                "TSCMAACopySpatialToHistory", "TSCMAAClearIntegratedCandidateBuffers",
                "TSCMAAComputeDispatchArgs", "TSCMAAResolveCandidates", "TSCMAAOutputCopy"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def read_baseline(path: Path, scene: str, recorded: dict) -> dict:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    meta = extract_metadata(lines)
    require(f"Scene: {scene}." in lines, f"{path}: scene mismatch")
    require(meta.get("benchmark_validation_pass") is True, f"{path}: no PASS")
    require(meta.get("candidate_readback_disabled") is True, f"{path}: readback enabled")
    require((meta.get("warmup_frames"), meta.get("measurement_frames"), meta.get("repeats"))
            == (300, 4800, 3), f"{path}: repetition contract mismatch")
    rows = [clean_row(row) for row in csv.reader(lines)]
    start = next(i for i, row in enumerate(rows) if row[:3] == ["Mode", "Timing metric", "Type"])
    end = next(i for i, row in enumerate(rows) if row and row[0] == "Frame-rate characterization:")
    timings = {mode: {} for mode in PARTS}
    for row in rows[start + 1:end]:
        if len(row) < 12 or row[0] not in timings:
            continue
        mode, metric = row[:2]
        require(metric not in timings[mode], f"{path}: duplicate timer {mode}/{metric}")
        require(int(row[3]) == 14400 and int(row[10]) == 3, f"{path}: incomplete timer")
        value = float(row[4])
        require(math.isfinite(value) and value > 0, f"{path}: invalid time")
        require(abs(value - recorded[mode][metric]["mean_ms"]) < 1e-9,
                f"{path}: CSV/recorded JSON mismatch {mode}/{metric}")
        timings[mode][metric] = value
    for mode, parts in PARTS.items():
        require(set(parts + ("SMAA",)).issubset(timings[mode]), f"{path}: missing timer")
    s, e = timings[STANDARD], timings[SELECTIVE]
    gap = e["SMAA"] - s["SMAA"]
    copies = e["TSCMAACopySpatialToHistory"] + e["TSCMAAOutputCopy"]
    scheduling = e["TSCMAAClearIntegratedCandidateBuffers"] + e["TSCMAAComputeDispatchArgs"]
    residual = {mode: timings[mode]["SMAA"] - sum(timings[mode][p] for p in PARTS[mode])
                for mode in PARTS}
    # Nested timers need not exactly sum to the parent; retain their residual.
    decomposition = {
        "spatial_path_delta_not_candidate_only_ms": e["SMAASpatial1X"] - s["SMAAStandardSpatialT2X"],
        "velocity_delta_ms": e["SMAAGenerateCameraVelocity"] - s["SMAAGenerateCameraVelocity"],
        "copies_ms": copies,
        "clear_and_args_ms": scheduling,
        "resolve_delta_ms": e["TSCMAAResolveCandidates"] - s["SMAAStandardTemporalResolve"],
        "timer_residual_delta_ms": residual[SELECTIVE] - residual[STANDARD],
    }
    require(abs(sum(decomposition.values()) - gap) < 1e-9, "gap decomposition does not reconcile")
    scenarios = {}
    for name, removed in (
        ("output_copy_zero", e["TSCMAAOutputCopy"]),
        ("both_copies_zero", copies),
        ("both_copies_clear_args_zero", copies + scheduling),
        ("candidate_resolve_zero", e["TSCMAAResolveCandidates"]),
    ):
        projected = e["SMAA"] - removed
        scenarios[name] = {"conditional_ms": projected,
                           "gap_to_standard_ms": projected - s["SMAA"],
                           "gap_to_standard_percent": 100 * (projected / s["SMAA"] - 1)}
    return {
        "source": path.relative_to(ROOT).as_posix(), "sha256": digest(path), "metadata": meta,
        "timings_ms": timings, "timer_residual_ms": residual,
        "gap_ms": gap, "required_reduction_percent": 100 * gap / e["SMAA"],
        "gap_decomposition": decomposition, "conditional_scenarios": scenarios,
        "nonspatial_budget_after_current_spatial_and_velocity_ms":
            s["SMAA"] - e["SMAASpatial1X"] - e["SMAAGenerateCameraVelocity"],
    }


def matched_evidence(path: Path) -> list[dict]:
    stored = json.loads(path.read_text(encoding="utf-8-sig"))
    require(stored.get("passed") is True and not stored.get("errors"), "matched evidence failed")
    evidence = []
    for case in stored["cases"]:
        raw = Path(case["source"])
        text, meta, timings = parse_results(raw)
        errors = validate(case["label"], case["scene"], case["path_kind"], text, meta, timings)
        require(not errors, str(errors))
        require(timings == case["timings"], f"{raw}: matched summary/raw mismatch")
        require((meta.get("warmup_frames"), meta.get("measurement_frames"), meta.get("repeats"))
                == (300, 4800, 3), "matched repetition contract mismatch")
        require(meta.get("candidate_readback_disabled") is True, "matched readback enabled")
        full = timings["ABL-Document-FullScreen-R"]["SMAA"]["mean_ms"]
        edge = timings["O-ET2X-R / integrated edge-selective"]["SMAA"]["mean_ms"]
        evidence.append({"scene": case["scene"], "path_kind": case["path_kind"],
                         "raw_source": str(raw), "sha256": digest(raw),
                         "full_screen_ms": full, "selective_ms": edge,
                         "selective_change_percent": 100 * (edge / full - 1)})
    require({(x["scene"], x["path_kind"]) for x in evidence}
            == {(s, k) for s in ("bistro", "minecraft") for k in ("legacy", "dual")}
            and len(evidence) == 4, "matched case matrix mismatch")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=ROOT / "Docs/Candidate-Selection-Gate-20260915")
    parser.add_argument("--matched", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary_path = args.baseline / "performance.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    require(summary.get("status") == "PASS", "baseline summary failed")
    scenes = {scene: read_baseline(args.baseline / f"{scene}-Benchmark-results.csv", scene,
                                  summary["scenes"][scene]["metrics"])
              for scene in ("bistro", "minecraft")}
    matched = matched_evidence(args.matched)
    output = {"status": "PASS", "classification": "historical measured-cost audit; no new GPU benchmark",
              "assumption": "Subtractions hold all remaining costs fixed and assign zero replacement cost. They are not measured speedups, hardware lower bounds, or proof of impossibility.",
              "comparison_limit": "September baseline and August matched evidence use different runs and paths; absolute timings are never subtracted across those sets.",
              "baseline_summary_sha256": digest(summary_path), "matched_summary_sha256": digest(args.matched),
              "scenes": scenes, "matched_historical_evidence": matched}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "budget.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# ET2X 성능 예산 재계산", "", "검증 PASS. 기존 원시 측정의 재분석이며 새 GPU 측정이 아니다.", "",
             "| 장면 | Standard ms | ET2X ms | 차이 ms | 필요한 ET2X 감소율 |",
             "|---|---:|---:|---:|---:|"]
    for scene, data in scenes.items():
        t = data["timings_ms"]
        lines.append(f"| {scene} | {t[STANDARD]['SMAA']:.6f} | {t[SELECTIVE]['SMAA']:.6f} | {data['gap_ms']:.6f} | {data['required_reduction_percent']:.2f}% |")
    lines += ["", "## 비용 차이 분해", "", "공간 구간 차이에는 jitter/subsample 등 경로 차이도 있어 후보 계산 단독 비용이 아니다.", "",
              "| 항목 | Bistro ms | Minecraft ms |", "|---|---:|---:|"]
    for key in scenes["bistro"]["gap_decomposition"]:
        lines.append(f"| {key} | {scenes['bistro']['gap_decomposition'][key]:+.6f} | {scenes['minecraft']['gap_decomposition'][key]:+.6f} |")
    lines += ["", "## 조건부 비용 삭제 가정", "", "나머지 비용 고정, 대체 비용 0이라는 산술 가정이다. 구현 가능한 하한이나 실측 가속률이 아니다.", "",
              "| 가정 | Bistro ms / Standard 대비 | Minecraft ms / Standard 대비 |", "|---|---:|---:|"]
    for name in scenes["bistro"]["conditional_scenarios"]:
        cells = [scenes[s]["conditional_scenarios"][name] for s in ("bistro", "minecraft")]
        lines.append(f"| {name} | " + " | ".join(f"{c['conditional_ms']:.6f} / {c['gap_to_standard_percent']:+.2f}%" for c in cells) + " |")
    lines += ["", "## 동일 temporal 계산의 기존 비교", "", "8월 결과의 내부 짝 비교만 사용한다. 위 9월 절대 시간과 합산하지 않는다.", "",
              "| 장면 | 경로 | Full-screen ms | Selective ms | 변화 |", "|---|---|---:|---:|---:|"]
    for item in matched:
        lines.append(f"| {item['scene']} | {item['path_kind']} | {item['full_screen_ms']:.6f} | {item['selective_ms']:.6f} | {item['selective_change_percent']:.2f}% |")
    (args.output / "budget.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(args.output), "scenes": len(scenes), "matched_cases": len(matched)}))


if __name__ == "__main__":
    main()
