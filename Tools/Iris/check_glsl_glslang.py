"""Compile every program of the Iris pack for every option combination with glslangValidator.

Each (program, stage) source is expanded with iris_expand.py; identical expanded sources are compiled
once. Reports per-variant results as JSON.

usage: python check_glsl_glslang.py <pack dir> <glslangValidator.exe> <work dir> <json out>
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from iris_expand import PROGRAMS, expand, variants  # noqa: E402


def main():
    pack, glslang, work, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    shaders = pack / 'shaders'
    work.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([glslang, '--version'], capture_output=True, text=True).stdout.splitlines()[:3]
    compiled, rows, failures = {}, [], 0
    for options in variants():
        for program in PROGRAMS:
            for ext, stage in (('vsh', 'vert'), ('fsh', 'frag')):
                source = expand(shaders, shaders / f'{program}.{ext}', options)
                digest = hashlib.sha256(source.encode()).hexdigest()
                if digest not in compiled:
                    path = work / f'{digest[:16]}.{stage}'
                    path.write_text(source, encoding='ascii', newline='\n')
                    result = subprocess.run([glslang, '-S', stage, str(path)], capture_output=True, text=True)
                    compiled[digest] = {'ok': result.returncode == 0, 'log': (result.stdout + result.stderr).strip()}
                    if result.returncode != 0:
                        failures += 1
                        print(f'FAIL {program}.{ext} {options}\n{compiled[digest]["log"]}')
                rows.append({'options': options, 'program': f'{program}.{ext}', 'source_sha256': digest, 'ok': compiled[digest]['ok']})
    summary = {'glslang': version, 'variants': len(list(variants())), 'program_stages': len(rows),
               'distinct_sources': len(compiled), 'failed_distinct_sources': failures,
               'all_ok': failures == 0, 'logs': {k: v['log'] for k, v in compiled.items() if v['log']}, 'rows': rows}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('variants', 'program_stages', 'distinct_sources', 'failed_distinct_sources', 'all_ok')}))


if __name__ == '__main__':
    main()
