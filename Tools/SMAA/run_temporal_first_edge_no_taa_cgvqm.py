"""Add jitter-on current-spatial control to the existing first-edge CGVQM gate."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from run_temporal_first_edge_cgvqm import (
    ROOT, DOC, BENCH, WINDOWS, NATIVE, SELECT, sha, sequence_hash, validate,
)

CURRENT = 'DBG-CurrentSpatial-R'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', required=True, choices=['bistro', 'minecraft'])
    scene = parser.parse_args().scene
    qp = DOC / f'{scene}-quality.json'
    cp = DOC / f'{scene}-cgvqm.json'
    quality = json.loads(qp.read_text())
    comparison = json.loads(cp.read_text())
    assert quality['validation'] == comparison['validation'] == 'PASS'
    assert quality['selection_mismatches'] == 0
    assert comparison['quality_report_sha256'] == sha(qp)
    capture, reference = Path(quality['capture']), Path(quality['reference'])
    results = {}
    for window, (start, end) in WINDOWS.items():
        baseline = comparison['results'][window]
        reference_hash = sequence_hash(reference, start, end)
        records = {}
        # Revalidate both prior scores against the original result files and actual PNGs.
        for label, mode in [('native', NATIVE), ('selective', SELECT)]:
            path = Path(baseline[f'{label}_result'])
            assert sha(path) == baseline[f'{label}_result_sha256']
            record = json.loads(path.read_text())
            validate(record, start, end)
            assert record['provenance']['scene'] == scene
            assert record['provenance']['test_mode'] == mode
            assert record['reference_sequence']['pixel_sha256'] == reference_hash
            assert record['test_sequence']['pixel_sha256'] == sequence_hash(capture / mode, start, end)
            assert record['results']['CGVQM-2']['score_higher_is_better'] == baseline[f'{label}_score']
            records[label] = record
        output = BENCH / 'FirstEdgeQuality' / scene / 'CGVQM2' / window / CURRENT
        output.mkdir(parents=True, exist_ok=True)
        result_path = output / 'CGVQM-Results.json'
        if not result_path.exists():
            command = [
                sys.executable, str(ROOT / 'Tools/SMAA/run_cgvqm_png_sequences.py'),
                '--test-dir', str(capture / CURRENT), '--reference-dir', str(reference),
                '--output-dir', str(output), '--start-index', str(start), '--frames', str(end - start),
                '--cgvqm-root', str(ROOT.parents[2] / '.research-tools/CGVQM'),
                '--model', '2', '--classification', 'engineering', '--scene', scene,
                '--camera-profile', 'original-flythrough-t2-still60-move120-still60',
                '--test-mode', CURRENT, '--reference-id', 'SS-Reference', '--device', 'cuda',
                '--patch-scale', '4', '--patch-pool', 'mean', '--skip-error-map-video',
            ]
            print(f'START {scene}/{window}: No-TAA, paired jitter ON', flush=True)
            with (output / 'runner.log').open('w', encoding='utf-8') as log:
                subprocess.run(command, check=True, timeout=600, stdout=log, stderr=subprocess.STDOUT)
        current = json.loads(result_path.read_text())
        validate(current, start, end)
        assert Path(current['test_sequence']['directory']).resolve() == (capture / CURRENT).resolve()
        assert current['provenance']['scene'] == scene
        assert current['provenance']['test_mode'] == CURRENT
        assert current['reference_sequence']['pixel_sha256'] == reference_hash
        assert current['test_sequence']['pixel_sha256'] == sequence_hash(capture / CURRENT, start, end)
        for key in ['torch', 'cuda_runtime', 'device']:
            assert current['runtime'][key] == records['native']['runtime'][key] == records['selective']['runtime'][key]
        no_taa = current['results']['CGVQM-2']['score_higher_is_better']
        native, selective = baseline['native_score'], baseline['selective_score']
        results[window] = dict(
            first_index=start, last_index=end - 1,
            native_score=native, selective_score=selective, no_taa_score=no_taa,
            selective_minus_no_taa=selective - no_taa, native_minus_no_taa=native - no_taa,
            selective_minus_native=selective - native,
            reference_pixel_sha256=reference_hash,
            no_taa_result=str(result_path), no_taa_result_sha256=sha(result_path), no_taa_record=current,
            native_result=baseline['native_result'], native_result_sha256=baseline['native_result_sha256'],
            selective_result=baseline['selective_result'], selective_result_sha256=baseline['selective_result_sha256'],
        )
        print(f'PASS {scene}/{window}: native={native:.6f}, selective={selective:.6f}, no_taa={no_taa:.6f}', flush=True)
    result = dict(
        scene=scene, validation='PASS', classification='engineering', mode=CURRENT,
        definition='Current spatial SMAA output only; paired projection jitter/subsample pattern retained; no temporal blend. Not unjittered O-1X.',
        quality_report_sha256=sha(qp), prior_cgvqm_report_sha256=sha(cp), results=results,
    )
    (DOC / f'{scene}-no-taa-cgvqm.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
