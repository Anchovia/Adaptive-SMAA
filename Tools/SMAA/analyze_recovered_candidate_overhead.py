"""Validate unchanged images and independent paired diagnostic-overhead timing."""
import argparse,csv,hashlib,json,math,re,statistics
from pathlib import Path
from analyze_integrated_source_comparison import IDS
from analyze_eight_case_performance import extract_metadata

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def text(run):
    paths=list(Path(run['report']).glob('*_results.csv'));assert len(paths)==1
    t=paths[0].read_text(encoding='utf-8-sig');assert 'FAIL' not in t
    return t
def hashes(root):
    paths=sorted(Path(root).rglob('*.png'));assert paths
    return [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]

def correctness(runs,extra):
    by={r['label']:r for r in runs};ex={r['label']:r for r in extra}
    checks=[]
    for r in runs+extra:
        if '-pair-' not in r['label']:text(r)
    for scene in ('bistro','minecraft'):
        reference=hashes(by[f'{scene}-Quality-source-0']['report']);assert len(reference)==480
        # BenchItemRecordSMAACameraMotion explicitly disables counter readback.
        for label,record in [('integrated-readback-off',by[f'{scene}-Quality-source-1'])]:
            actual=hashes(record['report']);assert actual==reference,(scene,label)
            checks.append(dict(scene=scene,comparison=label,frames=480,mismatch=0))
        historical=Path(by[f'{scene}-Quality-source-0']['report']).parent/({'bistro':'20260914_142836','minecraft':'20260914_143331'}[scene])
        assert hashes(historical)==reference
        checks.append(dict(scene=scene,comparison='previous-source',frames=480,mismatch=0))
        prior_mask=historical.parent/({'bistro':'20260914_191234','minecraft':'20260914_191249'}[scene])
        mask=hashes(ex[f'{scene}-readback-off-debug-2']['report'])
        assert len(mask)==12 and mask==hashes(prior_mask)
        checks.append(dict(scene=scene,comparison='readback-off-debug-mask',frames=12,mismatch=0))
    regression=by['default-eight-regression']
    before=Path(regression['report']).parent/'20260914_191019'
    assert len(hashes(regression['report']))==96
    assert hashes(before)==hashes(regression['report'])
    assert 'Aggregate: PASS' in text(by['snapshot'])
    return dict(status='PASS',image_checks=checks,default_eight_frames=96,default_eight_mismatch=0,
                snapshot=by['snapshot'],runs=runs+extra)

def performance(runs):
    runs=[r for r in runs if re.fullmatch(r'(bistro|minecraft)-pair-[123]-optional-[01]',r['label'])];assert len(runs)==12
    assert len({r['exe_sha256'] for r in runs})==1
    assert len({r['candidate_sha256'] for r in runs})==1
    assert len({r['shader_sha256'] for r in runs})==2
    for v in (0,1):assert len({r['shader_sha256'] for r in runs if r['label'].endswith(f'optional-{v}')})==1
    data={};environments=[];run_metrics=[]
    for run in runs:
        match=re.fullmatch(r'(bistro|minecraft)-pair-([123])-optional-([01])',run['label']);assert match
        scene,pair,variant=match.groups();key=(scene,int(pair),int(variant));assert key not in data
        t=text(run);metadata=extract_metadata(t.splitlines())
        for name,val in dict(api='DirectX11',resolution='1920 x 1017',vsync='OFF',warmup_frames=300,
            measurement_frames=4800,repeats=1,start_time_seconds=0.0,candidate_readback_disabled=True,
            benchmark_validation_pass=True).items():assert metadata.get(name)==val,(name,metadata)
        assert run['window']=='visible'
        assert metadata['scene']==scene
        environments.append(metadata['system_info'])
        modes={m:{} for m in IDS}
        for row in csv.reader(t.splitlines()):
            row=[x.strip() for x in row]
            if len(row)>=12 and row[0] in modes and row[2] in ('GPU timestamp','CPU wall interval'):
                assert int(row[3])==4800 and int(row[10])==1
                vals={k:float(row[i]) for k,i in [('mean_ms',4),('median_ms',5),('stddev_ms',6),('p95_ms',7),('p99_ms',8)]}
                assert all(math.isfinite(v) and v>=0 for v in vals.values())
                modes[row[0]][row[1]]=vals
        for mode in IDS:assert {'SMAA','WholeFrame','ApplicationFrameWall'}<=modes[mode].keys()
        assert 'TSCMAAExtractCandidates' not in modes[IDS[2]]
        assert 'TSCMAAExtractCandidates' in modes[IDS[1]]
        data[key]=modes
        run_metrics.append(dict(label=run['label'],metadata=metadata,modes=modes))
    assert len(set(environments))==1
    rows=[]
    for scene in ('bistro','minecraft'):
        for mode in IDS:
            metrics=data[(scene,1,0)][mode].keys()
            for pair in (1,2,3):
                for v in (0,1):assert data[(scene,pair,v)][mode].keys()==metrics
            for metric in metrics:
                before=[data[(scene,p,0)][mode][metric]['mean_ms'] for p in (1,2,3)]
                after=[data[(scene,p,1)][mode][metric]['mean_ms'] for p in (1,2,3)]
                delta=[b-a for a,b in zip(before,after)];pct=[100*(b/a-1) for a,b in zip(before,after)]
                mean=statistics.mean(delta);h=4.30265273*statistics.stdev(delta)/math.sqrt(3)
                rows.append(dict(scene=scene,mode=mode,metric=metric,before_ms=statistics.mean(before),after_ms=statistics.mean(after),
                    before_runs_ms=before,after_runs_ms=after,pair_percent=pct,mean_pair_percent=statistics.mean(pct),
                    delta_ms_ci95=[mean-h,mean+h]))
    normalized=[]
    for scene in ('bistro','minecraft'):
        for control in IDS[:2]:
            ratios=[]
            for pair in (1,2,3):
                before=data[(scene,pair,0)];after=data[(scene,pair,1)]
                rb=before[IDS[2]]['SMAA']['mean_ms']/before[control]['SMAA']['mean_ms']
                ra=after[IDS[2]]['SMAA']['mean_ms']/after[control]['SMAA']['mean_ms']
                ratios.append(100*(ra/rb-1))
            normalized.append(dict(scene=scene,control=control,pair_ratio_percent=ratios,mean_percent=statistics.mean(ratios)))
    return dict(status='PASS',runs=runs,run_metrics=run_metrics,metrics=rows,control_normalized_diagnostic=normalized,
        notes='Three independent process pairs; descriptive unadjusted t(2) intervals. No per-frame pseudoreplication. Control ratios are auxiliary diagnostics, not a replacement for raw timing.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--performance',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parents[2];out=root/'tmp/recovered-candidate-reuse'
    runs=read(out/'runs.json');extra=read(out/'overhead-runs.json')
    result=performance(extra) if a.performance else correctness(runs,extra)
    target=out/('performance.json' if a.performance else 'correctness.json')
    target.write_text(json.dumps(result,indent=2),encoding='utf8')
    if a.performance:
        print(json.dumps([r for r in result['metrics'] if r['metric'] in ('SMAA','WholeFrame')],indent=2))
    else:print(json.dumps(result['image_checks']))

if __name__=='__main__':main()
