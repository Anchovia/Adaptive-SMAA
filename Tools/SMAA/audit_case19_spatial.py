"""Compare optimized non-debug FXC output with the preserved case18 source tree."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FXC=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
ENTRIES={
 'PersistenceEdgeStencil.hlsl':['PersistenceLumaRawEdgePS','PersistenceLumaEdgePS','PersistenceColorEdgePS','PersistenceDepthEdgePS'],
 'SMAAWrapper.hlsl':['DX10_SMAALumaRawEdgeDetectionPS','DX10_SMAABlendingWeightCalculationPS','DX10_SMAANeighborhoodBlendingPS','DX10_SMAAResolvePS'],
 'SourceTemporalComponent.hlsl':['SourceComponentPS'],
 'FixedWeightRGBFeedback.hlsl':['FixedWeightRGBFeedbackPS'],
 'ResolvedRGBFeedback.hlsl':['NeighborhoodFeedbackSeedPS'],
}
def compile_shader(src,file,entry,out,gather=False,size=(1920,1061)):
    w,h=size
    cmd=[str(FXC),'/nologo','/T','ps_5_0','/E',entry,'/O3','/Ges','/I',str(src),
         '/D','SMAA_HLSL_4_1=1','/D','SMAA_PRESET_ULTRA=1','/D','SMAA_REPROJECTION=1',
         '/D',f'SMAA_RT_METRICS=float4(1.0/{w}.0,1.0/{h}.0,{w}.0,{h}.0)']
    if gather:cmd+=['/D','CASE19_GATHER_LUMA=1']
    cmd+=['/Fo',str(out),'/Fc',str(out.with_suffix('.asm')),str(src/file)]
    p=subprocess.run(cmd,capture_output=True,timeout=60)
    if p.returncode:raise RuntimeError((p.stdout+p.stderr).decode(errors='replace'))
    asm=out.with_suffix('.asm').read_text(errors='replace')
    instructions=re.findall(r'^\s*(sample_l|sample|gather4|ld)(?:_indexable)?\b',asm,re.M)
    return out.read_bytes(),{kind:instructions.count(kind) for kind in sorted(set(instructions))}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',required=True);ap.add_argument('--out',required=True);x=ap.parse_args()
    out=Path(x.out);out.mkdir(parents=True,exist_ok=True)
    head=ROOT/'Projects/CMAA2/SMAA';base=Path(x.baseline);rows=[]
    for size in [(1920,1061),(65,33)]:
        for file,entries in ENTRIES.items():
            for entry in entries:
                stem=f'{entry}-{size[0]}x{size[1]}'
                a,stats=compile_shader(head,file,entry,out/(stem+'-head.dxbc'),size=size)
                b,_=compile_shader(base,file,entry,out/(stem+'-base.dxbc'),size=size)
                rows.append(dict(entry=entry,size=size,macro_off_byte_identical=a==b,sha256=hashlib.sha256(a).hexdigest()))
    a,baseline=compile_shader(head,'PersistenceEdgeStencil.hlsl','PersistenceLumaRawEdgePS',out/'raw-point.dxbc')
    b,gather=compile_shader(head,'PersistenceEdgeStencil.hlsl','PersistenceLumaRawEdgePS',out/'raw-gather.dxbc',True)
    result=dict(validation='PASS' if all(r['macro_off_byte_identical'] for r in rows) else 'FAIL',
        compiler=str(FXC),comparison='O3 + strict, debug omitted for executable DXBC comparison; runtime uses debug metadata additionally',
        baseline=str(base),existing_entries=rows,point_texture_instructions=baseline,gather_texture_instructions=gather,
        changed_entry='PersistenceLumaRawEdgePS only when CASE19_GATHER_LUMA=1')
    (out/'shader-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='existing_entries'},indent=2))
    raise SystemExit(0 if result['validation']=='PASS' else 1)
if __name__=='__main__':main()
