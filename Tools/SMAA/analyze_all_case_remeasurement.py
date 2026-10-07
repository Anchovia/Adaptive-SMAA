"""Fresh paired performance and frame-aligned spatial-reference quality.

RGB/SSIM reference is a spatial supersample proxy, not temporal ground truth.
Motion-compensated ROI residual uses a common temporal-free case2 flow.
"""
import argparse,csv,hashlib,json,math,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
sys.path.append('C:/Users/USER/Desktop/research/.research-tools/quality-venv/Lib/site-packages')
import cv2

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'tmp/all-case-remeasurement'
OUT=ROOT/'Deliverables/SMAA_All_17_Remeasurement_20261007'
ROIS={'bistro':{'thin-chair':(1230,582,1358,670),'windows':(950,460,1110,588)},
 'minecraft':{'thin-seam':(956,524,1020,620),'leaves':(1420,590,1580,718),'grass-seam':(1450,665,1552,719)}}
FONT=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',13)
LUMA=np.array([.2126,.7152,.0722],np.float32)
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def rows(p):return [[value.strip() for value in r] for r in csv.reader(Path(p).read_text(encoding='utf-8-sig').splitlines())]
def rgb(p):
 with Image.open(p) as im:
  assert im.mode=='RGB' and im.size==(1920,1061),(str(p),im.mode,im.size)
  return np.asarray(im).copy()
def pixel_sha(a):return hashlib.sha256(a.tobytes()).hexdigest()
def gray(a):return a.astype(np.float32)@LUMA
def ssim(a,b):
 a=gray(a);b=gray(b)
 blur=lambda x:cv2.GaussianBlur(x,(11,11),1.5)[5:-5,5:-5]
 ma,mb=blur(a),blur(b)
 va,vb=blur(a*a)-ma*ma,blur(b*b)-mb*mb
 cov=blur(a*b)-ma*mb
 return float(np.mean(((2*ma*mb+6.5025)*(2*cov+58.5225))/((ma*ma+mb*mb+6.5025)*(va+vb+58.5225))))
def flow(previous,current):
 pg=cv2.cvtColor(previous,cv2.COLOR_RGB2GRAY);cg=cv2.cvtColor(current,cv2.COLOR_RGB2GRAY)
 kwargs=dict(pyr_scale=.5,levels=3,winsize=15,iterations=3,poly_n=5,poly_sigma=1.2,flags=0)
 f=cv2.calcOpticalFlowFarneback(pg,cg,None,**kwargs);b=cv2.calcOpticalFlowFarneback(cg,pg,None,**kwargs)
 yy,xx=np.mgrid[:cg.shape[0],:cg.shape[1]].astype(np.float32);mx,my=xx+b[:,:,0],yy+b[:,:,1]
 sampled=cv2.remap(f,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
 valid=(mx>=1)&(my>=1)&(mx<=cg.shape[1]-2)&(my<=cg.shape[0]-2)&(np.linalg.norm(b+sampled,axis=2)<=1)
 return mx,my,valid

def performance(plan,runs):
 output=[];detailed=[]
 for scene in ('bistro','minecraft'):
  for item in plan['cases']:
   run=next((r for r in runs if r['case']==item['case'] and r['scene']==scene and r['phase']=='Benchmark'),None)
   if run is None:continue
   stats=defaultdict(dict)
   for r in rows(run['report']):
    if r and r[0]=='timing':
     assert len(r)>=12 and int(r[4])==4800
     stats[(r[1],r[3])][int(r[2])]=float(r[5]);detailed.append(dict(case=item['case'],scene=scene,mode=r[1],metric=r[3],run=int(r[2]),samples=int(r[4]),mean_ms=float(r[5]),p95_ms=float(r[7]),p99_ms=float(r[8]),report=run['report']))
   def metric(name):
    t=stats[(item['target'],name)];c=stats[('O-T2X-R',name)]
    assert t,(item['case'],scene,'Missing timing',name)
    assert sorted(t)==list(range(6)) and sorted(c)==list(range(6)),(item['case'],scene,name,t,c)
    tv=np.array([t[i] for i in range(6)]);cv=np.array([c[i] for i in range(6)])
    ratio=(tv/cv-1)*100
    return dict(ms=float(tv.mean()),paired_control_ms=float(cv.mean()),percent=float((tv.mean()/cv.mean()-1)*100),
        paired_percent_mean=float(ratio.mean()),paired_percent_sd=float(ratio.std(ddof=1)),ci95_half_width=float(2.570582*ratio.std(ddof=1)/math.sqrt(6)),run_mean_sd=float(tv.std(ddof=1)))
   output.append(dict(case=item['case'],scene=scene,label=item['label'],AA=metric('SMAA'),temporal=metric('SR_Resolve') if item['temporal'] else None,camera=metric('SR_CameraVelocity') if item['temporal'] else None,whole_frame=metric('WholeFrame'),source=run['report']))
 dump(OUT/'performance.json',output)
 if detailed:
  with (OUT/'performance-runs.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(detailed[0]));w.writeheader();w.writerows(detailed)
 return output

def capture_paths(plan,runs):
 paths={};native_controls={}
 for scene in ('bistro','minecraft'):
  for item in plan['cases']:
   run=next((r for r in runs if r['case']==item['case'] and r['scene']==scene and r['phase']=='Capture'),None)
   if run is None:continue
   roots=[r[1] for r in rows(run['report']) if r and r[0]=='capture_root'];assert len(roots)==1
   folder=Path(roots[0]);target=folder/item['target'];native=folder/'O-T2X-R'
   assert len(list(target.glob('frame_*.png')))==240,(item['case'],scene,str(target))
   assert len(list(native.glob('frame_*.png')))==240
   paths[(scene,item['case'])]=target;native_controls[(scene,item['case'])]=native
 return paths,native_controls

def quality(plan,runs):
 paths,natives=capture_paths(plan,runs)
 assert len(paths)==34,'All fresh sequences must be complete before quality analysis'
 reference=load(ROOT/'Docs/Baseline-Restart/reused-reference-provenance.json')
 allrows=[];bridges=[];hashes={};roi_frames={};flow_rows=[];flow_controls={}
 for scene in ('bistro','minecraft'):
  for case in range(1,18):roi_frames[(scene,case)]={k:[] for k in ROIS[scene]}
  for key in ROIS[scene]:flow_controls[(scene,key)]=[]
  for f in range(240):
   ref=rgb(Path(reference[scene]['reference'])/f'frame_{f:05d}.png')
   native=rgb(paths[(scene,4)]/f'frame_{f:05d}.png');native_hash=pixel_sha(native)
   for case in range(1,18):
    a=rgb(paths[(scene,case)]/f'frame_{f:05d}.png')
    sha=pixel_sha(a);hashes[f'{scene}/{case}/{f}']=sha
    check=rgb(natives[(scene,case)]/f'frame_{f:05d}.png')
    assert pixel_sha(check)==native_hash,('Native baseline regression',scene,case,f)
    diff=a.astype(np.float32)-ref.astype(np.float32);mse=float(np.mean(diff*diff))
    phase='moving' if 60<=f<180 else 'transition' if 180<=f<210 else 'settled' if f>=220 else 'late-settling' if f>=210 else 'initial'
    allrows.append(dict(scene=scene,case=case,frame=f,phase=phase,reference_mae=float(np.abs(diff).mean()),psnr=99 if mse==0 else 10*math.log10(255**2/mse),luma_ssim=ssim(a,ref),difference_to_native_mae=float(np.abs(a.astype(np.float32)-native).mean())))
    for key,(x0,y0,x1,y1) in ROIS[scene].items():
     roi_frames[(scene,case)][key].append(a[y0:y1,x0:x1].copy())
     if case==2:flow_controls[(scene,key)].append(a[y0-32:y1+32,x0-32:x1+32].copy())
   if f%20==0:print(json.dumps(dict(scene=scene,frame=f,quality='RUNNING')),flush=True)
  bridges.append(dict(scene=scene,native_control_comparisons=17*240,native_hash_mismatch=0))
  for key,box in ROIS[scene].items():
   controls=flow_controls[(scene,key)]
   for f in range(1,240):
    mx,my,valid=flow(controls[f-1],controls[f])
    mx=mx[32:-32,32:-32]-32;my=my[32:-32,32:-32]-32;valid=valid[32:-32,32:-32]
    hh,ww=mx.shape;valid&=(mx>=1)&(my>=1)&(mx<=ww-2)&(my<=hh-2)
    for case in range(1,18):
     prev,cur=roi_frames[(scene,case)][key][f-1:f+1]
     warped=cv2.remap(prev.astype(np.float32),mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
     lum=gray(cur);plum=gray(prev)
     residual=np.abs(lum-gray(warped))
     flow_rows.append(dict(scene=scene,case=case,roi=key,frame=f,phase='moving' if 60<=f<180 else 'transition' if 180<=f<210 else 'settled' if f>=220 else 'late-settling' if f>=210 else 'initial',valid_fraction=float(valid.mean()),aligned_residual=float(residual[valid].mean()) if valid.any() else None,raw_temporal_mae=float(np.abs(lum-plum).mean()),edge_strength=float(np.abs(np.diff(lum,axis=1)).mean()+np.abs(np.diff(lum,axis=0)).mean())))
  print(json.dumps(dict(scene=scene,quality='PASS',native_bridge='PASS')),flush=True)
 with (OUT/'quality-per-frame.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
 with (OUT/'roi-temporal-diagnostics.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(flow_rows[0]));w.writeheader();w.writerows(flow_rows)
 summary=[]
 for scene in ('bistro','minecraft'):
  for case in range(1,18):
   out=dict(scene=scene,case=case)
   for phase in ('moving','transition','settled'):
    sel=[r for r in allrows if r['scene']==scene and r['case']==case and r['phase']==phase]
    out[phase]={k:float(np.mean([r[k] for r in sel])) for k in ('reference_mae','psnr','luma_ssim','difference_to_native_mae')}
   stable=[hashes[f'{scene}/{case}/{f}'] for f in range(220,240)];out['settled_distinct_frame_hashes']=len(set(stable))
   summary.append(out)
 dump(OUT/'quality.json',summary);dump(OUT/'native-baseline-bridge.json',bridges);dump(OUT/'output-pixel-hashes.json',hashes)
 sheets(paths,roi_frames)

def sheets(paths,roi_frames):
 gallery=OUT/'frames';gallery.mkdir(exist_ok=True)
 for scene in ('bistro','minecraft'):
  # Every target: original pixels, six moving + six transition frames, all ROIs.
  for case in range(1,18):
   if case==4:continue
   panels=[]
   for key in ROIS[scene]:
    crops=roi_frames[(scene,case)][key];controls=roi_frames[(scene,4)][key]
    h,w=crops[0].shape[:2];scale=2
    sheet=Image.new('RGB',(w*4+24,(h*2+26)*12+35),(24,24,24));d=ImageDraw.Draw(sheet)
    d.text((8,8),f'{scene} {key} 4 vs {case}; nearest 2x; moving / stop',font=FONT)
    for row,f in enumerate(list(range(126,132))+list(range(178,184))):
     y=35+row*(h*2+26);d.text((8,y),f'frame {f}: 4 left, {case} right',font=FONT)
     for col,a in enumerate((controls[f],crops[f])):sheet.paste(Image.fromarray(a).resize((w*2,h*2),Image.Resampling.NEAREST),(8+col*(w*2+8),y+22))
    name=f'{scene}-{key}-4-vs-{case}.png';sheet.save(gallery/name)
    # Pair GIF for motion and stop; originals, labels, no color adjustment.
    frames=[]
    for f in range(60,210,2):
     im=Image.new('RGB',(w*4+24,h*2+32),(24,24,24));dd=ImageDraw.Draw(im);dd.text((8,6),f'4 | {case}; f{f}; 60fps timeline, stride2 / 30fps',font=FONT)
     for col,a in enumerate((controls[f],crops[f])):im.paste(Image.fromarray(a).resize((w*2,h*2),Image.Resampling.NEAREST),(8+col*(w*2+8),28))
     frames.append(im)
    delays=[30 if i%3!=1 else 40 for i in range(len(frames))]
    frames[0].save(gallery/f'{scene}-{key}-4-vs-{case}.gif',save_all=True,append_images=frames[1:],duration=delays,loop=0,optimize=False)
   for f in (130,181,230):
    a=rgb(paths[(scene,4)]/f'frame_{f:05d}.png');b=rgb(paths[(scene,case)]/f'frame_{f:05d}.png')
    im=Image.new('RGB',(3840,1093),(24,24,24));d=ImageDraw.Draw(im);d.text((8,6),f'{scene} f{f}: original 4 left, case{case} right, 1x',font=FONT)
    im.paste(Image.fromarray(a),(0,32));im.paste(Image.fromarray(b),(1920,32));im.save(gallery/f'{scene}-full-f{f}-4-vs-{case}.png')
 print('PAIR SHEETS AND GIFS COMPLETE',flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--performance-only',action='store_true');args=p.parse_args()
 OUT.mkdir(parents=True,exist_ok=True);plan=load(BUILD/'manifest.json');runs=load(BUILD/'runs.json')
 performance(plan,runs)
 if not args.performance_only:quality(plan,runs)
if __name__=='__main__':main()
