"""Isolate center sharpening and segment clipping with production HLSL fixtures."""
import argparse, json, os, subprocess
import numpy as np
from pathlib import Path
from validate_recovered_clipping import compile, ROOT, SRC
from analyze_recovered_source_profile_probe import fixture, load, bicubic, X, Y, W, H, TO, FROM

BASE='d54c11abc323151b929a4c2c4e9167049a41069c'
NAMES=['Sharpen-Component','NoSharpen-Component','Sharpen-Segment','NoSharpen-Segment']

def segment(current, history, lo, hi):
    direction=history-current
    eps=np.array([1e-6,5e-7,5e-7])
    active=abs(direction)>eps
    bound=np.where(direction>0,hi,lo)
    ratios=np.divide(bound-current,direction,out=np.ones_like(direction),where=active)
    amount=np.clip(np.minimum(1,ratios.min(axis=-1)),0,1)
    return current+direction*amount[...,None]

def clip(a,history,disable_sharpen,segment_clip):
    ns=[load(a,X+x,Y+y)@TO.T for y in [-1,0,1] for x in [-1,0,1] if x or y]
    anchor=a@TO.T;c=anchor.copy()
    if not disable_sharpen:c+=(c-(ns[0]+ns[2]+ns[5]+ns[7])/4)*.263157904
    c[...,0]=np.maximum(c[...,0],0)
    n=np.stack(ns+[c]);mu=n.mean(axis=0)
    sigma=np.sqrt(np.maximum((n*n).mean(axis=0)-mu*mu,0));lo=mu-sigma;hi=mu+sigma
    h=history@TO.T
    result=segment(anchor,h,lo,hi) if segment_clip else np.minimum(np.maximum(h,lo),hi)
    return result@FROM.T,lo,hi,anchor

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'tmp/recovered-sharpen-segment/validation');a=p.parse_args()
    out=a.output;out.mkdir(parents=True,exist_ok=True);baseline=out/'baseline';baseline.mkdir(exist_ok=True)
    for f in ['SMAAWrapper.hlsl','RecoveredTSCMAA.hlsl','RecoveredTSCMAACandidate.hlsl','RecoveredTSCMAAUtility.hlsl']:
        (baseline/f).write_bytes(subprocess.check_output(['git','show',f'{BASE}:Projects/CMAA2/SMAA/{f}'],cwd=ROOT))
    fixed=['SMAA_RECOVERED_SIGNED_CHROMA=1','SMAA_RECOVERED_YCOCG_CLAMP=1']
    controls={}
    for entry in ['RecoveredExtractCS','RecoveredResolveCS']:
        for suffix,defs in [('default',[]),('corrected',fixed)]:
            old=compile(out,'old-'+suffix+entry,baseline/'RecoveredTSCMAA.hlsl',entry,defs)
            new=compile(out,'new-'+suffix+entry,SRC/'RecoveredTSCMAA.hlsl',entry,defs)
            assert old==new,(entry,suffix,old,new)
            controls[suffix+entry]=new
    build=out/'build.cmd'
    build.write_text('@echo off\ncall "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul\n'
        f'cl /nologo /EHsc /O2 /W4 /WX "{ROOT / "Tools/SMAA/recovered_source_profile_probe.cpp"}" /Fo:"{out / "probe.obj"}" /Fe:"{out / "probe.exe"}" /link d3d11.lib dxgi.lib\nexit /b %errorlevel%\n')
    subprocess.run(['cmd','/c',str(build)],env={k.upper():v for k,v in os.environ.items()},check=True,timeout=60,cwd=ROOT)
    all_gpu=[];records=[]
    for i,name in enumerate(NAMES):
        disable=i&1;seg=i>>1
        defs=fixed+[f'SMAA_RECOVERED_DISABLE_SHARPEN={disable}',f'SMAA_RECOVERED_SEGMENT_CLIP={seg}']
        compiler=compile(out,name,SRC/'RecoveredTSCMAA.hlsl','RecoveredResolveCS',defs)
        extract=compile(out,name+'-extract',SRC/'RecoveredTSCMAA.hlsl','RecoveredExtractCS',defs)
        assert extract==controls['defaultRecoveredExtractCS']
        compile(out,name+'-probe',ROOT/'Tools/SMAA/recovered_source_profile_probe.hlsl','ProfileProbeCS',defs)
        for repeat in range(2):
            subprocess.run([str(out/'probe.exe'),str(out/(name+'-probe.cso')),str(out/f'{name}-{repeat}.bin')],check=True,timeout=60)
        data=(out/f'{name}-0.bin').read_bytes();assert data==(out/f'{name}-1.bin').read_bytes()
        gpu=np.frombuffer(data,dtype=np.float32).reshape(8,H,W,4,4);assert np.isfinite(gpu).all()
        if all_gpu:assert np.array_equal(gpu[:,:,:,:2],all_gpu[0][:,:,:,:2]),'Candidate or sampler changed'
        all_gpu.append(gpu);rows=[]
        for f in range(8):
            c=fixture(f);h=c[:,::-1]
            cpu_history=bicubic(h,X+.87,Y+1.11)
            end_to_end,_,_,_=clip(c,cpu_history,disable,seg)
            # Isolate clipping from the hardware sampler's subtexel precision.
            # An outside anchor makes the segment limiter discontinuous when
            # a near-zero direction changes sign, so record that composed error.
            sampler_error=float(np.max(abs(cpu_history-gpu[f,:,:,1,:3])))
            assert sampler_error<.005,(name,f,sampler_error)
            expected,lo,hi,anchor=clip(c,gpu[f,:,:,1,:3].astype(np.float64),disable,seg)
            hist0,_,_,_=clip(c,bicubic(h,X+.5,Y+.5),disable,seg)
            final=np.floor(np.clip(np.sqrt(.789473712*hist0**2+(1-.789473712)*c**2),0,1)*255+.5)/255
            err=float(np.max(abs(gpu[f,:,:,2,:3]-expected)))
            final_err=float(np.max(abs(gpu[f,:,:,3,:3]-final))*255)
            assert err<.005 and final_err<=2.001,(name,f,err,final_err)
            actual=gpu[f,:,:,2,:3]@TO.T
            inside=np.all((anchor>=lo)&(anchor<=hi),axis=-1)
            scope=inside if seg else np.ones_like(inside)
            violation=float(max(np.max(lo[scope]-actual[scope],initial=0),np.max(actual[scope]-hi[scope],initial=0)))
            assert violation<.005,(name,f,violation)
            rows.append(dict(fixture=f,clip_max_error=err,final_max_byte_error=final_err,sampler_max_error=sampler_error,
                composed_cpu_sampler_clip_max_error=float(np.max(abs(gpu[f,:,:,2,:3]-end_to_end))),
                conditional_box_violation=violation,outside_anchor_pixels=int((~inside).sum())))
        records.append(dict(name=name,disable_sharpen=disable,segment_clip=seg,compiler=compiler,rows=rows,
                            gpu_repeat_exact=True,candidate_sampler_exact=True))
    # The document-style limiter deliberately keeps an outside anchor in this case.
    current=np.array([[2.,0.,0.]]);history=np.array([[3.,1.,0.]])
    assert np.array_equal(segment(current,history,-np.ones((1,3)),np.ones((1,3))),current)
    result=dict(status='PASS',baseline_commit=BASE,controls=controls,records=records,
        scope='8 synthetic production-function fixtures, not rendered image quality; CPU float64 tolerance .005 / final 2 LSB; box property only for inside anchors')
    (out/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
