"""Nearest-neighbour sheets of the history rejection capture (original lossless PNGs, no colour change).

Columns: O-1X, O-T2X-R, the selected route, the selected route + (a) 3x3 clamp / (b) previous depth /
(c) velocity weight, SS-Reference. Rows are consecutive frames. The ghost-map overview is the only
image with an overlay (red = ghost pixels of the screening), drawn on half-size frames.

usage: selected_history_rejection_sheets.py --scene bistro --run <capture run dir> --reference <SS-Reference dir> --out <dir>
         [--roi name x0 y0 x1 y1 scale f0 f1 ...] [--ghost-map f]
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SEL = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
COLS = [('O-1X', 'O-1X'), ('O-T2X-R', 'O-T2X-R'), ('선택 경로', SEL), ('+(a) 3x3 색 범위', SEL + '+HistoryClamp3x3'),
        ('+(b) 이전 depth', SEL + '+HistoryPreviousDepth'), ('+(c) velocity 비중', SEL + '+HistoryVelocityWeight'), ('SS-Reference', None)]
FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 15)
# Default sheets: ROI, nearest scale and frame groups (moving windows named by the coordinating
# session, then transition and settled).
DEFAULT = {
    'bistro': [('window-band', (946, 466, 1074, 554), 4, [range(120, 126), range(178, 184), range(230, 236)]),
               ('chair-legs', (1230, 582, 1358, 670), 4, [range(120, 126), range(178, 184), range(230, 236)])],
    'minecraft': [('foliage', (7, 718, 135, 806), 4, [range(85, 91), range(90, 96), range(178, 184), range(230, 236)]),
                  ('left-line', (0, 96, 96, 144), 6, [range(116, 122), range(120, 126), range(178, 184), range(230, 236)]),
                  ('seam', (956, 524, 1020, 620), 4, [range(126, 132), range(178, 184), range(230, 236)])],
}


def load(run, ref, mode, f):
    p = (Path(ref) if mode is None else Path(run) / mode) / f'frame_{f:05d}.png'
    with Image.open(p) as im:
        return np.asarray(im.convert('RGB')).copy()


def phase(f):
    return 'moving' if 60 <= f < 180 else 'transition' if 180 <= f < 210 else 'settled' if f >= 220 else 'pre' if f < 60 else 'late-transition'


def roi_sheet(scene, run, ref, name, roi, scale, frames, out):
    x0, y0, x1, y1 = roi; cw, ch = (x1 - x0) * scale, (y1 - y0) * scale
    frames = list(frames)
    sheet = Image.new('RGB', (len(COLS) * (cw + 6) + 6, len(frames) * (ch + 24) + 30), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.text((6, 5), f'{scene} {name} | ROI ({x0},{y0})-({x1},{y1}) nearest x{scale} | f{frames[0]}-{frames[-1]} '
                   f'({phase(frames[0])}-{phase(frames[-1])}) | 원본 PNG, 색 보정 없음', fill=(0, 0, 0), font=FONT)
    for ri, f in enumerate(frames):
        for ci, (label, mode) in enumerate(COLS):
            crop = Image.fromarray(load(run, ref, mode, f)[y0:y1, x0:x1]).resize((cw, ch), Image.NEAREST)
            px, py = 6 + ci * (cw + 6), 30 + ri * (ch + 24)
            sheet.paste(crop, (px, py + 20)); d.text((px, py), f'{label}  f{f}', fill=(0, 0, 0), font=FONT)
    path = Path(out) / f'{scene}-{name}-f{frames[0]:03d}-{frames[-1]:03d}.png'
    sheet.save(path); print(path.name)


def ghost_map(scene, run, ref, f, out, t_hist=24, t_worse=24):
    """Half-size frames with the screening's ghost pixels in red (3x3 dilated so they survive the halving)."""
    r = load(run, ref, None, f).astype(np.int16); o = load(run, ref, 'O-1X', f).astype(np.int16)
    eo = np.abs(o - r).max(axis=2)
    tiles = []
    for label, mode in COLS[2:6]:
        v = load(run, ref, mode, f).astype(np.int16)
        m = (np.abs(v - o).max(axis=2) > t_hist) & (np.abs(v - r).max(axis=2) > eo + t_worse)
        dil = m.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                dil |= np.roll(np.roll(m, dy, 0), dx, 1)
        im = v.astype(np.uint8).copy(); im[dil] = (255, 0, 0)
        tiles.append((f'{label}  f{f}  ghost {int(m.sum())} px', Image.fromarray(im).resize((960, 530), Image.NEAREST)))
    sheet = Image.new('RGB', (2 * 966 + 6, 2 * (530 + 24) + 30), (255, 255, 255)); d = ImageDraw.Draw(sheet)
    d.text((6, 5), f'{scene} f{f} | 빨강 = |mode-O1X|>{t_hist} 이고 기준 오차가 O-1X보다 {t_worse} 넘게 큰 화소 (3x3 확장, 표시용 오버레이, 1/2 nearest)',
           fill=(0, 0, 0), font=FONT)
    for i, (label, tile) in enumerate(tiles):
        px, py = 6 + (i % 2) * 966, 30 + (i // 2) * (530 + 24)
        sheet.paste(tile, (px, py + 20)); d.text((px, py), label, fill=(0, 0, 0), font=FONT)
    path = Path(out) / f'{scene}-ghost-map-f{f:03d}.png'
    sheet.save(path); print(path.name)


def main():
    ap = argparse.ArgumentParser()
    for k in ('scene', 'run', 'reference', 'out'):
        ap.add_argument('--' + k, required=True)
    ap.add_argument('--roi', nargs='+', action='append', default=[])
    ap.add_argument('--ghost-map', type=int, action='append', default=[])
    x = ap.parse_args()
    Path(x.out).mkdir(parents=True, exist_ok=True)
    if not x.roi and not x.ghost_map:
        for name, roi, scale, groups in DEFAULT[x.scene]:
            for g in groups:
                roi_sheet(x.scene, x.run, x.reference, name, roi, scale, g, x.out)
    for a in x.roi:
        name, (x0, y0, x1, y1, scale), frames = a[0], map(int, a[1:6]), [int(v) for v in a[6:]]
        roi_sheet(x.scene, x.run, x.reference, name, (x0, y0, x1, y1), scale, frames, x.out)
    for f in x.ghost_map:
        ghost_map(x.scene, x.run, x.reference, f, x.out)


if __name__ == '__main__':
    main()
