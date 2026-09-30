"""Hash-bridge prior CGVQM and compare identical-pose spatial-reference residuals."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from analyze_coverage_pattern_control import ROOT,DOC,A,B,C,rgb,dump

MODES=[A,B,C]
OLD={A:'Spatial-Edge-Stencil-Off-R',B:'Spatial-Full-Off-R',C:'O-T2X-R'}
WINDOWS={'moving':(60,180),'transition':(160,220)}
ROIS={'bistro':{'chairs':[1190,530,1478,722],'window':[880,430,1168,622]},'minecraft':{'thin_edges':[780,460,1068,652]}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',choices=['bistro','minecraft'],required=True);s=p.parse_args().scene
    valid=json.loads((DOC/f'{s}-capture-validation.json').read_text(encoding='utf-8'));assert valid['validation']=='PASS'
    cap=Path(valid['capture']);prior=json.loads((ROOT/f'Docs/Stencil-Lifecycle-Refresh/{s}-prior.json').read_text(encoding='utf-8'))
    records=prior['quality']['results'];ref=Path(records['moving']['records'][OLD[A]]['reference_sequence']['directory'])
    hashes={w:{m:hashlib.sha256() for m in MODES+['reference']} for w in WINDOWS}
    previous={};rows=[]
    regions={'full':None,**{name:np.s_[box[1]:box[3],box[0]:box[2]] for name,box in ROIS[s].items()}}
    for f in range(59,220):
        ri=rgb(ref/f'frame_{f:05d}.png');ims={m:rgb(cap/m/f'frame_{f:05d}.png') for m in MODES}
        for window,(lo,hi) in WINDOWS.items():
            if lo<=f<hi:
                for m,image in {**ims,'reference':ri}.items():hashes[window][m].update(f.to_bytes(8,'little'));hashes[window][m].update(image.tobytes())
        for m,image in ims.items():
            # Identical-pose spatial proxy: this is temporal change of reference
            # error, not a pure flicker/ghosting metric or optical-flow alignment.
            diff=image.astype(np.float32)-ri.astype(np.float32)
            err=diff[:,:,0]*.2126+diff[:,:,1]*.7152+diff[:,:,2]*.0722
            if f>=60:
                delta=np.abs(err-previous[m]);stats={}
                for name,roi in regions.items():
                    d=diff if roi is None else diff[roi];v=delta if roi is None else delta[roi]
                    stats[name]=dict(rgb_mae=float(np.abs(d).mean()),reference_error_temporal_delta=float(v.mean()))
                rows.append(dict(frame=f,mode=m,metrics=stats))
            previous[m]=err
        if f%60==0:print(s,'reference comparison frame',f,flush=True)
    reused={}
    for window,(lo,hi) in WINDOWS.items():
        reused[window]={}
        for m in MODES:
            old=records[window]['records'][OLD[m]]
            assert old['official_cgvqm']['commit']=='8302ff45b4ff5a691682baf23f7c007d6b591e98'
            assert old['runtime']['device']=='cuda'
            assert old['configuration']==dict(fps=60,patch_scale=4,patch_pool='mean',models=['2'],reference_index_offset=0)
            for key,name in [('test',m),('reference','reference')]:
                seq=old[key+'_sequence'];rt=old[key+'_round_trip']
                assert (seq['first_index'],seq['last_index'],seq['frame_count'],seq['width'],seq['height'])==(lo,hi-1,hi-lo,1920,1061)
                assert hashes[window][name].hexdigest()==seq['pixel_sha256'],(s,window,m,key,'prior score cannot be reused')
                assert rt['decoded_frames']==hi-lo and rt['mismatched_values']==rt['max_absolute_difference']==0
            score=old['results']['CGVQM-2']['score_higher_is_better'];assert math.isfinite(score)
            reused[window][m]=dict(score=score,test_pixel_sha256=hashes[window][m].hexdigest(),reference_pixel_sha256=hashes[window]['reference'].hexdigest(),
                prior_record_id=OLD[m],quality_source_commit=prior['quality_source_commit'],quality_source_path=prior['quality_source_path'])
    means={}
    for window,(lo,hi) in {**WINDOWS,'late_still':(190,220)}.items():
        means[window]={}
        for m in MODES:
            rr=[r for r in rows if r['mode']==m and lo<=r['frame']<hi]
            means[window][m]={region:{metric:float(np.mean([r['metrics'][region][metric] for r in rr])) for metric in rr[0]['metrics'][region]} for region in regions}
    result=dict(validation='PASS',scene=s,capture=str(cap),reference=str(ref),cgvqm_model_rerun=False,cgvqm_reused_by_complete_window_pixel_hash=reused,
        reference_metrics_frame_means=means,frame_metrics=rows,
        limitations='Reference is same-pose supersample spatial proxy, not temporal ground truth. Temporal residual mixes rendering/reference error changes with motion effects; not a pure shimmer/ghosting metric. CGVQM reused only after exact test AND reference window RGB stream hashes match; no model rerun, no timing claim.')
    dump(DOC/f'{s}-quality.json',result)
    print('PASS',s,'all six prior CGVQM scores exactly bridged; fresh reference residuals',flush=True)
    print(json.dumps(dict(scores={w:{m:x['score'] for m,x in r.items()} for w,r in reused.items()},moving=means['moving'])),flush=True)

if __name__=='__main__':main()
