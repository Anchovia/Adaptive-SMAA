"""Fail closed on changed input values, selection, output, controls or timing counts."""
import argparse,csv,hashlib,json,statistics
from pathlib import Path
import numpy as np
from PIL import Image
from analyze_first_edge_stencil import edge,coverage
R=Path(__file__).resolve().parents[2];D=R/'Docs/Edge-Persistence-Velocity-Load'
A='A-CurrentEdge-Stencil';F='F-EagerPreviousFetch';L='L-VelocityIntegerLoad';O='O-T2X-R';MODES=[A,F,L,O]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rgb(p):
 with Image.open(p) as im:
  assert im.size==(1920,1061) and im.mode=='RGB',(p,im.size,im.mode)
  return np.asarray(im).copy()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--scene',required=True,choices=['bistro','minecraft']);ap.add_argument('--phase',required=True,choices=['Test','Capture','Smoke','Benchmark','ProfileSmoke','ProfileBenchmark']);args=ap.parse_args()
 receipts=json.loads((R/'tmp/edge-velocity-load-runs.json').read_text(encoding='utf-8-sig'))
 rec=next(v for v in reversed(receipts) if v['scene']==args.scene and v['phase']==args.phase)
 p=Path(rec['report']);assert sha(p).upper()==rec['report_sha256']
 text=p.read_text();assert 'Aggregate: PASS' in text and 'FAIL' not in text
 rows=[[v.strip() for v in row if v.strip()] for row in csv.reader(text.splitlines()) if row]
 out=dict(validation='PASS',receipt=rec,classification='case-9 velocity access only')
 if args.phase in ['Test','Capture']:
  root=Path(next(r[1] for r in rows if r[0]=='capture_root'));n=6 if args.phase=='Test' else 240
  hashes={}
  for m in MODES:
   paths=sorted((root/m).glob('frame_[0-9][0-9][0-9][0-9][0-9].png'));assert len(paths)==n
   hashes[m]=[hashlib.sha256(rgb(p).tobytes()).hexdigest() for p in paths]
  old=json.loads((D/f'{args.scene}-baseline.json').read_text())
  mismatch={'L_vs_F':sum(a!=b for a,b in zip(hashes[L],hashes[F]))}
  for m in [A,F,O]:mismatch[m+'_preserved']=sum(a!=b for a,b in zip(hashes[m],old['output_hashes'][m][:n]))
  assert not any(mismatch.values()),mismatch
  traces={m:{} for m in [A,F,L]}
  for r in rows:
   if r[0]=='trace':
    assert r[5]=='PASS' and int(r[8])==0 and int(r[9])==0,('velocity probe',r)
    traces[r[1]][int(r[2])]=r
  assert all(len(v)==(6 if n==6 else 43) for v in traces.values())
  verified=[]
  for i in traces[F]:
   stem=f'frame_{i:05d}';raw=edge(root/F/(stem+'-edge.rg8'));mask=coverage(root/F/(stem+'-coverage.dds'))
   assert np.all(mask[raw])
   entry=dict(frame=i,current_count=int(raw.sum()),union_count=int(mask.sum()))
   for m in [A,F,L]:
    expected=raw if m==A else mask;r=traces[m][i]
    actual=coverage(root/m/(stem+'-coverage.dds'));assert np.array_equal(expected,actual)
    assert int(r[4])==int(expected.sum()) and int(r[3])>=int(r[4])
    assert int(r[6])==int(expected.sum()) and int(r[7])>=int(r[6])
    for suffix in ['-edge.rg8','-current.dds','-velocity.dds']:
     assert (root/m/(stem+suffix)).read_bytes()==(root/F/(stem+suffix)).read_bytes(),(m,i,suffix)
    final=rgb(root/m/(stem+'.png'));current=rgb(root/m/(stem+'-current.png'))
    assert not np.any(final[~expected]!=current[~expected]),(m,i,'nonselected output')
   verified.append(entry)
  checks=[r for r in rows if r[0]=='mode_check'];assert len(checks)==n*len(MODES) and all(r[-1]=='PASS' for r in checks)
  out.update(capture_root=str(root),frames_per_mode=n,output_hashes=hashes,mismatched_frames=mismatch,velocity_value_mismatches=0,velocity_coordinate_mismatches=0,probe_fullscreen_draws=sum(len(v) for v in traces.values()),trace_checks=verified)
  print('PASS exact velocity/coordinates, RGB/raw/current/coverage, preserved controls:',args.scene,args.phase)
 else:
  profile=args.phase.startswith('Profile');smoke=args.phase.endswith('Smoke');n=240 if smoke else (960 if profile else 4800);runs=1 if smoke else 3
  data={};details={};seen=set()
  for r in rows:
   if r[0]!='timing':continue
   _,m,run,metric,count,mean,median,p95,p99,sd,low=r
   run=int(run);assert m in MODES and int(count)==n and 0<=run<runs
   key=(m,metric,run);assert key not in seen;seen.add(key)
   data.setdefault(m,{}).setdefault(metric,{})[run]=float(mean)
   details.setdefault(m,{}).setdefault(metric,{})[run]=dict(median_ms=float(median),p95_ms=float(p95),p99_ms=float(p99),sd_ms=float(sd),slowest_one_percent_equivalent_fps=float(low))
  assert set(data)==set(MODES)
  assert all(len(v)==runs for d in data.values() for v in d.values())
  assert all(len(d)==(10 if profile else 6) for d in data.values())
  assert not any(r[0]=='trace' for r in rows)
  means={m:{k:statistics.mean(v.values()) for k,v in d.items()} for m,d in data.items()}
  comparisons={}
  for base in [A,F,O]:
   comparisons[base]={}
   for m in MODES:
    comparisons[base][m]={}
    for k in means[m]:
     deltas=[data[m][k][i]-data[base][k][i] for i in range(runs)]
     comparisons[base][m][k]=dict(delta_ms=means[m][k]-means[base][k],percent=100*(means[m][k]/means[base][k]-1),paired_percent=[100*(data[m][k][i]/data[base][k][i]-1) for i in range(runs)],paired_delta_ms=deltas,delta_sd_ms=statistics.stdev(deltas) if runs>1 else None)
  out.update(profile_scopes=profile,frames_per_run=n,repeats=runs,means=means,raw_runs=data,distribution=details,comparisons=comparisons)
  for m in MODES:print(m,{k:round(v,6) for k,v in means[m].items() if k in ['SMAA','SR_Resolve','SP_Edge']})
 (D/f'{args.scene}-{args.phase.lower()}.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
