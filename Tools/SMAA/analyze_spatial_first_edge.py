"""Item 6: baseline preservation, spatial input, mask/output and jitter verification."""
import argparse,csv,hashlib,json,statistics as st,struct
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[2];D=R/'Docs/Spatial-First-Edge-Temporal'
FULL='O-T2X-R';SEL='ABL-SpatialFirstEdge-T2X-R';REP=SEL+'-Repeat';MODES=[FULL,SEL,'AA-Off','O-1X',REP]
PROBES=[0,1,59,60,61,100,179,180,181,239]
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
    rs=json.loads((R/'tmp/spatial-first-edge-runs.json').read_text(encoding='utf-8-sig'));found=[r for r in rs if r['scene']==scene and r['phase']==phase];assert len(found)==1
    r=found[0];p=Path(r['report']);assert sha(p)==r['report_sha256'].lower()
    text=p.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    audit=json.loads((D/'source-shader-audit.json').read_text());assert r['executable_sha256'].lower()==audit['executable_sha256']
    return r,p,text
def capture(scene):
    rc,p,text=receipt(scene,'Capture');cap=p.parent;prior=json.loads((D/f'{scene}-prior.json').read_text());base=Path(prior['baseline']);old=Path(prior['first_edge_only_capture'])
    checks=[[x.strip() for x in r] for r in csv.reader(text.splitlines()) if r and r[0].strip()=='mode_check'];assert len(checks)==1200
    for mode in MODES:
        rr=[r for r in checks if r[1]==mode];assert [int(r[2]) for r in rr]==list(range(240))
        temporal=mode not in ['AA-Off','O-1X'];assert all(r[3:6]==['TemporalOn' if temporal else 'TemporalOff','CameraR' if temporal else 'NoR','PASS'] for r in rr)
        assert sorted(f.name for f in (cap/mode).glob('frame_?????.png'))==[f'frame_{i:05d}.png' for i in range(240)]
    mismatch=dict(baseline_frames=0,repeat_frames=0,spatial_current_pixels=0,selected_pixels=0,nonselected_pixels=0,prior_edge_pixels=0,edge_probe_pixels=0)
    rows=[];hashes={m:[] for m in MODES+['SpatialCurrent','PriorRawSelective']};before=None;lag2=None;probes=[]
    for i in range(240):
        prefix=f'frame_{i:05d}';ims={m:image(cap/m/f'{prefix}.png') for m in MODES}
        current=image(cap/SEL/f'{prefix}-current.png');fullcurrent=image(cap/FULL/f'{prefix}-current.png')
        rg=edges(cap/SEL/f'{prefix}-edge.rg8');mask=np.any(rg>0,axis=2)
        rawsel=image(old/'ABL-FirstEdge-TemporalOnly-R'/f'{prefix}.png')
        for m in [FULL,'O-1X','AA-Off']:mismatch['baseline_frames']+=int(not np.array_equal(ims[m],image(base/m/f'{prefix}.png')))
        mismatch['repeat_frames']+=int(not np.array_equal(ims[SEL],ims[REP]))
        mismatch['spatial_current_pixels']+=int(np.any(current!=fullcurrent,axis=2).sum())
        mismatch['selected_pixels']+=int((np.any(ims[SEL]!=ims[FULL],axis=2)&mask).sum())
        mismatch['nonselected_pixels']+=int((np.any(ims[SEL]!=current,axis=2)&~mask).sum())
        mismatch['prior_edge_pixels']+=int(np.any(rg!=edges(old/'ABL-FirstEdge-TemporalOnly-R'/f'{prefix}-edge.rg8'),axis=2).sum())
        if i==0:assert np.array_equal(ims[SEL],current)
        allims={**ims,'SpatialCurrent':current,'PriorRawSelective':rawsel}
        for m,im in allims.items():hashes[m].append(hashlib.sha256(im.tobytes()).hexdigest())
        row=dict(frame=i,selected_count=int(mask.sum()),selected_percent=float(mask.mean()*100))
        for name,m in [('selective',SEL),('full',FULL),('one_x','O-1X'),('off','AA-Off'),('spatial_current','SpatialCurrent'),('prior_raw_selective','PriorRawSelective')]:
            row[name+'_rgb_step']=float(np.abs(allims[m].astype(np.int16)-before[m].astype(np.int16)).mean()) if before else None
        if before:
            delta=np.abs(ims[SEL].astype(np.int16)-before[SEL].astype(np.int16)).mean(axis=2)
            groups={'both_selected':mask&before['mask'],'both_nonselected':~mask&~before['mask'],'selection_changed':mask!=before['mask']}
            for g,sel in groups.items():
                row[g+'_pixels']=int(sel.sum());row[g+'_changed_pixels']=int((sel&(delta>0)).sum());row[g+'_contribution']=float(np.where(sel,delta,0).mean())
            assert abs(sum(row[g+'_contribution'] for g in groups)-row['selective_rgb_step'])<1e-10
        else:
            for g in ['both_selected','both_nonselected','selection_changed']:
                for k in ['pixels','changed_pixels','contribution']:row[g+'_'+k]=None
        row['lag2_selective_equal']=bool(np.array_equal(ims[SEL],lag2)) if lag2 is not None else None
        if i in PROBES:
            for m in [FULL,REP]:mismatch['edge_probe_pixels']+=int(np.any(rg!=edges(cap/m/f'{prefix}-edge.rg8'),axis=2).sum())
            ds={m:{k:dds(cap/m/f'{prefix}-{k}.dds') for k in ['input','spatial','velocity']} for m in [FULL,SEL,REP]}
            for m in [SEL,REP]:
                for k in ds[FULL]:assert np.array_equal(ds[m][k],ds[FULL][k]),(i,m,k)
            spatial=ds[SEL]['spatial'][:,:,:3];assert np.array_equal(spatial,current)
            diff=np.abs(spatial.astype(np.int16)-ds[SEL]['input'][:,:,:3].astype(np.int16))
            changed=int(np.any(diff>0,axis=2).sum());assert changed>0,'Spatial correction unexpectedly absent'
            probes.append(dict(frame=i,spatial_vs_raw_changed_pixels=changed,spatial_vs_raw_rgb_mae=float(diff.mean()),
                edge_sha256=sha(cap/SEL/f'{prefix}-edge.rg8'),spatial_dds_sha256=sha(cap/SEL/f'{prefix}-spatial.dds')))
        rows.append(row);lag2=before[SEL] if before else None;before={**allims,'mask':mask}
        if i%60==59:print(f'{scene}: {i+1}/240 spatial and output frames checked',flush=True)
    assert sum(mismatch.values())==0,mismatch
    windows={}
    for name,start,end in [('all',0,240),('moving',60,180),('initial_still',20,60),('late_still',200,240)]:
        rr=rows[start:end];w=dict(selected_count_mean=st.mean(r['selected_count'] for r in rr),selected_percent_mean=st.mean(r['selected_percent'] for r in rr))
        if 'still' in name:
            w['unique_rgb_frames']={m:len(set(hashes[m][start:end])) for m in [FULL,SEL,'O-1X','AA-Off','SpatialCurrent','PriorRawSelective']}
            for m in [FULL,'O-1X','AA-Off']:assert w['unique_rgb_frames'][m]==1
            w['lag2_equal_pairs']=sum(r['lag2_selective_equal'] for r in rows[start+2:end]);w['lag2_pairs']=end-start-2
            for k in rows[0]:
                if k.endswith(('_rgb_step','_pixels','_contribution')):w[k]=st.mean(r[k] for r in rows[start+1:end])
        windows[name]=w
    result=dict(validation='PASS',scene=scene,receipt=rc,capture=str(cap),prior=prior,frames=240,pixels_checked=240*1920*1061,
        mismatches=mismatch,probes=probes,windows=windows,note='PASS means implementation and baseline preservation. Static stability assessed separately; no CGVQM/absolute ghosting claim.')
    (D/f'{scene}-capture.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    with (D/f'{scene}-frames.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps(dict(scene=scene,mismatches=mismatch,windows=windows),indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);a=p.parse_args();capture(a.scene)
