#!/usr/bin/env python3
"""Validate and combine formal CGVQM-2 for the document-kernel 2x4 ladder."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


OFFICIAL_COMMIT = "8302ff45b4ff5a691682baf23f7c007d6b591e98"
PROFILE = "flythrough-wide-yaw-360"
SCENES = ("Bistro", "Minecraft")
WINDOWS = {
    "central_motion_00150_00329": (150, 329, 180, "central motion"),
    "transition_00410_00439": (410, 439, 30, "motion→still transition"),
}
MODES = (
    ("standard_on", "O_T2X_R", "baseline", "O-T2X-R", "control", "on"),
    ("standard_off", "ABL_Standard_PatternOff_R", "pattern", "ABL-Standard-PatternOff-R", "control", "off"),
    ("k0_on", "ABL_FS_K0_Bilinear_W05_PatternOn_R", "ladder", "ABL-FS-K0-Bilinear-W05-PatternOn-R", "k0", "on"),
    ("k0_off", "ABL_FS_K0_Bilinear_W05_PatternOff_R", "ladder", "ABL-FS-K0-Bilinear-W05-PatternOff-R", "k0", "off"),
    ("k1_on", "ABL_FS_K1_Catmull_W05_PatternOn_R", "ladder", "ABL-FS-K1-Catmull-W05-PatternOn-R", "k1", "on"),
    ("k1_off", "ABL_FS_K1_Catmull_W05_PatternOff_R", "ladder", "ABL-FS-K1-Catmull-W05-PatternOff-R", "k1", "off"),
    ("k2_on", "ABL_FS_K2_Catmull_Clip_W05_PatternOn_R", "ladder", "ABL-FS-K2-Catmull-Clip-W05-PatternOn-R", "k2", "on"),
    ("k2_off", "ABL_FS_K2_Catmull_Clip_W05_PatternOff_R", "ladder", "ABL-FS-K2-Catmull-Clip-W05-PatternOff-R", "k2", "off"),
    ("k3_on", "ABL_Document_FullScreen_PatternOn_R", "interaction", "ABL-Document-FullScreen-PatternOn-R", "k3", "on"),
    ("k3_off", "ABL_Document_FullScreen_R", "coverage", "ABL-Document-FullScreen-R", "k3", "off"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--pattern-root", type=Path, required=True)
    parser.add_argument("--coverage-root", type=Path, required=True)
    parser.add_argument("--interaction-root", type=Path, required=True)
    parser.add_argument("--ladder-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise KeyError(".".join(keys))
        value = value[key]
    return value


def validate(payload: dict[str, Any], scene: str, key: str, provenance: str, start: int, end: int, count: int) -> list[str]:
    errors: list[str] = []
    def expect(label: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{scene}/{key}: {label}={actual!r}, expected={expected!r}")
    try:
        expect("classification", nested(payload, "classification"), "formal")
        expect("scene", nested(payload, "provenance", "scene"), scene)
        expect("profile", nested(payload, "provenance", "camera_profile"), PROFILE)
        expect("test_mode", nested(payload, "provenance", "test_mode"), provenance)
        expect("reference", nested(payload, "provenance", "reference_id"), "SS-Reference")
        expect("commit", nested(payload, "official_cgvqm", "commit"), OFFICIAL_COMMIT)
        expect("cuda", nested(payload, "runtime", "cuda_available"), True)
        expect("device", nested(payload, "runtime", "device"), "cuda")
        expect("gpu", nested(payload, "runtime", "gpu"), "NVIDIA GeForce RTX 3060 Ti")
        expect("patch_scale", nested(payload, "configuration", "patch_scale"), 4)
        expect("patch_pool", nested(payload, "configuration", "patch_pool"), "mean")
        expect("models", nested(payload, "configuration", "models"), ["2"])
        for sequence in ("test_sequence", "reference_sequence"):
            expect(f"{sequence}.frames", nested(payload, sequence, "frame_count"), count)
            expect(f"{sequence}.first", nested(payload, sequence, "first_index"), start)
            expect(f"{sequence}.last", nested(payload, sequence, "last_index"), end)
            expect(f"{sequence}.width", nested(payload, sequence, "width"), 1920)
            expect(f"{sequence}.height", nested(payload, sequence, "height"), 1017)
        for round_trip in ("test_round_trip", "reference_round_trip"):
            expect(f"{round_trip}.mismatch", nested(payload, round_trip, "mismatched_values"), 0)
            expect(f"{round_trip}.maxdiff", nested(payload, round_trip, "max_absolute_difference"), 0)
        score = float(nested(payload, "results", "CGVQM-2", "score_higher_is_better"))
        if not 0.0 <= score <= 100.0:
            errors.append(f"{scene}/{key}: score out of range {score}")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"{scene}/{key}: malformed result: {exc}")
    return errors


def main() -> int:
    args = parse_args()
    roots = {
        "baseline": args.baseline_root.resolve(), "pattern": args.pattern_root.resolve(),
        "coverage": args.coverage_root.resolve(), "interaction": args.interaction_root.resolve(),
        "ladder": args.ladder_root.resolve(),
    }
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    for scene in SCENES:
        for window, (start, end, count, label) in WINDOWS.items():
            hashes: set[str] = set()
            for key, directory, source, provenance, stage, pattern in MODES:
                path = roots[source] / scene / window / directory / "CGVQM-Results.json"
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"{scene}/{window}/{key}: cannot load {path}: {exc}")
                    continue
                errors.extend(validate(payload, scene, key, provenance, start, end, count))
                try:
                    score = float(nested(payload, "results", "CGVQM-2", "score_higher_is_better"))
                    hashes.add(str(nested(payload, "reference_sequence", "pixel_sha256")))
                except (KeyError, TypeError, ValueError) as exc:
                    errors.append(f"{scene}/{window}/{key}: missing score/hash: {exc}")
                    continue
                rows.append({"scene": scene, "window": window, "window_label": label, "mode_key": key, "stage": stage, "pattern": pattern, "score": score, "result_json": str(path)})
            if len(hashes) != 1:
                errors.append(f"{scene}/{window}: expected one shared reference hash, got {sorted(hashes)}")
    expected = len(SCENES) * len(WINDOWS) * len(MODES)
    if len(rows) != expected:
        errors.append(f"result count={len(rows)}, expected={expected}")
    if errors:
        raise RuntimeError("CGVQM validation failed:\n- " + "\n- ".join(errors))

    scores = {(r["scene"], r["window"], r["mode_key"]): float(r["score"]) for r in rows}
    comparisons: list[dict[str, Any]] = []
    for scene in SCENES:
        for window, (_, _, _, label) in WINDOWS.items():
            row: dict[str, Any] = {"scene": scene, "window": window, "window_label": label}
            for stage in ("k0", "k1", "k2", "k3"):
                row[f"{stage}_off_minus_on"] = scores[(scene, window, f"{stage}_off")] - scores[(scene, window, f"{stage}_on")]
            for pattern in ("on", "off"):
                row[f"{pattern}_catmull_k1_minus_k0"] = scores[(scene, window, f"k1_{pattern}")] - scores[(scene, window, f"k0_{pattern}")]
                row[f"{pattern}_clipping_k2_minus_k1"] = scores[(scene, window, f"k2_{pattern}")] - scores[(scene, window, f"k1_{pattern}")]
                row[f"{pattern}_weight08_k3_minus_k2"] = scores[(scene, window, f"k3_{pattern}")] - scores[(scene, window, f"k2_{pattern}")]
            row["contextual_k0_minus_standard_on"] = scores[(scene, window, "k0_on")] - scores[(scene, window, "standard_on")]
            row["contextual_k0_minus_standard_off"] = scores[(scene, window, "k0_off")] - scores[(scene, window, "standard_off")]
            comparisons.append(row)

    with (output / "document_kernel_ladder_cgvqm_scores.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
    with (output / "document_kernel_ladder_cgvqm_comparisons.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparisons[0].keys())); writer.writeheader(); writer.writerows(comparisons)
    (output / "document_kernel_ladder_cgvqm_summary.json").write_text(json.dumps({"classification": "formal", "official_commit": OFFICIAL_COMMIT, "rows": rows, "comparisons": comparisons}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# FullScreenDocument Sample-Pattern 2×4 Component Ladder CGVQM-2 결과", "",
        "## 검증 조건", "", f"- Intel 공식 CGVQM commit: `{OFFICIAL_COMMIT}`",
        "- CUDA: NVIDIA GeForce RTX 3060 Ti", "- FFV1 test/reference round-trip mismatch: 0",
        "- 각 scene/window의 10개 mode가 동일 reference pixel hash 사용", "- 점수는 높을수록 좋음", "",
        "## 점수", "", "| Scene | Window | Std On | Std Off | K0 On | K0 Off | K1 On | K1 Off | K2 On | K2 Off | K3 On | K3 Off |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scene in SCENES:
        for window, (_, _, _, label) in WINDOWS.items():
            vals = [scores[(scene, window, key)] for key, *_ in MODES]
            lines.append(f"| {scene} | {label} | " + " | ".join(f"{v:.6f}" for v in vals) + " |")
    lines += ["", "## 직교 차이", "", "양수는 뒤쪽/추가된 구성이 더 높은 CGVQM-2 점수를 뜻한다.", "", "| Scene | Window | K0 Off-On | K1 Off-On | K2 Off-On | K3 Off-On | On K1-K0 | On K2-K1 | On K3-K2 | Off K1-K0 | Off K2-K1 | Off K3-K2 | K0Doc-Std On | K0Doc-Std Off |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in comparisons:
        fields = ["k0_off_minus_on", "k1_off_minus_on", "k2_off_minus_on", "k3_off_minus_on", "on_catmull_k1_minus_k0", "on_clipping_k2_minus_k1", "on_weight08_k3_minus_k2", "off_catmull_k1_minus_k0", "off_clipping_k2_minus_k1", "off_weight08_k3_minus_k2", "contextual_k0_minus_standard_on", "contextual_k0_minus_standard_off"]
        lines.append(f"| {r['scene']} | {r['window_label']} | " + " | ".join(f"{float(r[f]):+.6f}" for f in fields) + " |")
    lines += ["", "## 해석 제한", "", "- CGVQM-2는 full-reference 주 지표이지만 절대 ghosting ground truth는 아니다.", "- supersample spatial proxy, error map, 후기 정지 Δ1/Δ2 진단 및 연속 프레임을 함께 해석한다.", "- K0~K3 내부 비교는 같은 FullScreenDocument 경로의 직교 ladder이므로 유효하다.", "- Standard controls는 point sampling, velocity-alpha 기반 가변 history weight(0~0.5), 직전 spatial-frame history를 사용한다. K0는 bilinear, 고정 0.5, resolve-output feedback history를 사용하므로 K0-Standard 차이는 참고값이며 실행 경로 bias로 단정하지 않는다."]
    (output / "SMAA-Document-Kernel-Component-Ladder-CGVQM-Results-ko.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PASS: validated {len(rows)} formal results; output={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
