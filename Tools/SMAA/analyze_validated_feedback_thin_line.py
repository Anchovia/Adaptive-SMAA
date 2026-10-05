"""Actual-output contrast in a fixed Minecraft screen strip; not object tracking."""
import json,csv
import numpy as np
from analyze_edge_validated_rgb_feedback import ROOT,DOC,MODES,CASES,load
from analyze_edge_resolved_rgb_feedback import weight
from edge_quality_inputs import rgb,dds,sha
d=load(DOC/'minecraft-capture.json');cap=__import__('pathlib').Path(d['capture_root']);rows=[];pixels=[]
luma=np.array([.2126,.7152,.0722],np.float32)
for frame in range(126,139):
 current=dds(cap/MODES[4]/f'frame_{frame:05d}-current.dds');x=int(np.argmin((current[578:612,966:984,:3].astype(np.float32)@luma).mean(axis=0)))+966
 def contrast(a):
  lum=a.astype(np.float32)@luma
  return float((.5*(lum[578:612,x-3]+lum[578:612,x+3])-lum[578:612,x]).mean())
 for case,mode in zip(CASES,MODES):
  arr=rgb(cap/mode/f'frame_{frame:05d}.png');coverage=wf=None
  if mode in MODES[4:]:
   coverage=dds(cap/mode/f'frame_{frame:05d}-coverage.dds')>0;wf=weight(cap/mode/f'frame_{frame:05d}-weight.dds')
  rows.append(dict(frame=frame,case=case,mode=mode,column=x,spatial_contrast=contrast(current[:,:,:3]),output_contrast=contrast(arr),selected_line_pixels=None if coverage is None else int(coverage[578:612,x].sum()),mean_line_history_weight=None if wf is None else float(wf[578:612,x].mean())))
  if frame in (128,129,130,131):
   pixels.append(dict(frame=frame,case=case,xy=[972,590],rgb=arr[590,972].tolist(),weight=None if wf is None else float(wf[590,972]),source=str(cap/mode/f'frame_{frame:05d}.png'),sha256=sha(cap/mode/f'frame_{frame:05d}.png')))
with (DOC/'minecraft-line-contrast.csv').open('w',newline='') as fp:
 wr=csv.DictWriter(fp,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
summary=[]
for case in CASES:
 rr=[r for r in rows if r['case']==case];v=np.array([r['output_contrast'] for r in rr]);summary.append(dict(case=case,mean_contrast=float(v.mean()),min=float(v.min()),max=float(v.max()),std=float(v.std()),adjacent_difference=float(np.abs(np.diff(v)).mean())))
(DOC/'minecraft-line-contrast.json').write_text(json.dumps(dict(classification='Fixed screen strip diagnostic; no object tracking, reference ground truth or standalone quality score',strip=dict(x_search=[966,983],y=[578,611],column='minimum mean CURRENT SPATIAL luma; shared across output modes',background='column +-3'),frames=[126,138],rows=rows,pixels=pixels,summary=summary),indent=2)+'\n')
print('PASS actual-output thin-line trace',len(rows),'records')
