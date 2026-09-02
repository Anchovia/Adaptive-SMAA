#!/usr/bin/env python3
"""Validate and combine formal CGVQM-2 ET2X feedback-topology results."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
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
    (
        "ResolvedOutput",
        "O-ET2X-R-ResolvedFeedback",
        "O-ET2X-R-ResolvedFeedback",
    ),
    (
        "SpatialFrame",
        "ABL-ET2X-R-SpatialFeedback",
        "ABL-ET2X-R-SpatialFeedback",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
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
    reference_start: int,
    reference_end: int,
    count: int,
) -> list[str]:
    errors: list[str] = []

    def expect(label: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(
                f"{scene}/{mode}: {label}={actual!r}, expected={expected!r}"
            )

    try:
        expect("classification", nested(payload, "classification"), "formal")
        expect("scene", nested(payload, "provenance", "scene"), scene)
        expect("profile", nested(payload, "provenance", "camera_profile"), PROFILE)
        expect(
            "test_mode",
            nested(payload, "provenance", "test_mode"),
            provenance_mode,
        )
        expect("reference", nested(payload, "provenance", "reference_id"), "SS-Reference")
        expect("commit", nested(payload, "official_cgvqm", "commit"), OFFICIAL_COMMIT)
        expect("cuda", nested(payload, "runtime", "cuda_available"), True)
        expect("device", nested(payload, "runtime", "device"), "cuda")
        expect("gpu", nested(payload, "runtime", "gpu"), "NVIDIA GeForce RTX 3060 Ti")
        expect("fps", nested(payload, "configuration", "fps"), 60)
        expect("patch_scale", nested(payload, "configuration", "patch_scale"), 4)
        expect("patch_pool", nested(payload, "configuration", "patch_pool"), "mean")
        expect("models", nested(payload, "configuration", "models"), ["2"])
        expect(
            "reference_offset",
            nested(payload, "configuration", "reference_index_offset"),
            reference_start,
        )
        expect("test.frames", nested(payload, "test_sequence", "frame_count"), count)
        expect("test.first", nested(payload, "test_sequence", "first_index"), 0)
        expect("test.last", nested(payload, "test_sequence", "last_index"), count - 1)
        expect(
            "reference.frames",
            nested(payload, "reference_sequence", "frame_count"),
            count,
        )
        expect(
            "reference.first",
            nested(payload, "reference_sequence", "first_index"),
            reference_start,
        )
        expect(
            "reference.last",
            nested(payload, "reference_sequence", "last_index"),
            reference_end,
        )
        for sequence in ("test_sequence", "reference_sequence"):
            expect(f"{sequence}.width", nested(payload, sequence, "width"), 1920)
            expect(f"{sequence}.height", nested(payload, sequence, "height"), 1017)
        for round_trip in ("test_round_trip", "reference_round_trip"):
            expect(f"{round_trip}.codec", nested(payload, round_trip, "codec"), "ffv1")
            expect(
                f"{round_trip}.pixel_format",
                nested(payload, round_trip, "pixel_format"),
                "bgr0",
            )
            expect(
                f"{round_trip}.decoded_frames",
                nested(payload, round_trip, "decoded_frames"),
                count,
            )
            expect(
                f"{round_trip}.mismatch",
                nested(payload, round_trip, "mismatched_values"),
                0,
            )
        for sequence in ("test_sequence", "reference_sequence"):
            pixel_hash = str(nested(payload, sequence, "pixel_sha256"))
            if re.fullmatch(r"[0-9a-f]{64}", pixel_hash) is None:
                errors.append(
                    f"{scene}/{mode}: {sequence}.pixel_sha256 is invalid: "
                    f"{pixel_hash!r}"
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
    root = args.root.resolve()
    output = args.output.resolve()
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for scene in SCENES:
        for window, (start, end, count, label) in WINDOWS.items():
            reference_hashes: set[str] = set()
            for mode, directory, provenance_mode in MODES:
                path = root / scene / window / directory / "CGVQM-Results.json"
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"{scene}/{window}/{mode}: cannot load {path}: {exc}")
                    continue
                errors.extend(
                    validate(
                        payload,
                        scene,
                        mode,
                        provenance_mode,
                        start,
                        end,
                        count,
                    )
                )
                try:
                    score = float(
                        nested(
                            payload,
                            "results",
                            "CGVQM-2",
                            "score_higher_is_better",
                        )
                    )
                    reference_hashes.add(
                        str(nested(payload, "reference_sequence", "pixel_sha256"))
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    errors.append(f"{scene}/{window}/{mode}: missing score/hash: {exc}")
                    continue
                rows.append(
                    {
                        "scene": scene,
                        "window": window,
                        "window_label": label,
                        "mode": mode,
                        "score": score,
                        "result_json": str(path),
                    }
                )
            if len(reference_hashes) != 1:
                errors.append(
                    f"{scene}/{window}: expected one shared reference hash, "
                    f"got {sorted(reference_hashes)}"
                )
    expected = len(SCENES) * len(WINDOWS) * len(MODES)
    if len(rows) != expected:
        errors.append(f"result count={len(rows)}, expected={expected}")
    if errors:
        print("FAIL: CGVQM validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    output.mkdir(parents=True, exist_ok=True)
    scores = {
        (row["scene"], row["window"], row["mode"]): row["score"] for row in rows
    }
    comparisons: list[dict[str, Any]] = []
    for scene in SCENES:
        for window, (_, _, _, label) in WINDOWS.items():
            resolved = scores[(scene, window, "ResolvedOutput")]
            spatial = scores[(scene, window, "SpatialFrame")]
            comparisons.append(
                {
                    "scene": scene,
                    "window": window,
                    "window_label": label,
                    "resolved_score": resolved,
                    "spatial_score": spatial,
                    "spatial_minus_resolved": spatial - resolved,
                }
            )

    with (output / "et2x_feedback_topology_cgvqm_scores.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with (output / "et2x_feedback_topology_cgvqm_comparisons.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparisons[0].keys()))
        writer.writeheader()
        writer.writerows(comparisons)
    (output / "et2x_feedback_topology_cgvqm_summary.json").write_text(
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

    lines = [
        "# O-ET2X-R History Feedback Topology CGVQM-2 결과",
        "",
        "## 검증 조건",
        "",
        f"- Intel 공식 CGVQM commit: `{OFFICIAL_COMMIT}`",
        "- CUDA device: NVIDIA GeForce RTX 3060 Ti",
        "- FFV1 test/reference round-trip mismatch: 0",
        "- 각 scene/window의 두 feedback mode가 동일 reference pixel hash 사용",
        "- 점수는 높을수록 좋으며 절대 ghosting ground truth는 아님",
        "",
        "| Scene | Window | ResolvedOutput | SpatialFrame | Spatial−Resolved |",
        "|---|---|---:|---:|---:|",
    ]
    for row in comparisons:
        lines.append(
            f"| {row['scene']} | {row['window_label']} | "
            f"{row['resolved_score']:.6f} | {row['spatial_score']:.6f} | "
            f"{row['spatial_minus_resolved']:+.6f} |"
        )
    lines += [
        "",
        "## 판정",
        "",
        "SpatialFrame feedback는 두 장면의 중앙 이동에서 점수를 높였지만 motion→still 전환에서는 낮췄다. 따라서 feedback topology 교체는 전 구간 단일 개선안이 아니라 motion phase trade-off다.",
    ]
    (output / "SMAA-ET2X-Feedback-Topology-CGVQM2-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"PASS: validated {len(rows)} CGVQM-2 results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
