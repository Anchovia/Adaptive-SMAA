"""Candidate-only gate: strict image bridges, reused scores and paired timing.

Supersampling is a spatial proxy, not absolute temporal/ghosting ground truth.
"""
import argparse, csv, hashlib, json, math, re
from pathlib import Path
import numpy as np
from PIL import Image
from analyze_eight_case_performance import extract_metadata
from summarize_recovered_sharpen_segment_cgvqm import load_result

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'tmp/candidate-selection-gate'
BENCH=ROOT/'Projects/CMAA2/AutoBench'
IDS=['O-T2X-R','O-ET2X-R-DocCandidate-DocKernel','O-ET2X-R-SourceCandidate-DocKernel-Integrated']
KEYS=['O-1X','O-T2X-R','profile-0','profile-1']
HIST={'bistro':'20260827_013824','minecraft':'20260827_014324'}
WINDOWS={'central':(150,329),'transition':(410,439),'post_still':(440,479)}

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(name,data):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf8')
def rgb(p):
    with Image.open(p) as im:return np.asarray(im.convert('RGB'))
def paths(root,count):
    p=sorted(Path(root).rglob('*.png'));assert len(p)==count,(root,len(p),count)
    assert [int(re.search(r'_profile_(\d+)_frame_',x.name)[1]) for x in p]==list(range(count))
    return p
def equal(a,b,label):
    if not np.array_equal(a,b):
        np.savez_compressed(OUT/f'failed-{label}.npz',actual=a,expected=b)
        raise AssertionError(f'RGB mismatch: {label}; actual arrays preserved')
def report(run):
    p=list(Path(run['report']).glob('*_results.csv'));assert len(p)==1
    t=p[0].read_text(encoding='utf-8-sig');assert not re.search(r'\bFAIL\b',t)
    return t
def historical(scene,key,old):
    if key=='O-T2X-R':
        r=read(ROOT/'tmp/integrated-source-cgvqm'/scene/'standard/central/CGVQM-Results.json')
        return Path(r['test_sequence']['directory'])
    if key=='O-1X':return BENCH/HIST[scene]/'O_1X'
    return Path(old['quality'][scene]['runs'][f'{scene}-{key}']['report'])

def images(runs,full):
    old=read(ROOT/'tmp/source-comparison-analysis/comparison.json')
    records=[];quality={};cgvqm=[]
    count=480 if full else 12;mode='Quality' if full else 'Short'
    for scene in HIST:
        ref=paths(Path(old['quality'][scene]['reference'])/'SS_Reference',480)
        bykey={k:paths(runs[f'{scene}-{mode}-{k}']['report'],count) for k in KEYS}
        oldseq={k:paths(historical(scene,k,old),480) for k in KEYS}
        short={k:paths(runs[f'{scene}-Short-{k}']['report'],12) for k in KEYS} if full else {}
        hashes={k:{w:hashlib.sha256() for w in WINDOWS} for k in KEYS+['reference']}
        rows=[];prev=None;prevref=None
        for i in range(count):
            arrays={k:rgb(bykey[k][i]) for k in KEYS}
            for k,a in arrays.items():
                assert a.shape==(1017,1920,3)
                equal(a,rgb(oldseq[k][i]),f'{scene}-{mode}-{k}-{i}')
                if full and i<12:equal(a,rgb(short[k][i]),f'{scene}-prefix-{k}-{i}')
            if full:
                target=rgb(ref[i]);tf=target.astype(np.float32)
                for w,(lo,hi) in WINDOWS.items():
                    if lo<=i<=hi:
                        for k,a in {**arrays,'reference':target}.items():
                            hashes[k][w].update(i.to_bytes(8,'little'));hashes[k][w].update(a.tobytes())
                floating={k:a.astype(np.float32) for k,a in arrays.items()}
                for k,a in floating.items():
                    delta=a-tf;mse=float(np.mean(delta*delta))
                    rows.append(dict(frame=i,mode=k,mae=float(np.mean(abs(delta))),psnr=10*math.log10(255**2/max(mse,1e-20)),
                        temporal_delta_residual=None if prev is None else float(np.mean(abs((a-prev[k])-(tf-prevref))))))
                prev=floating;prevref=tf
            if i%120==0:print(f'{scene} {mode}: {i}/{count}',flush=True)
        for k in KEYS:records.append(dict(scene=scene,key=k,frames=count,historical=str(historical(scene,k,old)),rgb_mismatch=0))
        if full:
            with (OUT/f'{scene}-per-frame.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            quality[scene]={w:{k:{metric:float(np.mean([r[metric] for r in rows if r['mode']==k and lo<=r['frame']<=hi]))
                for metric in ('mae','psnr','temporal_delta_residual')} for k in KEYS} for w,(lo,hi) in WINDOWS.items()}
            for w in ('central','transition'):
                for k in KEYS[1:]:
                    result=(ROOT/'tmp/integrated-source-cgvqm'/scene/'standard'/w/'CGVQM-Results.json') if k=='O-T2X-R' else ROOT/'tmp/source-comparison-cgvqm'/scene/k/w/'CGVQM-Results.json'
                    d=load_result(result,hashes['reference'][w].hexdigest())
                    assert d['test_sequence']['pixel_sha256']==hashes[k][w].hexdigest(),(scene,k,w)
                    lo,hi=WINDOWS[w]
                    for side in ('test','reference'):
                        s=d[side+'_sequence'];assert (s['first_index'],s['last_index'],s['frame_count'],s['width'],s['height'])==(lo,hi,hi-lo+1,1920,1017)
                    expected=k if k=='O-T2X-R' else IDS[2 if k=='profile-1' else 1].removesuffix('-Integrated')
                    assert d['provenance']==dict(scene=scene,camera_profile='flythrough-wide-yaw-360',test_mode=expected,reference_id='SS-Reference')
                    cgvqm.append(dict(scene=scene,key=k,window=w,reused_pixel_exact_score=True,**d))
    return dict(status='PASS',bridges=records,short_full_prefix_frames=96 if full else 0,quality=quality,cgvqm=cgvqm)

def performance(runs,smoke):
    out={};mode='Smoke' if smoke else 'Benchmark';count=180 if smoke else 4800;repeats=1 if smoke else 3
    for scene in HIST:
        run=runs[f'{scene}-{mode}'];t=report(run);md=extract_metadata(t.splitlines())
        for k,v in dict(api='DirectX11',resolution='1920 x 1017',vsync='OFF',warmup_frames=60 if smoke else 300,
            measurement_frames=count,repeats=repeats,start_time_seconds=0.0,benchmark_validation_pass=True,candidate_readback_disabled=not smoke).items():
            assert md.get(k)==v,(k,md)
        assert run['window']=='visible' and 'Candidate-selection paired gate' in t
        data={k:{} for k in IDS};counters={};rates={}
        for row in csv.reader(t.splitlines()):
            row=[x.strip() for x in row]
            while row and not row[-1]:row.pop()
            if len(row)>=12 and row[0] in IDS and row[2] in ('GPU timestamp','CPU wall interval'):
                assert int(row[3])==count*repeats and int(row[10])==repeats
                values={k:float(row[j]) for j,k in enumerate(['mean_ms','median_ms','frame_stddev_ms','p95_ms','p99_ms','max_ms'],4)}
                values['run_mean_stddev_ms']=float(row[11]);assert all(math.isfinite(v) and v>=0 for v in values.values())
                data[row[0]][row[1]]=values
            elif len(row)>=6 and row[0] in IDS:
                try:counters[row[0]]=dict(samples=int(row[1]),base=float(row[2]),candidate=float(row[3]),process=float(row[4]),ratio=float(row[5]))
                except ValueError:pass
            elif len(row)>=5 and row[0] in IDS:
                try:rates[row[0]]=dict(zip(['wall_average_fps','wall_1pct_low_fps','gpu_equivalent_average_fps','gpu_equivalent_1pct_low_fps'],map(float,row[1:5])))
                except ValueError:pass
        common={'ApplicationFrameWall','WholeFrame','SMAA','SMAAGenerateCameraVelocity'}
        for k in IDS:
            assert common<=set(data[k]),(k,list(data[k]))
            assert len(rates[k])==4
        for k in IDS[1:]:
            assert 'TSCMAAClearIntegratedCandidateBuffers' in data[k]
            assert 'TSCMAAExtractCandidates' not in data[k] and 'TSCMAAPrepareCandidates' not in data[k]
            if smoke:assert counters[k]['candidate']==counters[k]['process'] and counters[k]['candidate']>0
        assert set(data[IDS[1]])==set(data[IDS[2]])
        differences=[]
        for a,b in [(0,1),(0,2),(1,2)]:
            for metric in sorted(set(data[IDS[a]])&set(data[IDS[b]])):
                before=data[IDS[a]][metric]['mean_ms'];after=data[IDS[b]][metric]['mean_ms']
                differences.append(dict(baseline=IDS[a],test=IDS[b],metric=metric,delta_ms=after-before,percent=100*(after/before-1)))
        out[scene]=dict(run=run,metadata=md,metrics=data,frame_rates=rates,counters=counters,differences=differences)
    return dict(status='PASS',classification='engineering smoke' if smoke else 'formal paired performance',scenes=out)

def masks(runs):
    old={r['label']:r for r in read(ROOT/'tmp/source-comparison-runs.json')};result={}
    for scene in HIST:
        seq=[paths(runs[f'{scene}-Masks-profile-{i}']['report'],120) for i in (0,1)]
        previous=[paths(old[f'{scene}-mask-{i}']['report'],120) for i in (0,1)]
        finals=[paths(runs[f'{scene}-Quality-profile-{i}']['report'],480) for i in (0,1)]
        spatial=paths(runs[f'{scene}-Quality-O-1X']['report'],480);rows=[]
        for n in range(120):
            raw=[rgb(s[n]) for s in seq];selected=[];base=rgb(spatial[n])
            for i,a in enumerate(raw):
                equal(a,rgb(previous[i][n]),f'{scene}-mask-{i}-{n}')
                assert np.all((a==0)|(a==255)) and np.array_equal(a[...,0],a[...,1]) and np.array_equal(a[...,0],a[...,2])
                mask=a[...,0]>0;selected.append(mask)
                final=rgb(finals[i][n]);equal(final[~mask],base[~mask],f'{scene}-noncandidate-{i}-{n}')
            a,b=selected;union=int(np.count_nonzero(a|b));inter=int(np.count_nonzero(a&b))
            rows.append(dict(frame=n,document=int(a.sum()),source=int(b.sum()),added=int((b&~a).sum()),removed=int((a&~b).sum()),jaccard=inter/max(1,union)))
        result[scene]=dict(frames=120,mask_mismatch=0,noncandidate_mismatch=0,
            means={k:float(np.mean([r[k] for r in rows])) for k in rows[0] if k!='frame'},rows=rows)
    return dict(status='PASS',scenes=result)

def regressions(runs):
    current=sorted(Path(runs['default-eight']['report']).rglob('*.png'))
    previous=sorted((BENCH/'20260914_191019').rglob('*.png'));assert len(current)==len(previous)==96
    for n,(a,b) in enumerate(zip(current,previous)):equal(rgb(a),rgb(b),f'eight-{n}')
    t=report(runs['source-candidate-document-feedback']);assert 'PASS' in t
    return dict(status='PASS',default_eight_frames=96,rgb_mismatch=0,feedback_report=t)

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['short','quality','smoke','performance','masks','regressions']);a=p.parse_args()
    runs0=read(OUT/'runs.json');runs={r['label']:r for r in runs0};assert len(runs)==len(runs0)
    assert len({json.dumps(r['hashes'],sort_keys=True) for r in runs0})==1,'Executable/shaders changed across runs'
    for r in runs0:report(r)
    if a.mode in ('short','quality'):result=images(runs,a.mode=='quality')
    elif a.mode=='masks':result=masks(runs)
    elif a.mode=='regressions':result=regressions(runs)
    else:result=performance(runs,a.mode=='smoke')
    save(a.mode+'.json',result);print(f'PASS: {a.mode}',flush=True)
if __name__=='__main__':main()
