"""Lossless consecutive-frame sheets and actual-frame GIF/60Hz MP4 comparisons."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from analyze_edge_validated_rgb_feedback import ROOT,DOC,MODES,CASES,latest,load
from analyze_edge_resolved_rgb_feedback import capture_root,ROIS
from create_resolved_feedback_playback import Video,Gif
from edge_quality_inputs import ph,rgb,sha
FONT=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',13)
KEY=[0,4,5,6];ALL=list(range(8))
def compose(cap,frame,box,indices=KEY,overview=False,images=None):
 w,h=(480,265) if overview else ((box[2]-box[0])*2,(box[3]-box[1])*2)
 cols=4;rows=(len(indices)+cols-1)//cols
 size=(cols*(w+8)+8,rows*(h+50)+8);size=(size[0]+size[0]%2,size[1]+size[1]%2)
 canvas=Image.new('RGB',size,(18,20,23));draw=ImageDraw.Draw(canvas)
 for pos,index in enumerate(indices):
  x=8+(pos%cols)*(w+8);y=8+(pos//cols)*(h+50)
  title=['4 Original','6 Current edge','9 Prev edge','10 Bilinear','11 Resolved','12 Default','12 Response','12 Clip'][index]
  draw.text((x,y),title,font=FONT,fill='white');draw.text((x,y+17),f'f{frame} / J '+('ON' if index==0 else 'OFF'),font=FONT,fill='#cdd7e1')
  if images is None:
   with Image.open(cap/MODES[index]/f'frame_{frame:05d}.png') as im:
    tile=im.resize((w,h),Image.Resampling.LANCZOS) if overview else im.crop(box).resize((w,h),Image.Resampling.NEAREST)
  else:
   im=images[index]
   tile=im.resize((w,h),Image.Resampling.LANCZOS) if overview else im.crop(box).resize((w,h),Image.Resampling.NEAREST)
  canvas.paste(tile,(x,y+40))
 return canvas
def make(scene,out,count):
 receipt=latest(scene,'Capture',count);cap=capture_root(receipt)
 record=load(DOC/f'{scene}-capture.json') if count==240 else None
 hashes={m:[] for m in MODES}
 for f in range(count):
  for mode in MODES:
   value=ph(rgb(cap/mode/f'frame_{f:05d}.png'));hashes[mode].append(value)
   if record:assert value==record['output_hashes'][mode][f]
 if count==720:
  short=load(DOC/f'{scene}-capture.json')
  bridge={m:sum(a!=b for a,b in zip(hashes[m][:180],short['output_hashes'][m][:180])) for m in MODES}
  assert bridge[MODES[0]]==0, 'Native control changed within common poses'
  (DOC/f'{scene}-long-capture.json').write_text(json.dumps(dict(validation='PASS',receipt=receipt,capture_root=str(cap),frames=count,output_hashes=hashes,first_180_short_bridge_mismatched_frames=bridge,classification='actual long presentation timeline; no quantitative reference for later poses'),indent=2)+'\n')
 results=[];writers=[];phaseframes=[('moving',126),('transition',178 if count==240 else 658),('still',190 if count==240 else 700)]
 if count==720:phaseframes.insert(1,('late-moving',480))
 rois=dict(ROIS[scene])
 if count==720:
  rois.update({'windows':(950,460,1110,588)} if scene=='bistro' else {'foliage':(1420,590,1580,718)})
 for name,box in rois.items():
  paths=[]
  for phase,start in phaseframes:
   for pair in range(3):
    fs=[start+2*pair,start+2*pair+1];views=[compose(cap,f,box) for f in fs]
    sheet=Image.new('RGB',(views[0].width,views[0].height*2));sheet.paste(views[0],(0,0));sheet.paste(views[1],(0,views[0].height))
    target=out/f'{scene}-{name}-{phase}-pair{pair}.png';sheet.save(target);paths.append(dict(path=str(target),frames=fs,roi=box,filter='nearest',scale=2,tone_adjustment=False))
  tiles=[compose(cap,f,box).resize((400,180)) for f in sorted(set([0,60,130,180,count-1]+list(range(240,count,60))))]
  atlas=Image.new('RGB',(400,180*len(tiles)))
  for i,t in enumerate(tiles):atlas.paste(t,(0,i*180))
  palette=atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
  first=compose(cap,0,box);vid=Video(out/f'{scene}-{name}-60fps.mp4',first.size);gif=Gif(out/f'{scene}-{name}-slow.gif',palette)
  writers.append((name,box,vid,gif,paths))
 full=Video(out/f'{scene}-all-controls-60fps.mp4',compose(cap,0,None,ALL,True).size)
 for f in range(count):
  ims=[]
  for mode in MODES:
   with Image.open(cap/mode/f'frame_{f:05d}.png') as source:im=source.convert('RGB')
   assert ph(np.asarray(im))==hashes[mode][f]
   ims.append(im)
  full.write(compose(cap,f,None,ALL,True,ims),f)
  for name,box,vid,gif,paths in writers:
   im=compose(cap,f,box,images=ims);vid.write(im,f);gif.write(im,f)
  if f%180==0:print(scene,'media',f,'/',count,flush=True)
 for name,box,vid,gif,paths in writers:
  results.append(dict(roi=name,box=box,mode_indices=KEY,video=vid.close(),gif=gif.close(),sheets=paths))
  print(scene,name,'media complete',flush=True)
 overview=full.close()
 for f in [129,130,180 if count==240 else 660,count-1]:
  compose(cap,f,None,ALL,True).save(out/f'{scene}-all-f{f:05d}.png')
 return dict(scene=scene,frames=count,capture_root=str(cap),receipt=receipt,overview=overview,rois=results,output_hashes=hashes)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--frames',type=int,choices=[240,720],default=240);p.add_argument('--scene',choices=['bistro','minecraft']);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 rr=[make(s,out,a.frames) for s in ([a.scene] if a.scene else ['bistro','minecraft'])]
 if a.scene and (out/'manifest.json').exists():
  old=load(out/'manifest.json');assert old['source_frames']==[0,a.frames-1]
  rr=[r for r in old['results'] if r['scene']!=a.scene]+rr
 html='<!doctype html><html lang="ko"><meta charset="utf-8"><title>SMAA 12 품질 비교</title><style>body{background:#12151a;color:#edf1f7;font:16px sans-serif;max-width:1400px;margin:32px auto;padding:0 20px}video,img{max-width:100%;height:auto}section{margin:48px 0}a{color:#b5d7ff}</style><h1>⑫ history validation·adaptive 누적 비교</h1><p>확대 순서: ④ 원본 T2X-R / ⑪ resolved RGB / ⑫ 공개 기본값 / ⑫ 넓은 반응 범위. 전체 영상에는⑥·⑨·⑩ 및 clipping-only control도 포함합니다. ④ Pattern On, 나머지 Off. 모두 Original spatial SMAA와 camera reprojection을 사용합니다.</p><p>원본 실제 프레임을 사용했습니다. GIF·MP4는 손실이 있는 확인용이고, 판정은 nearest 확대 PNG로 합니다. 선택 마스크 확장은 없습니다.</p>'
 for r in rr:
  html+=f'<section><h2>{r["scene"]}</h2><h3>8개 조건 전체·60fps {a.frames/60:g}초</h3><video controls loop muted src="{Path(r["overview"]["path"]).name}"></video>'
  for q in r['rois']:
   html+=f'<h3>{q["roi"]}</h3><video controls loop muted src="{Path(q["video"]["path"]).name}"></video><p>느린 GIF·25fps {a.frames*.04:g}초</p><img loading="lazy" src="{Path(q["gif"]["path"]).name}">'
   for s in q['sheets']:html+=f'<p><a href="{Path(s["path"]).name}">연속 {s["frames"]} PNG</a></p>'
  html+='</section>'
 (out/'comparison.html').write_text(html,encoding='utf-8');(out/'manifest.json').write_text(json.dumps(dict(validation='PASS',source_fps=60,source_frames=[0,a.frames-1],mode_order=MODES,case_order=CASES,results=rr),indent=2)+'\n')
 print('PASS media decoded/frame counts checked',flush=True)
if __name__=='__main__':main()
