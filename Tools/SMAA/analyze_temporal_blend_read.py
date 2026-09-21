"""Verify identical outputs and summarize clean same-process read-cost runs."""
import argparse,csv,hashlib,json,math,statistics as st
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Docs/Temporal-Blend-Read-Cost'
MODES=['O-T2X-R','ABL-BlendBindOnly-R','ABL-BlendReadControl-R','ABL-BlendReadOne-R']
DEBUG='DBG-BlendRead-Observable-R'
INDICES=[0,1,60,61,140,179,180,200,201,239]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(scene,phase):
 rs=json.loads((ROOT/'tmp/temporal-blend-read-runs.json').read_text(encoding='utf-8-sig'))
 matches=[x for x in rs if x['scene']==scene and x['phase']==phase];assert len(matches)==1
 r=matches[0];p=Path(r['report']);assert sha(p)==r['report_sha256'].lower()
 text=p.read_text(encoding='utf-8-sig')
 for token in ('Aggregate: PASS','Blend texture read gate:','1920 x 1061','API:  DirectX11',f'Scene: {scene}'):assert token in text
 assert 'Aggregate: FAIL' not in text
 return r,p.parent,text
def rgba(p):
 with Image.open(p) as im:a=np.asarray(im.convert('RGBA'))
 assert a.shape==(1061,1920,4)
 return a
def capture(scene):
 r,cap,text=read(scene,'Capture')
 patterns=[[x.strip() for x in row] for row in csv.reader(text.splitlines()) if row and row[0].strip()=='pattern_check']
 assert len(patterns)==1200 and all(p[3:5]==['On','PASS'] for p in patterns)
 old=json.loads((ROOT/f'Docs/Temporal-Paired-DeJitter/{scene}-quality.json').read_text())
 prior=Path(old['receipt']['report']).parent;assert sha(Path(old['receipt']['report']))==old['receipt']['report_sha256'].lower()
 expected=[f'frame_{i:05d}.png' for i in INDICES]
 for mode in MODES+[DEBUG]:assert [p.name for p in sorted((cap/mode).glob('*.png'))]==expected
 checks=[];observable=[]
 for f in expected:
  native=cap/MODES[0]/f;assert sha(native)==sha(prior/MODES[0]/f),('baseline changed',scene,f)
  for mode in MODES[1:]:
   assert sha(cap/mode/f)==sha(native),(scene,mode,f,'output mismatch')
   checks.append(dict(frame=f,mode=mode,sha256=sha(native)))
  a,b=rgba(native),rgba(cap/DEBUG/f)
  diff=np.abs(a.astype(np.int16)-b.astype(np.int16))
  observable.append(dict(frame=f,changed_rgba_pixels=int(np.any(diff>0,axis=2).sum()),max_channel_delta=int(diff.max())))
 assert all(x['changed_rgba_pixels']>0 for x in observable),'probe never read meaningful data'
 result=dict(scene=scene,validation='PASS',classification='Output-preserving engineering gate; no quality ranking',receipt=r,
   baseline_bridge=10,exact_output_comparisons=len(checks),pattern_checks=len(patterns),mismatches=0,checks=checks,observable_scale_one=observable)
 (OUT/f'{scene}-capture.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ('checks','observable_scale_one')},indent=2))
def timing(scene,phase):
 r,cap,text=read(scene,phase);rows=[];dist=[]
 for row in csv.reader(text.splitlines()):
  v=[x.strip() for x in row]
  if v and v[0]=='timing':rows.append(dict(mode=v[1],run=int(v[2]),metric=v[3],samples=int(v[4]),mean_ms=float(v[5]),p95_ms=float(v[6]),scale=float(v[7])))
  if v and v[0]=='distribution':dist.append(dict(mode=v[1],run=int(v[2]),metric=v[3],samples=int(v[4]),median_ms=float(v[5]),sample_sd_ms=float(v[6]),p99_ms=float(v[7]),wall_fps=float(v[8]),wall_1pct_low_fps=float(v[9])))
 samples,repeats=(240,1) if phase=='Smoke' else (4800,4)
 metrics=['SMAA','Spatial','Resolve','WholeFrame','WallFrame']
 expected=[(m,i,k) for i in range(repeats) for m in (MODES if i%2==0 else MODES[::-1]) for k in metrics]
 for data in (rows,dist):assert [(x['mode'],x['run'],x['metric']) for x in data]==expected and all(x['samples']==samples for x in data)
 assert all(x['scale']==0 and math.isfinite(x['mean_ms']) and x['mean_ms']>0 for x in rows)
 assert all(y['median_ms']<=x['p95_ms']<=y['p99_ms'] for x,y in zip(rows,dist))
 means={m:{k:st.mean(x['mean_ms'] for x in rows if x['mode']==m and x['metric']==k) for k in metrics} for m in MODES}
 result=dict(scene=scene,phase=phase,validation='PASS',receipt=r,means=means,timing_rows=rows,distribution_rows=dist)
 (OUT/f'{scene}-{phase}.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(means,indent=2))
def summary():
 lines=['# Output-preserving blendRT read: measured tables','','Times are ms. Binding is not a CPU-to-GPU texture copy.',''];stats={};hashes=set()
 for scene in ('bistro','minecraft'):
  data={p:json.loads((OUT/f'{scene}-{p}.json').read_text()) for p in ('capture','Smoke','Benchmark')}
  for d in data.values():assert d['validation']=='PASS';hashes.add(d['receipt']['executable_sha256'])
  t=data['Benchmark'];rows=t['timing_rows'];stats[scene]=[]
  lines.extend([f'## {scene}','','| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |','|---|---:|---:|---:|---:|'])
  for m,v in t['means'].items():
   sd=lambda k:st.stdev(x['mean_ms'] for x in rows if x['mode']==m and x['metric']==k)
   lines.append(f"| {m} | {v['SMAA']:.6f} ± {sd('SMAA'):.6f} | {v['Resolve']:.6f} ± {sd('Resolve'):.6f} | {v['Spatial']:.6f} | {v['WholeFrame']:.6f} |")
  lines.extend(['','| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |','|---|---|---:|---:|---|'])
  for new,base in [(MODES[1],MODES[0]),(MODES[2],MODES[1]),(MODES[3],MODES[2]),(MODES[3],MODES[0])]:
   for metric in ('Resolve','SMAA','WholeFrame'):
    lookup={(x['mode'],x['run']):x['mean_ms'] for x in rows if x['metric']==metric}
    ds=[lookup[new,i]-lookup[base,i] for i in range(4)];mean=st.mean(ds);pct=100*(t['means'][new][metric]/t['means'][base][metric]-1)
    stats[scene].append(dict(new=new,base=base,metric=metric,delta_ms=mean,delta_percent=pct,repeat_deltas=ds,delta_sd_ms=st.stdev(ds)))
    lines.append(f'| {new} − {base} | {metric} | {mean:+.6f} | {pct:+.3f}% | '+', '.join(f'{x:+.6f}' for x in ds)+' |')
  lines.extend(['','| Phase | Run directory |','|---|---|'])
  for phase,d in data.items():lines.append(f"| {phase} | `{Path(d['receipt']['report']).parent.name}` |")
  lines.append('')
 assert len(hashes)==1,hashes
 lines.extend(['Four alternating-order repeats within one process; no cross-device or independent-day claim.',
               'ReadOne−ReadControl includes Load, coordinates, dependency, register/cache effects and different probe source; it is not isolated DRAM transfer time.',
               'ReadOne−Native includes the artificial sink arithmetic. No quality or candidate policy changes.',''])
 (OUT/'tables.md').write_text('\n'.join(lines));(OUT/'comparisons.json').write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps(stats,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft']);p.add_argument('--phase',choices=['Capture','Smoke','Benchmark','Summary'],required=True);a=p.parse_args()
 if a.phase=='Summary':summary()
 else:
  assert a.scene
  capture(a.scene) if a.phase=='Capture' else timing(a.scene,a.phase)
