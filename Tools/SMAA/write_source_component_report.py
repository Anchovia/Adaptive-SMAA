from pathlib import Path
import json,argparse,subprocess
ROOT=Path(__file__).resolve().parents[2]
DOC=next(p for p in (ROOT/'Docs').glob('Edge-History-Source-*') if (p/'case.json').exists())
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
info=load(DOC/'case.json');case=info['case'];mode=info['semantic_id'];base=info['controls'][0]
parser=argparse.ArgumentParser();parser.add_argument('--judgment',required=True);args=parser.parse_args()
lines=[f'# ⑭ 기준의 {case}번 {info["component"]} 단독 비교', '',args.judgment,'',f'브랜치: `{info["branch"]}`. 직접 기준: ⑭ `{info["base_commit"]}`. 새로운 clipping/sampling/blend 세 항목은 각각 독립이며 결합하지 않았다. 후보 선택식은 변경하지 않았다.','', '## GPU 성능','', 'RTX 3060 Ti / DX11 Release x64 / Ultra / 1920×1061 / hidden / VSync Off. Scene별 동일 프로세스의 ④·⑭·새 구현을 300 warm-up + 4,800 frame×6회 정/역 순서로 반복했다. PNG·readback·진단 query Off. 변화율은 같은 run의 대조군으로 계산한 평균이며 실행 사이 절대시간을 분모로 섞지 않았다.','', '| 장면 | 방식 | 전체 AA ms | ④ 대비 | ⑭ 대비 | temporal ms | temporal ④ 대비 | temporal ⑭ 대비 |','|---|---|---:|---:|---:|---:|---:|---:|']
all_results={}
for scene in ['bistro','minecraft']:
 p=load(DOC/f'{scene}-benchmark.json');q=load(DOC/f'{scene}-capture.json');assert p['validation']==q['validation']=='PASS'
 all_results[scene]=dict(performance=p,quality=q)
 index={(s['mode'],s['metric']):s for s in p['summary']}
 for m,label in [('O-T2X-R','④ T2X-R'),(base,'⑭ fixed0.8'),(mode,f'{case} {info["component"]}')]:
  a=index[m,'SMAA'];t=index[m,'SR_Resolve'];lines.append(f'| {scene} | {label} | {a["mean_ms"]:.6f} | {a["native4_paired_percent"]:+.2f}% | {a["case14_paired_percent"]:+.2f}% | {t["mean_ms"]:.6f} | {t["native4_paired_percent"]:+.2f}% | {t["case14_paired_percent"]:+.2f}% |')
lines+=['','## 品질 수치와 프레임 검사'.replace('品質','품질'),'','Supersample spatial proxy에 대한 RGB MAE(0~255, 낮을수록 작음)와 raw luma 2차 시간 차분(낮을수록 작음)을 함께 기록했다. 차분 감소는 blur와 motion의 영향도 포함해 반짝임/고스팅 해결을 단독 입증하지 않는다. CGVQM을 새로 실행한 결과가 아니다. ④는 paired Pattern On, ⑭와 새 구현은 Off이다.','', '| 장면 / 이동 ROI | ⑭ 참조 MAE | 새 MAE | ⑭ 2차 차분 | 새 2차 차분 |','|---|---:|---:|---:|---:|']
for scene in ['bistro','minecraft']:
 q=all_results[scene]['quality'];rois=['thin-chair','windows'] if scene=='bistro' else ['thin-seam','leaves','grass-seam']
 for roi in rois:
  a=next(r for r in q['roi_metrics'] if r['roi']==roi and r['window']=='moving' and r['mode']==base)
  b=next(r for r in q['roi_metrics'] if r['roi']==roi and r['window']=='moving' and r['mode']==mode)
  lines.append(f'| {scene}/{roi} | {a["reference_rgb_mae"]:.4f} | {b["reference_rgb_mae"]:.4f} | {a["luma_second_delta"]:.4f} | {b["luma_second_delta"]:.4f} |')
lines+=['','두 장면 각각 240 frame의 ④·⑭ RGB는 기존 검증 자료와 byte-hash mismatch 0이었다. Same-draw current/raw/velocity/edge/coverage도 ⑭와 새 구현 사이 mismatch 0. 24개 진단 frame의 selected weight0.8, nonselected current output, feedback RGB/current alpha와 연속 history chain 검증을 통과했다. Test에서는 first frame와 frame3 reset을 검사했다.','', '32 shader entry compile 중 기존 28개 DXBC byte 일치. 독립 CPU 식과 실제 helper의 GPU fixture 결과는 numeric-gpu-audit.json에 있다. Fixtures의 허용 오차는 GPU의 sRGB 변환/보간 정밀도를 포함하며 pixel-exact 계산이라고 표현하지 않는다.','', '원본 full frame, 이동126~131 / 전환178~183 / 안정210~215의 nearest 2배 연속 프레임을 검사했다. 영상·GIF는 원본 PNG를 사용한 확인용이며 손실이 있다. Animated playback을 직접 시청한 것으로 표현하지 않는다. ROI는 화면 고정 영역이며 object tracking이 아니다.','', '## 구현과 원본 차이','']
for diff in info.get('source_differences',[]):lines.append('- '+diff)
lines+=['','자세한 조건: method.md / 재현: Tools/SMAA/run_source_temporal_component.ps1 / 성능 raw CSV와 JSON: 같은 디렉터리 / 품질: scene-capture.json, scene-quality-per-frame.csv.','']
(DOC/'report.md').write_text('\n'.join(lines),encoding='utf-8')
dest=ROOT/f'Deliverables/SMAA_15_16_17_20261007/Evidence/case{case}';dest.mkdir(parents=True,exist_ok=True)
for p in DOC.iterdir():
 if p.is_file():(dest/p.name).write_bytes(p.read_bytes())
print('PASS report and preserved evidence',case)
