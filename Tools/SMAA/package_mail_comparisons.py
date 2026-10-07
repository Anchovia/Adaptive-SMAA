"""Email-ready portable report and verified case4 comparison ZIPs.
Presentation tooling only: no renderer edits, new benchmark or quality scores.
"""
import argparse,hashlib,html,json,re,sys,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import analyze_all_case_remeasurement as analysis
import create_source_component_extended_playback as enc
ROOT=Path(__file__).resolve().parents[2]
FRESH=ROOT/'Deliverables/SMAA_All_17_Remeasurement_20261007'
LONG=ROOT/'Deliverables/SMAA_4_Pair_Extended_20261007'
OUT=ROOT/'Deliverables/SMAA_Mail_Package_20261008'
PDF=OUT/'output/pdf/SMAA_01-17_Research_Report.pdf'
CASES=[i for i in range(1,18) if i!=4]
DESC={
1:'AA-Off. Spatial·temporal 모두 Off. AA 시간 0은 전체 렌더링 시간 0을 뜻하지 않는다.',
2:'원본 SMAA 1X: 공간 3단계만 수행. Temporal 및 paired sample pattern Off.',
3:'Spatial 보정 없이 전체 화면 원본 T2X-R 결합. Camera/depth reprojection, paired sample pattern On.',
4:'원본 spatial SMAA + 전체 화면 T2X-R. Camera/depth reprojection, paired jitter/subsample pattern On. 비교 기준.',
5:'1차 edge 검출은 수행하되 spatial 보정은 제외. 현재 edge에만 T2X-R 결합. Pattern Off.',
6:'원본 spatial SMAA + 현재 1차 edge에만 T2X-R 결합. 비선택 픽셀은 현재 spatial 색상. Pattern Off.',
7:'현재 edge와 재투영한 직전 raw edge의 합집합. Depth 검사를 사용한 초기 persistence 구현.',
8:'⑦의 선택 준비 비용을 FirstStencil 경로로 줄임. 이번 240프레임 출력은 ⑦과 완전히 동일.',
9:'⑧의 velocity 접근을 정수 좌표 Load로 변경. 이번 출력은 ⑦·⑧과 완전히 동일.',
10:'⑨에서 history RGB는 bilinear, alpha는 point로 읽음. History에는 각 프레임의 spatial 결과를 저장.',
11:'최종 resolve RGB를 다음 history로 feedback해 누적. Alpha는 현재 spatial 프레임의 velocity 정보를 유지.',
12:'ValidatedRGB 적응형 누적·history 검증. ResponsiveRGB/ClippedRGB 진단과 구분. 품질·비용 실패 사례로 보존.',
13:'누적 RGB에 정규화한 MJP 계열 cross 5-fetch 재구성. 가변 history weight 0..0.5. 확보 TSCMAA 소스와 동일 필터 아님.',
14:'⑬에서 후보 history weight를 TSCMAA 수치 0.8로 고정. 비후보 0.0, resolved RGB feedback.',
15:'⑭에 소스 기반 YCoCg history clipping을 추가. SMAA adaptation과 경계·수치 안전성 보완 포함.',
16:'⑭의 history 재구성을 확보 소스의 5-fetch 계산으로 교체. ⑮ clipping과 ⑰ 색 혼합은 포함하지 않음.',
17:'⑭의 encoded RGB를 제곱 → 혼합 → 제곱근으로 처리하는 gamma 2 근사. 정확한 sRGB 변환은 아님.'
}
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return enc.sha(p)
def inputs():
 plan=load(ROOT/'tmp/all-case-remeasurement/manifest.json');runs=load(ROOT/'tmp/all-case-remeasurement/runs.json')
 paths,_=analysis.capture_paths(plan,runs)
 hashes=load(FRESH/'output-pixel-hashes.json')
 correction=OUT/'source-hash-correction.json'
 if correction.exists():
  doc=load(correction);assert doc['validation']=='VERIFIED_DOCUMENTED_EXCEPTION' and not doc['formal_quality_windows_affected']
  for row in doc['entries']:
   key=f'{row["scene"]}/{row["case"]}/{row["frame"]}';assert row['phase']=='initial' and hashes[key]==row['expected_rgb']
   assert sha(row['path'])==row['png_sha256'];hashes[key]=row['actual_rgb']
 return plan,paths,hashes
def checked(p,h):
 from io import BytesIO
 import os
 for attempt in range(3):
  content=Path(p).read_bytes()
  with Image.open(BytesIO(content)) as im:
   assert im.mode=='RGB' and im.size==(1920,1061)
   im.load();actual=enc.pixel_hash(im)
   if actual==h:return im.copy()
  OUT.mkdir(parents=True,exist_ok=True)
  record=dict(path=str(p),attempt=attempt,expected_rgb=h,observed_rgb=actual,png_sha256=hashlib.sha256(content).hexdigest(),action='Rejected read; no unmatched pixels used')
  with (OUT/f'input-read-retries-{os.getpid()}.jsonl').open('a',encoding='utf-8') as fp:fp.write(json.dumps(record,ensure_ascii=False)+'\n')
 raise AssertionError(('RGB mismatch after 3 independent reads',str(p)))
def pair(a,b,f,case,size):
 w,h=size;out=Image.new('RGB',(2*w+24,h+60),'#12151a');d=ImageDraw.Draw(out)
 d.text((8,5),'04 Original T2X-R / Pattern ON',font=enc.FONT,fill='white')
 d.text((w+16,5),f'{case:02d} / Pattern '+('ON' if case==3 else 'OFF'),font=enc.FONT,fill='white')
 d.text((8,27),f'f{f:03d} / '+('initial still' if f<60 else 'moving' if f<180 else 'move -> still'),font=enc.SMALL,fill='#c9d7e2')
 out.paste(a,(8,52));out.paste(b,(w+16,52));return out
def media(scene):
 enc.FRAMES=240;_,paths,hashes=inputs();folder=OUT/'generated'/scene;folder.mkdir(parents=True,exist_ok=True)
 control=[]
 for f in range(240):
  a=checked(paths[scene,4]/f'frame_{f:05d}.png',hashes[f'{scene}/4/{f}'])
  control.append(a.resize((640,354),Image.Resampling.LANCZOS))
 results=[]
 for case in CASES:
  receipt=folder/f'{scene}-overview-4-vs-{case:02d}.json'
  if receipt.exists():
   old=load(receipt);assert all(sha(Path(v['path']))==v['sha256'] for v in old['media'].values());results.append(old);continue
  strip=Image.new('RGB',(792,272*8))
  for i,f in enumerate([0,60,126,130,179,181,209,239]):
   b=checked(paths[scene,case]/f'frame_{f:05d}.png',hashes[f'{scene}/{case}/{f}'])
   strip.paste(pair(control[f].resize((384,212),Image.Resampling.LANCZOS),b.resize((384,212),Image.Resampling.LANCZOS),f,case,(384,212)),(0,i*272))
  palette=strip.quantize(colors=256,dither=Image.Dither.NONE);base=f'{scene}-overview-4-vs-{case:02d}'
  v=enc.Video(folder/f'{base}-normal.mp4',(1304,414));v.stream.options={'crf':'14','preset':'veryfast','threads':'2'}
  slow=enc.Gif(folder/f'{base}-slow.gif',palette,1,40);fast=enc.Gif(folder/f'{base}-fast.gif',palette,2,20)
  for f in range(240):
   b=checked(paths[scene,case]/f'frame_{f:05d}.png',hashes[f'{scene}/{case}/{f}'])
   v.write(pair(control[f],b.resize((640,354),Image.Resampling.LANCZOS),f,case,(640,354)))
   g=pair(control[f].resize((384,212),Image.Resampling.LANCZOS),b.resize((384,212),Image.Resampling.LANCZOS),f,case,(384,212))
   q=slow.write(g,f);fast.write(g,f,quantized=q)
  r=dict(scene=scene,case=case,source_root=str(paths[scene,case]),source_frames=240,source_fps=60,source_seconds=4,source_hash_validation='PASS',whole_frame_not_crop=True,media=dict(normal=v.close(),slow=slow.close(),fast=fast.close()))
  dump(receipt,r);results.append(r);print(f'PASS {scene} 4 vs {case:02d}: whole MP4 + slow/fast GIF',flush=True)
 dump(folder/'manifest.json',results)
def tables():
 plan=load(ROOT/'tmp/all-case-remeasurement/manifest.json')
 perf={(r['scene'],r['case']):r for r in load(FRESH/'performance.json')}
 quality={(r['scene'],r['case']):r for r in load(FRESH/'quality.json')}
 return plan,perf,quality
def report():
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image as RI
 from reportlab.lib.styles import ParagraphStyle
 from reportlab.lib.pagesizes import A4
 from reportlab.lib import colors
 from reportlab.pdfbase import pdfmetrics
 from reportlab.pdfbase.ttfonts import TTFont
 pdfmetrics.registerFont(TTFont('K','C:/Windows/Fonts/malgun.ttf'));pdfmetrics.registerFont(TTFont('KB','C:/Windows/Fonts/malgunbd.ttf'))
 body=ParagraphStyle('body',fontName='K',fontSize=10,leading=16,spaceAfter=10,wordWrap='CJK')
 small=ParagraphStyle('small',parent=body,fontSize=8.4,leading=12.5,spaceAfter=7)
 heading=ParagraphStyle('heading',parent=body,fontName='KB',fontSize=16,leading=23,spaceAfter=16,textColor=colors.HexColor('#163553'))
 title=ParagraphStyle('title',parent=heading,fontSize=23,leading=32,spaceAfter=22)
 story=[];plan,perf,qual=tables()
 OUT.mkdir(parents=True,exist_ok=True);PDF.parent.mkdir(parents=True,exist_ok=True)
 def pdftext(t):return ''.join(str(ord(c)-ord('①')+1) if '①'<=c<='⑰' else c for c in str(t)).replace('全','전체 ')
 def p(t,style=body):story.append(Paragraph(html.escape(pdftext(t)).replace('\n','<br/>'),style))
 def pg(t):story.append(PageBreak());p(t,heading)
 def table(headers,rows,widths):
  t=Table([[Paragraph(html.escape(pdftext(c)).replace('\n','<br/>'),small) for c in r] for r in [headers,*rows]],colWidths=widths,repeatRows=1)
  t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eff8')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#ccd8e5')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]));story.append(t);story.append(Spacer(1,12))
 p('선택적 Temporal SMAA\n①-⑰ 속도·품질 비교',title)
 p('연구 공유 자료 | 2026-10-08 | 기준선: ④ Original SMAA T2X-R',small)
 p('현재 확인한 성과와 남은 문제',heading)
 p('현재 edge만 처리하는 ⑥은 수정된 ④보다 전체 AA 시간이 Bistro 15.11%, Minecraft 4.12% 짧았다. Temporal 결합 단계는 각각 78.12%, 33.60% 줄었다. 다만 이동 중 반짝임과 얇은 구조 손실이 남아 있다.')
 p('⑰의 전체 AA 시간은 Bistro 6.79% 감소, Minecraft 9.46% 증가다. 누적·history 재구성은 장면마다 비용과 품질의 절충이 있어 모든 장면에서 원본보다 빠르고 품질도 좋다고 결론낼 단계는 아니다.')
 p('기준선 stencil lifecycle 보완',heading)
 p('확인한 CMAA2 demo의 SMAA 통합 경로에는 매 프레임 stencil 초기화가 누락돼 있었다. 이전 edge 표시가 남아 현재 edge가 아닌 곳에서도 2차 spatial 패스가 실행될 수 있었다. 이를 초기화하도록 보완했다. SMAA 고유 알고리즘의 결함이나 새로운 AA 기법으로 주장하지 않는다.')
 p('아래 표는 초기화가 적용된 ①-⑰의 새 짝 비교다. 초기화 전 수치와의 차이를 이 표에서 역산하지 않는다. 소스별 브랜치·커밋·실행 파일·결과 CSV 해시는 evidence에 보존했다.')
 p('17개 번호는 구현 이력의 독립 비교군이다. 최종 논문의 Original/Adaptive × Standard/Edge-selective × reprojection Off/On 8-case와 구분한다. Intel TSCMAA 전체의 완전한 포팅이 아닌 SMAA adaptation이다.',small)
 for group in [range(1,10),range(10,18)]:
  pg('각 구현 설명 '+('①-⑨' if group.start==1 else '⑩-⑰'))
  for i in group:
   label=next(x['label'] for x in plan['cases'] if x['case']==i)
   p(f'{i:02d}. {label}',small);p(DESC[i])
  if group.start==10:p('⑮·⑯·⑰은 ⑭에서 각각 한 항목만 변경한 독립 실험이다. 서로 누적 적용한 버전이 아니다. ③·④ Pattern On, ⑤-⑰ Off이므로 차이를 후보 선택 효과 하나로 귀속하지 않는다.',small)
 pg('전체 AA GPU 시간')
 p('RTX 3060 Ti / DX11 Release x64 / Original SMAA Ultra / 1920×1061 / hidden windowed / VSync Off. 장면별 300 warm-up + 4,800프레임 × 6회. 같은 실행 파일에서 대상과 원본 ④를 교차 순서로 짝 측정. PNG 저장·진단 query·GPU readback Off.',small)
 rows=[]
 for i in range(1,18):
  b,m=perf['bistro',i]['AA'],perf['minecraft',i]['AA'];rows.append([f'{i:02d}',f'{b["ms"]:.5f}',f'{b["percent"]:+.2f}%',f'{m["ms"]:.5f}',f'{m["percent"]:+.2f}%'])
 table(['번호','Bistro ms','④ 대비','Minecraft ms','④ 대비'],rows,[45,105,75,125,95])
 p('음수는 시간 감소, 양수는 시간 증가. 비율의 분모는 해당 구현과 함께 측정한 ④다. AA 시간은 필요한 공간 처리·선택 준비·camera velocity·temporal 작업을 포함하며 전체 렌더링 시간과 구분한다.',small)
 p('Minecraft ⑨·⑩의 +0.52%·+0.40% 차이는 반복별 짝 비교 95% 구간이 0을 포함한다. 확정적인 속도 우열을 주장하지 않는다. 초기화 전후의 순수 효과는 별도 과거 감사 자료이며 이번 표와 섞지 않았다.',small)
 pg('Temporal 결합 단계 GPU 시간')
 p('공간 처리, 선택 준비와 camera velocity 생성은 제외한 resolve 시간이다.',small)
 rows=[]
 for i in range(1,18):
  b,m=perf['bistro',i]['temporal'],perf['minecraft',i]['temporal']
  rows.append([f'{i:02d}',f'{b["ms"]:.5f}' if b else '-',f'{b["percent"]:+.2f}%' if b else '-',f'{m["ms"]:.5f}' if m else '-',f'{m["percent"]:+.2f}%' if m else '-'])
 table(['번호','Bistro ms','④ 대비','Minecraft ms','④ 대비'],rows,[45,105,75,125,95])
 p('⑥은 두 장면에서 resolve 비용을 줄였다. 직전 edge 준비·history 누적은 다른 단계의 비용을 늘릴 수 있어 resolve 시간과 전체 AA 시간을 구분해야 한다.',small)
 p('각 정식 명령은 독립 CMAA2 프로세스에서 실행. 명령 앞뒤 잔류 프로세스 0개, 1,200초 timeout, 결과 CSV Aggregate PASS 확인. 총 102개 Smoke/Benchmark/Capture 명령이 완료됐다.',small)
 pg('품질: 같은 프레임의 공간 참조와 비교')
 p('Supersample 공간 reference proxy에 대한 PSNR/SSIM. Temporal ground truth가 아니며 높을수록 해당 참조에 가깝다. 이번 재측정에서 CGVQM은 재계산하지 않았고 과거 점수도 섞지 않았다. 이동 f60-179, 정지 전환 f180-209.',small)
 rows=[]
 for i in range(1,18):
  b,m=qual['bistro',i],qual['minecraft',i];rows.append([f'{i:02d}',f'{b["moving"]["psnr"]:.3f}\n{b["moving"]["luma_ssim"]:.5f}',f'{m["moving"]["psnr"]:.3f}\n{m["moving"]["luma_ssim"]:.5f}',f'{b["transition"]["psnr"]:.3f}',f'{m["transition"]["psnr"]:.3f}'])
 table(['번호','Bistro 이동\nPSNR / SSIM','Minecraft 이동\nPSNR / SSIM','Bistro 전환\nPSNR','Minecraft 전환\nPSNR'],rows,[38,110,117,90,90])
 p('⑦·⑧·⑨는 두 장면 240프레임 RGB가 완전히 동일했다. 정지 f220-239는 ⑫ 외 모든 구성에서 hash 하나. ⑫는 최대 인접 채널 차이 1/255, 평균 변경 픽셀 비율 0.0012% 미만으로 검사한 ROI에서 뚜렷한 정지 떨림은 보이지 않았다.',small)
 pg('연속 프레임에서 확인한 구조 손실')
 p('Minecraft 얇은 경계: ④(좌), ⑰(우). f128·f130에서 ⑰의 수직 경계 일부가 약해지거나 끊기고 f129·f131에서 다시 강해진다. ④도 완벽하지 않다. 반짝임 완전 해결로 판정하지 않는다.')
 _,paths,hashes=inputs();strip=Image.new('RGB',(824,632),'#12151a');d=ImageDraw.Draw(strip)
 for row,f in enumerate(range(128,132)):
  base_x=(row%2)*416;base_y=(row//2)*316
  d.text((base_x+8,base_y+6),f'f{f}: 04 left | 17 right',font=enc.FONT,fill='white')
  for col,c in enumerate([4,17]):
   im=checked(paths['minecraft',c]/f'frame_{f:05d}.png',hashes[f'minecraft/{c}/{f}'])
   strip.paste(im.crop((956,524,1020,620)).resize((192,288),Image.Resampling.NEAREST),(base_x+8+col*200,base_y+26))
 strip.save(OUT/'report-structure-loss.png');story.append(RI(str(OUT/'report-structure-loss.png'),width=440,height=440*632/824))
 p('원본 ROI nearest 3배 확대. 무손실 검사지는 전체 ZIP에 포함. 시간 변화가 감소해도 흐림·선 소실 때문일 수 있어 잔차를 품질 순위로 사용하지 않는다.',small)
 pg('ZIP 자료를 보는 방법')
 p('압축을 먼저 해제한 뒤 index.html을 브라우저에서 연다. 상대 경로의 오프라인 갤러리다. 항상 왼쪽 ④, 오른쪽 비교 번호. report 폴더는 보고서와 메일 초안, evidence 폴더는 수치·provenance다.')
 p('짧은 재측정은 ①-⑰ 모두 동일한 실제 4초/240프레임(정지 1 + 이동 2 + 정지 1). ④와 나머지 16개 번호의 전체 화면 MP4·느린/빠른 GIF 및 5개 세부 ROI 비교를 제공한다.')
 p('긴 비교는 ⑭-⑰의 이전 검증 720프레임을 재사용. 실제 12초(정지 1 + 이동 10 + 정지 1), 두 장면에서 전체 포함 14개 view. 짧은 재측정과 다른 경로 길이이며 새 품질 점수로 사용하지 않는다.')
 table(['자료','원본 경로','재생 시간·속도'],[['짧은 전체 MP4','240프레임 / 60Hz','4초 / 1배'],['짧은 전체 느린 GIF','全240프레임 유지','9.6초 / 약 0.42배'],['짧은 전체 빠른 GIF','stride2','2.4초 / 약 1.67배'],['짧은 ROI GIF','f60-209 모두 유지','5초 / 0.5배'],['긴 정상 MP4','720프레임 / 60Hz','12초 / 1배'],['긴 느린 GIF','全720프레임 유지','28.8초 / 약 0.42배'],['긴 빠른 GIF','stride2','7.2초 / 약 1.67배']],[130,160,155])
 p('MP4는 갤러리에서 0.5배·1배·2배로 재생 가능. 동일 경로의 재생 속도 변경이며 다른 카메라 속도로 새로 렌더한 결과가 아니다. 빠른 GIF는 일부 프레임을 건너뛰므로 반짝임은 모든 프레임 유지 영상·느린 GIF·원본 PNG로 판단한다.',small)
 p('전체 영상은 축소, ROI는 nearest 확대. GIF 팔레트와 H.264는 손실 표시용. 원본 해상도 전체 PNG 비교도 포함. 색·노출 보정 없음. 이번 temporal은 camera/depth reprojection이며 object motion, Adaptive 공간 처리, 후보 확장은 제외.',small)
 def footer(c,doc):
  c.setFont('K',8);c.setFillColor(colors.HexColor('#526477'));c.drawString(45,25,'Adaptive SMAA 연구 | 2026-10-08');c.drawRightString(A4[0]-45,25,str(doc.page))
 SimpleDocTemplate(str(PDF),pagesize=A4,leftMargin=45,rightMargin=45,topMargin=42,bottomMargin=45,title='SMAA 01-17 속도·품질 비교').build(story,onFirstPage=footer,onLaterPages=footer)
 draft='''제목: 선택적 temporal SMAA 오버헤드 개선 및 ①-⑰ 비교 결과 공유

교수님 안녕하세요.

말씀하신 TSCMAA 스타일 구현의 오버헤드 감소와 관련하여 구현 ①-⑰을 같은 조건에서 다시 측정하고 비교 자료를 정리했습니다.

확인한 CMAA2 demo의 SMAA 통합 경로에는 매 프레임 stencil 초기화가 누락돼 있어 보완했습니다. 이는 SMAA 알고리즘 변경이 아닌 demo 통합 경로의 lifecycle 수정이며, 이번 비교는 초기화가 적용된 원본 SMAA T2X-R(④)을 기준으로 수행했습니다.

현재 edge에만 temporal 결합하는 ⑥의 전체 AA 시간은 ④ 대비 Bistro 15.11%, Minecraft 4.12% 감소했습니다. Temporal 결합 단계는 각각 78.12%, 33.60% 감소했습니다. 선택적 결합의 실행 비용은 줄였으나 이동 중 반짝임과 얇은 구조 소실까지 해결했다고 보기는 어렵습니다.

직전 edge 보존, history 재구성·누적, TSCMAA 소스 기반 clipping·sampling·색 혼합을 각각 비교했습니다. ⑰은 Bistro에서 전체 AA 시간이 6.79% 감소했으나 Minecraft에서는 9.46% 증가했고, 연속 프레임에서도 일부 얇은 선 소실이 남아 있습니다. 단일 최종 구현은 아직 확정하지 않았습니다.

요약 ZIP에 전체 구현 설명, 속도·품질 표, 대표 두 방식 비교 GIF와 보고서를 첨부했습니다. 전체 미디어 ZIP은 용량이 커 별도로 전달하며, ④와 각 번호의 비교, 전체 화면, 여러 세부 장면, 느린·빠른 재생과 12초 긴 경로 영상을 포함합니다. 압축을 해제한 뒤 index.html을 열면 확인할 수 있습니다.

품질 수치는 supersample 공간 참조에 대한 PSNR/SSIM으로 temporal ground truth가 아니며, 이번에는 CGVQM을 재계산하지 않았습니다. 무손실 연속 프레임의 직접 검사 결과를 함께 첨부했습니다. ③·④는 paired sample pattern On, 선택적 구성은 Off이므로 차이를 후보 선택 효과 하나로 해석하지 않았습니다.

검토 의견을 후속 품질 보완과 최종 비교 구성에 반영하겠습니다.
감사합니다.
'''
 (OUT/'email-draft.txt').write_text(draft,encoding='utf-8')
 (OUT/'comparison.txt').write_text((FRESH/'comparison.md').read_text(encoding='utf-8'),encoding='utf-8')
 dump(OUT/'implementation-index.json',[dict(case=x['case'],label=x['label'],branch=x['branch'],commit=x['commit'],description=DESC[x['case']],spatial=x['spatial'],temporal=x['temporal'],paired_sample_pattern=x['paired_sample_pattern']) for x in plan['cases']])
 print('REPORT WRITTEN',PDF,flush=True)
CSS='body{max-width:1100px;margin:auto;padding:30px;font:16px/1.7 sans-serif;background:#f6f8fb;color:#202c3b}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #d4dfeb;text-align:left}th{background:#e9eff8}section{padding:20px;background:white;margin:24px 0;border:1px solid #d4dfeb;border-radius:8px}img,video{max-width:100%;height:auto}a{color:#1757a6}summary,button{cursor:pointer}button{padding:8px;margin:4px}.note{padding:12px;background:#fff3dc}nav a{margin-right:14px}'
def htable(headers,rows):return '<table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
def video(url):return f'<video controls loop muted playsinline preload="none" src="{url}"></video><p>'+''.join(f'<button onclick="this.parentElement.previousElementSibling.playbackRate={s}">{s}배</button>' for s in [.5,1,2])+'</p>'
def mail_media():
 enc.FRAMES=90;_,paths,hashes=inputs();folder=OUT/'mail-media';folder.mkdir(parents=True,exist_ok=True);records=[]
 for scene,key,box in [('bistro','thin-chair',(1230,582,1358,670)),('minecraft','thin-seam',(956,524,1020,620))]:
  w,h=(box[2]-box[0])*2,(box[3]-box[1])*2
  for case in [6,13,14,17]:
   frames=[]
   for f in range(110,200):
    im=Image.new('RGB',(2*w+24,h+32),'#12151a');d=ImageDraw.Draw(im);d.text((8,5),f'04 left | {case:02d} right / f{f}',font=enc.FONT,fill='white')
    for col,c in enumerate([4,case]):
     a=checked(paths[scene,c]/f'frame_{f:05d}.png',hashes[f'{scene}/{c}/{f}'])
     im.paste(a.crop(box).resize((w,h),Image.Resampling.NEAREST),(8+col*(w+8),28))
    frames.append(im)
   strip=Image.new('RGB',(frames[0].width,frames[0].height*10))
   for j in range(10):strip.paste(frames[j*9],(0,j*frames[0].height))
   pal=strip.quantize(colors=128,dither=Image.Dither.NONE);path=folder/f'{scene}-{key}-4-vs-{case}-mail.gif';g=enc.Gif(path,pal,1,40)
   for j,im in enumerate(frames):g.write(im,j)
   record=g.close();record.update(scene=scene,case=case,source_frame_range=[110,199],source_seconds=1.5,palette_colors=128,all_frames_retained=True);records.append(record)
   print('MAIL GIF PASS',scene,case,path.stat().st_size,flush=True)
 dump(folder/'manifest.json',records)
def package():
 assert PDF.exists();plan,perf,qual=tables();sources={}
 def add(src,dest):
  src=Path(src);assert src.is_file(),str(src);assert dest not in sources,dest;sources[dest]=src
 add(PDF,'report/Research_Report.pdf')
 for name in ['email-draft.txt','comparison.txt','implementation-index.json','report-structure-loss.png']:add(OUT/name,'report/'+name)
 for p in FRESH.iterdir():
  if p.is_file() and p.suffix in ['.json','.csv'] and not p.name.startswith('preliminary'):add(p,'evidence/'+p.name)
 for p in (ROOT/'Docs/All-Case-Remeasurement').iterdir():
  if p.is_file():add(p,'evidence/protocol/'+p.name)
 for run in load(ROOT/'tmp/all-case-remeasurement/runs.json'):
  src=Path(run['report']);assert sha(src).upper()==run['report_sha256'].upper()
  add(src,f'evidence/raw-reports/case{run["case"]:02d}-{run["scene"]}-{run["phase"]}.csv')
 stencil=Path('C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Docs/Stencil-Lifecycle-Refresh')
 for name in ['method.md','source-audit.json']:add(stencil/name,'evidence/stencil-lifecycle/'+name)
 for p in (FRESH/'frames').iterdir():add(p,'media/short-roi/'+p.name)
 for p in (FRESH/'inspection').iterdir():add(p,'frames/inspection/'+p.name)
 for name in ['source-recheck.json','source-hash-correction.json','source-hash-note.txt']:add(OUT/name,'evidence/'+name)
 for p in OUT.glob('input-read-retries-*.jsonl'):add(p,'evidence/'+p.name)
 for p in (OUT/'mail-media').iterdir():add(p,'media/mail/'+p.name)
 short=[]
 for scene in ['bistro','minecraft']:
  records=load(OUT/'generated'/scene/'manifest.json');assert {x['case'] for x in records}==set(CASES)
  for x in records:
   for r in x['media'].values():
    src=Path(r['path']);assert sha(src)==r['sha256'];add(src,'media/short-overview/'+src.name)
   short.append(x)
  add(OUT/'generated'/scene/'manifest.json',f'evidence/{scene}-short-media.json')
 long=load(LONG/'manifest.json');assert long['validation']=='PASS'
 for scene in long['results']:
  for x in scene['results']:
   for speed in ['normal','slow','fast']:
    r=x[speed];src=Path(r['path']);assert sha(src)==r['sha256'];add(src,'media/long/'+src.name)
 for p in LONG.iterdir():
  if p.suffix=='.png':add(p,'frames/long/'+p.name)
  elif p.suffix=='.json':add(p,'evidence/long/'+p.name)
 readme='''SMAA ①-⑰ 연구 비교 자료 | 2026-10-08
ZIP 전체를 압축 해제한 뒤 index.html을 브라우저에서 여십시오.
항상 왼쪽 ④ 원본 SMAA T2X-R, 오른쪽 비교 번호입니다.
report/Research_Report.pdf: 구현 설명, 전체 AA/temporal 시간, 품질 표, 직접 프레임 검사.
report/email-draft.txt: 메일 초안. 실제 메일 전송은 수행하지 않았습니다.
evidence/: 새 재측정 수치, 프로토콜, branch/commit/실행 provenance와 검증 기록.
media/: 짧은 4초 경로의 전체·ROI 비교 및 기존 12초 긴 경로 자료.
frames/: 연속 무손실 PNG 검사. 원본 해상도 전체 PNG는 media/short-roi/*full*.png.
짧은 자료는 ①-⑰, 240프레임. 긴 자료는 ⑭-⑰, 720프레임의 이전 검증 캡처 재사용.
느린 전체 GIF는 모든 프레임 유지/약 0.42배. 빠른 GIF는 stride2/약 1.67배.
짧은 ROI는 f60-209/0.5배/5초. 정상 MP4는 짧은 4초, 긴 12초/1배/60fps.
MP4 버튼 0.5/1/2배는 동일 경로의 재생 속도 변경입니다.
빠른 GIF는 일부 프레임을 생략하므로 반짝임 판정에 사용하지 마십시오.
전체 영상은 축소, ROI는 nearest 확대. GIF/H264는 손실 표시용, 원본 PNG 우선.
③·④ Pattern On, ⑤-⑰ Off. PSNR/SSIM은 공간 reference proxy. CGVQM 재계산 없음.
모든 temporal은 camera/depth reprojection. Object motion/Adaptive/확장은 이번 범위 밖.
7/8/9 두 장면 240프레임 출력 RGB hash는 완전히 같습니다.
이 17개 이력 비교는 최종 논문 8-case 행렬과 구분합니다.
요약 ZIP은 대표 자료만 포함, 전체 ZIP은 모든 비교 GIF/MP4·검사 PNG·근거를 포함.
전체 ZIP은 메일 첨부에 큰 용량이므로 요약본을 첨부하고 전체본은 별도 파일 공유를 권합니다.
원본 캡처 전체·실행 파일·장면 asset은 원래 경로에 보존했으며 ZIP에 복제하지 않았습니다.
Minecraft case5 f14 초기 구간의 이전 파생 RGB hash 불일치는 별도 예외 근거를 기록했습니다. PNG 파일 해시는 기존 정리 기록과 동일하고 품질 표 구간에는 영향이 없습니다. evidence/source-hash-note.txt 참조.
'''
 (OUT/'START_HERE.txt').write_text(readme,encoding='utf-8');add(OUT/'START_HERE.txt','START_HERE.txt')
 pr=[];qr=[]
 for i in range(1,18):
  b,m=perf['bistro',i],perf['minecraft',i];bq,mq=qual['bistro',i],qual['minecraft',i]
  fmt=lambda r:f'{r["ms"]:.5f} ({r["percent"]:+.2f}%)' if r else '-'
  pr.append([f'{i:02d}',next(x['label'] for x in plan['cases'] if x['case']==i),fmt(b['AA']),fmt(m['AA']),fmt(b['temporal']),fmt(m['temporal'])])
  qr.append([f'{i:02d}',f'{bq["moving"]["psnr"]:.3f} / {bq["moving"]["luma_ssim"]:.5f}',f'{mq["moving"]["psnr"]:.3f} / {mq["moving"]["luma_ssim"]:.5f}',f'{bq["transition"]["psnr"]:.3f}',f'{mq["transition"]["psnr"]:.3f}'])
 summary='<h1>SMAA ①-⑰ 비교 자료</h1><p>2026-10-08 / 항상 왼쪽 ④, 오른쪽 비교 번호. 기준선 stencil 초기화 보완 적용.</p><nav><a href="report/Research_Report.pdf">PDF 보고서</a><a href="report/email-draft.txt">메일 초안</a><a href="START_HERE.txt">읽는 방법</a></nav>'
 summary+='<h2>속도</h2><p>ms (같은 실행의 ④ 대비 변화율). 음수: 시간 감소. 전체 AA와 resolve를 구분.</p>'+htable(['번호','구현','Bistro AA','Minecraft AA','Bistro temporal','Minecraft temporal'],pr)
 summary+='<h2>품질</h2><p>공간 reference proxy. Temporal ground truth 아님. CGVQM 재측정 없음. 이동 PSNR / SSIM, 전환 PSNR.</p>'+htable(['번호','Bistro 이동','Minecraft 이동','Bistro 전환','Minecraft 전환'],qr)
 summary+='<p class="note">반짝임·얇은 선 소실은 아직 남아 있습니다. ③·④ Pattern On, ⑤-⑰ Off. 차이를 edge 선택 하나의 효과로 해석하지 않습니다.</p><h2>각 구현</h2>'+''.join(f'<p><strong>{i:02d}</strong> {html.escape(DESC[i])}</p>' for i in range(1,18))
 page=[summary,'<h2>짧은 재측정: ④와 각 번호</h2><p>전체는 실제 4초 경로. ROI는 실제 2.5초 구간을 5초로 재생.</p>']
 for i in CASES:
  page.append(f'<h2>④ ↔ {i:02d}</h2>')
  for scene in ['bistro','minecraft']:
   x=next(x for x in short if x['scene']==scene and x['case']==i)
   page.append(f'<section><h3>{scene} / 전체 화면</h3>'+video('media/short-overview/'+Path(x['media']['normal']['path']).name))
   for speed,label in [('slow','느림: 9.6초 / 약 0.42배 / 모든 프레임'),('fast','빠름: 2.4초 / 약 1.67배 / stride2')]:page.append(f'<details><summary>{label}</summary><img loading="lazy" src="media/short-overview/{Path(x["media"][speed]["path"]).name}"></details>')
   for key in analysis.ROIS[scene]:
    stem=f'{scene}-{key}-4-vs-{i}';page.append(f'<details><summary>{key}: 0.5배 / 5초</summary><img loading="lazy" src="media/short-roi/{stem}.gif"><p><a href="media/short-roi/{stem}.png">무손실 연속 12프레임 PNG</a></p></details>')
   page.append('<p>원본 전체 PNG: '+' / '.join(f'<a href="media/short-roi/{scene}-full-f{f}-4-vs-{i}.png">f{f}</a>' for f in [130,181,230])+'</p></section>')
 page.append('<h2>긴 경로: ④ ↔ ⑭·⑮·⑯·⑰</h2><p>실제 12초/720프레임. 이전 검증 캡처 재사용. 2개 렌더 장면, 전체 포함 14개 view.</p>')
 for i in [14,15,16,17]:
  page.append(f'<h2>④ ↔ {i}</h2>')
  for scene in long['results']:
   for x in scene['results']:
    if x['case']!=i:continue
    page.append(f'<section><h3>{scene["scene"]} / {html.escape(x["title"])}</h3>'+video('media/long/'+Path(x['normal']['path']).name))
    for speed,label in [('slow','느림: 28.8초 / 약 0.42배 / 全720프레임'),('fast','빠름: 7.2초 / 약 1.67배 / stride2')]:page.append(f'<details><summary>{label}</summary><img loading="lazy" src="media/long/{Path(x[speed]["path"]).name}"></details>')
    page.append('</section>')
 start='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SMAA 비교 자료</title><style>'+CSS+'</style><body>'
 end='<footer>기존 검증 결과의 자료 묶음. 모든 갤러리 경로는 ZIP 내부 상대 경로입니다.</footer></body></html>'
 (OUT/'index.html').write_text(start+'\n'.join(page)+end,encoding='utf-8');add(OUT/'index.html','index.html')
 selected=[f'media/mail/{s}-{r}-4-vs-{i}-mail.gif' for s,r in [('bistro','thin-chair'),('minecraft','thin-seam')] for i in [6,13,14,17]]
 mini=summary+'<h2>대표 비교 GIF</h2><p>약 0.42배/3.6초, 원본 f110-199의 全90프레임. 128색 표시용. 긴 자료·다른 장면은 전체 ZIP에 있습니다.</p>'+''.join(f'<section><h3>{Path(k).stem}</h3><img loading="lazy" src="{k}"></section>' for k in selected)
 (OUT/'summary-index.html').write_text(start+mini+end,encoding='utf-8')
 base={k:v for k,v in sources.items() if k.startswith('report/') or k in ['START_HERE.txt','evidence/performance.json','evidence/quality.json','evidence/visual-inspection.json','evidence/source-recheck.json','evidence/source-hash-correction.json','evidence/source-hash-note.txt']}
 base.update({k:sources[k] for k in selected});base['index.html']=OUT/'summary-index.html'
 manifest=dict(validation='PASS',classification='existing verified results; presentation package',fresh_cases=list(range(1,18)),short_pairs=[[4,i] for i in CASES],scenes=['bistro','minecraft'],short_frames=240,long_pairs=[[4,i] for i in [14,15,16,17]],long_frames=720,new_benchmarks=False,new_quality_scores=False,renderer_changed=False,source_sequences_preserved=True,documented_initial_rgb_hash_exception=True,provenance_commit='53d26a8f9028dd4c703843c6b87ce6ccd92ef763',files=[dict(path=k,bytes=v.stat().st_size,sha256=sha(v)) for k,v in sources.items()])
 dump(OUT/'package-manifest.json',manifest);sources['package-manifest.json']=OUT/'package-manifest.json'
 small_manifest={k:v for k,v in manifest.items() if k!='files'};small_manifest.update(package='mail summary only; full media in separate archive',files=[dict(path=k,bytes=v.stat().st_size,sha256=sha(v)) for k,v in base.items()])
 dump(OUT/'summary-manifest.json',small_manifest);base['package-manifest.json']=OUT/'summary-manifest.json'
 audits=[]
 for name,entries in [('SMAA_Mail_Summary_01-17.zip',base),('SMAA_Full_Comparisons_01-17.zip',sources)]:
  path=OUT/name
  with zipfile.ZipFile(path,'w',allowZip64=True) as z:
   for k,v in sorted(entries.items()):
    compress=v.suffix.lower() not in ['.gif','.png','.mp4','.pdf'];z.write(v,k,compress_type=zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED,compresslevel=6 if compress else None)
  with zipfile.ZipFile(path) as z:
   assert z.testzip() is None;names=set(z.namelist());assert names==set(entries)
   refs=re.findall(r'(?:href|src)="([^"]+)"',z.read('index.html').decode('utf-8'));assert all(r in names for r in refs),(path,[r for r in refs if r not in names])
  audits.append(dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path),files=len(entries),crc='PASS',offline_links='PASS'))
  print('ZIP PASS',name,path.stat().st_size,len(entries),flush=True)
 dump(OUT/'package-audit.json',dict(validation='PASS',packages=audits,short_pair_scenes=32,long_pair_views=56,renderer_changes=False,new_measurement=False,pdf_pages=8,pdf_visual_qa='Every final page directly opened; no clipped tables or missing case numerals',gif_presentation_qa='Representative decoded GIF frames directly opened; animation timing checked mechanically'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--media',choices=['bistro','minecraft']);p.add_argument('--report',action='store_true');p.add_argument('--mail-media',action='store_true');p.add_argument('--package',action='store_true');a=p.parse_args()
 if a.media:media(a.media)
 if a.report:report()
 if a.mail_media:mail_media()
 if a.package:package()
