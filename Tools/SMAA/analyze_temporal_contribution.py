"""Actual GPU contribution masks, unchanged controls, sparse contiguous quality windows."""
import argparse,csv,hashlib,json,math,statistics as st
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from create_temporal_contrast_playback import encode,gif

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Docs/Temporal-Selection-Validity'
NATIVE='O-T2X-R';FULL='ABL-PairedDeJitter-R';OLD='ABL-ScalarPairedDeJitter-001-R'
NEW=['ABL-ContributionNative-00005-R','ABL-ContributionPaired-00005-R']
MASK=['DBG-ContributionNative-00005-R','DBG-ContributionPaired-00005-R']
CURRENT=['DBG-CurrentSpatial-R','DBG-DeJitterSpatial-R']
MODES=[NATIVE,FULL,OLD,*NEW];ALL=[*MODES,*MASK,*CURRENT]
WINDOWS={'moving':range(140,156),'transition':range(176,192),'late_still':range(200,216)}
INDICES=[0,*WINDOWS['moving'],*WINDOWS['transition'],*WINDOWS['late_still']]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def image(p):
 with Image.open(p) as im:a=np.asarray(im.convert('RGBA'))
 assert a.shape==(1061,1920,4)
 return a
def luma(a):return (a[:,:,:3].astype(np.float32)*np.array([.2126,.7152,.0722],np.float32)).sum(axis=2)
def gradient(y):return .5*(float(np.abs(np.diff(y,axis=0)).mean())+float(np.abs(np.diff(y,axis=1)).mean()))
def read(scene,phase):
 rs=json.loads((ROOT/'tmp/temporal-selection-runs.json').read_text(encoding='utf-8-sig'))
 rs=[r for r in rs if r['scene']==scene and r['phase']==phase];assert len(rs)==1
 r=rs[0];p=Path(r['report']);assert sha(p)==r['report_sha256'].lower()
 text=p.read_text(encoding='utf-8-sig')
 for token in ('Aggregate: PASS','Contribution gate:','1920 x 1061','API:  DirectX11',f'Scene: {scene}'):assert token in text
 assert 'Aggregate: FAIL' not in text
 return r,p.parent,text

def capture(scene):
 receipt,cap,text=read(scene,'Capture')
 checks=[[x.strip() for x in row] for row in csv.reader(text.splitlines()) if row and row[0].strip()=='pattern_check']
 assert len(checks)==2160 and all(r[3:5]==['On','PASS'] for r in checks)
 q=json.loads((ROOT/f'Docs/Temporal-Paired-DeJitter/{scene}-quality.json').read_text())
 prior=Path(q['receipt']['report']).parent;ref=Path(q['reference'])
 assert sha(Path(q['receipt']['report']))==q['receipt']['report_sha256'].lower()
 for m in ALL:assert [p.name for p in sorted((cap/m).glob('*.png'))]==[f'frame_{i:05d}.png' for i in INDICES]
 hashes={m:[] for m in ALL};rows=[];coverage=[];previous={};old_ref=None;old_index=-2;bridges=0
 for i in INDICES:
  f=f'frame_{i:05d}.png'
  for m in (NATIVE,FULL,OLD,*CURRENT):
   assert sha(cap/m/f)==sha(prior/m/f),(m,i,'baseline regression');bridges+=1
  ims={m:image(cap/m/f) for m in ALL};reference=image(ref/f);ry=luma(reference);rg=gradient(ry)
  for m,a in ims.items():hashes[m].append(hashlib.sha256(a[:,:,:3].tobytes()).hexdigest())
  for n,mask_name,c,full in zip(NEW,MASK,CURRENT,(NATIVE,FULL)):
   mask=ims[mask_name][:,:,:3];assert np.all((mask==0)|(mask==255)) and np.all(mask==mask[:,:,:1])
   selected=mask[:,:,0]==255
   expected=np.where(selected[:,:,None],ims[full],ims[c])
   assert np.array_equal(ims[n],expected),(n,i,'selected/full or unselected/current mismatch')
   if i==0:assert not selected.any() and np.array_equal(ims[n],ims[c])
   oldmask=previous.get(mask_name)
   coverage.append(dict(frame=i,mode=n,selected_pixels=int(selected.sum()),selected_percent=float(selected.mean()*100),
     switch_percent=float(np.mean(selected!=oldmask)*100) if oldmask is not None and old_index==i-1 else None))
   previous[mask_name]=selected
  for m in MODES:
   a=ims[m][:,:,:3].astype(np.float32);r=reference[:,:,:3].astype(np.float32);d=a-r;y=luma(ims[m]);mse=float(np.square(d).mean())
   old=previous.get(m);consecutive=old is not None and old_index==i-1
   rows.append(dict(frame=i,mode=m,rgb_mae=float(np.abs(d).mean()),psnr_db=10*math.log10(255**2/mse) if mse else None,
    gradient_reference_ratio=gradient(y)/rg,
    rgb_step=float(np.abs(a-old[0]).mean()) if consecutive else None,
    reference_delta_residual=float(np.abs((y-old[1])-(ry-old_ref)).mean()) if consecutive else None))
   previous[m]=(a,y)
  old_ref=ry;old_index=i
  if i in (0,155,191,215):print(scene,'validated through frame',i,flush=True)
 result=dict(scene=scene,receipt=receipt,reference=str(ref),classification='Engineering quality windows; SS spatial proxy, not absolute temporal ground truth',
  indices=INDICES,pattern_checks=len(checks),baseline_hash_comparisons=bridges,selection_semantics_frames=98,selection_mismatches=0,
  windows={},coverage={},static={},per_frame=rows,per_frame_coverage=coverage,pixel_sha256=hashes)
 for window,indices in WINDOWS.items():
  result['windows'][window]={}
  for m in MODES:
   selected_rows=[r for r in rows if r['mode']==m and r['frame'] in indices]
   result['windows'][window][m]={k:st.mean(r[k] for r in selected_rows if r[k] is not None) for k in ('rgb_mae','psnr_db','gradient_reference_ratio','rgb_step','reference_delta_residual')}
  result['coverage'][window]={m:{k:st.mean(r[k] for r in coverage if r['mode']==m and r['frame'] in indices and r[k] is not None)
    for k in ('selected_pixels','selected_percent','switch_percent')} for m in NEW}
 for m in ALL:
  hs=hashes[m][-16:];result['static'][m]=dict(unique_rgb_frames=len(set(hs)),lag2_mismatches=sum(x!=y for x,y in zip(hs,hs[2:])))
 media=cap/'SelectionAnalysis';media.mkdir(exist_ok=True)
 roi=(420,590,900,910) if scene=='bistro' else (720,240,1200,560)
 visible=[NATIVE,OLD,*NEW];labels=['Original T2X-R','Previous paired selection','Contribution Native','Contribution Paired']
 def render(i,slow=False):
  canvas=Image.new('RGB',(1920,350),'#15181c');draw=ImageDraw.Draw(canvas)
  for col,(m,label) in enumerate(zip(visible,labels)):
   with Image.open(cap/m/f'frame_{i:05d}.png') as im:canvas.paste(im.convert('RGB').crop(roi),(col*480,30))
   draw.text((col*480+5,8),f'{label} | f{i} | '+('0.5x' if slow else '1x'),fill='white')
  return canvas
 result['media']={}
 for name,frames in WINDOWS.items():
  result['media'][name]=dict(video=encode(media/f'{name}.mp4',lambda i:render(frames[i]),len(frames)),
   gif=gif(media/f'{name}.gif',render,frames.start,frames.stop))
 sheet=Image.new('RGB',(1920,1400),'#15181c')
 for row,i in enumerate((200,201,202,203)):sheet.paste(render(i),(0,row*350))
 sheet.save(media/'still-sequence.png')
 result['still_sequence']=str(media/'still-sequence.png')
 (OUT/f'{scene}-quality.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(scene=scene,still=result['windows']['late_still'],coverage=result['coverage']),indent=2))

def timing(scene,phase):
 receipt,cap,text=read(scene,phase);rows=[];distributions=[]
 for row in csv.reader(text.splitlines()):
  v=[s.strip() for s in row]
  if v and v[0]=='timing':rows.append(dict(mode=v[1],run=int(v[2]),metric=v[3],samples=int(v[4]),mean_ms=float(v[5]),p95_ms=float(v[6]),threshold=float(v[7])))
  if v and v[0]=='distribution':distributions.append(dict(mode=v[1],run=int(v[2]),metric=v[3],samples=int(v[4]),median_ms=float(v[5]),sample_std_ms=float(v[6]),p99_ms=float(v[7]),wall_fps=float(v[8]),wall_1pct_low_fps=float(v[9])))
 samples,repeats=(240,1) if phase=='Smoke' else (4800,4)
 metrics=['SMAA','Spatial','Resolve','WholeFrame','WallFrame']
 expected=[(m,i,k) for i in range(repeats) for m in (MODES if i%2==0 else MODES[::-1]) for k in metrics]
 for data in (rows,distributions):
  assert [(r['mode'],r['run'],r['metric']) for r in data]==expected
  assert all(r['samples']==samples for r in data)
 for r,d in zip(rows,distributions):assert math.isfinite(r['mean_ms']) and r['mean_ms']>0 and d['median_ms']<=r['p95_ms']<=d['p99_ms']
 result=dict(scene=scene,phase=phase,validation='PASS',receipt=receipt,timing_rows=rows,distribution_rows=distributions,means={m:{k:st.mean(r['mean_ms'] for r in rows if r['mode']==m and r['metric']==k) for k in metrics} for m in MODES})
 (OUT/f'{scene}-{phase}.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result['means'],indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);p.add_argument('--phase',choices=['Capture','Smoke','Benchmark'],required=True);a=p.parse_args()
 capture(a.scene) if a.phase=='Capture' else timing(a.scene,a.phase)
