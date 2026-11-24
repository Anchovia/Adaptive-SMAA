"""Edge strength of each mode relative to SSRef in a -translationCapture run.

Edge strength = mean Sobel gradient magnitude of luma. Reported for the last still frame (frame 0) and for the saved
motion frames, over the whole frame and over the selected pixels of WeightDebug at the same frame. A ratio below 1
means the output is softer than the supersample reference at those pixels. Not a ground truth.

usage: python translation_sharpness.py --run <capture root> [--run ...] --out <json>
"""
import argparse, json
from pathlib import Path

import cv2
import numpy as np

MODES = ('Off', 'On', 'Fixed08', 'Official1Tap', 'SSRef')


def grad(p):
    g = cv2.cvtColor(cv2.imread(str(p), cv2.IMREAD_COLOR), cv2.COLOR_BGR2GRAY).astype(np.float32)
    return np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='append', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = {}
    for r in map(Path, a.run):
        name = f'{r.parent.name}/{r.name}'
        out[name] = {}
        for cond in ('fixed60', 'fixed300', 'fixedmean', 'recorded'):
            base = r / cond
            if not base.is_dir():
                continue
            modes = [m for m in MODES if (base / m).is_dir()]
            frames = sorted(int(p.stem.split('_')[1]) for p in (base / 'SSRef').glob('frame_*.png'))
            sums = {ph: {m: {'all': 0.0, 'sel': 0.0} for m in modes} for ph in ('still', 'motion')}
            for k in frames:
                ph = 'still' if k == 0 else 'motion'
                wd = cv2.imread(str(base / 'WeightDebug' / f'frame_{k:05d}.png'), cv2.IMREAD_COLOR)
                sel = wd[..., 1] >= 255 if wd is not None else None
                for m in modes:
                    g = grad(base / m / f'frame_{k:05d}.png')
                    sums[ph][m]['all'] += float(g.mean())
                    if sel is not None and sel.any():
                        sums[ph][m]['sel'] += float(g[sel].mean())
            res = {}
            for ph, d in sums.items():
                ref = d['SSRef']
                res[ph] = {m: {k: (v / ref[k] if ref[k] else None) for k, v in d[m].items()} for m in modes if m != 'SSRef'}
            out[name][cond] = res
            line = '  '.join(f"{m} {res['motion'][m]['sel']:.3f}" for m in modes if m != 'SSRef' and res['motion'][m]['sel'])
            still = '  '.join(f"{m} {res['still'][m]['sel']:.3f}" for m in modes if m != 'SSRef' and res['still'][m]['sel'])
            print(f'{name} {cond}: motion sel/ref {line} | still sel/ref {still}')
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
