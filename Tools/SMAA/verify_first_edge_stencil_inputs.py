"""Verify raw RGBA/velocity probes and reuse exactly the same native edges as item6."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'Docs/First-Edge-Temporal-Only-Stencil'
FULL = 'ABL-FirstEdge-TemporalOnly-Full-PatternOff-R'
SELECTED = 'ABL-FirstEdge-TemporalOnly-Stencil-PatternOff-R'
SPATIAL = 'ABL-Spatial-FirstEdge-Stencil-PatternOff-R'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', required=True, choices=['bistro', 'minecraft'])
    args = parser.parse_args()
    gate_path = DOCS / f'{args.scene}-capture.json'
    gate = json.loads(gate_path.read_text())
    assert gate['validation'] == 'PASS' and not any(gate['mismatches'].values())
    current = Path(gate['capture'])
    spatial_run = '20260929_151913' if args.scene == 'bistro' else '20260929_152613'
    spatial = Path('D:/SMAAResearchCaptures/first-edge-stencil-20260929/item6') / args.scene / spatial_run
    mismatches = dict(rgba_velocity_probes=0, item5_item6_edge_frames=0)
    probes = []
    for frame in [0, 1, 59, 60, 61, 100, 179, 180, 181, 239]:
        for kind in ['input', 'prepared', 'velocity']:
            name = f'probe_{frame:05d}-{kind}.dds'
            full_hash = sha(current / FULL / name)
            selected_hash = sha(current / SELECTED / name)
            mismatches['rgba_velocity_probes'] += int(full_hash != selected_hash)
            probes.append(dict(frame=frame, kind=kind, full_sha256=full_hash, selected_sha256=selected_hash))
    edges = []
    for frame in range(240):
        name = f'frame_{frame:05d}-edge.rg8'
        raw_hash = sha(current / SELECTED / name)
        spatial_hash = sha(spatial / SPATIAL / name)
        mismatches['item5_item6_edge_frames'] += int(raw_hash != spatial_hash)
        edges.append(dict(frame=frame, item5_sha256=raw_hash, item6_sha256=spatial_hash))
    result = dict(validation='PASS' if not any(mismatches.values()) else 'FAIL',
                  scene=args.scene, executable_sha256=gate['executable_sha256'],
                  capture_gate_sha256=sha(gate_path), capture=str(current), item6_capture=str(spatial),
                  probes_checked=len(probes), edge_frames_checked=len(edges),
                  mismatches=mismatches, probes=probes, edges=edges)
    (DOCS / f'{args.scene}-input-bridge.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['probes', 'edges']}, indent=2))
    assert result['validation'] == 'PASS'


if __name__ == '__main__':
    main()
