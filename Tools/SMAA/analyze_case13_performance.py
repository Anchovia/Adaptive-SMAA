"""Validate completed same-process 4-mode benchmarks; report paired run deltas."""
import argparse,csv,json,math,statistics
from pathlib import Path
from edge_quality_inputs import sha

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Edge-History-Catmull-Rom-Reconstruction'
MODES=['ABL-ET2X-R-PreviousRawEdge-BilinearRGB','ABL-ET2X-R-PreviousRawEdge-ResolvedRGB','ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB','O-T2X-R']
METRICS=['SF_Spatial','SMAA','SR_CameraVelocity','SR_Resolve','WallFrame','WholeFrame']

def analyze(scene):
    receipt=next(r for r in reversed(json.loads((ROOT/'tmp/edge-catmull-rom-rgb-feedback-runs.json').read_text(encoding='utf-8-sig'))) if r['scene']==scene and r['phase']=='Benchmark')
    path=Path(receipt['report']);assert sha(path).upper()==receipt['report_sha256']
    text=path.read_text(encoding='utf-8-sig');assert 'Aggregate: PASS' in text and 'FAIL' not in text
    assert 'PNG/query/readback Off' in text and receipt['window']=='hidden'
    rows=[]
    for row in csv.reader(text.splitlines()):
        row=[x.strip() for x in row]
        if not row or row[0]!='timing':continue
        assert len(row)>=11
        rows.append(dict(mode=row[1],run=int(row[2]),metric=row[3],samples=int(row[4]),mean_ms=float(row[5]),median_ms=float(row[6]),p95_ms=float(row[7]),p99_ms=float(row[8]),stddev_ms=float(row[9]),slowest_one_percent_equivalent_fps=float(row[10])))
    assert len(rows)==144
    index={(r['mode'],r['metric'],r['run']):r for r in rows};assert len(index)==144
    for m in MODES:
        for metric in METRICS:
            for run in range(6):
                r=index[m,metric,run];assert r['samples']==4800 and r['mean_ms']>0 and r['median_ms']>0 and r['p99_ms']>=r['p95_ms']>=r['median_ms']
    summary=[]
    for metric in METRICS:
        for m in MODES:
            v=[index[m,metric,i]['mean_ms'] for i in range(6)]
            s=dict(mode=m,metric=metric,run_count=6,samples_per_run=4800,mean_ms=statistics.mean(v),run_mean_sample_stddev_ms=statistics.stdev(v),p95_ms_mean=statistics.mean(index[m,metric,i]['p95_ms'] for i in range(6)),p99_ms_mean=statistics.mean(index[m,metric,i]['p99_ms'] for i in range(6)))
            for name,denom in [('native4',MODES[3]),('case10',MODES[0]),('case11',MODES[1])]:
                dv=[100*(index[m,metric,i]['mean_ms']/index[denom,metric,i]['mean_ms']-1) for i in range(6)]
                mean=statistics.mean(dv);err=2.570581835*statistics.stdev(dv)/math.sqrt(6)
                s[name+'_paired_percent']=mean;s[name+'_paired_percent_95_interval']=[mean-err,mean+err];s[name+'_per_run_percent']=dv
            summary.append(s)
    raw=DOC/f'{scene}-performance-runs.csv'
    with raw.open('w',newline='',encoding='utf-8') as fp:
        w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=dict(validation='PASS',classification='paired clean benchmark; intermediate history reconstruction filter ablation',receipt=receipt,repeats=6,warmup_frames_per_mode=300,measurement_frames_per_mode_per_run=4800,mode_order='forward/reverse on alternating run',diagnostics='PNG/readback/query Off',stats='Mean of six run means; paired percent per matching run. Unadjusted Student t interval df5; one process per scene, no multi-session independence claim.',summary=summary,rows=rows)
    dest=DOC/f'{scene}-benchmark.json';dest.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(scene,'PASS')
    for s in summary:
        if s['metric'] in ['SMAA','SR_Resolve']:print(s['mode'],s['metric'],s['mean_ms'],s['native4_paired_percent'],s['case10_paired_percent'],s['case11_paired_percent'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);analyze(p.parse_args().scene)
