"""Visualize six final RGB outputs with the same fixed Sobel contour display.

These are offline output contours, NOT SMAA first-pass or temporal selection masks.
No renderer, algorithm, capture, benchmark, or source image is changed.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from create_six_case_stencil_media import (
    ROOT, DOC, CLIPS, LABELS, FONT, BOLD, SMALL, TW, TH, LH, TOP, FOOT,
    sources, sha, dump,
)
from create_stencil_edge_media import write_gif


CLIP_IDS = ('bistro-chairs-moving', 'minecraft-thin-edges-moving', 'bistro-window-stop')


def contours(rgb, roi):
    """Sobel on display RGB luma, one-pixel halo, fixed 4x display gain."""
    x0, y0, x1, y1 = roi
    assert x0 > 0 and y0 > 0 and x1 < rgb.width and y1 < rgb.height
    a = np.asarray(rgb.crop((x0-1, y0-1, x1+1, y1+1)), dtype=np.float64)
    y = a @ np.array([0.2126, 0.7152, 0.0722])
    gx = (y[:-2, 2:] + 2*y[1:-1, 2:] + y[2:, 2:]
          - y[:-2, :-2] - 2*y[1:-1, :-2] - y[2:, :-2]) / 4
    gy = (y[2:, :-2] + 2*y[2:, 1:-1] + y[2:, 2:]
          - y[:-2, :-2] - 2*y[:-2, 1:-1] - y[:-2, 2:]) / 4
    strength = np.hypot(gx, gy)
    values = np.rint(np.clip(strength * 4, 0, 255)).astype(np.uint8)
    return Image.fromarray(values), int((strength * 4 > 255).sum())


def render(row, clip, f, single=None):
    size = (TW*2, TOP+(TH+LH)*3+FOOT) if single is None else (TW, TOP+TH+LH+FOOT)
    out = Image.new('L', size, 0)
    d = ImageDraw.Draw(out)
    d.text((12, 6), clip['title']+' · 출력 윤곽', font=BOLD, fill=255)
    phase = '정지' if f >= 180 else '이동'
    d.text((12, 44), f"2배 확대 · {clip['fps']/60:g}배속 · frame {f:03d} · {phase}", font=FONT, fill=220)
    indices = range(6) if single is None else [single-1]
    for i in indices:
        x = (i % 2)*TW if single is None else 0
        y = TOP+(i//2)*(TH+LH) if single is None else TOP
        d.text((x+12, y+6), LABELS[i], font=FONT, fill=255)
        out.paste(row[i].resize((TW, TH), Image.Resampling.NEAREST), (x, y+LH))
    d.text((12, size[1]-26), '동일 Sobel · 표시 강도 4배 · 내부 선택 마스크 아님', font=SMALL, fill=220)
    return out.convert('RGB')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = json.loads((DOC/'summary.json').read_text(encoding='utf-8'))
    color = json.loads((DOC/'media.json').read_text(encoding='utf-8'))
    assert summary['validation'] == color['validation'] == 'PASS'
    records = []
    for clip in (c for c in CLIPS if c['id'] in CLIP_IDS):
        out = args.output/clip['id']
        out.mkdir(exist_ok=True)
        assert not (out/'manifest.json').exists(), 'Output already complete'
        paired = next(c for c in color['clips'] if c['clip']['id'] == clip['id'])
        assert paired['clip'] == clip
        assert sha(paired['comparison_gif']['path']) == paired['comparison_gif']['sha256']
        src = sources(clip['scene'], summary)
        digest = hashlib.sha256()
        rows, saturated = [], [0]*6
        for f in range(clip['start'], clip['end']):
            row = []
            for i, s in enumerate(src):
                with Image.open(Path(s['folder'])/f'frame_{f:05d}.png') as im:
                    assert im.mode == 'RGB' and im.size == (1920, 1061)
                    h = hashlib.sha256(im.tobytes()).hexdigest()
                    assert h == s['hashes'][f], (s['case'], f)
                    digest.update(h.encode('ascii'))
                    result, sat = contours(im, clip['roi'])
                row.append(result)
                saturated[i] += sat
            rows.append(row)
        assert digest.hexdigest() == paired['source_rgb_digest']
        print(clip['id'], '360 source RGB hashes match color GIF inputs', flush=True)
        frames = [render(r, clip, clip['start']+i) for i, r in enumerate(rows)]
        grid = write_gif(out/'six-way-output-edges.gif', frames, clip['fps'])
        frames[len(frames)//2].save(out/'preview.png')
        del frames
        individuals = []
        for case in range(1, 7):
            frames = [render(r, clip, clip['start']+i, single=case) for i, r in enumerate(rows)]
            individuals.append(write_gif(out/f'case{case}-output-edges.gif', frames, clip['fps']))
            del frames
        assert grid['frames'] == paired['comparison_gif']['frames']
        assert grid['duration_ms'] == paired['comparison_gif']['duration_ms']
        rec = dict(validation='PASS', clip=clip, case_order=LABELS,
            layout='2 columns x 3 rows: [1,2] / [3,4] / [5,6]',
            source_rgb_verified_count=len(rows)*6, source_rgb_digest=digest.hexdigest(),
            source_summary_sha256=sha(DOC/'summary.json'),
            paired_color_gif=paired['comparison_gif'], output_contour_gif=grid,
            individual_contour_gifs=individuals, displayed_saturated_pixel_samples=saturated,
            method='Display-RGB luma 0.2126R+0.7152G+0.0722B; 3x3 Sobel axes /4; '
                   'Euclidean magnitude; fixed display gain 4; clamp 0..255, round to uint8. '
                   'One-pixel source halo, 2x nearest enlargement. No threshold or per-image normalization.',
            interpretation='Offline contours of FINAL RGB outputs, not internal first-pass edges, '
                           'not temporal selection masks and not a quality metric. '
                           'All cases/frames use identical settings; source images unchanged.',
            no_renderer_run=True)
        dump(out/'manifest.json', rec)
        records.append(rec)
        print(clip['id'], 'PASS: grid + 6 individual contour GIFs, decoded RGB exact', flush=True)
    dump(args.output/'manifest.json', dict(validation='PASS', clips=records))


if __name__ == '__main__':
    main()
