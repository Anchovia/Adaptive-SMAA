"""Case12 input/control bridges, lifecycle, GPU witnesses, and CPU ROI mirror."""
import argparse,csv,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from edge_quality_inputs import sha,ph,rgb,dds,linear,encoded,reconstruct,edges
from analyze_edge_resolved_rgb_feedback import capture_root,weight,ROIS

ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'Docs/Edge-History-Adaptive-Validation'
MODES=['O-T2X-R','ABL-FirstEdge-Spatial-T2X-R','ABL-ET2X-R-PreviousRawEdge','ABL-ET2X-R-PreviousRawEdge-BilinearRGB','ABL-ET2X-R-PreviousRawEdge-ResolvedRGB','ABL-ET2X-R-PreviousRawEdge-ValidatedRGB','ABL-ET2X-R-PreviousRawEdge-ResponsiveRGB','ABL-ET2X-R-PreviousRawEdge-ClippedRGB']
CASES=[4,6,9,10,11,12,'12-response','12-clip']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def latest(scene,phase,frames=240):return next(x for x in reversed(load(ROOT/'tmp/edge-validated-rgb-feedback-runs.json')) if x['scene']==scene and x['phase']==phase and x['frames']==frames)

def mirror(current,previous,velocity,box,policy):
 x0,y0,x1,y1=box;h,w=current.shape[:2];rec=reconstruct(current,previous,velocity)
 coords=rec['coords'][y0:y1,x0:x1];coord=coords-.5;i=np.floor(coord).astype(np.int32);f=coord-i
 hist=np.zeros((y1-y0,x1-x0,3),np.float32)
 for dx,dy in ((0,0),(1,0),(0,1),(1,1)):
  coeff=(f[:,:,0] if dx else 1-f[:,:,0])*(f[:,:,1] if dy else 1-f[:,:,1])
  hist+=linear(previous[(i[:,:,1]+dy).clip(0,h-1),(i[:,:,0]+dx).clip(0,w-1),:3])*coeff[:,:,None]
 lo9=np.ones_like(hist);hi9=np.zeros_like(hist);lo5=lo9.copy();hi5=hi9.copy()
 yy,xx=np.mgrid[y0:y1,x0:x1]
 for dy in (-1,0,1):
  for dx in (-1,0,1):
   c=linear(current[(yy+dy).clip(0,h-1),(xx+dx).clip(0,w-1),:3]);lo9=np.minimum(lo9,c);hi9=np.maximum(hi9,c)
   if dx==0 or dy==0:lo5=np.minimum(lo5,c);hi5=np.maximum(hi5,c)
 lo=.5*(lo9+lo5);hi=.5*(hi9+hi5);center=.5*(lo+hi);ext=.5*(hi-lo)+1e-8
 disp=hist-center;scale=np.maximum(1,np.max(np.abs(disp/ext),axis=2));hist=center+disp/scale[:,:,None]
 cur=linear(current[y0:y1,x0:x1,:3]);luma=np.array([.2126,.7152,.0722],np.float32);cy=cur@luma;hy=hist@luma
 diff=np.abs(cy-hy)/np.maximum(cy,np.maximum(hy,.2));feedback=np.full_like(cy,.5) if policy==3 else ( .05 if policy==2 else .88)+( .92 if policy==2 else .09)*(1-diff)**2
 wf=2*rec['weight'][y0:y1,x0:x1]*feedback
 bounds=np.all((coords>=0)&(coords<=np.array([w,h])),axis=2);wf[~bounds]=0
 return wf,encoded(cur+(hist-cur)*wf[:,:,None]),rec['safe'][y0:y1,x0:x1],lo,hi,cur,2*rec['weight'][y0:y1,x0:x1]

def verify_output_weight_bounds(actual,actual_weight,lo,hi,current,confidence,policy,safe):
 # Independent algebraic witnesses, not an exact finite-precision GPU sampler.
 # The clipped RGB must stay in the rounded current neighborhood box.
 wf=actual_weight[:,:,None];low=encoded(current+(lo-current)*wf-.5/255).astype(np.int16)-1
 high=encoded(current+(hi-current)*wf+.5/255).astype(np.int16)+1
 assert ((actual.astype(np.int16)>=low)&(actual.astype(np.int16)<=high))[safe].all(),'output outside clipped-color blend box'
 active=safe&(actual_weight>.001)
 if policy==3:
  assert np.abs(actual_weight[active]-.5*confidence[active]).max(initial=0)<3e-6
  return
 # Invert the observed RGB8 blend as an interval, allowing one encoded level and
 # .5/255 linear input-conversion uncertainty. Propagate into the feedback formula.
 o=actual.astype(np.float32);outlo=linear(np.maximum(o-1,0));outhi=linear(np.minimum(o+1,255))
 curlo=np.maximum(current-.5/255,0);curhi=np.minimum(current+.5/255,1)
 den=np.maximum(wf,.001);histlo=np.clip((outlo-(1-wf)*curhi)/den,0,1);histhi=np.clip((outhi-(1-wf)*curlo)/den,0,1)
 luma=np.array([.2126,.7152,.0722],np.float32);cl=curlo@luma;ch=curhi@luma;hl=histlo@luma;hh=histhi@luma
 dmin=np.maximum(0,np.maximum(cl-hh,hl-ch))/np.maximum(ch,np.maximum(hh,.2))
 dmax=np.minimum(1,np.maximum(np.abs(cl-hh),np.abs(ch-hl))/np.maximum(cl,np.maximum(hl,.2)))
 minimum=.05 if policy==2 else .88;span=.97-minimum
 lower=confidence*(minimum+span*(1-dmax)**2);upper=confidence*(minimum+span*(1-dmin)**2)
 assert ((actual_weight>=lower-3e-6)&(actual_weight<=upper+3e-6))[active].all(),'adaptive weight incompatible with observed RGB blend'

def verify(scene,phase):
 receipt=latest(scene,phase);cap=capture_root(receipt);trace=[]
 frames=sorted(int(p.name[6:11]) for p in (cap/MODES[5]).glob('frame_*-weight.dds'))
 assert len(frames)==(6 if phase=='Test' else 43),len(frames)
 checkmodes=MODES[1:] if phase=='Test' else MODES[4:]
 for frame in frames:
  prefix=lambda mode:str(cap/mode/f'frame_{frame:05d}')
  common=MODES[4];reset=frame==0 or (phase=='Test' and frame==3)
  current=dds(prefix(common)+'-current.dds');commoncov=dds(prefix(common)+'-coverage.dds')>0
  for mode in checkmodes:
   cur=dds(prefix(mode)+'-current.dds');cov=dds(prefix(mode)+'-coverage.dds')>0;wf=weight(prefix(mode)+'-weight.dds');out=rgb(prefix(mode)+'.png');history=dds(prefix(mode)+'-next-history.dds')
   assert np.isfinite(wf).all() and (wf>=0).all() and (wf<=.970001).all() and (wf[~cov]==0).all()
   assert np.array_equal(history[:,:,3],cur[:,:,3]),('alpha',scene,frame,mode)
   assert np.array_equal(out[~cov],cur[:,:,:3][~cov]),('nonselected',scene,frame,mode)
   feedback=mode in MODES[4:]
   assert np.array_equal(history[:,:,:3],out if feedback else cur[:,:,:3]),('history',scene,frame,mode)
   chain=frame-1 in frames and not reset
   if chain:
    old=cap/mode/f'frame_{frame-1:05d}-next-history.dds';assert sha(prefix(mode)+'-previous.dds')==sha(old),('chain',frame,mode)
   policy=MODES.index(mode)-4
   we=oe=None
   if feedback:
    for suffix in ('-raw.dds','-current.dds','-velocity.dds','-edge.rg8','-coverage.dds'):
     assert sha(prefix(mode)+suffix)==sha(prefix(common)+suffix),('common input/selection',scene,frame,mode,suffix)
    if reset:assert np.array_equal(out,cur[:,:,:3]),('seed',frame,mode)
    elif policy>0:
     box=list(ROIS[scene].values())[-1];x0,y0,x1,y1=box;previous=dds(prefix(mode)+'-previous.dds');velocity=dds(prefix(mode)+'-velocity.dds')
     pred,pixels,safe,lo,hi,lc,confidence=mirror(cur,previous,velocity,box,policy);safe=safe&cov[y0:y1,x0:x1]
     we=float(np.abs(pred-wf[y0:y1,x0:x1])[safe].max(initial=0));oe=int(np.abs(pixels.astype(np.int16)-out[y0:y1,x0:x1].astype(np.int16))[safe].max(initial=0))
     verify_output_weight_bounds(out[y0:y1,x0:x1],wf[y0:y1,x0:x1],lo,hi,lc,confidence,policy,safe)
   trace.append(dict(frame=frame,mode=mode,selected_percent=float(cov.mean()*100),selected_mean_weight=float(wf[cov].mean()) if cov.any() else 0,chain_checked=chain,roi_weight_max_error=we,roi_rgb_max_error=oe))
 result=dict(validation='PASS',phase=phase,scene=scene,receipt=receipt,capture_root=str(cap),trace=trace,classification='GPU lifecycle/input and color/weight-interval validation; not exact hardware sampling mirror; quality adoption requires frame inspection',mirror_limitations='Ideal float filter errors recorded without asserting exact GPU equality. RGB8 inverse-blend interval and rounded-box containment are independent bounded witnesses, not a sampled-history export.')
 if phase=='Capture':
  old=load(ROOT/f'Docs/Edge-Persistence-Resolved-RGB-Feedback/{scene}-capture.json');oldcap=Path(old['capture_root'])
  for frame in frames:
   for suffix in ('-raw.dds','-current.dds','-velocity.dds','-edge.rg8','-coverage.dds','-weight.dds','-previous.dds','-next-history.dds'):
    assert sha(cap/MODES[4]/f'frame_{frame:05d}{suffix}')==sha(oldcap/MODES[4]/f'frame_{frame:05d}{suffix}'),('old case11 diagnostic bridge',scene,frame,suffix)
  reference=Path(old['reference_root']);hashes={m:[] for m in MODES};rows=[];last={};lastd={};still={}
  for frame in range(240):
   ref=rgb(reference/f'frame_{frame:05d}.png')
   for mode in MODES:
    arr=rgb(cap/mode/f'frame_{frame:05d}.png');hashes[mode].append(ph(arr))
    if mode in (MODES[0],MODES[3],MODES[4]):assert ph(arr)==ph(rgb(oldcap/mode/f'frame_{frame:05d}.png')),('control bridge',scene,mode,frame)
    if 190<=frame<=195:still.setdefault(mode,[]).append(ph(arr))
    for name,box in ROIS[scene].items():
     x0,y0,x1,y1=box;a=arr[y0:y1,x0:x1].astype(np.float32);refroi=ref[y0:y1,x0:x1].astype(np.float32);lum=a@np.array([.2126,.7152,.0722],np.float32);key=(mode,name);delta=lum-last[key] if key in last else None
     rows.append(dict(frame=frame,mode=mode,roi=name,reference_rgb_mae=float(np.abs(a-refroi).mean()),luma_delta=None if delta is None else float(np.abs(delta).mean()),second_delta=None if delta is None or key not in lastd else float(np.abs(delta-lastd[key]).mean())))
     last[key]=lum
     if delta is not None:lastd[key]=delta
  summary=[]
  for name in ROIS[scene]:
   for window,start,end in [('moving',60,180),('transition',172,190),('still',190,240)]:
    for mode in MODES:
     rr=[x for x in rows if x['mode']==mode and x['roi']==name and start<=x['frame']<end];summary.append(dict(window=window,roi=name,mode=mode,reference_rgb_mae=float(np.mean([v['reference_rgb_mae'] for v in rr])),luma_delta=float(np.mean([v['luma_delta'] for v in rr])),second_delta=float(np.mean([v['second_delta'] for v in rr]))))
  with (DOC/f'{scene}-quality-per-frame.csv').open('w',newline='') as fp:
   wr=csv.DictWriter(fp,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
  result.update(reference_root=str(reference),reference_classification='supersample spatial proxy, not temporal ground truth',output_hashes=hashes,roi_metrics=summary,control_bridge=dict(frames=720,RGB_mismatch=0,source_capture=str(oldcap)),still_unique_hashes={m:len(set(v)) for m,v in still.items()})
 (DOC/f'{scene}-{phase.lower()}.json').write_text(json.dumps(result,indent=2)+'\n')
 print(scene,phase,'PASS',len(trace),'witnesses')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scene',required=True,choices=['bistro','minecraft']);p.add_argument('--phase',default='Capture',choices=['Test','Capture']);a=p.parse_args();verify(a.scene,a.phase)
