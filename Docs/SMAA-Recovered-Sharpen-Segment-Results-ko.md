# 확보 소스 기반 sharpening × segment clipping 분리 실험 결과

날짜: 2026-09-15. 기준 커밋 `d54c11a`, 실험 구현 `ffcf433`, DX11 수명주기 수정 `3e540f6`.
브랜치: `research/tscmaa-sharpen-segment-ablation`.

**결론: segment 방식은 이동 중 일부 지표를 개선했지만, 기존 document temporal kernel과의 큰 품질 격차는 남았다. Sharpening 제거도 일관된 추가 이득이 없었다.** 기존 kernel을 중심 연구 구현으로 유지하고, 소스 기반 clipping의 추가 탐색은 이번 범위에서 마무리한다. 이번 옵션은 비교용으로 보존하며 기본 8-case 설정을 바꾸지 않는다.

## 실험 범위

앞선 signed chroma와 YCoCg clipping 교정을 공통 기준으로 고정하고, 통계 계산용 중심
픽셀 sharpening과 history 제한 방식만 2×2로 바꿨다. 후보식·후보 목록·실행 구조와
history sampling/weight/feedback을 유지했으므로 이 네 조합 안에서는 두 clipping
요인의 효과를 분리할 수 있다. 기존 Standard/document 대조군과의 차이는 여러 설정을
포함하므로 후보 선택 한 가지의 효과로 해석하지 않는다.

| 조합 | 중심 표본 sharpening | clipping |
|---|---:|---|
| Sharpen-Component | 0.263157904 | YCoCg 성분별 clamp |
| NoSharpen-Component | 0 | YCoCg 성분별 clamp |
| Sharpen-Segment | 0.263157904 | 현재색→history 방향 제한 |
| NoSharpen-Segment | 0 | 현재색→history 방향 제한 |

Original SMAA Ultra, source RGB candidate, first-edge-pass 통합, threshold 1/22,
removal 0.5, CompactIndirect, **확장 None**, camera/depth reprojection On,
object velocity Off, jitter Off를 고정했다. source 5-fetch, 검은 border sampling,
UNORM 색 처리, weight 0.789473712, square/sqrt 혼합과 ResolvedOutput feedback도 유지했다.
따라서 원본 CMAA 공간 처리를 포함한 Intel TSCMAA의 완전한 재현은 아니다.

Segment anchor는 강조 전 현재색이다. 중심 강조는 variance 통계에만 영향을 준다.
Document 방식의 관측 min/max 교집합, 다른 주변 sampling, 색 공간/혼합 경로는 가져오지 않았다.
Source Co/Cg가 document의 절반 크기이므로 해당 축 epsilon도 절반으로 환산했다.
Anchor가 box 밖일 때 결과의 box 내부 보장은 없다. 이를 별도 anchor 보정으로 바꾸지는 않았다.

## 비교 조건과 검증

- Bistro/Minecraft 각각 네 조합 × 480프레임, 총 3,840프레임을 동일 수정 후 실행파일에서 확보했다.
  1920×1017, DirectX11 Release x64, VSync Off, fixed 60Hz,
  `flythrough-wide-yaw-360`, 동일 첫 pose 60-frame warm-up이다.
- 중앙 이동 150–329, 이동→정지 410–439, 후기 정지 440–479를 구분한다.
  Supersample은 동일 pose의 spatial-reference proxy이며 절대 temporal/고스팅 정답은 아니다.
- CGVQM-2는 Intel commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`, CUDA,
  60FPS, patch scale 4/mean pooling이다. FFV1/bgr0 입력 전체 RGB round-trip을 검증한다.
  이전 교정 기준의 점수는 새 캡처와 reference의 window hash가 일치할 때만 재사용한다.
  새 옵션 세 조합은 새로 계산한다. Heatmap 영상 인코딩만 생략하고 error-map 통계는 계산했다.
- GPU production-function probe는 35×29의 8 fixture를 네 조합별 두 번 실행했다.
  후보/샘플러 및 독립 반복은 동일하며, 동일 GPU history 입력에서 CPU clipping 최대 오차는
  0.000173 미만, 최종 중심 RGB 오차는 2LSB 이내였다.
- 원본 기본과 이전 교정 control의 Extract/Resolve DXBC를 모두 보존했다.
  네 조합의 resolve instruction slots는 227/222/246/241이다. GPU 시간으로 환산하지 않는다.
- 후보 mask 및 비후보 변경은 0, short/full 독립 prefix 96프레임도 일치했다.
  DX11 수정 전 유효 20개 명령의 2,112프레임과 수정 후 대응 캡처도 모두 RGB가 일치했다.
- 기존 8개 모드 96프레임이 기존 회귀 기준과 일치했다. Lifecycle은 failures 0,
  feedback의 output/history/visible mismatch 및 previous-history hash mismatch 모두 0이다.
  수명주기 수정 후 24개 capture + 3개 regression 명령은 모두 정상 clean 종료했다.

GPU subtexel sampling과 이상적 CPU sampling을 합성하면 outside anchor의 거의 0인
방향 부호가 바뀌어 segment 결과가 크게 달라질 수 있었다(합성 fixture 최대 약 0.395105).
이는 실제 장면 오류율이나 최종 영상의 최대 오차가 아니다. Sampling 자체를 0.005 미만으로
검사하고 동일 history 입력의 clipping을 별도로 검증했으며, 발견한 민감성을 숨기지 않고 기록한다.

## CGVQM-2 결과

높을수록 좋다. 같은 입력 hash의 기준 점수 3개는 재사용하고, 새 옵션 12개와 Minecraft 전환 기준 1개는 새로 계산했다.

| 장면·구간 | Sharpen-Component | NoSharpen-Component | Sharpen-Segment | NoSharpen-Segment |
|---|---|---|---|---|
| bistro 중앙 이동 | 88.653961 | 88.623459 | 89.115738 | 89.066757 |
| bistro 이동→정지 | 94.484528 | 94.460411 | 94.034149 | 94.019989 |
| minecraft 중앙 이동 | 90.536331 | 90.498779 | 90.661987 | 90.642632 |
| minecraft 이동→정지 | 93.601799 | 93.547211 | 93.563477 | 93.562225 |

기준 조합 대비 변화다. Sharpening을 유지한 segment와 sharpening 제거를 결합한 segment를 구분한다.

| 장면·구간 | 강조만 제거 | Segment만 적용 | 둘 다 적용 |
|---|---|---|---|
| bistro 중앙 이동 | -0.030502 | +0.461777 | +0.412796 |
| bistro 이동→정지 | -0.024117 | -0.450378 | -0.464539 |
| minecraft 중앙 이동 | -0.037552 | +0.125656 | +0.106300 |
| minecraft 이동→정지 | -0.054588 | -0.038322 | -0.039574 |

같은 reference hash의 **과거 대조군**과 비교하면 다음과 같다. 대조군을 이번에 새로 캡처한 것으로 표현하지 않는다.

| 장면·구간 | 이번 네 조합 중 최고 | Standard O-T2X-R | 기존 후보+기존 kernel | Source 후보+기존 kernel | 동일 source 후보 대조 대비 |
|---|---|---|---|---|---|
| bistro 중앙 이동 | 89.115738 | 94.133018 | 96.688576 | 96.615211 | -7.499474 |
| bistro 이동→정지 | 94.484528 | 95.126778 | 94.560982 | 94.627953 | -0.143425 |
| minecraft 중앙 이동 | 90.661987 | 95.986458 | 97.515762 | 97.722359 | -7.060371 |
| minecraft 이동→정지 | 93.601799 | 94.646790 | 93.739021 | 93.993668 | -0.391869 |

Source 후보+기존 kernel과 비교해도 격차가 남으므로, 이번 두 clipping 항목만으로 source kernel의 열세를 설명하거나 해결할 수 없다. 이것은 Intel TSCMAA 전체가 열등하다는 결론이 아니라 현재 SMAA adaptation의 한계다.

## 프레임별 reference 오차와 시간 변화

RGB MAE는 0–255 범위의 채널 평균 오차다. 낮을수록 spatial reference에 가깝다.

| 장면·구간 | Sharpen-Component | NoSharpen-Component | Sharpen-Segment | NoSharpen-Segment |
|---|---|---|---|---|
| bistro 중앙 이동 | 1.709660 | 1.711442 | 1.630584 | 1.628503 |
| bistro 이동→정지 | 1.515523 | 1.518889 | 1.518028 | 1.518633 |
| bistro 후기 정지 | 1.507557 | 1.510413 | 1.514141 | 1.514980 |
| minecraft 중앙 이동 | 0.948219 | 0.950054 | 0.921431 | 0.920456 |
| minecraft 이동→정지 | 1.515374 | 1.522284 | 1.521307 | 1.522975 |
| minecraft 후기 정지 | 1.548721 | 1.553453 | 1.562664 | 1.564761 |

Temporal-delta residual은 `(test_t-test_(t-1))-(ref_t-ref_(t-1))`의 절대 평균이며, window 첫 프레임에도 직전 timeline 프레임을 사용한다. Optical-flow 보정값이나 절대 flicker 점수가 아니다.

| 장면·구간 | Sharpen-Component | NoSharpen-Component | Sharpen-Segment | NoSharpen-Segment |
|---|---|---|---|---|
| bistro 중앙 이동 | 2.68484272 | 2.68805694 | 2.54556098 | 2.54241253 |
| bistro 이동→정지 | 0.25558028 | 0.25585910 | 0.25728988 | 0.25772166 |
| bistro 후기 정지 | 0.00001208 | 0.00001209 | 0.00001215 | 0.00001212 |
| minecraft 중앙 이동 | 1.45241394 | 1.45689438 | 1.42688168 | 1.42641818 |
| minecraft 이동→정지 | 0.23116204 | 0.23160334 | 0.23414667 | 0.23474034 |
| minecraft 후기 정지 | 0.00000038 | 0.00000006 | 0.00000004 | 0.00000004 |

두 지표가 함께 좋아지는 중앙 이동에서도 CGVQM은 기존 kernel보다 낮았다. RGB 오차가 조금 낮아도 CGVQM 순위가 다를 수 있으므로 단일 지표만으로 최적 조합을 고르지 않는다. PSNR과 두 요인의 주효과·상호작용 수치는 quality.json 및 cgvqm.json에 보존한다.

## 연속 영상과 시각적 확인

- bistro: 최대 조합 차이 frame 313, 고정 화면 ROI [1040, 112, 1360, 336]. [이동 비교](Recovered-Sharpen-Segment-20260915/bistro-motion.mp4), [정지 전환 비교](Recovered-Sharpen-Segment-20260915/bistro-transition.mp4), [대표 crop](Recovered-Sharpen-Segment-20260915/bistro-peak-crop.png).
- minecraft: 최대 조합 차이 frame 222, 고정 화면 ROI [1600, 504, 1920, 728]. [이동 비교](Recovered-Sharpen-Segment-20260915/minecraft-motion.mp4), [정지 전환 비교](Recovered-Sharpen-Segment-20260915/minecraft-transition.mp4), [대표 crop](Recovered-Sharpen-Segment-20260915/minecraft-peak-crop.png).

영상은 10FPS, 실제 60Hz timeline 대비 6배 느린 육안 확인용 H.264이며 지표 입력이 아니다. ROI는 중앙 이동에서 Sharpen-Component와 NoSharpen-Segment의 차이가 큰 위치를 선택했으므로 대표성 있는 무작위 표본으로 해석하지 않는다. Bistro 조명·유리잔과 Minecraft 잎 경계에서 reference와의 차이가 네 조합에 공통으로 남았다. 이 화면 차이를 모두 고스팅으로 분류하지 않는다.

## 성능과 채택 판단

이번 gate는 품질상 기존 구현을 대체할 근거를 확보하지 못해 사전 계획에 따라 반복 성능 본 측정을 확대하지 않았다. 따라서 이번 변경의 GPU 시간 개선·동등·악화를 주장하지 않는다. 정적 instruction 수나 후보 수를 속도로 환산하지 않는다.

기존 document kernel을 핵심 후보로 유지하고 소스 기반 네 옵션은 분석용으로 보존한다. 다음 핵심 선택은 기존 후보+기존 kernel과 source 후보+기존 kernel의 품질 및 **전체 AA 비용**을 같은 조건에서 확인하는 것이다. 그 뒤에 선택한 구현을 고정해 3×3/Dual Filter를 별도 옵션으로 다룬다. 확장은 이번 결과에 포함되지 않는다.

## 실행 실패와 검증 예외 기록

- 시작 단계 앱 종료 두 건은 점수에서 제외했다. 비동기 컴파일 완료 전에 concrete DX11 shader가 해체되는 결함을 별도 커밋으로 수정했다. 이후 27개 독립 명령은 정상 종료했다. [상세 근거와 한계](SMAA-DX11-Shader-Lifetime-Fix-ko.md)를 참조한다. 이전 블루스크린의 원인 증명은 아니다.
- 최초 Release 빌드는 실행 중인 캡처와 겹쳐 실행파일 lock으로 실패했다. 캡처 종료 뒤 단독 빌드는 통과했고, 빌드 전 자료는 별도 보존했다. 최종 gate에는 같은 수정 후 실행파일만 사용했다.
- Minecraft frame 436의 최초 baseline hash 검사는 실패했지만 당시 배열을 보존하지 못했다. 이후 430–479 재대조, frame 436의 독립 5회 PNG/RGB 대조 및 전체 480-frame 재분석은 모두 일치했다. 최초 원인은 미확정이며 동일성 기준은 완화하지 않았다. 이후 실패 시 실제 배열을 저장하도록 보강했고, Minecraft 전환 기준 CGVQM도 독립 재계산하여 이전과 같은 93.601799점(차이 0)을 확인했다.
- Minecraft NoSharpen-Segment 중앙 구간의 최초 FFV1은 308번 frame (x=1276,y=816)의 B 한 채널이 205 대신 77로 복원됐다. 두 검사와 별도 decode에서 재현되어 점수 계산 전에 제외했다. 실패 변환본을 보존하고 단일 프레임 독립 변환 두 번 및 전체 재변환을 검증했다. 재변환된 180프레임을 별도 프로세스에서 한 번 더 decode해 전체 RGB 일치를 확인했다. 최종 입력은 RGB mismatch 0인 파일만 사용했다. 변환 오류의 원인은 미확정이며 알고리즘/GPU/RAM 탓으로 단정하지 않는다.

실패 변환본의 최초 기록 SHA-256도 보존 후 파일과 일치하지 않았다. 현재 파일은 Python의 streaming/전체 읽기 세 쌍과 별도 PowerShell hash가 모두 일치했다. 최초 기록과 재검증 값을 모두 보존했으며 원인은 미확정이다. 이 파일은 점수에 사용하지 않은 실패 증거이고, 그 불일치를 최종 영상의 품질 차이로 해석하지 않는다.

## 재현 자료

[실험 프로토콜](SMAA-Recovered-Sharpen-Segment-Protocol-ko.md), [품질 지표와 실행 hash](Recovered-Sharpen-Segment-20260915/quality.json), [CGVQM 및 과거 대조군](Recovered-Sharpen-Segment-20260915/cgvqm.json), [픽셀 검증](Recovered-Sharpen-Segment-20260915/verify.json), [GPU 함수 검사](Recovered-Sharpen-Segment-20260915/validation.json), [회귀 검사](Recovered-Sharpen-Segment-20260915/regressions.json), [실행 예외](Recovered-Sharpen-Segment-20260915/incidents.json).

실행 도구는 Tools/SMAA의 validate/run/analyze_recovered_sharpen_segment 계열이다. 앱 캡처, 회귀, CGVQM은 순차 GPU 실행하며 각 CMAA2 명령은 독립 프로세스와 timeout을 사용한다. 원시 AutoBench/FFV1 및 crash dump는 로컬에 보존한다. Shader 스위치 네 개는 모두 default 0, 사용자 ApplicationSettings 전체 bytes는 원복했다.
