"""Analyze three independent before/after process pairs per scene.

Inputs are clean-run provenance JSON and existing eight-case benchmark CSVs.
Run means (not individual GPU frames) are the independent observations.
"""
import argparse
import json
import math
from pathlib import Path
import statistics

from analyze_eight_case_performance import MODES, parse_results


def summary(values):
    return {'mean': statistics.mean(values), 'stddev': statistics.stdev(values),
            'min': min(values), 'max': max(values)}


def analyze(manifest, root):
    if len(manifest) != 12 or len({r['run'] for r in manifest}) != 12:
        raise ValueError('Expected 12 unique clean runs: 2 scenes x 3 pairs x 2 variants')
    data = {}
    provenance = []
    reference_metadata = None
    expected_hashes = {'before': '2b6090f3ebeea0f2b70ac12cd9e3745820201c0c',
                       'after': '71d151dd56e787665b667e467d94f1a452e24009'}
    executable_hashes = {r['exe'] for r in manifest}
    if len(executable_hashes) != 1:
        raise ValueError('Executable changed within comparison')
    for record in manifest:
        key = (record['scene'], record['pair'], record['v'])
        if key in data or record['shader'] != expected_hashes[record['v']]:
            raise ValueError(f'Duplicate pair or wrong shader: {record}')
        csv_path = root/record['run']/f"{record['run']}_results.csv"
        metadata, timings, fps = parse_results(csv_path)
        required = {'scene': record['scene'], 'warmup_frames': 300,
                    'measurement_frames': 4800, 'repeats': 1,
                    'candidate_readback_disabled': True, 'benchmark_validation_pass': True,
                    'api': 'DirectX11', 'vsync': 'OFF', 'start_time_seconds': 1.0}
        for name, value in required.items():
            if metadata.get(name) != value:
                raise ValueError(f'{csv_path}: {name} expected {value}, got {metadata.get(name)}')
        environment = {name: metadata[name] for name in ('resolution', 'system_info', 'fullscreen')}
        if reference_metadata is not None and environment != reference_metadata:
            raise ValueError('Render environment changed')
        reference_metadata = environment
        if record['window'] != 'visible' or set(timings) != set(MODES):
            raise ValueError('Wrong window state/mode matrix')
        for mode in MODES:
            if not {'SMAA', 'WholeFrame', 'ApplicationFrameWall'} <= timings[mode].keys():
                raise ValueError(f'Missing metrics for {mode}')
            for metric in timings[mode].values():
                if metric['samples'] != 4800 or metric['runs'] != 1:
                    raise ValueError('Incorrect sample count')
                if not math.isfinite(metric['mean_ms']) or metric['mean_ms'] <= 0:
                    raise ValueError('Invalid timing')
        data[key] = timings
        provenance.append({**record, 'metadata': metadata, 'frame_rates': fps})
    results = []
    for scene in ('bistro', 'minecraft'):
        for mode in MODES:
            metric_names = data[(scene, 1, 'before')][mode].keys()
            for pair in (1, 2, 3):
                for variant in ('before', 'after'):
                    if data[(scene, pair, variant)][mode].keys() != metric_names:
                        raise ValueError('Metric set changed')
            for metric in metric_names:
                before = [data[(scene, p, 'before')][mode][metric]['mean_ms'] for p in (1, 2, 3)]
                after = [data[(scene, p, 'after')][mode][metric]['mean_ms'] for p in (1, 2, 3)]
                delta = [b-a for a, b in zip(before, after)]
                percent = [(b/a-1)*100 for a, b in zip(before, after)]
                mean_delta = statistics.mean(delta)
                # t(2), two-sided 95%; descriptive with only three process pairs.
                half_width = 4.30265273*statistics.stdev(delta)/math.sqrt(3)
                results.append({'scene': scene, 'mode': mode, 'metric': metric,
                                'before_ms': summary(before), 'after_ms': summary(after),
                                'pair_deltas_ms': delta, 'pair_percent': percent,
                                'mean_pair_percent': statistics.mean(percent),
                                'delta_ms_ci95': [mean_delta-half_width, mean_delta+half_width]})
    controls = []
    for scene in ('bistro', 'minecraft'):
        for mode in ('O-ET2X', 'O-ET2X-R', 'A-ET2X', 'A-ET2X-R'):
            control = mode.replace('ET2X', 'T2X')
            normalized = []
            for pair in (1, 2, 3):
                before_ratio = (data[(scene, pair, 'before')][mode]['SMAA']['mean_ms'] /
                                data[(scene, pair, 'before')][control]['SMAA']['mean_ms'])
                after_ratio = (data[(scene, pair, 'after')][mode]['SMAA']['mean_ms'] /
                               data[(scene, pair, 'after')][control]['SMAA']['mean_ms'])
                normalized.append((after_ratio/before_ratio-1)*100)
            controls.append({'scene': scene, 'mode': mode, 'control': control,
                             'relative_ratio_change_percent': normalized,
                             'mean_percent': statistics.mean(normalized)})
    return {'status': 'PASS', 'classification': 'paired process performance gate; n=3 per variant per scene',
            'note': '95% intervals are descriptive, unadjusted for multiple metrics; no per-frame pseudoreplication.',
            'runs': provenance, 'metrics': results, 'standard_normalized_diagnostic': controls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--autobench', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = analyze(json.loads(args.manifest.read_text(encoding='utf-8-sig')), args.autobench)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'paired_results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    rows = ['# Luma 재사용 전후 교차 측정', '',
            '변화율은 세 독립 pair의 평균이다. 음수는 변경 후 시간 감소를 뜻한다.', '',
            '|Scene|Mode|Metric|Before ms|After ms|평균 변화 %|pair 변화 %|',
            '|---|---|---|---:|---:|---:|---|']
    for r in result['metrics']:
        if r['metric'] in ('SMAA', 'WholeFrame'):
            rows.append(f"|{r['scene']}|{r['mode']}|{r['metric']}|{r['before_ms']['mean']:.6f}|"
                        f"{r['after_ms']['mean']:.6f}|{r['mean_pair_percent']:+.3f}|"
                        + ', '.join(f'{v:+.3f}' for v in r['pair_percent']) + '|')
    (args.output/'paired_summary.md').write_text('\n'.join(rows)+'\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'runs': len(result['runs']), 'metrics': len(result['metrics'])}))


if __name__ == '__main__':
    main()
