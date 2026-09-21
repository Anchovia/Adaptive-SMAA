"""Partition remaining static flicker by the new selector's two phases."""
import json
from pathlib import Path
import numpy as np
from analyze_temporal_paired_dejitter import rgb, DMASK, SCALAR, SLINEAR, LINEAR
root=Path(__file__).resolve().parents[2];out=root/'Docs/Temporal-Paired-DeJitter';result={}
for scene in ('bistro','minecraft'):
 q=json.loads((out/f'{scene}-quality.json').read_text())
 assert all(v['lag2_mismatches']==0 for v in q['static_hashes']['late_still'].values())
 capture=Path(q['receipt']['report']).parent
 masks=[rgb(capture/DMASK/f'frame_{i:05d}.png')[:,:,0]==255 for i in (200,201)]
 groups={'always_selected':masks[0]&masks[1],'always_unselected':~masks[0]&~masks[1],
         'selection_switches':masks[0]^masks[1]}
 deltas={}
 for mode in (SCALAR,LINEAR,SLINEAR):
  ims=[rgb(capture/mode/f'frame_{i:05d}.png').astype(np.int16) for i in (200,201)]
  deltas[mode]=np.abs(ims[0]-ims[1]).mean(axis=2)
 rows=[]
 for name,mask in groups.items():
  row=dict(group=name,pixels=int(mask.sum()),pixel_percent=float(mask.mean()*100))
  for mode,d in deltas.items():
   row[mode]=dict(conditional_step=float(d[mask].mean()) if mask.any() else 0,
                 full_frame_contribution=float(d[mask].sum()/mask.size))
  rows.append(row)
 for mode,d in deltas.items():
  assert abs(sum(r[mode]['full_frame_contribution'] for r in rows)-float(d.mean()))<1e-12
 assert rows[0][SLINEAR]['conditional_step']==0,'Always-selected region lost full-screen stability'
 result[scene]=dict(frames=[200,201],groups=rows,
  scope='Screen-fixed measured phase classes, not object tracking or a new selector')
(out/'static-groups.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
