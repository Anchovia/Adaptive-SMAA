"""Compile real entry points and audit point-control preservation and sampler use."""
import hashlib,json,re,subprocess
from pathlib import Path

repo=Path(__file__).resolve().parents[2]
out=repo/'tmp/edge-bilinear-shader';out.mkdir(exist_ok=True)
fxc=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
src=repo/'Projects/CMAA2/SMAA'
base=subprocess.run(['git','show','304f749:Projects/CMAA2/SMAA/FirstEdgeStencil.hlsl'],check=True,stdout=subprocess.PIPE).stdout
(out/'before.hlsl').write_bytes(base)
records=[]
for reprojection in [0,1]:
    defines=['/D','SMAA_HLSL_4_1=1','/D','SMAA_PRESET_ULTRA=1','/D',f'SMAA_REPROJECTION={reprojection}']
    for entry in ['FirstEdgeStencilPS','FirstEdgeStencilCoveragePS','FirstEdgeStencilWeightCoveragePS','BilinearHistoryRGBPS','BilinearHistoryRGBCoveragePS']:
        name=f'{entry}-R{reprojection}'
        cmd=[str(fxc),'/nologo','/T','ps_5_0','/E',entry,'/I',str(src),*defines,'/Fo',str(out/(name+'.dxbc')),'/Fc',str(out/(name+'.asm')),str(src/'FirstEdgeStencil.hlsl')]
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        assert p.returncode==0,p.stdout.decode(errors='replace')
        asm=(out/(name+'.asm')).read_text(errors='replace')
        samples=[line.strip() for line in asm.splitlines() if re.match(r'^\s*sample(?:_\w+)*\(',line)]
        record={'entry':entry,'reprojection':reprojection,'samples':samples,'bytecode_sha256':hashlib.sha256((out/(name+'.dxbc')).read_bytes()).hexdigest()}
        if entry in ['FirstEdgeStencilPS','FirstEdgeStencilCoveragePS']:
            old=out/(name+'-before.dxbc')
            p=subprocess.run([str(fxc),'/nologo','/T','ps_5_0','/E',entry,'/I',str(src),*defines,'/Fo',str(old),str(out/'before.hlsl')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            assert p.returncode==0,p.stdout.decode(errors='replace')
            assert old.read_bytes()==(out/(name+'.dxbc')).read_bytes(),name
            record['baseline_byte_exact']=True
        records.append(record)
r1={r['entry']:r for r in records if r['reprojection']==1}
assert len(r1['FirstEdgeStencilPS']['samples'])==3
assert len(r1['BilinearHistoryRGBPS']['samples'])==4
assert len(r1['FirstEdgeStencilWeightCoveragePS']['samples'])==3
assert len(r1['BilinearHistoryRGBCoveragePS']['samples'])==4
result={'validation':'PASS','compiler':str(fxc),'fxc_sha256':hashlib.sha256(fxc.read_bytes()).hexdigest(),'new_entry_compile_checks':10,'native_point_control_byte_exact_checks':4,'records':records,'interpretation':'R path: original3 fetch instructions vs RGB-only bilinear4; capture weight witness does not add fetch instructions. No new rendering pass.'}
(repo/'Docs/Edge-Persistence-Bilinear-History-RGB/shader-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('PASS:10 entries;4 byte-exact controls;point3 vs bilinear4 sample instructions.')
