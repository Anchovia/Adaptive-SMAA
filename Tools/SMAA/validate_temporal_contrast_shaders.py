"""Compile native regressions and inspect current-color-only temporal DXBC."""
import hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
shader=root/'Projects/CMAA2/SMAA'
out=root/'tmp/contrast-shaders';out.mkdir(parents=True,exist_ok=True)
fxc=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
old=out/'baseline.hlsl'
old.write_bytes(subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}',
    'show','88893da:Projects/CMAA2/SMAA/SMAAWrapper.hlsl'],cwd=root))
results=[]
def compile(source,entry,reproj,target,tag):
    blob=out/f'{tag}_{entry}_{reproj}.dxbc';asm=blob.with_suffix('.asm')
    cmd=[str(fxc),'/nologo','/WX','/O3','/T',target,'/E',entry,'/D','SMAA_HLSL_4_1=1',
        '/D','SMAA_PRESET_ULTRA=1','/D',f'SMAA_REPROJECTION={reproj}',
        '/I',str(shader),'/Fo',str(blob),'/Fc',str(asm),str(source)]
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return blob.read_bytes(),asm.read_text()
for reproj in (0,1):
    for entry in ('DX10_SMAALumaEdgeDetectionPS','DX10_SMAABlendingWeightCalculationPS',
                  'DX10_SMAANeighborhoodBlendingPS','DX10_SMAAResolvePS'):
        a,_=compile(old,entry,reproj,'ps_4_1','before')
        b,_=compile(shader/'SMAAWrapper.hlsl',entry,reproj,'ps_4_1','after')
        assert a==b,(entry,reproj)
        results.append({'entry':entry,'reprojection':reproj,'byte_identical':True,
                        'sha256':hashlib.sha256(b).hexdigest()})
    for entry in ('DX10_SMAAContrastResolvePS','DX10_SMAAContrastMaskPS','DX10_SMAACurrentSpatialPS'):
        b,asm=compile(shader/'SMAAWrapper.hlsl',entry,reproj,'ps_5_0','experiment')
        if entry=='DX10_SMAAContrastResolvePS':
            assert 'deriv_rtx_fine' in asm and 'deriv_rty_fine' in asm
            assert 'dcl_resource_texture2d (float,float,float,float) t8' not in asm
            # Three fetches with R, two without R: no repeated current sample.
            samples=[l.strip() for l in asm.splitlines() if l.strip().startswith('sample')]
            assert len(samples)==(3 if reproj else 2),samples
            assert 'if_' in asm and 'ret' in asm
        results.append({'entry':entry,'reprojection':reproj,'compiled':True,
                        'sha256':hashlib.sha256(b).hexdigest()})
dest=root/'Docs/Temporal-Contrast-Initial';dest.mkdir(parents=True,exist_ok=True)
(dest/'shader-validation.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS: 8 unchanged native variants; 6 experimental variants; derivative/texture instruction checks')
