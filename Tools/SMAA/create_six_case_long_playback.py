"""Stream long six-case media; never hold the full RGB sequence in memory."""
import argparse,hashlib,json
from fractions import Fraction
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import av,numpy as np
from PIL import Image,ImageDraw,ImageFont,GifImagePlugin
STATE: Path
OUT: Path
ORDER=['2','3','4','5','9','10']
LABELS={'2':'2 SMAA 1X','3':'3 Full temporal only','4':'4 Original SMAA T2X-R','5':'5 Current edge only','9':'9 Current + previous edge','10':'10 Previous + bilinear RGB'}
DETAIL={'2':'Spatial ON / Temporal OFF / Jitter OFF','3':'Spatial OFF / Temporal ON / Jitter ON','4':'Spatial ON / Temporal ON / Jitter ON','5':'Spatial OFF / Selected temporal / Jitter OFF','9':'Spatial ON / Selected temporal / Jitter OFF','10':'Spatial ON / Selected temporal / Jitter OFF'}
SHORT={'2':'S ON | T OFF | J OFF','3':'S OFF | Full T | J ON','4':'S ON | Full T | J ON','5':'S OFF | Edge T | J OFF','9':'S ON | Edge T | J OFF','10':'S ON | Edge T | J OFF'}
FONT=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
SMALL=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',11)
POOL=ThreadPoolExecutor(max_workers=4)
ROIS={
 ('bistro',2):[('chairs','의자·테이블의 가는 선',(1230,546,1358,706)),('windows','창살과 반복 경계',(950,460,1110,588))],
 ('bistro',14):[('flowers','꽃·잎과 가는 구조',(1000,580,1160,708)),('railings','차양·금속 경계',(1200,120,1360,248))],
 ('minecraft',2):[('seams','벽 이음선과 얇은 경계',(932,512,1060,672)),('leaves','식생의 촘촘한 무늬',(1420,590,1580,718))],
 ('minecraft',14):[('blocks','블록 경계·계단',(1250,530,1410,658)),('trees','나뭇잎과 배경 경계',(380,620,540,748))]}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def item(case,scene,start):
 record=next(x for x in json.loads((STATE/f'case{case}-validated.json').read_text(encoding='utf-8-sig')) if x['scene']==scene and x['start_time']==start)
 assert record['validation']=='PASS' and record['frames']==720 and record['fps']==60
 return record
def paths(scene,start):
 sources={};receipts={}
 for case in ['2','3','5']:
  r=item(case,scene,start);mode=next(m for m in r['modes'] if m!='O-T2X-R')
  sources[case]=Path(r['capture_root'])/mode;receipts[case]=dict(receipt=r,mode=mode)
 r=item('10',scene,start)
 for case,mode in [('4','O-T2X-R'),('9','O-ET2X-R-PreviousRawEdge-Point'),('10','ABL-ET2X-R-PreviousRawEdge-BilinearRGB')]:
  sources[case]=Path(r['capture_root'])/mode;receipts[case]=dict(receipt=r,mode=mode)
 return sources,receipts
def compose(images,f,box=None):
 w,h=(640,354) if box is None else ((box[2]-box[0])*2,(box[3]-box[1])*2)
 size=(3*(w+8)+8,2*(h+64)+8);size=(size[0]+size[0]%2,size[1]+size[1]%2)
 canvas=Image.new('RGB',size,(18,20,23));d=ImageDraw.Draw(canvas)
 for i,case in enumerate(ORDER):
  x=8+(i%3)*(w+8);y=8+(i//3)*(h+64)
  d.text((x,y),LABELS[case],font=FONT,fill='white')
  d.text((x,y+18),DETAIL[case] if box is None else SHORT[case],font=SMALL,fill=(205,215,225))
  phase='initial still' if f<60 else ('moving' if f<=660 else 'final still')
  d.text((x,y+34),f'f{f:03d} / {phase}',font=SMALL,fill=(205,215,225))
  im=images[case].resize((w,h),Image.Resampling.LANCZOS) if box is None else images[case].crop(box).resize((w,h),Image.Resampling.NEAREST)
  canvas.paste(im,(x,y+52))
 return canvas
def originals(sources,f):
 def read(pair):
  c,p=pair
  with Image.open(p/f'frame_{f:05d}.png') as im:return c,im.convert('RGB')
 return dict(POOL.map(read,sources.items()))
class Video:
 def __init__(self,path,size):
  self.path=path;self.out=av.open(str(path),'w');self.s=self.out.add_stream('libx264',rate=60)
  self.s.width=size[0];self.s.height=size[1];self.s.pix_fmt='yuv420p';self.s.options={'crf':'12','preset':'fast','threads':'2'}
 def write(self,im,f):
  v=av.VideoFrame.from_ndarray(np.asarray(im),format='rgb24');v.pts=f;v.time_base=Fraction(1,60)
  for p in self.s.encode(v):self.out.mux(p)
 def close(self):
  for p in self.s.encode():self.out.mux(p)
  self.out.close()
  with av.open(str(self.path)) as out:
   s=out.streams.video[0];pts=[float(f.pts*f.time_base) for f in out.decode(s)]
   assert len(pts)==720 and s.average_rate==60 and all(b>a for a,b in zip(pts,pts[1:]))
  return dict(path=str(self.path),sha256=sha(self.path),frames=720,fps=60,duration_seconds=12,monotonic_pts=True,codec='H264 CRF12 yuv420p; lossy presentation')
class Gif:
 def __init__(self,path,palette):self.path=path;self.palette=palette;self.out=path.open('wb');self.hashes=[]
 def write(self,im,f):
  im=im.quantize(palette=self.palette,dither=Image.Dither.NONE)
  if f==0:
   header,_=GifImagePlugin.getheader(im,info={'loop':0,'optimize':False})
   for b in header:self.out.write(b)
  for b in GifImagePlugin.getdata(im,duration=40,disposal=2,include_color_table=False):self.out.write(b)
  self.hashes.append(hashlib.sha256(im.convert('RGB').tobytes()).hexdigest())
 def close(self):
  self.out.write(b';');self.out.close();total=0
  with Image.open(self.path) as im:
   assert im.n_frames==720
   for f in range(im.n_frames):
    im.seek(f);total+=im.info['duration'];assert hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()==self.hashes[f]
  assert total==28800
  return dict(path=str(self.path),sha256=sha(self.path),frames=720,fps=25,duration_seconds=28.8,playback_speed=25/60,fixed_palette=True,dither=False,decoded_frames_verified=True,codec='shared 256-color palette; lossy presentation')
def make(scene,start):
 sources,receipts=paths(scene,start);stem=f'{scene}-path{start}';specs=ROIS[scene,start]
 palette_samples={name:[] for name,_,_ in specs}
 for f in [0,60,130,180,240,300,360,420,480,540,600,660,719]:
  ims=originals(sources,f)
  for name,_,box in specs:palette_samples[name].append(compose(ims,f,box).resize((400,300)))
 palettes={}
 for name,samples in palette_samples.items():
  atlas=Image.new('RGB',(400,300*len(samples)))
  for i,im in enumerate(samples):atlas.paste(im,(0,i*300))
  palettes[name]=atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
 first=originals(sources,0);full=Video(OUT/f'{stem}-full-60fps.mp4',compose(first,0).size)
 writers={name:(Video(OUT/f'{stem}-{name}-60fps.mp4',compose(first,0,box).size),Gif(OUT/f'{stem}-{name}-slow.gif',palettes[name])) for name,_,box in specs}
 for f in range(720):
  ims=first if f==0 else originals(sources,f)
  full.write(compose(ims,f),f)
  for name,_,box in specs:
   view=compose(ims,f,box);video,gif=writers[name];video.write(view,f);gif.write(view,f)
   if f in [0,130,360,480,660,670,719]:view.save(OUT/f'{stem}-{name}-f{f:03d}.png')
  if f%180==0:print('MEDIA',stem,f,'/720',flush=True)
 result=dict(scene=scene,start_time=start,mode_order=ORDER,sources={c:str(p) for c,p in sources.items()},source_receipts={c:dict(mode=v['mode'],branch=v['receipt']['branch'],commit=v['receipt']['commit'],executable_sha256=v['receipt']['executable_sha256'],report=v['receipt']['report'],report_sha256=v['receipt']['report_sha256'],validation=v['receipt']['validation']) for c,v in receipts.items()},full_video=full.close(),rois=[])
 for name,title,box in specs:
  video,gif=writers[name];result['rois'].append(dict(name=name,title=title,box=box,scale=2,resize='nearest',video=video.close(),gif=gif.close()))
 # Lossless six-frame sheets supplement the lossy playback files.
 result['inspection_sheets']=[]
 for name,title,box in specs:
  for phase,frames in [('moving',range(130,136)),('late-moving',range(480,486)),('transition',range(658,664)),('still',range(700,706))]:
   views=[compose(originals(sources,f),f,box) for f in frames]
   sheet=Image.new('RGB',(views[0].width,views[0].height*6),(18,20,23))
   for i,v in enumerate(views):sheet.paste(v,(0,i*v.height))
   path=OUT/f'{stem}-{name}-{phase}-six-frames.png';sheet.save(path)
   result['inspection_sheets'].append(dict(path=str(path),roi=box,frames=list(frames),scale=2,filter='nearest'))
 (STATE/f'{stem}-media.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 print('PASS MEDIA',stem,flush=True);return result
def main():
 global STATE,OUT
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--state',type=Path,required=True,help='Directory containing verified case2/3/5/10 capture receipts')
 parser.add_argument('--output',type=Path,required=True,help='Separate local presentation output directory')
 args=parser.parse_args();STATE=args.state.resolve();OUT=args.output.resolve()
 OUT.mkdir(parents=True,exist_ok=True);results=[]
 for scene,start in ROIS:
  receipt=STATE/f'{scene}-path{start}-media.json'
  if receipt.exists():
   result=json.loads(receipt.read_text(encoding='utf-8-sig'))
   media=[result['full_video']]+[r[k] for r in result['rois'] for k in ['video','gif']]
   assert all(Path(m['path']).exists() and sha(m['path'])==m['sha256'] for m in media), 'Existing media receipt mismatch'
  else:result=make(scene,start)
  results.append(result)
 manifest=dict(mode_order=ORDER,source_fps=60,source_frames=[0,719],source_duration_seconds=12,slow_gif_duration_seconds=28.8,timeline={'initial_still':[0,59],'moving':[60,660],'final_still':[661,719]},classification='New actual extended camera captures; no frame repetition or interpolated motion; presentation only',results=results)
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 sections=[]
 for r in results:
  heading=('Bistro' if r['scene']=='bistro' else 'Minecraft')+f' · 카메라 구간 {r["start_time"]}–{r["start_time"]+10}초'
  section=f'<section><h2>{heading}</h2><h3>전체 화면 · 60fps · 12초</h3><video controls loop muted playsinline preload="metadata" src="{Path(r["full_video"]["path"]).name}"></video>'
  for roi in r['rois']:
   section+=f'<h3>{roi["title"]}</h3><p>원본 픽셀 2배 확대 · 정상 속도 60fps, 12초</p><video controls loop muted playsinline preload="metadata" src="{Path(roi["video"]["path"]).name}"></video><p>느린 GIF · 25fps, 28.8초 · 0.417배속</p><img loading="lazy" src="{Path(roi["gif"]["path"]).name}">'
  sections.append(section+'</section>')
 html='<!doctype html><html lang="ko"><meta charset="utf-8"><title>SMAA ②·③·④·⑤·⑨·⑩ 긴 비교</title><style>body{background:#12151a;color:#edf1f7;font:16px sans-serif;margin:32px auto;max-width:1100px;padding:0 20px}video,img{width:100%;height:auto}section{margin:50px 0}table{border-collapse:collapse}td,th{padding:8px 16px;border:1px solid #48515e}a{color:#b5d7ff}</style><h1>②·③·④·⑤·⑨·⑩ 긴 비교</h1><p>배치: 위쪽 ②·③·④, 아래쪽 ⑤·⑨·⑩. 모두 같은 프레임·카메라 시점입니다.</p><p>② 공간 SMAA만 / ③ 전체 화면 temporal만 / ④ 원본 SMAA T2X-R / ⑤ 현재 edge temporal만 / ⑨ SMAA + 현재·직전 edge / ⑩ ⑨ + history RGB bilinear.</p><p>③·④ 지터 On, ②·⑤·⑨·⑩ Off. 각 원본 720프레임: 시작 정지 1초 → 이동 10초 → 이동 후 정지 약 1초. 정상 영상 12초, GIF 28.8초. GIF와 MP4는 손실이 있는 확인용 자료이며 원본 PNG로 검증했습니다.</p>'+''.join(sections)+'</html>'
 (OUT/'comparison.html').write_text(html,encoding='utf8')
 print('PASS all 8 GIFs, 8 ROI videos and 4 overview videos',flush=True)
if __name__=='__main__':main()
