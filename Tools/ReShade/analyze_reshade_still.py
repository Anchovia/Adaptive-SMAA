"""Check the ReShade still screenshots of run_reshade_still.ps1 and make nearest-neighbour zoom sheets.

For every scene and pose:
  - every PNG passes the chunk CRC check
  - the four Before shots (one per preset) are pixel-identical, so all presets saw the same frame
  - Original SMAA changed the frame (After != Before)
  - Adaptive with every tier at the preset maximum equals Original SMAA pixel for pixel
  - Adaptive vs Original: pixels that differ at all and by more than 8/255 in any channel, over the whole
    frame and over the pixels Original SMAA changed
  - tier view: edge pixels per search tier
Zoom sheets (nearest, x6) show the windows with the most Adaptive-vs-Original pixels above 8/255.

usage: python -I analyze_reshade_still.py --run <scene>=<run dir> [...] --sheets <dir> --json <file>
"""
import argparse
import json
import struct
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

STEPS = ('original', 'adaptive', 'tierview', 'tiersatmax')
# The tier view writes (0.2, 0.4, 1.0), (0.2, 1.0, 0.2), (1.0, 0.3, 0.2) through an sRGB render target view.
TIER_COLORS = {'tier0_blue': (124, 170, 255), 'tier1_green': (124, 255, 124), 'tier2_red': (255, 149, 124)}


def png_crc_ok(path):
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return False
    pos = 8
    while pos < len(data):
        length, = struct.unpack('>I', data[pos:pos + 4])
        chunk = data[pos + 4:pos + 8 + length]
        crc, = struct.unpack('>I', data[pos + 8 + length:pos + 12 + length])
        if zlib.crc32(chunk) & 0xffffffff != crc:
            return False
        if chunk[:4] == b'IEND':
            return pos + 12 + length == len(data)
        pos += 12 + length
    return False


def load(path):
    return np.asarray(Image.open(path).convert('RGB'), dtype=np.int16)


def top_windows(mask, size=(96, 64), count=3):
    h, w = mask.shape
    ww, wh = size
    integral = np.pad(mask.astype(np.int64).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    sums = integral[wh:, ww:] - integral[:-wh, ww:] - integral[wh:, :-ww] + integral[:-wh, :-ww]
    picked = []
    sums = sums.astype(np.float64)
    for _ in range(count):
        y, x = np.unravel_index(np.argmax(sums), sums.shape)
        if sums[y, x] <= 0:
            break
        picked.append((int(x), int(y), int(sums[y, x])))
        sums[max(0, y - wh):y + wh, max(0, x - ww):x + ww] = -1
    return picked


def zoom_sheet(images, labels, windows, out, scale=6):
    ww, wh = 96, 64
    pad, label_h = 8, 18
    cols = len(images)
    width = cols * (ww * scale + pad) + pad
    height = len(windows) * (wh * scale + pad + label_h) + pad
    sheet = Image.new('RGB', (width, height), (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    for row, (x, y, n) in enumerate(windows):
        top = pad + row * (wh * scale + pad + label_h)
        for col, (img, label) in enumerate(zip(images, labels)):
            crop = Image.fromarray(img[y:y + wh, x:x + ww].astype(np.uint8)).resize((ww * scale, wh * scale), Image.NEAREST)
            left = pad + col * (ww * scale + pad)
            sheet.paste(crop, (left, top + label_h))
            draw.text((left, top + 3), f'{label}  x={x} y={y} {ww}x{wh}  x{scale} nearest  >8/255: {n}px', fill=(230, 230, 230))
    sheet.save(out)


def max_diff_sheet(before, original, adaptive, diff, out, size=(32, 24), scale=12, gain=3.0):
    """Crop around the largest Adaptive-vs-Original difference: top row as captured, bottom row with the
    brightness multiplied by `gain` (labelled; not a capture)."""
    ww, wh = size
    y, x = np.unravel_index(np.argmax(diff), diff.shape)
    x0 = int(min(max(x - ww // 2, 0), diff.shape[1] - ww))
    y0 = int(min(max(y - wh // 2, 0), diff.shape[0] - wh))
    pad, label_h = 8, 18
    labels = ['Before (no AA)', 'Original SMAA Ultra', 'Adaptive SMAA Ultra']
    width = 3 * (ww * scale + pad) + pad
    height = 2 * (wh * scale + pad + label_h) + pad
    sheet = Image.new('RGB', (width, height), (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    for row, factor in enumerate((1.0, gain)):
        top = pad + row * (wh * scale + pad + label_h)
        for col, (img, label) in enumerate(zip((before, original, adaptive), labels)):
            crop = np.clip(img[y0:y0 + wh, x0:x0 + ww] * factor, 0, 255).astype(np.uint8)
            left = pad + col * (ww * scale + pad)
            sheet.paste(Image.fromarray(crop).resize((ww * scale, wh * scale), Image.NEAREST), (left, top + label_h))
            note = 'as captured' if factor == 1.0 else f'brightness x{gain:g} (adjusted)'
            draw.text((left, top + 3), f'{label}  x={x0} y={y0} {ww}x{wh} x{scale} nearest  {note}', fill=(230, 230, 230))
    sheet.save(out)
    return {'x': x0, 'y': y0, 'width': ww, 'height': wh, 'max_pixel': [int(x), int(y)], 'max_abs_diff': int(diff[y, x])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='append', required=True)
    parser.add_argument('--sheets', type=Path, required=True)
    parser.add_argument('--json', type=Path, required=True)
    args = parser.parse_args()
    args.sheets.mkdir(parents=True, exist_ok=True)
    summary = {'checks': [], 'all_pass': True}
    for item in args.run:
        scene, run_dir = item.split('=', 1)
        shots = Path(run_dir) / 'shots'
        for pose in range(3):
            paths = {(s, k): shots / f'p{pose}_{s}_{k}.png' for s in STEPS for k in ('before', 'after')}
            crc = {f'{s}_{k}': png_crc_ok(p) for (s, k), p in paths.items()}
            img = {key: load(p) for key, p in paths.items()}
            befores = [img[(s, 'before')] for s in STEPS]
            same_before = all(np.array_equal(befores[0], b) for b in befores[1:])
            before, original, adaptive = img[('original', 'before')], img[('original', 'after')], img[('adaptive', 'after')]
            tiers_at_max = img[('tiersatmax', 'after')]
            smaa_changed = np.any(original != before, axis=2)
            diff = np.abs(adaptive - original).max(axis=2)
            any_diff, big_diff = diff > 0, diff > 8
            tier_view = img[('tierview', 'after')]
            tiers = {name: int(np.all(tier_view == np.array(color), axis=2).sum()) for name, color in TIER_COLORS.items()}
            tiers['black'] = int(np.all(tier_view == 0, axis=2).sum())
            pixels = diff.size
            row = {
                'scene': scene, 'pose': pose, 'resolution': [int(before.shape[1]), int(before.shape[0])],
                'png_crc_ok': all(crc.values()), 'before_identical_across_presets': bool(same_before),
                'original_changed_pixels': int(smaa_changed.sum()),
                'original_changed_ratio': float(smaa_changed.mean()),
                'tiers_at_max_equals_original': bool(np.array_equal(tiers_at_max, original)),
                'tiers_at_max_max_abs_diff': int(np.abs(tiers_at_max - original).max()),
                'adaptive_diff_pixels': int(any_diff.sum()), 'adaptive_diff_ratio': float(any_diff.mean()),
                'adaptive_diff_gt8_pixels': int(big_diff.sum()), 'adaptive_diff_gt8_ratio': float(big_diff.mean()),
                'adaptive_diff_ratio_of_smaa_changed': float(any_diff[smaa_changed].mean()) if smaa_changed.any() else None,
                'adaptive_diff_gt8_ratio_of_smaa_changed': float(big_diff[smaa_changed].mean()) if smaa_changed.any() else None,
                'adaptive_diff_outside_smaa_changed': int((any_diff & ~smaa_changed).sum()),
                'adaptive_max_abs_diff': int(diff.max()),
                'tier_view_pixels': tiers, 'tier_view_unclassified': int(pixels - sum(tiers.values())),
            }
            row['pass'] = (row['png_crc_ok'] and row['before_identical_across_presets'] and row['original_changed_pixels'] > 0
                           and row['tiers_at_max_equals_original'] and row['tier_view_unclassified'] == 0)
            summary['all_pass'] &= row['pass']
            windows = top_windows(big_diff)
            row['zoom_windows'] = [{'x': x, 'y': y, 'gt8_pixels': n} for x, y, n in windows]
            if windows:
                amplified = np.clip(np.abs(adaptive - original) * 8, 0, 255)
                sheet = args.sheets / f'{scene}_p{pose}_zoom.png'
                zoom_sheet([before, original, adaptive, amplified, tier_view],
                           ['Before (no AA)', 'Original SMAA Ultra', 'Adaptive SMAA Ultra', '|Adaptive-Original| x8', 'Tier view'],
                           windows, sheet)
                row['zoom_sheet'] = str(sheet)
                row['max_diff_crop'] = max_diff_sheet(before, original, adaptive, diff, args.sheets / f'{scene}_p{pose}_maxdiff.png')
            summary['checks'].append(row)
            print(json.dumps({k: v for k, v in row.items() if k not in ('zoom_windows',)}, ensure_ascii=False))
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('all_pass', summary['all_pass'])


if __name__ == '__main__':
    main()
