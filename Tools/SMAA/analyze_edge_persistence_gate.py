"""One-frame previous raw-edge union; offline proxy, no GPU method or timing claim."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
from edge_persistence_trace_inputs import ROOT,A,C,ROIS,dds,edges,rgb,sha,ph,dump,reconstruct

DOC=ROOT/'Docs/Edge-Persistence-Gate'
OUT=ROOT/'Projects/CMAA2/Captures/edge-persistence-gate-20261001'

def metrics(base,proxy,ref,add,safe):
    b=np.abs(base.astype(np.float32)-ref).mean(axis=2)
    p=np.abs(proxy.astype(np.float32)-ref).mean(axis=2)
    v=add&safe;delta=p-b
    return dict(base_mae=float(b.mean()),proxy_mae=float(p.mean()),
        all_image_proxy_minus_base=float(delta.mean()),safe_added_pixels=int(v.sum()),
        safe_added_error_change_per_image_pixel=float(np.where(v,delta,0).mean()),
        safe_added_improved_gt_1=int((v&(delta < -1)).sum()),
        safe_added_worsened_gt_1=int((v&(delta > 1)).sum()),
        safe_added_mean_error_change=float(delta[v].mean()) if v.any() else 0)

def analyze(scene):
    v=json.loads((DOC/f'input/{scene}-capture-validation.json').read_text())
    assert v['validation']=='PASS';cap=Path(v['capture'])
    hashes={(r['mode'],r['frame'],r['kind']):r['sha256'] for r in v['source_files']}
    frames=sorted(r['frame'] for r in v['records'] if r['mode']==A)
    frames=[f for f in frames if f-1 in frames];assert len(frames)==29
    prior=json.loads((ROOT/f'Docs/Stencil-Lifecycle-Refresh/{scene}-prior.json').read_text())
    refdir=Path(prior['quality']['results']['moving']['records']['Spatial-Edge-Stencil-Off-R']['reference_sequence']['directory'])
    baseline=json.loads((ROOT/f'Docs/Stencil-Lifecycle-Refresh/{scene}-rgb-hashes.json').read_text())
    records=[];sources=[];exports={name:{} for name in ROIS[scene]}
    gain=np.zeros((1061,1920),np.float64)
    for f in frames:
        pre=cap/A/f'frame_{f:05d}'
        for k in ('raw','current','previous','velocity'):
            assert sha(str(pre)+f'-{k}.dds')==hashes[A,f,k]
        cur=dds(str(pre)+'-current.dds');prev=dds(str(pre)+'-previous.dds');vel=dds(str(pre)+'-velocity.dds')
        assert ph(prev)==ph(dds(cap/A/f'frame_{f-1:05d}-current.dds'))
        e=edges(str(pre)+'-edge.rg8').any(axis=2)
        ep=edges(cap/A/f'frame_{f-1:05d}-edge.rg8').any(axis=2)
        final=rgb(str(pre)+'.png');native=rgb(cap/C/f'frame_{f:05d}.png');ref=rgb(refdir/f'frame_{f:05d}.png')
        assert ph(final)==baseline[A][f] and ph(native)==baseline[C][f]
        pred=reconstruct(cur,prev,vel);q=pred['coords'];h,w=e.shape
        inside=(q[:,:,0]>=0)&(q[:,:,0]<w)&(q[:,:,1]>=0)&(q[:,:,1]<h)
        ix=np.floor(q[:,:,0]).astype(int).clip(0,w-1);iy=np.floor(q[:,:,1]).astype(int).clip(0,h-1)
        warped=ep[iy,ix]&inside;union=e|warped;add=warped&~e;safe=pred['safe']&inside
        expect=np.where(e[:,:,None],pred['full_resolve'],cur[:,:,:3])
        err=np.abs(expect.astype(np.int16)-final.astype(np.int16)).max(axis=2)
        assert err[pred['safe']].max()<=1
        assert np.array_equal(final[~e],cur[:,:,:3][~e])
        proxy=np.where(add[:,:,None],pred['full_resolve'],final)
        assert np.all(union>=e) and np.array_equal(proxy[e],final[e])
        assert np.array_equal(proxy[~union],cur[:,:,:3][~union])
        if f>=190:assert not vel.any() and np.array_equal(e,ep) and not add.any() and np.array_equal(proxy,final)
        rec=dict(frame=f,phase='moving' if f<180 else 'transition' if f<186 else 'still',
            current_pixels=int(e.sum()),union_pixels=int(union.sum()),added_pixels=int(add.sum()),
            current_percent=float(e.mean()*100),union_percent=float(union.mean()*100),
            additional_percent_of_current=float(add.sum()/e.sum()*100),
            unsafe_added_pixels=int((add&~safe).sum()),out_of_bounds_pixels=int((~inside).sum()),
            baseline_reconstruction_max_error=int(err[pred['safe']].max()),
            reference=metrics(final,proxy,ref,add,safe),roi={})
        if 130<=f<=135:
            delta=np.abs(proxy.astype(np.float32)-ref).mean(axis=2)-np.abs(final.astype(np.float32)-ref).mean(axis=2)
            gain+=np.where(add&safe,delta,0)
        for name,box in ROIS[scene].items():
            x0,y0,x1,y1=box;r=np.s_[y0:y1,x0:x1]
            rec['roi'][name]=dict(current_percent=float(e[r].mean()*100),union_percent=float(union[r].mean()*100),
                **metrics(final[r],proxy[r],ref[r],add[r],safe[r]))
            data=dict(current=cur[r][:,:,:3],history=pred['history'][r][:,:,:3],base=final[r],proxy=proxy[r],native=native[r],reference=ref[r],
                current_mask=e[r],warped_previous=warped[r],union_mask=union[r],added_mask=add[r],safe=safe[r],weight=pred['weight'][r])
            for k,a in data.items():exports[name].setdefault(k,[]).append(a.copy())
        d=OUT/scene;d.mkdir(parents=True,exist_ok=True)
        if f in [131,180,192]:Image.fromarray(proxy).save(d/f'frame_{f:05d}-CPU-proxy.png')
        sources.append(dict(frame=f,final_rgb_sha256=ph(final),reference_rgb_sha256=ph(ref),reference_path=str(refdir/f'frame_{f:05d}.png'),
            current_edge_sha256=sha(str(pre)+'-edge.rg8'),previous_edge_sha256=sha(cap/A/f'frame_{f-1:05d}-edge.rg8')))
        records.append(rec)
        print(scene,f,'candidate',round(rec['current_percent'],3),'->',round(rec['union_percent'],3),'added',rec['added_pixels'],flush=True)
    summary={}
    for phase in ['moving','transition','still']:
        r=[r for r in records if r['phase']==phase];add=sum(x['added_pixels'] for x in r);old=sum(x['current_pixels'] for x in r)
        summary[phase]=dict(frames=[x['frame'] for x in r],current_percent=float(np.mean([x['current_percent'] for x in r])),
            union_percent=float(np.mean([x['union_percent'] for x in r])),additional_percent_of_current=100*add/old,
            added_pixel_frames=add,safe_improved_pixel_frames=sum(x['reference']['safe_added_improved_gt_1'] for x in r),
            safe_worsened_pixel_frames=sum(x['reference']['safe_added_worsened_gt_1'] for x in r),
            mean_reference_mae_change_all_proxy=float(np.mean([x['reference']['all_image_proxy_minus_base'] for x in r])),
            safe_added_error_change_per_image_pixel=float(np.mean([x['reference']['safe_added_error_change_per_image_pixel'] for x in r])))
    for name,data in exports.items():np.savez_compressed(OUT/f'{scene}-{name}.npz',frames=np.array(frames),roi=np.array(ROIS[scene][name]),**{k:np.stack(a) for k,a in data.items()})
    # Screen-fixed 48x48 patch with greatest summed reference-error increase in f130..135.
    integral=np.pad(gain,((1,0),(1,0))).cumsum(axis=0).cumsum(axis=1);patches=[]
    for y in range(0,1061-48,8):
        for x in range(0,1920-48,8):
            score=integral[y+48,x+48]-integral[y,x+48]-integral[y+48,x]+integral[y,x]
            patches.append((float(score),x,y,x+48,y+48))
    worst=max(patches);best=min(patches)
    dump(DOC/f'{scene}-results.json',dict(validation='PASS',classification='offline-one-frame-raw-edge-union-proxy',scene=scene,
        input_capture=str(cap),input_commit='756ff54',renderer_base='304f749',frames=frames,records=records,summary=summary,
        sources=sources,reference_increase_patch=dict(sum_error_change=worst[0],roi=worst[1:]),
        reference_decrease_patch=dict(sum_error_change=best[0],roi=best[1:]),
        limitations='CPU proxy, not GPU output or timing. Point-boundary uncertainty recorded. Spatial reference errors are not disocclusion truth.'))
    print('PASS',scene,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=ROIS,required=True);analyze(p.parse_args().scene)
