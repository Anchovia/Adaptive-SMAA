"""Bounded output equivalence and paired runtime analysis, no quality scoring."""
import argparse,csv,hashlib,json,math,statistics as st
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
NATIVE='O-T2X-R';BASE='ABL-ScalarPairedDeJitter-001-R'
MODES=[NATIVE,BASE,'ABL-SpeedBranch-R','ABL-SpeedUniformScalar-R','ABL-SpeedUniformBranch-R','ABL-SpeedUniformWarp-R','ABL-SpeedPhaseScalar-R']
GROUP_MODES=[NATIVE,BASE,'ABL-SpeedPhaseScalar-R','ABL-SpeedGroup4-R','ABL-SpeedGroup8-R','ABL-SpeedGroup16-R','ABL-SpeedDensity8-R','ABL-SpeedDensity16-R']
METRICS=['SMAA','Spatial','Resolve','WholeFrame','WallFrame']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(scene,phase,receipt):
 records=json.loads(receipt.read_text(encoding='utf-8-sig'))
 rs=[r for r in records if r['scene']==scene and r['phase']==phase];assert len(rs)==1
 r=rs[0];report=Path(r['report']);assert sha(report)==r['report_sha256'].lower()
 text=report.read_text(encoding='utf-8-sig')
 for token in ('Aggregate: PASS','1920 x 1061','API:  DirectX11','Speed-only paired resolve gate:',f'Scene: {scene}'):
  assert token in text,token
 assert 'Aggregate: FAIL' not in text
 return r,report.parent,text
def capture(scene,phase,receipt):
 r,path,text=read(scene,phase,receipt)
 modes=GROUP_MODES if phase=='GroupCapture' else MODES
 indices=sorted(set(range(0,240,5))|{1,61,179,181,201});assert len(indices)==53
 files=[f'frame_{i:05d}.png' for i in indices]
 checks=[[x.strip() for x in row] for row in csv.reader(text.splitlines()) if row and row[0].strip()=='pattern_check']
 assert len(checks)==len(modes)*240 and all(row[3:5]==['On','PASS'] for row in checks)
 old=ROOT/'Projects/CMAA2/AutoBench'/('20260921_165121' if scene=='minecraft' else '20260921_165534')
 results={};bridges=0
 for m in modes:
  assert [p.name for p in sorted((path/m).glob('*.png'))]==files,m
  target=old/m if m in (NATIVE,BASE) else path/BASE
  bad=[];maxdiff=0;channels=0;hashes=[]
  for f in files:
   hashes.append(sha(path/m/f))
   if sha(path/m/f)!=sha(target/f):
    a=np.asarray(Image.open(path/m/f).convert('RGBA')).astype(np.int16)
    b=np.asarray(Image.open(target/f).convert('RGBA')).astype(np.int16)
    d=np.abs(a-b);maxdiff=max(maxdiff,int(d.max()));channels+=int(np.count_nonzero(d));bad.append(f)
   if m in (NATIVE,BASE):bridges+=1
  results[m]=dict(match=not bad,mismatching_frames=bad,max_channel_error=maxdiff,differing_channels=channels,png_sha256=hashes)
 result=dict(scene=scene,receipt=r,indices=indices,baseline_bridge_comparisons=bridges,pattern_checks=len(checks),modes=results,
  scope='53 sampled RGBA PNGs per mode out of 240 rendered frames; not a quality evaluation or universal equivalence proof')
 assert results[NATIVE]['match'] and results[BASE]['match'],'Baseline regression'
 return result
def timing(scene,phase,receipt):
 r,path,text=read(scene,phase,receipt);rows=[];dist=[]
 for row in csv.reader(text.splitlines()):
  v=[x.strip() for x in row]
  if v and v[0]=='timing':rows.append(dict(mode=v[1],run=int(v[2]),metric=v[3],samples=int(v[4]),mean_ms=float(v[5]),p95_ms=float(v[6]),threshold=float(v[7])))
  if v and v[0]=='distribution':dist.append(dict(mode=v[1],run=int(v[2]),metric=v[3],samples=int(v[4]),median_ms=float(v[5]),sample_std_ms=float(v[6]),p99_ms=float(v[7]),wall_fps=float(v[8]),wall_1pct_low_fps=float(v[9])))
 modes=GROUP_MODES if phase.startswith('Group') else MODES if phase!='Benchmark' else [NATIVE,BASE,'ABL-SpeedUniformScalar-R','ABL-SpeedPhaseScalar-R']
 samples,repeats=(240,1) if phase.endswith('Smoke') else (2400,3) if phase.endswith('ScreenBenchmark') else (4800,4)
 expected=[(m,i,t) for i in range(repeats) for m in (modes if i%2==0 else modes[::-1]) for t in METRICS]
 for data in (rows,dist):
  assert [(v['mode'],v['run'],v['metric']) for v in data]==expected
  assert all(v['samples']==samples for v in data)
 for a,b in zip(rows,dist):
  assert math.isfinite(a['mean_ms']) and a['mean_ms']>0
  assert b['median_ms']<=a['p95_ms']<=b['p99_ms']
 assert 'pattern_check,' not in text
 means={m:{t:dict(mean_ms=st.mean(v['mean_ms'] for v in rows if v['mode']==m and v['metric']==t),
   runs=[v['mean_ms'] for v in rows if v['mode']==m and v['metric']==t]) for t in METRICS} for m in modes}
 comparisons={}
 for m in modes:
  if m in (NATIVE,BASE):continue
  for ref in (BASE,NATIVE):
   comparisons[m+' minus '+ref]={}
   for t in METRICS:
    a,b=means[m][t],means[ref][t];ds=[x-y for x,y in zip(a['runs'],b['runs'])]
    comparisons[m+' minus '+ref][t]=dict(delta_ms=a['mean_ms']-b['mean_ms'],delta_percent=100*(a['mean_ms']/b['mean_ms']-1),
     slower_runs=sum(x>0 for x in ds),paired_run_deltas_ms=ds)
 return dict(scene=scene,phase=phase,validation='PASS',receipt=r,means=means,comparisons=comparisons,timing_rows=rows,distribution_rows=dist,
  scope='Alternating repetitions within one process; not independent process pairs or equivalence proof')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scene',required=True);p.add_argument('--phase',choices=['Capture','Smoke','ScreenBenchmark','GroupCapture','GroupSmoke','GroupScreenBenchmark','Benchmark'],required=True)
 p.add_argument('--receipt',type=Path,default=ROOT/'tmp/temporal-speed-runs.json')
 p.add_argument('--output-dir',type=Path,default=ROOT/'Docs/Temporal-Speed-Limits');a=p.parse_args()
 result=capture(a.scene,a.phase,a.receipt) if a.phase.endswith('Capture') else timing(a.scene,a.phase,a.receipt)
 a.output_dir.mkdir(parents=True,exist_ok=True)
 dest=a.output_dir/f'{a.scene}-{a.phase}.json';dest.write_text(json.dumps(result,indent=2)+'\n')
 if a.phase.endswith('Capture'):print(json.dumps({k:{x:v[x] for x in ['match','mismatching_frames','max_channel_error','differing_channels']} for k,v in result['modes'].items()},indent=2))
 else:print(json.dumps({m:{t:v[t]['mean_ms'] for t in ['SMAA','Resolve']} for m,v in result['means'].items()},indent=2))
