"""Validate all 16 source/document CGVQM runs and preserve official scores.

The reference is a supersampled spatial proxy, not temporal ground truth.
No score is recomputed from error maps or adjusted for clip-boundary padding.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from analyze_recovered_source_comparison import IDS

COMMIT = '8302ff45b4ff5a691682baf23f7c007d6b591e98'
WINDOWS = {'central': (150, 329), 'transition': (410, 439)}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate(root, comparison):
    jobs = read(root / 'jobs.json')
    expected = {(s, p, w) for s in ('bistro', 'minecraft')
                for p in range(4) for w in WINDOWS}
    keys = [(j['scene'], j['profile'], j['window']) for j in jobs]
    assert len(keys) == len(set(keys)) == 16 and set(keys) == expected
    rows, reference_hashes, runtimes = [], {}, []
    for job in jobs:
        scene, profile, window = job['scene'], job['profile'], job['window']
        quality = comparison['quality'][scene]
        assert quality['spatial_control_pixel_hash_mismatch'] == 0
        path = Path(job['result'])
        data = read(path)
        start, end = WINDOWS[window]
        count = end - start + 1
        assert data['classification'] == 'formal'
        assert data['official_cgvqm']['commit'] == COMMIT
        assert data['provenance'] == dict(scene=scene,
            camera_profile='flythrough-wide-yaw-360', test_mode=IDS[profile],
            reference_id='SS-Reference')
        assert data['configuration'] == dict(fps=60, patch_scale=4,
            patch_pool='mean', models=['2'], reference_index_offset=0)
        runtime = data['runtime']
        assert runtime['device'] == 'cuda' and runtime['cuda_available']
        runtimes.append(runtime)
        for side in ('test', 'reference'):
            sequence = data[f'{side}_sequence']
            assert (sequence['frame_count'], sequence['first_index'], sequence['last_index'],
                    sequence['width'], sequence['height']) == (count, start, end, 1920, 1017)
            assert len(sequence['pixel_sha256']) == 64
            roundtrip = data[f'{side}_round_trip']
            assert roundtrip['codec'] == 'ffv1' and roundtrip['pixel_format'] == 'bgr0'
            assert roundtrip['decoded_frames'] == count
            assert roundtrip['mismatched_values'] == roundtrip['max_absolute_difference'] == 0
        test_parent = Path(quality['runs'][f'{scene}-profile-{profile}']['report']).resolve()
        assert Path(data['test_sequence']['directory']).resolve().parent == test_parent
        ref_parent = Path(quality['reference']).resolve() / 'SS_Reference'
        assert Path(data['reference_sequence']['directory']).resolve() == ref_parent
        ref_hash = data['reference_sequence']['pixel_sha256']
        assert reference_hashes.setdefault((scene, window), ref_hash) == ref_hash
        metric = data['results']['CGVQM-2']
        score = metric['score_higher_is_better']
        assert math.isfinite(score)
        with Path(metric['per_frame_csv']).open(encoding='utf-8-sig', newline='') as f:
            frame_rows = list(csv.DictReader(f))
        assert [int(r['frame_index']) for r in frame_rows] == list(range(start, end + 1))
        assert all(math.isfinite(float(r[k])) for r in frame_rows
                   for k in ('mean', 'p95', 'p99', 'maximum'))
        rows.append(dict(scene=scene, mode=IDS[profile], window=window,
            first_index=start, last_index=end, frames=count, cgvqm2=score,
            test_pixel_sha256=data['test_sequence']['pixel_sha256'],
            reference_pixel_sha256=ref_hash, result=str(path),
            result_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    assert all(r == runtimes[0] for r in runtimes)
    for row in rows:
        baseline = next(r['cgvqm2'] for r in rows if r['scene'] == row['scene']
                        and r['window'] == row['window'] and r['mode'] == IDS[0])
        row['delta_from_document'] = row['cgvqm2'] - baseline
    return dict(validation='PASS', official_commit=COMMIT, runtime=runtimes[0],
        metric_scope='Official CGVQM-2 score, higher is better; spatial-reference proxy, not absolute ghosting truth',
        round_trip_mismatched_values=0, reference_hash_groups=len(reference_hashes),
        runs=rows)


def plot(summary, performance, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    labels = ['Doc / Doc', 'Source / Doc', 'Doc / Source', 'Source / Source']
    colors = ['#526878', '#14867b', '#cb8a23', '#ba5050']
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.2))
    fig.subplots_adjust(left=0.075, right=0.99, bottom=0.15, top=0.86,
                        hspace=0.32, wspace=0.25)
    deltas = [r['delta_from_document'] for r in summary['runs']]
    quality_limits = (min(0, min(deltas))*1.08, max(0.5, max(deltas)*1.5))
    for column, scene in enumerate(('bistro', 'minecraft')):
        ax = axes[0, column]
        for i, mode in enumerate(IDS):
            delta = [next(r['delta_from_document'] for r in summary['runs']
                     if r['scene'] == scene and r['mode'] == mode and r['window'] == w)
                     for w in WINDOWS]
            ax.bar(np.arange(2) + (i-1.5)*0.19, delta, 0.18, color=colors[i], label=labels[i])
        ax.axhline(0, color='#34404a', linewidth=0.8)
        ax.set_ylim(*quality_limits)
        ax.set_xticks([0, 1], ['Central motion', 'Motion to still'])
        ax.set_title(scene.capitalize())
        ax.set_ylabel('CGVQM-2 change vs Doc / Doc\nHigher is better')
        ax.grid(axis='y', alpha=0.15)
        ax = axes[1, column]
        metrics = performance['performance'][f'{scene}-paired-benchmark']['metrics']
        values = [metrics[m]['SMAA']['mean_ms'] for m in IDS]
        errors = [metrics[m]['SMAA']['run_mean_stddev_ms'] for m in IDS]
        ax.bar(range(4), values, color=colors, yerr=errors, capsize=3)
        for i, v in enumerate(values):
            ax.text(i, v+0.012, f'{v:.3f}', ha='center', fontsize=9)
        ax.set_ylim(0, 0.61)
        ax.set_xticks(range(4), labels, rotation=12)
        ax.set_ylabel('SMAA GPU time (ms)\nLower is better')
        ax.grid(axis='y', alpha=0.15)
    handles, legend_labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc='upper center', bbox_to_anchor=(0.5, 0.95),
               ncol=4, frameon=False)
    fig.suptitle('Recovered-source SMAA adaptation: candidate / temporal kernel', fontsize=14, y=0.99)
    fig.supxlabel('Quality: wide camera path, supersampled spatial proxy. Timing: separate flythrough, 3 runs.\n'
        'Error bars: run-mean SD. Source candidate includes an extra compute pass; not Intel sample timing.', fontsize=9)
    fig.savefig(destination, dpi=170)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cgvqm-root', type=Path, required=True)
    parser.add_argument('--comparison', type=Path, required=True)
    parser.add_argument('--performance', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    summary = validate(args.cgvqm_root, read(args.comparison))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'cgvqm-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    rows = summary['runs']
    with (args.output / 'cgvqm-scores.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if args.performance:
        plot(summary, read(args.performance), args.output / 'quality-performance.png')
    for scene in ('bistro', 'minecraft'):
        for window in WINDOWS:
            values = [next(r['cgvqm2'] for r in rows if r['scene'] == scene
                      and r['window'] == window and r['mode'] == mode) for mode in IDS]
            print(scene, window, ' / '.join(f'{v:.6f}' for v in values))
    print(f'PASS: {len(rows)} formal results, 32 lossless round trips, 4 shared reference hashes')


if __name__ == '__main__':
    main()
