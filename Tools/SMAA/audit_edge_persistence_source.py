"""Record exact renderer provenance and unchanged native shader bytecode."""
from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parents[2];D=R/'Docs/Edge-Persistence-GPU';D.mkdir(parents=True,exist_ok=True)
T=R/'tmp/persistence-source-audit';T.mkdir(parents=True,exist_ok=True)
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
for name in ['FirstEdgeStencil.hlsl','SMAAWrapper.hlsl','SMAA.hlsl']:
    (T/name).write_bytes(git('show','304f749:Projects/CMAA2/SMAA/'+name))
for name in ['SMAAWrapper.hlsl','SMAA.hlsl']:
    assert (T/name).read_bytes().replace(b'\r\n',b'\n')==(R/'Projects/CMAA2/SMAA'/name).read_bytes().replace(b'\r\n',b'\n')
results=[]
entries=['ExactLumaEdgePS','ExactLumaRawEdgePS','ExactColorEdgePS','ExactDepthEdgePS','NeighborhoodRetainPS','FirstEdgeStencilPS','FirstEdgeStencilCoveragePS']
for reproject in [0,1]:
    for entry in entries+['NeighborhoodPersistencePS','NeighborhoodCurrentDepthPS']:
        outputs=[]
        for which,folder in [('baseline',T),('target',R/'Projects/CMAA2/SMAA')]:
            if which=='baseline' and entry not in entries:continue
            dest=T/f'{which}-{entry}-{reproject}.dxbc'
            run=subprocess.run([fxc,'/nologo','/T','ps_5_0','/E',entry,'/D',f'SMAA_REPROJECTION={reproject}','/D','SMAA_PRESET_ULTRA=1','/Fo',str(dest),str(folder/'FirstEdgeStencil.hlsl')],capture_output=True,text=True)
            assert run.returncode==0,run.stdout+run.stderr
            outputs.append(sha(dest))
        if entry in entries:assert outputs[0]==outputs[1],(entry,reproject)
        results.append({'entry':entry,'reprojection':reproject,'dxbc_sha256':outputs[-1],'baseline_byte_identical':entry in entries})
files=['Projects/CMAA2/CMAA2Sample.cpp','Projects/CMAA2/EdgePersistenceVerification.inl','Projects/CMAA2/SMAA/SMAA.cpp','Projects/CMAA2/SMAA/SMAA.h','Projects/CMAA2/SMAA/FirstEdgeStencil.hlsl','Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp','Projects/CMAA2/SMAA/vaSMAAWrapper.h']
data={'validation':'PASS','branch':git('branch','--show-current').decode().strip(),'renderer_commit':git('rev-parse','HEAD').decode().strip(),'base':'304f7493c6a5e53fa3cfac5dfd084ce0e86ca459',
      'executable_sha256':sha(R/'Projects/CMAA2/CMAA2.exe'),'fxc':fxc,'shader_results':results,'source_sha256':{n:sha(R/n) for n in files},'dependencies':{'guard_and_trace':'9fefa77','cpu_decoder':'63fbd59'},'build_log_sha256':sha(R/'tmp/baseline-restart-build.log')}
(D/'source-audit.json').write_text(json.dumps(data,indent=2)+'\n')
print('PASS: 14 baseline bytecodes unchanged, 4 new variants compiled')
