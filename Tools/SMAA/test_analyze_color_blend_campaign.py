"""Reject incomplete formal timing tables before producing campaign results."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from analyze_color_blend_campaign import METRICS, MODES, validate


class TimingValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name) / 'results.csv'
        self.lines = ['API:  DirectX11', 'Resolution:   1920 x 1061', 'Vsync:        OFF',
                      'Fullscreen:   Windowed', 'Benchmark: PNG/query/readback Off; 4800 frames x 6 alternating repeats.']
        for mode in MODES:
            for run in range(6):
                for metric in sorted(METRICS):
                    self.lines.append(f'timing, {mode}, {run}, {metric}, 4800, 0.1, 0.1, 0.11, 0.12, 0.01, 8000')
        self.lines.append('Aggregate: PASS')

    def check(self):
        self.report.write_text('\n'.join(self.lines) + '\n', encoding='utf-8')
        receipt = dict(report=str(self.report), report_sha256=hashlib.sha256(self.report.read_bytes()).hexdigest(),
                       harness='Optimization')
        return validate(receipt)

    def test_complete_table_passes(self):
        result = self.check()
        self.assertEqual(result['repeats'], 6)
        self.assertEqual(len(result['modes']), 6)

    def test_duplicate_row_rejected(self):
        self.lines.insert(-1, self.lines[5])
        with self.assertRaisesRegex(ValueError, 'timing rows'):
            self.check()

    def test_missing_row_rejected(self):
        self.lines.pop(5)
        with self.assertRaisesRegex(ValueError, 'timing rows'):
            self.check()

    def test_wrong_sample_count_rejected(self):
        self.lines[5] = self.lines[5].replace(', 4800,', ', 240,')
        with self.assertRaisesRegex(ValueError, 'sample count'):
            self.check()

    def test_wrong_resolution_rejected(self):
        self.lines[1] = 'Resolution: 1902 x 1001'
        with self.assertRaisesRegex(ValueError, 'resolution'):
            self.check()

    def test_profile_cannot_be_formal(self):
        self.lines[4] = 'Profile: diagnostic pass timers On'
        with self.assertRaisesRegex(ValueError, 'benchmark condition'):
            self.check()


if __name__ == '__main__':
    unittest.main()
