"""Compile real-resolution shaders and preserve bytecode/source provenance."""
from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parents[2];D=R/'Docs/Edge-Persistence-Spatial-Cost';D.mkdir(exist_ok=True)
T=R/'tmp/spatial-cost-source-audit';T.mkdir(exist_ok=True)
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
for name in ['FirstEdgeStencil.hlsl','SMAAWrapper.hlsl','SMAA.hlsl']:
    (T/name).write_bytes(git('show','304f749:Projects/CMAA2/SMAA/'+name))
for name in ['SMAAWrapper.hlsl','SMAA.hlsl']:
    assert (T/name).read_bytes().replace(b'\r\n',b'\n')==(R/'Projects/CMAA2/SMAA'/name).read_bytes().replace(b'\r\n',b'\n')
entries=['ExactLumaEdgePS','ExactLumaRawEdgePS','ExactColorEdgePS','ExactDepthEdgePS','NeighborhoodRetainPS','FirstEdgeStencilPS','FirstEdgeStencilCoveragePS']
new=['NeighborhoodPersistencePS','NeighborhoodCurrentDepthPS','NeighborhoodConstantDepthPS','NeighborhoodConservativeDepthPS']
results=[]
for reproject in [0,1]:
    for entry in entries+new:
        outputs=[]
        for which,folder in [('baseline',T),('target',R/'Projects/CMAA2/SMAA')]:
            if which=='baseline' and entry not in entries:continue
            dest=T/f'{which}-{entry}-{reproject}.dxbc'
            args=[fxc,'/nologo','/T','ps_5_0','/E',entry,'/D',f'SMAA_REPROJECTION={reproject}','/D','SMAA_PRESET_ULTRA=1','/D','SMAA_RT_METRICS=float4(1.0/1920,1.0/1061,1920,1061)','/Fo',str(dest),'/Fc',str(dest.with_suffix('.asm')),str(folder/'FirstEdgeStencil.hlsl')]
            run=subprocess.run(args,capture_output=True,text=True);assert run.returncode==0,run.stdout+run.stderr
            outputs.append(sha(dest))
        if entry in entries:assert outputs[0]==outputs[1],(entry,reproject)
        results.append(dict(entry=entry,reprojection=reproject,dxbc_sha256=outputs[-1],baseline_byte_identical=entry in entries))
files=['Projects/CMAA2/CMAA2Sample.cpp','Projects/CMAA2/EdgePersistenceSpatialCost.inl','Projects/CMAA2/SMAA/SMAA.cpp','Projects/CMAA2/SMAA/SMAA.h','Projects/CMAA2/SMAA/FirstEdgeStencil.hlsl','Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp','Projects/CMAA2/SMAA/vaSMAAWrapper.h']
files.append('Projects/CMAA2/SMAA/PersistenceEdgeStencil.hlsl')
native=(R/'Projects/CMAA2/SMAA/SMAA.hlsl').read_bytes().decode('latin1').replace('\r\n','\n')
alternative=(R/files[-1]).read_text()
def function(source,name):
    start=source.index('float2 '+name+'(');brace=source.index('{',start);n=1;i=brace+1
    while n:n+=(source[i]=='{')-(source[i]=='}');i+=1
    return source[start:i]
for kind in ['Luma','LumaRaw','Color','Depth']:
    name='SMAA'+kind+'EdgeDetectionPS'
    expected=function(native,name).replace(name,'Persistence'+name).replace('discard;','return float2(0.0, 0.0);')
    assert [line.rstrip() for line in function(alternative,'Persistence'+name).splitlines()]==[line.rstrip() for line in expected.splitlines()]
    entry='Persistence'+kind+'EdgePS';dest=T/(entry+'.dxbc')
    run=subprocess.run([fxc,'/nologo','/T','ps_5_0','/E',entry,'/D','SMAA_REPROJECTION=1','/D','SMAA_PRESET_ULTRA=1','/D','SMAA_RT_METRICS=float4(1.0/1920,1.0/1061,1920,1061)','/Fo',str(dest),'/Fc',str(dest.with_suffix('.asm')),str(R/files[-1])],capture_output=True,text=True)
    assert run.returncode==0,run.stdout+run.stderr
    results.append(dict(entry=entry,dxbc_sha256=sha(dest),edge_equation_body_verified=True))
data=dict(validation='PASS',branch=git('branch','--show-current').decode().strip(),base='304f7493c6a5e53fa3cfac5dfd084ce0e86ca459',explicit_dependencies=['a8eca21','9b9953e','24c26fb'],executable_sha256=sha(R/'Projects/CMAA2/CMAA2.exe'),fxc=fxc,resolution=[1920,1061],shader_results=results,source_sha256={n:sha(R/n) for n in files},build_log_sha256=sha(R/'tmp/baseline-restart-build.log'))
(D/'source-audit.json').write_text(json.dumps(data,indent=2)+'\n')
print('PASS: native 14 bytecodes unchanged; 8 depth variants and 4 stencil edge shaders compiled at actual resolution')
