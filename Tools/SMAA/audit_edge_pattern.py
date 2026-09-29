"""Validate original shader preservation and conditional edge-only texture accesses."""
import hashlib,json,re,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];S=R/'Projects/CMAA2/SMAA';D=R/'Docs/First-Edge-Pattern-Off';T=R/'tmp/edge-pattern-item5-shaders'
def git(*args):return subprocess.check_output(['git','-c',f'safe.directory={R.as_posix()}',*args],cwd=R)
def norm(b):return b.replace(b'\r\n',b'\n')
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    T.mkdir(exist_ok=True,parents=True);D.mkdir(exist_ok=True,parents=True);unchanged={}
    for p,ref in [('SMAA.hlsl','e14f122'),('SMAAWrapper.hlsl','e14f122'),('TemporalOnlyControl.hlsl','7c2feeb'),('FirstEdgeTemporalOnly.hlsl','a774772')]:
        b=norm((S/p).read_bytes());assert b==norm(git('show',f'{ref}:Projects/CMAA2/SMAA/{p}'));unchanged[p]=sha(b)
    body=norm((S/'SMAA.cpp').read_bytes());original=norm(git('show','e14f122:Projects/CMAA2/SMAA/SMAA.cpp'))
    for start,end in [(b'void SMAA::go(',b'void SMAA::reproject('),(b'void SMAA::reproject(',b'void SMAA::separate('),(b'void SMAA::edgesDetectionPass(',b'void SMAA::blendingWeightsCalculationPass(')]:
        x=body[body.index(start):body.index(end,body.index(start))]
        if start==b'void SMAA::go(':x=x.split(b'void SMAA::detectFirstEdges(')[0]
        y=original[original.index(start):original.index(end,original.index(start))]
        assert x.rstrip()==y.rstrip(),start;unchanged[start.decode()]=sha(x.rstrip())
    fxc=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.19041.0/x64/fxc.exe');variants=[]
    for r in [0,1]:
        obj=T/f'first-edge-r{r}.dxbc';asm=T/f'first-edge-r{r}.asm'
        args=[str(fxc),'/nologo','/O3','/T','ps_4_1','/E','FirstEdgeTemporalOnlyPS','/D',f'SMAA_REPROJECTION={r}',
              '/D','SMAA_PRESET_ULTRA=1','/D','SMAA_RT_METRICS=float4(1.0/1920,1.0/1061,1920,1061)',
              '/Fo',str(obj),'/Fc',str(asm),str(S/'FirstEdgeTemporalOnly.hlsl')]
        subprocess.run(args,check=True,capture_output=True)
        text=asm.read_text();code=[l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith('//')]
        loads=[l for l in code if l.startswith(('ld ','ld_'))];assert len(loads)==1 and 't8.' in loads[0],loads
        branch=next(i for i,l in enumerate(code) if l.startswith('if_'));early=next(i for i,l in enumerate(code) if l=='ret');assert early>branch
        samples=[(i,l) for i,l in enumerate(code) if l.startswith('sample')]
        assert sum('t2.' in l for _,l in samples)==1
        assert sum('t4.' in l for _,l in samples)==1
        assert sum('t7.' in l for _,l in samples)==r
        assert all(i>early for i,l in samples if 't4.' in l or 't7.' in l)
        variants.append(dict(reprojection=r,profile='ps_4_1',dxbc_sha256=sha(obj.read_bytes()),instructions=code))
    paths=git('diff','--name-only','e14f122','--','Projects/CMAA2').decode().splitlines()
    paths+=['Projects/CMAA2/SMAA/FirstEdgeTemporalOnly.hlsl','Projects/CMAA2/FirstEdgeOnlyVerification.inl','Projects/CMAA2/EdgePatternVerification.inl']
    sources={p:sha(norm((R/p).read_bytes())) for p in sorted(set(paths)) if (R/p).is_file()}
    result=dict(validation='PASS',base='c51ca28',dependency=['7c2feeb','a774772'],branch=git('branch','--show-current').decode().strip(),
        original_unchanged=unchanged,source_sha256_lf=sources,variants=variants,compiler=str(fxc),
        executable_sha256=sha((R/'Projects/CMAA2/CMAA2.exe').read_bytes()),
        scope='Source and DXBC checks; no GPU ISA/warp/DRAM measurement. R-On actual captures; R-Off compile only.')
    (D/'source-shader-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print('PASS: native source preserved; integer edge Load and conditional history/velocity samples verified')
if __name__=='__main__':main()
