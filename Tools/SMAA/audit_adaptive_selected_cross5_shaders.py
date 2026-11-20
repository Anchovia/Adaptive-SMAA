"""FXC audit for experiment/adaptive-selected-cross5.

1. Original (no SMAA_ADAPTIVE_SEARCH): every SMAA entry point of the DX11 path, the selected-route
   shaders and the history filter resolves (a)(b)(c)(c') and its variants must compile to the same DXBC
   as the footprint branch (74338ff), at the four presets, with and without reprojection.
2. Adaptive (SMAA_ADAPTIVE_SEARCH=1): every entry point that tooling/adaptive-tier-minimal (644f836)
   has must compile to the same DXBC as that commit, at the four presets, with and without reprojection
   (the selected-route shaders with reprojection only, as the route requires it).
   The footprint line inherits one field from the history rejection branch (PreviousDepthUnpack in
   SMAAReprojectionConstants), which changes the constant buffer of every shader that reads it. An
   Adaptive entry that differs is compiled again from the minimal source with that field added; it
   counts as explained only if it is then identical.
3. The (c') Cross5 resolve with SMAA_ADAPTIVE_SEARCH=1 compiles and is compared with the Original one.

The macros follow SMAA::SMAA (SMAA_RT_METRICS for 1920x1061, the preset, SMAA_REPROJECTION and
SMAA_ADAPTIVE_SEARCH) and the profiles of vaSMAAWrapperDX11::CreateTechnique.

usage: audit_adaptive_selected_cross5_shaders.py --head HEAD --footprint 74338ff --minimal 644f836 --out <json>
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
FILTERS = [(T, e, 'ps_5_0') for e in ('SelectedResolveClampPS', 'SelectedResolveDepthPS', 'SelectedResolveVelocityPS',
                                      'SelectedNeighborhoodVelocityAlphaPS', 'SelectedResolveVelocityPingPongPS',
                                      'SelectedResolveVelocityPingPongKeepPS', 'SelectedResolveVelocityCross5PS',
                                      'SelectedResolveVelocityFootprint12PS')]
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
        return None, (p.stdout + p.stderr)[-400:]
    return hashlib.sha256(out.read_bytes()).hexdigest()[:16], ''


def add_depth_unpack_field(src, out):
    """Copy of a source tree with PreviousDepthUnpack added after PreviousViewProj (HLSL side)."""
    out.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        (out / f).write_bytes((src / f).read_bytes())
    w = (out / W).read_bytes().decode('utf-8')
    nl = '\r\n' if '\r\n' in w else '\n'
    old = '    float4x4 PreviousViewProj;' + nl + '#else'
    assert w.count(old) == 1
    (out / W).write_bytes(w.replace(old, '    float4x4 PreviousViewProj;' + nl + '    float4 PreviousDepthUnpack;' + nl + '#else').encode('utf-8'))
    return out


def compare(a_src, b_src, entries, tmp, adaptive, reprojection_options, tag):
    rows = []
    for file, entry, profile in entries:
        for preset in PRESETS:
            for rep in reprojection_options:
                ha, ea = compile_(a_src, file, entry, profile, tmp / f'{tag}a.cso', preset, rep, adaptive)
                hb, eb = compile_(b_src, file, entry, profile, tmp / f'{tag}b.cso', preset, rep, adaptive)
                rows.append(dict(file=file, entry=entry, preset=preset, reprojection=rep, adaptive=adaptive,
                                 head=ha, other=hb, same=ha is not None and ha == hb, error=ea or eb))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--head', default='HEAD')
    ap.add_argument('--footprint', default='74338ff')
    ap.add_argument('--minimal', default='644f836')
    ap.add_argument('--out', required=True)
    x = ap.parse_args()
    tmp = Path(tempfile.mkdtemp())
    head, fp, mini = extract(x.head, tmp / 'head'), extract(x.footprint, tmp / 'fp'), extract(x.minimal, tmp / 'mini')
    original = compare(head, fp, CORE + SELECTED + FILTERS, tmp, False, (False, True), 'o')
    adaptive = compare(head, mini, CORE, tmp, True, (False, True), 'ac') + compare(head, mini, SELECTED, tmp, True, (True,), 'as')
    mini_field = add_depth_unpack_field(mini, tmp / 'mini-field')
    for r in adaptive:
        if not r['same']:
            entry = next(e for e in CORE + SELECTED if e[1] == r['entry'])
            hb, _ = compile_(mini_field, entry[0], entry[1], entry[2], tmp / 'mf.cso', r['preset'], r['reprojection'], True)
            r['same_with_depth_unpack_field'] = hb == r['head']
    cross5 = []
    for preset in PRESETS:
        ho, _ = compile_(head, T, 'SelectedResolveVelocityCross5PS', 'ps_5_0', tmp / 'x5o.cso', preset, True, False)
        ha, ea = compile_(head, T, 'SelectedResolveVelocityCross5PS', 'ps_5_0', tmp / 'x5a.cso', preset, True, True)
        cross5.append(dict(preset=preset, original=ho, adaptive=ha, same=ho == ha, error=ea))
    res = dict(head=x.head, footprint=x.footprint, minimal=x.minimal,
               original=dict(compiled=len(original), identical=sum(r['same'] for r in original), rows=original),
               adaptive=dict(compiled=len(adaptive), identical=sum(r['same'] for r in adaptive),
                             explained_by_depth_unpack_field=sum(r.get('same_with_depth_unpack_field', False) for r in adaptive), rows=adaptive),
               cross5_adaptive_vs_original=cross5)
    res['pass'] = (res['original']['identical'] == len(original) and all(c['adaptive'] for c in cross5)
                   and all(r['same'] or r.get('same_with_depth_unpack_field') for r in adaptive))
    Path(x.out).parent.mkdir(parents=True, exist_ok=True)
    Path(x.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(f"Original vs {x.footprint}: {res['original']['identical']}/{len(original)} identical")
    print(f"Adaptive vs {x.minimal}: {res['adaptive']['identical']}/{len(adaptive)} identical, "
          f"{res['adaptive']['explained_by_depth_unpack_field']} more identical with the PreviousDepthUnpack field")
    for r in original + adaptive:
        if not r['same'] and not r.get('same_with_depth_unpack_field'):
            print('  DIFF', r['entry'], r['preset'], 'rep' if r['reprojection'] else 'norep', 'adaptive' if r['adaptive'] else 'original', r['error'][:200])
    print('Cross5 resolve Adaptive vs Original:', [(c['preset'], c['same']) for c in cross5])
    print('PASS' if res['pass'] else 'FAIL')


if __name__ == '__main__':
    main()
