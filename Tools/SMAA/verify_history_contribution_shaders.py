"""Compare non-diagnostic DXBC to the branch baseline; compile the weight witness."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CFG=json.loads((ROOT/'Docs/Stencil-Lifecycle-Refresh/case.json').read_text())
BASE={5:'0b4191407b340bdcaab207b7f8b3f1b872731b71',6:'304f7493c6a5e53fa3cfac5dfd084ce0e86ca459'}[CFG['case']]
FXC=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
OUT=ROOT/f'tmp/history-contribution-shaders-case{CFG["case"]}'
DOC=ROOT/f'Docs/History-Contribution/case{CFG["case"]}'
DOC.mkdir(parents=True,exist_ok=True)
for version in ('before','after'):
    folder=OUT/version
    folder.mkdir(parents=True,exist_ok=True)
    for name in ('SMAA.hlsl','SMAAWrapper.hlsl','FirstEdgeStencil.hlsl'):
        path='Projects/CMAA2/SMAA/'+name
        data=subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT) if version=='before' else (ROOT/path).read_bytes()
        (folder/name).write_bytes(data)

def compile(version,entry,file,diagnostic=False,engine=False):
    folder=OUT/version
    output=folder/(entry+'.dxbc')
    command=[str(FXC),'/nologo','/T','ps_5_0','/E',entry,'/O3','/Fo',str(output)]
    definitions={'SMAA_REPROJECTION':'1','SMAA_PRESET_ULTRA':'1',
                 'SMAA_RT_METRICS':'float4(1.0/1920.0,1.0/1061.0,1920.0,1061.0)'}
    if diagnostic:definitions['SMAA_CAPTURE_HISTORY_WEIGHT']='1'
    if engine:
        (folder/'MagicMacrosMagicFile.h').write_text(''.join('#define '+k+' '+v+'\n' for k,v in definitions.items()))
        command+=['/D','VA_COMPILED_AS_SHADER_CODE=1','/D','VA_DIRECTX=11']
    else:
        for k,v in definitions.items():command+=['/D',k+'='+v]
    command+=[str(folder/file)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True)
    assert result.returncode==0,(entry,result.stdout,result.stderr)
    return hashlib.sha256(output.read_bytes()).hexdigest()

results=[]
for file,entries in [('SMAAWrapper.hlsl',['DX10_SMAAResolvePS','DX10_SMAALumaEdgeDetectionPS','DX10_SMAABlendingWeightCalculationPS','DX10_SMAANeighborhoodBlendingPS']),
                     ('FirstEdgeStencil.hlsl',['FirstEdgeStencilPS','FirstEdgeStencilCoveragePS'])]:
    for entry in entries:
        before=compile('before',entry,file);after=compile('after',entry,file)
        assert before==after,entry
        engine_before=compile('before',entry,file,engine=True)
        engine_after=compile('after',entry,file,engine=True)
        assert engine_before==engine_after==after,entry
        results.append(dict(entry=entry,byte_exact=True,engine_include_byte_exact=True,dxbc_sha256=after))
diagnostic=compile('after','FirstEdgeHistoryContributionPS','FirstEdgeStencil.hlsl',True)
assert compile('after','FirstEdgeHistoryContributionPS','FirstEdgeStencil.hlsl',True,True)==diagnostic
record=dict(validation='PASS',case=CFG['case'],baseline=BASE,compiler=str(FXC),production_entries=results,
            diagnostic_dxbc_sha256=diagnostic,engine_macro_include_verified=True,
            scope='Six listed production entries are byte-identical in direct /D and engine-style virtual macro include compilation. Diagnostic compiled both ways. Runtime RGB still requires capture.')
(DOC/'shader-validation.json').write_text(json.dumps(record,indent=2)+'\n')
print('PASS:',len(results),'unchanged DXBC entries; native-weight diagnostic compiles',flush=True)
