"""Translation stability analysis for one -translationCapture run (one scene and direction).

Layout: <run>/<condition>/<mode>/frame_XXXXX.png, modes Off, On, Fixed08, Official1Tap, WeightDebug, SSRef.
Frame 0 is the last still frame; the saved motion frames are consecutive (fixed60: 1..N; others: the last 0.1 s).

Per condition and colour mode (against SSRef, the demo's SuperSampleReference at the same pose):
  ref_mae   mean |out - ref| over RGB bytes (spatial error at the pose)
  tde       mean |(out_k - out_k-1) - (ref_k - ref_k-1)| over consecutive motion frames: change between frames
            that the reference does not have (shimmer, crawl, popping); the scene motion cancels to the extent the
            output follows the reference
  change    mean |out_k - out_k-1| (not motion compensated)
Masks from WeightDebug frame k: selected (G = 255), depth edge (selected and B >= 51, a relative view-depth jump of at
least 10% to a 4-neighbour), texture edge (selected, smaller jump). Weight statistics: share of selected pixels with
Cross5 weight below 0.4 (R < 128) and below 0.1 (R < 32), split by mask, and selection churn (share of the selected
pixels of frame k that were not selected in frame k-1, not motion compensated). Neither tde nor ref_mae is a ground
truth; SSRef is a spatial supersample reference.

usage: python analyze_translation_stability.py --run <capture root> --out <dir>
"""
import argparse, json
from pathlib import Path

import numpy as np
from PIL import Image

COLOUR = ('Off', 'On', 'Fixed08', 'Official1Tap')
CONDS = ('fixed60', 'fixed300', 'fixedmean', 'recorded')
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), np.float32)


def frames_of(d):
    return sorted(int(p.stem.split('_')[1]) for p in d.glob('frame_*.png'))


def masks(wd):
    sel = wd[..., 1] >= 254.5
    depth = sel & (wd[..., 2] >= 50.5)
    return {'all': np.ones(sel.shape, bool), 'selected': sel, 'depth_edge': depth, 'texture_edge': sel & ~depth}


def mmean(a, m):
    return float(a[m].mean()) if m.any() else float('nan')


def analyze_condition(run, cond, out):
    base = run / cond
    idx = frames_of(base / 'SSRef')
    for m in COLOUR + ('WeightDebug',):
        assert frames_of(base / m) == idx, (cond, m)
    motion = [k for k in idx if k > 0]
    pairs = [(a, b) for a, b in zip(idx, idx[1:]) if b == a + 1 and a > 0]
    acc = {m: {k: {'ref_mae': [], 'tde': [], 'change': []} for k in ('all', 'selected', 'depth_edge', 'texture_edge')} for m in COLOUR}
    wstat = {k: {'n': 0, 'lt04': 0, 'lt01': 0, 'wsum': 0.0} for k in ('selected', 'depth_edge', 'texture_edge')}
    churn = []
    tde_map = {m: None for m in COLOUR}
    per_frame = []
    prev = None
    for k in motion:
        cur = {m: load(base / m / f'frame_{k:05d}.png') for m in COLOUR + ('SSRef',)}
        wd = load(base / 'WeightDebug' / f'frame_{k:05d}.png')
        mk = masks(wd)
        row = {'frame': k, 'selected_share': float(mk['selected'].mean())}
        r = wd[..., 0] / 255.0
        for key in wstat:
            sel = mk[key]
            wstat[key]['n'] += int(sel.sum()); wstat[key]['lt04'] += int((sel & (wd[..., 0] < 127.5)).sum())
            wstat[key]['lt01'] += int((sel & (wd[..., 0] < 31.5)).sum()); wstat[key]['wsum'] += float((r[sel] * 0.8).sum())
        for m in COLOUR:
            err = np.abs(cur[m] - cur['SSRef']).mean(axis=2)
            for key, msk in mk.items():
                acc[m][key]['ref_mae'].append(mmean(err, msk))
        if prev is not None and (prev['k'], k) in pairs:
            dref = cur['SSRef'] - prev['SSRef']
            sel_prev = prev['sel']
            churn.append(float((mk['selected'] & ~sel_prev).sum() / max(1, mk['selected'].sum())))
            for m in COLOUR:
                d = cur[m] - prev[m]
                tde = np.abs(d - dref).mean(axis=2)
                chg = np.abs(d).mean(axis=2)
                for key, msk in mk.items():
                    acc[m][key]['tde'].append(mmean(tde, msk)); acc[m][key]['change'].append(mmean(chg, msk))
                tl = np.abs((d - dref) @ LUMA)
                tde_map[m] = tl if tde_map[m] is None else tde_map[m] + tl
                row[f'tde_{m}'] = float(tde.mean())
        per_frame.append(row)
        prev = dict(cur, k=k, sel=mk['selected'])
    res = {'frames': len(motion), 'pairs': len(pairs), 'modes': {}, 'weights': {}, 'churn_mean': float(np.mean(churn)) if churn else None}
    for m in COLOUR:
        res['modes'][m] = {key: {s: float(np.nanmean(v)) if v else None for s, v in d.items()} for key, d in acc[m].items()}
    for key, s in wstat.items():
        res['weights'][key] = {'pixels': s['n'], 'share_w_lt_0_4': s['lt04'] / max(1, s['n']), 'share_w_lt_0_1': s['lt01'] / max(1, s['n']),
                               'mean_weight': s['wsum'] / max(1, s['n'])}
    np.savez_compressed(out / f'tde_maps_{cond}.npz', **{m: tde_map[m] / max(1, len(pairs)) for m in COLOUR if tde_map[m] is not None})
    res['per_frame'] = per_frame
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    run, out = Path(a.run), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {'run': str(run)}
    for cond in CONDS:
        if (run / cond).is_dir():
            summary[cond] = analyze_condition(run, cond, out)
            r = summary[cond]
            print(f"== {cond}: {r['frames']} motion frames, {r['pairs']} pairs, churn {r['churn_mean']}")
            for m in COLOUR:
                d = r['modes'][m]
                print(f"  {m:13s} ref_mae all {d['all']['ref_mae']:.3f} sel {d['selected']['ref_mae']:.3f} | tde all {d['all']['tde']:.4f} "
                      f"sel {d['selected']['tde']:.3f} depth {d['depth_edge']['tde']:.3f} tex {d['texture_edge']['tde']:.3f}")
            for key, w in r['weights'].items():
                print(f"  weights {key:12s} px {w['pixels']:9d} w<0.4 {w['share_w_lt_0_4']:.3f} w<0.1 {w['share_w_lt_0_1']:.3f} mean {w['mean_weight']:.3f}")
    (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
