"""FXC check for the T2x-R branch: every entry point of the demo against 192a2ab, and the SMAA entry points with
SMAA_REPROJECTION=1 (the T2x-R build, original search) against 60bae94, the research branch of O-T2X-R."""
import hashlib, json, subprocess, tempfile
from pathlib import Path

FXC = r'C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
REPO = r'C:/Users/USER/Desktop/research'
NEW = Path(r'C:/Users/USER/Desktop/research/tmp/worktrees/improved-smaa-demo-t2x-r/Projects/CMAA2/SMAA')
FILES = ['SMAA.hlsl', 'SMAAWrapper.hlsl', 'SelectedTemporal.hlsl', 'CatmullRomHistory5Tap.hlsli']
W, T = 'SMAAWrapper.hlsl', 'SelectedTemporal.hlsl'
CORE = [(W, e, 'vs_4_0') for e in ('DX10_SMAAEdgeDetectionVS', 'DX10_SMAABlendingWeightCalculationVS', 'DX10_SMAANeighborhoodBlendingVS', 'DX10_SMAAResolveVS')]
CORE += [(W, f'DX10_SMAA{k}EdgeDetectionPS', 'ps_4_1') for k in ('LumaRaw', 'Luma', 'Color', 'Depth')]
CORE += [(W, e, 'ps_4_1') for e in ('DX10_SMAABlendingWeightCalculationPS', 'DX10_SMAANeighborhoodBlendingPS', 'DX10_SMAAResolvePS')]
SEL = [(T, f'Selected{k}EdgePS', 'ps_5_0') for k in ('LumaRaw', 'Luma', 'Color', 'Depth')]
SEL += [(T, e, 'ps_5_0') for e in ('SelectedNeighborhoodPS', 'SelectedSeedResolvePS', 'SelectedResolveVelocityCross5PS')]
VEL = [(W, 'DX10_SMAAGenerateCameraVelocityPS', 'ps_5_0')]


def macros(preset, adaptive=False, reprojection=False):
    m = [f'SMAA_PRESET_{preset}'] + (['SMAA_REPROJECTION=1'] if reprojection else []) + (['SMAA_ADAPTIVE_SEARCH=1'] if adaptive else [])
    return m + ['SMAA_HLSL_4_1=1', 'SMAA_RT_METRICS=float4(1.0 / 1920, 1.0 / 1061, 1920, 1061)']


def comp(src, file, entry, prof, ms, out):
    args = [FXC, '/nologo', '/T', prof, '/E', entry, '/Fo', str(out)]
    for m in ms:
        args += ['/D', m]
    r = subprocess.run(args + [file], cwd=src, capture_output=True)
    return hashlib.sha256(out.read_bytes()).hexdigest() if r.returncode == 0 else 'FAIL'


def extract(commit, dst):
    dst.mkdir()
    for f in FILES:
        p = subprocess.run(['git', '-c', 'gc.auto=0', '-C', REPO, 'show', f'{commit}:Projects/CMAA2/SMAA/{f}'], capture_output=True)
        if p.returncode == 0:
            (dst / f).write_bytes(p.stdout)


rows = []
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    extract('192a2ab', t / 'demo')
    extract('60bae94', t / 'research')
    for preset in ('LOW', 'MEDIUM', 'HIGH', 'ULTRA'):
        groups = [('original vs 192a2ab', 'demo', CORE, macros(preset)), ('adaptive vs 192a2ab', 'demo', CORE + SEL, macros(preset, adaptive=True)),
                  ('T2x-R (SMAA_REPROJECTION) vs 60bae94', 'research', CORE, macros(preset, reprojection=True))]
        for group, ref, entries, ms in groups:
            for file, entry, prof in entries:
                a = comp(NEW, file, entry, prof, ms, t / 'a.bin')
                b = comp(t / ref, file, entry, prof, ms, t / 'b.bin')
                rows.append({'group': group, 'preset': preset, 'entry': entry, 'new': a, 'reference': b, 'same': a == b and a != 'FAIL'})
    for file, entry, prof in VEL:
        for group, ref in (('velocity vs 192a2ab', 'demo'), ('velocity vs 60bae94', 'research')):
            a = comp(NEW, file, entry, prof, [], t / 'a.bin'); b = comp(t / ref, file, entry, prof, [], t / 'b.bin')
            rows.append({'group': group, 'preset': '-', 'entry': entry, 'new': a, 'reference': b, 'same': a == b and a != 'FAIL'})
summary = {}
for r in rows:
    s = summary.setdefault(r['group'], [0, 0])
    s[0] += r['same']; s[1] += 1
for g, (a, n) in summary.items():
    print(f'{g}: {a}/{n} same')
print('different:', [(r['group'], r['preset'], r['entry']) for r in rows if not r['same']])
Path(r'C:/Users/USER/AppData/Local/Temp/claude/0a1930c72cdea8a6/0ad536f8-3e1a-473d-b07f-699a89f1ba0b/scratchpad/fxc-t2xr.json').write_text(json.dumps({'summary': summary, 'rows': rows}, indent=1))
