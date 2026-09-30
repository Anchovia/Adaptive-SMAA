"""Evaluate the real GPU persistence output; reuse controls only by RGB hash.

CGVQM is auxiliary evidence against a spatial proxy. The source rendering,
jitter policy, and native temporal math are not modified by this analysis.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from PIL import Image

from analyze_edge_persistence_gpu import A, B, C, DOC, ROOT

OFFICIAL = ROOT.parents[2] / '.research-tools/CGVQM'
COMMIT = '8302ff45b4ff5a691682baf23f7c007d6b591e98'
WINDOWS = {'moving': (60, 180), 'transition': (160, 220)}
PATTERN = 'frame_[0-9][0-9][0-9][0-9][0-9].png'
CONFIG = dict(fps=60, patch_scale=4, patch_pool='mean', models=['2'], reference_index_offset=0)
PROFILE = 'original-flythrough-t2-still60-move120-still60'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs(scene, quality):
    expected = json.loads((DOC / f'{scene}-rgb-hashes.json').read_text())
    roots = {m: Path(quality['capture']) / m for m in (A, B, C)}
    roots['reference'] = Path(quality['reference'])
    digests = {w: {m: hashlib.sha256() for m in roots} for w in WINDOWS}
    for m, folder in roots.items():
        files = sorted(folder.glob(PATTERN))
        assert [p.name for p in files] == [f'frame_{f:05d}.png' for f in range(240)]
        for f, p in enumerate(files):
            with Image.open(p) as im:
                assert im.mode == 'RGB' and im.size == (1920, 1061)
                pixels = np.asarray(im).tobytes()
            if m != 'reference':
                assert hashlib.sha256(pixels).hexdigest() == expected[m][f], (scene, m, f)
            for w, (lo, hi) in WINDOWS.items():
                if lo <= f < hi:
                    digests[w][m].update(f.to_bytes(8, 'little'))
                    digests[w][m].update(pixels)
        print(f'INPUT PASS {scene}/{m}: 240 frames', flush=True)
    return {w: {m: d.hexdigest() for m, d in dd.items()} for w, dd in digests.items()}


def validate(d, scene, start, end, test_hash, reference_hash):
    assert d['official_cgvqm']['commit'] == COMMIT
    assert d['configuration'] == CONFIG
    assert d['runtime']['device'] == 'cuda'
    assert d['provenance']['scene'] == scene
    assert d['provenance']['camera_profile'] == PROFILE
    for name, digest in [('test', test_hash), ('reference', reference_hash)]:
        s, r = d[name + '_sequence'], d[name + '_round_trip']
        assert (s['first_index'], s['last_index'], s['frame_count'], s['width'], s['height']) == (start, end-1, end-start, 1920, 1061)
        assert s['pixel_sha256'] == digest, (scene, name, 'hash')
        assert r['decoded_frames'] == end-start
        assert r['mismatched_values'] == r['max_absolute_difference'] == 0
    assert math.isfinite(d['results']['CGVQM-2']['score_higher_is_better'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', choices=['bistro', 'minecraft'], required=True)
    scene = parser.parse_args().scene
    qp = DOC / f'{scene}-quality.json'
    q = json.loads(qp.read_text())
    assert q['validation'] == 'PASS'
    assert sha(q['receipt']['report']).lower() == q['receipt']['report_sha256'].lower()
    prior_path = ROOT / f'Docs/Stencil-Lifecycle-Refresh/{scene}-prior.json'
    prior = json.loads(prior_path.read_text())['quality']
    assert prior['validation'] == 'PASS'
    hashes = inputs(scene, q)
    results = {}
    for w, (start, end) in WINDOWS.items():
        old = prior['results'][w]['records']
        records = {A: old['Spatial-Edge-Stencil-Off-R'], C: old[C]}
        for m, d in records.items():
            validate(d, scene, start, end, hashes[w][m], hashes[w]['reference'])
        out = ROOT / f'Projects/CMAA2/AutoBench/EdgePersistenceQuality/{scene}/{w}/{B}'
        out.mkdir(parents=True, exist_ok=True)
        result_path = out / 'CGVQM-Results.json'
        receipt_path = out / 'invocation.json'
        command = [sys.executable, str(ROOT / 'Tools/SMAA/run_cgvqm_png_sequences.py'),
                   '--test-dir', str(Path(q['capture']) / B), '--reference-dir', q['reference'],
                   '--frame-glob', PATTERN, '--output-dir', str(out),
                   '--start-index', str(start), '--frames', str(end-start),
                   '--cgvqm-root', str(OFFICIAL), '--model', '2', '--classification', 'engineering',
                   '--scene', scene, '--camera-profile', PROFILE, '--test-mode', B,
                   '--reference-id', 'SS-Reference', '--device', 'cuda',
                   '--patch-scale', '4', '--patch-pool', 'mean', '--skip-error-map-video']
        if not result_path.exists():
            print(f'START CGVQM {scene}/{w}: GPU persistence', flush=True)
            started = datetime.now(timezone.utc).isoformat()
            t0 = time.monotonic()
            with (out / 'runner.log').open('w', encoding='utf-8') as log:
                subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=600)
            receipt_path.write_text(json.dumps(dict(command=command, started_utc=started,
                elapsed_seconds=time.monotonic()-t0, result_sha256=sha(result_path)), indent=2)+'\n')
        d = json.loads(result_path.read_text())
        validate(d, scene, start, end, hashes[w][B], hashes[w]['reference'])
        assert d['provenance']['test_mode'] == B and d['provenance']['frame_glob'] == PATTERN
        invocation = json.loads(receipt_path.read_text())
        assert invocation['result_sha256'] == sha(result_path)
        for old_record in records.values():
            for key in ['torch', 'cuda_runtime', 'gpu', 'device']:
                assert d['runtime'][key] == old_record['runtime'][key], key
        records[B] = d
        scores = {m: r['results']['CGVQM-2']['score_higher_is_better'] for m, r in records.items()}
        results[w] = dict(frame_interval_inclusive=[start, end-1], scores=scores,
            persistence_minus_current_edge=scores[B]-scores[A], persistence_minus_native=scores[B]-scores[C],
            newly_evaluated=[B], controls_reused_by_exact_rgb_hash=[A, C],
            input_stream_hashes=hashes[w], records=records,
            new_result_path=str(result_path), new_result_sha256=sha(result_path), invocation=invocation)
        print(f'PASS {scene}/{w}: old={scores[A]:.6f}, GPU={scores[B]:.6f}, native={scores[C]:.6f}', flush=True)
    sources = {str(p.relative_to(OFFICIAL)): sha(p) for p in sorted(OFFICIAL.rglob('*.py')) if '.git' not in p.parts}
    for p in sorted((OFFICIAL / 'weights').glob('*.pickle')):
        sources[str(p.relative_to(OFFICIAL))] = sha(p)
    report = dict(validation='PASS', scene=scene, classification='engineering quality gate',
        renderer_commit='2d4d0ccba06f6f9882c16abffd7489bed52030d7',
        capture=q['capture'], reference=q['reference'], reference_type=q['reference_type'],
        quality_source_sha256=sha(qp), prior_records_sha256=sha(prior_path),
        input_frames_verified_per_stream=240, results=results, official_source_hashes=sources,
        limitations=['CGVQM is auxiliary, not absolute ghosting ground truth.',
            'A/B pattern Off; native pattern On. Native comparison is not coverage-only.',
            'Moving frames 60..179; transition frames 160..219 includes moving and still.',
            'Unmodified official model, patch scale 4, patch mean pooling; tiny line defects can be diluted.',
            'No new renderer capture or performance run; validated existing GPU captures.'])
    (DOC / f'{scene}-cgvqm.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
