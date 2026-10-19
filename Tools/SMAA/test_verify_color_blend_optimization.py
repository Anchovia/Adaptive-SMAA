"""Exercise false-PASS risks using small lossless PNG fixtures, without a GPU."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

import verify_color_blend_optimization as verifier


class CaptureValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.receipts = self.root / 'runs.json'
        self.record = self.root / 'original.json'
        self.patcher = patch.multiple(verifier, FRAME_COUNT=3, SIZE=(8, 6), RUNS=[self.receipts])
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.entries = []
        for label, harness, modes in [('candidate', 'Optimization', verifier.MODES),
                                      ('cleanup', 'Preservation', [verifier.CASE17, verifier.NATIVE])]:
            root = self.root / label
            lines = ['Resolution: 8 x 6', 'Scene: bistro']
            for mode in modes:
                (root / mode).mkdir(parents=True)
                for frame in range(3):
                    pixels = np.full((6, 8, 3), frame + (10 if mode == verifier.NATIVE else 0), dtype=np.uint8)
                    Image.fromarray(pixels).save(root / mode / f'frame_{frame:05d}.png')
                    jitter = (.25 if frame % 2 == 0 else -.25) if mode == verifier.NATIVE else 0.
                    lines.append(f'mode_check, {mode}, {frame}, {jitter}, {jitter}, PASS, ')
            lines.append('Aggregate: PASS')
            report = self.root / f'{label}.csv'
            report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            self.entries.append(dict(label=label, harness=harness, scene='bistro', phase='Capture',
                                     report=str(report), capture_root=str(root), executable_sha256='fixture'))
        self.save_receipts()
        hashes = {m: verifier.hashes(self.root / 'cleanup', m) for m in [verifier.CASE17, verifier.NATIVE]}
        self.record.write_text(json.dumps(dict(validation='PASS', receipt=dict(scene='bistro'), rgb_hashes=hashes)), encoding='utf-8')

    def save_receipts(self):
        for entry in self.entries:
            entry['report_sha256'] = hashlib.sha256(Path(entry['report']).read_bytes()).hexdigest().upper()
        self.receipts.write_text(json.dumps(self.entries), encoding='utf-8')

    def rewrite_report(self, edit, index=0):
        path = Path(self.entries[index]['report'])
        path.write_text(edit(path.read_text(encoding='utf-8')), encoding='utf-8')
        self.save_receipts()

    def run_check(self):
        output = self.root / 'validation.json'
        with contextlib.redirect_stdout(io.StringIO()):
            code = verifier.main(['candidate', '--reference', 'cleanup', '--scene', 'bistro',
                                  '--record', str(self.record), '--out', str(output)])
        return code, json.loads(output.read_text(encoding='utf-8'))

    def assert_fails(self, message):
        code, result = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(result['validation'], 'FAIL')
        self.assertIn(message, result['error'])

    def test_complete_six_mode_capture_passes(self):
        code, result = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(result['validation'], 'PASS')
        self.assertEqual(len(result['modes']), 6)

    def test_missing_combined_mode_fails(self):
        combined = verifier.MODES[-2]
        self.rewrite_report(lambda t: '\n'.join(line for line in t.splitlines() if combined not in line))
        self.assert_fails('Incomplete mode/frame checks')

    def test_missing_frame_check_fails(self):
        self.rewrite_report(lambda t: t.replace(f'mode_check, {verifier.NATIVE}, 1, -0.25, -0.25, PASS, \n', ''))
        self.assert_fails('Incomplete mode/frame checks')

    def test_duplicate_frame_check_fails(self):
        self.rewrite_report(lambda t: t + f'mode_check, {verifier.CASE17}, 0, 0, 0, PASS, \n')
        self.assert_fails('Duplicate mode_check')

    def test_wrong_native_start_phase_fails(self):
        self.rewrite_report(lambda t: t.replace(f'{verifier.NATIVE}, 0, 0.25, 0.25', f'{verifier.NATIVE}, 0, -0.25, -0.25'))
        self.assert_fails('Invalid phase/state')

    def test_changed_resolution_fails(self):
        Image.new('RGB', (7, 6)).save(self.root / 'candidate' / verifier.MODES[-2] / 'frame_00001.png')
        self.assert_fails('Unexpected PNG format/size')

    def test_missing_png_fails(self):
        (self.root / 'candidate' / verifier.MODES[-2] / 'frame_00002.png').unlink()
        self.assert_fails('Incomplete/unexpected PNG indices')

    def test_short_original_hash_record_fails(self):
        record = json.loads(self.record.read_text(encoding='utf-8'))
        record['rgb_hashes'][verifier.CASE17].pop()
        self.record.write_text(json.dumps(record), encoding='utf-8')
        self.assert_fails('Hash record frame count is incomplete')

    def test_report_hash_tamper_fails(self):
        path = Path(self.entries[0]['report'])
        path.write_text(path.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        self.assert_fails('Report hash changed')

    def test_false_aggregate_pass_fails(self):
        self.rewrite_report(lambda t: t + 'failed_size, candidate, 1, 7, 6, FAIL\n')
        self.assert_fails('Incomplete/failed report')

    def test_candidate_pixel_change_returns_failure_and_location(self):
        path = self.root / 'candidate' / verifier.MODES[-2] / 'frame_00001.png'
        with Image.open(path) as im:
            pixels = np.asarray(im).copy()
        pixels[2, 3, 1] += 7
        Image.fromarray(pixels).save(path)
        code, result = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(result['validation'], 'MISMATCH')
        row = next(r for r in result['modes'] if r['mode'] == verifier.MODES[-2])
        self.assertEqual(row['mismatch_frames']['same_run'], [1])
        self.assertEqual(row['mismatch_details']['same_run'],
                         [dict(frame=1, changed_pixels=1, max_channel_error=7, bbox=[3, 2, 3, 2])])

    def test_native_regression_returns_failure(self):
        Image.new('RGB', (8, 6), (77, 77, 77)).save(self.root / 'candidate' / verifier.NATIVE / 'frame_00002.png')
        code, result = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(result['validation'], 'MISMATCH')
        row = next(r for r in result['modes'] if r['mode'] == verifier.NATIVE)
        self.assertEqual(row['vs_reference_capture'], 1)
        self.assertEqual(row['vs_original_record'], 1)


if __name__ == '__main__':
    unittest.main()
