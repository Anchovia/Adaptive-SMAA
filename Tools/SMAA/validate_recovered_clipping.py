"""Production DXBC controls and independent CPU/GPU clipping-factorial gate."""
import argparse, hashlib, json, os, re, subprocess
from pathlib import Path
import numpy as np
from analyze_recovered_source_profile_probe import fixture, load, bicubic, X, Y, W, H, TO, FROM

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'Projects/CMAA2/SMAA'
BASE='c5b5a149ee7c1d992cd4d7169bea480690dc8e31'
FXC=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe')
NAMES=['SourceClip','SignedChroma','YCoCgClamp','SignedChroma-YCoCgClamp']

def clip(a,history,signed,domain):
    ns=[load(a,X+x,Y+y)@TO.T for y in [-1,0,1] for x in [-1,0,1] if x or y]
    corners=(ns[0]+ns[2]+ns[5]+ns[7])/4
    c=a@TO.T;c=c+(c-corners)*.263157904
    if signed:c[...,0]=np.maximum(c[...,0],0)
    else:c=np.maximum(c,0)
    n=np.stack(ns+[c]);mu=n.mean(axis=0)
    sigma=np.sqrt(np.maximum((n*n).mean(axis=0)-mu*mu,0));lo=mu-sigma;hi=mu+sigma
    if domain:return np.minimum(np.maximum(history@TO.T,lo),hi)@FROM.T,lo,hi
    return np.minimum(np.maximum(history,lo@FROM.T),hi@FROM.T),lo,hi

def compile(out,name,source,entry,defs):
    target=out/name
    args=[str(FXC),'/nologo','/T','cs_5_0','/E',entry,'/O3','/Ges','/WX','/I',str(SRC),
          '/Fo',str(target.with_suffix('.cso')),'/Fc',str(target.with_suffix('.asm'))]
    for d in ['SMAA_PRESET_ULTRA=1','SMAA_TSCMAA_COMPUTE=1']+defs:args+=['/D',d]
    r=subprocess.run(args+[str(source)],capture_output=True,text=True,timeout=60)
    assert r.returncode==0,r.stdout+r.stderr
    asm=target.with_suffix('.asm').read_text()
    return dict(sha256=hashlib.sha256(target.with_suffix('.cso').read_bytes()).hexdigest(),
                slots=int(re.search(r'Approximately (\d+) instruction slots',asm)[1]))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'tmp/recovered-clipping/validation');a=p.parse_args()
    out=a.output;out.mkdir(parents=True,exist_ok=True);baseline=out/'baseline';baseline.mkdir(exist_ok=True)
    for f in ['SMAAWrapper.hlsl','RecoveredTSCMAA.hlsl','RecoveredTSCMAACandidate.hlsl','RecoveredTSCMAAUtility.hlsl']:
        (baseline/f).write_bytes(subprocess.check_output(['git','show',f'{BASE}:Projects/CMAA2/SMAA/{f}'],cwd=ROOT))
    controls={}
    for entry in ['RecoveredExtractCS','RecoveredResolveCS']:
        old=compile(out,'old-'+entry,baseline/'RecoveredTSCMAA.hlsl',entry,[])
        new=compile(out,'default-'+entry,SRC/'RecoveredTSCMAA.hlsl',entry,[])
        assert old==new,(entry,old,new)
        controls[entry]=new
    # Rebuild the existing tracked, windowless hardware harness.
    build=out/'build.cmd'
    build.write_text('@echo off\ncall "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul\n'
        f'cl /nologo /EHsc /O2 /W4 /WX "{ROOT / "Tools/SMAA/recovered_source_profile_probe.cpp"}" /Fo:"{out / "probe.obj"}" /Fe:"{out / "probe.exe"}" /link d3d11.lib dxgi.lib\nexit /b %errorlevel%\n')
    subprocess.run(['cmd','/c',str(build)],env={k.upper():v for k,v in os.environ.items()},check=True,timeout=60,cwd=ROOT)
    all_gpu=[];records=[]
    for i,name in enumerate(NAMES):
        signed=i&1;domain=i>>1
        defs=[f'SMAA_RECOVERED_SIGNED_CHROMA={signed}',f'SMAA_RECOVERED_YCOCG_CLAMP={domain}']
        compiler=compile(out,name,SRC/'RecoveredTSCMAA.hlsl','RecoveredResolveCS',defs)
        extract=compile(out,name+'-extract',SRC/'RecoveredTSCMAA.hlsl','RecoveredExtractCS',defs)
        assert extract==controls['RecoveredExtractCS']
        compile(out,name+'-probe',ROOT/'Tools/SMAA/recovered_source_profile_probe.hlsl','ProfileProbeCS',defs)
        for repeat in range(2):
            subprocess.run([str(out/'probe.exe'),str(out/(name+'-probe.cso')),str(out/f'{name}-{repeat}.bin')],check=True,timeout=60)
        data=(out/f'{name}-0.bin').read_bytes();assert data==(out/f'{name}-1.bin').read_bytes()
        gpu=np.frombuffer(data,dtype=np.float32).reshape(8,H,W,4,4);assert np.isfinite(gpu).all()
        if all_gpu:assert np.array_equal(gpu[:,:,:,:2],all_gpu[0][:,:,:,:2]),'Candidate or sampler changed'
        all_gpu.append(gpu);rows=[]
        for f in range(8):
            c=fixture(f);h=c[:,::-1]
            expected,lo,hi=clip(c,bicubic(h,X+.87,Y+1.11),signed,domain)
            hist0,_,_=clip(c,bicubic(h,X+.5,Y+.5),signed,domain)
            final=np.floor(np.clip(np.sqrt(.789473712*hist0**2+(1-.789473712)*c**2),0,1)*255+.5)/255
            err=float(np.max(abs(gpu[f,:,:,2,:3]-expected)))
            final_err=float(np.max(abs(gpu[f,:,:,3,:3]-final))*255)
            assert err<.005 and final_err<=2.001,(name,f,err,final_err)
            inside=gpu[f,:,:,2,:3]@TO.T
            violation=float(max(np.max(lo-inside),np.max(inside-hi),0)) if domain else None
            if domain:assert violation<.005,(name,f,violation)
            rows.append(dict(fixture=f,clip_max_error=err,final_max_byte_error=final_err,box_violation=violation))
        examples={label:dict(clipped=gpu[f,14,17,2,:3].tolist(),final_rgb=np.rint(gpu[f,14,17,3,:3]*255).astype(int).tolist())
                  for f,label in [(1,'gray'),(2,'red'),(3,'blue')]}
        if i==3:
            assert examples['red']['final_rgb']==[255,0,0] and examples['blue']['final_rgb']==[0,0,255]
        records.append(dict(name=name,signed_chroma=signed,ycocg_clamp=domain,compiler=compiler,rows=rows,
                            flat_color_examples=examples,gpu_repeat_exact=True,candidate_sampler_exact=True))
    result=dict(status='PASS',baseline_commit=BASE,controls=controls,records=records,
        scope='8 synthetic production-function fixtures, not rendered image quality; float64 CPU with shader filtering/minprecision tolerance')
    (out/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
