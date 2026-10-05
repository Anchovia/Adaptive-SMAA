"""Three-way 720-frame presentation; stream output with shared GIF palette."""
import argparse,hashlib,json
from fractions import Fraction
from pathlib import Path
import av,numpy as np
from PIL import Image,ImageDraw,ImageFont,GifImagePlugin
from analyze_edge_resolved_rgb_feedback import ROOT,DOC,MODES,load
from edge_quality_inputs import sha
FONT=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
SMALL=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',11)
LABELS=['4 Original SMAA T2X-R','10 Spatial history RGB','11 Resolved RGB feedback']
DETAIL=['Spatial ON / Full T / Pattern ON','Spatial ON / Edge T / Pattern OFF','Spatial ON / Edge T / Pattern OFF']
FRAME_COUNT=720
ROIS={'bistro':[('chairs','의자·테이블의 얇은 선',(1230,546,1358,706)),('windows','창살과 반복 경계',(950,460,1110,588))],
      'minecraft':[('seams','벽 이음선과 가는 경계',(932,512,1060,672)),('leaves','식생의 촘촘한 무늬',(1420,590,1580,718))]}
def compose(images,f,box=None):
 w,h=(640,354) if box is None else ((box[2]-box[0])*2,(box[3]-box[1])*2)
 size=(3*(w+8)+8,h+72);size=(size[0]+size[0]%2,size[1]+size[1]%2)
 canvas=Image.new('RGB',size,(18,20,23));d=ImageDraw.Draw(canvas)
 phase='initial still' if f<60 else ('moving' if f<=FRAME_COUNT-60 else 'final still')
 for i,image in enumerate(images):
  x=8+i*(w+8)
  d.text((x,6),LABELS[i],font=FONT,fill='white')
  d.text((x,24),DETAIL[i] if box is None else DETAIL[i].replace('Spatial ON / ','S ON / '),font=SMALL,fill='#cdd7e1')
  d.text((x,40),f'f{f:03d} / {phase}',font=SMALL,fill='#cdd7e1')
  tile=image.resize((w,h),Image.Resampling.LANCZOS) if box is None else image.crop(box).resize((w,h),Image.Resampling.NEAREST)
  canvas.paste(tile,(x,60))
 return canvas
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
   assert len(pts) in [240,720] and s.average_rate==60 and all(b>a for a,b in zip(pts,pts[1:]))
  return dict(path=str(self.path),sha256=sha(self.path),frames=len(pts),fps=60,duration_seconds=len(pts)/60,monotonic_pts=True,codec='H264 CRF12 yuv420p; lossy presentation')
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
   assert im.n_frames==len(self.hashes) and im.n_frames in [240,720]
   for f in range(im.n_frames):
    im.seek(f);total+=im.info['duration'];assert hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()==self.hashes[f]
  assert total==len(self.hashes)*40
  return dict(path=str(self.path),sha256=sha(self.path),frames=len(self.hashes),fps=25,duration_seconds=total/1000,playback_speed=25/60,fixed_palette=True,dither=False,decoded_frames_verified=True,codec='shared 256-color palette; lossy presentation')

def make(scene,out,frames):
 evidence=DOC/f'{scene}-long-capture.json' if frames==720 else DOC/f'{scene}-capture.json'
 receipt=load(evidence);assert receipt['validation']=='PASS'
 assert (receipt['control_rgb_mismatch'] if frames==720 else receipt['control_bridge']['rgb_mismatch'])==0
 hashes=receipt['rgb_hashes'] if frames==720 else receipt['output_hashes']
 capture=Path(receipt['capture_root'])
 def images(f):
  ims=[]
  for mode in MODES:
   with Image.open(capture/mode/f'frame_{f:05d}.png') as source:
    im=source.convert('RGB');assert hashlib.sha256(im.tobytes()).hexdigest()==hashes[mode][f]
    ims.append(im)
  return ims
 specs=ROIS[scene];samples={name:[] for name,_,_ in specs}
 for f in sorted(set([0,60,130,180,frames-1]+list(range(240,frames,60)))):
  ims=images(f)
  for name,_,box in specs:samples[name].append(compose(ims,f,box).resize((400,220)))
 palettes={}
 for name,tiles in samples.items():
  atlas=Image.new('RGB',(400,220*len(tiles)))
  for i,im in enumerate(tiles):atlas.paste(im,(0,i*220))
  palettes[name]=atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
 first=images(0);full=Video(out/f'{scene}-full-60fps.mp4',compose(first,0).size)
 writers={name:(Video(out/f'{scene}-{name}-60fps.mp4',compose(first,0,box).size),Gif(out/f'{scene}-{name}-slow.gif',palettes[name])) for name,_,box in specs}
 for f in range(frames):
  ims=first if f==0 else images(f);full.write(compose(ims,f),f)
  for name,_,box in specs:
   view=compose(ims,f,box);video,gif=writers[name];video.write(view,f);gif.write(view,f)
   if f in [130,180,195,360,480,660,700,frames-1]:view.save(out/f'{scene}-{name}-f{f:03d}.png')
  if f%180==0:print(scene,'media',f,'/',frames,flush=True)
 result=dict(scene=scene,mode_order=MODES,capture_evidence_sha256=sha(evidence),frames=frames,full_video=full.close(),rois=[])
 for name,title,box in specs:
  video,gif=writers[name];result['rois'].append(dict(name=name,title=title,roi=box,scale=2,filter='nearest',video=video.close(),gif=gif.close()))
 # Lossless consecutive frames supplement the lossy playback formats.
 result['inspection_sheets']=[]
 for name,_,box in specs:
  for phase,start in ([('moving',130),('late-moving',480),('transition',658),('still',700)] if frames==720 else [('moving',130),('transition',178),('still',190)]):
   for pair in range(3):
    fs=[start+pair*2,start+pair*2+1];views=[compose(images(f),f,box) for f in fs]
    sheet=Image.new('RGB',(views[0].width,views[0].height*2),(18,20,23))
    for row,view in enumerate(views):sheet.paste(view,(0,row*view.height))
    path=out/f'{scene}-{name}-{phase}-pair{pair}.png';sheet.save(path)
    result['inspection_sheets'].append(dict(path=str(path),frames=fs,roi=box,scale=2,filter='nearest',tone_adjustment=False))
 (DOC/f'{scene}-media-{frames}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(scene,f'PASS media; all {frames} frames decoded and checked',flush=True)
 return result

def main():
 global FRAME_COUNT
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--frames',type=int,choices=[240,720],default=720)
 args=parser.parse_args();frames=args.frames;FRAME_COUNT=frames
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);results=[]
 for scene in ROIS:
  result=make(scene,out,frames);results.append(result)
 sections=[]
 for r in results:
  section=f'<section><h2>{r["scene"].title()}</h2><h3>전체 경로 · 정상 속도 60fps, {frames/60:g}초</h3><video controls loop muted playsinline preload="metadata" src="{Path(r["full_video"]["path"]).name}"></video>'
  for roi in r['rois']:
   section+=f'<h3>{roi["title"]}</h3><p>원본 픽셀 2배 확대 · 60fps, {frames/60:g}초</p><video controls loop muted playsinline preload="metadata" src="{Path(roi["video"]["path"]).name}"></video><p>느린 GIF · 25fps, {frames*.04:g}초</p><img loading="lazy" src="{Path(roi["gif"]["path"]).name}">'
  section+='</section>';sections.append(section)
 html='<!doctype html><html lang="ko"><meta charset="utf-8"><title>④·⑩·⑪ RGB history 비교</title><style>body{background:#12151a;color:#edf1f7;font:16px sans-serif;margin:32px auto;max-width:1200px;padding:0 20px}video,img{width:100%;height:auto}section{margin:50px 0}a{color:#b5d7ff}</style><h1>④·⑩·⑪ RGB history 비교</h1><p>왼쪽: ④ 원본 SMAA T2X-R. 가운데: ⑩ 직전 spatial history. 오른쪽: ⑪ 직전 temporal 결과 RGB feedback.</p><p>세 구성 모두 원본 spatial SMAA와 camera reprojection을 사용합니다. ④ Pattern On, ⑩·⑪ Off. ⑩·⑪는 현재·직전 raw edge 선택과 같은 0..0.5 history weight를 사용합니다. 변경 변수는 history RGB 저장값 하나입니다.</p>'+f'<p>실제 {frames}프레임: 정지 1초 → 연속 이동 {(frames-120)/60:g}초 → 정지 약 1초. 정상 영상 {frames/60:g}초, 느린 GIF {frames*.04:g}초. 영상·GIF는 손실이 있는 확인용입니다. 동일 원본 PNG와 연속 프레임으로 품질을 검사합니다.</p>'+''.join(sections)+'</html>'
 (out/'comparison.html').write_text(html,encoding='utf-8')
 (out/'manifest.json').write_text(json.dumps(dict(classification='presentation only; no interpolation or duplicated source frames',source_frames=[0,frames-1],source_fps=60,mode_order=MODES,results=results),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('PASS four GIFs, four crop videos, two overview videos',flush=True)

if __name__=='__main__':main()
