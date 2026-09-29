"""Paired native-versus-selective timing with all spatial passes preserved."""
import argparse,csv,json,math,statistics as st
from analyze_spatial_first_edge import D,FULL,SEL,receipt
METRICS=['WholeFrame','SMAA','SF_CameraVelocity','SF_Spatial','SF_Resolve','WallFrame']
def analyze(scene,phase):
    rc,path,text=receipt(scene,phase);assert '1920 x 1061' in text and 'NVIDIA GeForce RTX 3060 Ti' in text
    repeats,n=(1,240) if phase=='Smoke' else (4,4800);rows=[];rates=[]
    for row in csv.reader(text.splitlines()):
        r=[x.strip() for x in row]
        if r and r[0]=='timing':
            mode,repeat,metric,count=r[1],int(r[2]),r[3],int(r[4]);v=list(map(float,r[5:10]))
            assert count==n and len(v)==5 and all(math.isfinite(x) and x>=0 for x in v)
            assert v[0]>0 and v[2]>=v[1]>=v[3]
            rows.append(dict(mode=mode,repeat=repeat,metric=metric,samples=count,mean_ms=v[0],p95_ms=v[1],p99_ms=v[2],median_ms=v[3],std_ms=v[4]))
        elif r and r[0]=='rate':
            assert int(r[5])==n
            rates.append(dict(mode=r[1],repeat=int(r[2]),average_fps=float(r[3]),one_percent_low_fps=float(r[4])))
    expected=[(m,r,k) for r in range(repeats) for m in ([FULL,SEL] if r%2==0 else [SEL,FULL]) for k in sorted(METRICS)]
    assert [(r['mode'],r['repeat'],r['metric']) for r in rows]==expected
    assert [(r['mode'],r['repeat']) for r in rates]==[(m,r) for r in range(repeats) for m in ([FULL,SEL] if r%2==0 else [SEL,FULL])]
    for rate in rates:
        wall=next(r for r in rows if (r['mode'],r['repeat'],r['metric'])==(rate['mode'],rate['repeat'],'WallFrame'))
        assert abs(rate['average_fps']-1000/wall['mean_ms'])<1e-3
        assert 0<rate['one_percent_low_fps']<=rate['average_fps']
    summary={}
    for mode in [FULL,SEL]:
        summary[mode]={}
        for metric in METRICS:
            rr=[r for r in rows if r['mode']==mode and r['metric']==metric];means=[r['mean_ms'] for r in rr]
            summary[mode][metric]=dict(mean_ms=st.mean(means),run_means_ms=means,run_mean_std_ms=st.stdev(means) if repeats>1 else None,
                mean_run_median_ms=st.mean(r['median_ms'] for r in rr),mean_run_p95_ms=st.mean(r['p95_ms'] for r in rr),mean_run_p99_ms=st.mean(r['p99_ms'] for r in rr))
    changes={}
    for metric in METRICS:
        s,f=summary[SEL][metric],summary[FULL][metric];ds=[a-b for a,b in zip(s['run_means_ms'],f['run_means_ms'])]
        ps=[(a/b-1)*100 for a,b in zip(s['run_means_ms'],f['run_means_ms'])]
        changes[metric]=dict(delta_ms=s['mean_ms']-f['mean_ms'],percent=(s['mean_ms']/f['mean_ms']-1)*100,paired_deltas_ms=ds,paired_percent=ps,paired_delta_std_ms=st.stdev(ds) if repeats>1 else None)
    out=dict(validation='PASS',scene=scene,phase=phase,receipt=rc,repeats=repeats,frames_per_repeat=n,metrics=summary,selective_minus_native=changes,rates=rates,
        note='Hidden-window engineering; same native spatial, jitter, history and camera motion. No image/mask readback. Timestamp query instrumentation remains. Wall FPS includes host/window scheduling. No matched-quality improvement claim.')
    (D/f'{scene}-{phase.lower()}-performance.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    for suffix,rr in [('timings',rows),('rates',rates)]:
        with (D/f'{scene}-{phase.lower()}-{suffix}.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=rr[0]);w.writeheader();w.writerows(rr)
    print(json.dumps(dict(validation='PASS',scene=scene,phase=phase,means={m:{k:v['mean_ms'] for k,v in d.items()} for m,d in summary.items()},changes=changes),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);p.add_argument('--phase',choices=['Smoke','Benchmark'],required=True);a=p.parse_args();analyze(a.scene,a.phase)
