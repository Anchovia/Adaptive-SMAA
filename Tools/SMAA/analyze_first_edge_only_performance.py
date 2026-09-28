"""Validate within-run first-edge-only GPU scope measurements; no FPS claim."""
import argparse
import csv
import json
import math
import statistics as st

from analyze_first_edge_only import D, FULL, DETECT, SEL, receipt

MODES = [FULL, DETECT, SEL]
BASE_METRICS = ['SMAA', 'FE_CameraVelocity', 'FE_Prepare', 'FE_Resolve']


def analyze(scene, phase):
    rc, path, text = receipt(scene, phase)
    assert '1920 x 1061' in text and 'NVIDIA GeForce RTX 3060 Ti' in text
    repeats, samples = (1, 240) if phase == 'Smoke' else (4, 4800)
    rows = []
    for raw in csv.reader(text.splitlines()):
        raw = [x.strip() for x in raw]
        if not raw or raw[0] != 'timing':
            continue
        mode, repeat, metric, count = raw[1], int(raw[2]), raw[3], int(raw[4])
        vals = list(map(float, raw[5:10]))
        assert len(vals) == 5 and all(math.isfinite(v) and v >= 0 for v in vals)
        assert vals[0] > 0 and vals[2] >= vals[1] >= vals[3]
        assert count == samples
        rows.append(dict(mode=mode, repeat=repeat, metric=metric, samples=count,
                         mean_ms=vals[0], p95_ms=vals[1], p99_ms=vals[2], median_ms=vals[3], std_ms=vals[4]))
    assert len(rows) == 14 * repeats
    expected = [(m, r, k) for r in range(repeats) for m in (MODES if r % 2 == 0 else MODES[::-1])
                for k in sorted(BASE_METRICS + ([] if m == FULL else ['FE_EdgeDetection']))]
    assert [(r['mode'], r['repeat'], r['metric']) for r in rows] == expected
    table = {}
    for m in MODES:
        table[m] = {}
        for k in BASE_METRICS + ([] if m == FULL else ['FE_EdgeDetection']):
            rr = [r for r in rows if r['mode'] == m and r['metric'] == k]
            means = [r['mean_ms'] for r in rr]
            table[m][k] = dict(mean_ms=st.mean(means), run_means_ms=means,
                               run_mean_std_ms=st.stdev(means) if repeats > 1 else None,
                               mean_run_median_ms=st.mean(r['median_ms'] for r in rr),
                               mean_run_p95_ms=st.mean(r['p95_ms'] for r in rr),
                               mean_run_p99_ms=st.mean(r['p99_ms'] for r in rr))
    contrasts = {}
    for label, test, control in [('detect_minus_full', DETECT, FULL),
                                 ('selective_minus_detect', SEL, DETECT),
                                 ('selective_minus_full', SEL, FULL)]:
        contrasts[label] = {}
        for k in BASE_METRICS:
            t, c = table[test][k], table[control][k]
            ds = [a-b for a,b in zip(t['run_means_ms'], c['run_means_ms'])]
            ps = [(a/b-1)*100 for a,b in zip(t['run_means_ms'], c['run_means_ms'])]
            contrasts[label][k] = dict(delta_ms=t['mean_ms']-c['mean_ms'],
                                      percent=(t['mean_ms']/c['mean_ms']-1)*100,
                                      paired_run_delta_ms=ds, paired_run_percent=ps,
                                      paired_delta_std_ms=st.stdev(ds) if repeats > 1 else None)
    out = dict(validation='PASS', scene=scene, phase=phase, receipt=rc, repeats=repeats,
               frames_per_repeat=samples, metrics=table, contrasts=contrasts,
               note='Hidden-window engineering scope timing; no image/mask snapshots or readback. GPU timestamp queries included. '
                    'Not WholeFrame/FPS, not a matched-quality speedup, not formal six-case performance. '
                    'Selective-minus-detect combines edge Load, branch, skipped sampling, and GPU scheduling effects.')
    (D/f'{scene}-{phase.lower()}-performance.json').write_text(json.dumps(out, indent=2)+'\n', encoding='utf-8')
    with (D/f'{scene}-{phase.lower()}-timings.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
    print(json.dumps(dict(validation='PASS', scene=scene, phase=phase,
                         scope_means_ms={m:{k:v['mean_ms'] for k,v in d.items()} for m,d in table.items()},
                         contrasts=contrasts), indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', required=True, choices=['bistro', 'minecraft'])
    ap.add_argument('--phase', required=True, choices=['Smoke', 'Benchmark'])
    args = ap.parse_args()
    analyze(args.scene, args.phase)
