"""History rejection experiment on the selected route: validation and per-frame quality numbers.

Input: one capture run of experiment/selected-history-rejection (O-1X, O-T2X-R, the selected route and
the selected route with each history filter) and the existing SS-Reference of the same timeline
(2x, 3x3 grid, 8xMSAA spatial reference; not a temporal ground truth).

Checks
  frames 00000..00239 in every mode, 1920x1061, every PNG chunk CRC valid;
  pose: O-T2X-R and the selected route byte-identical to the capture whose numbers were bridged to the
        reference (c20-a), and O-1X byte-identical to an earlier O-1X capture of the same timeline;
  baseline: O-T2X-R and the selected route byte-identical to the base executable's capture (b6c3ebc).

Per frame and mode (max-channel absolute error against the reference, 0..255)
  ghost_px: |mode - O1X| > 24 and err(mode) > err(O1X) + 24 (the screening of the coordinating
            session; O1X is the same run's SMAA 1X). For O-T2X-R the jitter alone moves pixels away
            from O1X, so its count is listed for reference only.
  hist_px:  |mode - O1X| > 24 (pixels the history moved visibly).
  mae, psnr: whole-frame RGB error against the reference.
  err_on_base_ghost: mean max-channel error on the selected route's own ghost pixels.
Phases: pre f0-59, moving f60-179, transition f180-209, settled f220-239 (f210-219 not aggregated).

usage: analyze_selected_history_rejection.py --scene bistro --run <capture run dir> --reference <SS-Reference dir>
         --reference-run <c20-a capture run dir> --pose <earlier O-1X dir> --base <base capture run dir> --out <json>
"""
import argparse, hashlib, json, struct, zlib
from pathlib import Path
import numpy as np
from PIL import Image

SEL = 'ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha'
MODES = [('O-1X', 'O-1X'), ('O-T2X-R', 'O-T2X-R'), ('selected', SEL), ('clamp3x3', SEL + '+HistoryClamp3x3'),
         ('prevdepth', SEL + '+HistoryPreviousDepth'), ('velocity', SEL + '+HistoryVelocityWeight')]
TEMPORAL = [k for k, _ in MODES if k != 'O-1X']
FRAMES, SIZE, T_HIST, T_WORSE = 240, (1920, 1061), 24, 24
PHASES = {'pre': range(0, 60), 'moving': range(60, 180), 'transition': range(180, 210), 'settled': range(220, 240)}


def crc_ok(p):
    data = p.read_bytes()
    if data[:8] != bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]):
        return False
    pos = 8
    while pos + 12 <= len(data):
        n = struct.unpack('>I', data[pos:pos + 4])[0]
        if pos + 12 + n > len(data) or zlib.crc32(data[pos + 4:pos + 8 + n]) & 0xffffffff != struct.unpack('>I', data[pos + 8 + n:pos + 12 + n])[0]:
            return False
        pos += 12 + n
    return pos == len(data)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rgb(p):
    with Image.open(p) as im:
        return np.asarray(im.convert('RGB')).astype(np.int16)


def frame(d, f):
    return Path(d) / f'frame_{f:05d}.png'


def byte_bridge(a, b):
    same = sum(1 for f in range(FRAMES) if frame(a, f).is_file() and frame(b, f).is_file() and sha(frame(a, f)) == sha(frame(b, f)))
    return dict(a=str(a), b=str(b), identical=same, frames=FRAMES, pass_=same == FRAMES)


def main():
    ap = argparse.ArgumentParser()
    for k in ('scene', 'run', 'reference', 'reference-run', 'pose', 'base', 'out'):
        ap.add_argument('--' + k, required=True)
    x = ap.parse_args()
    run = Path(x.run)
    dirs = {k: run / m for k, m in MODES}
    checks = {}
    for k, d in dirs.items():
        names = sorted(p.name for p in d.glob('frame_*.png'))
        expect = [f'frame_{i:05d}.png' for i in range(FRAMES)]
        bad = [n for n in expect if not (d / n).is_file() or not crc_ok(d / n)]
        with Image.open(d / expect[0]) as im:
            size = im.size
        checks[k] = dict(frames=len(names), exact_names=names == expect, damaged_or_missing=bad, size=list(size),
                         pass_=names == expect and not bad and size == SIZE)
    refs = [frame(x.reference, f) for f in range(FRAMES)]
    checks['reference'] = dict(frames=sum(p.is_file() for p in refs), pass_=all(p.is_file() and crc_ok(p) for p in refs))
    bridges = {'pose_O-1X': byte_bridge(dirs['O-1X'], Path(x.pose)),
               'reference_run_O-T2X-R': byte_bridge(dirs['O-T2X-R'], Path(x.reference_run) / 'O-T2X-R'),
               'reference_run_selected': byte_bridge(dirs['selected'], Path(x.reference_run) / SEL),
               'base_O-T2X-R': byte_bridge(dirs['O-T2X-R'], Path(x.base) / 'O-T2X-R'),
               'base_selected': byte_bridge(dirs['selected'], Path(x.base) / SEL)}
    if not all(c['pass_'] for c in checks.values()):
        Path(x.out).parent.mkdir(parents=True, exist_ok=True)
        Path(x.out).write_text(json.dumps(dict(scene=x.scene, run=str(run), checks=checks, bridges=bridges, all_checks_pass=False), indent=1) + '\n', encoding='utf-8')
        raise SystemExit(f'{x.scene}: frame checks failed, no metrics computed')
    rows = []
    for f in range(FRAMES):
        r = rgb(refs[f]); o = rgb(frame(dirs['O-1X'], f)); eo = np.abs(o - r).max(axis=2)
        imgs = {k: rgb(frame(dirs[k], f)) for k in TEMPORAL}
        errs = {k: np.abs(v - r).max(axis=2) for k, v in imgs.items()}
        hist = {k: np.abs(v - o).max(axis=2) > T_HIST for k, v in imgs.items()}
        ghost = {k: hist[k] & (errs[k] > eo + T_WORSE) for k in TEMPORAL}
        base_ghost = ghost['selected']
        row = dict(f=f)
        for k in ['O-1X'] + TEMPORAL:
            v = o if k == 'O-1X' else imgs[k]
            mse = float(((v - r).astype(np.float64) ** 2).mean())
            row[k] = dict(mae=float(np.abs(v - r).mean()), psnr=float(10 * np.log10(255 ** 2 / mse)) if mse > 0 else None,
                          err_on_base_ghost=float((eo if k == 'O-1X' else errs[k])[base_ghost].mean()) if base_ghost.any() else None)
            if k != 'O-1X':
                ys, xs = np.nonzero(ghost[k])
                row[k].update(ghost_px=int(ghost[k].sum()), hist_px=int(hist[k].sum()),
                              ghost_box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None)
        rows.append(row)
        if f % 40 == 0:
            print(x.scene, f, {k: row[k]['ghost_px'] for k in TEMPORAL}, flush=True)
    summary = {}
    for ph, fr in PHASES.items():
        summary[ph] = {}
        for k in ['O-1X'] + TEMPORAL:
            vals = [rows[f][k] for f in fr]
            s = dict(mae=float(np.mean([v['mae'] for v in vals])),
                     psnr=float(np.mean([v['psnr'] for v in vals if v['psnr'] is not None])))
            if k != 'O-1X':
                g = [v['ghost_px'] for v in vals]
                s.update(ghost_mean=float(np.mean(g)), ghost_max=int(max(g)), ghost_max_f=int(list(fr)[int(np.argmax(g))]),
                         hist_mean=float(np.mean([v['hist_px'] for v in vals])))
            eg = [v['err_on_base_ghost'] for v in vals if v['err_on_base_ghost'] is not None]
            s['err_on_base_ghost'] = float(np.mean(eg)) if eg else None
            summary[ph][k] = s
    res = dict(scene=x.scene, run=str(run), reference=x.reference, modes=dict(MODES), thresholds=dict(hist=T_HIST, worse=T_WORSE),
               phases={k: [v.start, v.stop - 1] for k, v in PHASES.items()}, checks=checks, bridges=bridges,
               all_checks_pass=all(c['pass_'] for c in checks.values()) and all(b['pass_'] for b in bridges.values()),
               summary=summary, frames=rows)
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(x.scene, 'checks', 'PASS' if res['all_checks_pass'] else 'FAIL', {k: b['identical'] for k, b in bridges.items()})
    for ph in PHASES:
        print(f'  {ph:10}', '  '.join(f"{k} g{summary[ph][k].get('ghost_mean', 0):.0f}/{summary[ph][k].get('ghost_max', 0)} "
                                         f"mae{summary[ph][k]['mae']:.3f}" for k in ['O-1X'] + TEMPORAL))


if __name__ == '__main__':
    main()
