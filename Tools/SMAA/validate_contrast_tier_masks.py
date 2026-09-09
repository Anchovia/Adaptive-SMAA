"""Engineering validation of matched temporal-matrix GPU candidate masks.

Manifest keys: high, medium_high, low, all_base, base (debug view 1), repeat_high.
Paths identify independent, finalized three/equal-length capture runs. This
tests mask set identities, not the exact finalDelta CPU/GPU classification.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from validate_temporal_capture_repeatability import inspect


def mask(path):
    with Image.open(path) as image:
        rgb = np.asarray(image.convert('RGB'))
    if not np.all((rgb == 0) | (rgb == 255)) or not np.all(rgb == rgb[..., :1]):
        raise ValueError(f'Non-binary RGB mask: {path}')
    return rgb[..., 0] != 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    paths = {key: Path(value) for key, value in json.loads(args.manifest.read_text()).items()}
    required = {'high', 'medium_high', 'low', 'all_base', 'base', 'repeat_high'}
    assert set(paths) == required
    assert len(set(paths.values())) == len(required), 'Independent runs required'
    runs = {key: inspect(path) for key, path in paths.items()}
    control = runs['all_base']
    for run in runs.values():
        assert run['prelude'] > 0 and not run['phase_failures'], run['root']
        for field in ('warmup', 'frames', 'mode_dirs'):
            assert run[field] == control[field], field
    for key in ('high', 'medium_high', 'low', 'all_base', 'repeat_high'):
        # Trace the chosen experimental policy through the finalized report.
        expected = {'high': 'ExperimentalContrastHigh', 'medium_high': 'ExperimentalContrastMediumHigh',
                    'low': 'ExperimentalContrastLow', 'all_base': 'AllBaseEdges',
                    'repeat_high': 'ExperimentalContrastHigh'}[key]
        report = next(paths[key].glob('*_results.csv')).read_text(encoding='utf-8-sig')
        assert f'Effective candidate policy: {expected}; source: SMAAFirstPassIntegratedCandidates' in report
    assert runs['high']['hashes'] == runs['repeat_high']['hashes'], 'Independent repeat mismatch'
    rows = []
    for mode, directory in control['mode_dirs'].items():
        if 'ET2X' not in mode:
            # Standard paths must ignore candidate overrides/debug views.
            for frame in range(control['frames']):
                name = f'{directory}/{directory}_frame_{frame:05d}.png'
                assert len({run['hashes'][name] for run in runs.values()}) == 1, name
            continue
        for frame in range(control['frames']):
            name = f'{directory}/{directory}_frame_{frame:05d}.png'
            masks = {key: mask(root / name) for key, root in paths.items()}
            high, mh, low, all_base, base = [masks[k] for k in ('high', 'medium_high', 'low', 'all_base', 'base')]
            assert all(x.shape == base.shape for x in masks.values()), name
            assert np.array_equal(all_base, base), name
            assert not np.any(high & ~mh), name
            assert not np.any(low & mh), name
            assert np.array_equal(low | mh, base), name
            assert all(not np.any(x & ~base) for x in masks.values()), name
            rows.append({'mode': mode, 'frame': frame,
                         'counts': {k: int(np.count_nonzero(v)) for k, v in masks.items()}})
    result = {'status': 'PASS', 'scope': 'GPU binary mask set identities, standard controls, repeat phase/hash',
              'not_tested': ['float32 GPU boundary oracle', 'candidate-list readback uniqueness', 'quality/performance'],
              'runs': {k: str(v) for k, v in paths.items()}, 'records': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
