"""Current-read de-jitter gate: controls, changed masks, reconstruction and timing."""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics as st
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from analyze_temporal_contrast_reference import rgb, luma, edge, sha
from create_temporal_contrast_playback import encode, gif

NATIVE = 'O-T2X-R'
POINT = 'ABL-ScalarCurrentLinear-001-R'
LINEAR = 'ABL-CurrentDeJitter-R'
SCALAR = 'ABL-ScalarWeight-001-R'
SLINEAR = 'ABL-ScalarDeJitter-001-R'
MODES = (NATIVE, SCALAR, POINT, LINEAR, SLINEAR)
VISIBLE = (NATIVE, LINEAR, SCALAR, SLINEAR)
MASK, SPATIAL = 'DBG-ContrastMask-001-R', 'DBG-CurrentSpatial-R'
DMASK, DBASE = 'DBG-DeJitterMask-001-R', 'DBG-DeJitterSpatial-R'
WINDOWS = {'initial_still': (20, 60), 'moving': (60, 180),
           'transition': (160, 220), 'late_still': (200, 240)}
METRICS = ('SMAA', 'Spatial', 'Resolve', 'WholeFrame', 'WallFrame')


def read_receipt(path, scene, phase):
    receipts = json.loads(path.read_text(encoding='utf-8-sig'))
    assert len({r['report'] for r in receipts}) == len(receipts)
    assert len({r['executable_sha256'] for r in receipts}) == 1
    assert all(r['window'] == 'hidden' for r in receipts)
    for prev, nxt in zip(receipts, receipts[1:]):
        assert datetime.fromisoformat(prev['completed_utc']) <= datetime.fromisoformat(nxt['started_utc'])
    records = [r for r in receipts if r['scene'] == scene and r['phase'] == phase]
    assert len(records) == 1
    record = records[0]
    report = Path(record['report'])
    assert sha(report) == record['report_sha256'].lower()
    text = report.read_text(encoding='utf-8-sig')
    for token in ('Aggregate: PASS', f'Scene: {scene}', '1920 x 1061',
                  'Current de-jitter gate: one linear current read', 'API:  DirectX11'):
        assert token in text, token
    assert 'Aggregate: FAIL' not in text
    return record, report.parent, text


def quality(a):
    record, capture, text = read_receipt(a.receipt, a.scene, 'Capture')
    checks = [[s.strip() for s in r] for r in csv.reader(text.splitlines())
              if r and r[0].strip() == 'pattern_check']
    names = (*MODES, MASK, SPATIAL, DMASK, DBASE, LINEAR+'-Repeat', SLINEAR+'-Repeat')
    assert len(checks) == 2640
    expected = [f'frame_{i:05d}.png' for i in range(240)]
    for name in names:
        assert [f.name for f in sorted((capture/name).glob('*.png'))] == expected
        group = [r for r in checks if r[1] == name]
        assert [int(r[2]) for r in group] == list(range(240))
        assert all(r[3:5] == ['On', 'PASS'] for r in group)
    bench = Path(__file__).resolve().parents[2]/'Projects/CMAA2/AutoBench'
    qpath = bench/'ContrastReferenceAnalysis'/a.scene/'reference-quality.json'
    q = json.loads(qpath.read_text(encoding='utf-8'))
    old, reference = Path(q['capture']), Path(q['quality_capture'])/'SS-Reference'
    reference_reports = list(Path(q['quality_capture']).glob('*_results.csv'))
    assert len(reference_reports) == 1 and sha(reference_reports[0]) == q['quality_report_sha256']
    scalar_prior = bench/('20260921_004743' if a.scene == 'bistro' else '20260921_004230')
    pairs = [(capture/NATIVE, old/NATIVE), (capture/SCALAR, scalar_prior/SCALAR),
             (capture/MASK, old/MASK), (capture/SPATIAL, old/SPATIAL),
             (capture/POINT, capture/SCALAR),
             (capture/LINEAR, capture/(LINEAR+'-Repeat')),
             (capture/SLINEAR, capture/(SLINEAR+'-Repeat'))]
    for left, right in pairs:
        for f in expected:
            assert sha(left/f) == sha(right/f), (left, right, f)
    print(f'{a.scene}: 2640 pattern checks, 1680 control/repeat hash comparisons PASS', flush=True)
    rows, counts, prev, hashes = [], [], {}, {m: [] for m in VISIBLE}
    streams = {m: hashlib.sha256() for m in VISIBLE}
    prev_ref = prev_mask = None
    first_seed_differences = {}
    mirror_checks = []
    lut = np.arange(256, dtype=np.float64)/255
    lut = np.where(lut <= .04045, lut/12.92, ((lut+.055)/1.055)**2.4)
    for i, f in enumerate(expected):
        ref = rgb(reference/f)
        ry = luma(ref)
        ref_edge = edge(ry)
        spatial = rgb(capture/SPATIAL/f)
        raw = rgb(capture/MASK/f)
        assert np.all((raw == 0) | (raw == 255)) and np.all(raw == raw[:, :, :1])
        mask = raw[:, :, 0] == 255
        images = {m: rgb(capture/m/f) for m in VISIBLE}
        dbase = rgb(capture/DBASE/f)
        draw = rgb(capture/DMASK/f)
        assert np.all((draw == 0) | (draw == 255)) and np.all(draw == draw[:, :, :1])
        dmask = draw[:, :, 0] == 255
        for full, selected, use_mask, base_image in ((NATIVE, SCALAR, mask, spatial), (LINEAR, SLINEAR, dmask, dbase)):
            assert np.array_equal(images[selected][use_mask], images[full][use_mask]), (i, selected, 'selected')
            assert np.array_equal(images[selected][~use_mask], base_image[~use_mask]), (i, selected, 'unselected')
        if i == 0:
            first_seed_differences = {m: int(np.count_nonzero(im != (dbase if m in (LINEAR, SLINEAR) else spatial))) for m, im in images.items()}
            assert all(v == 0 for v in first_seed_differences.values())
        if i in (0, 1, 90, 91, 200, 201):
            phase = .25 if i % 2 == 0 else -.25
            linear = lut[spatial]
            # Quarter-pixel bilinear: .75 center + .25 neighbor on each axis.
            sx = np.clip(np.arange(1920) + (1 if phase > 0 else -1), 0, 1919)
            sy = np.clip(np.arange(1061) + (1 if phase > 0 else -1), 0, 1060)
            horizontal = .75*linear + .25*linear[:, sx]
            filtered = .75*horizontal + .25*horizontal[sy]
            encoded = np.where(filtered <= .0031308, filtered*12.92, 1.055*filtered**(1/2.4)-.055)
            cpu = np.floor(np.clip(encoded*255, 0, 255)+.5).astype(np.uint8)
            delta = np.abs(cpu.astype(np.int16)-dbase.astype(np.int16))
            check = dict(frame=i, phase=phase, max_rgb_error=int(delta.max()), mean_rgb_error=float(delta.mean()),
                         differing_channels=int(np.count_nonzero(delta)))
            # Preserve the failed <=2-level ideal-CPU assumption; do not relabel
            # it as an exact CPU mirror. Validate the production sampling on an
            # independently uploaded sRGB texture through a bounded GPU probe.
            check['ideal_cpu_within_two_rgb_levels'] = check['max_rgb_error'] <= 2
            root = Path(__file__).resolve().parents[2]
            probe_dir = root/'tmp/dejitter-probe'
            rgba = np.full((1061,1920,4),255,dtype=np.uint8);rgba[:,:,:3]=spatial
            input_path, output_path = probe_dir/(a.scene+'-input.bin'), probe_dir/(a.scene+'-output.bin')
            rgba.tofile(input_path)
            probe = subprocess.run([str(probe_dir/'probe.exe'), str(root/'Projects/CMAA2/SMAA/TemporalDeJitterProbe.hlsl'),
                str(input_path), str(output_path), '1' if phase>0 else '2'], capture_output=True, text=True, timeout=30)
            assert probe.returncode == 0, probe.stdout+probe.stderr
            sample = np.fromfile(output_path,dtype=np.float32).reshape(1061,1920,4)[:,:,:3].astype(np.float64)
            assert np.isfinite(sample).all()
            encoded_probe = np.where(sample<=.0031308,sample*12.92,1.055*np.maximum(sample,0)**(1/2.4)-.055)
            gpu_probe = np.floor(np.clip(encoded_probe*255,0,255)+.5).astype(np.uint8)
            probe_delta = np.abs(gpu_probe.astype(np.int16)-dbase.astype(np.int16))
            check['uploaded_texture_gpu_probe_max_rgb_error'] = int(probe_delta.max())
            check['uploaded_texture_gpu_probe_mean_rgb_error'] = float(probe_delta.mean())
            assert check['uploaded_texture_gpu_probe_max_rgb_error'] <= 1, check
            mirror_checks.append(check)
        counts.append(dict(frame=i, selected_pixels=int(dmask.sum()), selected_percent=float(dmask.mean()*100),
            original_selected_percent=float(mask.mean()*100), selection_change_percent=float(np.mean(mask != dmask)*100),
            removed_percent=float(np.mean(mask & ~dmask)*100), added_percent=float(np.mean(~mask & dmask)*100),
            mask_switch_percent=float(np.mean(dmask != prev_mask)*100) if prev_mask is not None else None))
        for m, im in images.items():
            pixels = im.tobytes()
            hashes[m].append(hashlib.sha256(pixels).hexdigest())
            streams[m].update(pixels)
            y = luma(im)
            d = im.astype(np.float32)-ref.astype(np.float32)
            mse = float(np.square(d).mean(dtype=np.float64))
            rows.append(dict(frame=i, mode=m, rgb_mae=float(np.abs(d).mean(dtype=np.float64)),
                psnr_db=10*math.log10(255**2/mse) if mse else None,
                edge_reference_ratio=edge(y)/ref_edge,
                rgb_step=float(np.abs(im.astype(np.int16)-prev[m][0].astype(np.int16)).mean()) if m in prev else None,
                reference_delta_residual=float(np.abs((y-prev[m][1])-(ry-prev_ref)).mean(dtype=np.float64)) if m in prev else None))
            prev[m] = im, y
        prev_ref, prev_mask = ry, dmask
        if i % 60 == 59:
            print(f'{a.scene}: {i+1}/240 frames, exact selection semantics PASS', flush=True)
    result = dict(scene=a.scene, classification='Current-read de-jitter engineering gate; changed selector and current alpha, unchanged Point history; spatial proxy, not temporal ground truth',
        receipt=record, reference_analysis_sha256=sha(qpath), reference=str(reference),
        pattern_checks=2640, bridge_and_repeat_comparisons=1680, mismatches=0,
        selection_semantics_frames=480, first_frame_differing_channels=first_seed_differences, cpu_spatial_mirror=mirror_checks,
        pixel_stream_sha256={m: h.hexdigest() for m, h in streams.items()}, windows={}, coverage={}, static_hashes={})
    for window, (start, end) in WINDOWS.items():
        result['windows'][window] = {}
        for m in VISIBLE:
            group = [r for r in rows if r['mode'] == m and start <= r['frame'] < end]
            result['windows'][window][m] = {k: st.mean(r[k] for r in group if r[k] is not None)
                for k in group[0] if k not in ('mode', 'frame')}
        group = [r for r in counts if start <= r['frame'] < end]
        result['coverage'][window] = {k: st.mean(r[k] for r in group if r[k] is not None)
            for k in group[0] if k != 'frame'}
        if 'still' in window:
            result['static_hashes'][window] = {m: dict(unique_rgb_frames=len(set(h[start:end])),
                lag2_mismatches=sum(x != y for x, y in zip(h[start:end-2], h[start+2:end]))) for m, h in hashes.items()}
    a.output.mkdir(parents=True, exist_ok=True)
    for filename, data in (('per-frame-quality.csv', rows), ('per-frame-coverage.csv', counts)):
        with (a.output/filename).open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=data[0]); w.writeheader(); w.writerows(data)
    roi = (420, 590, 900, 910) if a.scene == 'bistro' else (720, 240, 1200, 560)
    labels = ('Original T2X-R', 'Full current de-jitter', 'Scalar original', 'Scalar current de-jitter')

    def render(i, slow=False):
        canvas = Image.new('RGB', (1920, 350), '#15181c')
        draw = ImageDraw.Draw(canvas)
        for col, (mode, label) in enumerate(zip(VISIBLE, labels)):
            with Image.open(capture/mode/f'frame_{i:05d}.png') as im:
                canvas.paste(im.convert('RGB').crop(roi), (col*480, 30))
            draw.text((col*480+5, 8), label+f' | f{i:03d} | '+('0.5x' if slow else '1x'), fill='white')
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
    print(f'{a.scene}: quality and video verification PASS', flush=True)


def performance(a):
    record, _, text = read_receipt(a.receipt, a.scene, 'Benchmark')
    for token in ('Frames: 4800', 'Warmup: 300', 'Repeats: 4', 'no PNG or candidate readback'):
        assert token in text, token
    assert 'pattern_check,' not in text
    elapsed = re.findall(r'Focused preconditioning elapsed seconds: ([\d.]+)', text)
    assert len(elapsed) == 1 and 30 <= float(elapsed[0]) < 60
    rows, distributions = [], []
    for v in csv.reader(text.splitlines()):
        v = [s.strip() for s in v]
        if v and v[0] == 'timing':
            rows.append(dict(mode=v[1], run=int(v[2]), metric=v[3], samples=int(v[4]),
                             mean_ms=float(v[5]), p95_ms=float(v[6]), threshold=float(v[7])))
        if v and v[0] == 'distribution':
            distributions.append(dict(mode=v[1], run=int(v[2]), metric=v[3], samples=int(v[4]),
                median_ms=float(v[5]), sample_std_ms=float(v[6]), p99_ms=float(v[7]),
                wall_fps=float(v[8]), wall_1pct_low_fps=float(v[9])))
    expected = [(m, run, metric) for run in range(4)
                for m in (MODES if run % 2 == 0 else MODES[::-1]) for metric in METRICS]
    for data in (rows, distributions):
        assert [(r['mode'], r['run'], r['metric']) for r in data] == expected
        assert all(r['samples'] == 4800 for r in data)
    for r, d in zip(rows, distributions):
        assert r['threshold'] == (.01 if r['mode'] in (SCALAR, SLINEAR, POINT) else 0)
        assert all(math.isfinite(r[k]) and r[k] > 0 for k in ('mean_ms', 'p95_ms'))
        assert d['median_ms'] <= r['p95_ms'] <= d['p99_ms']
    means = {m: {} for m in MODES}
    for m in MODES:
        for metric in METRICS:
            values = [r['mean_ms'] for r in rows if r['mode'] == m and r['metric'] == metric]
            means[m][metric] = dict(mean_ms=st.mean(values), run_std_ms=st.stdev(values), run_means_ms=values)
    comparisons = {}
    for candidate, control in ((POINT, SCALAR), (LINEAR, NATIVE), (SLINEAR, POINT),
                               (SLINEAR, SCALAR), (SLINEAR, NATIVE), (SCALAR, NATIVE)):
        comparisons[candidate+' minus '+control] = {}
        for metric in METRICS:
            c, b = means[candidate][metric], means[control][metric]
            diffs = [x-y for x, y in zip(c['run_means_ms'], b['run_means_ms'])]
            comparisons[candidate+' minus '+control][metric] = dict(delta_ms=c['mean_ms']-b['mean_ms'],
                delta_percent=100*(c['mean_ms']/b['mean_ms']-1), slower_runs=sum(d > 0 for d in diffs),
                paired_run_deltas_ms=diffs, forward_mean_delta_ms=st.mean(diffs[::2]), reverse_mean_delta_ms=st.mean(diffs[1::2]))
    result = dict(scene=a.scene, validation='PASS', receipt=record,
        preconditioning_seconds=float(elapsed[0]),
        classification='Four alternating repeats within one process per scene; engineering comparison, not four independent runs or equivalence proof',
        means=means, comparisons=comparisons, timing_rows=rows, distribution_rows=distributions)
    a.summary.parent.mkdir(parents=True, exist_ok=True)
    a.summary.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(scene=a.scene, means=means, comparisons=comparisons), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene', required=True, choices=('bistro', 'minecraft'))
    p.add_argument('--phase', choices=('quality', 'performance'), default='quality')
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--summary', type=Path, required=True)
    a = p.parse_args()
    if a.phase == 'quality':
        assert a.output is not None
        quality(a)
    else:
        performance(a)
