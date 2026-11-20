"""Velocity footprint capture ((c') Cross5 / Footprint12): validation, output differences, history rejection
numbers and the 1px column check of (c').

Checks
  frames 00000..00239, 1920x1061 and valid chunk CRCs in every mode;
  byte bridges: O-1X, O-T2X-R, the selected route, selected + (c), selected + (c'), case 19 and
  19 + (c') against the velocity ping-pong capture of the same timeline (they must not change).

Output differences (per frame, max-channel absolute difference of the decoded RGB)
  Cross5 and Footprint12 against (c') and (c), Footprint12 against Cross5, the case-19 variants against
  19 + (c'), and 19 + Footprint12 against selected + Footprint12: share of differing pixels, share above
  8, maximum, and the densest 64x64 window of differing pixels at the frame with the most of them.

Ghost pixels, reference MAE and PSNR use the definitions of analyze_selected_history_rejection.py
(spatial = the same run's O-1X, reference = SS-Reference, phases moving f60-179, transition
f180-209, settled f220-239).

Column check (Minecraft): the coordinating session found 1px vertical lines of (c') in the first dirt
column right of the previous frame's wall edge (x97 f119, x64 f120-124, x30 f121-126, rows 96-143)
and in the foliage (x32 f87-89, x110 f86-88, rows 718-805). For each named column and frame: the mean
over the rows of the max-channel |mode - O-1X| and |mode - SS-Reference|, and the mean RGB of the
column. For the left ROI also the column with the largest mean |mode - O-1X| among the columns more
than one pixel right of the current wall edge (f118 x96|97, f119 x63|64, f120 x29|30, off screen
from f121; f118 has none inside the ROI), so a line that moved to another column is still found.

usage: analyze_velocity_footprint.py --scene bistro --run <capture run dir> --reference <SS-Reference dir>
         --pingpong-run <velocity ping-pong capture run dir> --out <json>
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
import analyze_selected_history_rejection as a

SEL = a.SEL
C19 = SEL + '+VelocityInEdge'
MODES = [('O-1X', 'O-1X'), ('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('velocity', SEL + '+HistoryVelocityWeight'),
         ('pingpong', SEL + '+HistoryVelocityPingPong'), ('cross5', SEL + '+HistoryVelocityPingPongCross5'),
         ('footprint12', SEL + '+HistoryVelocityPingPongFootprint12'), ('case19', C19),
         ('case19-pingpong', C19 + '+HistoryVelocityPingPong'), ('case19-cross5', C19 + '+HistoryVelocityPingPongCross5'),
         ('case19-footprint12', C19 + '+HistoryVelocityPingPongFootprint12')]
TEMPORAL = [k for k, _ in MODES if k != 'O-1X']
BRIDGED = ['O-1X', 'O-T2X-R', 'selected', 'velocity', 'pingpong', 'case19', 'case19-pingpong']
PAIRS = [('cross5', 'pingpong'), ('footprint12', 'pingpong'), ('footprint12', 'cross5'), ('cross5', 'velocity'),
         ('footprint12', 'velocity'), ('case19-cross5', 'case19-pingpong'), ('case19-footprint12', 'case19-pingpong'),
         ('case19-footprint12', 'footprint12')]
FRAMES, T_HIST, T_WORSE, PHASES = a.FRAMES, a.T_HIST, a.T_WORSE, a.PHASES
COLUMNS = {'minecraft': [('left-line', 97, (96, 144), range(118, 123)), ('left-line', 64, (96, 144), range(119, 127)),
                         ('left-line', 30, (96, 144), range(120, 129)), ('foliage', 32, (718, 806), range(85, 93)),
                         ('foliage', 110, (718, 806), range(84, 92))]}
# f118 has no column more than one pixel right of its wall edge (x96) inside the ROI, so the scan starts at f119.
LEFT = dict(rows=(96, 144), cols=(0, 96), frames=range(119, 129), edge={119: 63, 120: 29})


def densest(m, w=64, h=64):
    ii = np.pad(m.astype(np.float64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    win = ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]
    y0, x0 = np.unravel_index(np.argmax(win), win.shape)
    return [int(x0), int(y0), int(x0 + w), int(y0 + h)], int(win.max())


def column_check(scene, dirs, reference):
    if scene not in COLUMNS:
        return None
    res = {'named': [], 'left_scan': []}
    for roi, x, (y0, y1), frames in COLUMNS[scene]:
        for f in frames:
            r = a.rgb(a.frame(reference, f))[y0:y1, x]
            imgs = {k: a.rgb(a.frame(dirs[k], f))[y0:y1, x] for k, _ in MODES}
            o = imgs['O-1X']
            res['named'].append(dict(roi=roi, x=x, rows=[y0, y1 - 1], f=f, modes={
                k: dict(d1x=float(np.abs(v - o).max(axis=1).mean()), dref=float(np.abs(v - r).max(axis=1).mean()),
                        rgb=[round(float(c), 1) for c in v.mean(axis=0)]) for k, v in imgs.items()}))
    (y0, y1), (x0, x1) = LEFT['rows'], LEFT['cols']
    for f in LEFT['frames']:
        lo = LEFT['edge'].get(f, -1) + 2
        imgs = {k: a.rgb(a.frame(dirs[k], f))[y0:y1, x0:x1] for k, _ in MODES}
        o = imgs['O-1X']; row = dict(f=f, first_column=lo, modes={})
        for k, v in imgs.items():
            prof = np.abs(v - o).max(axis=2).mean(axis=0)[lo:]
            row['modes'][k] = dict(x=int(lo + np.argmax(prof)), d1x=float(prof.max()))
        res['left_scan'].append(row)
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ('scene', 'run', 'reference', 'pingpong-run', 'out'):
        ap.add_argument('--' + k, required=True)
    x = ap.parse_args()
    run, pp = Path(x.run), Path(x.pingpong_run)
    dirs = {k: run / m for k, m in MODES}
    expect = [f'frame_{i:05d}.png' for i in range(FRAMES)]
    checks = {}
    for k, d in dirs.items():
        names = sorted(p.name for p in d.glob('frame_*.png'))
        bad = [n for n in expect if not (d / n).is_file() or not a.crc_ok(d / n)]
        with Image.open(d / expect[0]) as im:
            size = im.size
        checks[k] = dict(frames=len(names), exact_names=names == expect, damaged_or_missing=bad, size=list(size),
                         pass_=names == expect and not bad and size == a.SIZE)
    refs = [a.frame(x.reference, f) for f in range(FRAMES)]
    checks['reference'] = dict(frames=sum(p.is_file() for p in refs), pass_=all(p.is_file() and a.crc_ok(p) for p in refs))
    bridges = {f'pingpong_{k}': a.byte_bridge(dirs[k], pp / dict(MODES)[k]) for k in BRIDGED}
    ok = all(c['pass_'] for c in checks.values())
    res = dict(scene=x.scene, run=str(run), reference=x.reference, pingpong_run=str(pp), modes=dict(MODES),
               checks=checks, bridges=bridges)
    if not ok:
        res['all_checks_pass'] = False
        Path(x.out).parent.mkdir(parents=True, exist_ok=True)
        Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
        raise SystemExit(f'{x.scene}: frame checks failed, no metrics computed')
    rows = []
    worst = {f'{p} vs {q}': (-1, None) for p, q in PAIRS}
    for f in range(FRAMES):
        r = a.rgb(refs[f]); imgs = {k: a.rgb(a.frame(dirs[k], f)) for k, _ in MODES}
        o = imgs['O-1X']; eo = np.abs(o - r).max(axis=2)
        row = dict(f=f, diffs={})
        for k in ['O-1X'] + TEMPORAL:
            v = imgs[k]; mse = float(((v - r).astype(np.float64) ** 2).mean())
            row[k] = dict(mae=float(np.abs(v - r).mean()), psnr=float(10 * np.log10(255 ** 2 / mse)) if mse > 0 else None)
            if k != 'O-1X':
                e = np.abs(v - r).max(axis=2); hist = np.abs(v - o).max(axis=2) > T_HIST
                row[k].update(ghost_px=int((hist & (e > eo + T_WORSE)).sum()), hist_px=int(hist.sum()))
        for p, q in PAIRS:
            d = np.abs(imgs[p] - imgs[q]).max(axis=2); key = f'{p} vs {q}'
            row['diffs'][key] = dict(px=int((d > 0).sum()), px_gt8=int((d > 8).sum()), max=int(d.max()))
            if row['diffs'][key]['px'] > worst[key][0]:
                box, n = densest(d > 0)
                worst[key] = (row['diffs'][key]['px'], dict(f=f, px=row['diffs'][key]['px'], window=box, window_px=n))
        rows.append(row)
        if f % 40 == 0:
            print(x.scene, f, {k: row[k]['ghost_px'] for k in TEMPORAL}, flush=True)
    npx = a.SIZE[0] * a.SIZE[1]
    summary = {}
    for ph, fr in PHASES.items():
        s = {}
        for k in ['O-1X'] + TEMPORAL:
            vals = [rows[f][k] for f in fr]
            s[k] = dict(mae=float(np.mean([v['mae'] for v in vals])), psnr=float(np.mean([v['psnr'] for v in vals if v['psnr'] is not None])))
            if k != 'O-1X':
                g = [v['ghost_px'] for v in vals]
                s[k].update(ghost_mean=float(np.mean(g)), ghost_max=int(max(g)), ghost_max_f=int(list(fr)[int(np.argmax(g))]))
        s['diffs'] = {}
        for p, q in PAIRS:
            key = f'{p} vs {q}'; vals = [rows[f]['diffs'][key] for f in fr]
            s['diffs'][key] = dict(share_pct=100 * float(np.mean([v['px'] for v in vals])) / npx,
                                   share_gt8_pct=100 * float(np.mean([v['px_gt8'] for v in vals])) / npx,
                                   max=int(max(v['max'] for v in vals)), frames_identical=sum(v['px'] == 0 for v in vals))
        summary[ph] = s
    columns = column_check(x.scene, dirs, x.reference)
    res.update(all_checks_pass=ok and all(b['pass_'] for b in bridges.values()), summary=summary,
               worst_diff_frames={k: v[1] for k, v in worst.items()}, columns=columns, frames=rows)
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(x.scene, 'checks', 'PASS' if res['all_checks_pass'] else 'FAIL', {k: b['identical'] for k, b in bridges.items()})
    for ph in PHASES:
        print(f'  {ph:10}', '  '.join(f"{k} g{summary[ph][k].get('ghost_mean', 0):.0f} mae{summary[ph][k]['mae']:.3f}" for k in TEMPORAL))
        print(' ' * 13, '  '.join(f"[{k}] {v['share_pct']:.3f}%/{v['share_gt8_pct']:.3f}% max{v['max']} same{v['frames_identical']}" for k, v in summary[ph]['diffs'].items()))
    print('  worst', res['worst_diff_frames'])
    if columns:
        show = ['O-1X', 'selected', 'velocity', 'pingpong', 'cross5', 'footprint12', 'case19', 'case19-pingpong', 'case19-footprint12']
        print('  named columns: d1x per mode', show)
        for c in columns['named']:
            print(f"   {c['roi']:9} x{c['x']:<3} f{c['f']:3}", ' '.join(f"{c['modes'][k]['d1x']:6.1f}" for k in show))
        print('  left scan: (x, d1x) of the strongest column right of the wall edge')
        for c in columns['left_scan']:
            print(f"   f{c['f']:3} from x{c['first_column']:<3}", ' '.join(f"{c['modes'][k]['x']:3}:{c['modes'][k]['d1x']:5.1f}" for k in show))


if __name__ == '__main__':
    main()
