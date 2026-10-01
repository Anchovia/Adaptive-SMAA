"""Validate exact outputs, spatial/temporal coverage and paired timing separately."""
import argparse, csv, hashlib, json, statistics
from pathlib import Path
import numpy as np
from PIL import Image
from analyze_first_edge_stencil import coverage, edge

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Edge-Persistence-Spatial-Cost'
A='A-CurrentEdge-Stencil'; E='E-PreviousRawEdge-FirstStencil'
F='F-EagerPreviousFetch'; U='U-DepthMask-UnionWeights'; G='G-DepthMask-CurrentWeights'; O='O-T2X-R'
MODES=[A,E,F,U,G,O]

def rgb_hash(p):
    with Image.open(p) as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(p,im.mode,im.size)
        return hashlib.sha256(im.tobytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scene',required=True,choices=['bistro','minecraft'])
    ap.add_argument('--phase',required=True,choices=['Test','Capture','Smoke','Benchmark','ProfileSmoke','ProfileBenchmark'])
    a=ap.parse_args()
    records=json.loads((ROOT/'tmp/edge-persistence-spatial-cost-runs.json').read_text(encoding='utf-8-sig'))
    rec=next(r for r in reversed(records) if r['scene']==a.scene and r['phase']==a.phase)
    report=Path(rec['report']);text=report.read_text();assert 'Aggregate: PASS' in text and 'FAIL' not in text
    rows=[[x.strip() for x in row if x.strip()] for row in csv.reader(text.splitlines()) if row]
    result=dict(receipt=rec,classification='same-output execution experiment',shader_stencil_reference_supported=next((r[1] for r in rows if r[0]=='shader_stencil_reference_supported'),None))
    if a.phase in ['Capture','Test']:
        base=Path(next(r[1] for r in rows if r[0]=='capture_root'));n=6 if a.phase=='Test' else 240
        hashes={}
        for m in MODES:
            files=sorted((base/m).glob('frame_[0-9][0-9][0-9][0-9][0-9].png'))
            assert len(files)==n,(m,len(files));hashes[m]=[rgb_hash(p) for p in files]
        checks={m+' vs E':sum(x!=y for x,y in zip(hashes[m],hashes[E])) for m in [F,U,G]}
        old=json.loads((ROOT/'Docs/Edge-Persistence-Cost-Audit'/f'{a.scene}-capture.json').read_text())
        for m in [A,E,O]:checks[m+' vs preserved']=sum(x!=y for x,y in zip(hashes[m],old['output_hashes'][m][:n]))
        assert not any(checks.values()),checks
        traces={m:{} for m in MODES[:-1]}
        for row in rows:
            if row[0]=='trace':
                assert row[5]=='PASS';traces[row[1]][int(row[2])]=row
        trace_checks=[]
        assert len(traces[E])==(6 if a.phase=='Test' else 43)
        for i,er in traces[E].items():
            stem=f'frame_{i:05d}';em=coverage(base/E/(stem+'-coverage.dds'))
            raw=edge(base/E/(stem+'-edge.rg8'));raw_n=int(raw.sum());union_n=int(em.sum())
            assert np.all(em[raw]);entry=dict(frame=i,current_samples=raw_n,union_samples=union_n,weights={})
            for m in MODES[:-1]:
                row=traces[m][i];mask=coverage(base/m/(stem+'-coverage.dds'))
                expected=raw if m==A else em
                assert np.array_equal(mask,expected),(m,i,'temporal coverage')
                assert int(row[4])==int(expected.sum()) and int(row[3])>=int(row[4]),(m,i,'temporal invocations')
                expected_weights=raw_n if m in [A,G] else union_n
                assert int(row[6])==expected_weights and int(row[7])>=expected_weights,(m,i,'weight gate',row,expected_weights)
                for suffix in ['-edge.rg8','-current.dds']:
                    assert (base/m/(stem+suffix)).read_bytes()==(base/E/(stem+suffix)).read_bytes(),(m,i,suffix)
                with Image.open(base/m/(stem+'.png')) as im:final=np.asarray(im).copy()
                with Image.open(base/m/(stem+'-current.png')) as im:current=np.asarray(im).copy()
                assert not np.any(final[~expected]!=current[~expected]),(m,i,'nonselected changed')
                entry['weights'][m]=dict(samples=int(row[6]),ps_invocations=int(row[7]))
            trace_checks.append(entry)
        mode_checks=[r for r in rows if r[0]=='mode_check'];assert len(mode_checks)==n*len(MODES)
        result.update(capture_root=str(base),frames_per_mode=n,mismatched_frames=checks,output_hashes=hashes,trace_checks=trace_checks)
        print('PASS exact RGB/raw/current/coverage and actual pass2 counts',a.scene,a.phase)
    else:
        profile=a.phase.startswith('Profile');n=240 if a.phase.endswith('Smoke') else 4800;reps=1 if n==240 else 3
        data={};seen=set()
        for r in rows:
            if r[0]!='timing':continue
            _,m,run,k,count,mean,*_=r
            assert m in MODES and int(count)==n and int(run) in range(reps)
            key=(m,k,int(run));assert key not in seen;seen.add(key)
            data.setdefault(m,{}).setdefault(k,{})[int(run)]=float(mean)
        # Initial pre-candidate profiling is preserved as a separate three-mode run.
        expected=MODES if F in data else [A,E,O]
        assert set(data)==set(expected)
        assert all(len(v)==reps for ms in data.values() for v in ms.values())
        assert all(len(ms)==(10 if profile else 6) for ms in data.values())
        means={m:{k:statistics.mean(v.values()) for k,v in ms.items()} for m,ms in data.items()}
        comparisons={}
        for base in [A,E,O]+([U] if U in data else []):
            comparisons[base]={}
            for m in data:
                comparisons[base][m]={}
                for k in data[m]:
                    delta=[data[m][k][i]-data[base][k][i] for i in range(reps)]
                    comparisons[base][m][k]=dict(delta_ms=means[m][k]-means[base][k],percent=100*(means[m][k]/means[base][k]-1),paired_delta_ms=delta,paired_percent=[100*(data[m][k][i]/data[base][k][i]-1) for i in range(reps)],delta_sd_ms=statistics.stdev(delta) if reps>1 else None)
        result.update(profile_scopes=profile,raw_runs=data,means=means,comparisons=comparisons)
        for m in data:print(m,{k:round(v,6) for k,v in means[m].items() if k in ['SMAA','SR_Resolve','SP_Edge','SP_Weights','SP_Neighborhood']})
    DOC.mkdir(exist_ok=True)
    (DOC/f'{a.scene}-{a.phase.lower()}.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
