"""Adaptive + selected route + (c') Cross5 capture: validation, output bridges, ghost/error numbers and the
1px column check, with Original and Adaptive SMAA side by side.

Checks
  frames 00000..00239, 1920x1061 and valid chunk CRCs in every mode;
  byte bridges: O-1X, O-T2X-R, the selected route and selected + Cross5 against the footprint capture
  (c27); A-1X against the minimal branch's SMAA 1X capture; Adaptive + selected route against the minimal
  branch's temporal capture (both verified there against the research 1% RGBA8 captures).

Ghost pixels use the screening of the earlier experiments: |mode - S| > 24 and error > error(S) + 24,
error = max-channel difference to the SS-Reference. S is O-1X for every mode (the definition of the
earlier documents); for the Adaptive modes the same count against A-1X is also given. Reference MAE
and PSNR as before; phases moving f60-179, transition f180-209, settled f220-239.

Output differences: Adaptive vs Original on the same route, Cross5 vs no filter on the same spatial
SMAA, and A-1X vs O-1X.

Column check (Minecraft): the five (c') line columns of the footprint document, as the mean over the
rows of the max-channel difference to the same-spatial 1X (O-1X for Original, A-1X for Adaptive modes).

usage: analyze_adaptive_selected_cross5.py --scene bistro --run <run> --reference <SS-Reference>
         --footprint-run <c27 run> --minimal-run <minimal temporal run> --minimal-spatial-run <minimal 1X run> --out <json>
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
import analyze_selected_history_rejection as a
import analyze_velocity_footprint as fp

SEL = a.SEL
X5 = '+HistoryVelocityPingPongCross5'
MODES = [('O-1X', 'O-1X'), ('A-1X', 'A-1X'), ('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('cross5', SEL + X5),
         ('A-selected', 'A-' + SEL), ('A-cross5', 'A-' + SEL + X5)]
TEMPORAL = ['O-T2X-R', 'selected', 'cross5', 'A-selected', 'A-cross5']
ADAPTIVE = {'A-1X', 'A-selected', 'A-cross5'}
PAIRS = [('A-selected', 'selected'), ('A-cross5', 'cross5'), ('cross5', 'selected'), ('A-cross5', 'A-selected'), ('A-1X', 'O-1X')]
FRAMES, T_HIST, T_WORSE, PHASES = a.FRAMES, a.T_HIST, a.T_WORSE, a.PHASES


def ghosts(v, s, r, es):
    return int(((np.abs(v - s).max(axis=2) > T_HIST) & (np.abs(v - r).max(axis=2) > es + T_WORSE)).sum())


def column_check(dirs, reference):
    rows = []
    for roi, x, (y0, y1), frames in fp.COLUMNS['minecraft']:
        for f in frames:
            r = a.rgb(a.frame(reference, f))[y0:y1, x]
            imgs = {k: a.rgb(a.frame(dirs[k], f))[y0:y1, x] for k, _ in MODES}
            out = {}
            for k, v in imgs.items():
                s = imgs['A-1X' if k in ADAPTIVE else 'O-1X']
                out[k] = dict(d1x=float(np.abs(v - s).max(axis=1).mean()), dref=float(np.abs(v - r).max(axis=1).mean()),
                              rgb=[round(float(c), 1) for c in v.mean(axis=0)])
            rows.append(dict(roi=roi, x=x, rows=[y0, y1 - 1], f=f, modes=out))
    return rows


def main():
    ap = argparse.ArgumentParser()
    for k in ('scene', 'run', 'reference', 'footprint-run', 'minimal-run', 'minimal-spatial-run', 'out'):
        ap.add_argument('--' + k, required=True)
    x = ap.parse_args()
    run = Path(x.run)
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
    fpr, mt, ms = Path(x.footprint_run), Path(x.minimal_run), Path(x.minimal_spatial_run)
    bridges = {f'footprint_{k}': a.byte_bridge(dirs[k], fpr / dict(MODES)[k]) for k in ('O-1X', 'O-T2X-R', 'selected', 'cross5')}
    bridges['minimal_A-1X'] = a.byte_bridge(dirs['A-1X'], ms / 'A-1X')
    bridges['minimal_O-1X'] = a.byte_bridge(dirs['O-1X'], ms / 'O-1X')
    bridges['minimal_A-selected'] = a.byte_bridge(dirs['A-selected'], mt / ('A-' + SEL))
    bridges['minimal_selected'] = a.byte_bridge(dirs['selected'], mt / SEL)
    bridges['minimal_O-T2X-R'] = a.byte_bridge(dirs['O-T2X-R'], mt / 'O-T2X-R')
    ok = all(c['pass_'] for c in checks.values())
    res = dict(scene=x.scene, run=str(run), reference=x.reference, footprint_run=str(fpr), minimal_run=str(mt),
               minimal_spatial_run=str(ms), modes=dict(MODES), checks=checks, bridges=bridges)
    if not ok:
        res['all_checks_pass'] = False
        Path(x.out).parent.mkdir(parents=True, exist_ok=True)
        Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
        raise SystemExit(f'{x.scene}: frame checks failed, no metrics computed')
    rows = []
    worst = {f'{p} vs {q}': (-1, None) for p, q in PAIRS}
    for f in range(FRAMES):
        r = a.rgb(refs[f]); imgs = {k: a.rgb(a.frame(dirs[k], f)) for k, _ in MODES}
        o, ad = imgs['O-1X'], imgs['A-1X']
        eo, ea = np.abs(o - r).max(axis=2), np.abs(ad - r).max(axis=2)
        row = dict(f=f, diffs={})
        for k, _ in MODES:
            v = imgs[k]; mse = float(((v - r).astype(np.float64) ** 2).mean())
            row[k] = dict(mae=float(np.abs(v - r).mean()), psnr=float(10 * np.log10(255 ** 2 / mse)) if mse > 0 else None)
            if k in TEMPORAL:
                row[k]['ghost_px'] = ghosts(v, o, r, eo)
                if k in ADAPTIVE:
                    row[k]['ghost_px_vs_a1x'] = ghosts(v, ad, r, ea)
        for p, q in PAIRS:
            d = np.abs(imgs[p] - imgs[q]).max(axis=2); key = f'{p} vs {q}'
            row['diffs'][key] = dict(px=int((d > 0).sum()), px_gt8=int((d > 8).sum()), max=int(d.max()))
            if row['diffs'][key]['px'] > worst[key][0]:
                box, n = fp.densest(d > 0)
                worst[key] = (row['diffs'][key]['px'], dict(f=f, px=row['diffs'][key]['px'], window=box, window_px=n))
        rows.append(row)
        if f % 40 == 0:
            print(x.scene, f, {k: row[k]['ghost_px'] for k in TEMPORAL}, flush=True)
    npx = a.SIZE[0] * a.SIZE[1]
    summary = {}
    for ph, fr in PHASES.items():
        s = {}
        for k, _ in MODES:
            vals = [rows[f][k] for f in fr]
            s[k] = dict(mae=float(np.mean([v['mae'] for v in vals])), psnr=float(np.mean([v['psnr'] for v in vals if v['psnr'] is not None])))
            if k in TEMPORAL:
                g = [v['ghost_px'] for v in vals]
                s[k].update(ghost_mean=float(np.mean(g)), ghost_max=int(max(g)), ghost_max_f=int(list(fr)[int(np.argmax(g))]))
                if k in ADAPTIVE:
                    s[k]['ghost_mean_vs_a1x'] = float(np.mean([v['ghost_px_vs_a1x'] for v in vals]))
        s['diffs'] = {}
        for p, q in PAIRS:
            key = f'{p} vs {q}'; vals = [rows[f]['diffs'][key] for f in fr]
            s['diffs'][key] = dict(share_pct=100 * float(np.mean([v['px'] for v in vals])) / npx,
                                   share_gt8_pct=100 * float(np.mean([v['px_gt8'] for v in vals])) / npx,
                                   max=int(max(v['max'] for v in vals)), frames_identical=sum(v['px'] == 0 for v in vals))
        summary[ph] = s
    columns = column_check(dirs, x.reference) if x.scene == 'minecraft' else None
    res.update(all_checks_pass=ok and all(b['pass_'] for b in bridges.values()), summary=summary,
               worst_diff_frames={k: v[1] for k, v in worst.items()}, columns=columns, frames=rows)
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(x.scene, 'checks', 'PASS' if res['all_checks_pass'] else 'FAIL', {k: b['identical'] for k, b in bridges.items()})
    for ph in PHASES:
        print(f'  {ph:10}', '  '.join(f"{k} g{summary[ph][k].get('ghost_mean', 0):.0f} mae{summary[ph][k]['mae']:.4f}" for k, _ in MODES))
        print(' ' * 13, '  '.join(f"[{k}] {v['share_pct']:.3f}%/{v['share_gt8_pct']:.3f}% max{v['max']}" for k, v in summary[ph]['diffs'].items()))
    if columns:
        show = ['selected', 'cross5', 'A-selected', 'A-cross5']
        print('  columns d1x (same-spatial 1X):', show)
        for c in columns:
            print(f"   {c['roi']:9} x{c['x']:<3} f{c['f']:3}", ' '.join(f"{c['modes'][k]['d1x']:6.1f}" for k in show))


if __name__ == '__main__':
    main()
