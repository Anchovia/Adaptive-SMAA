"""Existing-PNG selector screening; no GPU timing or exact shader-mask claim."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Docs/Temporal-Selection-Validity';OUT.mkdir(exist_ok=True)
NATIVE='O-T2X-R';PAIRED='ABL-PairedDeJitter-R'
OLD={'native':'ABL-ScalarWeight-001-R','paired':'ABL-ScalarPairedDeJitter-001-R'}
CURRENT={'native':'DBG-CurrentSpatial-R','paired':'DBG-DeJitterSpatial-R'}
FULL={'native':NATIVE,'paired':PAIRED}
STARTS=[20,80,100,140,160,180,200]
THRESHOLDS={'absolute':[.00025,.0005,.001,.002,.004,.008,.016], 'relative':[.01,.02,.04,.08]}
v=np.arange(256,dtype=np.float32)/255
DECODE=np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def image(p):
 with Image.open(p) as im:a=np.asarray(im.convert('RGB'))
 assert a.shape==(1061,1920,3)
 return a
def y(a):return np.sum(a.astype(np.float32)*np.array([.2126,.7152,.0722],np.float32),axis=2)
def metric(a,r):return np.abs(a.astype(np.int16)-r.astype(np.int16)).mean(axis=2)
rows=[];sources=[]
for scene in ('bistro','minecraft'):
 qpath=ROOT/f'Docs/Temporal-Paired-DeJitter/{scene}-quality.json'
 q=json.loads(qpath.read_text());cap=Path(q['receipt']['report']).parent;ref=Path(q['reference'])
 assert sha(Path(q['receipt']['report']))==q['receipt']['report_sha256'].lower()
 assert all(d['lag2_mismatches']==0 for d in q['static_hashes']['late_still'].values())
 source=dict(scene=scene,prior_analysis_sha256=sha(qpath),report_sha256=q['receipt']['report_sha256'],frames=[])
 sources.append(source)
 for start in STARTS:
  rs=[image(ref/f'frame_{i:05d}.png') for i in (start,start+1)]
  frame_hashes={}
  native=[image(cap/NATIVE/f'frame_{i:05d}.png') for i in (start,start+1)]
  for basis in ('native','paired'):
   cs=[image(cap/CURRENT[basis]/f'frame_{i:05d}.png') for i in (start,start+1)]
   fs=[image(cap/FULL[basis]/f'frame_{i:05d}.png') for i in (start,start+1)]
   os=[image(cap/OLD[basis]/f'frame_{i:05d}.png') for i in (start,start+1)]
   old_masks=[image(cap/('DBG-ContrastMask-001-R' if basis=='native' else 'DBG-DeJitterMask-001-R')/f'frame_{i:05d}.png')[:,:,0]==255 for i in (start,start+1)]
   for k in range(2):assert np.array_equal(os[k],np.where(old_masks[k][:,:,None],fs[k],cs[k]))
   ec=[metric(a,r) for a,r in zip(cs,rs)];ef=[metric(a,r) for a,r in zip(fs,rs)]
   impacts=[];relative=[]
   for c,f in zip(cs,fs):
    lc,lf=DECODE[c],DECODE[f]
    d=np.max(np.abs(lf-lc),axis=2);impacts.append(d)
    relative.append(d/np.maximum(np.maximum(lc.max(axis=2),lf.max(axis=2)),.01))
   old_step=np.max(np.abs(os[0].astype(np.int16)-os[1].astype(np.int16)),axis=2)
   remaining_fail=old_step>1
   stable=old_step==0
   ry_step=y(rs[1])-y(rs[0])
   options=[('full',None,[np.ones_like(stable),np.ones_like(stable)]),
            ('current',None,[np.zeros_like(stable),np.zeros_like(stable)]),('gradient-001',.01,old_masks)]
   for family,ts in THRESHOLDS.items():
    values=impacts if family=='absolute' else relative
    for direction in ('large','small'):
     for t in ts:options.append((family+'-'+direction,t,[d>=t if direction=='large' else d<t for d in values]))
   for name,t,masks in options:
    ims=[np.where(m[:,:,None],f,c) for m,c,f in zip(masks,cs,fs)]
    step=np.abs(ims[1].astype(np.int16)-ims[0].astype(np.int16))
    current_error=sum(float(e.mean()) for e in ec)/2
    reference_error=sum(float(np.where(m,a,b).mean()) for m,a,b in zip(masks,ef,ec))/2
    native_error=sum(float(metric(a,r).mean()) for a,r in zip(native,rs))/2
    both=masks[0]&masks[1]
    rows.append(dict(scene=scene,basis=basis,frame=start,split='development' if start in (20,80,100) else 'validation',
      window='still' if start in (20,200) else 'transition' if start==180 else 'moving',selector=name,threshold=t,
      selected_percent=50*sum(float(m.mean()) for m in masks),switch_percent=float(np.mean(masks[0]^masks[1])*100),
      rgb_mae=reference_error,native_rgb_mae=native_error,current_rgb_mae=current_error,
      rgb_step=float(step.mean()),max_rgb_step=int(step.max()),
      reference_delta_residual=float(np.abs((y(ims[1])-y(ims[0]))-ry_step).mean()),
      remaining_failure_pixels=int(remaining_fail.sum()),
      both_selected_on_old_fail_percent=float(both[remaining_fail].mean()*100) if remaining_fail.any() else None,
      both_selected_on_old_stable_percent=float(both[stable].mean()*100) if stable.any() else None,
      oracle_rgb_mae=sum(float(np.minimum(a,b).mean()) for a,b in zip(ef,ec))/2))
   for mode in (CURRENT[basis],FULL[basis],OLD[basis]):
    for i in (start,start+1):frame_hashes[f'{mode}/{i}']=sha(cap/mode/f'frame_{i:05d}.png')
  for i in (start,start+1):frame_hashes[f'SS-Reference/{i}']=sha(ref/f'frame_{i:05d}.png')
  source['frames'].append(dict(start=start,sha256=frame_hashes))
  print(f'{scene}: pair {start}/{start+1} complete',flush=True)
result=dict(classification='Offline PNG-quantized feature proxy; fixed camera-path samples; no GPU implementation or performance claim',
 sources=sources,rows=rows)
(OUT/'offline.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS: {len(rows)} selector/basis/pose rows')
