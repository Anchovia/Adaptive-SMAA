"""Analyze recorded GPU outputs; never launch or modify the renderer.

CPU point-history/weight reconstruction is diagnostic, with a one-level UNORM
rounding tolerance and exclusion of uncertain point-sampling boundaries.
"""
import argparse
import csv
import json
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from edge_quality_inputs import dds, edges, ph, reconstruct, rgb, sha

CASE6 = 'ABL-Spatial-FirstEdge-Stencil-PatternOff-R'
CASE9 = 'F-EagerPreviousFetch'
NATIVE = 'O-T2X-R'
FULL = 'ABL-Spatial-FullScreen-PatternOff-R'
FRAMES = list(range(127, 139)) + list(range(173, 186)) + list(range(189, 196))
WINDOWS = {'moving': range(130, 136), 'transition': range(178, 184), 'still': range(190, 196)}
ROIS = {'bistro': (1230, 582, 1358, 670), 'minecraft': (956, 524, 1020, 620)}
LABELS = ['4 Native / pattern On', '6 Current edge / Off', '9 Previous union / Off',
          'Full screen / Off', 'SS spatial reference']


def read_json(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write_json(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def font(size=14):
    return ImageFont.truetype('C:/Windows/Fonts/consola.ttf', size)


def crop(a, roi):
    x0, y0, x1, y1 = roi
    return a[y0:y1, x0:x1].copy()


def gray(a):
    return np.repeat(a[:, :, None], 3, axis=2)


def sheet(path, title, frames, images, labels, scale=2):
    h, w = images[0][0].shape[:2]
    cw, ch, gap = w * scale, h * scale, 8
    canvas = Image.new('RGB', (len(labels) * (cw + gap) + gap,
                               62 + len(frames) * (ch + 24 + gap)), (20, 20, 20))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 5), title, font=font(), fill='white')
    for c, label in enumerate(labels):
        # Two lines keep narrow Minecraft columns readable.
        parts = label.split(' / ')
        draw.text((gap + c * (cw + gap), 24), '\n'.join(parts), font=font(12), fill='white')
    for r, frame in enumerate(frames):
        y = 62 + r * (ch + 24 + gap)
        for c, a in enumerate(images[r]):
            x = gap + c * (cw + gap)
            draw.text((x, y), f'f{frame}', font=font(), fill='white')
            im = Image.fromarray(a).resize((cw, ch), Image.Resampling.NEAREST)
            canvas.paste(im, (x, y + 22))
    canvas.save(path)


def video(path, dirs, reference, roi):
    x0, y0, x1, y1 = roi
    cw, ch = (x1 - x0) * 2, (y1 - y0) * 2
    width, height = 5 * (cw + 8) + 8, ch + 64
    width += width % 2
    height += height % 2
    with av.open(str(path), 'w') as out:
        stream = out.add_stream('libx264', rate=60)
        stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
        stream.options = {'crf': '16', 'preset': 'fast'}
        for idx, frame in enumerate(range(60, 240)):
            canvas = Image.new('RGB', (width, height), (20, 20, 20))
            draw = ImageDraw.Draw(canvas)
            draw.text((8, 3), f'f{frame} | fixed timeline 60 FPS | ROI {roi} | nearest 2x', font=font(12), fill='white')
            paths = [d / f'frame_{frame:05d}.png' for d in dirs] + [reference / f'frame_{frame:05d}.png']
            for c, (p, label) in enumerate(zip(paths, LABELS)):
                x = 8 + c * (cw + 8)
                draw.text((x, 22), '\n'.join(label.split(' / ')), font=font(12), fill='white')
                with Image.open(p) as im:
                    canvas.paste(im.crop(roi).resize((cw, ch), Image.Resampling.NEAREST), (x, 62))
            vf = av.VideoFrame.from_image(canvas)
            vf.pts = idx
            for packet in stream.encode(vf):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    with av.open(str(path)) as inp:
        stream = inp.streams.video[0]
        times = [float(f.pts * f.time_base) for f in inp.decode(stream)]
        assert len(times) == 180 and all(b > a for a, b in zip(times, times[1:]))
        assert stream.average_rate == 60
    return {'frames': 180, 'fps': 60, 'profile_indices': [60, 239],
            'decode_validation': 'PASS', 'sha256': sha(path),
            'classification': 'lossy H264 visual aid; PNGs are authoritative'}


def analyze(scene, root, repo, make_video):
    src = root / 'sources'
    latest = read_json(src / f'{scene}-case9-capture.json')
    prior = read_json(src / f'{scene}-spatial-cost-capture.json')
    thin = read_json(src / f'{scene}-thin-validation.json')
    full = read_json(src / f'{scene}-full-off-validation.json')
    hashes = read_json(repo / f'Docs/Stencil-Lifecycle-Refresh/{scene}-rgb-hashes.json')
    refs = read_json(repo / 'Docs/Baseline-Restart/reused-reference-provenance.json')
    reference = Path(refs[scene]['reference'])
    trace = Path(thin['capture'])
    nine = Path(latest['capture_root']) / CASE9
    four = Path(latest['capture_root']) / NATIVE
    six = trace / CASE6
    full_dir = Path(full['capture']) / FULL
    dirs = [four, six, nine, full_dir]
    outdir = root / 'media'
    outdir.mkdir(exist_ok=True)
    print(f'{scene}: verifying all recorded output frames', flush=True)
    checks = 0
    for f in range(240):
        name = f'frame_{f:05d}.png'
        for path, expected in [
            (four / name, latest['output_hashes'][NATIVE][f]),
            (four / name, hashes[NATIVE][f]),
            (nine / name, latest['output_hashes'][CASE9][f]),
            (nine / name, prior['output_hashes'][CASE9][f]),
            (six / name, hashes[CASE6][f]),
            (Path(full['capture']) / CASE6 / name, hashes[CASE6][f]),
            (trace / NATIVE / name, hashes[NATIVE][f]),
            (Path(full['capture']) / NATIVE / name, hashes[NATIVE][f]),
            (full_dir / name, full['rgb_hashes'][FULL][f]),
        ]:
            assert ph(rgb(path)) == expected, (scene, f, path)
            checks += 1
    for entry in thin['source_files']:
        p = trace / entry['mode'] / f"frame_{entry['frame']:05d}-{entry['kind']}.dds"
        assert sha(p) == entry['sha256'], p
    source_hashes = []
    records, roi_data = [], {}
    pixels = []
    for f in FRAMES:
        prefix = f'frame_{f:05d}'
        c, p, v = [dds(nine / (prefix + '-' + k + '.dds')) for k in ['current', 'previous', 'velocity']]
        raw = dds(nine / (prefix + '-raw.dds'))
        mask = dds(nine / (prefix + '-coverage.dds')) != 0
        edge = edges(nine / (prefix + '-edge.rg8')).any(axis=2)
        assert np.all(mask | ~edge), (scene, f, 'raw edge lost')
        for kind, arr in [('current', c), ('previous', p), ('velocity', v), ('raw', raw)]:
            assert np.array_equal(arr, dds(six / (prefix + '-' + kind + '.dds'))), (scene, f, kind)
        assert np.array_equal(edge, edges(six / (prefix + '-edge.rg8')).any(axis=2))
        assert np.array_equal(edge, dds(six / (prefix + '-coverage.dds')) != 0)
        rec = reconstruct(c, p, v)
        coords = rec['coords']
        ix, iy = np.floor(coords[:, :, 0]).astype('int32'), np.floor(coords[:, :, 1]).astype('int32')
        in_bounds = (ix >= 0) & (ix < 1920) & (iy >= 0) & (iy < 1061)
        previous_edge = edges(nine / f'frame_{f-1:05d}-edge.rg8').any(axis=2)
        gathered_edge = previous_edge[iy.clip(0, 1060), ix.clip(0, 1919)] & in_bounds
        expected_union = edge | gathered_edge
        safe = rec['safe']
        union_mismatch = np.count_nonzero((mask != expected_union) & safe)
        assert union_mismatch == 0, (scene, f, union_mismatch)
        final6, final9, final4, finalfull = [rgb(d / (prefix + '.png')) for d in [six, nine, four, full_dir]]
        assert np.array_equal(final9[~mask], c[:, :, :3][~mask])
        assert np.array_equal(final6[~edge], c[:, :, :3][~edge])
        assert np.array_equal(final9[mask], finalfull[mask]), (scene, f, '9 full control differs')
        assert np.array_equal(final6[edge], finalfull[edge]), (scene, f, '6 full control differs')
        expected = np.where(mask[:, :, None], rec['full_resolve'], c[:, :, :3])
        error = np.abs(expected.astype('int16') - final9.astype('int16')).max(axis=2)
        assert error[safe].max() <= 1, (scene, f, int(error[safe].max()))
        # Diagnostic count, not an absolute visibility/ghosting classification.
        delta_full = np.abs(finalfull.astype('int16') - c[:, :, :3].astype('int16')).max(axis=2)
        record = {'frame': f, 'current_edge_pixels': int(edge.sum()), 'union_pixels': int(mask.sum()),
                  'added_pixels': int((mask & ~edge).sum()), 'safe_point_pixels': int(safe.sum()),
                  'cpu_max_rgb_error_safe': int(error[safe].max()),
                  'union_mismatch_safe': int(union_mismatch),
                  'full_off_delta_ge8_outside6': int(((delta_full >= 8) & ~edge).sum()),
                  'full_off_delta_ge8_outside9': int(((delta_full >= 8) & ~mask).sum()),
                  'mean_selected_weight_cpu': float(rec['weight'][mask].mean()),
                  'maximum_camera_velocity': float(np.abs(v.astype('float32')).max()),
                  'current_history_rgb_different_pixels': int(np.any(c[:, :, :3] != rec['history'][:, :, :3], axis=2).sum())}
        roi = ROIS[scene]
        data = {'four': crop(final4, roi), 'six': crop(final6, roi), 'nine': crop(final9, roi),
                'full': crop(finalfull, roi), 'ref': crop(rgb(reference / (prefix + '.png')), roi),
                'raw': crop(raw[:, :, :3], roi), 'current': crop(c[:, :, :3], roi),
                'history': crop(rec['history'][:, :, :3], roi), 'edge': crop(edge, roi),
                'mask': crop(mask, roi), 'weight': crop(rec['weight'], roi), 'safe': crop(safe, roi)}
        roi_data[f] = data
        if scene == 'minecraft' and f in (130, 131, 132, 134, 135, 190):
            x, y = {130: (971, 544), 131: (971, 544), 132: (972, 544),
                    134: (972, 544), 135: (973, 544), 190: (975, 544)}[f]
            pixels.append({'frame': f, 'xy': [x, y], 'raw': raw[y, x, :3].tolist(),
                           'spatial': c[y, x, :3].tolist(), 'history_cpu_point': rec['history'][y, x, :3].tolist(),
                           'edge6': bool(edge[y, x]), 'union9': bool(mask[y, x]),
                           'weight_cpu': float(rec['weight'][y, x]), 'point_safe': bool(safe[y, x]),
                           'case4': final4[y, x].tolist(), 'case6': final6[y, x].tolist(),
                           'case9': final9[y, x].tolist(), 'full_off': finalfull[y, x].tolist(),
                           'spatial_reference': rgb(reference / (prefix + '.png'))[y, x].tolist()})
        records.append(record)
        for pth in [nine / (prefix + '-' + k + ext) for k, ext in [('raw', '.dds'), ('current', '.dds'),
                    ('previous', '.dds'), ('velocity', '.dds'), ('coverage', '.dds'), ('edge', '.rg8')]]:
            source_hashes.append({'path': str(pth), 'sha256': sha(pth)})
        source_hashes.append({'path': str(reference / (prefix + '.png')), 'sha256': sha(reference / (prefix + '.png'))})
        print(f'{scene}: trace f{f} PASS', flush=True)
    for window, frames in WINDOWS.items():
        fs = list(frames)
        ims = [[roi_data[f][k] for k in ['four', 'six', 'nine', 'full', 'ref']] for f in fs]
        sheet(outdir / f'{scene}-{window}.png', f'{scene} | {ROIS[scene]} | nearest 2x | reference is spatial only', fs, ims, LABELS)
    for part, fs in [('moving-before', list(range(127, 133))), ('moving-after', list(range(133, 139)))]:
        ims = [[roi_data[f][k] for k in ['four', 'six', 'nine', 'full', 'ref']] for f in fs]
        sheet(outdir / f'{scene}-{part}.png', f'{scene} | {ROIS[scene]} | nearest 2x', fs, ims, LABELS)
    fs = list(WINDOWS['moving'])
    causal = []
    for f in fs:
        d = roi_data[f]
        causal.append([d['raw'], d['current'], d['history'], gray(d['mask'].astype('uint8') * 255),
                       gray(np.rint(d['weight'] * d['mask'] * 255).astype('uint8')), d['nine']])
    sheet(outdir / f'{scene}-causal-moving.png', f'{scene} | actual inputs/mask/output; point history and weight CPU | nearest 2x', fs, causal,
          ['Raw / GPU', 'Spatial / GPU', 'History point / CPU', '9 Union mask / GPU', 'Weight 0..1 / CPU', '9 Output / GPU'])
    still_frames = list(WINDOWS['still'])
    still = {}
    for k in ['raw', 'current', 'history', 'four', 'six', 'nine', 'full']:
        still[k] = {'different_frames_from_first': sum(not np.array_equal(roi_data[f][k], roi_data[190][k]) for f in still_frames),
                    'pixel_frame_differences_from_current': sum(int(np.any(roi_data[f][k] != roi_data[f]['current'], axis=2).sum()) for f in still_frames)}
    metadata = {'validation': 'PASS', 'scene': scene, 'output_hash_checks': checks,
                'source_snapshot_checks': 'PASS', 'trace_frames': FRAMES,
                'full_off_equal_on_actual_selected_pixels': True,
                'input_6_9_equal': True, 'roi': ROIS[scene], 'records': records,
                'representative_pixels': pixels, 'still_roi': still,
                'source_files': source_hashes, 'capture_directories': [str(d) for d in dirs],
                'reference': str(reference),
                'limitations': ['CPU point/weight is diagnostic, not a GPU weight capture for case9.',
                                'Point boundary exclusion applies to union/CPU tests, not GPU-to-GPU equality.',
                                'Full-screen Off is a coverage-only control, not native case4.',
                                'Reference is spatial only; RGB difference is not absolute ghosting.',
                                'The ge8 counter measures differences to a control, not quality failures.']}
    if make_video:
        metadata['video'] = video(outdir / f'{scene}-moving-through-still.mp4', dirs, reference, ROIS[scene])
    write_json(root / f'{scene}-analysis.json', metadata)
    if pixels:
        with (root / 'representative-pixels.csv').open('w', encoding='utf-8', newline='') as fp:
            w = csv.DictWriter(fp, fieldnames=list(pixels[0]))
            w.writeheader()
            w.writerows(pixels)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--scene', choices=['bistro', 'minecraft', 'both'], default='both')
    parser.add_argument('--video', action='store_true')
    args = parser.parse_args()
    root = args.repo / 'Docs/Edge-Temporal-Quality-Failure'
    for entry in read_json(root / 'source-provenance.json'):
        assert sha(root / entry['local_snapshot']) == entry['sha256'], entry
    scenes = ['bistro', 'minecraft'] if args.scene == 'both' else [args.scene]
    for scene in scenes:
        analyze(scene, root, args.repo, args.video)
    print('PASS: immutable GPU captures verified; no renderer changes or new performance measurement.', flush=True)


if __name__ == '__main__':
    main()
