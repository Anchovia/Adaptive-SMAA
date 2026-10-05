"""Compile real MRT entry points and check case10 production shader preservation."""
import hashlib,json,re,subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[2]
src=root/'Projects/CMAA2/SMAA'
out=root/'tmp/edge-resolved-rgb-feedback/shaders';out.mkdir(parents=True,exist_ok=True)
fxc=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
entries={
 'FirstEdgeStencil.hlsl':['FirstEdgeStencilPS','FirstEdgeStencilCoveragePS','NeighborhoodRetainPS','BilinearHistoryRGBPS','BilinearHistoryRGBCoveragePS'],
 'ResolvedRGBFeedback.hlsl':['NeighborhoodFeedbackSeedPS','ResolvedRGBFeedbackPS','ResolvedRGBFeedbackCoveragePS'],
}
records=[]
for reprojection in [0,1]:
    defines=['/D','SMAA_HLSL_4_1=1','/D','SMAA_PRESET_ULTRA=1','/D',f'SMAA_REPROJECTION={reprojection}']
    for file,functions in entries.items():
        for entry in functions:
            name=f'{entry}-R{reprojection}'
            cmd=[str(fxc),'/nologo','/T','ps_5_0','/E',entry,'/I',str(src),*defines,'/Fo',str(out/(name+'.dxbc')),'/Fc',str(out/(name+'.asm')),str(src/file)]
            p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            assert p.returncode==0,p.stdout.decode(errors='replace')
            asm=(out/(name+'.asm')).read_text(errors='replace')
            samples=[line.strip() for line in asm.splitlines() if re.match(r'^\s*sample(?:_\w+)*\(',line)]
            record=dict(entry=entry,reprojection=reprojection,sample_instructions=len(samples),bytecode_sha256=hashlib.sha256((out/(name+'.dxbc')).read_bytes()).hexdigest())
            if file=='FirstEdgeStencil.hlsl':
                # Existing source files are unchanged, confirmed against the imported case10 commit.
                old=subprocess.run(['git','-c',f'safe.directory={root.as_posix()}','show','96c495a:Projects/CMAA2/SMAA/FirstEdgeStencil.hlsl'],stdout=subprocess.PIPE,check=True).stdout
                before=out/'before.hlsl';before.write_bytes(old)
                oldout=out/(name+'-before.dxbc')
                p=subprocess.run([str(fxc),'/nologo','/T','ps_5_0','/E',entry,'/I',str(src),*defines,'/Fo',str(oldout),str(before)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                assert p.returncode==0,p.stdout.decode(errors='replace')
                assert oldout.read_bytes()==(out/(name+'.dxbc')).read_bytes(),name
                record['case10_byte_exact']=True
            if reprojection==1 and entry.startswith('ResolvedRGBFeedback'):
                assert len(samples)==4,(entry,samples)
                assert 'forceEarlyDepthStencil' in asm
            records.append(record)
result=dict(validation='PASS',compiler=str(fxc),entry_checks=len(records),case10_byte_exact_checks=10,records=records,
 interpretation='Case11 selected resolve retains case10 four sampling instructions. Extra MRT writes; no extra production draw/copy. Alpha feedback uses current spatial velocity metadata.')
dest=root/'Docs/Edge-Persistence-Resolved-RGB-Feedback/shader-audit.json'
dest.write_text(json.dumps(result,indent=2)+'\n')
print('PASS shader compilation,10 unchanged control bytecodes; case11 four fetches and early stencil')
