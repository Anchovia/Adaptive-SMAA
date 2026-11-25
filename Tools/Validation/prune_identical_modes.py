"""Removes capture folders whose every frame was verified byte-identical to an existing reference capture.

Only modes listed here are touched, and only after re-checking SHA-256 against the reference frame by frame. A manifest
(mode, frame, SHA-256, reference path) is written first, so the deleted frames can be traced to the reference files that
remain on disk.

usage: python prune_identical_modes.py --capture <run> --c29-spatial <run> --c29-temporal <run> --c30 <run> --manifest <json>
"""
import argparse, hashlib, json, shutil
from pathlib import Path

FINAL = 'A-ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha+HistoryVelocityPingPongCross5'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    for k in ('capture', 'c29-spatial', 'c29-temporal', 'c30', 'manifest'):
        ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    cap, s29, t29, c30 = map(Path, (a.capture, a.c29_spatial, a.c29_temporal, a.c30))
    pairs = {'O-1X': s29 / 'O-1X', 'O-High': s29 / 'O-High', 'O-Medium': s29 / 'O-Medium', 'O-Low': s29 / 'O-Low',
             'AT-Ultra': t29 / FINAL, 'AT-High': c30 / 'AT-High', 'AT-Medium': c30 / 'AT-Medium', 'AT-Low': c30 / 'AT-Low',
             'ATOff-Ultra': s29 / 'A-1X', 'ATOff-High': s29 / 'A-High', 'ATOff-Medium': s29 / 'A-Medium', 'ATOff-Low': s29 / 'A-Low'}
    manifest = {'capture': str(cap), 'modes': {}}
    for mode, ref in pairs.items():
        rows = []
        for k in range(240):
            n, r = cap / mode / f'frame_{k:05d}.png', ref / f'frame_{k:05d}.png'
            hn, hr = sha(n), sha(r)
            if hn != hr:
                raise SystemExit(f'{mode} frame {k} differs from {r}; nothing removed')
            rows.append([k, hn])
        manifest['modes'][mode] = {'reference': str(ref), 'frames': rows}
    Path(a.manifest).write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')
    for mode in pairs:
        shutil.rmtree(cap / mode)
    print('removed', len(pairs), 'mode folders; manifest', a.manifest)


if __name__ == '__main__':
    main()
