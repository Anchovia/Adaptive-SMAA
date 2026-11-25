"""Sheets of SMAA T2x-R next to SMAA 1X and SMAA Adaptive + Temporal (nearest x4, original pixels).

The crop sits where T2x-R and Adaptive + Temporal differ most at --at (default 120, camera moving). Two sheets: six
consecutive moving frames (117..122) and six still frames (200..205); rows O-1X, T2x-R, Adaptive + Temporal. A third
image shows the whole T2x-R frame at frames 120 and 210 at half size.

usage: python t2xr_sheets.py --t2xr <T2xR-Ultra dir> --o1x <O-1X dir> --at <AT-Ultra dir> --out <dir> --tag <name> [--roi x,y]
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

W, H, S = 64, 48, 4


def load(d, k):
    return np.asarray(Image.open(Path(d) / f'frame_{k:05d}.png').convert('RGB'))


def main():
    ap = argparse.ArgumentParser()
    for k in ('t2xr', 'o1x', 'at', 'out', 'tag'):
        ap.add_argument('--' + k, required=True)
    ap.add_argument('--roi')
    ap.add_argument('--frame', type=int, default=120)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows = (('SMAA 1X', a.o1x), ('SMAA T2x-R', a.t2xr), ('SMAA Adaptive + Temporal', a.at))
    if a.roi:
        x0, y0 = map(int, a.roi.split(','))
    else:
        d = np.abs(load(a.t2xr, a.frame).astype(int) - load(a.at, a.frame).astype(int)).max(axis=2).astype(float)
        best = (-1, 0, 0)
        for y in range(0, d.shape[0] - H, 8):
            for x in range(0, d.shape[1] - W, 8):
                v = d[y:y + H, x:x + W].mean()
                if v > best[0]:
                    best = (v, x, y)
        _, x0, y0 = best
    for name, frames in (('moving', range(117, 123)), ('still', range(200, 206))):
        sheet = Image.new('RGB', (190 + len(frames) * (W * S + 6), 26 + len(rows) * (H * S + 22)), (32, 32, 32))
        dr = ImageDraw.Draw(sheet)
        dr.text((8, 6), f'{a.tag} {name} frames, crop x={x0} y={y0} {W}x{H}, x{S} nearest (original pixels)', fill=(230, 230, 230))
        for r, (label, d) in enumerate(rows):
            top = 26 + r * (H * S + 22)
            dr.text((8, top + 24), label, fill=(230, 230, 230))
            for c, k in enumerate(frames):
                left = 190 + c * (W * S + 6)
                sheet.paste(Image.fromarray(load(d, k)[y0:y0 + H, x0:x0 + W]).resize((W * S, H * S), Image.NEAREST), (left, top + 18))
                dr.text((left, top + 2), f'frame {k}', fill=(230, 230, 230))
        sheet.save(out / f'{a.tag}_{name}_x{x0}_y{y0}.png')
    full = Image.new('RGB', (2 * 966, 556), (32, 32, 32))
    dr = ImageDraw.Draw(full)
    for i, k in enumerate((120, 210)):
        full.paste(Image.fromarray(load(a.t2xr, k)).resize((960, 530), Image.LANCZOS), (i * 966, 22))
        dr.text((i * 966 + 6, 4), f'{a.tag} SMAA T2x-R frame {k} (half size)', fill=(230, 230, 230))
    full.save(out / f'{a.tag}_t2xr_full.png')
    print('roi', x0, y0)


if __name__ == '__main__':
    main()
