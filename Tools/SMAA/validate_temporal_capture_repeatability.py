"""Validate temporal-matrix capture phases and exact repeat PNGs (engineering).

Run directories must contain CapturePhase rows from the readiness-aware capture.
Comparison is byte-exact and is not a visual-quality or performance score.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re


def inspect(root):
    reports = list(root.glob('*_results.csv'))
    if len(reports) != 1:
        raise ValueError(f'{root}: expected one finalized report')
    report = reports[0].read_text(encoding='utf-8-sig')
    warmup = int(re.search(r'Warm-up:\s+(\d+) frames', report)[1])
    frames = int(re.search(r'Capture:\s+(\d+) frames per mode', report)[1])
    prelude = int(re.search(r'Readiness prelude:\s+(\d+)', report)[1])
    mode_dirs = {}
    phases = {}
    for row in csv.reader(report.splitlines()):
        row = [x.strip() for x in row]
        if row and row[0].startswith(('O-', 'A-')) and len(row) >= 3:
            # Historical report rows are not CSV-quoted; descriptions may contain
            # commas. The output directory is the final nonempty field.
            mode_dirs[row[0]] = next(value for value in reversed(row) if value)
        if row and row[0] == 'CapturePhase':
            key = (row[1], int(row[2]))
            if key in phases:
                raise ValueError(f'{root}: duplicate capture phase row {key}')
            phases[key] = {'phase': int(row[3]), 'jitter': [float(row[4]), float(row[5])],
                           'history': row[6]}
    if not mode_dirs:
        raise ValueError(f'{root}: no modes')
    hashes = {}
    phase_failures = []
    for mode, directory in mode_dirs.items():
        expected = {f'{directory}_frame_{i:05d}.png' for i in range(frames)}
        actual = {p.name for p in (root/directory).glob('*.png')}
        if actual != expected:
            raise ValueError(f'{root}: PNG index mismatch in {mode}')
        for i in range(frames):
            state = phases[(mode, i)]
            expected_phase = (warmup + i) % 2
            expected_jitter = [0.0, 0.0] if 'ET2X' in mode else [0.25 if expected_phase == 0 else -0.25]*2
            if state != {'phase': expected_phase, 'jitter': expected_jitter, 'history': 'resolve'}:
                phase_failures.append({'mode': mode, 'frame': i, 'actual': state})
            path = root/directory/f'{directory}_frame_{i:05d}.png'
            hashes[f'{directory}/{path.name}'] = hashlib.sha256(path.read_bytes()).hexdigest()
    if len(phases) != len(hashes):
        raise ValueError(f'{root}: unexpected phase rows')
    return {'root': str(root), 'warmup': warmup, 'frames': frames, 'prelude': prelude,
            'mode_dirs': mode_dirs, 'phase_failures': phase_failures, 'hashes': hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-legacy', action='store_true',
                        help='Record legacy phase violations without accepting them as stable captures')
    args = parser.parse_args()
    runs = [inspect(root) for root in args.runs]
    reference = runs[0]
    mismatches = []
    for run in runs[1:]:
        if any(run[k] != reference[k] for k in ('warmup', 'frames', 'mode_dirs')):
            raise ValueError('Only compare runs with identical mode/frame/warm-up settings')
        for name, value in reference['hashes'].items():
            if run['hashes'][name] != value:
                mismatches.append({'root': run['root'], 'image': name})
    stable = all(r['prelude'] > 0 and not r['phase_failures'] for r in runs) and not mismatches
    output = {'status': 'PASS' if stable else 'NOT_REPEATABLE_OR_LEGACY',
              'classification': 'engineering phase/hash validation',
              'runs': runs, 'mismatches': mismatches}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps({'status': output['status'], 'images': [len(r['hashes']) for r in runs],
                      'phase_failures': [len(r['phase_failures']) for r in runs],
                      'hash_mismatches': len(mismatches)}))
    if not stable and not args.allow_legacy:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
