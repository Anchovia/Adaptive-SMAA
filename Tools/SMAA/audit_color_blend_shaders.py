"""Compile case-17 shader entries before/after an optimization commit with FXC.

Existing entries must be byte-identical DXBC. New present-history entries are
compiled and their disassembly compared with the original two-target resolve
so that the RGB arithmetic can be inspected (only output writes may differ).
"""
import argparse,difflib,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'Projects/CMAA2/SMAA'
FXC=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
EXISTING={'SourceTemporalComponent.hlsl':['SourceComponentPS','SourceComponentCoveragePS'],
          'FixedWeightRGBFeedback.hlsl':['FixedWeightRGBFeedbackPS','FixedWeightRGBFeedbackCoveragePS'],
          'ResolvedRGBFeedback.hlsl':['NeighborhoodFeedbackSeedPS','ResolvedRGBFeedbackPS'],
          'FirstEdgeStencil.hlsl':['NeighborhoodRetainPS']}
NEW={'SourceTemporalComponent.hlsl':[('SourceComponentPresentPS','SourceComponentPS')],
     'FixedWeightRGBFeedback.hlsl':[('FixedWeightRGBPresentPS','FixedWeightRGBFeedbackPS')]}
def compile_(src_dir,file,entry,out,reprojection):
    defines=['/D','SMAA_HLSL_4_1=1','/D','SMAA_PRESET_ULTRA=1','/D',f'SMAA_REPROJECTION={reprojection}','/D','SMAA_RT_METRICS=float4(1.0/1920.0,1.0/1061.0,1920.0,1061.0)']
    p=subprocess.run([str(FXC),'/nologo','/T','ps_5_0','/E',entry,'/I',str(SRC),*defines,'/Fo',str(out),'/Fc',str(out.with_suffix('.asm')),str(src_dir/file)],capture_output=True)
    assert p.returncode==0,(file,entry,p.stdout+p.stderr);return out.read_bytes()
def body(asm):
    lines=[l for l in Path(asm).read_text(errors='replace').splitlines() if l and not l.startswith('//')]
    return [l for l in lines if not l.startswith('dcl_output') and not l.startswith('mov o') and not l.startswith('ret')]
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);ap.add_argument('--out',required=True);x=ap.parse_args()
    out=Path(x.out);out.mkdir(parents=True,exist_ok=True);base=out/'base-src';base.mkdir(exist_ok=True);rows=[];new=[]
    for file in set(EXISTING)|set(NEW):
        (base/file).write_bytes(subprocess.run(['git','-C',str(ROOT),'show',f'{x.base}:Projects/CMAA2/SMAA/{file}'],capture_output=True,check=True).stdout)
    for r in (0,1):
        for file,entries in EXISTING.items():
            for e in entries:
                a=compile_(SRC,file,e,out/f'{e}-R{r}-head.dxbc',r);b=compile_(base,file,e,out/f'{e}-R{r}-base.dxbc',r)
                rows.append(dict(entry=e,reprojection=r,byte_identical=a==b,sha256=hashlib.sha256(a).hexdigest()))
        for file,pairs in NEW.items():
            for e,ref in pairs:
                compile_(SRC,file,e,out/f'{e}-R{r}.dxbc',r);compile_(SRC,file,ref,out/f'{ref}-R{r}-ref.dxbc',r)
                d=list(difflib.unified_diff(body(out/f'{ref}-R{r}-ref.asm'),body(out/f'{e}-R{r}.asm'),lineterm='',n=0))
                new.append(dict(entry=e,reference=ref,reprojection=r,diff_lines=[l for l in d if not l.startswith(('---','+++','@@'))]))
    res=dict(compiler=str(FXC),base=x.base,existing=rows,existing_all_identical=all(r['byte_identical'] for r in rows),new_entries=new)
    (out/'shader-audit.json').write_text(json.dumps(res,indent=1)+'\n',encoding='utf-8')
    print(json.dumps(dict(existing_all_identical=res['existing_all_identical'],checked=len(rows)),indent=1))
    for n in new:print(n['entry'],'R',n['reprojection'],'non-output diff lines:',len(n['diff_lines']));[print('   ',l) for l in n['diff_lines'][:40]]
