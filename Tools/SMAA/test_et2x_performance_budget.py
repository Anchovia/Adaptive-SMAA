"""Reject incomplete or inconsistent evidence before publishing a cost budget."""
import json
from pathlib import Path
import tempfile
import unittest

from analyze_et2x_performance_budget import ROOT, read_baseline


class EvidenceValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = ROOT / "Docs/Candidate-Selection-Gate-20260915"
        cls.path = cls.folder / "bistro-Benchmark-results.csv"
        cls.text = cls.path.read_text(encoding="utf-8-sig")
        cls.recorded = json.loads((cls.folder / "performance.json").read_text(
            encoding="utf-8-sig"))["scenes"]["bistro"]["metrics"]

    def reject(self, text, message):
        with tempfile.TemporaryDirectory(prefix="et2x-budget-") as folder:
            path = Path(folder) / "invalid.csv"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, message):
                read_baseline(path, "bistro", self.recorded)

    def test_valid_raw_matches_archived_summary(self):
        result = read_baseline(self.path, "bistro", self.recorded)
        self.assertGreater(result["gap_ms"], 0)

    def test_incomplete_samples_are_rejected(self):
        self.reject(self.text.replace("14400,", "14399,", 1), "incomplete timer")

    def test_summary_disagreement_is_rejected(self):
        self.reject(self.text.replace("0.277314,", "0.177314,", 1), "CSV/recorded JSON mismatch")

    def test_nonfinite_time_is_rejected(self):
        self.reject(self.text.replace("0.277314,", "nan,", 1), "invalid time")

    def test_scene_mismatch_is_rejected(self):
        self.reject(self.text.replace("Scene: bistro.", "Scene: minecraft."), "scene mismatch")

    def test_failed_run_is_rejected(self):
        self.reject(self.text.replace("Performance benchmark validation: PASS",
                                      "Performance benchmark validation: FAIL"), "no PASS")

    def test_duplicate_timer_is_rejected(self):
        row = next(line for line in self.text.splitlines() if line.startswith("O-T2X-R, SMAA,"))
        self.reject(self.text.replace(row, row + "\n" + row), "duplicate timer")


if __name__ == "__main__":
    unittest.main()
