"""FXC audit for tooling/adaptive-selected-cross5-minimal.

1. Against tooling/adaptive-tier-minimal (644f836): every SMAA and selected-route entry point must compile
   to the same DXBC, Original and Adaptive (SMAA_ADAPTIVE_SEARCH=1), at the four presets, with and without
   reprojection (selected-route entries with reprojection only). This branch only adds the Cross5 resolve.
2. Against the integration branch experiment/adaptive-selected-cross5 (c55db4f): the same entry points and
   the Cross5 resolve. Expected differences: the case-19 velocity edge shaders (the integration branch has
   the PreviousDepthUnpack field in the reprojection constant buffer) and the Cross5 resolve (rewritten here
   without the case-19 unknown-velocity check and with the blend inlined). Every other entry must match.

usage: audit_adaptive_selected_cross5_minimal_shaders.py --out <json>
"""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FXC = Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
FILES = ['SMAA.hlsl', 'SMAAWrapper.hlsl', 'SelectedTemporal.hlsl', 'CatmullRomHistory5Tap.hlsli']
W, T = 'SMAAWrapper.hlsl', 'SelectedTemporal.hlsl'
CORE = [(W, 'DX10_SMAAEdgeDetectionVS', 'vs_4_0'), (W, 'DX10_SMAABlendingWeightCalculationVS', 'vs_4_0'),
        (W, 'DX10_SMAANeighborhoodBlendingVS', 'vs_4_0'), (W, 'DX10_SMAAResolveVS', 'vs_4_0')]
CORE += [(W, f'DX10_SMAA{k}EdgeDetectionPS', 'ps_4_1') for k in ('LumaRaw', 'Luma', 'Color', 'Depth')]
CORE += [(W, e, 'ps_4_1') for e in ('DX10_SMAABlendingWeightCalculationPS', 'DX10_SMAANeighborhoodBlendingPS', 'DX10_SMAAResolvePS')]
SELECTED = [(T, f'Selected{k}{v}EdgePS', 'ps_5_0') for k in ('LumaRaw', 'Luma', 'Color', 'Depth') for v in ('', 'Velocity')]
SELECTED += [(T, e, 'ps_5_0') for e in ('SelectedNeighborhoodPS', 'SelectedResolvePS', 'SelectedSeedResolvePS')]
CROSS5 = [(T, 'SelectedResolveVelocityCross5PS', 'ps_5_0')]
PRESETS = ['LOW', 'MEDIUM', 'HIGH', 'ULTRA']


def extract(commit, out):
    out.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        (out / f).write_bytes(subprocess.run(['git', '-c', 'gc.auto=0', '-C', str(ROOT), 'show', f'{commit}:Projects/CMAA2/SMAA/{f}'],
                                             capture_output=True, check=True).stdout)
    return out


def compile_(src, file, entry, profile, out, preset, reprojection, adaptive):
    d = ['SMAA_RT_METRICS=float4(1.0 / 1920, 1.0 / 1061, 1920, 1061)', f'SMAA_PRESET_{preset}']
    if reprojection:
        d.append('SMAA_REPROJECTION=1')
    if adaptive:
        d.append('SMAA_ADAPTIVE_SEARCH=1')
    args = [str(FXC), '/nologo', '/T', profile, '/E', entry, '/I', str(src)]
    for x in d:
        args += ['/D', x]
    args += ['/Fo', str(out), str(src / file)]
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode:
        return None
    return hashlib.sha256(out.read_bytes()).hexdigest()[:16]


def compare(a, b, entries, tmp, tag):
    rows = []
    for file, entry, profile in entries:
        reps = (True,) if file == T else (False, True)
        for adaptive in (False, True):
            for preset in PRESETS:
                for rep in reps:
                    ha = compile_(a, file, entry, profile, tmp / f'{tag}a.cso', preset, rep, adaptive)
                    hb = compile_(b, file, entry, profile, tmp / f'{tag}b.cso', preset, rep, adaptive)
                    rows.append(dict(entry=entry, preset=preset, reprojection=rep, adaptive=adaptive, head=ha, other=hb,
                                     same=ha is not None and ha == hb, compiled=ha is not None))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--head', default='HEAD')
    ap.add_argument('--minimal', default='644f836')
    ap.add_argument('--integration', default='c55db4f')
    ap.add_argument('--out', required=True)
    x = ap.parse_args()
    tmp = Path(tempfile.mkdtemp())
    head, mini, integ = extract(x.head, tmp / 'head'), extract(x.minimal, tmp / 'mini'), extract(x.integration, tmp / 'integ')
    vs_min = compare(head, mini, CORE + SELECTED, tmp, 'm')
    vs_int = compare(head, integ, CORE + SELECTED + CROSS5, tmp, 'i')
    velocity_edges = {f'Selected{k}VelocityEdgePS' for k in ('LumaRaw', 'Luma', 'Color', 'Depth')}
    unexpected = [r for r in vs_int if not r['same'] and r['entry'] not in velocity_edges | {'SelectedResolveVelocityCross5PS'}]
    res = dict(head=x.head, minimal=x.minimal, integration=x.integration,
               vs_minimal=dict(compiled=len(vs_min), identical=sum(r['same'] for r in vs_min), rows=vs_min),
               vs_integration=dict(compiled=len(vs_int), identical=sum(r['same'] for r in vs_int),
                                   differing_entries=sorted({r['entry'] for r in vs_int if not r['same']}),
                                   unexpected=len(unexpected), rows=vs_int),
               cross5_compiles=all(r['compiled'] for r in vs_int if r['entry'] == 'SelectedResolveVelocityCross5PS'))
    res['pass'] = res['vs_minimal']['identical'] == len(vs_min) and not unexpected and res['cross5_compiles']
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(f"vs {x.minimal}: {res['vs_minimal']['identical']}/{len(vs_min)} identical")
    print(f"vs {x.integration}: {res['vs_integration']['identical']}/{len(vs_int)} identical; differing entries: {res['vs_integration']['differing_entries']}; unexpected {len(unexpected)}")
    print('PASS' if res['pass'] else 'FAIL')


if __name__ == '__main__':
    main()
