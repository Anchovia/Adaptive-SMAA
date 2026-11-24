"""Temporal-difference error of On and Off binned by the local screen speed, for fixed300 (or fixed60).

Uses Off/On frames and the velocity DDS of a velocity run and SSRef/WeightDebug frames of the full run of the same
scene, direction and start time (same camera path; the Off/On frames of both runs are checked to be byte-identical).
tde60 = |(out_k - out_k-lag) - (ref_k - ref_k-lag)| per pixel (luma), lag = frames per 1/60 s. Pixels: selected at
frame k, texture edges only (relative depth jump below 10%) and at least 8 pixels from a depth edge; binned by |v_k|
in pixels per frame.

usage: python translation_speed_bins.py --vel-run <velocity run root> --full-run <full run root> --cond fixed300 --out <json>
"""
import argparse, hashlib, json
from pathlib import Path

import cv2
import numpy as np

from verify_translation_velocity import load_dds_rg16f, W, H

BINS = [0, 0.5, 1, 2, 4, 8, 16, 1e9]
LUMA = np.array([0.0722, 0.7152, 0.2126], np.float32)  # BGR


def img(p):
    return cv2.imread(str(p), cv2.IMREAD_COLOR).astype(np.float32) @ LUMA


def main():
    ap = argparse.ArgumentParser()
    for k in ('vel-run', 'full-run', 'cond', 'out'):
        ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    vb, fb = Path(a.vel_run) / a.cond, Path(a.full_run) / a.cond
    lag = 1 if a.cond == 'fixed60' else 5
    frames = sorted(int(p.stem.split('_')[1]) for p in (vb / 'On').glob('velocity_*.dds'))
    same = all(hashlib.sha256((vb / m / f'frame_{k:05d}.png').read_bytes()).digest() == hashlib.sha256((fb / m / f'frame_{k:05d}.png').read_bytes()).digest()
               for m in ('Off', 'On') for k in frames)
    acc = {m: np.zeros(len(BINS) - 1) for m in ('Off', 'On')}
    cnt = np.zeros(len(BINS) - 1)
    for k in frames:
        if k - lag not in frames or k - lag <= 0:
            continue
        v = load_dds_rg16f(vb / 'On' / f'velocity_{k:05d}.dds')
        speed = np.hypot(v[..., 0] * W, v[..., 1] * H)
        wd = cv2.imread(str(fb / 'WeightDebug' / f'frame_{k:05d}.png'), cv2.IMREAD_COLOR)  # BGR: B = depth jump, G = selected
        sel = wd[..., 1] >= 255
        depth = sel & (wd[..., 0] >= 51)
        near = cv2.dilate(depth.astype(np.uint8), np.ones((17, 17), np.uint8)).astype(bool)
        mask = sel & ~depth & ~near
        dref = img(fb / 'SSRef' / f'frame_{k:05d}.png') - img(fb / 'SSRef' / f'frame_{k - lag:05d}.png')
        b = np.digitize(speed, BINS) - 1
        for m in ('Off', 'On'):
            t = np.abs(img(vb / m / f'frame_{k:05d}.png') - img(vb / m / f'frame_{k - lag:05d}.png') - dref)
            for i in range(len(BINS) - 1):
                mm = mask & (b == i)
                acc[m][i] += t[mm].sum()
                if m == 'On':
                    cnt[i] += mm.sum()
    rows = []
    for i in range(len(BINS) - 1):
        if cnt[i] < 1000:
            continue
        off, on = acc['Off'][i] / cnt[i], acc['On'][i] / cnt[i]
        rows.append({'speed_px_per_frame': [BINS[i], BINS[i + 1]], 'pixels': int(cnt[i]), 'tde60_off': off, 'tde60_on': on, 'on_vs_off': on / off - 1})
        print(f"|v| {BINS[i]:>4}-{BINS[i + 1]:<6} px {int(cnt[i]):9d}  Off {off:.3f}  On {on:.3f}  On/Off-1 {100 * (on / off - 1):+.1f}%")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({'vel_run': a.vel_run, 'full_run': a.full_run, 'cond': a.cond, 'lag': lag, 'off_on_identical_to_full_run': same, 'bins': rows}, indent=1) + '\n', encoding='utf-8')
    print('Off/On identical to the full run:', same)


if __name__ == '__main__':
    main()
