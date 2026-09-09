"""Compile pre/post SMAA wrappers and compare controls and texture instructions.

Supply an unmodified wrapper (e.g. git show of the parent revision) as --before.
This is a compiler check, not a GPU image-equivalence or performance test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--fxc', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for integrated in (False, True):
        for adaptive in (False, True):
            for raw in (False, True):
                name = f'{"integrated" if integrated else "standard"}_{"adaptive" if adaptive else "original"}_{"raw" if raw else "rgb"}'
                if integrated:
                    entry = 'DX10_SMAALumaEdgeDetectionIntegratedTemporalCandidatesPS'
                else:
                    entry = 'DX10_SMAALumaRawEdgeDetectionPS' if raw else 'DX10_SMAALumaEdgeDetectionPS'
                record = {'variant': name}
                for label, source in [('before', args.before), ('after', args.after)]:
                    stem = args.output / f'{name}_{label}'
                    cmd = [str(args.fxc), '/nologo', '/T', 'ps_5_0' if integrated else 'ps_4_1',
                           '/E', entry, '/O3', '/Ges', '/WX',
                           '/D', 'SMAA_PRESET_ULTRA=1', '/I', str(args.after.resolve().parent),
                           '/Fc', str(stem.with_suffix('.asm')), '/Fo', str(stem.with_suffix('.cso'))]
                    if integrated:
                        cmd += ['/D', 'SMAA_INTEGRATED_TEMPORAL_CANDIDATES=1']
                    if adaptive:
                        cmd += ['/D', 'SMAA_ADAPTIVE_SEARCH=1']
                    if raw and integrated:
                        cmd += ['/D', 'SMAA_INTEGRATED_RAW_LUMA=1']
                    subprocess.run(cmd + [str(source)], check=True, capture_output=True)
                    asm = stem.with_suffix('.asm').read_text()
                    record[label] = {
                        'sample': len(re.findall(r'^\s*sample_indexable', asm, re.M)),
                        'load': len(re.findall(r'^\s*ld_indexable', asm, re.M)),
                        'temps': int(re.search(r'dcl_temps (\d+)', asm)[1]),
                        'instruction_slots': int(re.search(r'Approximately (\d+) instruction slots', asm)[1]),
                        'sha256': hashlib.sha256(stem.with_suffix('.cso').read_bytes()).hexdigest(),
                    }
                if integrated:
                    assert record['before']['load'] == 8, record
                    assert record['after']['load'] == 3, record
                    assert record['before']['sample'] == record['after']['sample'] == 7, record
                else:
                    assert record['before']['sha256'] == record['after']['sha256'], record
                records.append(record)
    (args.output / 'compiler_validation.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'PASS', 'variants': len(records), 'records': records}, indent=2))


if __name__ == '__main__':
    main()
