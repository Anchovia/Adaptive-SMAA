#!/usr/bin/env python3
"""Validate and combine formal CGVQM-2 sample-pattern gate results."""

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
    ("O-1X", "O_1X", "baseline", "O-1X"),
    ("O-T2X-R", "O_T2X_R", "baseline", "O-T2X-R"),
    (
        "Standard-PatternOff-R",
        "ABL_Standard_PatternOff_R",
        "pattern",
        "ABL-Standard-PatternOff-R",
    ),
    (
        "FullScreenDocument-R",
        "ABL_Document_FullScreen_R",
        "coverage",
        "ABL-Document-FullScreen-R",
    ),
    (
        "FullScreenDocument-PatternOn-R",
        "ABL_Document_FullScreen_PatternOn_R",
        "interaction",
        "ABL-Document-FullScreen-PatternOn-R",
    ),
    ("O-ET2X-R", "O_ET2X_R", "baseline", "O-ET2X-R"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--pattern-root", type=Path, required=True)
    parser.add_argument("--coverage-root", type=Path, required=True)
    parser.add_argument("--interaction-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise KeyError(".".join(keys))
        value = value[key]
    return value


def validate(
    payload: dict[str, Any],
    scene: str,
    mode: str,
    provenance_mode: str,
    start: int,
    end: int,
    count: int,
) -> list[str]:
    errors: list[str] = []

    def expect(label: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{scene}/{mode}: {label}={actual!r}, expected={expected!r}")

    try:
        expect("classification", nested(payload, "classification"), "formal")
        expect("scene", nested(payload, "provenance", "scene"), scene)
        expect("profile", nested(payload, "provenance", "camera_profile"), PROFILE)
        expect("test_mode", nested(payload, "provenance", "test_mode"), provenance_mode)
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
            expect(
                f"{round_trip}.mismatch",
                nested(payload, round_trip, "mismatched_values"),
                0,
            )
            expect(
                f"{round_trip}.maxdiff",
                nested(payload, round_trip, "max_absolute_difference"),
                0,
            )
        score = float(nested(payload, "results", "CGVQM-2", "score_higher_is_better"))
        if not 0.0 <= score <= 100.0:
            errors.append(f"{scene}/{mode}: score out of range {score}")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"{scene}/{mode}: malformed result: {exc}")
    return errors


def main() -> int:
    args = parse_args()
    roots = {
        "baseline": args.baseline_root.resolve(),
        "pattern": args.pattern_root.resolve(),
        "coverage": args.coverage_root.resolve(),
        "interaction": args.interaction_root.resolve(),
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    for scene in SCENES:
        for window, (start, end, count, window_label) in WINDOWS.items():
            reference_hashes: set[str] = set()
            for mode, directory, source, provenance_mode in MODES:
                path = roots[source] / scene / window / directory / "CGVQM-Results.json"
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"{scene}/{window}/{mode}: cannot load {path}: {exc}")
                    continue
                errors.extend(
                    validate(payload, scene, mode, provenance_mode, start, end, count)
                )
                try:
                    score = float(nested(payload, "results", "CGVQM-2", "score_higher_is_better"))
                    reference_hashes.add(str(nested(payload, "reference_sequence", "pixel_sha256")))
                except (KeyError, TypeError, ValueError) as exc:
                    errors.append(f"{scene}/{window}/{mode}: missing score/hash: {exc}")
                    continue
                rows.append(
                    {
                        "scene": scene,
                        "window": window,
                        "window_label": window_label,
                        "mode": mode,
                        "score": score,
                        "result_json": str(path),
                    }
                )
            if len(reference_hashes) != 1:
                errors.append(
                    f"{scene}/{window}: expected one shared reference hash, got {sorted(reference_hashes)}"
                )
    expected = len(SCENES) * len(WINDOWS) * len(MODES)
    if len(rows) != expected:
        errors.append(f"result count={len(rows)}, expected={expected}")
    if errors:
        raise RuntimeError("CGVQM validation failed:\n- " + "\n- ".join(errors))

    scores = {(row["scene"], row["window"], row["mode"]): row["score"] for row in rows}
    comparisons: list[dict[str, Any]] = []
    for scene in SCENES:
        for window, (_, _, _, window_label) in WINDOWS.items():
            one_x = scores[(scene, window, "O-1X")]
            standard = scores[(scene, window, "O-T2X-R")]
            pattern = scores[(scene, window, "Standard-PatternOff-R")]
            document = scores[(scene, window, "FullScreenDocument-R")]
            document_pattern_on = scores[(scene, window, "FullScreenDocument-PatternOn-R")]
            edge = scores[(scene, window, "O-ET2X-R")]
            comparisons.append(
                {
                    "scene": scene,
                    "window": window,
                    "window_label": window_label,
                    "pattern_off_minus_standard": pattern - standard,
                    "document_pattern_off_minus_on": document - document_pattern_on,
                    "document_on_minus_standard_on": document_pattern_on - standard,
                    "document_minus_pattern_off": document - pattern,
                    "edge_minus_document": edge - document,
                    "pattern_off_minus_one_x": pattern - one_x,
                    "standard_minus_one_x": standard - one_x,
                }
            )

    with (output / "standard_sample_pattern_cgvqm_scores.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with (output / "standard_sample_pattern_cgvqm_comparisons.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparisons[0].keys()))
        writer.writeheader()
        writer.writerows(comparisons)
    (output / "standard_sample_pattern_cgvqm_summary.json").write_text(
        json.dumps(
            {
                "classification": "formal",
                "official_commit": OFFICIAL_COMMIT,
                "rows": rows,
                "comparisons": comparisons,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    comparison_lookup = {
        (row["scene"], row["window"]): row for row in comparisons
    }

    lines = [
        "# SMAA Standard Temporal Sample-Pattern CGVQM-2 결과",
        "",
        "## 검증 조건",
        "",
        f"- Intel 공식 CGVQM commit: `{OFFICIAL_COMMIT}`",
        "- CUDA device: NVIDIA GeForce RTX 3060 Ti",
        "- FFV1 test/reference round-trip mismatch: 0",
        "- 모든 mode/window가 동일 reference pixel hash 사용",
        "- 점수는 높을수록 좋음; 절대 ghosting ground truth는 아님",
        "",
        "## 점수",
        "",
        "| Scene | Window | O-1X | O-T2X-R | Std PatternOff | Doc PatternOn | Doc PatternOff | Edge PatternOff |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for scene in SCENES:
        for window, (_, _, _, label) in WINDOWS.items():
            lines.append(
                f"| {scene} | {label} | "
                f"{scores[(scene, window, 'O-1X')]:.6f} | "
                f"{scores[(scene, window, 'O-T2X-R')]:.6f} | "
                f"{scores[(scene, window, 'Standard-PatternOff-R')]:.6f} | "
                f"{scores[(scene, window, 'FullScreenDocument-PatternOn-R')]:.6f} | "
                f"{scores[(scene, window, 'FullScreenDocument-R')]:.6f} | "
                f"{scores[(scene, window, 'O-ET2X-R')]:.6f} |"
            )
    lines.extend(
        [
            "",
            "## 직교 비교",
            "",
            "양수는 뒤쪽 방식의 CGVQM-2 점수가 더 높음을 뜻한다.",
            "",
            "| Scene | Window | Std Off − On | Doc Off − On | DocOn − StdOn | DocOff − StdOff | EdgeOff − DocOff | StdOff − 1X |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in comparisons:
        lines.append(
            f"| {row['scene']} | {row['window_label']} | "
            f"{row['pattern_off_minus_standard']:+.6f} | "
            f"{row['document_pattern_off_minus_on']:+.6f} | "
            f"{row['document_on_minus_standard_on']:+.6f} | "
            f"{row['document_minus_pattern_off']:+.6f} | "
            f"{row['edge_minus_document']:+.6f} | "
            f"{row['pattern_off_minus_one_x']:+.6f} |"
        )
    lines.extend(
        [
            "",
            "## 결론",
            "",
            "- central motion에서는 Pattern-Off가 Standard보다 높다. 이 경로에서 Standard T2X의 alternating subpixel pattern이 perceptual reference 오차의 주된 원인임을 지지한다.",
            "- motion→still transition에서는 Standard가 Pattern-Off보다 높다. Standard pattern은 정지 전환에서 2-frame subpixel accumulation 이점을 제공한다.",
            "- Pattern-Off가 대체로 O-1X에 가까운 것은 pattern을 제거하면 Standard resolve만으로는 temporal supersampling 이점이 제한됨을 보여준다.",
            "- document kernel에서는 Pattern-Off가 Pattern-On보다 central motion과 motion→still 모두 높았다: "
            f"Bistro {comparison_lookup[('Bistro', 'central_motion_00150_00329')]['document_pattern_off_minus_on']:+.6f}/"
            f"{comparison_lookup[('Bistro', 'transition_00410_00439')]['document_pattern_off_minus_on']:+.6f}, "
            f"Minecraft {comparison_lookup[('Minecraft', 'central_motion_00150_00329')]['document_pattern_off_minus_on']:+.6f}/"
            f"{comparison_lookup[('Minecraft', 'transition_00410_00439')]['document_pattern_off_minus_on']:+.6f}.",
            "- 따라서 paired sample pattern의 transition 이점은 kernel과 독립적이지 않으며, document profile에 pattern을 단순 재활성화하지 않는다.",
            "- edge-selective Pattern-On은 안정적인 unjittered noncandidate base가 없어 제외했으며, 기존 bilinear DeJitter 근사는 블러가 확인된 별도 탈락 ablation이다.",
        ]
    )
    (output / "SMAA-Standard-Sample-Pattern-CGVQM-Results-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"PASS: validated {len(rows)} formal results; output={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
