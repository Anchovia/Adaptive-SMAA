"""Summarize fixed first-edge quality measurements and viewing artifacts."""
import json,statistics as st
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'Docs/Temporal-First-Edge-Quality';B=ROOT/'Projects/CMAA2/AutoBench/FirstEdgeQuality'
N='O-T2X-R';S='ABL-FirstEdge-Reuse-R'
q={s:json.loads((D/f'{s}-quality.json').read_text()) for s in ['bistro','minecraft']};c={s:json.loads((D/f'{s}-cgvqm.json').read_text()) for s in q}
assert len({x['receipt']['executable_sha256'] for x in q.values()})==1
for x in q.values():assert x['validation']=='PASS' and x['selection_mismatches']==0 and x['pattern_checks']==1200
for x in c.values():assert x['validation']=='PASS'
lines=['# 실제 첫-pass edge 선택 T2X-R 품질 결과','',
'현재 구현은 원본 T2X-R보다 두 장면 모두 정지 안정성이 떨어졌고, 공간 참조 오차가 증가했다.',
'Bistro의 GPU 성능 개선은 앞 gate에서 확인했지만, 현재 edge만 선택하는 방식은 비edge 픽셀의',
'지터를 안정화하지 못한다. 기본 원본을 교체할 품질 근거를 얻지 못했다. 알고리즘은 수정하지 않았다.',
'', '## 정지 떨림','',
'RGB 변화는 인접 프레임의 0~255 RGB 채널 평균 절대 차이다. 지각적 품질 감소율이 아니다.',
'후기 정지 200~239 frame을 분석했다. 두 장면 모두 원본은 같은 RGB 영상 1개로 고정되고,',
'선택적 구현은 A/B 두 영상이 교대로 반복된다. 2-frame 간격 hash 불일치는 0이다.',
'', '| 장면 | 원본 정지 RGB 변화 | Edge 선택 RGB 변화 | 두 위상 모두 선택 % | 계속 비선택 % | 선택 전환 % |','|---|---:|---:|---:|---:|---:|']
for s,v in q.items():
 g=v['late_still_groups'];w=v['windows']['late_still']
 lines.append(f"| {s} | {w[N]['rgb_step']:.6f} | {w[S]['rgb_step']:.6f} | {g['always_selected']['area_percent']:.3f} | {g['always_unselected']['area_percent']:.3f} | {g['selection_switches']['area_percent']:.3f} |")
lines+=['','선택 영역 분해는 후기 정지의 201~239 인접 pair다. 두 frame 모두 선택되는 영역의 RGB 변화는',
'두 장면 모두 0이었다. 계속 비선택인 영역과 선택이 바뀌는 영역이 전체 변화에 기여했다.',
'즉 edge 여부가 현재 frame에서 false라는 사실은 temporal 안정화가 필요 없다는 뜻이 아니었다.',
'', '| 장면 | 계속 비선택의 전체 변화 기여 | 선택 전환의 전체 변화 기여 | 합계 |','|---|---:|---:|---:|']
for s,v in q.items():
 g=v['late_still_groups'];a=g['always_unselected']['whole_frame_step_contribution'];b=g['selection_switches']['whole_frame_step_contribution'];lines.append(f'| {s} | {a:.6f} | {b:.6f} | {a+b:.6f} |')
lines+=['','## 공간 및 시간 지표','',
'동일 pose의 2x 선형 해상도, 3x3 subpixel grid, 8xMSAA supersampling spatial reference를 사용했다.',
'MAE/시간차 잔차는 낮을수록 참조에 가깝다. 윤곽비는 Sobel magnitude/reference이며 1에 가까워지는',
'것만으로 선명도 우위라고 판단하지 않는다. Aliasing도 윤곽 강도를 높일 수 있다.',
'시간차 잔차는 `(Yt−Yt-1)−(Ref_t−Ref_t-1)`의 평균 절댓값이며 절대 ghosting 점수가 아니다.',
'', '| 장면 | 구간 | 방식 | RGB MAE | PSNR dB | sampled luma SSIM | 윤곽/참조 | 시간차 잔차 |','|---|---|---|---:|---:|---:|---:|---:|']
for s,v in q.items():
 for window in ['moving','transition','late_still']:
  for m in [N,S]:
   x=v['windows'][window][m];lines.append(f"| {s} | {window} | {m} | {x['rgb_mae']:.6f} | {x['psnr_db']:.3f} | {x['luma_ssim']:.6f} | {x['edge_reference_ratio']:.4f} | {x['reference_delta_residual']:.6f} |")
lines+=['','SSIM은 매 10번째 frame 표본, 다른 지표는 각 구간 전체 frame이다. PSNR/SSIM은 frame별 값의 평균이다.',
'Moving은 60~179, transition은 160~219로 이동 후반과 정지 직후를 포함한다.',
'후기 정지에서는 60-frame 정지 구간이 끝날 때까지 두 위상 변동이 사라지지 않았다.',
'', '## CGVQM-2','', '| 장면 | 구간 | 원본 | Edge 선택 | 선택−원본 |','|---|---|---:|---:|---:|']
for s,v in c.items():
 for w,x in v['results'].items():lines.append(f"| {s} | {w} | {x['native_score']:.6f} | {x['selective_score']:.6f} | {x['selective_minus_native']:+.6f} |")
lines+=['','CGVQM-2는 높을수록 좋다. Intel 공식 commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`,',
'CUDA, 60FPS, patch_scale=4, patch_pool=mean을 사용했다. FFV1 RGB encode/decode pixel mismatch 0.',
'원본 네 점수는 기존 결과를 재사용했다. 현재 native/reference의 frame index를 포함한 pixel-stream SHA-256,',
'범위·해상도·설정·공식 commit·Torch/CUDA 버전의 일치를 확인했다. Selected 네 clip만 새로 실행했다.',
'이 점수는 공간 참조 영상에 대한 종합 영상 품질이며 순수 잔상 양 또는 temporal ground truth가 아니다.',
'', '## 영상과 관찰','',
'좌→우 순서는 **SS 공간 참조 / 원본 T2X-R / 현재 edge 선택 T2X-R**이다.',
'정속 MP4는 240 frame, 60FPS, 4초다. 확대본은 사전 지정 480x320 screen-fixed ROI를 원본 pixel 크기로 배치했다.',
'GIF는 0.5배속과 고정 palette를 사용했다. Loop 경계는 잔상으로 세지 않는다.',
'Bistro ROI는 의자 다리·메뉴판·바닥, Minecraft는 벽면·전경 구조물 경계를 포함한다.',
'', '| 장면 | 전체 화면 | 확대 정속 | 이동 반속 GIF | 정지 전환 GIF | 정지 후기 GIF |','|---|---|---|---|---|---|']
for s in q:
 p=lambda f:(B/s/f).as_posix()
 lines.append(f'| {s} | [MP4]({p("overview-60fps.mp4")}) | [MP4]({p("detail-60fps.mp4")}) | [GIF]({p("moving.gif")}) | [GIF]({p("transition.gif")}) | [GIF]({p("late-still.gif")}) |')
lines+=['','정지 frame 200/201의 8배 차이 이미지에서는 원본의 변화가 없고, 선택적 결과에 표면 texture와',
'얇은 구조의 변화가 남는 것을 확인했다. Minecraft 벽면 texture, Bistro 바닥과 얇은 의자 구조에서',
'이 차이를 볼 수 있다. 8배 차이는 가시화를 위한 증폭이며 실제 밝기 변화 크기는 위 RGB 지표로 본다.',
'이동 연속 crop에서는 edge 선택 결과의 texture와 일부 경계가 더 날카롭게 보이지만,',
'그것이 세부 보존인지 aliasing 증가인지는 윤곽 하나로 구분할 수 없다. 뚜렷한 잔상 감소는 확정하지 못했다.',
'영상 생성과 frame/FPS/PTS 검증을 완료했으며, 여기서의 육안 관찰은 연속 PNG/차이 이미지 검토다.',
'동영상은 사용자가 정속으로 확인할 수 있도록 제공하며 사용자 지각 실험을 실시한 것은 아니다.',
'독립 물체 운동, 단독 회전, 추적 ROI 및 disocclusion ground truth는 이번 평가에 포함하지 않았다.',
'', '## 검증과 성능 결과 연결','',
'- 두 장면 각각 5 mode x 240 PNG, 총 2,400장. 전체 capture 구간 pattern 검사 2,400개 PASS.',
'- Native/reference-native/과거 native, current-spatial 및 selected repeat의 hash bridge 총 1,920회 PASS.',
'- 이전 성능 gate의 selected/raw sparse frame bridge 총 40회 PASS. 모든 480 frame에서 selected=native, nonselected=current RGB exact.',
'- RGB PNG는 alpha를 저장하지 않는다. GPU alpha byte 정확성을 PNG로 검증했다고 표현하지 않는다.',
'- Renderer shader는 `be93be3` 고정. Native 8개 DXBC, 기존 controls와 selected 소스는 바뀌지 않았다.',
'- 연속 capture command만 추가했다. Original 공간, camera/depth R On, paired jitter, spatial-frame history 유지.',
'- Capture는 fresh process/timeout/완성 PASS/잔류 process 0 확인. 품질 작업에 GPU 성능 측정을 섞지 않았다.',
'- 기존 속도 gate에서 Bistro 전체 AA -2.478%, Minecraft +1.234%였다. 이번 품질 결과를 합치면',
'  현재 구현을 두 장면에서 품질을 보존하는 일관된 성능 개선이라고 결론낼 수 없다.',
'', '## 데이터와 재현','',
'브랜치 `experiment/temporal-first-edge-selective`, 계획 `b0e5db3`, capture/분석 코드 `c9cd92c`.',
'`*-quality.json`, `*-cgvqm.json`, frame별 품질/후보/정지 영역 CSV에 지표와 provenance를 기록했다.',
'`run_temporal_first_edge_quality.ps1`로 장면별 capture 후 `analyze_temporal_first_edge_quality.py`,',
'`run_temporal_first_edge_cgvqm.py`, 이 요약 도구를 순서대로 실행한다.',
'PNG/MP4/GIF/AutoBench 원본과 lossless 중간 영상은 로컬에 보존하고 Git에는 코드와 정량 결과를 넣는다.','']
(D/'report.md').write_text('\n'.join(lines),encoding='utf-8');print('PASS: first-edge quality report written')
