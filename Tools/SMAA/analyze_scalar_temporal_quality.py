"""Bridge ScalarWeight to evaluated RGB sequences; diagnose static phase instability.

No renderer changes or GPU runs. Existing CGVQM scores are inherited, not rerun.
Screen-fixed ROIs come from the earlier review, before this analysis.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from create_temporal_contrast_playback import encode, gif

NATIVE = 'O-T2X-R'
BRANCH = 'ABL-Contrast-001-R'
SCALAR = 'ABL-ScalarWeight-001-R'
MASK = 'DBG-ContrastMask-001-R'
ROIS = {'bistro': (420, 590, 900, 910), 'minecraft': (720, 240, 1200, 560)}
WINDOWS = {'moving': (60, 180), 'transition': (160, 220), 'late_still': (200, 240)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rgb(path):
    with Image.open(path) as im:
        assert im.size == (1920, 1061), path
        return np.array(im.convert('RGB'))


def luminance(im):
    # Display-encoded RGB levels, NOT the linear-light shader selector.
    return im.astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)


def gradients(y):
    return np.stack((y[:-1, 1:] - y[:-1, :-1], y[1:, :-1] - y[:-1, :-1]))


def verify_inherited_cgvqm(result, bench):
    """Rehash current RGB inputs against the original official run records."""
    for scene, summary in result['scenes'].items():
        capture, reference = Path(summary['capture']), Path(summary['reference_capture'])
        verified = []
        for window in ('moving', 'transition'):
            start, end = WINDOWS[window]
            streams = {m: hashlib.sha256() for m in (NATIVE, SCALAR, 'SS-Reference')}
            for i in range(start, end):
                for mode, h in streams.items():
                    folder = reference if mode == 'SS-Reference' else capture
                    h.update(i.to_bytes(8, 'little', signed=False))
                    h.update(rgb(folder / mode / f'frame_{i:05d}.png').tobytes())
            for mode, prior in ((NATIVE, NATIVE), (SCALAR, BRANCH)):
                record_path = bench / 'ContrastReferenceAnalysis' / scene / 'CGVQM2' / window / prior / 'CGVQM-Results.json'
                record = json.loads(record_path.read_text(encoding='utf-8'))
                assert record['configuration'] == {'fps': 60, 'patch_scale': 4, 'patch_pool': 'mean', 'models': ['2'], 'reference_index_offset': 0}
                assert record['test_sequence']['pixel_sha256'] == streams[mode].hexdigest()
                assert record['reference_sequence']['pixel_sha256'] == streams['SS-Reference'].hexdigest()
                for key in ('test_round_trip', 'reference_round_trip'):
                    assert record[key]['mismatched_values'] == record[key]['max_absolute_difference'] == 0
                    assert record[key]['decoded_frames'] == end-start
                assert record['results']['CGVQM-2']['score_higher_is_better'] == summary['inherited_cgvqm'][window][mode]
                verified.append({'window': window, 'mode': mode, 'record_sha256': sha(record_path),
                                 'test_pixel_sha256': streams[mode].hexdigest(),
                                 'reference_pixel_sha256': streams['SS-Reference'].hexdigest()})
            print(f'{scene}/{window}: original CGVQM test/reference pixel hashes PASS', flush=True)
        summary['cgvqm_input_verification'] = verified


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--summary', required=True, type=Path)
    p.add_argument('--verify-inherited-only', action='store_true')
    a = p.parse_args()
    bench = a.root / 'Projects/CMAA2/AutoBench'
    if a.verify_inherited_only:
        result = json.loads(a.summary.read_text(encoding='utf-8'))
        verify_inherited_cgvqm(result, bench)
        a.summary.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        return
    receipts = json.loads((a.root / 'tmp/temporal-cost-final-runs.json').read_text(encoding='utf-8'))
    captures = {r['scene']: Path(r['report']).parent for r in receipts if r['phase'] == 'Capture'}
    result = {'classification': 'Engineering quality gate, not final eight-case results',
              'selector_threshold': .01, 'frames_per_scene': 240,
              'quality_scores': 'Reused only after exact sequence bridge; no new CGVQM run',
              'scenes': {}}
    expected = [f'frame_{i:05d}.png' for i in range(240)]
    for scene, capture in captures.items():
        analysis = bench / 'ContrastReferenceAnalysis' / scene
        q = json.loads((analysis / 'reference-quality.json').read_text(encoding='utf-8'))
        old, quality = Path(q['capture']), Path(q['quality_capture'])
        out = a.output / scene
        out.mkdir(parents=True, exist_ok=True)
        reports = list(capture.glob('*_results.csv'))
        assert len(reports) == 1
        report = reports[0].read_text(encoding='utf-8-sig')
        for token in ('Aggregate: PASS', f'Scene: {scene}', 'Frames: 240', '1920 x 1061'):
            assert token in report
        qr = list(quality.glob('*_results.csv'))
        assert len(qr) == 1 and sha(qr[0]) == q['quality_report_sha256']
        folders = [capture / m for m in (NATIVE, BRANCH, SCALAR, MASK)]
        folders += [old / m for m in (NATIVE, BRANCH, MASK, 'DBG-CurrentSpatial-R')]
        folders += [quality / m for m in (NATIVE, MASK, 'SS-Reference')]
        for folder in folders:
            assert [f.name for f in sorted(folder.glob('*.png'))] == expected, folder
        bridges = [(capture / SCALAR, old / BRANCH), (capture / SCALAR, capture / BRANCH),
                   (capture / NATIVE, old / NATIVE), (capture / MASK, old / MASK),
                   (capture / NATIVE, quality / NATIVE), (capture / MASK, quality / MASK)]
        for left, right in bridges:
            for name in expected:
                assert sha(left / name) == sha(right / name), (left, right, name)
        print(f'{scene}: {len(bridges)*240} exact PNG bridge comparisons PASS', flush=True)
        streams = {m: hashlib.sha256() for m in (NATIVE, SCALAR)}
        still_hashes = {m: [] for m in (NATIVE, SCALAR)}
        static_rows, roi_rows = [], []
        previous = None
        x0, y0, x1, y1 = ROIS[scene]
        for i, name in enumerate(expected):
            images = {m: rgb(capture / m / name) for m in (NATIVE, SCALAR)}
            for m, im in images.items():
                streams[m].update(im.tobytes())
                if i >= 200:
                    still_hashes[m].append(hashlib.sha256(im.tobytes()).hexdigest())
            mask_rgb = rgb(capture / MASK / name)
            assert np.all((mask_rgb == 0) | (mask_rgb == 255))
            assert np.all(mask_rgb == mask_rgb[:, :, :1])
            mask = mask_rgb[:, :, 0] == 255
            spatial = rgb(old / 'DBG-CurrentSpatial-R' / name)
            assert np.array_equal(images[SCALAR][mask], images[NATIVE][mask])
            assert np.array_equal(images[SCALAR][~mask], spatial[~mask])
            ref = rgb(quality / 'SS-Reference' / name)[y0:y1, x0:x1]
            ref_y = luminance(ref)
            ref_g = gradients(ref_y)
            for m, im in images.items():
                tile = im[y0:y1, x0:x1]
                y = luminance(tile)
                g = gradients(y)
                roi_rows.append({'frame': i, 'mode': m,
                                 'rgb_mae': float(np.abs(tile.astype(np.float32) - ref).mean()),
                                 'gradient_mae': float(np.abs(g - ref_g).mean()),
                                 'gradient_energy_ratio': float(np.abs(g).mean() / np.abs(ref_g).mean())})
            if i >= 201:
                delta = np.abs(images[SCALAR].astype(np.int16) - previous['scalar'].astype(np.int16))
                changed = np.any(delta != 0, axis=2)
                groups = {'both_unselected': ~mask & ~previous['mask'],
                          'both_selected': mask & previous['mask'],
                          'selection_switched': mask != previous['mask']}
                static_rows.append({'frame': i, 'scalar_rgb_step': float(delta.mean()),
                                    'native_rgb_step': float(np.abs(images[NATIVE].astype(np.int16) - previous['native'].astype(np.int16)).mean()),
                                    'changed_pixels': int(changed.sum()),
                                    'groups': {k: {'pixels': int(v.sum()), 'changed_pixels': int((v & changed).sum()),
                                                   'rgb_absolute_sum': int(delta[v].sum())} for k, v in groups.items()}})
            previous = {'scalar': images[SCALAR], 'native': images[NATIVE], 'mask': mask}
            if i % 60 == 59:
                print(f'{scene}: frame {i+1}/240 semantics and static diagnostics PASS', flush=True)
        for mode, prior in ((NATIVE, NATIVE), (SCALAR, BRANCH)):
            assert streams[mode].hexdigest() == q['test_full_sequence_pixel_sha256'][prior]
        cg = json.loads((analysis / 'cgvqm-comparison.json').read_text(encoding='utf-8'))
        summary = {'capture': str(capture), 'old_capture': str(old), 'reference_capture': str(quality),
                   'report_sha256': sha(reports[0]), 'prior_quality_json_sha256': sha(analysis / 'reference-quality.json'),
                   'cgvqm_json_sha256': sha(analysis / 'cgvqm-comparison.json'),
                   'bridge_comparisons': len(bridges)*240, 'bridge_mismatches': 0,
                   'selection_semantics_frames': 240, 'selection_semantics_mismatches': 0,
                   'pixel_stream_sha256': {m: h.hexdigest() for m, h in streams.items()},
                   'coverage': q['coverage']['all'][BRANCH],
                   'inherited_quality': {w: {m: q['quality'][w][p] for m, p in ((NATIVE, NATIVE), (SCALAR, BRANCH))} for w in WINDOWS},
                   'inherited_cgvqm': {w: {m: cg[w][p]['score'] for m, p in ((NATIVE, NATIVE), (SCALAR, BRANCH))} for w in ('moving', 'transition')},
                   'roi': ROIS[scene], 'roi_metrics': {}, 'late_still': {}, 'static_steps': static_rows}
        for w, (start, end) in WINDOWS.items():
            summary['roi_metrics'][w] = {}
            for m in (NATIVE, SCALAR):
                rows = [r for r in roi_rows if r['mode'] == m and start <= r['frame'] < end]
                summary['roi_metrics'][w][m] = {k: float(np.mean([r[k] for r in rows])) for k in ('rgb_mae', 'gradient_mae', 'gradient_energy_ratio')}
        for m, hashes in still_hashes.items():
            summary['late_still'][m] = {'unique_rgb_frames': len(set(hashes)),
                                       'lag2_mismatches': sum(x != y for x, y in zip(hashes, hashes[2:])),
                                       'mean_adjacent_rgb_step': float(np.mean([r['native_rgb_step' if m == NATIVE else 'scalar_rgb_step'] for r in static_rows]))}
        total = sum(g['rgb_absolute_sum'] for r in static_rows for g in r['groups'].values())
        summary['late_still']['change_attribution'] = {
            k: {'mean_changed_pixels': float(np.mean([r['groups'][k]['changed_pixels'] for r in static_rows])),
                'fraction_of_rgb_change': sum(r['groups'][k]['rgb_absolute_sum'] for r in static_rows) / total}
            for k in static_rows[0]['groups']}
        paths = [quality / 'SS-Reference', capture / NATIVE, capture / SCALAR]
        labels = ['SS spatial reference', 'Original T2X-R', 'ScalarWeight 0.01']

        def render(i, slow=False):
            canvas = Image.new('RGB', (1440, 350), '#15181c')
            draw = ImageDraw.Draw(canvas)
            for col, (folder, label) in enumerate(zip(paths, labels)):
                with Image.open(folder / f'frame_{i:05d}.png') as im:
                    canvas.paste(im.convert('RGB').crop(ROIS[scene]), (col*480, 30))
                draw.text((col*480+5, 8), f'{label} | f{i:03d} | ' + ('0.5x' if slow else '1x'), fill='white')
            return canvas

        summary['video'] = encode(out / 'detail-60fps.mp4', render, 240)
        summary['gifs'] = [gif(out / f'{w}.gif', render, start, end) for w, start, end in
                           [('moving', 90, 150), ('transition', 160, 220), ('still', 200, 220)]]
        for label, indices in [('moving', range(110, 114)), ('transition', range(179, 183)), ('still', range(200, 204))]:
            sheet = Image.new('RGB', (1920, 1050), '#15181c')
            for col, i in enumerate(indices):
                frame = render(i)
                for row in range(3):
                    sheet.paste(frame.crop((row*480, 0, (row+1)*480, 350)), (col*480, row*350))
            sheet.save(out / f'{label}-sequence.png')
        # Diagnostic magnification only; fixed scale shared by all columns.
        sheet = Image.new('RGB', (1440, 350), '#15181c')
        draw = ImageDraw.Draw(sheet)
        for col, (folder, label) in enumerate(zip(paths, labels)):
            d = np.abs(rgb(folder / 'frame_00201.png').astype(np.int16) - rgb(folder / 'frame_00200.png').astype(np.int16))
            tile = np.clip(d[y0:y1, x0:x1]*8, 0, 255).astype(np.uint8)
            sheet.paste(Image.fromarray(tile), (col*480, 30))
            draw.text((col*480+5, 8), label + ' | |f201-f200| x8', fill='white')
        sheet.save(out / 'still-difference-x8.png')
        result['scenes'][scene] = summary
        print(f'{scene}: 60 FPS decode/PTS and GIF checks PASS', flush=True)
    verify_inherited_cgvqm(result, bench)
    a.summary.parent.mkdir(parents=True, exist_ok=True)
    a.summary.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
