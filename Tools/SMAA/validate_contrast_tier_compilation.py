"""Compile contrast-tier branches and unchanged spatial controls with FXC.

Specialized variants prove the tier paths have no texture loads. The actual
dynamic variant is also compiled and its disassembly retained for inspection.
This does not replace GPU mask, buffer, or quality validation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fxc', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    include = root / 'Projects/CMAA2/SMAA'
    current = (include / 'SMAAWrapper.hlsl').read_text(encoding='utf-8-sig')
    before = subprocess.check_output(
        ['git', 'show', 'f88f026:Projects/CMAA2/SMAA/SMAAWrapper.hlsl'], cwd=root).decode('utf-8-sig')
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for adaptive in (False, True):
        for raw in (False, True):
            prefix = f'{"adaptive" if adaptive else "original"}_{"raw" if raw else "rgb"}'
            hashes = []
            for label, source in [('before', before), ('after', current)]:
                path = args.output / f'{prefix}_{label}.hlsl'
                path.write_text(source, encoding='utf-8')
                entry = 'DX10_SMAALumaRawEdgeDetectionPS' if raw else 'DX10_SMAALumaEdgeDetectionPS'
                hashes.append(compile_one(path, entry, False, adaptive, raw, include, args.fxc)['sha256'])
            assert hashes[0] == hashes[1], (prefix, hashes)
            records.append({'variant': prefix, 'spatial_byte_identical': True})
            for policy in (None, 0, 1, 3, 4, 5):
                source = current
                if policy is not None:
                    expression = 'uint policy = (uint)(g_SMAAReprojection.TSCMAACandidateParams.y + 0.5);'
                    start = source.index('bool TSCMAAIntegratedSelectCandidate(')
                    end = source.index('SMAA_EDGE_OUTPUT DX10_SMAALumaEdgeDetectionIntegrated', start)
                    selector = source[start:end]
                    assert selector.count(expression) == 1
                    source = source[:start] + selector.replace(expression, f'uint policy = {policy};') + source[end:]
                path = args.output / f'{prefix}_policy_{policy}.hlsl'
                path.write_text(source, encoding='utf-8')
                record = compile_one(path, 'DX10_SMAALumaEdgeDetectionIntegratedTemporalCandidatesPS',
                                     True, adaptive, raw, include, args.fxc)
                record.update(variant=prefix, policy=policy)
                assert record['loads'] == (3 if policy in (None, 1) else 0), record
                assert record['samples'] == 7, record
                records.append(record)
    # CPU float32 boundary oracle; GPU boundary execution is a separate gate.
    boundaries = []
    for threshold in (0.1, 1.0 / 3.0):
        bits = struct.unpack('<I', struct.pack('<f', threshold))[0]
        values = [struct.unpack('<f', struct.pack('<I', bits + d))[0] for d in (-1, 0, 1)]
        bound = values[1]
        assert [v >= bound for v in values] == [False, True, True]
        assert [v < bound for v in values] == [True, False, False]
        boundaries.append({'threshold_f32': bound, 'below_equal_above': values})
    report = {'status': 'PASS', 'scope': 'FXC compilation, spatial bytecode, specialized load counts, CPU float32 oracle only',
              'records': records, 'boundaries': boundaries}
    (args.output / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def compile_one(path, entry, integrated, adaptive, raw, include, fxc):
    cmd = [str(fxc), '/nologo', '/T', 'ps_5_0' if integrated else 'ps_4_1', '/E', entry,
           '/O3', '/Ges', '/WX', '/D', 'SMAA_PRESET_ULTRA=1', '/I', str(include),
           '/Fc', str(path.with_suffix('.asm')), '/Fo', str(path.with_suffix('.cso'))]
    if integrated:
        cmd += ['/D', 'SMAA_INTEGRATED_TEMPORAL_CANDIDATES=1']
    if adaptive:
        cmd += ['/D', 'SMAA_ADAPTIVE_SEARCH=1']
    if integrated and raw:
        cmd += ['/D', 'SMAA_INTEGRATED_RAW_LUMA=1']
    result = subprocess.run(cmd + [str(path)], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
    asm = path.with_suffix('.asm').read_text()
    return {'loads': len(re.findall(r'^\s*ld_indexable', asm, re.M)),
            'samples': len(re.findall(r'^\s*sample_indexable', asm, re.M)),
            'sha256': hashlib.sha256(path.with_suffix('.cso').read_bytes()).hexdigest()}


if __name__ == '__main__':
    main()
