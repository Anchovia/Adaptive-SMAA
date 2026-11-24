"""Sheets for the showcase run: the displayed screen with the UI and nearest-neighbour crops of the final colour.

For each saved frame: the AT-Ultra back buffer (with the UI) scaled to half size, and a crop (x4 nearest) of
SMAA 1X and SMAA Adaptive + Temporal around the pixel where they differ most, with the absolute
difference x8 (amplified, labelled).

usage: python showcase_sheets.py --run <showcase capture root> --out <dir>
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

FRAMES = (0, 60, 120, 180, 239)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    run, out = Path(a.run), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in FRAMES:
        screen = Image.open(run / 'AT-Ultra' / f'screen_{f:05d}.png').convert('RGB')
        screen.resize((screen.width // 2, screen.height // 2), Image.LANCZOS).save(out / f'screen_half_{f:05d}.png')
        o = np.asarray(Image.open(run / 'O-1X' / f'frame_{f:05d}.png').convert('RGB')).astype(int)
        t = np.asarray(Image.open(run / 'AT-Ultra' / f'frame_{f:05d}.png').convert('RGB')).astype(int)
        d = np.abs(o - t).max(axis=2)
        y, x = np.unravel_index(np.argmax(d), d.shape)
        w, h, s = 96, 64, 4
        x0, y0 = int(np.clip(x - w // 2, 0, d.shape[1] - w)), int(np.clip(y - h // 2, 0, d.shape[0] - h))
        tiles = [(o, 'SMAA 1X (Ultra)'), (t, 'SMAA Adaptive + Temporal (Ultra)'), (np.clip(np.abs(o - t) * 8, 0, 255), '|difference| x8 (amplified)')]
        sheet = Image.new('RGB', (3 * (w * s + 8) + 8, h * s + 30), (32, 32, 32))
        draw = ImageDraw.Draw(sheet)
        for i, (img, label) in enumerate(tiles):
            crop = Image.fromarray(img[y0:y0 + h, x0:x0 + w].astype(np.uint8)).resize((w * s, h * s), Image.NEAREST)
            left = 8 + i * (w * s + 8)
            sheet.paste(crop, (left, 24))
            draw.text((left, 6), f'{label}  frame {f}  x={x0} y={y0} {w}x{h} x{s} nearest', fill=(230, 230, 230))
        sheet.save(out / f'crop_{f:05d}.png')
        print(f, 'max diff', int(d.max()), 'pixels differing', int((d > 0).sum()))


if __name__ == '__main__':
    main()
