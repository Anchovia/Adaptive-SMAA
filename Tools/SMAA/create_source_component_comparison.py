"""Compare independent case14 branches without merging their implementations."""
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw,ImageFont,GifImagePlugin
from create_source_component_playback import Video,ROIS
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Deliverables/SMAA_15_16_17_20261007';OUT.mkdir(parents=True,exist_ok=True)
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
evidence={i:OUT/f'Evidence/case{i}' for i in [15,16,17]}
infos={i:load(p/'case.json') for i,p in evidence.items()}
LABELS=['4 T2X-R JOn','14 Base JOff','15 Clip JOff','16 5tap JOff','17 Mix JOff']
FONT=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',13)
def compose(ims,f,box):
 w=(box[2]-box[0])*2;h=(box[3]-box[1])*2;out=Image.new('RGB',(5*(w+8)+8,h+60),(18,20,23));d=ImageDraw.Draw(out)
 for i,im in enumerate(ims):
  x=8+i*(w+8);d.text((x,7),LABELS[i],font=FONT,fill='white');d.text((x,28),f'f{f} / '+('move' if 60<=f<180 else 'still'),font=FONT,fill='white')
  out.paste(im.crop(box).resize((w,h),Image.Resampling.NEAREST),(x,50))
 return out
class Gif:
 def __init__(self,path,palette,ms):self.path=path;self.palette=palette;self.ms=ms;self.fp=path.open('wb');self.hashes=[]
 def write(self,im,f):
  p=im.quantize(palette=self.palette,dither=Image.Dither.NONE)
  if f==0:
   chunks,_=GifImagePlugin.getheader(p,info={'loop':0,'optimize':False})
   for b in chunks:self.fp.write(b)
  for b in GifImagePlugin.getdata(p,duration=self.ms,disposal=2,include_color_table=False):self.fp.write(b)
  self.hashes.append(hashlib.sha256(p.convert('RGB').tobytes()).hexdigest())
 def close(self):
  self.fp.write(b';');self.fp.close();total=0
  with Image.open(self.path) as im:
   assert im.n_frames==240
   for f in range(240):
    im.seek(f);total+=im.info['duration'];assert hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()==self.hashes[f]
  assert total==240*self.ms
  return dict(path=str(self.path),frames=240,fps=1000/self.ms,seconds=total/1000,decode_hash_match=True)
results=[];lines=['# ⑮·⑯·⑰: ⑭에서 독립 분기한 소스 요소 비교','','⑮ clipping, ⑯ recovered five-fetch sampling, ⑰ gamma2 color blend. 세 구현은 완료된 ⑭에서 직접 분기했으며 서로의 변경을 포함하지 않는다. 후보식·지터·가중치·feedback·spatial 처리를 유지했다. 새 production pass/copy/texture는 없다.','', '| 새 구현 / 장면 | 전체 AA ms | 같은 실행 ④ ms | 같은 실행 ⑭ ms | AA ④ 대비 | AA ⑭ 대비 | temporal ms | temporal ④ 대비 | temporal ⑭ 대비 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for i in [15,16,17]:
 for scene in ['bistro','minecraft']:
  p=load(evidence[i]/f'{scene}-benchmark.json');idx={(r['mode'],r['metric']):r for r in p['summary']};m=infos[i]['semantic_id'];base=infos[i]['controls'][0];a=idx[m,'SMAA'];t=idx[m,'SR_Resolve']
  lines.append(f'| {i}/{scene} | {a["mean_ms"]:.6f} | {idx["O-T2X-R","SMAA"]["mean_ms"]:.6f} | {idx[base,"SMAA"]["mean_ms"]:.6f} | {a["native4_paired_percent"]:+.2f}% | {a["case14_paired_percent"]:+.2f}% | {t["mean_ms"]:.6f} | {t["native4_paired_percent"]:+.2f}% | {t["case14_paired_percent"]:+.2f}% |')
lines+=['','各行'.replace('各行','각 행')+'의 분모는 대응 실험의 같은 run이다. 서로 다른 실행의 시간 하나로 비율을 다시 계산하지 않는다. RTX3060Ti / DX11 Release x64 / Ultra / 1920×1061 / hidden / VSync Off / 300 warm-up +4,800 frame×6회. PNG/query/readback Off의 별도 clean process.','', '## 품질과 구현 범위','','품질은 두 장면 각각 240 frame의 같은 pose에서 원본 PNG와 nearest 확대 연속 프레임, spatial proxy MAE/PSNR, raw temporal difference로 확인했다. CGVQM 재실행 결과가 아니며 raw difference 감소만으로 고스팅/반짝임 해결을 확정하지 않는다. ④ Pattern On, ⑭~⑰ Off 차이를 표시했다.','', '| 이동 ROI | ④ MAE | ⑭ MAE | ⑮ MAE | ⑯ MAE | ⑰ MAE |','|---|---:|---:|---:|---:|---:|']
for scene in ['bistro','minecraft']:
 qs={i:load(evidence[i]/f'{scene}-capture.json') for i in [15,16,17]}
 for roi in (['thin-chair','windows'] if scene=='bistro' else ['thin-seam','leaves','grass-seam']):
  baseline=next(r for r in qs[15]['roi_metrics'] if r['roi']==roi and r['window']=='moving' and r['mode']==infos[15]['controls'][0])
  native=next(r for r in qs[15]['roi_metrics'] if r['roi']==roi and r['window']=='moving' and r['mode']=='O-T2X-R')
  v=[next(r['reference_rgb_mae'] for r in qs[i]['roi_metrics'] if r['roi']==roi and r['window']=='moving' and r['mode']==infos[i]['semantic_id']) for i in [15,16,17]]
  lines.append(f'| {scene}/{roi} | {native["reference_rgb_mae"]:.4f} | {baseline["reference_rgb_mae"]:.4f} | {v[0]:.4f} | {v[1]:.4f} | {v[2]:.4f} |')
 def images(f):
  srcs=[(15,'O-T2X-R'),(15,infos[15]['controls'][0])]+[(i,infos[i]['semantic_id']) for i in [15,16,17]];ims=[]
  for i,m in srcs:
   p=Path(qs[i]['capture_root'])/m/f'frame_{f:05d}.png'
   with Image.open(p) as source:im=source.convert('RGB')
   assert hashlib.sha256(im.tobytes()).hexdigest()==qs[i]['output_hashes'][m][f];ims.append(im)
  return ims
 # Same four-case controls must bridge across all three branch captures.
 for i in [16,17]:
  for m in ['O-T2X-R',infos[i]['controls'][0]]:assert qs[i]['output_hashes'][m]==qs[15]['output_hashes'][m]
 specs=ROIS[scene];samples={name:[] for name,_,_ in specs}
 for f in [0,60,130,180,239]:
  ims=images(f)
  for name,_,box in specs:samples[name].append(compose(ims,f,box).resize((600,180)))
 writers={}
 first=images(0)
 for name,title,box in specs:
  atlas=Image.new('RGB',(600,180*len(samples[name])))
  for j,im in enumerate(samples[name]):atlas.paste(im,(0,j*180))
  palette=atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
  prefix=f'{scene}-{name}-all';view=compose(first,0,box)
  video=Video(OUT/f'{prefix}-60fps.mp4',(view.width+view.width%2,view.height+view.height%2))
  writers[name]=(video,[Gif(OUT/f'{prefix}-slow.gif',palette,40),Gif(OUT/f'{prefix}-fast.gif',palette,20)],[])
 for f in range(240):
  ims=first if f==0 else images(f)
  for name,title,box in specs:
   video,gifs,sheets=writers[name];view=compose(ims,f,box)
   if view.size!=(video.s.width,video.s.height):
    v=Image.new('RGB',(video.s.width,video.s.height));v.paste(view,(0,0))
   else:v=view
   video.write(v,f)
   for g in gifs:g.write(view,f)
   if f in [130,180,210]:
    path=OUT/f'{scene}-{name}-all-f{f}.png';view.save(path);sheets.append(str(path))
  if f%120==0:print('Five-way progress',scene,f,'/240',flush=True)
 for name,title,box in specs:
  video,gifs,sheets=writers[name]
  results.append(dict(scene=scene,roi=box,title=title,name=name,mode_order=[4,14,15,16,17],nearest_scale=2,video=video.close(),slow=gifs[0].close(),fast=gifs[1].close(),original_frame_png=sheets))
  print('PASS five-way',scene,name,flush=True)
lines+=['','| 이동 ROI | ④ luma 2차 차분 | ⑭ | ⑮ | ⑯ | ⑰ |','|---|---:|---:|---:|---:|---:|']
for scene in ['bistro','minecraft']:
 qs={i:load(evidence[i]/f'{scene}-capture.json') for i in [15,16,17]}
 for roi in (['thin-chair','windows'] if scene=='bistro' else ['thin-seam','leaves','grass-seam']):
  a=next(r for r in qs[15]['roi_metrics'] if r['roi']==roi and r['window']=='moving' and r['mode']==infos[15]['controls'][0])
  native=next(r for r in qs[15]['roi_metrics'] if r['roi']==roi and r['window']=='moving' and r['mode']=='O-T2X-R')
  values=[next(r['luma_second_delta'] for r in qs[i]['roi_metrics'] if r['roi']==roi and r['window']=='moving' and r['mode']==infos[i]['semantic_id']) for i in [15,16,17]]
  lines.append(f'| {scene}/{roi} | {native["luma_second_delta"]:.4f} | {a["luma_second_delta"]:.4f} | {values[0]:.4f} | {values[1]:.4f} | {values[2]:.4f} |')
lines+=['','## 성능 추정 범위','','아래 구간은 동일 프로세스 안의 여섯 paired run으로 계산한 미보정 95% Student-t 구간이다. 서로 다른 세션에 대한 재현 범위가 아니며 다중 비교 보정은 하지 않았다. 구간이 0을 포함하거나 변화가 매우 작으면 안정적인 성능 차이를 주장하지 않는다.','','| 실험/장면 | 전체 AA ⑭ 대비 추정 구간 | temporal ⑭ 대비 추정 구간 |','|---|---:|---:|']
for i in [15,16,17]:
 for scene in ['bistro','minecraft']:
  p=load(evidence[i]/f'{scene}-benchmark.json');idx={(r['mode'],r['metric']):r for r in p['summary']}
  a=idx[infos[i]['semantic_id'],'SMAA']['case14_paired_percent_95_interval']
  t=idx[infos[i]['semantic_id'],'SR_Resolve']['case14_paired_percent_95_interval']
  lines.append(f'| {i}/{scene} | {a[0]:+.2f}% ~ {a[1]:+.2f}% | {t[0]:+.2f}% ~ {t[1]:+.2f}% |')

lines+=['','⑮는 current spatial neighborhood의 gamma1 YCoCg clamp이며 signed chroma/variance/좌표계 안전성 수정과 sharpening Off가 포함된다. 원본 ClipColor의 완전한 동일 구현이라고 표현하지 않는다. ⑯는 원본의 비대칭 계수까지 유지하되 SMAA linear RGB/clamp sampler를 유지한다. ⑰는 원본 encoded RGB square/sqrt 식을 sRGB-view SMAA에 분리 적용한 adapter이며 색 공간 변환과 범위 제한 비용을 포함한다. 원본 UNORM 파이프라인 전체의 비용을 뜻하지 않는다.','', '세 실험 모두 검사한 이동 얇은 선에서 구조 단절을 해결했다고 판정하지 않는다. 작은 지표 개선/유사 점수로 품질 성공을 주장하지 않는다. 기본 구현은 변경하지 않고 실험 결과로 보존한다. 각각의 detailed report와 정확성 검증은 Evidence/case15, case16, case17에 있다.','']
(OUT/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
(OUT/'manifest.json').write_text(json.dumps(dict(validation='PASS',source_frames=240,source_fps=60,mode_order=[4,14,15,16,17],control_hash_mismatch=0,independent_branches=infos,results=results),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
parts=['<!doctype html><meta charset="utf-8"><title>④·⑭·⑮·⑯·⑰ 비교</title><style>body{max-width:1500px;margin:32px auto;background:#12151a;color:#eef3fa;font:16px sans-serif;padding:20px}img,video{width:100%;height:auto}section{margin:40px 0}a{color:#9ed1ff}</style><h1>④·⑭·⑮·⑯·⑰ 독립 실험 비교</h1><p>왼쪽부터 ④ T2X-R / ⑭ fixed0.8 / ⑮ clipping / ⑯ source sampler / ⑰ gamma2 blend. Spatial SMAA 모두 On, camera/depth reprojection On. ④ Pattern On, 나머지 Off. 240개 실제 프레임, 정지1초→이동2초→정지1초. GIF는 손실이 있는 확인용이며 원본 PNG도 제공한다.</p><p><a href="summary.md">측정 요약</a> · <a href="Case15/comparison.html">⑮ 개별 비교</a> · <a href="Case16/comparison.html">⑯ 개별 비교</a> · <a href="Case17/comparison.html">⑰ 개별 비교</a></p>']
for r in results:
 parts.append(f'<section><h2>{r["scene"]} — {r["title"]}</h2><p>정상 60fps / 4초</p><video controls loop muted playsinline src="{Path(r["video"]["path"]).name}"></video><p>빠른 GIF 50fps / 4.8초</p><img loading="lazy" src="{Path(r["fast"]["path"]).name}"><details><summary>느린 GIF 25fps / 9.6초와 원본 픽셀</summary><img loading="lazy" src="{Path(r["slow"]["path"]).name}">'+''.join(f'<a href="{Path(p).name}"><img loading="lazy" src="{Path(p).name}"></a>' for p in r['original_frame_png'])+'</details></section>')
(OUT/'comparison.html').write_text('\n'.join(parts),encoding='utf-8')
print('PASS combined media and paired summary')
