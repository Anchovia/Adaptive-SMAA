"""FXC audit for tooling/adaptive-tier-minimal.

1. Original (no SMAA_ADAPTIVE_SEARCH): every SMAA entry point the DX11 path uses must compile to
   the same DXBC as the base commit, at the four presets, with and without reprojection.
2. Adaptive: every entry point must compile to the same DXBC as the research commit built with the
   macros its harness passed for the 1% tiers with the tier in an RGBA8 edge target (EdgeFormat 4,
   modes A-*-T3-1p-E4 and +Tier1pRGBA8). The selected-route shaders are compared with reprojection
   only, because the research commit added a reprojection-Off variant that the base does not have.
   The research edge shaders return a struct whose member is spelled SV_Target, the minimal ones a
   float3 spelled SV_TARGET like the Original shaders, so their DXBC differs in that signature name.
   When the bytes differ the tool compares the disassembly with the semantic names upper-cased and
   reports whether anything else differs.

The macros follow SMAA::SMAA (SMAA_RT_METRICS for 1920x1061, the preset, SMAA_REPROJECTION) and
the profiles vaSMAAWrapperDX11::CreateTechnique.

usage: audit_adaptive_tier_minimal_shaders.py --base b6c3ebc --research 019db06 --out <dir>
"""
import argparse, hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'Projects/CMAA2/SMAA'
FXC = Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
FILES = ['SMAA.hlsl', 'SMAAWrapper.hlsl', 'SelectedTemporal.hlsl', 'CatmullRomHistory5Tap.hlsli']
W = 'SMAAWrapper.hlsl'
T = 'SelectedTemporal.hlsl'
ENTRIES = [(W, 'DX10_SMAAEdgeDetectionVS', 'vs_4_0'), (W, 'DX10_SMAABlendingWeightCalculationVS', 'vs_4_0'),
           (W, 'DX10_SMAANeighborhoodBlendingVS', 'vs_4_0'), (W, 'DX10_SMAAResolveVS', 'vs_4_0')]
ENTRIES += [(W, f'DX10_SMAA{k}EdgeDetectionPS', 'ps_4_1') for k in ('LumaRaw', 'Luma', 'Color', 'Depth')]
ENTRIES += [(W, e, 'ps_4_1') for e in ('DX10_SMAABlendingWeightCalculationPS', 'DX10_SMAANeighborhoodBlendingPS', 'DX10_SMAAResolvePS')]
ENTRIES += [(T, f'Selected{k}{v}EdgePS', 'ps_5_0') for k in ('LumaRaw', 'Luma', 'Color', 'Depth') for v in ('', 'Velocity')]
ENTRIES += [(T, e, 'ps_5_0') for e in ('SelectedNeighborhoodPS', 'SelectedResolvePS', 'SelectedSeedResolvePS')]
PRESETS = ['LOW', 'MEDIUM', 'HIGH', 'ULTRA']
# Research macros of the 1% RGBA8 tier modes: SMAA::SMAA added each tier value that differed from the
# shipped default (T1 0.1, T2 1/3, steps 4/3/8, diag1 -1) as "%.9g" of the float, and MaxSteps >= 0
# as SMAA_RESEARCH_MAX_SEARCH_STEPS.
RESEARCH = {
    'ULTRA': dict(SMAA_ADAPTIVE_T1='0.0764705911', SMAA_ADAPTIVE_T2='0.201960787', SMAA_ADAPTIVE_STEPS0='3',
                  SMAA_ADAPTIVE_DIAG0='16', SMAA_ADAPTIVE_DIAG1='16', SMAA_RESEARCH_MAX_SEARCH_STEPS='20'),
    'HIGH': dict(SMAA_ADAPTIVE_T1='0.123529412', SMAA_ADAPTIVE_T2='0.201960787', SMAA_ADAPTIVE_STEPS0='2',
                 SMAA_ADAPTIVE_DIAG0='8', SMAA_ADAPTIVE_STEPS1='6', SMAA_ADAPTIVE_DIAG1='8', SMAA_RESEARCH_MAX_SEARCH_STEPS='12'),
    'MEDIUM': dict(SMAA_ADAPTIVE_T1='0.150980398', SMAA_ADAPTIVE_T2='0.300000012', SMAA_ADAPTIVE_STEPS0='3',
                   SMAA_ADAPTIVE_DIAG0='8', SMAA_ADAPTIVE_STEPS1='6', SMAA_ADAPTIVE_DIAG1='8'),
    'LOW': dict(SMAA_ADAPTIVE_T1='0.201960787', SMAA_ADAPTIVE_T2='0.249019608', SMAA_ADAPTIVE_STEPS0='2',
                SMAA_ADAPTIVE_DIAG0='8', SMAA_ADAPTIVE_STEPS1='3', SMAA_ADAPTIVE_DIAG1='8'),
}


def extract(commit, out):
    out.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        (out / f).write_bytes(subprocess.run(['git', '-C', str(ROOT), 'show', f'{commit}:Projects/CMAA2/SMAA/{f}'],
                                             capture_output=True, check=True).stdout)
    return out


def compile_(src, file, entry, profile, out, preset, reprojection, macros):
    d = ['SMAA_RT_METRICS=float4(1.0 / 1920, 1.0 / 1061, 1920, 1061)', f'SMAA_PRESET_{preset}']
    if reprojection:
        d.append('SMAA_REPROJECTION=1')
    d += [f'{k}={v}' for k, v in macros.items()]
    args = [str(FXC), '/nologo', '/T', profile, '/E', entry, '/I', str(src)]
    for x in d:
        args += ['/D', x]
    args += ['/Fo', str(out), str(src / file)]
    p = subprocess.run(args, capture_output=True)
    assert p.returncode == 0, (str(src), file, entry, preset, p.stdout + p.stderr)
    return out.read_bytes()


def disassembly(path):
    p = subprocess.run([str(FXC), '/nologo', '/dumpbin', str(path)], capture_output=True, text=True, check=True)
    return [l.rstrip() for l in p.stdout.splitlines()]


def same_but_semantic_case(a, b):
    """True when two DXBC files disassemble to the same text once semantic names are upper-cased."""
    la, lb = disassembly(a), disassembly(b)
    norm = lambda ls: [l.replace('SV_Target', 'SV_TARGET') for l in ls]
    return len(la) == len(lb) and norm(la) == norm(lb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True); ap.add_argument('--research', required=True); ap.add_argument('--out', required=True)
    x = ap.parse_args()
    out = Path(x.out); out.mkdir(parents=True, exist_ok=True)
    base = extract(x.base, out / 'base-src')
    research = extract(x.research, out / 'research-src')
    rows = []
    for preset in PRESETS:
        for r in (0, 1):
            for file, entry, profile in ENTRIES:
                for adaptive in (0, 1):
                    if adaptive and file == T and not r:
                        continue
                    tag = f'{entry}-{preset}-R{r}-A{adaptive}'
                    head = compile_(SRC, file, entry, profile, out / f'{tag}-head.dxbc', preset, r,
                                    {'SMAA_ADAPTIVE_SEARCH': '1'} if adaptive else {})
                    other = out / f'{tag}-{"research" if adaptive else "base"}.dxbc'
                    if adaptive:
                        ref = compile_(research, file, entry, profile, other, preset, r,
                                       dict(SMAA_ADAPTIVE_SEARCH='1', SMAA_ADAPTIVE_TIER_IN_EDGES='1', **RESEARCH[preset]))
                    else:
                        ref = compile_(base, file, entry, profile, other, preset, r, {})
                    rows.append(dict(entry=entry, preset=preset, reprojection=r, adaptive=adaptive,
                                     against='research' if adaptive else 'base', byte_identical=head == ref,
                                     same_but_semantic_case=head != ref and same_but_semantic_case(out / f'{tag}-head.dxbc', other),
                                     sha256=hashlib.sha256(head).hexdigest()))
    orig = [r for r in rows if not r['adaptive']]
    adap = [r for r in rows if r['adaptive']]
    res = dict(compiler=str(FXC), base=x.base, research=x.research, research_macros=RESEARCH,
               original_vs_base_identical=all(r['byte_identical'] for r in orig), original_checked=len(orig),
               adaptive_vs_research_identical=all(r['byte_identical'] for r in adap), adaptive_checked=len(adap),
               adaptive_byte_identical=sum(r['byte_identical'] for r in adap),
               adaptive_semantic_case_only=sum(r['same_but_semantic_case'] for r in adap),
               adaptive_other_differences=sum(not r['byte_identical'] and not r['same_but_semantic_case'] for r in adap),
               original_other_differences=sum(not r['byte_identical'] for r in orig),
               adaptive_differs_from_original=sum(1 for a in adap for o in orig
                                                  if (a['entry'], a['preset'], a['reprojection']) == (o['entry'], o['preset'], o['reprojection'])
                                                  and a['sha256'] != o['sha256']),
               entries=rows)
    (out / 'adaptive-tier-minimal-shader-audit.json').write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print({k: v for k, v in res.items() if k not in ('entries', 'research_macros')})
    for r in rows:
        if not r['byte_identical'] and not r['same_but_semantic_case']:
            print('DIFFERS', r['entry'], r['preset'], 'R%d' % r['reprojection'], 'vs', r['against'])


if __name__ == '__main__':
    main()
