"""Sheets for the AT-Toggle capture: six frames around each switch (Off at 90, On at 150), nearest x4 crops.

The crop sits where AT-Ultra (Temporal On) and ATOff-Ultra (Off) differ most at frame 120 (camera moving).
Rows: AT-Toggle, ATOff-Ultra, AT-Ultra; columns: the frames. A second sheet shows the whole AT-Toggle frame at
half size for frames 89, 90, 149, 150 and 151.

usage: python toggle_sheets.py --run <capture root of one scene> --out <dir>
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

WINDOWS = {'off_at_90': range(87, 93), 'on_at_150': range(148, 154)}
ROWS = ('AT-Toggle', 'ATOff-Ultra', 'AT-Ultra')


def load(run, mode, f):
    return np.asarray(Image.open(run / mode / f'frame_{f:05d}.png').convert('RGB'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    run, out = Path(a.run), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    d = np.abs(load(run, 'AT-Ultra', 120).astype(int) - load(run, 'ATOff-Ultra', 120).astype(int)).max(axis=2)
    y, x = np.unravel_index(np.argmax(d), d.shape)
    w, h, s = 64, 48, 4
    x0, y0 = int(np.clip(x - w // 2, 0, d.shape[1] - w)), int(np.clip(y - h // 2, 0, d.shape[0] - h))
    for name, frames in WINDOWS.items():
        sheet = Image.new('RGB', (110 + len(frames) * (w * s + 6), 24 + len(ROWS) * (h * s + 22)), (32, 32, 32))
        draw = ImageDraw.Draw(sheet)
        draw.text((8, 6), f'{run.name}  crop x={x0} y={y0} {w}x{h}, x{s} nearest', fill=(230, 230, 230))
        for r, mode in enumerate(ROWS):
            top = 24 + r * (h * s + 22)
            draw.text((8, top + 20), mode, fill=(230, 230, 230))
            for c, f in enumerate(frames):
                left = 110 + c * (w * s + 6)
                crop = Image.fromarray(load(run, mode, f)[y0:y0 + h, x0:x0 + w]).resize((w * s, h * s), Image.NEAREST)
                sheet.paste(crop, (left, top + 18))
                draw.text((left, top + 2), f'frame {f}', fill=(230, 230, 230))
        sheet.save(out / f'{name}.png')
    full = [89, 90, 149, 150, 151]
    tiles = [Image.fromarray(load(run, 'AT-Toggle', f)).resize((960, 530), Image.LANCZOS) for f in full]
    sheet = Image.new('RGB', (3 * 966, 2 * 556), (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    for i, (f, t) in enumerate(zip(full, tiles)):
        left, top = (i % 3) * 966, (i // 3) * 556
        sheet.paste(t, (left, top + 22))
        draw.text((left + 6, top + 4), f'AT-Toggle frame {f} (half size)', fill=(230, 230, 230))
    sheet.save(out / 'toggle_full_frames.png')
    print('crop', x0, y0, 'max diff at 120', int(d.max()))


if __name__ == '__main__':
    main()
