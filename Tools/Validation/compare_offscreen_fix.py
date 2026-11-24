"""Compares On with the off-screen history fix (onoff run) against the earlier full run of the same path.

The old run (validation/improved-smaa-demo-translation-stability) has Off, On (without the fix), SSRef and WeightDebug;
the new run has Off and On with the fix. Off must be byte-identical between the two runs (same camera path and inputs),
and so must On at frame 0 (still camera, velocity 0). For each condition: how many On frames and pixels changed and
how many of the changed pixels lie in the 32-pixel border band, and the 1/60 s temporal-difference error tde60 (see
analyze_translation_stability.py) of Off, old On and new On over all pixels, the border band, the interior and the
selected pixels of the old WeightDebug (the selection does not change with the fix).

usage: python compare_offscreen_fix.py --old <old run root> --new <new run root> --out <json>
"""
import argparse, hashlib, json
from pathlib import Path

import numpy as np
from PIL import Image

CONDS = ('fixed60', 'fixed300', 'fixedmean', 'recorded')


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), np.float32)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    for k in ('old', 'new', 'out'):
        ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    old, new = Path(a.old), Path(a.new)
    out = {'old': str(old), 'new': str(new)}
    for cond in CONDS:
        ob, nb = old / cond, new / cond
        if not nb.is_dir():
            continue
        frames = sorted(int(p.stem.split('_')[1]) for p in (nb / 'On').glob('frame_*.png'))
        off_same = all(sha(ob / 'Off' / f'frame_{k:05d}.png') == sha(nb / 'Off' / f'frame_{k:05d}.png') for k in frames)
        still_same = sha(ob / 'On' / 'frame_00000.png') == sha(nb / 'On' / 'frame_00000.png')
        dts = [float(l.split(',')[2]) for l in (new / 'camera.csv').read_text().splitlines()[1:] if l.split(',')[0] == cond]
        lag = max(1, int(round((1.0 / 60.0) / float(np.mean(dts)))))
        h, w = load(nb / 'On' / f'frame_{frames[0]:05d}.png').shape[:2]
        band = np.zeros((h, w), bool); band[:32] = band[-32:] = True; band[:, :32] = band[:, -32:] = True
        changed_frames, changed_px, changed_band = 0, 0, 0
        acc = {m: {r: [] for r in ('all', 'border32', 'interior', 'selected')} for m in ('Off', 'On_old', 'On_new')}
        cache = {}
        for k in frames:
            if k == 0:
                continue
            cur = {'Off': load(ob / 'Off' / f'frame_{k:05d}.png'), 'On_old': load(ob / 'On' / f'frame_{k:05d}.png'),
                   'On_new': load(nb / 'On' / f'frame_{k:05d}.png'), 'SSRef': load(ob / 'SSRef' / f'frame_{k:05d}.png')}
            d = np.abs(cur['On_new'] - cur['On_old']).max(axis=2) > 0
            if d.any():
                changed_frames += 1; changed_px += int(d.sum()); changed_band += int((d & band).sum())
            sel = np.asarray(Image.open(ob / 'WeightDebug' / f'frame_{k:05d}.png').convert('RGB'))[..., 1] >= 255
            regions = {'all': np.ones((h, w), bool), 'border32': band, 'interior': ~band, 'selected': sel}
            if k - lag in cache:
                prev = cache[k - lag]
                dref = cur['SSRef'] - prev['SSRef']
                for m in ('Off', 'On_old', 'On_new'):
                    t = np.abs(cur[m] - prev[m] - dref).mean(axis=2)
                    for r, msk in regions.items():
                        if msk.any():
                            acc[m][r].append(float(t[msk].mean()))
            cache[k] = {m: cur[m] for m in ('Off', 'On_old', 'On_new', 'SSRef')}
            cache.pop(k - lag - 1, None)
        res = {'frames': len(frames), 'lag_60hz': lag, 'off_identical': off_same, 'still_on_identical': still_same,
               'on_frames_changed': changed_frames, 'on_pixels_changed': changed_px,
               'changed_share_in_border32': changed_band / changed_px if changed_px else None,
               'tde60': {m: {r: float(np.mean(v)) if v else None for r, v in d2.items()} for m, d2 in acc.items()}}
        out[cond] = res
        t = res['tde60']
        print(f"{cond}: Off identical {off_same}, still On identical {still_same}, On frames changed {changed_frames}/{len(frames) - 1}, "
              f"pixels {changed_px} ({100 * (res['changed_share_in_border32'] or 0):.0f}% in border)")
        for r in ('all', 'border32', 'interior', 'selected'):
            print(f"   tde60 {r:9s} Off {t['Off'][r]:.4f}  On old {t['On_old'][r]:.4f}  On new {t['On_new'][r]:.4f}  "
                  f"new/old {100 * (t['On_new'][r] / t['On_old'][r] - 1):+.2f}%  new/Off {100 * (t['On_new'][r] / t['Off'][r] - 1):+.2f}%")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
