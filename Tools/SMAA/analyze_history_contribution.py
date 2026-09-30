"""Validate measured native history weights and paired current-to-final RGB changes."""
import argparse
import csv
import hashlib
import json
import struct
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
CFG=json.loads((ROOT/'Docs/Stencil-Lifecycle-Refresh/case.json').read_text())
CASE=CFG['case']
BASE={5:'0b4191407b340bdcaab207b7f8b3f1b872731b71',6:'304f7493c6a5e53fa3cfac5dfd084ce0e86ca459'}[CASE]
DOC=ROOT/f'Docs/History-Contribution/case{CASE}'
OUT=ROOT/'Projects/CMAA2/Captures/history-contribution-20260930'
CLIPS=[dict(id='bistro-chairs-moving',scene='bistro',title='Bistro · 의자 다리 / 이동',start=100,end=160,roi=[1190,530,1478,722],fps=30),
       dict(id='minecraft-thin-edges-moving',scene='minecraft',title='Minecraft · 얇은 경계 / 이동',start=100,end=160,roi=[780,460,1068,652],fps=30),
       dict(id='bistro-window-stop',scene='bistro',title='Bistro · 창살 / 이동 → 정지',start=160,end=220,roi=[880,430,1168,622],fps=15)]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def git_json(ref,path):return json.loads(subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT))
def rgb(path):
    with Image.open(path) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(path,im.mode,im.size)
        return np.asarray(im).copy()
def rhash(a):return hashlib.sha256(a.tobytes()).hexdigest()

def dds(path):
    b=Path(path).read_bytes();assert b[:4]==b'DDS '
    h,w=struct.unpack_from('<2I',b,12);assert (w,h)==(1920,1061)
    if b[84:88]==b'DX10':
        fmt=struct.unpack_from('<I',b,128)[0];offset=148
        dtype,channels={27:(np.uint8,4),28:(np.uint8,4),29:(np.uint8,4),41:(np.float32,1),34:(np.float16,2),61:(np.uint8,1)}[fmt]
    else:
        offset=128;fourcc=struct.unpack_from('<I',b,84)[0]
        if fourcc in (112,114):dtype,channels={112:(np.float16,2),114:(np.float32,1)}[fourcc]
        else:
            bits=struct.unpack_from('<I',b,88)[0];assert bits==8
            dtype,channels=np.uint8,1
    a=np.frombuffer(b[offset:],dtype).reshape(h,w,channels)
    return a[:,:,0] if channels==1 else a

def weight_reference(folder,f,weight,mask):
    pre=folder/f'frame_{f:05d}'
    current=dds(str(pre)+'-current.dds');previous=dds(str(pre)+'-previous.dds')
    v=dds(str(pre)+'-velocity.dds').astype(np.float32)
    h,w=mask.shape;y,x=np.mgrid[:h,:w]
    uv=np.stack(((x.astype(np.float32)+.5)/w,(y.astype(np.float32)+.5)/h),axis=-1)
    p=(uv-v)*np.array([w,h],np.float32)
    ix=np.clip(np.floor(p[:,:,0]).astype(np.int32),0,w-1)
    iy=np.clip(np.floor(p[:,:,1]).astype(np.int32),0,h-1)
    ca=current[:,:,3].astype(np.float32)/255
    pa=previous[iy,ix,3].astype(np.float32)/255
    # DXBC uses mul(previousAlpha, previousAlpha), then mad(currentAlpha,
    # currentAlpha, -previousSquared). Mirror the single rounding of that mad;
    # separate float32 multiplies cancel exactly for equal alphas and disagree
    # with the GPU by up to ~0.0004 after sqrt near zero.
    alpha_delta=(ca.astype(np.float64)*ca.astype(np.float64)-(pa*pa).astype(np.float64)).astype(np.float32)
    cpu=np.float32(.5)*np.clip(1-np.sqrt(np.abs(alpha_delta)/np.float32(5))*np.float32(30),0,1)
    fraction=p-np.floor(p)
    # Exclude near texel selection boundaries where raster/sample precision can differ.
    safe=mask & np.all((fraction>.01)&(fraction<.99),axis=2)
    assert safe.sum()>.9*mask.sum()
    errors=np.abs(cpu[safe]-weight[safe]);maximum=float(errors.max())
    assert maximum<2e-6,(f,maximum)
    return dict(frame=f,safe_pixels=int(safe.sum()),selected_pixels=int(mask.sum()),maximum_weight_error=maximum,
        mean_weight_error=float(errors.mean()),tolerance=2e-6,arithmetic='DXBC mul + fused mad alpha delta',
        near_point_sample_boundary_excluded=int((mask&~safe).sum()))

def metrics(weight,mask,diff):
    n=int(mask.sum());w=weight[mask];d=diff[mask]
    return dict(selected=n,coverage_percent=float(mask.mean()*100),weight_mean=float(w.mean()),
        weight_p10=float(np.quantile(w,.1)),weight_median=float(np.median(w)),weight_p90=float(np.quantile(w,.9)),
        weight_zero_percent=float(np.mean(w==0)*100),weight_below_0_05_percent=float(np.mean(w<.05)*100),
        changed_selected_percent=float(np.mean(d>0)*100),delta_mean_max_rgb_level=float(d.mean()),
        delta_p95_max_rgb_level=float(np.quantile(d,.95)),delta_max_rgb_level=int(d.max())) if n else dict(selected=0)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--scene',required=True,choices=['bistro','minecraft']);a=ap.parse_args()
    receipt=json.loads((DOC/f'{a.scene}-run.json').read_text(encoding='utf-8-sig'))
    assert receipt['executable_sha256'].lower()==sha(ROOT/'Projects/CMAA2/CMAA2.exe')
    assert receipt['report_sha256'].lower()==sha(receipt['report'])
    text=Path(receipt['report']).read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    rows=[[s.strip() for s in r if s.strip()] for r in csv.reader(text.splitlines()) if r]
    capture=Path(next(r[1] for r in rows if r[0]=='capture_root'))
    target=CFG['target'];modes=[target,'O-T2X-R',target+'-Repeat']
    checks=[r for r in rows if r[0]=='mode_check'];assert len(checks)==720 and all(r[-1]=='PASS' for r in checks)
    expected=git_json(BASE,f'Docs/Stencil-Lifecycle-Refresh/{a.scene}-rgb-hashes.json')
    verified=0
    for mode in modes:
        expected_mode=target if mode.endswith('-Repeat') else mode
        for f in range(240):
            assert rhash(rgb(capture/mode/f'frame_{f:05d}.png'))==expected[expected_mode][f],(mode,f,'RGB regression')
            verified+=1
    print(CASE,a.scene,verified,'final RGB frames match corrected baseline including diagnostic Off repeat',flush=True)
    old=Path(git_json('2b3ca2f',f'Docs/Six-Case-Stencil-Lifecycle/case{CASE}/{a.scene}-prior.json')['target_capture'])
    exports={c['id']:dict(clip=c,weight=[],delta=[],mask=[]) for c in CLIPS if c['scene']==a.scene}
    folder=capture/target;records=[];probes=[]
    for f in range(100,220):
        prefix=folder/f'frame_{f:05d}'
        weight=dds(str(prefix)+'-weight.dds');cov=dds(str(prefix)+'-coverage.dds');mask=cov>0
        assert weight.dtype==np.float32 and np.isfinite(weight).all()
        assert np.all(weight[~mask]==-1) and np.all((weight[mask]>=0)&(weight[mask]<=.5))
        assert np.array_equal(cov,dds(old/f'frame_{f:05d}-coverage.dds')),(f,'coverage changed')
        execution=[r for r in rows if r[:3]==['execution',target,str(f)]]
        assert len(execution)==1 and execution[0][-1]=='PASS' and int(execution[0][4])==int(mask.sum())
        current=rgb(str(prefix)+'-current.png');final=rgb(str(prefix)+'.png')
        delta=np.max(np.abs(final.astype(np.int16)-current.astype(np.int16)),axis=2).astype(np.uint8)
        assert not np.any(delta[~mask]),(f,'nonselected differs from current')
        rec=dict(frame=f,full=metrics(weight,mask,delta),roi={},weight_sha256=sha(str(prefix)+'-weight.dds'),
            current_rgb_sha256=rhash(current),coverage_sha256=sha(str(prefix)+'-coverage.dds'))
        for name,e in exports.items():
            c=e['clip']
            if c['start']<=f<c['end']:
                x0,y0,x1,y1=c['roi'];roi=np.s_[y0:y1,x0:x1]
                e['weight'].append(weight[roi].copy());e['delta'].append(delta[roi].copy());e['mask'].append(mask[roi].copy())
                rec['roi'][name]=metrics(weight[roi],mask[roi],delta[roi])
        if f in (100,179,180,190):probes.append(weight_reference(folder,f,weight,mask))
        records.append(rec)
    OUT.mkdir(parents=True,exist_ok=True);clips=[]
    for name,e in exports.items():
        path=OUT/f'{name}-case{CASE}.npz';np.savez_compressed(path,weight=np.stack(e['weight']),delta=np.stack(e['delta']),mask=np.stack(e['mask']))
        clips.append(dict(clip=e['clip'],data=str(path.resolve()),sha256=sha(path)))
    phases={}
    for name,lo,hi in [('moving',100,180),('transition',180,190),('late_still',190,220)]:
        selected=[r['full'] for r in records if lo<=r['frame']<hi]
        phases[name]={k:float(np.mean([r[k] for r in selected])) for k in selected[0]}
    result=dict(validation='PASS',case=CASE,scene=a.scene,baseline=BASE,capture=str(capture),source_capture_receipt=receipt,
        verified_final_rgb_frames=verified,unchanged_coverage_frames=120,nonselected_current_mismatch_pixels=0,
        weight_cpu_probes=probes,phases_frame_means=phases,frames=records,clips=clips,
        scope='Actual native GPU weight. Delta is max absolute RGB channel difference after 8-bit storage, in 0..255 levels. Neither weight nor delta is a quality or anti-flicker score. No timing result.')
    dump(DOC/f'{a.scene}-analysis.json',result);dump(OUT/f'case{CASE}-{a.scene}-analysis.json',result)
    print(CASE,a.scene,'PASS',json.dumps(phases),flush=True)

if __name__=='__main__':main()
