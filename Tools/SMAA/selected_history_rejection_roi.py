"""ROI numbers for the thin-line and ghost windows of the history rejection capture.

For each ROI and mode, over the given frames: RGB MAE against the SS-Reference, the share of ROI pixels
identical to the same run's O-1X (no visible history), the ghost pixel count of the screening and the
mean absolute frame-to-frame change (camera motion included; compare modes with each other only).

usage: selected_history_rejection_roi.py --scene bistro --run <capture run dir> --reference <SS-Reference dir> --out <json>
"""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image

SEL = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
MODES = [('O-1X', 'O-1X'), ('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('clamp3x3', SEL + '+HistoryClamp3x3'),
         ('prevdepth', SEL + '+HistoryPreviousDepth'), ('velocity', SEL + '+HistoryVelocityWeight')]
ROIS = {
    'bistro': {'window-band': ((946, 466, 1074, 554), range(120, 126)),
               'chair-legs': ((1230, 582, 1358, 670), range(120, 126)),
               'chair-legs-moving': ((1230, 582, 1358, 670), range(60, 180))},
    'minecraft': {'foliage': ((7, 718, 135, 806), range(85, 96)),
                  'left-line': ((0, 96, 96, 144), range(116, 126)),
                  'seam': ((956, 524, 1020, 620), range(126, 132)),
                  'seam-moving': ((956, 524, 1020, 620), range(60, 180))},
}


def rgb(p):
    with Image.open(p) as im:
        return np.asarray(im.convert('RGB')).astype(np.int16)


def main():
    ap = argparse.ArgumentParser()
    for k in ('scene', 'run', 'reference', 'out'):
        ap.add_argument('--' + k, required=True)
    x = ap.parse_args()
    run, ref = Path(x.run), Path(x.reference)
    res = dict(scene=x.scene, run=str(run), reference=str(ref), rois={})
    for name, ((x0, y0, x1, y1), frames) in ROIS[x.scene].items():
        acc = {k: dict(mae=[], same_as_1x=[], ghost=[], change=[]) for k, _ in MODES}
        prev = {}
        for f in frames:
            r = rgb(ref / f'frame_{f:05d}.png')[y0:y1, x0:x1]
            imgs = {k: rgb(run / m / f'frame_{f:05d}.png')[y0:y1, x0:x1] for k, m in MODES}
            o = imgs['O-1X']; eo = np.abs(o - r).max(axis=2)
            for k, v in imgs.items():
                a = acc[k]
                a['mae'].append(float(np.abs(v - r).mean()))
                a['same_as_1x'].append(float((np.abs(v - o).max(axis=2) == 0).mean()))
                a['ghost'].append(int(((np.abs(v - o).max(axis=2) > 24) & (np.abs(v - r).max(axis=2) > eo + 24)).sum()))
                if k in prev:
                    a['change'].append(float(np.abs(v - prev[k]).mean()))
                prev[k] = v
        res['rois'][name] = dict(box=[x0, y0, x1, y1], frames=[frames.start, frames.stop - 1],
                                 modes={k: {m: float(np.mean(v)) if v else None for m, v in a.items()} for k, a in acc.items()})
        print(name, {k: (round(v['mae'], 3), round(v['same_as_1x'], 3), round(v['ghost'], 1), round(v['change'] or 0, 3))
                     for k, v in res['rois'][name]['modes'].items()})
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
