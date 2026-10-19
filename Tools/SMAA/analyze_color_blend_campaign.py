"""Validate and summarize the fixed case-17 optimization and cleanup campaign.

Optimization deltas use controls from the same process/repeat. Cleanup ABBA
lists each process separately and normalizes case 17 to its own native control;
two processes per build are insufficient for a strong speed claim.
"""
import argparse
import csv
import hashlib
import json
import re
import statistics
from pathlib import Path

from analyze_color_blend_performance import CASE17, NATIVE, ci, rows, summarize
from verify_color_blend_optimization import MODES

METRICS = {'SMAA', 'SF_Spatial', 'SR_CameraVelocity', 'SR_Resolve', 'WholeFrame', 'WallFrame'}
ABBA = ['before-bench-1', 'after-bench-1', 'after-bench-2', 'before-bench-2']


def validate(receipt):
    report = Path(receipt['report'])
    text = report.read_text(encoding='utf-8-sig')
    if hashlib.sha256(report.read_bytes()).hexdigest().upper() != receipt['report_sha256'].upper():
        raise ValueError(f'Report hash changed: {report}')
    for required in ['API:  DirectX11', 'Vsync:        OFF', 'Fullscreen:   Windowed',
                     'PNG/query/readback Off', '4800 frames x 6 alternating repeats']:
        if required not in text:
            raise ValueError(f'Missing benchmark condition {required}: {report}')
    if not re.search(r'Resolution:\s*1920\s*x\s*1061\b', text):
        raise ValueError(f'Wrong resolution: {report}')
    modes = MODES if receipt.get('harness', 'Preservation') == 'Optimization' else [CASE17, NATIVE]
    r = rows(report)
    expected = {(mode, run, metric) for mode in modes for run in range(6) for metric in METRICS}
    if set(r) != expected or len(re.findall(r'^timing,', text, re.M)) != len(r):
        raise ValueError(f'Duplicate/missing/extra timing rows: {report}')
    if any(v['samples'] != 4800 or any(not (0 < v[k] < float('inf')) for k in
                                      ['mean', 'median', 'p95', 'p99', 'low1_fps']) for v in r.values()):
        raise ValueError(f'Invalid sample count or timing: {report}')
    result = summarize(report)
    result['receipt'] = receipt
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', nargs='+', required=True)
    ap.add_argument('--out-dir', required=True)
    x = ap.parse_args()
    receipts = {}
    for path in x.runs:
        for r in json.loads(Path(path).read_text(encoding='utf-8-sig')):
            if r['phase'] == 'Benchmark' and r['label'] in ABBA + ['opt-bench-b']:
                receipts[(r['scene'], r['label'])] = r
    expected = {(scene, label) for scene in ['bistro', 'minecraft'] for label in ABBA + ['opt-bench-b']}
    if set(receipts) != expected:
        raise ValueError(f'Campaign incomplete: missing={expected - receipts.keys()}')
    summaries = {key: validate(r) for key, r in receipts.items()}
    output = dict(validation='PASS', classification='output-preservation optimization; alpha adoption pending',
                  optimization={}, cleanup_abba={})
    table = []
    for scene in ['bistro', 'minecraft']:
        opt = summaries[(scene, 'opt-bench-b')]
        raw = rows(opt['report'])
        present = CASE17 + '+OPT-PresentHistory'
        combined = CASE17 + '+OPT-NeighborhoodNoDepth+PresentHistory'
        opt['combined_vs_present_history'] = {
            metric: dict(percent=ci([100 * (raw[(combined, run, metric)]['mean'] /
                                           raw[(present, run, metric)]['mean'] - 1) for run in range(6)]),
                         delta_ms=ci([raw[(combined, run, metric)]['mean'] -
                                      raw[(present, run, metric)]['mean'] for run in range(6)]))
            for metric in sorted(METRICS)
        }
        output['optimization'][scene] = opt
        for mode in MODES:
            a = opt['absolute'][mode]
            table.append(dict(scene=scene, build='optimization paired run', mode=mode,
                              **{m + '_ms': a[m]['mean'] for m in sorted(METRICS)},
                              vs_native_percent=0 if mode == NATIVE else opt['paired'][f'{mode} vs {NATIVE}']['SMAA']['percent']['mean'],
                              vs_case17_percent=0 if mode == CASE17 else opt['paired'][f'{mode} vs {CASE17}']['SMAA']['percent']['mean']))
        sequence = []
        for label in ABBA:
            result = summaries[(scene, label)]
            sequence.append(dict(label=label, report=result['report'], receipt=result['receipt'],
                                 case17=result['absolute'][CASE17], native=result['absolute'][NATIVE],
                                 case17_vs_native=result['paired'][f'{CASE17} vs {NATIVE}']))
        before = [r for r in sequence if r['label'].startswith('before')]
        after = [r for r in sequence if r['label'].startswith('after')]
        comparison = {}
        for metric in sorted(METRICS):
            b = [r['case17'][metric]['mean'] for r in before]
            a = [r['case17'][metric]['mean'] for r in after]
            # Each normalized ratio uses only the native control in that process.
            bn = [1 + r['case17_vs_native'][metric]['percent']['mean'] / 100 for r in before]
            an = [1 + r['case17_vs_native'][metric]['percent']['mean'] / 100 for r in after]
            comparison[metric] = dict(before_process_means_ms=b, after_process_means_ms=a,
                                      absolute_change_percent=100 * (statistics.fmean(a) / statistics.fmean(b) - 1),
                                      before_ratios_to_own_native=bn, after_ratios_to_own_native=an,
                                      normalized_change_percent=100 * (statistics.fmean(an) / statistics.fmean(bn) - 1))
        output['cleanup_abba'][scene] = dict(sequence=sequence, comparison=comparison,
            limitation='Two independent processes per build; cross-process absolute differences are descriptive, not same-run causal speed estimates.')
    out = Path(x.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'campaign-performance.json').write_text(json.dumps(output, indent=1) + '\n', encoding='utf-8')
    with (out / 'optimization-performance.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    print('PASS: 10 complete benchmark processes, 6 repeats x 4800 frames per mode')


if __name__ == '__main__':
    main()
