#!/usr/bin/env python3
"""Validate and combine the formal CGVQM-2 motion-to-still coverage gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
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
    ("O-1X", "O_1X", "baseline"),
    ("O-T2X-R", "O_T2X_R", "baseline"),
    ("FullScreenDocument-R", "ABL_Document_FullScreen_R", "coverage"),
    ("O-ET2X-R", "O_ET2X_R", "baseline"),
)
EXPECTED_PROVENANCE_MODE = {
    "O-1X": "O-1X",
    "O-T2X-R": "O-T2X-R",
    "FullScreenDocument-R": "ABL-Document-FullScreen-R",
    "O-ET2X-R": "O-ET2X-R",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--coverage-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--hash-bridge",
        nargs=3,
        action="append",
        required=True,
        metavar=("SCENE", "NEW_CAPTURE_ROOT", "FORMAL_CAPTURE_ROOT"),
        help="Prove that the three reused control sequences are byte-identical.",
    )
    return parser.parse_args()


def nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise KeyError(".".join(keys))
        value = value[key]
    return value


def load_result(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_result(
    payload: dict[str, Any],
    *,
    scene: str,
    mode: str,
    start: int,
    end: int,
    count: int,
) -> list[str]:
    errors: list[str] = []

    def expect(label: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{scene}/{mode}: {label}={actual!r}, expected {expected!r}")

    try:
        expect("classification", nested(payload, "classification"), "formal")
        expect("scene", nested(payload, "provenance", "scene"), scene)
        expect("camera_profile", nested(payload, "provenance", "camera_profile"), PROFILE)
        expect(
            "test_mode",
            nested(payload, "provenance", "test_mode"),
            EXPECTED_PROVENANCE_MODE[mode],
        )
        expect("reference_id", nested(payload, "provenance", "reference_id"), "SS-Reference")
        expect("official commit", nested(payload, "official_cgvqm", "commit"), OFFICIAL_COMMIT)
        expect("CUDA", nested(payload, "runtime", "cuda_available"), True)
        expect("device", nested(payload, "runtime", "device"), "cuda")
        expect("GPU", nested(payload, "runtime", "gpu"), "NVIDIA GeForce RTX 3060 Ti")
        expect("patch_scale", nested(payload, "configuration", "patch_scale"), 4)
        expect("patch_pool", nested(payload, "configuration", "patch_pool"), "mean")
        expect("models", nested(payload, "configuration", "models"), ["2"])
        for sequence in ("test_sequence", "reference_sequence"):
            expect(f"{sequence}.frame_count", nested(payload, sequence, "frame_count"), count)
            expect(f"{sequence}.first_index", nested(payload, sequence, "first_index"), start)
            expect(f"{sequence}.last_index", nested(payload, sequence, "last_index"), end)
            expect(f"{sequence}.width", nested(payload, sequence, "width"), 1920)
            expect(f"{sequence}.height", nested(payload, sequence, "height"), 1017)
        for round_trip in ("test_round_trip", "reference_round_trip"):
            expect(
                f"{round_trip}.mismatched_values",
                nested(payload, round_trip, "mismatched_values"),
                0,
            )
            expect(
                f"{round_trip}.max_absolute_difference",
                nested(payload, round_trip, "max_absolute_difference"),
                0,
            )
        score = float(nested(payload, "results", "CGVQM-2", "score_higher_is_better"))
        if not 0.0 <= score <= 100.0:
            errors.append(f"{scene}/{mode}: CGVQM-2 score out of range: {score}")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"{scene}/{mode}: malformed result: {exc}")
    return errors


def delta(a: float, b: float) -> float:
    return a - b


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_hash_bridges(
    raw_bridges: list[list[str]], errors: list[str]
) -> list[dict[str, Any]]:
    bridge_modes = ("O_1X", "O_T2X_R", "O_ET2X_R")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_scene, raw_new, raw_formal in raw_bridges:
        scene = "Bistro" if raw_scene.lower() == "bistro" else (
            "Minecraft" if raw_scene.lower() == "minecraft" else raw_scene
        )
        if scene not in SCENES:
            errors.append(f"unsupported hash-bridge scene: {raw_scene}")
            continue
        if scene in seen:
            errors.append(f"duplicate hash-bridge scene: {scene}")
            continue
        seen.add(scene)
        new_root = Path(raw_new).resolve()
        formal_root = Path(raw_formal).resolve()
        for mode in bridge_modes:
            new_files = sorted((new_root / mode).glob("*.png"))
            formal_files = sorted((formal_root / mode).glob("*.png"))
            mismatches = 0
            if len(new_files) != 480 or len(formal_files) != 480:
                errors.append(
                    f"{scene}/{mode}: hash bridge counts new={len(new_files)}, "
                    f"formal={len(formal_files)}, expected 480"
                )
            if [path.name for path in new_files] != [path.name for path in formal_files]:
                errors.append(f"{scene}/{mode}: hash bridge filenames differ")
            for new_path, formal_path in zip(new_files, formal_files):
                if sha256(new_path) != sha256(formal_path):
                    mismatches += 1
            if mismatches:
                errors.append(f"{scene}/{mode}: {mismatches} byte hash mismatches")
            rows.append(
                {
                    "scene": scene,
                    "mode": mode,
                    "new_capture_root": str(new_root),
                    "formal_capture_root": str(formal_root),
                    "new_frame_count": len(new_files),
                    "formal_frame_count": len(formal_files),
                    "byte_hash_mismatches": mismatches,
                }
            )
    if seen != set(SCENES):
        errors.append(f"hash-bridge scenes={sorted(seen)}, expected {sorted(SCENES)}")
    return rows


def main() -> int:
    args = parse_args()
    baseline_root = args.baseline_root.resolve()
    coverage_root = args.coverage_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    bridge_rows = validate_hash_bridges(args.hash_bridge, errors)
    for scene in SCENES:
        for window, (start, end, count, window_label) in WINDOWS.items():
            reference_hashes: set[str] = set()
            for mode, directory, source in MODES:
                root = baseline_root if source == "baseline" else coverage_root
                result_path = root / scene / window / directory / "CGVQM-Results.json"
                try:
                    payload = load_result(result_path)
                except (FileNotFoundError, json.JSONDecodeError) as exc:
                    errors.append(f"{scene}/{window}/{mode}: cannot load {result_path}: {exc}")
                    continue
                errors.extend(
                    validate_result(
                        payload,
                        scene=scene,
                        mode=mode,
                        start=start,
                        end=end,
                        count=count,
                    )
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
                        "result_json": str(result_path),
                    }
                )
            if len(reference_hashes) != 1:
                errors.append(
                    f"{scene}/{window}: expected one shared reference hash, got "
                    f"{sorted(reference_hashes)}"
                )

    expected_rows = len(SCENES) * len(WINDOWS) * len(MODES)
    if len(rows) != expected_rows:
        errors.append(f"result count={len(rows)}, expected {expected_rows}")

    scores = {(row["scene"], row["window"], row["mode"]): row["score"] for row in rows}
    comparisons: list[dict[str, Any]] = []
    if not errors:
        for scene in SCENES:
            for window, (_, _, _, window_label) in WINDOWS.items():
                one_x = scores[(scene, window, "O-1X")]
                standard = scores[(scene, window, "O-T2X-R")]
                full = scores[(scene, window, "FullScreenDocument-R")]
                edge = scores[(scene, window, "O-ET2X-R")]
                standard_edge_gap = standard - edge
                coverage_recovery = full - edge
                gap_fraction = (
                    coverage_recovery / standard_edge_gap
                    if standard_edge_gap > 0.0 and coverage_recovery > 0.0
                    else None
                )
                comparisons.append(
                    {
                        "scene": scene,
                        "window": window,
                        "window_label": window_label,
                        "o_1x": one_x,
                        "standard": standard,
                        "full_document": full,
                        "edge_selective": edge,
                        "edge_minus_full": delta(edge, full),
                        "edge_minus_standard": delta(edge, standard),
                        "full_minus_standard": delta(full, standard),
                        "coverage_recovered_score_gap_fraction": gap_fraction,
                    }
                )

    with (output_dir / "motion_to_still_coverage_cgvqm_scores.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["scene"])
        writer.writeheader()
        writer.writerows(rows)
    if comparisons:
        with (output_dir / "motion_to_still_coverage_cgvqm_comparisons.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(comparisons[0]))
            writer.writeheader()
            writer.writerows(comparisons)
    if bridge_rows:
        with (output_dir / "motion_to_still_coverage_hash_bridge.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(bridge_rows[0]))
            writer.writeheader()
            writer.writerows(bridge_rows)

    summary = {
        "passed": not errors,
        "errors": errors,
        "official_commit": OFFICIAL_COMMIT,
        "profile": PROFILE,
        "scores": rows,
        "comparisons": comparisons,
        "hash_bridge": bridge_rows,
    }
    (output_dir / "motion_to_still_coverage_cgvqm_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Motion-to-still coverage CGVQM-2 gate",
        "",
        f"검증: **{'PASS' if not errors else 'FAIL'}**",
        "",
        f"- IntelLabs/CGVQM commit: `{OFFICIAL_COMMIT}`",
        "- GPU: NVIDIA GeForce RTX 3060 Ti / CUDA",
        "- 입력: FFV1 decoded RGB pixel-exact round-trip",
        f"- 재사용 control capture hash bridge: {sum(row['new_frame_count'] for row in bridge_rows):,} PNG, byte mismatch {sum(row['byte_hash_mismatches'] for row in bridge_rows):,}",
        "- FullScreenDocument-R과 O-ET2X-R은 spatial SMAA 1X, jitter Off, camera/depth reprojection, Catmull-Rom 5-tap, YCoCg clipping, history weight 0.8을 동일하게 유지한다.",
        "- 두 mode의 통제 차이는 full-screen 대 integrated first-pass edge-selective coverage/execution이다.",
        "",
        "| Scene | Window | O-1X | O-T2X-R | FullScreenDocument-R | O-ET2X-R | Edge−Full | Edge−Standard |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparisons:
        lines.append(
            f"| {row['scene']} | {row['window_label']} | {row['o_1x']:.6f} | "
            f"{row['standard']:.6f} | {row['full_document']:.6f} | "
            f"{row['edge_selective']:.6f} | {row['edge_minus_full']:+.6f} | "
            f"{row['edge_minus_standard']:+.6f} |"
        )
    lines += [
        "",
        "## 판정",
        "",
        "- Central motion에서는 두 장면 모두 O-ET2X-R이 matched full-screen control보다 높다. 후보 제한이 움직임 중 품질 저하의 원인이라는 가설은 지지되지 않는다.",
        "- Motion→still transition에서는 FullScreenDocument-R이 O-ET2X-R보다 소폭 높다. 따라서 restricted coverage가 정지 전환 손실에 일부 관여한다.",
        "- 그러나 FullScreenDocument-R도 두 장면 모두 Standard O-T2X-R에 미치지 못한다. 남은 격차에는 Standard의 jitter/sample diversity 또는 다른 temporal kernel 차이가 포함된다.",
        "- 이 결과만으로 candidate persistence/confidence를 바로 채택하지 않는다. 다음 통제 실험은 full-screen Standard kernel에서 jitter만 분리해야 한다.",
    ]
    if errors:
        lines += ["", "## 검증 오류", ""] + [f"- {error}" for error in errors]
    (output_dir / "SMAA-Motion-To-Still-Coverage-CGVQM-ko.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"VALIDATION {'PASS' if not errors else 'FAIL'}: {len(rows)}/{expected_rows} results")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
