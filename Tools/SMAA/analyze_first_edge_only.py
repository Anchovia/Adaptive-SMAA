"""Validate actual first edges, selective pixel outputs, and static jitter attribution."""
import argparse,csv,hashlib,json,statistics,struct
from pathlib import Path
import numpy as np
from analyze_temporal_only import dds,image,sha

R=Path(__file__).resolve().parents[2];D=R/'Docs/First-Edge-Temporal-Only'
FULL='ABL-TemporalOnly-R';DETECT='DIAG-TemporalOnly-EdgeDetect-R';SEL='ABL-FirstEdge-TemporalOnly-R';REP=SEL+'-Repeat';NATIVE='O-T2X-R'
MODES=[FULL,DETECT,SEL,NATIVE,REP];PROBES=[0,1,59,60,61,100,179,180,181,239]
def edges(p):
    b=p.read_bytes();assert b[:4]==b'EDG1';w,h=struct.unpack_from('<2I',b,4);assert (w,h)==(1920,1061)
    a=np.frombuffer(b[12:],dtype=np.uint8).reshape(h,w,2);assert np.isin(a,[0,255]).all();return a
def receipt(scene,phase):
    rs=json.loads((R/'tmp/first-edge-only-runs.json').read_text(encoding='utf-8-sig'));found=[r for r in rs if r['scene']==scene and r['phase']==phase];assert len(found)==1
    r=found[0];p=Path(r['report']);assert sha(p)==r['report_sha256'].lower()
    text=p.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    audit=json.loads((D/'source-shader-audit.json').read_text());assert r['executable_sha256'].lower()==audit['executable_sha256']
    return r,p,text
def capture(scene):
    rc,p,text=receipt(scene,'Capture');cap=p.parent
    prior=json.loads((D/'prior-provenance.json').read_text())[scene];old=Path(prior['capture']);base=Path(prior['baseline'])
    checks=[[x.strip() for x in row] for row in csv.reader(text.splitlines()) if row and row[0].strip()=='mode_check'];assert len(checks)==1200
    for m in MODES:
        x=[r for r in checks if r[1]==m];assert [int(r[2]) for r in x]==list(range(240))
        assert all(r[3:6]==['TemporalOn','CameraR','PASS'] for r in x)
        assert sorted(f.name for f in (cap/m).glob('frame_?????.png'))==[f'frame_{i:05d}.png' for i in range(240)]
    rows=[];hashes={m:[] for m in MODES+["Current"]};before=None;lag2=None;probe_results=[]
    counts=dict(prior_full_frames=0,prior_native_frames=0,detect_only_frames=0,repeat_frames=0,selected_pixels=0,nonselected_pixels=0,edge_probe_pixels=0,rgba_probe_pixels=0)
    for i in range(240):
        prefix=f'frame_{i:05d}';ims={m:image(cap/m/f'{prefix}.png') for m in MODES}
        cur=image(cap/SEL/f'{prefix}-current.png');rg=edges(cap/SEL/f'{prefix}-edge.rg8');mask=np.any(rg>0,axis=2)
        counts['prior_full_frames']+=int(not np.array_equal(ims[FULL],image(old/FULL/f'{prefix}.png')))
        counts['prior_native_frames']+=int(not np.array_equal(ims[NATIVE],image(base/NATIVE/f'{prefix}.png')))
        counts['detect_only_frames']+=int(not np.array_equal(ims[FULL],ims[DETECT]))
        counts['repeat_frames']+=int(not np.array_equal(ims[SEL],ims[REP]))
        bad_select=np.any(ims[SEL]!=ims[FULL],axis=2)&mask
        bad_other=np.any(ims[SEL]!=cur,axis=2)&~mask
        counts['selected_pixels']+=int(bad_select.sum());counts['nonselected_pixels']+=int(bad_other.sum())
        if i==0:assert np.array_equal(cur,ims[SEL]),'Seed mismatch'
        row=dict(frame=i,selected_count=int(mask.sum()),selected_percent=float(mask.mean()*100),selected_mismatch=int(bad_select.sum()),nonselected_mismatch=int(bad_other.sum()))
        for m,im in {**ims,'Current':cur}.items():hashes[m].append(hashlib.sha256(im.tobytes()).hexdigest())
        if before is not None:
            for name,im,key in [('selective',ims[SEL],SEL),('full',ims[FULL],FULL),('native',ims[NATIVE],NATIVE),('current',cur,'Current')]:
                row[name+'_rgb_step']=float(np.abs(im.astype(np.int16)-before[key].astype(np.int16)).mean())
            delta=np.abs(ims[SEL].astype(np.int16)-before[SEL].astype(np.int16)).mean(axis=2)
            changed=delta>0
            groups={'both_selected':mask&before['mask'],'both_nonselected':~mask&~before['mask'],'selection_changed':mask!=before['mask']}
            for group,g in groups.items():
                row[group+'_pixels']=int(g.sum());row[group+'_changed_pixels']=int((g&changed).sum())
                row[group+'_rgb_step_contribution']=float(np.where(g,delta,0).mean())
            row['mask_changed_count']=int((mask!=before['mask']).sum())
            assert abs(sum(row[g+'_rgb_step_contribution'] for g in groups)-row['selective_rgb_step'])<1e-10
        else:
            for name in ['selective','full','native','current']:row[name+'_rgb_step']=None
            for group in ['both_selected','both_nonselected','selection_changed']:
                for k in ['pixels','changed_pixels','rgb_step_contribution']:row[group+'_'+k]=None
            row['mask_changed_count']=None
        row['lag2_selective_equal']=bool(np.array_equal(ims[SEL],lag2)) if lag2 is not None else None
        if i in PROBES:
            for m in [DETECT,NATIVE,REP]:counts['edge_probe_pixels']+=int(np.any(rg!=edges(cap/m/f'{prefix}-edge.rg8'),axis=2).sum())
            ds={m:{k:dds(cap/m/f'{prefix}-{k}.dds')[0] for k in ['input','prepared','velocity']} for m in [FULL,DETECT,SEL,REP]}
            for m in [DETECT,SEL,REP]:
                for k in ds[FULL]:assert np.array_equal(ds[m][k],ds[FULL][k]),(i,m,k)
            raw=ds[SEL];rgb_bad=int(np.any(raw['input'][:,:,:3]!=raw['prepared'][:,:,:3],axis=2).sum());assert rgb_bad==0
            assert np.array_equal(raw['prepared'][:,:,:3],cur)
            # A recorded checksum for each input proves exactly which frames were compared.
            probe_results.append(dict(frame=i,rgb_input_mismatch_pixels=rgb_bad,edge_rg_sha256=sha(cap/SEL/f'{prefix}-edge.rg8'),
                prepared_dds_sha256=sha(cap/SEL/f'{prefix}-prepared.dds'),input_dds_sha256=sha(cap/SEL/f'{prefix}-input.dds')))
        rows.append(row);lag2=before[SEL] if before is not None else None;before={SEL:ims[SEL],FULL:ims[FULL],NATIVE:ims[NATIVE],'Current':cur,'mask':mask}
        if i%60==59:print(f'{scene}: {i+1}/240 selection and output frames checked',flush=True)
    assert sum(counts.values())==0,counts
    windows={}
    for name,start,end in [('all',0,240),('moving',60,180),('initial_still',20,60),('late_still',200,240)]:
        rr=rows[start:end];w=dict(selected_count_mean=statistics.mean(r['selected_count'] for r in rr),selected_percent_mean=statistics.mean(r['selected_percent'] for r in rr),
             selected_count_min=min(r['selected_count'] for r in rr),selected_count_max=max(r['selected_count'] for r in rr))
        if 'still' in name:
            w['unique_rgb_frames']={m:len(set(hashes[m][start:end])) for m in [FULL,SEL,NATIVE,'Current']}
            w['lag2_selective_equal_pairs']=sum(r['lag2_selective_equal'] for r in rows[start+2:end]);w['lag2_pairs']=end-start-2
            for k in ['selective_rgb_step','full_rgb_step','native_rgb_step','current_rgb_step','mask_changed_count']:
                w[k]=statistics.mean(r[k] for r in rows[start+1:end])
            w['attribution']={g:{k:statistics.mean(r[g+'_'+k] for r in rows[start+1:end]) for k in ['pixels','changed_pixels','rgb_step_contribution']} for g in ['both_selected','both_nonselected','selection_changed']}
            assert w['unique_rgb_frames'][FULL]==w['unique_rgb_frames'][NATIVE]==1
        windows[name]=w
    result=dict(validation='PASS',scene=scene,receipt=rc,capture=str(cap),mismatches=counts,frames=240,selection_pixel_comparisons=240*1920*1061,
        probe_frames=PROBES,probes=probe_results,windows=windows,prior=prior,
        note='PASS is implementation/selection correctness, not static-quality success. Selective variation is retained as measured. Camera-only; no CGVQM/ghosting-quality claim.')
    (D/f'{scene}-capture.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    with (D/f'{scene}-frames.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps(dict(scene=scene,mismatches=counts,windows=windows),indent=2),flush=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scene',choices=['bistro','minecraft'],required=True);a=ap.parse_args();capture(a.scene)
if __name__=='__main__':main()
