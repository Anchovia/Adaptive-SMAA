"""Validate unchanged output and trace native resolve from exact input readbacks."""
import argparse,csv,hashlib,json,struct
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'Docs/Thin-Line-Trace'
OUT=ROOT/'Projects/CMAA2/Captures/thin-line-trace-20261001'
A='ABL-Spatial-FirstEdge-Stencil-PatternOff-R';C='O-T2X-R'
ROIS={'bistro':{'chairs':(1190,530,1478,722),'window':(880,430,1168,622)},
      'minecraft':{'thin_edges':(780,460,1068,652)}}
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ph(a):return hashlib.sha256(a.tobytes()).hexdigest()
def rgb(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061)
        return np.asarray(im).copy()
def dds(p):
    b=Path(p).read_bytes();assert b[:4]==b'DDS ';h,w=struct.unpack_from('<2I',b,12);assert (w,h)==(1920,1061)
    if b[84:88]==b'DX10':
        fmt=struct.unpack_from('<I',b,128)[0];off=148
        typ,n={27:(np.uint8,4),28:(np.uint8,4),29:(np.uint8,4),34:(np.float16,2),61:(np.uint8,1)}[fmt]
    else:
        off=128;fourcc=struct.unpack_from('<I',b,84)[0];bits=struct.unpack_from('<I',b,88)[0]
        if fourcc==112:typ,n=np.float16,2
        elif bits==8:typ,n=np.uint8,1
        else:raise AssertionError(('unsupported DDS',p,fourcc,bits))
    a=np.frombuffer(b[off:],typ).reshape(h,w,n)
    return a[:,:,0] if n==1 else a
def edges(p):
    b=Path(p).read_bytes();assert b[:4]==b'EDG1' and struct.unpack_from('<2I',b,4)==(1920,1061)
    a=np.frombuffer(b[12:],np.uint8).reshape(1061,1920,2);assert np.isin(a,[0,255]).all()
    return a
def linear(a):
    c=a.astype(np.float32)/np.float32(255)
    return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
def encoded(a):
    c=np.clip(a,0,1);return np.rint(255*np.where(c<=.0031308,c*12.92,1.055*c**(1/2.4)-.055)).clip(0,255).astype(np.uint8)
def reconstruct(current,previous,v):
    h,w=v.shape[:2];y,x=np.mgrid[:h,:w]
    uv=np.stack(((x.astype(np.float32)+.5)/np.float32(w),(y.astype(np.float32)+.5)/np.float32(h)),axis=-1)
    coords=(uv-v.astype(np.float32))*np.array([w,h],np.float32)
    ix=np.floor(coords[:,:,0]).astype(np.int32).clip(0,w-1);iy=np.floor(coords[:,:,1]).astype(np.int32).clip(0,h-1)
    prev=previous[iy,ix];ca=current[:,:,3].astype(np.float32)/255;pa=prev[:,:,3].astype(np.float32)/255
    # Confirmed native DXBC mul(previous alpha squared) + fused mad.
    delta=(ca.astype(np.float64)**2-(pa*pa).astype(np.float64)).astype(np.float32)
    weight=np.float32(.5)*np.clip(1-np.sqrt(np.abs(delta)/np.float32(5))*np.float32(30),0,1)
    lc=linear(current[:,:,:3]);lp=linear(prev[:,:,:3]);mix=encoded(lc+(lp-lc)*weight[:,:,None])
    frac=coords-np.floor(coords);safe=np.all((frac>.01)&(frac<.99),axis=2)
    return dict(history=prev,weight=weight,coords=coords,safe=safe,full_resolve=mix)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--scene',choices=ROIS,required=True);ap.add_argument('--phase',choices=['smoke','capture'],default='capture');args=ap.parse_args()
    s,phase=args.scene,args.phase;n=6 if phase=='smoke' else 240
    rec=json.loads((DOC/f'{s}-{phase}-run.json').read_text(encoding='utf-8-sig'))
    assert sha(rec['report'])==rec['report_sha256'].lower()
    audit=json.loads((DOC/'source-audit.json').read_text());assert rec['executable_sha256'].lower()==audit['executable_sha256']
    text=Path(rec['report']).read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    rows=[[x.strip() for x in r if x.strip()] for r in csv.reader(text.splitlines()) if r]
    cap=Path(next(r[1] for r in rows if r[0]=='capture_root'))
    checks=[r for r in rows if r[0]=='mode_check'];assert len(checks)==3*n and all(r[-1]=='PASS' for r in checks)
    base=json.loads((ROOT/f'Docs/Stencil-Lifecycle-Refresh/{s}-rgb-hashes.json').read_text())
    for m in (A,C,A+'-Repeat'):
        for f in range(n):assert ph(rgb(cap/m/f'frame_{f:05d}.png'))==base[A if m.endswith('-Repeat') else m][f],(m,f,'baseline RGB')
    print(s,phase,3*n,'baseline RGB frames exact',flush=True)
    trace_frames=list(range(1,6)) if phase=='smoke' else list(range(127,139))+list(range(173,186))+list(range(189,196))
    export={m:{name:{} for name in ROIS[s]} for m in (A,C)};records=[];previous_current={};source_hashes=[]
    old_npz={}
    if phase=='capture':
        names={'chairs':'bistro-chairs-moving','window':'bistro-window-stop','thin_edges':'minecraft-thin-edges-moving'}
        for name in ROIS[s]:
            p=ROOT/'Projects/CMAA2/Captures/history-contribution-20260930'/f'{names[name]}-case6.npz'
            if p.exists():old_npz[name]=np.load(p)
    for m in (A,C):
        for f in trace_frames:
            pre=cap/m/f'frame_{f:05d}'
            inp={k:dds(str(pre)+f'-{k}.dds') for k in ('raw','current','previous','velocity')}
            for k in inp:source_hashes.append(dict(mode=m,frame=f,kind=k,sha256=sha(str(pre)+f'-{k}.dds')))
            current,previous,v=inp['current'],inp['previous'],inp['velocity'];assert np.isfinite(v).all()
            if (m,f-1) in previous_current:assert ph(previous)==previous_current[(m,f-1)],(m,f,'history link')
            previous_current[(m,f)]=ph(current)
            e=edges(str(pre)+'-edge.rg8');mask=e.any(axis=2);final=rgb(str(pre)+'.png')
            assert np.array_equal(current[:,:,:3],rgb(str(pre)+'-current.png'))
            selected=mask if m==A else np.ones(mask.shape,bool)
            if m==A:
                assert np.array_equal(dds(str(pre)+'-coverage.dds')>0,mask)
                assert np.array_equal(final[~mask],current[:,:,:3][~mask]),(f,'nonselected not current')
            execution=[r for r in rows if r[:3]==['trace',m,str(f)]];assert len(execution)==1 and execution[0][-1]=='PASS'
            assert list(map(int,execution[0][3:5]))==[int(selected.sum())]*2
            pred=reconstruct(current,previous,v)
            expected=np.where(selected[:,:,None],pred['full_resolve'],current[:,:,:3])
            err=np.max(np.abs(expected.astype(np.int16)-final.astype(np.int16)),axis=2)
            valid=pred['safe'];mx=int(err[valid].max());p99=float(np.quantile(err[valid],.99))
            assert mx<=1,(m,f,'CPU native output mismatch',mx,p99)
            record=dict(mode=m,frame=f,selected_pixels=int(selected.sum()),safe_point_pixels=int(valid.sum()),
                point_boundary_uncertain_pixels=int((~valid).sum()),max_rgb_error_safe=mx,mean_max_rgb_error_safe=float(err[valid].mean()),
                safe_exact_rgb_percent=float(np.mean(err[valid]==0)*100),roi={})
            for name,box in ROIS[s].items():
                x0,y0,x1,y1=box;r=np.s_[y0:y1,x0:x1];store=export[m][name]
                data=dict(raw=inp['raw'][r][:,:,:3],current=current[r][:,:,:3],previous_point=pred['history'][r][:,:,:3],
                    weight=pred['weight'][r],edge=e[r],mask=selected[r],coords=pred['coords'][r],safe=valid[r],final=final[r],
                    full_resolve=pred['full_resolve'][r])
                for key,a in data.items():store.setdefault(key,[]).append(a.copy())
                extra={}
                # Independent previous GPU MRT observations, linked by identical
                # baseline output and exact coverage; no shader edits in this branch.
                if m==A and name in old_npz:
                    start=160 if name=='window' else 100;idx=f-start
                    if 0<=idx<len(old_npz[name]['weight']):
                        old=old_npz[name];assert np.array_equal(old['mask'][idx],mask[r])
                        good=valid[r]&mask[r]
                        we=float(np.max(np.abs(pred['weight'][r][good]-old['weight'][idx][good]))) if good.any() else 0
                        assert we<2e-6,(f,'prior GPU weight',we)
                        extra['prior_gpu_weight_max_error']=we
                record['roi'][name]=dict(selected_percent=float(selected[r].mean()*100),mean_selected_weight=float(pred['weight'][r][selected[r]].mean()) if selected[r].any() else 0,**extra)
            records.append(record)
        print(s,phase,m,len(trace_frames),'traces validated',flush=True)
    outputs=[]
    if phase=='capture':
        OUT.mkdir(parents=True,exist_ok=True)
        for m,regions in export.items():
            for name,data in regions.items():
                p=OUT/f'{s}-{name}-{"edge-off" if m==A else "native-on"}.npz'
                np.savez_compressed(p,frames=np.array(trace_frames),roi=np.array(ROIS[s][name]),**{k:np.stack(v) for k,v in data.items()})
                outputs.append(dict(mode=m,roi=name,path=str(p),sha256=sha(p)))
    dump(DOC/f'{s}-{phase}-validation.json',dict(validation='PASS',scene=s,phase=phase,capture=str(cap),receipt=rec,
        base='304f7493c6a5e53fa3cfac5dfd084ce0e86ca459',baseline_rgb_frames=3*n,trace_frames_per_mode=len(trace_frames),records=records,source_files=source_hashes,roi_exports=outputs,
        limitations='Point-history/weight are CPU reconstructions validated against unchanged real output and available prior GPU weights. Coordinates near point boundaries are marked uncertain. sRGB/UNORM native output tolerance is one 8-bit RGB level. No quality/speed conclusion from these checks.'))
    print('PASS',s,phase,flush=True)
if __name__=='__main__':main()
