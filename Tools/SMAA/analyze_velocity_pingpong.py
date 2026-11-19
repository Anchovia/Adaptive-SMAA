"""Velocity ping-pong (c') capture: validation, output differences and the history rejection numbers.

Checks
  frames 00000..00239, 1920x1061 and valid chunk CRCs in every mode;
  byte bridges: O-1X, O-T2X-R, the selected route and selected + (c) against the history rejection
  capture of the same timeline, and case 19 against the base executable's capture (b6c3ebc).

Output differences (per frame, max-channel absolute difference of the decoded RGB)
  (c') vs (c), 19+(c') vs 19, 19+(c') vs selected+(c'), 19+(c') Keep vs 19+(c'), 19 vs selected:
  share of differing pixels, share above 8, maximum, and the densest 64x64 window of differing
  pixels at the frame with the most of them.

Ghost pixels, reference MAE and PSNR use the definitions of analyze_selected_history_rejection.py
(spatial = the same run's O-1X, reference = SS-Reference, phases moving f60-179, transition
f180-209, settled f220-239).

usage: analyze_velocity_pingpong.py --scene bistro --run <capture run dir> --reference <SS-Reference dir>
         --rejection-run <history rejection capture run dir> --base <base capture run dir> --out <json>
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
         ('pingpong', SEL + '+HistoryVelocityPingPong'), ('case19', C19), ('case19-pingpong', C19 + '+HistoryVelocityPingPong'),
         ('case19-pingpong-keep', C19 + '+HistoryVelocityPingPongKeepUnknown')]
TEMPORAL = [k for k, _ in MODES if k != 'O-1X']
PAIRS = [('pingpong', 'velocity'), ('case19-pingpong', 'case19'), ('case19-pingpong', 'pingpong'),
         ('case19-pingpong-keep', 'case19-pingpong'), ('case19', 'selected'), ('pingpong', 'selected')]
FRAMES, T_HIST, T_WORSE, PHASES = a.FRAMES, a.T_HIST, a.T_WORSE, a.PHASES


def densest(m, w=64, h=64):
    ii = np.pad(m.astype(np.float64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    win = ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]
    y0, x0 = np.unravel_index(np.argmax(win), win.shape)
    return [int(x0), int(y0), int(x0 + w), int(y0 + h)], int(win.max())


def main():
    ap = argparse.ArgumentParser()
    for k in ('scene', 'run', 'reference', 'rejection-run', 'base', 'out'):
        ap.add_argument('--' + k, required=True)
    x = ap.parse_args()
    run, rej, base = Path(x.run), Path(x.rejection_run), Path(x.base)
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
    bridges = {f'rejection_{k}': a.byte_bridge(dirs[k], rej / dict(MODES)[k]) for k in ('O-1X', 'O-T2X-R', 'selected', 'velocity')}
    bridges['base_case19'] = a.byte_bridge(dirs['case19'], base / C19)
    ok = all(c['pass_'] for c in checks.values())
    res = dict(scene=x.scene, run=str(run), reference=x.reference, rejection_run=str(rej), base=str(base), modes=dict(MODES),
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
    res.update(all_checks_pass=ok and all(b['pass_'] for b in bridges.values()), summary=summary,
               worst_diff_frames={k: v[1] for k, v in worst.items()}, frames=rows)
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(x.scene, 'checks', 'PASS' if res['all_checks_pass'] else 'FAIL', {k: b['identical'] for k, b in bridges.items()})
    for ph in PHASES:
        print(f'  {ph:10}', '  '.join(f"{k} g{summary[ph][k].get('ghost_mean', 0):.0f} mae{summary[ph][k]['mae']:.3f}" for k in TEMPORAL))
        print(' ' * 13, '  '.join(f"[{k}] {v['share_pct']:.3f}%/{v['share_gt8_pct']:.3f}% max{v['max']} same{v['frames_identical']}" for k, v in summary[ph]['diffs'].items()))
    print('  worst', res['worst_diff_frames'])


if __name__ == '__main__':
    main()
