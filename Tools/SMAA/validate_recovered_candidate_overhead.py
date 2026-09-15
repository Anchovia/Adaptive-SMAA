"""Compile optional diagnostic stores and unchanged spatial/compute controls."""
import hashlib, json, re, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'tmp/recovered-candidate-reuse/compiler'
FXC=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
SRC=ROOT/'Projects/CMAA2/SMAA'

def compile_shader(name, source, entry, target, defs):
    stem=OUT/name
    cmd=[str(FXC),'/nologo','/T',target,'/E',entry,'/O3','/Ges','/WX',
         '/I',str(SRC),'/Fo',str(stem.with_suffix('.cso')),'/Fc',str(stem.with_suffix('.asm'))]
    for definition in ['SMAA_PRESET_ULTRA=1']+defs:cmd+=['/D',definition]
    result=subprocess.run(cmd+[str(source)],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    asm=stem.with_suffix('.asm').read_text()
    return dict(sha256=hashlib.sha256(stem.with_suffix('.cso').read_bytes()).hexdigest(),
        load=len(re.findall(r'^\s*ld_indexable',asm,re.M)),
        slots=int(re.search(r'Approximately (\d+) instruction slots',asm)[1]),
        temps=int(re.search(r'dcl_temps (\d+)',asm)[1]))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    baseline=OUT/'baseline';baseline.mkdir(exist_ok=True)
    for f in ['SMAAWrapper.hlsl','RecoveredTSCMAACandidate.hlsl','RecoveredTSCMAA.hlsl']:
        data=subprocess.check_output(['git','show',f'd54c46c:Projects/CMAA2/SMAA/{f}'],cwd=ROOT)
        (baseline/f).write_bytes(data)
    records=[]
    for adaptive in (0,1):
        for raw in (0,1):
            defs=['SMAA_INTEGRATED_TEMPORAL_CANDIDATES=1','SMAA_RECOVERED_INTEGRATED_CANDIDATES=1']
            if adaptive:defs+=['SMAA_ADAPTIVE_SEARCH=1']
            if raw:defs+=['SMAA_INTEGRATED_RAW_LUMA=1']
            pair=[compile_shader(f'integrated-{adaptive}-{raw}-{v}',SRC/'SMAAWrapper.hlsl',
                'DX10_SMAALumaEdgeDetectionIntegratedTemporalCandidatesPS','ps_5_0',defs+[f'SMAA_RECOVERED_OPTIONAL_DIAGNOSTICS={v}']) for v in (0,1)]
            old=compile_shader(f'baseline-{adaptive}-{raw}',baseline/'SMAAWrapper.hlsl',
                'DX10_SMAALumaEdgeDetectionIntegratedTemporalCandidatesPS','ps_5_0',defs)
            assert old['sha256']==pair[0]['sha256']
            records.append(dict(adaptive=adaptive,raw=raw,before=pair[0],after=pair[1]))
            entry='DX10_SMAALumaRawEdgeDetectionPS' if raw else 'DX10_SMAALumaEdgeDetectionPS'
            defs=['SMAA_ADAPTIVE_SEARCH=1'] if adaptive else []
            controls=[compile_shader(f'spatial-{adaptive}-{raw}-{v}',p/'SMAAWrapper.hlsl',entry,'ps_4_1',defs) for v,p in enumerate((baseline,SRC))]
            assert controls[0]['sha256']==controls[1]['sha256']
    for entry in ['RecoveredExtractCS','RecoveredResolveCS']:
        pair=[compile_shader(f'{entry}-{v}',p/'RecoveredTSCMAA.hlsl',entry,'cs_5_0',['SMAA_TSCMAA_COMPUTE=1']) for v,p in enumerate((baseline,SRC))]
        assert pair[0]['sha256']==pair[1]['sha256']
    (OUT/'validation.json').write_text(json.dumps(dict(status='PASS',records=records,unchanged_spatial=4,unchanged_compute=2),indent=2))
    print(json.dumps(records,indent=2))

if __name__=='__main__':main()
