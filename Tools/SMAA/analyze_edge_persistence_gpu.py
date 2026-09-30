"""Validate GPU raw-edge persistence and measure quality against a spatial proxy.

No absolute temporal/ghosting ground truth is claimed. Original PNGs and ROI
sequences must also be opened by the reviewer before a quality conclusion.
"""
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np
from edge_persistence_trace_inputs import rgb,dds,edges,reconstruct,ph,sha,dump

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Edge-Persistence-GPU'
A='ABL-Spatial-FirstEdge-Stencil-PatternOff-R'
B='ABL-Spatial-PreviousRawEdge-Depth-PatternOff-R'
C='O-T2X-R'
D='DIAG-Spatial-CurrentEdge-Depth-PatternOff-R'
ROI={'bistro':{'chairs':(1190,530,1478,722),'window':(880,430,1168,622)},
     'minecraft':{'thin_edges':(780,460,1068,652)}}

def receipt(scene,phase):
    data=json.loads((ROOT/'tmp/edge-persistence-runs.json').read_text(encoding='utf-8-sig'))
    hits=[x for x in data if x['scene']==scene and x['phase']==phase]
    assert len(hits)==1,(scene,phase,len(hits))
    r=hits[0];assert sha(r['report']).lower()==r['report_sha256'].lower()
    rows=list(csv.reader(Path(r['report']).read_text(encoding='utf-8-sig').splitlines()))
    assert any('Aggregate: PASS' in ','.join(x) for x in rows)
    assert not any(v.strip()=='FAIL' for x in rows for v in x)
    path=Path(next(x[1].strip() for x in rows if x and x[0].strip()=='capture_root'))
    return r,rows,path

def quality(scene):
    r,rows,path=receipt(scene,'Capture')
    refs=ROOT/'Projects/CMAA2/AutoBench'/('20260917_140856' if scene=='bistro' else '20260917_141121')/'SS-Reference'
    expected=json.loads((ROOT/f'Docs/Stencil-Lifecycle-Refresh/{scene}-rgb-hashes.json').read_text())
    hashes={m:[] for m in [A,B,C,D,B+'-Repeat']};records=[];trace=[];previous={};previous_ref=None
    queries={(x[1].strip(),int(x[2])):(int(x[3]),int(x[4])) for x in rows if x and x[0].strip()=='trace'}
    for f in range(240):
        prefix=f'frame_{f:05d}'
        ims={m:rgb(path/m/(prefix+'.png')) for m in hashes}
        ref=rgb(refs/(prefix+'.png'))
        for m,a in ims.items():hashes[m].append(ph(a))
        for m in [A,C]:assert hashes[m][-1]==expected[m][f],('baseline_changed',scene,m,f)
        assert hashes[A][-1]==hashes[D][-1],('depth_handoff_changed',scene,f)
        assert hashes[B][-1]==hashes[B+'-Repeat'][-1],('repeat_changed',scene,f)
        regions={'full':(0,0,1920,1061),**ROI[scene]}
        for region,(x0,y0,x1,y1) in regions.items():
            rr=ref[y0:y1,x0:x1].astype(np.float32)
            for m in [A,B,C]:
                a=ims[m][y0:y1,x0:x1].astype(np.float32);err=a-rr
                mse=float(np.mean(err*err));mae=float(np.mean(np.abs(err)))
                luma=a@np.array([.2126,.7152,.0722],np.float32)
                edge=float((np.abs(np.diff(luma,axis=0)).mean()+np.abs(np.diff(luma,axis=1)).mean())/2)
                row={'frame':f,'region':region,'mode':m,'rgb_mae':mae,'psnr':float(10*np.log10(255**2/mse)) if mse else 100.,'edge_strength':edge}
                if f>0:
                    prev=previous[m][y0:y1,x0:x1].astype(np.float32)
                    pr=previous_ref[y0:y1,x0:x1].astype(np.float32)
                    row['frame_change']=float(np.mean(np.abs(a-prev)))
                    row['reference_delta_residual']=float(np.mean(np.abs((a-prev)-(rr-pr))))
                records.append(row)
        if (path/B/(prefix+'-edge.rg8')).exists():
            raw=edges(path/A/(prefix+'-edge.rg8'));cur=dds(path/A/(prefix+'-current.dds'))
            vel=dds(path/A/(prefix+'-velocity.dds'));e=np.any(raw>0,2)
            for m in [B,D]:
                for suffix in ['-edge.rg8','-current.dds','-velocity.dds','-raw.dds']:
                    assert sha(path/A/(prefix+suffix))==sha(path/m/(prefix+suffix)),('input_changed',scene,m,f,suffix)
                if f>0:assert sha(path/A/(prefix+'-previous.dds'))==sha(path/m/(prefix+'-previous.dds'))
            cov={m:dds(path/m/(prefix+'-coverage.dds'))>0 for m in [A,B,D]}
            assert np.array_equal(e,cov[A]) and np.array_equal(e,cov[D]),('current_depth_mask',scene,f)
            assert not np.any(e&~cov[B]),('raw_edge_lost',scene,f)
            assert np.array_equal(ims[B][e],ims[A][e]),('existing_selected_changed',scene,f)
            assert np.array_equal(ims[B][~cov[B]],cur[:,:,:3][~cov[B]]),('nonselected_changed',scene,f)
            for m in cov:
                inv,samples=queries[m,f]
                assert samples==int(cov[m].sum()),('query_mask',scene,m,f,samples,int(cov[m].sum()))
                assert samples<=inv<1920*1061,('execution_not_selective',scene,m,f,samples,inv)
            row={'frame':f,'current_count':int(e.sum()),'union_count':int(cov[B].sum()),
                 'added_count':int((cov[B]&~e).sum()),'queries':{m:queries[m,f] for m in cov}}
            if f==0:assert np.array_equal(e,cov[B]),'history reset did not discard previous edge'
            prevraw=path/A/(f'frame_{f-1:05d}-edge.rg8')
            if f>0 and prevraw.exists():
                rec=reconstruct(cur,dds(path/A/(prefix+'-previous.dds')),vel)
                q=rec['coords'];x=np.floor(q[:,:,0]).astype(int);y=np.floor(q[:,:,1]).astype(int)
                inside=(x>=0)&(x<1920)&(y>=0)&(y<1061)
                pe=np.any(edges(prevraw)>0,2)[y.clip(0,1060),x.clip(0,1919)]&inside
                expected_mask=e|pe;bad=expected_mask!=cov[B]
                row['mask_mismatch']=int(bad.sum());row['safe_mask_mismatch']=int((bad&rec['safe']).sum())
                assert row['safe_mask_mismatch']==0,('union_mask',scene,f,row)
                predicted=cur[:,:,:3].copy();predicted[cov[B]]=rec['full_resolve'][cov[B]]
                delta=np.abs(predicted.astype(np.int16)-ims[B].astype(np.int16))
                row['safe_native_max_error']=int(delta[rec['safe']].max())
                row['safe_native_error_gt1']=int(np.any(delta>1,2)[rec['safe']].sum())
                assert row['safe_native_error_gt1']==0,('native_math',scene,f,row)
            trace.append(row)
        previous={m:ims[m] for m in [A,B,C]};previous_ref=ref
        if f%40==0:print(scene,'validated frame',f,flush=True)
    summary={}
    for window,(lo,hi) in {'initial_still':(2,59),'moving':(60,179),'transition':(178,185),'late_still':(190,239)}.items():
        summary[window]={}
        for region in regions:
            summary[window][region]={}
            for m in [A,B,C]:
                rr=[x for x in records if lo<=x['frame']<=hi and x['mode']==m and x['region']==region]
                summary[window][region][m]={k:float(np.mean([x[k] for x in rr if k in x])) for k in ['rgb_mae','psnr','edge_strength','frame_change','reference_delta_residual']}
    DOC.mkdir(parents=True,exist_ok=True)
    dump(DOC/f'{scene}-quality.json',{'validation':'PASS','receipt':r,'capture':str(path),'reference':str(refs),'reference_type':'supersample spatial proxy; not temporal ground truth',
         'controls_hash_matches':480,'depth_control_hash_matches':240,'repeat_hash_matches':240,'summary':summary,'traces':trace,'records':records})
    dump(DOC/f'{scene}-rgb-hashes.json',hashes)
    print(scene,'QUALITY INPUT/CORRECTNESS PASS; visual inspection pending',flush=True)

def performance(scene,phase):
    r,rows,path=receipt(scene,phase);metrics={};repeats=6 if phase=='Benchmark' else 1;n=4800 if phase=='Benchmark' else 240
    for x in rows:
        if not x or x[0].strip()!='timing':continue
        _,mode,run,metric,samples,mean,median,p95,p99,stddev,low,*_=map(str.strip,x)
        assert int(samples)==n
        metrics.setdefault(mode,{}).setdefault(metric,[]).append({'run':int(run),'mean_ms':float(mean),'median_ms':float(median),'p95_ms':float(p95),'p99_ms':float(p99),'stddev_ms':float(stddev),'one_percent_fps':float(low)})
    assert set(metrics)=={A,B,C}
    result={}
    for m in metrics:
        assert set(metrics[m])=={'WholeFrame','SMAA','SR_CameraVelocity','SF_Spatial','SR_Resolve','WallFrame'}
        result[m]={}
        for metric,v in metrics[m].items():
            assert sorted(x['run'] for x in v)==list(range(repeats))
            result[m][metric]={'mean_ms':float(np.mean([x['mean_ms'] for x in v])),
                               'run_mean_stddev_ms':float(np.std([x['mean_ms'] for x in v])), 'runs':v}
    differences={}
    for control in [A,C]:
        differences[control]={}
        for metric in result[B]:
            d=[100*(t['mean_ms']/c['mean_ms']-1) for t,c in zip(sorted(result[B][metric]['runs'],key=lambda x:x['run']),sorted(result[control][metric]['runs'],key=lambda x:x['run']))]
            differences[control][metric]={'aggregate_percent':100*(result[B][metric]['mean_ms']/result[control][metric]['mean_ms']-1),'paired_percent':d}
    DOC.mkdir(parents=True,exist_ok=True);dump(DOC/f'{scene}-{phase.lower()}.json',{'validation':'PASS','receipt':r,'modes':result,'target_percent_vs_control':differences})
    print(scene,phase,'PASS',json.dumps({m:{k:v['mean_ms'] for k,v in mv.items()} for m,mv in result.items()}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('scene',choices=['bistro','minecraft']);p.add_argument('phase',choices=['Capture','Smoke','Benchmark']);a=p.parse_args()
    quality(a.scene) if a.phase=='Capture' else performance(a.scene,a.phase)
