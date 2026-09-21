"""Analyze paired-pattern On/Off without changing the temporal luma selector."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from analyze_temporal_contrast_reference import rgb, luma, sha
from create_temporal_contrast_playback import encode, gif

ON = ('O-T2X-R', 'ABL-ScalarWeight-001-R')
OFF = ('ABL-Standard-PatternOff-R', 'ABL-ScalarWeight-001-PatternOff-R')
MASK = ('DBG-ContrastMask-001-R', 'DBG-ContrastMask-001-PatternOff-R')
SPATIAL = ('DBG-CurrentSpatial-R', 'DBG-CurrentSpatial-PatternOff-R')
MODES = (*ON, *OFF)
WINDOWS = {'initial_still': (20, 60), 'moving': (60, 180), 'transition': (160, 220), 'late_still': (200, 240)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene', required=True, choices=('bistro', 'minecraft'))
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--summary', type=Path, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    bench = root / 'Projects/CMAA2/AutoBench'
    receipts = json.loads(a.receipt.read_text(encoding='utf-8-sig'))
    receipt = [r for r in receipts if r['scene'] == a.scene and r['phase'] == 'JitterCapture']
    assert len(receipt) == 1
    capture = Path(receipt[0]['report']).parent
    report = Path(receipt[0]['report']).read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in report and f'Scene: {a.scene}' in report
    checks = [r for r in csv.reader(report.splitlines()) if r and r[0].strip() == 'pattern_check']
    assert len(checks) == 2400 and all(r[4].strip() == 'PASS' for r in checks)
    qpath = bench / 'ContrastReferenceAnalysis' / a.scene / 'reference-quality.json'
    q = json.loads(qpath.read_text(encoding='utf-8'))
    old = Path(q['capture'])
    reference = Path(q['quality_capture']) / 'SS-Reference'
    scalar_prior = bench / ('20260921_004743' if a.scene == 'bistro' else '20260921_004230')
    expected = [f'frame_{i:05d}.png' for i in range(240)]
    names = (*MODES, *MASK, *SPATIAL, *(m+'-Repeat' for m in OFF))
    for name in names:
        assert [f.name for f in sorted((capture/name).glob('*.png'))] == expected
    for name in names:
        rows = [r for r in checks if r[1].strip() == name]
        assert [int(r[2]) for r in rows] == list(range(240))
        assert all(r[3].strip() == ('Off' if 'PatternOff' in name else 'On') for r in rows)
    pairs = [(capture/ON[0], old/ON[0]), (capture/ON[1], scalar_prior/ON[1]),
             (capture/MASK[0], old/MASK[0]), (capture/SPATIAL[0], old/SPATIAL[0])]
    pairs += [(capture/m, capture/(m+'-Repeat')) for m in OFF]
    for left, right in pairs:
        for f in expected:
            assert sha(left/f) == sha(right/f), (left, right, f)
    print(f'{a.scene}: 2400 pattern checks, 1440 exact bridge/repeat comparisons PASS', flush=True)
    a.output.mkdir(parents=True, exist_ok=True)
    rows, counts, hashes, stream_hashes = [], [], {m: [] for m in MODES}, {m: hashlib.sha256() for m in MODES}
    prev, prev_ref, prev_mask = {}, None, {}
    for i, f in enumerate(expected):
        ref = rgb(reference/f)
        ry = luma(ref)
        images = {m: rgb(capture/m/f) for m in MODES}
        for j, modes in enumerate((ON, OFF)):
            raw_mask = rgb(capture/MASK[j]/f)
            assert np.all((raw_mask == 0) | (raw_mask == 255)) and np.all(raw_mask == raw_mask[:, :, :1])
            mask = raw_mask[:, :, 0] == 255
            spatial = rgb(capture/SPATIAL[j]/f)
            assert np.array_equal(images[modes[1]][mask], images[modes[0]][mask])
            assert np.array_equal(images[modes[1]][~mask], spatial[~mask])
            if i == 0:
                assert all(np.array_equal(images[m], spatial) for m in modes)
            counts.append({'frame': i, 'pattern': 'On' if j == 0 else 'Off', 'selected_pixels': int(mask.sum()),
                           'selected_percent': 100*float(mask.mean()),
                           'mask_switch_percent': 100*float(np.mean(mask != prev_mask[j])) if j in prev_mask else None})
            prev_mask[j] = mask
        for m, im in images.items():
            pixels = im.tobytes()
            hashes[m].append(hashlib.sha256(pixels).hexdigest())
            stream_hashes[m].update(pixels)
            y = luma(im)
            d = im.astype(np.float32) - ref.astype(np.float32)
            mse = float(np.square(d).mean(dtype=np.float64))
            rows.append({'frame': i, 'mode': m, 'rgb_mae': float(np.abs(d).mean(dtype=np.float64)),
                         'psnr_db': 10*math.log10(255**2/mse) if mse else None,
                         'rgb_step': float(np.abs(im.astype(np.int16)-prev[m][0].astype(np.int16)).mean()) if m in prev else None,
                         'luma_step': float(np.abs(y-prev[m][1]).mean(dtype=np.float64)) if m in prev else None,
                         'reference_delta_residual': float(np.abs((y-prev[m][1])-(ry-prev_ref)).mean(dtype=np.float64)) if m in prev else None})
            prev[m] = (im, y)
        prev_ref = ry
        if i % 60 == 59:
            print(f'{a.scene}: {i+1}/240 frames, exact selection semantics PASS', flush=True)
    result = {'scene': a.scene, 'classification': 'Pattern/selection interaction diagnosis; not final eight-case or performance result',
              'receipt': receipt[0], 'report_sha256': sha(Path(receipt[0]['report'])),
              'reference_analysis_sha256': sha(qpath), 'reference': str(reference),
              'pattern_checks': 2400, 'bridge_and_repeat_comparisons': 1440, 'mismatches': 0,
              'selection_semantics_frames': 480, 'first_frame_seed_checks': 4,
              'pixel_stream_sha256': {m: h.hexdigest() for m, h in stream_hashes.items()},
              'windows': {}, 'coverage': {}, 'static_hashes': {}}
    for window, (start, end) in WINDOWS.items():
        result['windows'][window], result['coverage'][window] = {}, {}
        for m in MODES:
            selected = [r for r in rows if r['mode'] == m and start <= r['frame'] < end]
            result['windows'][window][m] = {k: float(np.mean([r[k] for r in selected if r[k] is not None])) for k in selected[0] if k not in ('mode', 'frame')}
        for pattern in ('On', 'Off'):
            selected = [r for r in counts if r['pattern'] == pattern and start <= r['frame'] < end]
            result['coverage'][window][pattern] = {k: float(np.mean([r[k] for r in selected if r[k] is not None])) for k in ('selected_pixels', 'selected_percent', 'mask_switch_percent')}
        if 'still' in window:
            result['static_hashes'][window] = {m: {'unique_rgb_frames': len(set(h[start:end])),
                'lag2_mismatches': sum(x != y for x, y in zip(h[start:end-2], h[start+2:end]))} for m, h in hashes.items()}
    for filename, data in (('per-frame-quality.csv', rows), ('per-frame-coverage.csv', counts)):
        with (a.output/filename).open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=data[0]); w.writeheader(); w.writerows(data)
    roi = (420, 590, 900, 910) if a.scene == 'bistro' else (720, 240, 1200, 560)
    labels = ('Original | Pattern On', 'ScalarWeight | Pattern On', 'Full-screen | Pattern Off', 'ScalarWeight | Pattern Off')

    def render(i, slow=False):
        canvas = Image.new('RGB', (1920, 350), '#15181c')
        draw = ImageDraw.Draw(canvas)
        for col, (mode, label) in enumerate(zip(MODES, labels)):
            with Image.open(capture/mode/f'frame_{i:05d}.png') as im:
                canvas.paste(im.convert('RGB').crop(roi), (col*480, 30))
            draw.text((col*480+5, 8), label + f' | f{i:03d} | ' + ('0.5x' if slow else '1x'), fill='white')
        return canvas

    result['roi'] = roi
    result['video'] = encode(a.output/'four-way-60fps.mp4', render, 240)
    result['gifs'] = [gif(a.output/f'{w}.gif', render, start, end) for w, start, end in
                      [('moving', 90, 150), ('transition', 160, 220), ('still', 200, 220)]]
    for window, indices in (('moving', range(110, 114)), ('still', range(200, 204))):
        sheet = Image.new('RGB', (1920, 1400), '#15181c')
        for col, i in enumerate(indices):
            frame = render(i)
            for row in range(4):
                sheet.paste(frame.crop((row*480, 0, (row+1)*480, 350)), (col*480, row*350))
        sheet.save(a.output/f'{window}-sequence.png')
    a.summary.parent.mkdir(parents=True, exist_ok=True)
    a.summary.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(f'{a.scene}: PASS, video frame/PTS and fixed-palette GIF verified', flush=True)


if __name__ == '__main__':
    main()
