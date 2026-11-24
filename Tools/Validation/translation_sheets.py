"""Sheets and GIFs for one condition of a -translationCapture run.

ROI: the 64x48 window (stride 8) where the temporal-difference error of On minus that of Off is largest (On shimmers
more than Off there), from tde_maps_<condition>.npz of analyze_translation_stability.py, or --roi x,y.
Sheet: --count consecutive motion frames (default 8) with the largest On error inside the ROI; rows Off, On, Fixed08,
Official1Tap, SSRef and the Cross5 weight (grey = weight/0.8 at selected pixels, black = not selected, blue tint =
depth edge), nearest x4. GIF: every saved motion frame, the five colour rows side by side, nearest x3, 8 frames/s
(slow motion; the label gives the frame and its time within the motion).

usage: python translation_sheets.py --run <capture root> --analysis <analysis dir> --cond <condition> --out <dir>
           [--roi x,y] [--count 8] [--stride 1] [--tag name]
--stride s uses every s-th saved frame (fixed300: 5 = frames 1/60 s apart, what a 60 Hz display shows) for the
sheet window and the GIF.
"""
import argparse, json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROWS = ('Off', 'On', 'Fixed08', 'Official1Tap', 'SSRef')
W, H = 64, 48


def load(p):
    return np.asarray(Image.open(p).convert('RGB'))


def weight_tile(wd):
    sel = wd[..., 1] >= 255
    g = np.where(sel, wd[..., 0], 0).astype(np.uint8)
    t = np.stack([g, g, g], -1)
    depth = sel & (wd[..., 2] >= 51)
    t[depth, 2] = np.maximum(t[depth, 2], 160)
    return t


def main():
    ap = argparse.ArgumentParser()
    for k in ('run', 'analysis', 'cond', 'out'):
        ap.add_argument('--' + k, required=True)
    ap.add_argument('--roi')
    ap.add_argument('--count', type=int, default=8)
    ap.add_argument('--tag', default='')
    ap.add_argument('--stride', type=int, default=1)
    a = ap.parse_args()
    run, base, out = Path(a.run), Path(a.run) / a.cond, Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    maps = np.load(Path(a.analysis) / f'tde_maps_{a.cond}.npz')
    if a.roi:
        x0, y0 = map(int, a.roi.split(','))
    else:
        diff = maps['On'] - maps['Off']
        best = (-1e9, 0, 0)
        for y in range(0, diff.shape[0] - H, 8):
            for x in range(0, diff.shape[1] - W, 8):
                v = float(diff[y:y + H, x:x + W].mean())
                if v > best[0]:
                    best = (v, x, y)
        _, x0, y0 = best
    frames = sorted(int(p.stem.split('_')[1]) for p in (base / 'On').glob('frame_*.png') if int(p.stem.split('_')[1]) > 0)
    st = a.stride
    frames = [k for k in frames if (frames[-1] - k) % st == 0]
    crop = lambda img: img[y0:y0 + H, x0:x0 + W]
    tiles = {m: {k: crop(load(base / m / f'frame_{k:05d}.png')) for k in frames} for m in ROWS}
    wtiles = {k: weight_tile(crop(load(base / 'WeightDebug' / f'frame_{k:05d}.png'))) for k in frames}
    dt = {}
    cam = Path(run / 'camera.csv')
    if cam.is_file():
        t = 0.0
        for line in cam.read_text().splitlines()[1:]:
            c, f, d = line.split(',')[:3]
            if c == a.cond:
                t += float(d); dt[int(f)] = t
    # Window of consecutive frames with the largest On error in the ROI.
    err = []
    for k in frames:
        if k - st in tiles['On']:
            d = tiles['On'][k].astype(float) - tiles['On'][k - st] - (tiles['SSRef'][k].astype(float) - tiles['SSRef'][k - st])
            err.append((k, float(np.abs(d).mean())))
    n = a.count
    starts = [err[i][0] for i in range(len(err) - n + 1) if err[i + n - 1][0] - err[i][0] == (n - 1) * st]
    start = max(starts, key=lambda s: sum(e for k, e in err if s <= k < s + n * st)) if starts else frames[0]
    window = [k for k in range(start, start + n * st, st) if k in tiles['On']]
    s = 4
    sheet = Image.new('RGB', (130 + len(window) * (W * s + 6), 26 + (len(ROWS) + 1) * (H * s + 22)), (32, 32, 32))
    dr = ImageDraw.Draw(sheet)
    dr.text((8, 6), f'{run.parent.name}/{run.name} {a.cond}  crop x={x0} y={y0} {W}x{H}, x{s} nearest (original pixels)', fill=(230, 230, 230))
    for r, name in enumerate(ROWS + ('Cross5 weight',)):
        top = 26 + r * (H * s + 22)
        dr.text((8, top + 24), name, fill=(230, 230, 230))
        for c, k in enumerate(window):
            img = wtiles[k] if name == 'Cross5 weight' else tiles[name][k]
            left = 130 + c * (W * s + 6)
            sheet.paste(Image.fromarray(img).resize((W * s, H * s), Image.NEAREST), (left, top + 18))
            dr.text((left, top + 2), f'frame {k}' + (f'  t={dt[k]:.4f}s' if k in dt else ''), fill=(230, 230, 230))
    tag = a.tag or f'{a.cond}_s{st}_x{x0}_y{y0}'
    sheet.save(out / f'sheet_{tag}.png')
    g = 3
    gif = []
    for k in frames:
        im = Image.new('RGB', (len(ROWS) * (W * g + 6) + 6, H * g + 40), (32, 32, 32))
        d2 = ImageDraw.Draw(im)
        for c, name in enumerate(ROWS):
            left = 6 + c * (W * g + 6)
            im.paste(Image.fromarray(tiles[name][k]).resize((W * g, H * g), Image.NEAREST), (left, 34))
            d2.text((left, 20), name, fill=(230, 230, 230))
        d2.text((6, 4), f'{a.cond} frame {k}' + (f' t={dt[k]:.4f}s' if k in dt else '') + f'  x={x0} y={y0} x{g} nearest, slow motion', fill=(230, 230, 230))
        gif.append(im)
    gif[0].save(out / f'compare_{tag}.gif', save_all=True, append_images=gif[1:], duration=125, loop=0)
    info = {'run': str(run), 'cond': a.cond, 'stride': st, 'roi': [x0, y0, W, H], 'window': window, 'gif_frames': frames}
    (out / f'sheet_{tag}.json').write_text(json.dumps(info, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(info))


if __name__ == '__main__':
    main()
