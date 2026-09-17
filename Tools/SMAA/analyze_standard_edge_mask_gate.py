"""Validate native Standard coverage-only captures and paired GPU timestamps."""
import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sequence(record):
    report = Path(record['report'])
    files = sorted(report.parent.glob('*/*.png'))
    expected = int(record['arguments'][-1].strip('"').split()[-2])
    assert len(files) == expected > 1, (report, len(files), expected)
    keys = [tuple(map(int, re.search(r'_profile_(\d+)_frame_(\d+)\.png$', p.name).groups())) for p in files]
    assert keys == [(150+i, i) for i in range(expected)], keys
    assert 'Failed' not in report.read_text(encoding='utf-8-sig'), report
    return files, keys


def quality(records):
    by_label = {r['label']: r for r in records}
    assert len(by_label) == len(records) == 5
    sequences = {k: load_sequence(v) for k, v in by_label.items()}
    count = len(sequences['standard'][0])
    assert all(s[1] == sequences['standard'][1] for s in sequences.values())
    selected_count = total = inside_bad = outside_bad = repeat_bad = 0
    rows = []
    previous = None
    for i in range(count):
        images = {k: np.asarray(Image.open(s[0][i]).convert('RGB')) for k, s in sequences.items()}
        std, masked, spatial, mask, repeat = [images[k] for k in ('standard', 'masked', 'spatial', 'mask', 'masked-repeat')]
        assert len({a.shape for a in images.values()}) == 1
        assert np.all((mask == 0) | (mask == 255))
        assert np.array_equal(mask[..., 0], mask[..., 1]) and np.array_equal(mask[..., 0], mask[..., 2])
        selected = mask[..., 0] > 0
        selected_count += int(selected.sum())
        total += selected.size
        inside_bad += int(np.count_nonzero(np.any(masked != std, axis=2) & selected))
        outside_bad += int(np.count_nonzero(np.any(masked != spatial, axis=2) & ~selected))
        repeat_bad += int(np.count_nonzero(np.any(masked != repeat, axis=2)))
        row = {'profile_frame': 150+i, 'selected_pixels': int(selected.sum()),
               'selected_percent': float(selected.mean()*100),
               'masked_vs_standard_rgb_mae': float(np.abs(masked.astype(float)-std).mean())}
        if previous is not None:
            for label in ('standard', 'masked', 'spatial'):
                row[label+'_adjacent_rgb_mae'] = float(np.abs(images[label].astype(float)-previous[label]).mean())
        rows.append(row)
        previous = images
    assert 0 < selected_count < total
    assert inside_bad == outside_bad == repeat_bad == 0, (inside_bad, outside_bad, repeat_bad)
    return {'frames': count, 'selected_screen_percent': selected_count/total*100,
            'candidate_vs_native_standard_mismatch_pixels': inside_bad,
            'noncandidate_vs_current_spatial_mismatch_pixels': outside_bad,
            'repeat_mismatch_pixels': repeat_bad, 'per_frame': rows,
            'interpretation': 'Engineering coverage identity gate; raw adjacent difference includes camera motion, not absolute ghosting or quality.'}


def performance(record):
    path = Path(record['report'])
    text = path.read_text(encoding='utf-8-sig')
    assert 'Performance benchmark validation: PASS' in text
    assert 'Candidate counter readback: disabled' in text
    assert 'repeats: 3, warm-up: 300 frames, measurement: 4800' in text
    assert 'Native Standard coverage-only paired gate' in text
    assert f"Scene: {record['scene']}." in text
    assert 'Resolution:   1920 x 1017' in text
    modes = ('O-T2X-R', 'ABL-Standard-EdgeMask-R')
    metrics = ('ApplicationFrameWall', 'WholeFrame', 'SMAA', 'SMAAGenerateCameraVelocity',
               'SMAAStandardSpatialT2X', 'SMAAStandardTemporalResolve')
    values = {m: {} for m in modes}
    for row in csv.reader(text.splitlines(), skipinitialspace=True):
        row = [v.strip() for v in row]
        if len(row) < 12 or row[0] not in modes:
            continue
        assert row[1] in metrics, ('Unexpected additional pass', row)
        assert row[1] not in values[row[0]], row
        assert int(row[3]) == 14400 and int(row[10]) == 3, row
        nums = [float(row[j]) for j in range(4, 10)] + [float(row[11])]
        assert all(math.isfinite(x) and x >= 0 for x in nums)
        values[row[0]][row[1]] = dict(zip(('mean_ms','median_ms','frame_stddev_ms','p95_ms','p99_ms','max_ms','run_mean_stddev_ms'), nums))
    assert all(set(v) == set(metrics) for v in values.values())
    delta = {m: (values[modes[1]][m]['mean_ms']/values[modes[0]][m]['mean_ms']-1)*100 for m in metrics}
    return {'window': record['window'], 'metrics': values, 'masked_minus_standard_percent': delta,
            'report_sha256': digest(path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--receipt', type=Path, default=Path('tmp/standard-edge-mask-runs.json'))
    ap.add_argument('--output', type=Path, default=Path('Docs/Standard-Edge-Mask-20260917'))
    ap.add_argument('--require-complete', action='store_true')
    args = ap.parse_args()
    records = json.loads(args.receipt.read_text(encoding='utf-8-sig'))
    result = {'classification': 'Native Standard coverage-only ablation; not final 8-case or recovered TSCMAA reproduction',
              'records': records, 'quality': {}, 'performance': {}}
    for scene in ('bistro', 'minecraft'):
        q = [r for r in records if r['phase'] == 'Quality' and r['scene'] == scene]
        if q:
            result['quality'][scene] = quality(q)
        p = [r for r in records if r['phase'] == 'Performance' and r['scene'] == scene]
        assert len(p) <= 1
        if p:
            result['performance'][scene] = performance(p[0])
        bridges = [r for r in records if r['phase'] == 'FinalBuildBridge' and r['scene'] == scene]
        if bridges:
            assert len(bridges) == 1
            earlier = next(r for r in q if r['label'] == 'masked')
            a, ka = load_sequence(earlier)
            b, kb = load_sequence(bridges[0])
            assert ka == kb and all(digest(x) == digest(y) for x, y in zip(a, b))
            assert bridges[0]['executable_sha256'] == p[0]['executable_sha256']
            result['quality'][scene]['final_performance_binary_png_hash_bridge'] = True
    lifecycle = [r for r in records if r['phase'] == 'Lifecycle']
    if lifecycle:
        assert len(lifecycle) == 1
        report = Path(lifecycle[0]['report'])
        body = report.read_text(encoding='utf-8-sig')
        assert 'ABL-Standard-EdgeMask-R mode change, yes, yes, PASS' in body
        assert 'failures 0 => PASS' in body
        result['lifecycle'] = {'passed': True, 'report_sha256': digest(report)}
    if args.require_complete:
        assert set(result['quality']) == set(result['performance']) == {'bistro', 'minecraft'}
        assert result['lifecycle']['passed']
        assert all(q['final_performance_binary_png_hash_bridge'] for q in result['quality'].values())
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
