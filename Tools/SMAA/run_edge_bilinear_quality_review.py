"""Quality-only review of cases 4/6/9/10; no renderer or AA changes.

Validate original capture hashes and run unmodified Intel CGVQM-2 through
the existing lossless adapter, using one separate process per evaluation.
"""
import argparse
import csv
import copy
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_edge_bilinear_history_rgb import DOC, MODES, ROIS, ROOT
from evaluate_baseline_cgvqm import stream, validate

RESEARCH = ROOT.parents[2]
CGVQM_PYTHON = RESEARCH / '.research-tools/cgvqm-venv/Scripts/python.exe'
ADAPTER = RESEARCH / 'Tools/SMAA/run_cgvqm_png_sequences.py'
CGVQM = RESEARCH / '.research-tools/CGVQM'
OUTPUT = ROOT / 'tmp/edge-bilinear-quality-review'
CASES = [4, 6, 9, 10]
WINDOWS = [('moving', 60, 120), ('transition', 160, 60)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rgb(path):
    with Image.open(path) as im:
        assert im.size == (1920, 1061), (path, im.size)
        return np.array(im.convert('RGB'))


def validate_and_measure():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    for scene in ['bistro', 'minecraft']:
        capture = json.loads((DOC / f'{scene}-capture.json').read_text(encoding='utf-8-sig'))
        source = Path(capture['capture_root'])
        reference = Path(capture['reference_root'])
        rows = []
        ref_hashes = []
        for frame in range(240):
            ref = rgb(reference / f'frame_{frame:05d}.png')
            ref_hashes.append(hashlib.sha256(ref.tobytes()).hexdigest())
            for case, mode in zip(CASES, MODES):
                value = rgb(source / mode / f'frame_{frame:05d}.png')
                actual = hashlib.sha256(value.tobytes()).hexdigest()
                assert actual == capture['output_hashes'][mode][frame], (scene, mode, frame, 'RGB hash mismatch')
                for name, box in [('full', (0, 0, 1920, 1061)), *ROIS[scene].items()]:
                    x0, y0, x1, y1 = box
                    diff = value[y0:y1, x0:x1].astype(np.float32) - ref[y0:y1, x0:x1].astype(np.float32)
                    mse = float(np.mean(diff * diff))
                    rows.append(dict(scene=scene, case=case, mode=mode, frame=frame, roi=name,
                                     rgb_mae=float(np.mean(np.abs(diff))), mse=mse,
                                     psnr=float(10 * np.log10(255**2 / max(mse, 1e-12)))))
            if frame % 60 == 59:
                print(f'PNG_CHECK {scene} {frame + 1}/240', flush=True)
        path = DOC / f'{scene}-review-per-frame.csv'
        with path.open('w', newline='', encoding='utf-8') as fp:
            writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        metrics = []
        for window, start, count in [*WINDOWS, ('late-still', 190, 50)]:
            for case, mode in zip(CASES, MODES):
                for roi in ['full', *ROIS[scene]]:
                    cells = [r for r in rows if r['case'] == case and r['roi'] == roi and start <= r['frame'] < start + count]
                    mse = float(np.mean([r['mse'] for r in cells]))
                    metrics.append(dict(case=case, mode=mode, window=window, roi=roi,
                                        first_frame=start, last_frame=start + count - 1,
                                        rgb_mae=float(np.mean([r['rgb_mae'] for r in cells])),
                                        pooled_psnr=float(10 * np.log10(255**2 / max(mse, 1e-12)))))
        records.append(dict(scene=scene, validation='PASS', frames_per_case=240, checked_cases=CASES,
                            rgb_hash_mismatch=0, reference_rgb_hashes=ref_hashes, metrics=metrics,
                            capture_root=str(source), reference_root=str(reference),
                            reference_classification='supersampled spatial proxy; not temporal ground truth',
                            per_frame_csv=str(path), per_frame_sha256=sha(path)))
    path = DOC / 'quality-review-png.json'
    path.write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(f'PNG_QUALITY_PASS {path}', flush=True)


def run_metric(timeout, selected_scene=None):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    if selected_scene is not None and (DOC / 'quality-review-cgvqm.json').exists():
        prior = json.loads((DOC / 'quality-review-cgvqm.json').read_text(encoding='utf-8'))
        results = [v for v in prior if v['scene'] != selected_scene]
        for v in results:
            assert sha(v['result_json']) == v['result_sha256']
    total = 2 * len(WINDOWS) * len(CASES)
    for scene in ([selected_scene] if selected_scene is not None else ['bistro', 'minecraft']):
        capture = json.loads((DOC / f'{scene}-capture.json').read_text(encoding='utf-8-sig'))
        for window, start, count in WINDOWS:
            for case, mode in zip(CASES, MODES):
                directory = OUTPUT / scene / window / f'case-{case}'
                directory.mkdir(parents=True, exist_ok=True)
                # Keep official 30-frame temporal patch boundaries. Two equal
                # 60-frame invocations cover a 120-frame window without loading
                # the whole window into RAM. Only pooling reduction order varies.
                original_sequence = Path(capture['capture_root']) / mode
                # Diagnostic PNGs share the capture directory. Give the strict
                # adapter a directory containing final frames only; copy bytes
                # unchanged because the D-drive source cannot be hard-linked on C.
                sequence = OUTPUT / 'FinalPNGs' / scene / f'case-{case}'
                sequence.mkdir(parents=True, exist_ok=True)
                for frame in range(240):
                    source_png = original_sequence / f'frame_{frame:05d}.png'
                    final_png = sequence / source_png.name
                    if not final_png.exists():
                        shutil.copyfile(source_png, final_png)
                    assert sha(source_png) == sha(final_png), (scene, case, frame, 'FinalPNG byte mismatch')
                reference = Path(capture['reference_root'])
                parts = []
                started = time.time()
                for first in range(start, start + count, 60):
                    dest = directory / f'part-{first:05d}-{first + 59:05d}'
                    dest.mkdir(parents=True, exist_ok=True)
                    command = [str(CGVQM_PYTHON), str(ADAPTER), '--test-dir', str(sequence),
                           '--reference-dir', capture['reference_root'], '--output-dir', str(directory),
                           '--cgvqm-root', str(CGVQM), '--start-index', str(first), '--frames', '60',
                           '--fps', '60', '--model', '2', '--device', 'cuda', '--patch-scale', '4',
                           '--patch-pool', 'mean', '--skip-error-map-video', '--classification', 'engineering',
                           '--scene', scene, '--camera-profile', 'original-flythrough-t2-still60-move120-still60',
                           '--test-mode', mode, '--reference-id', 'SS-Reference-spatial-proxy']
                    command[command.index('--output-dir') + 1] = str(dest)
                    print(f'CGVQM_PART {scene} {window} case{case} frames{first}-{first + 59}', flush=True)
                    part_path = dest / 'CGVQM-Results.json'
                    if not part_path.exists():
                        with (dest / 'run.log').open('w', encoding='utf-8') as fp:
                            subprocess.run(command, cwd=str(RESEARCH), stdout=fp, stderr=subprocess.STDOUT,
                                           timeout=timeout, check=True)
                    part = json.loads(part_path.read_text(encoding='utf-8'))
                    validate(part, first, first + 60)
                    assert part['provenance']['test_mode'] == mode and part['provenance']['scene'] == scene
                    assert part['test_sequence']['pixel_sha256'] == stream(sequence, first, first + 60)
                    assert part['reference_sequence']['pixel_sha256'] == stream(reference, first, first + 60)
                    parts.append(part)
                print(f'CGVQM_START {len(results) + 1}/{total} {scene} {window} case{case}', flush=True)
                result_path = directory / 'CGVQM-Results.json'
                result = copy.deepcopy(parts[0])
                for kind, folder in [('test', sequence), ('reference', reference)]:
                    result[kind + '_sequence'].update(first_index=start, last_index=start + count - 1,
                                                      frame_count=count, pixel_sha256=stream(folder, start, start + count))
                    trips = [p[kind + '_round_trip'] for p in parts]
                    result[kind + '_round_trip'] = dict(videos=[p['video'] for p in trips], decoded_frames=count,
                        mismatched_values=sum(p['mismatched_values'] for p in trips),
                        max_absolute_difference=max(p['max_absolute_difference'] for p in trips))
                score = float(np.mean([p['results']['CGVQM-2']['score_higher_is_better'] for p in parts]))
                result['results'] = {'CGVQM-2': {'score_higher_is_better': score}}
                result['official_chunk_results'] = parts
                result['evaluation_method'] = 'Unmodified official <=60-frame invocations; original30-frame patch boundaries; equal-patch mean pooling'
                result['native_full_window_bridge'] = None
                if case == 4:
                    native = json.loads((DOC.parent / 'Baseline-Restart' / f'{scene}-cgvqm.json').read_text(encoding='utf-8-sig'))['results'][window]['native_record']
                    validate(native, start, start + count)
                    assert native['test_sequence']['pixel_sha256'] == result['test_sequence']['pixel_sha256']
                    assert native['reference_sequence']['pixel_sha256'] == result['reference_sequence']['pixel_sha256']
                    delta = score - native['results']['CGVQM-2']['score_higher_is_better']
                    assert abs(delta) <= 0.00002, (scene, window, 'bounded/full-window bridge', delta)
                    result['native_full_window_bridge'] = dict(score_difference=delta, tolerance=0.00002, validation='PASS')
                result_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
                assert result['test_sequence']['frame_count'] == count
                assert result['test_sequence']['first_index'] == start
                assert result['reference_sequence']['first_index'] == start
                assert result['test_sequence']['last_index'] == start + count - 1
                assert result['runtime']['device'] == 'cuda'
                assert result['configuration']['patch_scale'] == 4
                assert result['configuration']['patch_pool'] == 'mean'
                assert result['official_cgvqm']['commit'] == '8302ff45b4ff5a691682baf23f7c007d6b591e98'
                assert result['test_round_trip']['mismatched_values'] == 0
                assert result['reference_round_trip']['mismatched_values'] == 0
                results.append(dict(scene=scene, window=window, case=case, mode=mode,
                                    first_frame=start, last_frame=start + count - 1, score=score,
                                    result_json=str(result_path), result_sha256=sha(result_path),
                                    elapsed_seconds=time.time() - started, record=result))
                (DOC / 'quality-review-cgvqm.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
                print(f'CGVQM_DONE {len(results)}/{total} {scene} {window} case{case} score={score:.6f}', flush=True)
        # Remove only this adapter's temporary copies after the whole scene.
        cleanup = OUTPUT / 'FinalPNGs' / scene
        expected_cleanup = OUTPUT.resolve() / 'FinalPNGs' / scene
        assert cleanup.resolve() == expected_cleanup
        assert expected_cleanup.is_relative_to(ROOT.resolve())
        shutil.rmtree(cleanup)
        print(f'INPUT_COPIES_CLEANED {scene}; originals and verification videos retained', flush=True)
    print('CGVQM_QUALITY_PASS 16/16 windows, 24 separate model processes; FFV1 RGB mismatch0; native full-window bridge PASS', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['png', 'cgvqm'], required=True)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--scene', choices=['bistro', 'minecraft'])
    args = parser.parse_args()
    if args.phase == 'png':
        validate_and_measure()
    else:
        run_metric(args.timeout, args.scene)
