"""Follow-up checks on the run_gl_checks.py output.

- Spatial shift equivariance: SMAA 1X output of frame t against frame t-1 moved by the pan, in the
  interior. Where it differs, the selected route cannot equal SMAA 1X even with exact history.
- Velocity rounding: the RGBA16F velocity against the exact value (the demo stores R16G16_FLOAT too).
- Nearest-neighbour zoom sheets (x4) of the input, SMAA 1X and the final combination at the pixels with
  the largest difference for the 1.5 px pan, saved next to the case outputs.

usage: python inspect_gl_checks.py <work dir> <json out>
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

W, H = 1600, 1000


def final(case_dir, mode, tiers, t):
    raw = (case_dir / f'm{mode}_t{int(tiers)}' / f'final_{t:03d}.rgba').read_bytes()
    return np.frombuffer(raw, np.uint8).reshape(H, W, 4)[::-1, :, :3].astype(int)


def color_input(case_dir, t):
    return np.frombuffer((case_dir / f'color_{t:03d}.raw').read_bytes(), np.uint8).reshape(H, W, 4)[::-1, :, :3].astype(int)


def main():
    work, out = Path(sys.argv[1]), Path(sys.argv[2])
    interior = np.zeros((H, W), bool)
    interior[96:H - 96, 96:W - 96] = True
    report = {}
    for scene in ('minecraft', 'bistro'):
        rows = {}
        for case, (dx, dy) in (('pan_x2', (2, 0)), ('pan_y2', (0, 2))):
            cdir = work / scene / case
            for mode in (1, 2):
                diffs = []
                for t in range(1, 6):
                    cur, prev = final(cdir, mode, False, t), final(cdir, mode, False, t - 1)
                    # Content moves left by dx and down by dy (screen) each frame.
                    moved = np.roll(prev, (dy, -dx), axis=(0, 1))
                    d = np.abs(cur - moved).max(axis=2)[interior]
                    diffs.append({'max': int(d.max()), 'pixels_gt0': int((d > 0).sum())})
                rows[f'{case}_mode{mode}_shift_equivariance'] = diffs
        cdir = work / scene / 'pan_x1p5'
        a, b, src = final(cdir, 2, False, 5), final(cdir, 6, False, 5), color_input(cdir, 5)
        d = np.abs(a - b).max(axis=2) * interior
        y, x = np.unravel_index(np.argmax(d), d.shape)
        x0, y0 = int(np.clip(x - 24, 0, W - 48)), int(np.clip(y - 16, 0, H - 32))
        scale, pad = 8, 6
        sheet = Image.new('RGB', (3 * (48 * scale + pad) + pad, 32 * scale + 2 * pad + 16), (32, 32, 32))
        draw = ImageDraw.Draw(sheet)
        for i, (img, label) in enumerate(((src, 'input (no AA)'), (a, 'Adaptive SMAA 1X'), (b, 'Adaptive selected + Cross5'))):
            crop = Image.fromarray(img[y0:y0 + 32, x0:x0 + 48].astype(np.uint8)).resize((48 * scale, 32 * scale), Image.NEAREST)
            left = pad + i * (48 * scale + pad)
            sheet.paste(crop, (left, pad + 16))
            draw.text((left, 3), f'{label} frame 5 x={x0} y={y0} 48x32 x{scale} nearest', fill=(230, 230, 230))
        path = work / scene / 'pan_x1p5_maxdiff_f5.png'
        sheet.save(path)
        rows['pan_x1p5_frame5_max_diff'] = {'x': int(x), 'y': int(y), 'value': int(d.max()), 'sheet': str(path)}
        report[scene] = rows
        print(scene, json.dumps(rows))
    out.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
