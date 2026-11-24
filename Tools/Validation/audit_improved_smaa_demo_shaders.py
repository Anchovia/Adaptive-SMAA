"""FXC audit for baseline/improved-smaa-demo.

Compiles the SMAA shader entry points of a worktree with the macros the demo passes (preset, SMAA_HLSL_4_1,
SMAA_RT_METRICS, SMAA_ADAPTIVE_SEARCH for the new item) and compares the DXBC with reference commits:
  1. Original SMAA (no Adaptive), four presets: every entry point against ee0020d.
  2. The new item (Adaptive), four presets: SMAA entry points and the selected route against
     tooling/adaptive-selected-cross5-minimal (60bae94). 60bae94 compiled the selected route with
     SMAA_REPROJECTION=1 except the neighborhood pass; the baseline compiles it without, which
     changes no selected entry point.
  3. The camera-velocity shader (no macros) against 60bae94.

usage: python audit_improved_smaa_demo_shaders.py --repo <repo root> --worktree <worktree> --out <json>
"""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path

FXC = Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
FILES = ['SMAA.hlsl', 'SMAAWrapper.hlsl', 'SelectedTemporal.hlsl', 'CatmullRomHistory5Tap.hlsli']
W, T = 'SMAAWrapper.hlsl', 'SelectedTemporal.hlsl'
CORE = [(W, 'DX10_SMAAEdgeDetectionVS', 'vs_4_0'), (W, 'DX10_SMAABlendingWeightCalculationVS', 'vs_4_0'),
        (W, 'DX10_SMAANeighborhoodBlendingVS', 'vs_4_0'), (W, 'DX10_SMAAResolveVS', 'vs_4_0')]
CORE += [(W, f'DX10_SMAA{k}EdgeDetectionPS', 'ps_4_1') for k in ('LumaRaw', 'Luma', 'Color', 'Depth')]
CORE += [(W, e, 'ps_4_1') for e in ('DX10_SMAABlendingWeightCalculationPS', 'DX10_SMAANeighborhoodBlendingPS', 'DX10_SMAAResolvePS')]
SELECTED = [(T, f'Selected{k}EdgePS', 'ps_5_0') for k in ('LumaRaw', 'Luma', 'Color', 'Depth')]
SELECTED += [(T, e, 'ps_5_0') for e in ('SelectedNeighborhoodPS', 'SelectedSeedResolvePS', 'SelectedResolveVelocityCross5PS')]
PRESETS = ['LOW', 'MEDIUM', 'HIGH', 'ULTRA']


def extract(repo, commit, out):
    out.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        p = subprocess.run(['git', '-c', 'gc.auto=0', '-C', str(repo), 'show', f'{commit}:Projects/CMAA2/SMAA/{f}'], capture_output=True)
        if p.returncode == 0:
            (out / f).write_bytes(p.stdout)
    return out


def compile_(src, file, entry, profile, out, macros):
    if not (src / file).is_file():
        return None
    args = [str(FXC), '/nologo', '/T', profile, '/E', entry, '/I', str(src)]
    for m in macros:
        args += ['/D', m]
    args += ['/Fo', str(out), str(src / file)]
    p = subprocess.run(args, capture_output=True, text=True)
    return hashlib.sha256(out.read_bytes()).hexdigest() if p.returncode == 0 else None


def app_macros(preset, adaptive, reprojection=False):
    m = [f'SMAA_PRESET_{preset}']
    if reprojection:
        m.append('SMAA_REPROJECTION=1')
    if adaptive:
        m.append('SMAA_ADAPTIVE_SEARCH=1')
    return m + ['SMAA_HLSL_4_1=1', 'SMAA_RT_METRICS=float4(1.0 / 1920, 1.0 / 1061, 1920, 1061)']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--worktree', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    new = Path(a.worktree) / 'Projects/CMAA2/SMAA'
    rows, ok = [], True
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        original = extract(a.repo, 'ee0020d', tmp / 'ee0020d')
        minimal = extract(a.repo, '60bae94', tmp / '60bae94')

        def check(group, ref_name, ref_dir, file, entry, profile, new_macros, ref_macros):
            nonlocal ok
            h_new = compile_(new, file, entry, profile, tmp / 'n.bin', new_macros)
            h_ref = compile_(ref_dir, file, entry, profile, tmp / 'r.bin', ref_macros)
            same = h_new is not None and h_new == h_ref
            ok &= same
            rows.append({'group': group, 'reference': ref_name, 'file': file, 'entry': entry, 'macros': new_macros,
                         'reference_macros': ref_macros, 'new_sha256': h_new, 'reference_sha256': h_ref, 'same': same})

        for preset in PRESETS:
            for file, entry, profile in CORE:
                check('original', 'ee0020d', original, file, entry, profile, app_macros(preset, False), app_macros(preset, False))
                check('new item', '60bae94', minimal, file, entry, profile, app_macros(preset, True), app_macros(preset, True))
            for file, entry, profile in SELECTED:
                ref = app_macros(preset, True, reprojection=entry != 'SelectedNeighborhoodPS')
                check('new item', '60bae94', minimal, file, entry, profile, app_macros(preset, True), ref)
        check('velocity', '60bae94', minimal, W, 'DX10_SMAAGenerateCameraVelocityPS', 'ps_5_0', [], [])
    summary = {'fxc': str(FXC), 'all_same': ok, 'compared': len(rows), 'same': sum(r['same'] for r in rows),
               'by_group': {g: [sum(r['same'] for r in rows if r['group'] == g), sum(r['group'] == g for r in rows)] for g in ('original', 'new item', 'velocity')},
               'rows': rows}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}))
    for r in rows:
        if not r['same']:
            print('DIFF', r['group'], r['entry'], r['macros'][0], r['new_sha256'] and r['new_sha256'][:12], r['reference_sha256'] and r['reference_sha256'][:12])


if __name__ == '__main__':
    main()
