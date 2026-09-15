"""Three independent process pairs; no per-frame pseudoreplication."""
import csv, hashlib, json, math, statistics
from pathlib import Path
from analyze_integrated_source_comparison import IDS
from analyze_eight_case_performance import extract_metadata
from analyze_recovered_source_comparison import report_text

ROOT=Path(__file__).resolve().parents[2]

def main():
    runs=json.loads((ROOT/'tmp/recovered-clipping/runs.json').read_text(encoding='utf-8-sig'))
    runs=[r for r in runs if r['mode']=='Benchmark'];assert len(runs)==12
    assert len({r['exe_sha256'] for r in runs})==1 and len({r['candidate_sha256'] for r in runs})==1
    assert len({r['utility_sha256'] for r in runs})==2
    data={};details=[]
    for r in runs:
        v=0 if r['variant']=='SourceClip' else 1
        assert r['variant'] in ('SourceClip','SignedChroma-YCoCgClamp')
        assert r['signed_chroma']==r['ycocg_clamp']==v
        assert hashlib.sha256(r['utility_source'].encode()).hexdigest()==r['utility_sha256'].lower()
        key=(r['scene'],r['pair'],v);assert key not in data
        text=report_text(r['report']);meta=extract_metadata(text.splitlines())
        for name,value in dict(api='DirectX11',resolution='1920 x 1017',vsync='OFF',warmup_frames=300,
            measurement_frames=4800,repeats=1,start_time_seconds=0.0,candidate_readback_disabled=True,
            benchmark_validation_pass=True,scene=r['scene']).items():assert meta.get(name)==value,(name,meta)
        assert r['window']=='visible';modes={name:{} for name in IDS}
        for row in csv.reader(text.splitlines()):
            row=[x.strip() for x in row]
            if len(row)>=12 and row[0] in modes and row[2] in ('GPU timestamp','CPU wall interval'):
                assert int(row[3])==4800 and int(row[10])==1
                values={k:float(row[i]) for k,i in [('mean_ms',4),('p95_ms',7),('p99_ms',8)]}
                assert all(math.isfinite(v) and v>=0 for v in values.values())
                modes[row[0]][row[1]]=values
        for name in IDS:assert {'SMAA','WholeFrame','ApplicationFrameWall'}<=modes[name].keys()
        assert 'TSCMAAExtractCandidates' not in modes[IDS[2]] and 'TSCMAAExtractCandidates' in modes[IDS[1]]
        data[key]=modes;details.append(dict(run={k:v for k,v in r.items() if k!='utility_source'},metadata=meta,modes=modes))
    rows=[];ratios=[]
    for scene in ('bistro','minecraft'):
        for mode in IDS:
            for metric in data[(scene,1,0)][mode]:
                before=[data[(scene,p,0)][mode][metric]['mean_ms'] for p in (1,2,3)]
                after=[data[(scene,p,1)][mode][metric]['mean_ms'] for p in (1,2,3)]
                delta=[a-b for a,b in zip(after,before)];d=statistics.mean(delta)
                margin=4.30265273*statistics.stdev(delta)/math.sqrt(3)
                rows.append(dict(scene=scene,mode=mode,metric=metric,before_ms=statistics.mean(before),after_ms=statistics.mean(after),
                    before_runs_ms=before,after_runs_ms=after,pair_percent=[100*(a/b-1) for a,b in zip(after,before)],delta_ms_ci95=[d-margin,d+margin]))
        for v,name in enumerate(('SourceClip','SignedChroma-YCoCgClamp')):
            ratios.append(dict(scene=scene,variant=name,source_over_standard_smaa_percent=[100*(data[(scene,p,v)][IDS[2]]['SMAA']['mean_ms']/data[(scene,p,v)][IDS[0]]['SMAA']['mean_ms']-1) for p in (1,2,3)]))
    result=dict(status='PASS',runs=details,metrics=rows,source_vs_standard=ratios,
        scope='Both source separate and integrated use the clipping switch; Standard is unchanged. Three independent process pairs, descriptive unadjusted t(2) intervals.')
    out=ROOT/'tmp/recovered-clipping/analysis/performance.json';out.write_text(json.dumps(result,indent=2))
    print(json.dumps([r for r in rows if r['metric'] in ('SMAA','WholeFrame')],indent=2))
if __name__=='__main__':main()
