"""Compile real entries; preserve the 4/10/11 shaders and count case13 samples."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'Projects/CMAA2/SMAA'
OUT=ROOT/'tmp/case13-filter-shaders';OUT.mkdir(parents=True,exist_ok=True)
FXC=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
entries={'FirstEdgeStencil.hlsl':['FirstEdgeStencilPS','FirstEdgeStencilCoveragePS','NeighborhoodRetainPS','BilinearHistoryRGBPS','BilinearHistoryRGBCoveragePS'],
         'ResolvedRGBFeedback.hlsl':['NeighborhoodFeedbackSeedPS','ResolvedRGBFeedbackPS','ResolvedRGBFeedbackCoveragePS'],
         'CatmullRomRGBFeedback.hlsl':['CatmullRomRGBFeedbackPS','CatmullRomRGBFeedbackCoveragePS'],
         'SMAAWrapper.hlsl':['DX10_SMAAResolvePS','DX10_SMAANeighborhoodBlendingPS']}
records=[]
for reprojection in [0,1]:
    defines=['/D','SMAA_HLSL_4_1=1','/D','SMAA_PRESET_ULTRA=1','/D',f'SMAA_REPROJECTION={reprojection}','/D','SMAA_RT_METRICS=float4(1.0/1920.0,1.0/1061.0,1920.0,1061.0)']
    for file,names in entries.items():
        for entry in names:
            name=f'{entry}-R{reprojection}'
            common=[str(FXC),'/nologo','/T','ps_5_0','/E',entry,'/I',str(SRC),*defines]
            p=subprocess.run([*common,'/Fo',str(OUT/(name+'.dxbc')),'/Fc',str(OUT/(name+'.asm')),str(SRC/file)],capture_output=True)
            assert p.returncode==0,p.stdout+p.stderr
            asm=(OUT/(name+'.asm')).read_text(errors='replace')
            samples=[line for line in asm.splitlines() if re.match(r'^\s*sample(?:_\w+)*\(',line)]
            row=dict(entry=entry,reprojection=reprojection,sample_instructions=len(samples),bytecode_sha256=hashlib.sha256((OUT/(name+'.dxbc')).read_bytes()).hexdigest())
            if file!='CatmullRomRGBFeedback.hlsl':
                old=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','show',f'b793b74:Projects/CMAA2/SMAA/{file}'],capture_output=True,check=True).stdout
                before=OUT/'before.hlsl';before.write_bytes(old)
                previous=OUT/(name+'-before.dxbc')
                p=subprocess.run([*common,'/Fo',str(previous),str(before)],capture_output=True)
                assert p.returncode==0,p.stdout+p.stderr
                assert previous.read_bytes()==(OUT/(name+'.dxbc')).read_bytes(),name
                row['control_byte_exact']=True
            else:
                assert len(samples)==(8 if reprojection else 7),(entry,samples)
                assert 'forceEarlyDepthStencil' in asm
            records.append(row)
result=dict(validation='PASS',compiler=str(FXC),entry_checks=len(records),controls_byte_exact=sum(r.get('control_byte_exact',False) for r in records),records=records,
            interpretation='Case13 history RGB five fetches plus current, point history alpha and camera velocity: eight samples R1. Existing controls byte-exact. No new production pass.')
(ROOT/'Docs/Edge-History-Catmull-Rom-Reconstruction/shader-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['validation','entry_checks','controls_byte_exact']}))
