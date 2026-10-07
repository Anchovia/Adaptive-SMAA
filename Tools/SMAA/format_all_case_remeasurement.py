"""Create Korean comparison tables and a local two-way image gallery."""
import csv,html,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Deliverables/SMAA_All_17_Remeasurement_20261007'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,s):Path(p).write_text(s,encoding='utf-8')
def main():
 plan=load(ROOT/'tmp/all-case-remeasurement/manifest.json');perf=load(OUT/'performance.json');qual=load(OUT/'quality.json')
 assert len(perf)==34 and len(qual)==34
 pp={(r['scene'],r['case']):r for r in perf};qq={(r['scene'],r['case']):r for r in qual}
 runs=load(ROOT/'tmp/all-case-remeasurement/runs.json');assert len(runs)==102
 def cell(r):return '—' if r is None else f"{r['ms']:.5f} ({r['percent']:+.2f}%)"
 lines=['①~⑰ 속도·품질 재측정','',
  'RTX 3060 Ti · DX11 Release x64 · Original SMAA Ultra · 1920×1061 · hidden/windowed · VSync Off.',
  '장면별 300 warm-up + 4,800프레임 × 6회. 순서를 정방향/역방향으로 교차했다. 각 번호의 독립 소스와 실행 파일에서 원본 ④를 짝 측정했다.',
  '괄호는 해당 실행의 ④ 대비 시간 변화율이다. 음수는 시간 감소, 양수는 시간 증가다. ①의 AA 0은 AA 작업 자체가 없다는 의미이며 전체 렌더링 시간은 0이 아니다.','',
  '| 번호·구현 | Bistro 전체 AA ms | Minecraft 전체 AA ms |','|---|---:|---:|']
 for item in plan['cases']:
  c=item['case'];lines.append(f"| {c:02d} {item['label']} | {cell(pp['bistro',c]['AA'])} | {cell(pp['minecraft',c]['AA'])} |")
 lines+=['','Temporal 결합 단계만 비교한 시간이다. Camera velocity 생성과 공간 처리·선택 준비 비용은 포함하지 않는다.','','| 번호 | Bistro temporal ms | Minecraft temporal ms |','|---|---:|---:|']
 for item in plan['cases']:
  c=item['case'];lines.append(f"| {c:02d} | {cell(pp['bistro',c]['temporal'])} | {cell(pp['minecraft',c]['temporal'])} |")
 lines+=['','아래는 같은 프레임의 supersample **공간 참조 대용값**과 비교한 결과다. Temporal ground truth가 아니며, 점수로 반짝임·선 소실·잔상이 해결됐다고 판정하지 않는다.',
  '이동: f60~179. 정지 전환: f180~209. SSIM은 encoded Rec.709 luma, Gaussian 11×11/σ1.5, 가장자리 5픽셀 제외다. PSNR·SSIM은 높을수록 해당 참조에 가깝다.','','| 번호 | Bistro 이동 PSNR / SSIM | Minecraft 이동 PSNR / SSIM | Bistro 전환 PSNR | Minecraft 전환 PSNR |','|---|---:|---:|---:|---:|']
 for item in plan['cases']:
  c=item['case'];b=qq['bistro',c];m=qq['minecraft',c]
  lines.append(f"| {c:02d} | {b['moving']['psnr']:.3f} / {b['moving']['luma_ssim']:.5f} | {m['moving']['psnr']:.3f} / {m['moving']['luma_ssim']:.5f} | {b['transition']['psnr']:.3f} | {m['transition']['psnr']:.3f} |")
 lines+=['','④ 대비 고정 ROI의 움직임 보정 잔차 변화율. 낮을수록 이 보조 지표의 시간 변화가 적다. 공통 flow는 temporal을 사용하지 않는 ②에서 추정했다. 각 ROI에 32픽셀 여유 영역, Farneback, forward/backward 오차 ≤1픽셀·화면 내 유효 조건을 사용했다. 물체 추적이나 절대 고스팅 지표가 아니다.','','| 번호 | Bistro 의자 가는 구조 | Minecraft 얇은 경계 | Minecraft 나뭇잎 |','|---|---:|---:|---:|']
 with (OUT/'roi-temporal-diagnostics.csv').open(encoding='utf-8-sig',newline='') as f:rr=list(csv.DictReader(f))
 def residual(scene,c,roi):return float(np.mean([float(r['aligned_residual']) for r in rr if r['scene']==scene and int(r['case'])==c and r['roi']==roi and r['phase']=='moving' and r['aligned_residual']]))
 for item in plan['cases']:
  c=item['case'];vals=[(residual(s,c,r)/residual(s,4,r)-1)*100 for s,r in [('bistro','thin-chair'),('minecraft','thin-seam'),('minecraft','leaves')]]
  lines.append(f"| {c:02d} | {vals[0]:+.2f}% | {vals[1]:+.2f}% | {vals[2]:+.2f}% |")
 lines+=['','실행 조건','',
  '- ③·④: 원본 paired projection jitter / subsample pattern On. ⑤~⑰: pattern Off. 따라서 전체 차이를 후보 선택 효과만으로 해석할 수 없다.',
  '- 모든 temporal 구성은 camera/depth reprojection이다. Object motion velocity, 후보 확장, Adaptive 공간 처리의 결합은 이번 범위에 포함하지 않는다.',
  '- ⑦은 기존 depth 방식, ⑧은 당시 비용 감사의 FirstStencil 방식, ⑨는 velocity integer Load 방식이다. 서로 다른 번호로 보존했다.',
  '- ⑫은 ValidatedRGB 정책이며 ResponsiveRGB·ClippedRGB 진단 정책을 ⑫의 결과로 섞지 않았다.',
  '- ⑮ clipping, ⑯ sampling, ⑰ 색 혼합은 각각 ⑭에 한 항목만 변경한 구현이다.',
  '- 프로덕션 SMAA C++/HLSL 소스는 각 pinned branch의 원본을 보존했다. 측정 도구는 대상·④만 순회, 6회 반복, RGB 캡처에서 진단 DDS 생략으로만 조정했다.',
  '- 최초 ④ 실행은 작업 경로 길이 때문에 장면 자료를 읽지 못해 중단했다. 정식 결과에서 제외하고 짧은 경로에서 다시 시작했다.',
  '- 정식 실행은 매 명령 앞뒤 CMAA2 프로세스 0개, 독립 프로세스, 1,200초 timeout 및 Aggregate PASS를 확인했다.',
  '- 성능 실행에는 PNG 저장·진단 query·GPU readback이 없다. 품질 분석은 성능 실행이 모두 끝난 후 수행했다.',
  '- GPU 실행 파일·장면 자료·원본 캡처는 Git에 올리지 않는다. 실행 파일/생산 소스/결과 CSV 해시는 별도 provenance에 기록했다.','']
 inspection=OUT/'visual-inspection.json'
 if inspection.exists():
  v=load(inspection);lines+=['원본 프레임 직접 검사','']+[f'- {x}' for x in v['findings_ko']]+['']
 write(OUT/'comparison.md','\n'.join(lines))
 manifest={str(c):{s:str(next(r for r in runs if r['case']==c and r['scene']==s and r['phase']=='Capture')['report']) for s in ('bistro','minecraft')} for c in range(1,18)}
 (OUT/'capture-reports.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 media=['<!doctype html><meta charset="utf-8"><title>①~⑰ 재측정</title><style>body{background:#171717;color:#eee;font:16px/1.6 sans-serif;max-width:1300px;margin:24px auto}img{max-width:100%;height:auto}details{padding:8px;border:1px solid #555}a{color:#9cf}pre{white-space:pre-wrap}</style><h1>①~⑰ 재측정</h1><pre>'+html.escape('\n'.join(lines))+'</pre>']
 for s in ('bistro','minecraft'):
  media.append('<h2>'+s+'</h2>')
  for c in range(1,18):
   if c==4:continue
   media.append(f'<details><summary>④ vs {c:02d}</summary>')
   for roi in (['thin-chair','windows'] if s=='bistro' else ['thin-seam','leaves','grass-seam']):
    name=f'{s}-{roi}-4-vs-{c}'
    media.append(f'<h3>{roi}</h3><img loading="lazy" src="frames/{name}.gif"><p><a href="frames/{name}.png">연속 원본 프레임 비교</a></p>')
   media.append('</details>')
 write(OUT/'comparison.html','\n'.join(media))
 print('PASS: full 17-case tables and gallery')
if __name__=='__main__':main()
