from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from analyze_eight_case_performance import (
    FRAME_RATE_FIELDS,
    clean_row,
    extract_metadata,
    integer,
    number,
    percent_delta,
)


# Report contract shared with the C++ benchmark gate. Keep labels, table columns,
# and timer names here so an eventual C++ schema change has one Python update site.
# Common to the repeated benchmark and short GPU smoke report titles.
REPORT_TITLE_MARKER = "SMAA previous-depth disocclusion"
INTERNAL_PASS_MARKER = "Performance benchmark validation: PASS"
READBACK_DISABLED_MARKER = "Candidate counter readback was disabled"
READBACK_ENABLED_MARKER = "Candidate counter readback: enabled"

TIMING_TABLE_COLUMNS = (
    "Mode",
    "Timing metric",
    "Type",
    "Samples",
    "Mean ms",
    "Median ms",
    "Frame stddev ms",
    "P95 ms",
    "P99 ms",
    "Max ms",
    "Runs",
    "Run-mean stddev ms",
)
FRAME_RATE_TABLE_COLUMNS = (
    "Mode",
    "Wall average FPS",
    "Wall 1% low FPS",
    "GPU-equivalent average FPS",
    "GPU-equivalent 1% low FPS",
)
COUNTER_TABLE_COLUMNS = (
    "Mode",
    "Counter samples",
    "Mean base edges",
    "Mean candidates",
    "Mean process count",
    "Mean candidate/base",
)

TEMPORAL_STANDARD = "Standard"
TEMPORAL_ET2X = "ET2X"
OBJECT_CAMERA_ONLY = "CameraOnly"
OBJECT_RIGID = "Rigid"
DEPTH_OFF = "DepthOff"
DEPTH_ON = "DepthOn"


@dataclass(frozen=True)
class ConfigurationSpec:
    label: str
    temporal: str
    object_motion: str
    depth_rejection: str


# These are the eight exact configuration labels expected in the report's Mode
# column. They deliberately expose all three independent gate axes.
CONFIGURATIONS = (
    ConfigurationSpec(
        "O-T2X-R / camera-only / depth Off",
        TEMPORAL_STANDARD,
        OBJECT_CAMERA_ONLY,
        DEPTH_OFF,
    ),
    ConfigurationSpec(
        "O-T2X-R / camera-only / depth On",
        TEMPORAL_STANDARD,
        OBJECT_CAMERA_ONLY,
        DEPTH_ON,
    ),
    ConfigurationSpec(
        "O-T2X-R / camera+rigid / depth Off",
        TEMPORAL_STANDARD,
        OBJECT_RIGID,
        DEPTH_OFF,
    ),
    ConfigurationSpec(
        "O-T2X-R / camera+rigid / depth On",
        TEMPORAL_STANDARD,
        OBJECT_RIGID,
        DEPTH_ON,
    ),
    ConfigurationSpec(
        "O-ET2X-R / camera-only / depth Off",
        TEMPORAL_ET2X,
        OBJECT_CAMERA_ONLY,
        DEPTH_OFF,
    ),
    ConfigurationSpec(
        "O-ET2X-R / camera-only / depth On",
        TEMPORAL_ET2X,
        OBJECT_CAMERA_ONLY,
        DEPTH_ON,
    ),
    ConfigurationSpec(
        "O-ET2X-R / camera+rigid / depth Off",
        TEMPORAL_ET2X,
        OBJECT_RIGID,
        DEPTH_OFF,
    ),
    ConfigurationSpec(
        "O-ET2X-R / camera+rigid / depth On",
        TEMPORAL_ET2X,
        OBJECT_RIGID,
        DEPTH_ON,
    ),
)
CONFIGURATION_BY_LABEL = {spec.label: spec for spec in CONFIGURATIONS}
CONFIGURATION_LABELS = tuple(spec.label for spec in CONFIGURATIONS)

COMMON_TIMING_METRICS = (
    "ApplicationFrameWall",
    "WholeFrame",
    "SMAA",
    "SMAAGenerateCameraVelocity",
)
STANDARD_TIMING_METRICS = (
    "SMAAStandardSpatialT2X",
    "SMAAStandardTemporalResolve",
)
ET2X_TIMING_METRICS = (
    "SMAASpatial1X",
    "TSCMAACopySpatialToHistory",
    "TSCMAAClearIntegratedCandidateBuffers",
    "TSCMAAComputeDispatchArgs",
    "TSCMAAResolveCandidates",
    "TSCMAAOutputCopy",
)
RIGID_OBJECT_TIMING_METRIC = "SMAAGenerateRigidObjectVelocity"
DEPTH_HISTORY_COPY_TIMING_METRIC = "SMAACopyDepthHistory"

COUNTER_FIELDS = (
    "base_edges",
    "candidates",
    "process_count",
    "candidate_to_base",
)
COUNTER_ABSOLUTE_TOLERANCE = 0.001
COUNTER_RATIO_TOLERANCE = 0.000001
FRAME_RATE_ABSOLUTE_TOLERANCE = 0.002

FORMAL_GPU = "NVIDIA GeForce RTX 3060 Ti"
FORMAL_API = "DirectX11"
FORMAL_RESOLUTION = "1920 x 1017"
FORMAL_VSYNC = "OFF"
FORMAL_WARMUP_FRAMES = 300
FORMAL_MEASUREMENT_FRAMES = 4800
FORMAL_MIN_REPEATS = 3

MODES_OUTPUT_NAME = "object_motion_disocclusion_performance_modes.csv"
EFFECTS_OUTPUT_NAME = "object_motion_disocclusion_depth_effects.csv"
COUNTER_OUTPUT_NAME = "object_motion_disocclusion_candidate_invariance.csv"
SUMMARY_OUTPUT_NAME = "object_motion_disocclusion_performance_summary.json"
REPORT_OUTPUT_NAME = "object_motion_disocclusion_performance_report_ko.md"


class AnalysisError(RuntimeError):
    pass


@dataclass
class ReportData:
    path: Path
    text: str
    metadata: dict[str, Any]
    timings: dict[str, dict[str, dict[str, Any]]]
    frame_rates: dict[str, dict[str, float]]
    counters: dict[str, dict[str, float | int]]
    readback_state: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and analyze the eight-configuration SMAA object-motion "
            "previous-depth disocclusion performance gate."
        )
    )
    parser.add_argument("results_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--counter-results-csv",
        type=Path,
        help=(
            "Optional readback-on characterization CSV. It is required when the "
            "timing CSV has candidate readback disabled, because depth-toggle "
            "candidate invariance cannot be inferred from timing rows."
        ),
    )
    parser.add_argument(
        "--window-state",
        choices=("visible", "hidden", "unknown"),
        default="unknown",
        help="Record how the benchmark window was presented.",
    )
    parser.add_argument(
        "--classification",
        choices=("engineering", "formal"),
        default="engineering",
        help="Classify the timing evidence; formal imposes the fixed benchmark contract.",
    )
    parser.add_argument(
        "--expect-readback",
        choices=("on", "off", "either"),
        default="either",
        help="Expected candidate-readback state of the timing CSV.",
    )
    return parser.parse_args()


def required_timing_metrics(spec: ConfigurationSpec) -> tuple[str, ...]:
    metrics = list(COMMON_TIMING_METRICS)
    metrics.extend(
        STANDARD_TIMING_METRICS
        if spec.temporal == TEMPORAL_STANDARD
        else ET2X_TIMING_METRICS
    )
    if spec.object_motion == OBJECT_RIGID:
        metrics.append(RIGID_OBJECT_TIMING_METRIC)
    if spec.depth_rejection == DEPTH_ON:
        metrics.append(DEPTH_HISTORY_COPY_TIMING_METRIC)
    return tuple(metrics)


def paired_timing_metrics(spec: ConfigurationSpec) -> tuple[str, ...]:
    """Metrics present on both sides of a DepthOff/DepthOn comparison."""
    metrics = list(COMMON_TIMING_METRICS)
    metrics.extend(
        STANDARD_TIMING_METRICS
        if spec.temporal == TEMPORAL_STANDARD
        else ET2X_TIMING_METRICS
    )
    if spec.object_motion == OBJECT_RIGID:
        metrics.append(RIGID_OBJECT_TIMING_METRIC)
    return tuple(metrics)


def _find_exact_header(
    rows: list[list[str]], columns: tuple[str, ...], table_name: str
) -> int:
    matches = [index for index, row in enumerate(rows) if tuple(row) == columns]
    if len(matches) != 1:
        raise AnalysisError(
            f"{table_name}: expected exactly one header {columns}, found {len(matches)}"
        )
    return matches[0]


def _contiguous_table_rows(
    rows: list[list[str]], header_index: int, column_count: int
) -> list[list[str]]:
    table_rows: list[list[str]] = []
    for row in rows[header_index + 1 :]:
        if not row:
            if table_rows:
                break
            continue
        if len(row) != column_count:
            if table_rows:
                break
            raise AnalysisError(
                f"table after row {header_index + 1}: expected {column_count} columns, "
                f"found {len(row)}"
            )
        table_rows.append(row)
    return table_rows


def _readback_state(text: str, has_counter_table: bool) -> str:
    reported_on = READBACK_ENABLED_MARKER in text or has_counter_table
    reported_off = READBACK_DISABLED_MARKER in text
    if reported_on and reported_off:
        raise AnalysisError("report declares candidate readback both enabled and disabled")
    if reported_on:
        return "on"
    if reported_off:
        return "off"
    return "unknown"


def parse_report(path: Path) -> ReportData:
    if not path.is_file():
        raise AnalysisError(f"results CSV does not exist: {path}")

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text = "\n".join(lines)
    rows = [clean_row(row) for row in csv.reader(lines)]
    metadata = extract_metadata(lines)

    timing_header = _find_exact_header(rows, TIMING_TABLE_COLUMNS, "timing table")
    frame_header = _find_exact_header(rows, FRAME_RATE_TABLE_COLUMNS, "frame-rate table")
    counter_headers = [
        index for index, row in enumerate(rows) if tuple(row) == COUNTER_TABLE_COLUMNS
    ]
    if len(counter_headers) > 1:
        raise AnalysisError(
            f"candidate counter table: expected at most one header, found {len(counter_headers)}"
        )

    timings: dict[str, dict[str, dict[str, Any]]] = {}
    for row in _contiguous_table_rows(rows, timing_header, len(TIMING_TABLE_COLUMNS)):
        label, metric = row[0], row[1]
        if label not in CONFIGURATION_BY_LABEL:
            raise AnalysisError(f"timing table contains unknown configuration: {label}")
        if metric in timings.setdefault(label, {}):
            raise AnalysisError(f"duplicate timing row: {label}/{metric}")
        timings[label][metric] = {
            "type": row[2],
            "samples": integer(row[3]),
            "mean_ms": number(row[4]),
            "median_ms": number(row[5]),
            "frame_stddev_ms": number(row[6]),
            "p95_ms": number(row[7]),
            "p99_ms": number(row[8]),
            "max_ms": number(row[9]),
            "runs": integer(row[10]),
            "run_mean_stddev_ms": number(row[11]),
        }

    frame_rates: dict[str, dict[str, float]] = {}
    for row in _contiguous_table_rows(rows, frame_header, len(FRAME_RATE_TABLE_COLUMNS)):
        label = row[0]
        if label not in CONFIGURATION_BY_LABEL:
            raise AnalysisError(f"frame-rate table contains unknown configuration: {label}")
        if label in frame_rates:
            raise AnalysisError(f"duplicate frame-rate row: {label}")
        frame_rates[label] = {
            field: number(value)
            for field, value in zip(FRAME_RATE_FIELDS, row[1:])
        }

    counters: dict[str, dict[str, float | int]] = {}
    if counter_headers:
        for row in _contiguous_table_rows(
            rows, counter_headers[0], len(COUNTER_TABLE_COLUMNS)
        ):
            label = row[0]
            if label not in CONFIGURATION_BY_LABEL:
                raise AnalysisError(
                    f"candidate counter table contains unknown configuration: {label}"
                )
            if label in counters:
                raise AnalysisError(f"duplicate candidate counter row: {label}")
            counters[label] = {
                "samples": integer(row[1]),
                "base_edges": number(row[2]),
                "candidates": number(row[3]),
                "process_count": number(row[4]),
                "candidate_to_base": number(row[5]),
            }

    return ReportData(
        path=path.resolve(),
        text=text,
        metadata=metadata,
        timings=timings,
        frame_rates=frame_rates,
        counters=counters,
        readback_state=_readback_state(text, bool(counter_headers)),
    )


def validate_report(
    report: ReportData,
    *,
    classification: str,
    window_state: str,
    expected_readback: str,
) -> list[str]:
    errors: list[str] = []
    metadata = report.metadata

    if REPORT_TITLE_MARKER not in report.text:
        errors.append(f"missing report title marker: {REPORT_TITLE_MARKER}")
    if INTERNAL_PASS_MARKER not in report.text:
        errors.append(f"missing internal PASS marker: {INTERNAL_PASS_MARKER}")
    if expected_readback != "either" and report.readback_state != expected_readback:
        errors.append(
            f"candidate readback {report.readback_state} != expected {expected_readback}"
        )
    if report.readback_state == "unknown":
        errors.append("candidate readback state is not recorded")

    expected_samples: int | None = None
    if "repeats" in metadata and "measurement_frames" in metadata:
        expected_samples = metadata["repeats"] * metadata["measurement_frames"]
    else:
        errors.append("missing repeats or measurement-frame metadata")

    observed_timing_labels = set(report.timings)
    expected_labels = set(CONFIGURATION_LABELS)
    if observed_timing_labels != expected_labels:
        errors.append(
            "timing configurations differ: "
            f"missing={sorted(expected_labels - observed_timing_labels)}, "
            f"extra={sorted(observed_timing_labels - expected_labels)}"
        )
    if set(report.frame_rates) != expected_labels:
        errors.append(
            "frame-rate configurations differ: "
            f"missing={sorted(expected_labels - set(report.frame_rates))}, "
            f"extra={sorted(set(report.frame_rates) - expected_labels)}"
        )

    all_profile_metrics = set(STANDARD_TIMING_METRICS) | set(ET2X_TIMING_METRICS)
    for spec in CONFIGURATIONS:
        mode_timings = report.timings.get(spec.label, {})
        required = set(required_timing_metrics(spec))
        missing = required - set(mode_timings)
        if missing:
            errors.append(f"{spec.label}: missing timers {sorted(missing)}")
        unexpected = set(mode_timings) - required
        if unexpected:
            errors.append(f"{spec.label}: unexpected timers {sorted(unexpected)}")

        wrong_profile = all_profile_metrics - set(
            STANDARD_TIMING_METRICS
            if spec.temporal == TEMPORAL_STANDARD
            else ET2X_TIMING_METRICS
        )
        present_wrong_profile = wrong_profile & set(mode_timings)
        if present_wrong_profile:
            errors.append(
                f"{spec.label}: timers from the other temporal path are present "
                f"{sorted(present_wrong_profile)}"
            )
        if (
            spec.object_motion == OBJECT_CAMERA_ONLY
            and RIGID_OBJECT_TIMING_METRIC in mode_timings
        ):
            errors.append(
                f"{spec.label}: unexpected {RIGID_OBJECT_TIMING_METRIC} timer"
            )
        if (
            spec.depth_rejection == DEPTH_OFF
            and DEPTH_HISTORY_COPY_TIMING_METRIC in mode_timings
        ):
            errors.append(
                f"{spec.label}: unexpected {DEPTH_HISTORY_COPY_TIMING_METRIC} timer"
            )

        for metric in required & set(mode_timings):
            timing = mode_timings[metric]
            expected_type = (
                "CPU wall interval" if metric == "ApplicationFrameWall" else "GPU timestamp"
            )
            if timing["type"] != expected_type:
                errors.append(
                    f"{spec.label}/{metric}: type {timing['type']} != {expected_type}"
                )
            if expected_samples is not None and timing["samples"] != expected_samples:
                errors.append(
                    f"{spec.label}/{metric}: samples {timing['samples']} != "
                    f"{expected_samples}"
                )
            if "repeats" in metadata and timing["runs"] != metadata["repeats"]:
                errors.append(
                    f"{spec.label}/{metric}: runs {timing['runs']} != "
                    f"{metadata['repeats']}"
                )
            for field in (
                "mean_ms",
                "median_ms",
                "frame_stddev_ms",
                "p95_ms",
                "p99_ms",
                "max_ms",
                "run_mean_stddev_ms",
            ):
                if not math.isfinite(timing[field]):
                    errors.append(f"{spec.label}/{metric}: non-finite {field}")
                elif timing[field] < 0.0:
                    errors.append(f"{spec.label}/{metric}: negative {field}")

        mode_frame_rates = report.frame_rates.get(spec.label, {})
        for field in FRAME_RATE_FIELDS:
            value = mode_frame_rates.get(field)
            if value is None:
                continue
            if not math.isfinite(value) or value <= 0.0:
                errors.append(f"{spec.label}/{field}: frame rate must be finite and positive")

        if all(metric in mode_timings for metric in ("ApplicationFrameWall", "WholeFrame")):
            wall = mode_timings["ApplicationFrameWall"]
            whole = mode_timings["WholeFrame"]
            derived = {
                "wall_average_fps": 1000.0 / wall["mean_ms"]
                if wall["mean_ms"] > 0.0
                else 0.0,
                "wall_1pct_low_fps": 1000.0 / wall["p99_ms"]
                if wall["p99_ms"] > 0.0
                else 0.0,
                "gpu_equivalent_average_fps": 1000.0 / whole["mean_ms"]
                if whole["mean_ms"] > 0.0
                else 0.0,
                "gpu_equivalent_1pct_low_fps": 1000.0 / whole["p99_ms"]
                if whole["p99_ms"] > 0.0
                else 0.0,
            }
            for field, expected in derived.items():
                actual = mode_frame_rates.get(field)
                if actual is not None and math.isfinite(actual):
                    if abs(actual - expected) > FRAME_RATE_ABSOLUTE_TOLERANCE:
                        errors.append(
                            f"{spec.label}/{field}: {actual:.6f} != derived "
                            f"{expected:.6f} within {FRAME_RATE_ABSOLUTE_TOLERANCE:.6f}"
                        )

    if report.readback_state == "off" and report.counters:
        errors.append("candidate counters are present while readback is reported disabled")
    if report.readback_state == "on":
        expected_counter_labels = {
            spec.label for spec in CONFIGURATIONS if spec.temporal == TEMPORAL_ET2X
        }
        observed_counter_labels = set(report.counters)
        if observed_counter_labels != expected_counter_labels:
            errors.append(
                "readback-on report candidate counter configurations differ: "
                f"missing={sorted(expected_counter_labels - observed_counter_labels)}, "
                f"extra={sorted(observed_counter_labels - expected_counter_labels)}"
            )

    if classification == "formal":
        if window_state != "visible":
            errors.append("formal evidence requires --window-state visible")
        if FORMAL_GPU not in metadata.get("system_info", ""):
            errors.append(f"formal GPU must contain {FORMAL_GPU}")
        if metadata.get("api") != FORMAL_API:
            errors.append(f"formal API must be {FORMAL_API}")
        if metadata.get("resolution") != FORMAL_RESOLUTION:
            errors.append(f"formal resolution must be {FORMAL_RESOLUTION}")
        if metadata.get("vsync") != FORMAL_VSYNC:
            errors.append(f"formal VSync must be {FORMAL_VSYNC}")
        if metadata.get("warmup_frames") != FORMAL_WARMUP_FRAMES:
            errors.append(
                f"formal warm-up must be {FORMAL_WARMUP_FRAMES} frames"
            )
        if metadata.get("measurement_frames") != FORMAL_MEASUREMENT_FRAMES:
            errors.append(
                f"formal measurement must be {FORMAL_MEASUREMENT_FRAMES} frames"
            )
        if metadata.get("repeats", 0) < FORMAL_MIN_REPEATS:
            errors.append(f"formal evidence requires at least {FORMAL_MIN_REPEATS} repeats")
        if report.readback_state != "off":
            errors.append("formal timing evidence requires candidate readback off")

    return errors


def _depth_pair(
    temporal: str, object_motion: str
) -> tuple[ConfigurationSpec, ConfigurationSpec]:
    matches = [
        spec
        for spec in CONFIGURATIONS
        if spec.temporal == temporal and spec.object_motion == object_motion
    ]
    off = next(spec for spec in matches if spec.depth_rejection == DEPTH_OFF)
    on = next(spec for spec in matches if spec.depth_rejection == DEPTH_ON)
    return off, on


def validate_counter_source(
    timing_report: ReportData, counter_report: ReportData
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    if counter_report.readback_state != "on":
        errors.append("candidate characterization source must report readback enabled")

    for field in ("system_info", "api", "resolution", "scene"):
        timing_value = timing_report.metadata.get(field)
        counter_value = counter_report.metadata.get(field)
        if timing_value != counter_value:
            errors.append(
                f"counter source {field} {counter_value!r} != timing source {timing_value!r}"
            )

    expected_counter_samples: int | None = None
    if (
        "repeats" in counter_report.metadata
        and "measurement_frames" in counter_report.metadata
    ):
        expected_counter_samples = (
            counter_report.metadata["repeats"]
            * counter_report.metadata["measurement_frames"]
        )

    expected_counter_labels = {
        spec.label for spec in CONFIGURATIONS if spec.temporal == TEMPORAL_ET2X
    }
    observed_counter_labels = set(counter_report.counters)
    if observed_counter_labels != expected_counter_labels:
        errors.append(
            "candidate counter configurations differ: "
            f"missing={sorted(expected_counter_labels - observed_counter_labels)}, "
            f"extra={sorted(observed_counter_labels - expected_counter_labels)}"
        )

    for label in sorted(expected_counter_labels & observed_counter_labels):
        values = counter_report.counters[label]
        if (
            expected_counter_samples is not None
            and values["samples"] != expected_counter_samples
        ):
            errors.append(
                f"{label}: counter samples {values['samples']} != "
                f"{expected_counter_samples}"
            )
        for field in COUNTER_FIELDS:
            if not math.isfinite(float(values[field])):
                errors.append(f"{label}: non-finite {field}")
            elif values[field] < 0.0:
                errors.append(f"{label}: negative {field}")
        if values["candidates"] > values["base_edges"] + COUNTER_ABSOLUTE_TOLERANCE:
            errors.append(f"{label}: candidates exceed base edges")

        delta = abs(float(values["candidates"]) - float(values["process_count"]))
        passed = delta <= COUNTER_ABSOLUTE_TOLERANCE
        checks.append(
            {
                "check": "candidate_process_match",
                "temporal_profile": TEMPORAL_ET2X,
                "object_motion": CONFIGURATION_BY_LABEL[label].object_motion,
                "depth_rejection": CONFIGURATION_BY_LABEL[label].depth_rejection,
                "metric": "candidates_vs_process_count",
                "left_label": "Mean candidates",
                "right_label": "Mean process count",
                "left_value": values["candidates"],
                "right_value": values["process_count"],
                "absolute_delta": delta,
                "tolerance": COUNTER_ABSOLUTE_TOLERANCE,
                "pass": passed,
            }
        )
        if not passed:
            errors.append(
                f"{label}: candidate/process delta {delta:.6f} exceeds "
                f"{COUNTER_ABSOLUTE_TOLERANCE:.6f}"
            )

        expected_ratio = (
            float(values["candidates"]) / float(values["base_edges"])
            if values["base_edges"] > 0.0
            else 0.0
        )
        if abs(expected_ratio - float(values["candidate_to_base"])) > 0.000002:
            errors.append(
                f"{label}: reported candidate/base ratio does not match means"
            )

    for object_motion in (OBJECT_CAMERA_ONLY, OBJECT_RIGID):
        off, on = _depth_pair(TEMPORAL_ET2X, object_motion)
        if off.label not in counter_report.counters or on.label not in counter_report.counters:
            continue
        off_values = counter_report.counters[off.label]
        on_values = counter_report.counters[on.label]
        if off_values["samples"] != on_values["samples"]:
            errors.append(
                f"{TEMPORAL_ET2X}/{object_motion}: DepthOff/DepthOn counter sample "
                "counts differ"
            )
        for field in COUNTER_FIELDS:
            left = float(off_values[field])
            right = float(on_values[field])
            tolerance = (
                COUNTER_RATIO_TOLERANCE
                if field == "candidate_to_base"
                else COUNTER_ABSOLUTE_TOLERANCE
            )
            delta = abs(right - left)
            passed = delta <= tolerance
            checks.append(
                {
                    "check": "depth_toggle_invariance",
                    "temporal_profile": TEMPORAL_ET2X,
                    "object_motion": object_motion,
                    "depth_rejection": "DepthOff-vs-DepthOn",
                    "metric": field,
                    "left_label": off.label,
                    "right_label": on.label,
                    "left_value": left,
                    "right_value": right,
                    "absolute_delta": delta,
                    "tolerance": tolerance,
                    "pass": passed,
                }
            )
            if not passed:
                errors.append(
                    f"{TEMPORAL_ET2X}/{object_motion}/{field}: DepthOn-DepthOff "
                    f"absolute delta {delta:.6f} exceeds {tolerance:.6f}"
                )

    return errors, checks


def build_mode_rows(report: ReportData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in CONFIGURATIONS:
        for metric in required_timing_metrics(spec):
            timing = report.timings[spec.label][metric]
            rows.append(
                {
                    "configuration": spec.label,
                    "temporal_profile": spec.temporal,
                    "object_motion": spec.object_motion,
                    "depth_rejection": spec.depth_rejection,
                    "metric_kind": "timing",
                    "metric": metric,
                    "unit": "ms",
                    **timing,
                    "value": timing["mean_ms"],
                }
            )
        for metric in FRAME_RATE_FIELDS:
            value = report.frame_rates[spec.label][metric]
            rows.append(
                {
                    "configuration": spec.label,
                    "temporal_profile": spec.temporal,
                    "object_motion": spec.object_motion,
                    "depth_rejection": spec.depth_rejection,
                    "metric_kind": "frame_rate",
                    "metric": metric,
                    "unit": "fps",
                    "type": "derived",
                    "samples": "",
                    "mean_ms": "",
                    "median_ms": "",
                    "frame_stddev_ms": "",
                    "p95_ms": "",
                    "p99_ms": "",
                    "max_ms": "",
                    "runs": "",
                    "run_mean_stddev_ms": "",
                    "value": value,
                }
            )
    return rows


def build_effect_rows(report: ReportData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for temporal in (TEMPORAL_STANDARD, TEMPORAL_ET2X):
        for object_motion in (OBJECT_CAMERA_ONLY, OBJECT_RIGID):
            off, on = _depth_pair(temporal, object_motion)
            for metric in paired_timing_metrics(off):
                for statistic in ("mean_ms", "p95_ms", "p99_ms"):
                    off_value = report.timings[off.label][metric][statistic]
                    on_value = report.timings[on.label][metric][statistic]
                    combined_run_stddev = ""
                    absolute_delta_over_combined_run_stddev = ""
                    if statistic == "mean_ms":
                        combined_run_stddev = math.hypot(
                            report.timings[off.label][metric][
                                "run_mean_stddev_ms"
                            ],
                            report.timings[on.label][metric][
                                "run_mean_stddev_ms"
                            ],
                        )
                        if combined_run_stddev > 0.0:
                            absolute_delta_over_combined_run_stddev = (
                                abs(on_value - off_value) / combined_run_stddev
                            )
                    rows.append(
                        {
                            "effect_kind": "paired_timing",
                            "temporal_profile": temporal,
                            "object_motion": object_motion,
                            "depth_off_configuration": off.label,
                            "depth_on_configuration": on.label,
                            "metric": metric,
                            "statistic": statistic,
                            "unit": "ms",
                            "depth_off_value": off_value,
                            "depth_on_value": on_value,
                            "depth_on_minus_off": on_value - off_value,
                            "depth_on_minus_off_percent": percent_delta(
                                on_value, off_value
                            ),
                            "combined_run_mean_stddev_ms": combined_run_stddev,
                            "absolute_delta_over_combined_run_stddev": (
                                absolute_delta_over_combined_run_stddev
                            ),
                        }
                    )

            depth_copy = report.timings[on.label][DEPTH_HISTORY_COPY_TIMING_METRIC]
            for statistic in ("mean_ms", "p95_ms", "p99_ms"):
                rows.append(
                    {
                        "effect_kind": "depth_on_only_component",
                        "temporal_profile": temporal,
                        "object_motion": object_motion,
                        "depth_off_configuration": off.label,
                        "depth_on_configuration": on.label,
                        "metric": DEPTH_HISTORY_COPY_TIMING_METRIC,
                        "statistic": statistic,
                        "unit": "ms",
                        "depth_off_value": "",
                        "depth_on_value": depth_copy[statistic],
                        "depth_on_minus_off": depth_copy[statistic],
                        "depth_on_minus_off_percent": "",
                        "combined_run_mean_stddev_ms": "",
                        "absolute_delta_over_combined_run_stddev": "",
                    }
                )

            for metric in FRAME_RATE_FIELDS:
                off_value = report.frame_rates[off.label][metric]
                on_value = report.frame_rates[on.label][metric]
                rows.append(
                    {
                        "effect_kind": "paired_frame_rate",
                        "temporal_profile": temporal,
                        "object_motion": object_motion,
                        "depth_off_configuration": off.label,
                        "depth_on_configuration": on.label,
                        "metric": metric,
                        "statistic": "value",
                        "unit": "fps",
                        "depth_off_value": off_value,
                        "depth_on_value": on_value,
                        "depth_on_minus_off": on_value - off_value,
                        "depth_on_minus_off_percent": percent_delta(
                            on_value, off_value
                        ),
                        "combined_run_mean_stddev_ms": "",
                        "absolute_delta_over_combined_run_stddev": "",
                    }
                )
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: Iterable[str]) -> None:
    fieldnames = list(fields)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _signed(value: float, digits: int = 6) -> str:
    return f"{value:+.{digits}f}"


def build_markdown(
    timing_report: ReportData,
    counter_report: ReportData,
    effects: list[dict[str, Any]],
    counter_checks: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str:
    mean_effects = {
        (row["temporal_profile"], row["object_motion"], row["metric"]): row
        for row in effects
        if row["statistic"] == "mean_ms"
    }
    lines = [
        "# Object-motion previous-depth rejection 성능 분석",
        "",
        "## 실행 조건과 검증",
        "",
        f"- 분류: `{args.classification}`",
        f"- 창 상태: `{args.window_state}`",
        f"- 장면: `{timing_report.metadata.get('scene', 'unknown')}`",
        f"- GPU: `{timing_report.metadata.get('system_info', 'unknown')}`",
        f"- API / 해상도: `{timing_report.metadata.get('api', 'unknown')}` / "
        f"`{timing_report.metadata.get('resolution', 'unknown')}`",
        f"- timing CSV readback: `{timing_report.readback_state}`",
        f"- 후보 통계 CSV: `{counter_report.path}`",
        f"- 후보 통계 readback: `{counter_report.readback_state}`",
        f"- 반복: `{timing_report.metadata.get('repeats', 'unknown')}`회, warm-up "
        f"`{timing_report.metadata.get('warmup_frames', 'unknown')}` frame, 측정 "
        f"`{timing_report.metadata.get('measurement_frames', 'unknown')}` frame/configuration/repeat",
        f"- 후보 통계 범위: `{counter_report.metadata.get('repeats', 'unknown')}`회, "
        f"warm-up `{counter_report.metadata.get('warmup_frames', 'unknown')}` frame, 측정 "
        f"`{counter_report.metadata.get('measurement_frames', 'unknown')}` frame/configuration/repeat",
        "- 내부 benchmark PASS, 8개 configuration, 필수 timer/sample/run, "
        "DepthOn/DepthOff 후보 불변성: **PASS**",
        "",
        "## DepthOn − DepthOff 평균 성능 효과",
        "",
        "| Temporal | Object velocity | WholeFrame | SMAA | Depth copy |",
        "|---|---|---:|---:|---:|",
    ]

    for temporal in (TEMPORAL_STANDARD, TEMPORAL_ET2X):
        for object_motion in (OBJECT_CAMERA_ONLY, OBJECT_RIGID):
            whole = mean_effects[(temporal, object_motion, "WholeFrame")]
            smaa = mean_effects[(temporal, object_motion, "SMAA")]
            depth_copy = mean_effects[
                (temporal, object_motion, DEPTH_HISTORY_COPY_TIMING_METRIC)
            ]
            lines.append(
                f"| {temporal} | {object_motion} | "
                f"{_signed(float(whole['depth_on_minus_off']))} ms "
                f"({_signed(float(whole['depth_on_minus_off_percent']), 3)}%) | "
                f"{_signed(float(smaa['depth_on_minus_off']))} ms "
                f"({_signed(float(smaa['depth_on_minus_off_percent']), 3)}%) | "
                f"{float(depth_copy['depth_on_value']):.6f} ms |"
            )

    lines.extend(
        [
            "",
            "양의 시간 변화는 DepthOn의 추가 비용, 음의 시간 변화는 감소를 뜻한다. "
            "Depth copy는 DepthOff에 존재하지 않는 On-only 구성 요소이므로 비율을 계산하지 않았다.",
            "",
            "## 세부 timer 평균 효과",
            "",
            "| Temporal | Object velocity | Timer | Off (ms) | On (ms) | On−Off (ms) | 변화율 | |Δ|/combined run σ |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in effects:
        if row["effect_kind"] != "paired_timing" or row["statistic"] != "mean_ms":
            continue
        variation_ratio = row["absolute_delta_over_combined_run_stddev"]
        variation_text = (
            f"{float(variation_ratio):.3f}" if variation_ratio != "" else "n/a"
        )
        lines.append(
            f"| {row['temporal_profile']} | {row['object_motion']} | `{row['metric']}` | "
            f"{float(row['depth_off_value']):.6f} | {float(row['depth_on_value']):.6f} | "
            f"{_signed(float(row['depth_on_minus_off']))} | "
            f"{_signed(float(row['depth_on_minus_off_percent']), 3)}% | "
            f"{variation_text} |"
        )

    lines.extend(
        [
            "",
            "## 후보 및 process 불변성",
            "",
            "| 검사 | Object velocity | Depth | 지표 | 왼쪽 | 오른쪽 | 절대 차이 | 허용치 | 결과 |",
            "|---|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for check in counter_checks:
        lines.append(
            f"| {check['check']} | {check['object_motion']} | "
            f"{check['depth_rejection']} | `{check['metric']}` | "
            f"{float(check['left_value']):.6f} | {float(check['right_value']):.6f} | "
            f"{float(check['absolute_delta']):.6f} | "
            f"{float(check['tolerance']):.6f} | "
            f"{'PASS' if check['pass'] else 'FAIL'} |"
        )

    lines.extend(
        [
            "",
            "후보 불변성은 previous-depth rejection toggle이 현재 프레임의 edge 선택, "
            "compact 목록 및 indirect process count를 바꾸지 않았음을 확인한다. 품질 개선 "
            "여부는 이 성능 gate와 별도의 frame-aligned 품질 gate에서 판단해야 한다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    try:
        timing_report = parse_report(args.results_csv)
        timing_errors = validate_report(
            timing_report,
            classification=args.classification,
            window_state=args.window_state,
            expected_readback=args.expect_readback,
        )

        if args.counter_results_csv is not None:
            counter_report = parse_report(args.counter_results_csv)
            counter_errors = validate_report(
                counter_report,
                classification="engineering",
                window_state=args.window_state,
                expected_readback="on",
            )
        elif timing_report.readback_state == "on":
            counter_report = timing_report
            counter_errors = []
        else:
            raise AnalysisError(
                "timing CSV has candidate readback disabled; provide a matching "
                "readback-on CSV with --counter-results-csv to verify candidate invariance"
            )

        invariance_errors, counter_checks = validate_counter_source(
            timing_report, counter_report
        )
        errors = timing_errors + counter_errors + invariance_errors
        if errors:
            raise AnalysisError("validation failed:\n- " + "\n- ".join(errors))

        args.output.mkdir(parents=True, exist_ok=True)
        mode_rows = build_mode_rows(timing_report)
        effect_rows = build_effect_rows(timing_report)

        _write_csv(
            args.output / MODES_OUTPUT_NAME,
            mode_rows,
            (
                "configuration",
                "temporal_profile",
                "object_motion",
                "depth_rejection",
                "metric_kind",
                "metric",
                "unit",
                "type",
                "samples",
                "mean_ms",
                "median_ms",
                "frame_stddev_ms",
                "p95_ms",
                "p99_ms",
                "max_ms",
                "runs",
                "run_mean_stddev_ms",
                "value",
            ),
        )
        _write_csv(
            args.output / EFFECTS_OUTPUT_NAME,
            effect_rows,
            (
                "effect_kind",
                "temporal_profile",
                "object_motion",
                "depth_off_configuration",
                "depth_on_configuration",
                "metric",
                "statistic",
                "unit",
                "depth_off_value",
                "depth_on_value",
                "depth_on_minus_off",
                "depth_on_minus_off_percent",
                "combined_run_mean_stddev_ms",
                "absolute_delta_over_combined_run_stddev",
            ),
        )
        _write_csv(
            args.output / COUNTER_OUTPUT_NAME,
            counter_checks,
            (
                "check",
                "temporal_profile",
                "object_motion",
                "depth_rejection",
                "metric",
                "left_label",
                "right_label",
                "left_value",
                "right_value",
                "absolute_delta",
                "tolerance",
                "pass",
            ),
        )

        summary = {
            "schema": {
                "report_title_marker": REPORT_TITLE_MARKER,
                "configuration_labels": list(CONFIGURATION_LABELS),
                "timing_table_columns": list(TIMING_TABLE_COLUMNS),
                "frame_rate_table_columns": list(FRAME_RATE_TABLE_COLUMNS),
                "counter_table_columns": list(COUNTER_TABLE_COLUMNS),
                "required_timers_by_configuration": {
                    spec.label: list(required_timing_metrics(spec))
                    for spec in CONFIGURATIONS
                },
                "counter_absolute_tolerance": COUNTER_ABSOLUTE_TOLERANCE,
                "counter_ratio_tolerance": COUNTER_RATIO_TOLERANCE,
                "frame_rate_absolute_tolerance": FRAME_RATE_ABSOLUTE_TOLERANCE,
            },
            "provenance": {
                "timing_results_csv": str(timing_report.path),
                "timing_results_sha256": _sha256(timing_report.path),
                "counter_results_csv": str(counter_report.path),
                "counter_results_sha256": _sha256(counter_report.path),
                "classification": args.classification,
                "window_state": args.window_state,
                "timing_readback_state": timing_report.readback_state,
                "counter_readback_state": counter_report.readback_state,
                "counter_metadata": counter_report.metadata,
                **timing_report.metadata,
            },
            "validation": {
                "passed": True,
                "configuration_count": len(CONFIGURATIONS),
                "counter_check_count": len(counter_checks),
                "candidate_invariance_passed": all(
                    bool(check["pass"]) for check in counter_checks
                ),
            },
            "depth_effects": effect_rows,
            "candidate_invariance": counter_checks,
        }
        (args.output / SUMMARY_OUTPUT_NAME).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (args.output / REPORT_OUTPUT_NAME).write_text(
            build_markdown(
                timing_report,
                counter_report,
                effect_rows,
                counter_checks,
                args,
            ),
            encoding="utf-8",
        )

        print(f"PASS: {len(CONFIGURATIONS)} configurations validated")
        print(f"PASS: {len(counter_checks)} candidate/process invariance checks")
        print(f"Output: {args.output.resolve()}")
        return 0
    except (AnalysisError, OSError, ValueError, StopIteration) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
