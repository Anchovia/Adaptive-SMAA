"""Full timeline quality gate for fixed actual first-edge selective T2X-R."""
import argparse,csv,hashlib,json,math,statistics as st
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from analyze_temporal_contrast_reference import rgb,luma,edge,sha,blur,ssim
from create_temporal_contrast_playback import encode,gif
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Docs/Temporal-First-Edge-Quality'
BENCH=ROOT/'Projects/CMAA2/AutoBench'
NATIVE='O-T2X-R';SELECT='ABL-FirstEdge-Reuse-R';SPATIAL='DBG-CurrentSpatial-R';RAW='DBG-RawEdge';REPEAT=SELECT+'-Repeat'
MODES=[NATIVE,SELECT,SPATIAL]
WINDOWS={'initial_still':(20,60),'moving':(60,180),'transition':(160,220),'late_still':(200,240)}
def main():
 p=argparse.ArgumentParser();p.add_argument('--scene',choices=['bistro','minecraft'],required=True);p.add_argument('--receipt',type=Path,default=ROOT/'tmp/temporal-first-edge-quality-runs.json');a=p.parse_args()
 rs=json.loads(a.receipt.read_text(encoding='utf-8-sig'));rec=[r for r in rs if r['scene']==a.scene and r['phase']=='Capture'];assert len(rec)==1
 rec=rec[0];report=Path(rec['report']);assert sha(report)==rec['report_sha256'].lower();cap=report.parent;t=report.read_text(encoding='utf-8-sig')
 for token in ['Aggregate: PASS','First-edge continuous quality gate:','1920 x 1061',f'Scene: {a.scene}']:assert token in t,token
 assert 'Aggregate: FAIL' not in t
 checks=[[v.strip() for v in r] for r in csv.reader(t.splitlines()) if r and r[0].strip()=='pattern_check'];assert len(checks)==1200
 expected=[f'frame_{i:05d}.png' for i in range(240)]
 for mode in MODES+[RAW,REPEAT]:
  assert [x.name for x in sorted((cap/mode).glob('*.png'))]==expected
  group=[r for r in checks if r[1]==mode];assert [int(r[2]) for r in group]==list(range(240)) and all(r[3:5]==['On','PASS'] for r in group)
 qpath=BENCH/'ContrastReferenceAnalysis'/a.scene/'reference-quality.json';q=json.loads(qpath.read_text());reference=Path(q['quality_capture'])/'SS-Reference';old=Path(q['capture'])
 rr=list(reference.parent.glob('*_results.csv'));assert len(rr)==1 and sha(rr[0])==q['quality_report_sha256']
 assert [x.name for x in sorted(reference.glob('*.png'))]==expected
 prior=json.loads((ROOT/f'Docs/Temporal-First-Edge-Selective/{a.scene}-capture.json').read_text());prior_report=Path(prior['receipt']['report']);assert sha(prior_report)==prior['receipt']['report_sha256'].lower()
 for f in expected:
  assert sha(cap/NATIVE/f)==sha(reference.parent/NATIVE/f)==sha(old/NATIVE/f),('native bridge',f)
  assert sha(cap/SPATIAL/f)==sha(old/SPATIAL/f),('spatial bridge',f)
  assert sha(cap/SELECT/f)==sha(cap/REPEAT/f),('repeat',f)
 for f in [f'frame_{i:05d}.png' for i in [0,1,60,61,140,179,180,200,201,239]]:
  assert sha(cap/SELECT/f)==sha(prior_report.parent/SELECT/f),('timed shader output bridge',f)
  assert sha(cap/RAW/f)==sha(prior_report.parent/RAW/f),('raw edge bridge',f)
 print(a.scene+': full native/spatial/repeat bridges and 20 sparse prior bridges PASS',flush=True)
 out=BENCH/'FirstEdgeQuality'/a.scene;out.mkdir(parents=True,exist_ok=True);DOC.mkdir(exist_ok=True)
 rows=[];coverage=[];prev={};prev_ref=None;prev_mask=None;hashes={m:[] for m in MODES};groups=[];refhash=hashlib.sha256()
 for i,f in enumerate(expected):
  ref=rgb(reference/f);refhash.update(ref.tobytes());ry=luma(ref);re=edge(ry)
  ims={m:rgb(cap/m/f) for m in MODES};raw=rgb(cap/RAW/f)
  assert np.all((raw==0)|(raw==255)) and not np.any(raw[:,:,2])
  mask=np.any(raw[:,:,:2]>0,axis=2);target=np.where(mask[:,:,None],ims[NATIVE],ims[SPATIAL]);assert np.array_equal(ims[SELECT],target),(a.scene,i,'selection semantics')
  coverage.append(dict(frame=i,selected_pixels=int(mask.sum()),selected_percent=float(mask.mean()*100),mask_switch_percent=float(np.mean(mask!=prev_mask)*100) if prev_mask is not None else None))
  do_ssim=i%10==0
  if do_ssim:mb=blur(ry);vb=blur(ry*ry)-mb*mb
  for m,im in ims.items():
   y=luma(im);diff=im.astype(np.float32)-ref.astype(np.float32);mse=float(np.square(diff).mean(dtype=np.float64));hashes[m].append(hashlib.sha256(im.tobytes()).hexdigest())
   step=np.abs(im.astype(np.int16)-prev[m][0].astype(np.int16)) if m in prev else None
   rows.append(dict(frame=i,mode=m,rgb_mae=float(np.abs(diff).mean(dtype=np.float64)),psnr_db=10*math.log10(255**2/mse) if mse else None,edge_reference_ratio=edge(y)/re,luma_ssim=ssim(y,ry,mb,vb) if do_ssim else None,rgb_step=float(step.mean()) if step is not None else None,changed_pixels_percent=float(np.any(step>0,axis=2).mean()*100) if step is not None else None,reference_delta_residual=float(np.abs((y-prev[m][1])-(ry-prev_ref)).mean(dtype=np.float64)) if m in prev else None))
   if m==SELECT and 201<=i<240:
    for name,g in [('always_selected',mask&prev_mask),('always_unselected',~mask&~prev_mask),('selection_switches',mask!=prev_mask)]:
     count=int(g.sum());groups.append(dict(frame=i,group=name,area_percent=100*count/mask.size,mean_rgb_step=float(step[g].mean()) if count else 0,whole_frame_step_contribution=float(step[g].sum(dtype=np.float64)/(mask.size*3))))
   prev[m]=(im,y)
  prev_ref=ry;prev_mask=mask
  if i%40==39:print(f'{a.scene}: {i+1}/240 quality frames PASS',flush=True)
 result=dict(scene=a.scene,receipt=rec,validation='PASS',shader_fixed_at='be93be3',capture=str(cap),reference=str(reference),reference_analysis_sha256=sha(qpath),reference_report_sha256=sha(rr[0]),reference_pixel_stream_sha256=refhash.hexdigest(),classification='Camera-path engineering quality; supersampling spatial proxy, not temporal ground truth',full_bridge_comparisons=960,sparse_bridge_comparisons=20,selection_semantics_frames=240,selection_mismatches=0,pattern_checks=1200,windows={},coverage={},static_hashes={},late_still_groups={})
 for name,(start,end) in WINDOWS.items():
  result['windows'][name]={}
  for m in MODES:
   sub=[r for r in rows if r['mode']==m and start<=r['frame']<end]
   result['windows'][name][m]={k:st.mean(r[k] for r in sub if r[k] is not None) for k in sub[0] if k not in ['frame','mode']}
  sub=[r for r in coverage if start<=r['frame']<end];result['coverage'][name]={k:st.mean(r[k] for r in sub if r[k] is not None) for k in sub[0] if k!='frame'}
  if 'still' in name:result['static_hashes'][name]={m:dict(unique_rgb_frames=len(set(h[start:end])),lag2_mismatches=sum(h[j]!=h[j-2] for j in range(start+2,end))) for m,h in hashes.items()}
 for g in ['always_selected','always_unselected','selection_switches']:
  sub=[r for r in groups if r['group']==g];result['late_still_groups'][g]={k:st.mean(r[k] for r in sub) for k in ['area_percent','mean_rgb_step','whole_frame_step_contribution']}
 for name,data in [('per-frame-quality.csv',rows),('per-frame-coverage.csv',coverage),('late-still-groups.csv',groups)]:
  with (out/name).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=data[0]);w.writeheader();w.writerows(data)
 # Save compact measured CSVs, not raw frames, with the report.
 for name in ['per-frame-quality.csv','per-frame-coverage.csv','late-still-groups.csv']:(DOC/f'{a.scene}-{name}').write_bytes((out/name).read_bytes())
 roi=(420,590,900,910) if a.scene=='bistro' else (720,240,1200,560)
 paths=[reference,cap/NATIVE,cap/SELECT];labels=['SS spatial reference','Original T2X-R','First-edge selective T2X-R']
 def render(i,crop=False,slow=False):
  tw,th=(480,320) if crop else (640,354);canvas=Image.new('RGB',(tw*3,th+30),'#15181c');draw=ImageDraw.Draw(canvas)
  for col,(folder,label) in enumerate(zip(paths,labels)):
   with Image.open(folder/f'frame_{i:05d}.png') as im:tile=im.convert('RGB').crop(roi) if crop else im.convert('RGB').resize((tw,th),Image.Resampling.LANCZOS)
   canvas.paste(tile,(col*tw,30));draw.text((col*tw+4,8),f'{label} | f{i:03d} | '+('0.5x' if slow else '1x'),fill='white')
  return canvas
 detail=lambda i,slow=False:render(i,crop=True,slow=slow)
 result['roi']=roi;result['videos']=[encode(out/'overview-60fps.mp4',render,240),encode(out/'detail-60fps.mp4',detail,240)]
 result['gifs']=[gif(out/f'{name}.gif',detail,start,end) for name,start,end in [('moving',90,150),('transition',160,220),('late-still',200,220)]]
 for name,indices in [('moving',[110,111,112,113]),('stop',[179,180,181,182]),('still',[200,201,202,203])]:
  sheet=Image.new('RGB',(1920,1050),'#15181c')
  for col,i in enumerate(indices):
   tile=detail(i)
   for row in range(3):sheet.paste(tile.crop((row*480,0,(row+1)*480,350)),(col*480,row*350))
  sheet.save(out/f'{name}-sequence.png')
 # Original pixel differences, amplified for visibility, do not use video frames.
 sheet=Image.new('RGB',(1440,350),'#15181c');draw=ImageDraw.Draw(sheet)
 for j,m in enumerate([NATIVE,SELECT,SPATIAL]):
  x=rgb(cap/m/'frame_00200.png');y=rgb(cap/m/'frame_00201.png');delta=np.clip(np.abs(x.astype(np.int16)-y.astype(np.int16))*8,0,255).astype('uint8')
  sheet.paste(Image.fromarray(delta).crop(roi),(j*480,30));draw.text((j*480+4,8),m+' | abs(f201-f200) x8',fill='white')
 sheet.save(out/'still-difference-x8.png')
 result['media_scope']='MP4 CRF12/YUV420 and fixed-palette GIF are viewing aids; PNG metrics use original RGB. Fixed ROI is not object-tracked.'
 (DOC/f'{a.scene}-quality.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(a.scene+': quality + playback frame/FPS/PTS validation PASS',flush=True)
if __name__=='__main__':main()
