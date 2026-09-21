"""Classify actual GPU static changes without treating RGB thresholds as perception."""
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from analyze_temporal_contribution import ROOT,OUT,NEW,MASK,OLD,image
result={}
for scene in ('bistro','minecraft'):
 q=json.loads((OUT/f'{scene}-quality.json').read_text());cap=Path(q['receipt']['report']).parent
 prior=Path(json.loads((ROOT/f'Docs/Temporal-Paired-DeJitter/{scene}-quality.json').read_text())['receipt']['report']).parent
 records=[];deltas=[]
 for n,mask_name,old in zip(NEW,MASK,('ABL-ScalarWeight-001-R',OLD)):
  before=[image(prior/old/f'frame_{i:05d}.png')[:,:,:3].astype(np.int16) for i in (200,201)]
  after=[image(cap/n/f'frame_{i:05d}.png')[:,:,:3].astype(np.int16) for i in (200,201)]
  b=np.abs(before[0]-before[1]);a=np.abs(after[0]-after[1]);bm=b.max(axis=2);am=a.max(axis=2)
  masks=[image(cap/mask_name/f'frame_{i:05d}.png')[:,:,0]==255 for i in (200,201)]
  groups={'old_stable':bm==0,'old_one_level_only':bm==1,'old_change_above_one':bm>1}
  rows=[]
  for name,m in groups.items():
   rows.append(dict(group=name,pixels=int(m.sum()),screen_percent=float(m.mean()*100),
    before_rgb_step=float(b[m].mean()) if m.any() else None,after_rgb_step=float(a[m].mean()) if m.any() else None,
    after_change_above_one_percent=float(np.mean(am[m]>1)*100) if m.any() else None,
    both_selected_percent=float((masks[0]&masks[1])[m].mean()*100) if m.any() else None))
  records.append(dict(mode=n,old=old,groups=rows,mask_switch_pixels=int(np.count_nonzero(masks[0]^masks[1])),max_rgb_step=int(a.max())))
  deltas.extend([b,a])
 media=cap/'SelectionAnalysis';canvas=Image.new('RGB',(1920,384),'#15181c');draw=ImageDraw.Draw(canvas)
 for col,(d,label) in enumerate(zip(deltas,('Old native luma','New native contribution','Old paired luma','New paired contribution'))):
  im=Image.fromarray(np.minimum(d*8,255).astype(np.uint8)).resize((480,265),Image.Resampling.NEAREST)
  canvas.paste(im,(col*480,60));draw.text((col*480+5,12),label,fill='white');draw.text((col*480+5,30),'f200/f201 RGB difference x8',fill='white')
 path=media/'static-difference-x8.png';canvas.save(path)
 result[scene]=dict(frames=[200,201],classification='Static two-phase RGB change classes; >1 is an engineering threshold, not a visibility threshold',modes=records,image=str(path))
(OUT/'static-groups.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
