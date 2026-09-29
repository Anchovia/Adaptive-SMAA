"""Item 6 pattern ablation: exact controls, selected/nonselected invariants, static stability."""
import argparse,csv,hashlib,json,statistics as st,struct
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[2];D=R/'Docs/Spatial-First-Edge-Pattern-Off';B=R/'Projects/CMAA2/AutoBench'
ITEM=6
ONFULL='O-T2X-R';ONSEL='ABL-SpatialFirstEdge-T2X-R'
FULL='ABL-Spatial-FullTemporal-PatternOff-R';SEL='ABL-Spatial-FirstEdge-PatternOff-R';REP=SEL+'-Repeat'
PRIOR={'bistro':'20260929_084056','minecraft':'20260929_084926'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def image(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(p,im.mode,im.size)
        return np.asarray(im).copy()
def edges(p):
    b=p.read_bytes();assert b[:4]==b'EDG1';w,h=struct.unpack_from('<2I',b,4);assert (w,h)==(1920,1061)
    a=np.frombuffer(b[12:],dtype=np.uint8).reshape(h,w,2);assert np.isin(a,[0,255]).all();return a
def dds(p):
    b=p.read_bytes();assert b[:4]==b'DDS ' and struct.unpack_from('<I',b,4)[0]==124
    h,w,pitch=struct.unpack_from('<3I',b,12);assert (w,h)==(1920,1061)
    fourcc=b[84:88];fmt=struct.unpack_from('<I',b,128)[0] if fourcc==b'DX10' else None;offset=148 if fmt is not None else 128
    if fmt==34 or fourcc==struct.pack('<I',112):a=np.frombuffer(b[offset:],dtype='<f2').reshape(h,w,2).astype(np.float32)
    elif fmt in (27,28,29,87,90,91) or (fmt is None and fourcc==b'\x00'*4):
        assert len(b)-offset==w*h*4;a=np.frombuffer(b[offset:],dtype=np.uint8).reshape(h,w,4)
        if fmt in (87,90,91) or (fmt is None and struct.unpack_from('<I',b,92)[0]==0x00ff0000):a=a[:,:,[2,1,0,3]]
    else:raise AssertionError((str(p),fourcc,fmt))
    assert np.isfinite(a).all();return a
def receipt(scene,phase):
    rs=json.loads((R/f'tmp/edge-pattern-item{ITEM}-runs.json').read_text(encoding='utf-8-sig'));rs=[r for r in rs if r['scene']==scene and r['phase']==phase];assert len(rs)==1
    r=rs[0];p=Path(r['report']);assert sha(p)==r['report_sha256'].lower()
    text=p.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    audit=json.loads((D/'source-shader-audit.json').read_text());assert r['executable_sha256'].lower()==audit['executable_sha256']
    rows=[[v.strip() for v in row] for row in csv.reader(text.splitlines()) if row]
    for row in rows:
        while row and row[-1]=='':row.pop()
    return r,[row for row in rows if row]
def capture(scene):
    rc,report=receipt(scene,'Capture');cap=Path(next(r[1] for r in report if r[0]=='capture_root'));old=B/PRIOR[scene]
    modes=[ONFULL,ONSEL,FULL,SEL,'AA-Off','O-1X',REP]
    hashes={m:{} for m in modes};currenthash={m:{} for m in [FULL,SEL]}
    for row in report:
        if row[0]=='final_hash':hashes[row[1]][int(row[2])]=row[3]
        if row[0]=='current_hash':currenthash[row[1]][int(row[2])]=row[3]
    checks=[r for r in report if r[0]=='mode_check'];assert len(checks)==240*len(modes)
    for mode in modes:
        assert list(hashes[mode])==list(range(240)),mode
        rr=[r for r in checks if r[1]==mode];assert [int(r[2]) for r in rr]==list(range(240))
        assert all(r[-1]=='PASS' for r in rr)
    for mode in [FULL,SEL]:assert list(currenthash[mode])==list(range(240))
    mismatch=dict(on_and_native_control_frames=0,repeat_frames=0,spatial_current_pixels=0,selected_pixels=0,nonselected_pixels=0,full_current_frames=0)
    rows=[];before={};probes=[];rgbhash={m:[] for m in [FULL,SEL,ONFULL,ONSEL,'O-1X','AA-Off']}
    for i in range(240):
        p=f'frame_{i:05d}';ims={m:image(cap/m/(p+'.png')) for m in [FULL,SEL]}
        for m in [ONFULL,ONSEL,'AA-Off','O-1X']:
            source=old/m/(p+'.png');mismatch['on_and_native_control_frames']+=int(sha(source)!=hashes[m][i]);ims[m]=image(source)
        for m in [FULL,SEL]:assert sha(cap/m/(p+'.png'))==hashes[m][i]
        mismatch['repeat_frames']+=int(hashes[SEL][i]!=hashes[REP][i])
        cur=image(cap/SEL/(p+'-current.png'));assert sha(cap/SEL/(p+'-current.png'))==currenthash[SEL][i]
        mismatch['full_current_frames']+=int(currenthash[FULL][i]!=currenthash[SEL][i])
        mismatch['spatial_current_pixels']+=int(np.any(cur!=ims['O-1X'],axis=2).sum())
        mask=np.any(edges(cap/SEL/(p+'-edge.rg8'))>0,axis=2)
        mismatch['selected_pixels']+=int((np.any(ims[SEL]!=ims[FULL],axis=2)&mask).sum())
        mismatch['nonselected_pixels']+=int((np.any(ims[SEL]!=cur,axis=2)&~mask).sum())
        if i==0:assert np.array_equal(ims[SEL],cur)
        if i in [0,1,59,60,61,100,179,180,181,239]:
            ds={m:{k:dds(cap/m/f'probe_{i:05d}-{k}.dds') for k in ['input','spatial','velocity']} for m in [FULL,SEL]}
            for k in ds[FULL]:assert np.array_equal(ds[FULL][k],ds[SEL][k]),(i,k)
            assert np.array_equal(ds[SEL]['spatial'][:,:,:3],cur)
            changed=int(np.any(ds[SEL]['spatial'][:,:,:3]!=ds[SEL]['input'][:,:,:3],axis=2).sum())
            assert changed>0,'Native spatial correction must be present'
            probes.append(dict(frame=i,spatial_vs_input_changed_pixels=changed,velocity_max=float(np.abs(ds[SEL]['velocity']).max())))
        row=dict(frame=i,selected_count=int(mask.sum()),selected_percent=float(mask.mean()*100))
        for m,im in ims.items():
            rgbhash[m].append(hashlib.sha256(im.tobytes()).hexdigest())
            row[m+'_step']=float(np.abs(im.astype(np.int16)-before[m].astype(np.int16)).mean()) if before else None
        if before:row['mask_switch_pixels']=int(np.count_nonzero(mask!=before['mask']))
        else:row['mask_switch_pixels']=None
        rows.append(row);before={**ims,'mask':mask}
        if i%60==59:print(f'{scene} {i+1}/240 output frames verified',flush=True)
    assert sum(mismatch.values())==0,mismatch
    windows={}
    for name,start,end in [('all',0,240),('moving',60,180),('initial_still',20,60),('late_still',200,240)]:
        w=dict(selected_count_mean=st.mean(r['selected_count'] for r in rows[start:end]),selected_percent_mean=st.mean(r['selected_percent'] for r in rows[start:end]))
        if 'still' in name:
            w['unique_rgb_frames']={m:len(set(h[start:end])) for m,h in rgbhash.items()}
            w['rgb_step']={m:st.mean(r[m+'_step'] for r in rows[start+1:end]) for m in rgbhash}
            w['mask_switch_pixels']=st.mean(r['mask_switch_pixels'] for r in rows[start+1:end])
            assert all(w['unique_rgb_frames'][m]==1 and w['rgb_step'][m]==0 for m in [FULL,SEL,ONFULL,'AA-Off','O-1X']),w
            assert w['mask_switch_pixels']==0
        windows[name]=w
    out=dict(validation='PASS',static_stability='PASS',scene=scene,item=ITEM,capture=str(cap),prior=str(old),receipt=rc,frames=240,pixels_checked=240*1920*1061,mismatches=mismatch,windows=windows,probes=probes,
        scope='Paired jitter/area-pattern ablation. Native temporal math, spatial-frame history, camera/depth R. Static stability does not establish moving quality or speed.')
    D.mkdir(exist_ok=True,parents=True);(D/f'{scene}-capture.json').write_text(json.dumps(out,indent=2)+'\n')
    with (D/f'{scene}-frames.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps(dict(scene=scene,mismatches=mismatch,windows=windows),indent=2),flush=True)
def performance(scene,phase):
    rc,rows=receipt(scene,phase);modes=[ONFULL,ONSEL,FULL,SEL];runs=4 if phase=='Benchmark' else 1;n=4800 if phase=='Benchmark' else 240
    timing={m:{} for m in modes};rates=[]
    for r in rows:
        if r[0]=='timing':
            _,m,run,metric,count,mean,p95,p99,median,std,*_=r;assert m in modes and int(count)==n
            timing[m].setdefault(metric,[]).append(dict(run=int(run),samples=int(count),mean_ms=float(mean),p95_ms=float(p95),p99_ms=float(p99),median_ms=float(median),std_ms=float(std)))
        if r[0]=='rate':rates.append(r)
    for m in modes:
        assert len(timing[m])==6
        for metric,v in timing[m].items():assert sorted(r['run'] for r in v)==list(range(runs)) and all(r['mean_ms']>0 for r in v)
    means={m:{k:st.mean(r['mean_ms'] for r in v) for k,v in d.items()} for m,d in timing.items()}
    comparisons={}
    for name,a,b in [('selection_pattern_on',ONSEL,ONFULL),('selection_pattern_off',SEL,FULL),('off_selective_vs_native_on',SEL,ONFULL),('off_vs_on_selective',SEL,ONSEL)]:
        comparisons[name]={k:dict(delta_ms=means[a][k]-means[b][k],delta_percent=(means[a][k]/means[b][k]-1)*100,paired_percent_by_run=[(x['mean_ms']/y['mean_ms']-1)*100 for x,y in zip(timing[a][k],timing[b][k])]) for k in means[a]}
    out=dict(validation='PASS',classification='engineering',scene=scene,item=ITEM,phase=phase,receipt=rc,sample_frames_per_run=n,repeats=runs,window='hidden',means_ms=means,timing=timing,rates=rates,comparisons=comparisons)
    (D/f'{scene}-{phase.lower()}.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(scene=scene,phase=phase,means_ms=means,comparisons=comparisons),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);p.add_argument('--phase',choices=['Capture','Smoke','Benchmark'],default='Capture');a=p.parse_args()
    capture(a.scene) if a.phase=='Capture' else performance(a.scene,a.phase)
