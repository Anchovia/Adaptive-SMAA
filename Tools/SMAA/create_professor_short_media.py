import hashlib,json,sys
from fractions import Fraction
from pathlib import Path
import av
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageSequence

ROOT=Path(__file__).resolve().parents[2]
OUT=Path('C:/Users/USER/Desktop/research/Deliverables/TSCMAA_Professor_20261001')
MEDIA=OUT/'media';MEDIA.mkdir(parents=True,exist_ok=True)
DATA=json.loads((ROOT/'tmp/professor-sources.json').read_text(encoding='utf-8'))
FONT=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',16)
SMALL=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',13)
BG='#111518'
LABELS=['① AA-Off','② SMAA 1X','③ Temporal-only','④ 원본 SMAA T2X-R','⑤ Edge temporal-only','⑥ SMAA + 현재 edge','⑦ 직전 edge · 개선 전','⑧ 직전 edge · 개선 후']
ROIS=[('minecraft','minecraft-line','Minecraft 얇은 선',(956,524,1020,620),2),
 ('bistro','bistro-chairs','Bistro 의자 다리',(1230,582,1358,670),2),
 ('bistro','bistro-window','Bistro 창문',(906,470,1034,558),2),
 ('bistro','bistro-balcony','Bistro 발코니 난간',(930,152,1122,264),1),
 ('minecraft','minecraft-foliage','Minecraft 나뭇잎',(1344,712,1536,824),1)]

def compose(tiles,title,index,scale,speed,subset=None):
 cases=list(range(1,9)) if subset is None else subset
 w=max(224,tiles[cases[0]].width*scale);h=tiles[cases[0]].height*scale
 rows=(len(cases)+3)//4;size=(4*w+50,54+rows*(h+56))
 im=Image.new('RGB',(size[0]+size[0]%2,size[1]+size[1]%2),BG);d=ImageDraw.Draw(im)
 phase='이동' if 60<=index<180 else '정지'
 d.text((10,4),f'{title} | f{index:03d} · {phase} | {speed}',font=FONT,fill='white')
 d.text((10,28),'③④ Pattern On / 나머지 Off · 화면 고정 ROI · 원본 색 · nearest 확대',font=SMALL,fill='#c4cbd1')
 for k,c in enumerate(cases):
  x=10+(k%4)*(w+10);y=54+(k//4)*(h+56)
  d.text((x,y),LABELS[c-1],font=FONT,fill='white')
  d.text((x,y+23),('spatial On' if c in (2,4,6,7,8) else 'spatial Off'),font=SMALL,fill='#c4cbd1')
  tile=tiles[c].resize((tiles[c].width*scale,h),Image.Resampling.NEAREST)
  im.paste(tile,(x+(w-tile.width)//2,y+48))
 return im

def encode_mp4(path,render,n):
 first=render(0)
 with av.open(str(path),'w',format='mp4') as out:
  stream=out.add_stream('libx264',rate=60);stream.width=first.width;stream.height=first.height
  stream.pix_fmt='yuv420p';stream.options={'crf':'12','preset':'fast'};stream.time_base=Fraction(1,60)
  for i in range(n):
   f=av.VideoFrame.from_ndarray(np.asarray(render(i)),format='rgb24');f.pts=i;f.time_base=Fraction(1,60)
   for p in stream.encode(f):out.mux(p)
  for p in stream.encode():out.mux(p)
 with av.open(str(path)) as inp:
  s=inp.streams.video[0];assert s.average_rate==60
  stamps=[f.pts*s.time_base for f in inp.decode(video=0)]
  assert len(stamps)==n and all(b-a==Fraction(1,60) for a,b in zip(stamps,stamps[1:]))
 return dict(file=path.name,frames=n,fps=60,duration_seconds=n/60,pts_verified=True)

def gif_pair(stem,render,n,slow_ms=100):
 # Keep every original temporal phase in both GIFs. Same pixels/palette, only durations differ.
 frames=[render(i) for i in range(n)]
 atlas=Image.new('RGB',(frames[0].width,frames[0].height*n))
 for i,f in enumerate(frames):atlas.paste(f,(0,i*f.height))
 palette=atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
 indexed=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
 del atlas,frames
 result={}
 for speed,durations in [('slow',[slow_ms]*n),('fast',[20]*n)]:
  p=MEDIA/f'{stem}-{speed}.gif'
  indexed[0].save(p,save_all=True,append_images=indexed[1:],duration=durations,loop=0,disposal=1,optimize=False)
  with Image.open(p) as dec:
   assert dec.n_frames==n
   for i,f in enumerate(ImageSequence.Iterator(dec)):
    assert f.info['duration']==durations[i]
    assert np.array_equal(np.asarray(f.convert('RGB')),np.asarray(indexed[i].convert('RGB')))
  result[speed]=dict(file=p.name,frames=n,seconds=sum(durations)/1000,playback_speed=(n/60)/(sum(durations)/1000),fixed_palette=True,dither=False,decode_verified=True,bytes=p.stat().st_size)
 return result

def main():
 crops={};sources={}
 for scene in ('bistro','minecraft'):
  for case in range(1,9):
   c=DATA['short_captures'][str(case)][scene];cap=Path(c['capture_root'])/c['mode']
   for i in range(240):
    with Image.open(cap/f'frame_{i:05d}.png') as im:
     rgb=im.convert('RGB');assert rgb.size==(1920,1061)
     assert hashlib.sha256(rgb.tobytes()).hexdigest()==c['hashes'][i]
     for s,name,title,roi,scale in ROIS:
      if s==scene:crops[name,case,i]=rgb.crop(roi)
   sources[f'{case}-{scene}']=dict(root=str(cap),verified_frames=240,commit=c['commit'])
  print('PASS source hashes all eight:',scene,flush=True)
 records=[]
 for scene,name,title,roi,scale in ROIS:
  def render(i,speed='재생 속도는 파일명 참조',subset=None):
   return compose({c:crops[name,c,i] for c in range(1,9)},title,i,scale,speed,subset)
  # Glyph labels avoid implying that the slow GIF is a real-time rendering.
  pair=gif_pair(name,lambda i:render(i,'slow=1/6배속 · fast=0.83배속'),240)
  video=encode_mp4(MEDIA/f'{name}-60fps.mp4',lambda i:render(i,'정상 속도 60fps'),240)
  render(131,'원본 PNG').save(MEDIA/f'{name}-poster.png')
  sheets=[]
  for phase,indices in [('moving',range(130,136)),('transition',range(178,184)),('still',range(190,196))]:
   for subset in ([1,2,3,4],[5,6,7,8]):
    row=render(indices[0],'연속 프레임 검사',subset)
    sheet=Image.new('RGB',(row.width,row.height*6),BG)
    for j,i in enumerate(indices):sheet.paste(render(i,'연속 프레임 검사',subset),(0,j*row.height))
    p=MEDIA/f'{name}-{phase}-{subset[0]}to{subset[-1]}-six.png';sheet.save(p);sheets.append(p.name)
  records.append(dict(scene=scene,name=name,title=title,roi=roi,scale=scale,gifs=pair,video=video,sheets=sheets,poster=f'{name}-poster.png'))
  print('PASS media',name,flush=True)
 manifest=dict(case_layout=[[1,2,3,4],[5,6,7,8]],sources=sources,media=records,source_frames=[0,239],source_fps=60,original_colors=True)
 (OUT/'short-media-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('PASS all five short-region comparisons',flush=True)

if __name__=='__main__':main()
