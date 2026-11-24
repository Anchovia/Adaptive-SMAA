"""Checks the camera velocity used by the selected route against the image motion of a -translationCapture velocity run.

For consecutive saved frames k-1, k of a condition (fixed60, fixed300) it warps Off frame k-1 (Adaptive SMAA 1X) to
frame k with s * velocity_k (the history lookup uv - v, bilinear) for s = 0.80 .. 1.20 and reports the mean absolute
residual over pixels away from velocity discontinuities (|grad v| small: no silhouette, no disocclusion). If the velocity
is right the residual is smallest at s = 1.00. It also measures the shift of 64x64 patches with phase correlation and
compares it with the median velocity of the patch (patches with nearly uniform velocity and a clear peak only).

usage: python verify_translation_velocity.py --run <capture root of a velocity run> --out <json>
"""
import argparse, json, struct
from pathlib import Path

import cv2
import numpy as np

W, H = 1920, 1061
SCALES = [round(0.80 + 0.02 * i, 2) for i in range(21)]


def load_dds_rg16f(p):
    b = Path(p).read_bytes()
    assert b[:4] == b'DDS '
    h, w = struct.unpack_from('<II', b, 12)
    fourcc = b[84:88]
    off = 128
    if fourcc == b'DX10':
        fmt = struct.unpack_from('<I', b, 128)[0]
        assert fmt == 34, fmt  # DXGI_FORMAT_R16G16_FLOAT
        off = 148
    else:
        assert struct.unpack_from('<I', b, 84)[0] == 112, fourcc  # D3DFMT_G16R16F
    return np.frombuffer(b, np.float16, count=h * w * 2, offset=off).reshape(h, w, 2).astype(np.float32)


def gray(p):
    return cv2.cvtColor(cv2.imread(str(p), cv2.IMREAD_COLOR), cv2.COLOR_BGR2GRAY).astype(np.float32)


def check(run, cond):
    base = run / cond
    idx = sorted(int(p.stem.split('_')[1]) for p in (base / 'On').glob('velocity_*.dds'))
    xs, ys = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    res = {s: [] for s in SCALES}
    ratios, speeds = [], []
    for k in idx:
        if k - 1 not in idx and not (base / 'Off' / f'frame_{k - 1:05d}.png').is_file():
            continue
        if k == 0 or not (base / 'Off' / f'frame_{k - 1:05d}.png').is_file():
            continue
        v = load_dds_rg16f(base / 'On' / f'velocity_{k:05d}.dds')
        vx, vy = v[..., 0] * W, v[..., 1] * H
        cur, prev = gray(base / 'Off' / f'frame_{k:05d}.png'), gray(base / 'Off' / f'frame_{k - 1:05d}.png')
        g = np.maximum.reduce([np.abs(np.diff(vx, axis=1, prepend=vx[:, :1])), np.abs(np.diff(vy, axis=0, prepend=vy[:1])),
                               np.abs(np.diff(vx, axis=0, prepend=vx[:1])), np.abs(np.diff(vy, axis=1, prepend=vy[:, :1]))])
        smooth = cv2.erode((g < 0.05).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        tex = cv2.Laplacian(cur, cv2.CV_32F, ksize=3)
        mask = smooth & (np.abs(tex) > 4)
        speeds.append(float(np.median(np.hypot(vx, vy)[mask])) if mask.any() else 0.0)
        for s in SCALES:
            mx, my = xs - s * vx, ys - s * vy
            inb = (mx >= 0) & (mx <= W - 1) & (my >= 0) & (my <= H - 1)
            warped = cv2.remap(prev, mx, my, cv2.INTER_LINEAR)
            m = mask & inb
            res[s].append(float(np.abs(warped - cur)[m].mean()) if m.any() else np.nan)
        win = cv2.createHanningWindow((64, 64), cv2.CV_32F)
        for y in range(32, H - 96, 64):
            for x in range(32, W - 96, 64):
                pv = vx[y:y + 64, x:x + 64], vy[y:y + 64, x:x + 64]
                if not smooth[y:y + 64, x:x + 64].all():
                    continue
                mvx, mvy = float(np.median(pv[0])), float(np.median(pv[1]))
                sp = np.hypot(mvx, mvy)
                if sp < 2.0 or np.hypot(pv[0] - mvx, pv[1] - mvy).max() > 0.05 * sp + 0.05:
                    continue
                (dx, dy), resp = cv2.phaseCorrelate(prev[y:y + 64, x:x + 64], cur[y:y + 64, x:x + 64], win)
                if resp < 0.3:
                    continue
                ratios.append(float((dx * mvx + dy * mvy) / (sp * sp)))
    curve = {str(s): float(np.nanmean(v)) for s, v in res.items() if v}
    best = min(curve, key=curve.get) if curve else None
    return {'pairs': len(res[1.0]), 'median_speed_px_per_frame': float(np.median(speeds)) if speeds else None, 'residual_by_scale': curve,
            'best_scale': best, 'phase_patches': len(ratios),
            'phase_ratio_median': float(np.median(ratios)) if ratios else None,
            'phase_ratio_p10_p90': [float(np.percentile(ratios, 10)), float(np.percentile(ratios, 90))] if ratios else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    run = Path(a.run)
    out = {'run': str(run)}
    for cond in ('fixed60', 'fixed300'):
        out[cond] = r = check(run, cond)
        c = r['residual_by_scale']
        print(f"{cond}: pairs {r['pairs']}, median speed {r['median_speed_px_per_frame']:.2f} px/frame, best scale {r['best_scale']}, "
              f"residual s=0.90 {c.get('0.9', float('nan')):.3f} s=1.00 {c.get('1.0', float('nan')):.3f} s=1.10 {c.get('1.1', float('nan')):.3f}; "
              f"phase patches {r['phase_patches']}, ratio median {r['phase_ratio_median']}, p10/p90 {r['phase_ratio_p10_p90']}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
