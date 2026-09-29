"""Preserve the exact native spatial code, audit reused edge-selection DXBC."""
import hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];S=R/'Projects/CMAA2/SMAA';D=R/'Docs/Spatial-First-Edge-Temporal';T=R/'tmp/spatial-first-edge-shaders'
def git(*args):return subprocess.check_output(['git','-c',f'safe.directory={R.as_posix()}',*args],cwd=R)
def norm(b):return b.replace(b'\r\n',b'\n')
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    T.mkdir(exist_ok=True,parents=True);unchanged={}
    for p in ['SMAA.hlsl','SMAAWrapper.hlsl']:
        b=norm((S/p).read_bytes());assert b==norm(git('show',f'e14f122:Projects/CMAA2/SMAA/{p}'));unchanged[p]=sha(b)
    body=norm((S/'SMAA.cpp').read_bytes());base=norm(git('show','e14f122:Projects/CMAA2/SMAA/SMAA.cpp'))
    for start,end in [(b'void SMAA::go(',b'void SMAA::reproject('),(b'void SMAA::reproject(',b'void SMAA::separate('),(b'void SMAA::edgesDetectionPass(',b'void SMAA::blendingWeightsCalculationPass('),(b'void SMAA::blendingWeightsCalculationPass(',b'void SMAA::neighborhoodBlendingPass(')]:
        x=body[body.index(start):body.index(end,body.index(start))]
        if start==b'void SMAA::go(':x=x.split(b'void SMAA::reprojectSpatialFirstEdges(')[0]
        y=base[base.index(start):base.index(end,base.index(start))];assert x.rstrip()==y.rstrip(),start;unchanged[start.decode()]=sha(x.rstrip())
    # The final spatial pass and all later helpers (including jitter) remain unchanged.
    start=b'void SMAA::neighborhoodBlendingPass('
    assert body[body.index(start):]==base[base.index(start):]
    unchanged[start.decode()]=sha(body[body.index(start):])
    wrapper=norm((S/'vaSMAAWrapperDX11.cpp').read_bytes())
    assert b'SMAA::MODE_SMAA_T2X );' in wrapper and b'prepareTemporalOnly' not in wrapper and b'detectFirstEdges' not in wrapper
    shader=norm((S/'SpatialFirstEdge.hlsl').read_bytes())
    prior=norm(git('show','a774772:Projects/CMAA2/SMAA/FirstEdgeTemporalOnly.hlsl'))
    assert shader.split(b'\n',1)[1].replace(b'SpatialFirstEdgePS',b'FirstEdgeTemporalOnlyPS')==prior.split(b'\n',1)[1]
    sample=norm((R/'Projects/CMAA2/CMAA2Sample.cpp').read_bytes())
    tick=sample[sample.index(b'void CMAA2Sample::OnTick('):sample.index(b'vaDrawResultFlags CMAA2Sample::DrawScene(')]
    assert tick.count(b'GetRenderDevice().BeginFrame(deltaTime);')==1
    assert tick.count(b'GetRenderDevice().EndAndPresentFrame(')==1
    fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.19041.0/x64/fxc.exe';variants=[]
    for r in [0,1]:
        obj=T/f'spatial-edge-r{r}.dxbc';asm=T/f'spatial-edge-r{r}.asm'
        subprocess.run([fxc,'/nologo','/O3','/T','ps_4_1','/E','SpatialFirstEdgePS','/D',f'SMAA_REPROJECTION={r}',
            '/D','SMAA_PRESET_ULTRA=1','/D','SMAA_RT_METRICS=float4(1.0/1920,1.0/1061,1920,1061)',
            '/Fo',str(obj),'/Fc',str(asm),str(S/'SpatialFirstEdge.hlsl')],check=True,capture_output=True)
        code=[l.strip() for l in asm.read_text().splitlines() if l.strip() and not l.strip().startswith('//')]
        loads=[l for l in code if l.startswith(('ld ','ld_'))];assert len(loads)==1 and 't8.' in loads[0]
        branch=next(i for i,l in enumerate(code) if l.startswith('if_'));early=next(i for i,l in enumerate(code) if l=='ret');assert early>branch
        samples=[(i,l) for i,l in enumerate(code) if l.startswith('sample')]
        assert sum('t2.' in l for _,l in samples)==sum('t4.' in l for _,l in samples)==1
        assert sum('t7.' in l for _,l in samples)==r
        assert all(i>early for i,l in samples if 't4.' in l or 't7.' in l)
        variants.append(dict(reprojection=r,dxbc_sha256=sha(obj.read_bytes()),instructions=code))
    paths=git('diff','--name-only','e14f122','--','Projects/CMAA2').decode().splitlines()+['Projects/CMAA2/SMAA/SpatialFirstEdge.hlsl','Projects/CMAA2/SpatialFirstEdgeVerification.inl']
    out=dict(validation='PASS',baseline='e14f122',reused_helper='a774772',frame_lifecycle_dependency='c51ca28 -> 54f85af',branch=git('branch','--show-current').decode().strip(),
        original_unchanged=unchanged,source_sha256_lf={p:sha(norm((R/p).read_bytes())) for p in sorted(set(paths))},
        variants=variants,executable_sha256=sha((R/'Projects/CMAA2/CMAA2.exe').read_bytes()),compiler=fxc,
        scope='Native spatial source exact; selected shader math matches item 5. R-On runtime, R-Off compile only. DXBC is not GPU ISA profiling.')
    (D/'source-shader-audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print('PASS: native spatial functions/shaders exact; selected shader and conditional accesses audited')
if __name__=='__main__':main()
