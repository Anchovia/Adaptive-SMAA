# 첫 edge 선택 구현의 품질 비교

①~⑥과 raw/spatial full-screen Pattern-Off 대조군을 같은 240-frame timeline과
supersample spatial reference로 비교했다. 알고리즘 코드는 변경하지 않았다.
기존 ②·④·⑤·⑥ 및 Off full 점수는 새 캡처와 RGB/index hash가 일치하는 범위에서
재사용했고, 빠져 있던 ①·③의 두 장면×두 구간 CGVQM-2를 새로 계산했다.

## CGVQM-2 전체 비교

높을수록 좋다. 이동=60~179, 전환=160~219, 60 FPS. 점수 하나로 잔상·깜빡임·선명도를
각각 판정하지 않는다. ⑤·⑥은 jitter/sample pattern Off이며 ③·④는 원본 pattern On이다.

| 구성 | Bistro 이동 | Bistro 전환 | Minecraft 이동 | Minecraft 전환 |
|---|---:|---:|---:|---:|
| 1 AA-Off | 95.8146 | 95.5780 | 95.3416 | 94.9866 |
| 2 Original SMAA 1X | 96.0628 | 95.8746 | 95.1725 | 94.9164 |
| 3 Full temporal / no spatial | 96.2490 | 96.7925 | 95.0927 | 96.2164 |
| 4 Original SMAA T2X-R | 96.1912 | 96.7193 | 93.9114 | 94.9057 |
| 5 Edge temporal / no spatial | 96.0332 | 95.6477 | 95.4060 | 94.9690 |
| 6 SMAA + edge temporal | 96.1734 | 95.9116 | 95.2341 | 94.8942 |
| Control raw full / jitter Off | 96.2200 | 95.7115 | 95.3286 | 94.9182 |
| Control SMAA full / jitter Off | 96.3548 | 95.9736 | 95.1213 | 94.8153 |

①·③의 품질 평가 누락은 이번에 채웠다. ③의 높은 점수를 공간 AA 생략이 항상
더 좋다는 결론으로 일반화하지 않는다. 이 장면·reference·지표에서 관측한 결과다.

## ⑥과 원본 ④의 차이 분리

원본 paired sample pattern에는 projection jitter와 spatial subsample-index 조합이
함께 포함된다. 아래는 실제 사용한 두 비교의 차이이며, 모든 상황에 독립적으로 적용되는
주효과나 통계적 유의성 주장이 아니다.

| 장면·구간 | ⑥ − 원본④ | Off full − 원본④ | ⑥ − Off full |
|---|---:|---:|---:|
| bistro moving | -0.0179 | +0.1635 | -0.1814 |
| bistro transition | -0.8076 | -0.7456 | -0.0620 |
| minecraft moving | +1.3227 | +1.2099 | +0.1128 |
| minecraft transition | -0.0116 | -0.0905 | +0.0789 |

⑥은 Bistro 이동에서 원본과 비슷하고 전환에서 낮았다. Minecraft 이동에서는 높았지만
전환에서는 거의 비슷했다. Minecraft 이동의 큰 차이는 대부분 full-screen 경로에서도
나타난 sample-pattern 변경 차이이며, 모두 edge 선택 효과로 설명할 수 없다.
같은 Off 조건의 edge 선택만 비교하면 Bistro는 낮고 Minecraft는 높아 장면 의존성이 남는다.

공간 AA가 없는 ⑤도 대응 기준선 ③과 비교하고, raw Off full 대조군으로 선택 효과를
따로 본다. 이 비교를 ④ 대비의 공간+temporal 최종 품질로 바꾸어 해석하지 않는다.

| 장면·구간 | ⑤ − ③ | Raw Off full − ③ | ⑤ − Raw Off full |
|---|---:|---:|---:|
| bistro moving | -0.2158 | -0.0290 | -0.1868 |
| bistro transition | -1.1448 | -1.0810 | -0.0639 |
| minecraft moving | +0.3133 | +0.2359 | +0.0774 |
| minecraft transition | -1.2474 | -1.2981 | +0.0508 |


## 전체 화면 참조 오차와 시간 변화

MAE는 낮을수록, SSIM은 높을수록 reference에 가깝다. Flow 잔차가 낮다는 것은
공통 SS-Reference flow로 정렬한 오류의 시간 변화가 작다는 뜻이다. 일정하게 유지되는
오류도 이 지표에서는 작을 수 있으므로 절대 고스팅 양이나 전체 품질 점수로 쓰지 않는다.
Reference 자체의 warp 잔차와 flow 유효 비율은 JSON에 함께 기록했다.

| 장면·구간 | 구성 | RGB MAE | PSNR dB | SSIM | Flow 오류 변화 |
|---|---|---:|---:|---:|---:|
| bistro moving | SMAA 1X | 0.6926 | 39.677 | 0.985567 | 0.6565 |
| bistro moving | Temporal-only / Pattern On | 0.7240 | 40.279 | 0.985533 | 0.6788 |
| bistro moving | Raw full / Pattern Off | 0.7201 | 39.664 | 0.985776 | 0.5886 |
| bistro moving | Raw edge / Pattern Off | 0.7100 | 39.344 | 0.984991 | 0.6492 |
| bistro moving | Original T2X-R | 0.7350 | 40.377 | 0.985581 | 0.6650 |
| bistro moving | Full / Pattern Off | 0.6976 | 40.464 | 0.986821 | 0.5544 |
| bistro moving | SMAA + edge / Pattern Off | 0.6829 | 40.136 | 0.986072 | 0.6150 |
| bistro transition | SMAA 1X | 0.7086 | 39.278 | 0.985389 | 0.2324 |
| bistro transition | Temporal-only / Pattern On | 0.6304 | 41.182 | 0.988985 | 0.2677 |
| bistro transition | Raw full / Pattern Off | 0.7503 | 38.607 | 0.984188 | 0.2177 |
| bistro transition | Raw edge / Pattern Off | 0.7464 | 38.485 | 0.983905 | 0.2342 |
| bistro transition | Original T2X-R | 0.6461 | 41.131 | 0.988773 | 0.2630 |
| bistro transition | Full / Pattern Off | 0.7112 | 39.525 | 0.985815 | 0.2048 |
| bistro transition | SMAA + edge / Pattern Off | 0.7053 | 39.408 | 0.985554 | 0.2205 |
| minecraft moving | SMAA 1X | 1.5174 | 34.733 | 0.982252 | 1.4877 |
| minecraft moving | Temporal-only / Pattern On | 1.7740 | 34.874 | 0.977705 | 1.5786 |
| minecraft moving | Raw full / Pattern Off | 1.7314 | 34.799 | 0.980113 | 1.2288 |
| minecraft moving | Raw edge / Pattern Off | 1.5850 | 34.520 | 0.981608 | 1.3997 |
| minecraft moving | Original T2X-R | 1.9874 | 34.352 | 0.972034 | 1.6198 |
| minecraft moving | Full / Pattern Off | 1.7557 | 35.185 | 0.979694 | 1.2230 |
| minecraft moving | SMAA + edge / Pattern Off | 1.5996 | 34.993 | 0.981348 | 1.3958 |
| minecraft transition | SMAA 1X | 1.5895 | 34.619 | 0.981697 | 0.5538 |
| minecraft transition | Temporal-only / Pattern On | 1.4405 | 36.316 | 0.985161 | 0.6599 |
| minecraft transition | Raw full / Pattern Off | 1.6950 | 34.028 | 0.979930 | 0.4821 |
| minecraft transition | Raw edge / Pattern Off | 1.6324 | 33.948 | 0.980638 | 0.5466 |
| minecraft transition | Original T2X-R | 1.7332 | 35.355 | 0.978732 | 0.6785 |
| minecraft transition | Full / Pattern Off | 1.6957 | 34.732 | 0.980388 | 0.4763 |
| minecraft transition | SMAA + edge / Pattern Off | 1.6269 | 34.690 | 0.981224 | 0.5383 |

### 정렬 지표의 적용 범위

이동 구간의 flow 유효 비율과 reference 자체의 재투영 잔차다. 유효하지 않은 위치를
제외하므로 이 지표만으로 새로 드러난 영역의 품질을 판정하지 않는다. 0.5/1/2 px는
forward/backward consistency 허용값이며, 아래 잔차 차이는 ⑥ − ④다.

| 장면 | 유효 비율(1 px) | Reference warp 잔차 | 차이(0.5 px) | 차이(1 px) | 차이(2 px) |
|---|---:|---:|---:|---:|---:|
| bistro | 99.464% | 0.6926 | -0.0500 | -0.0500 | -0.0498 |
| minecraft | 97.421% | 2.6214 | -0.2187 | -0.2241 | -0.2279 |

### 선택·비선택 영역

⑥의 실제 첫 패스 RG edge mask를 공통 영역 구분에 사용한 이동 구간 평균이다.
다른 mode의 RGB 오차도 같은 mask에서 평가했으며, 이 mask가 원본 ④의 jitter On
edge mask라는 뜻은 아니다. 선택 전환은 같은 화면 좌표의 이전/현재 mask 차이다.
움직이는 동일 표면의 후보 유지율이나 GPU helper invocation 비율로 해석하지 않는다.

| 장면 | 선택 비율 | 선택 전환 비율 | 영역 | ④ RGB MAE | Off full RGB MAE | ⑥ RGB MAE |
|---|---:|---:|---|---:|---:|---:|
| bistro | 2.567% | 2.104% | 선택 | 5.5542 | 5.2079 | 5.2079 |
| bistro | 2.567% | 2.104% | 비선택 | 0.6079 | 0.5787 | 0.5635 |
| bistro | 2.567% | 2.104% | 선택 전환 | 4.0666 | 3.7398 | 3.8426 |
| minecraft | 20.694% | 13.930% | 선택 | 4.4681 | 4.0114 | 4.0114 |
| minecraft | 20.694% | 13.930% | 비선택 | 1.3924 | 1.2157 | 1.0134 |
| minecraft | 20.694% | 13.930% | 선택 전환 | 3.9599 | 3.4280 | 3.2383 |

## 얇은 구조·가려짐 경계 ROI

아래는 이동 구간의 ⑥ − ④ 차이다. 오차 차이가 음수면 reference에 더 가깝다.
Gradient 오차도 reference와의 차이이며, gradient가 강한 것 자체를 품질 향상으로
취급하지 않는다. 화면 고정 ROI이고 object tracking이나 정확한 disocclusion mask는 아니다.

| 장면·ROI | RGB MAE 차이 | SSIM 차이 | Gradient 오차 차이 | Flow 오류 변화 차이 |
|---|---:|---:|---:|---:|
| bistro chair-legs | -0.0239 | -0.000093 | -0.0200 | -0.0809 |
| bistro foreground-boundary | +0.0079 | -0.001205 | -0.0041 | -0.0343 |
| bistro window-rails | +0.0550 | -0.003314 | +0.0114 | -0.0630 |
| minecraft stone-steps | -0.2549 | +0.005157 | -0.2091 | -0.1450 |
| minecraft foliage | -0.8054 | +0.024455 | -0.6531 | -0.0942 |
| minecraft foreground-boundary | -0.5141 | +0.012026 | -0.3497 | -0.4848 |

## 정지 안정화

Frame 180 이후 각 mode 자신의 후기 정지 frame 239와 영구적으로 일치하기까지 걸린
프레임 수다. 관측된 마지막 40개 frame 전체의 일치를 요구하며, 마지막 한 frame의
자기 일치만으로 안정화됐다고 판정하지 않는다. `미확인`은 이 byte-exact 기준의
지속 안정화가 확인되지 않았다는 뜻이며 변화 크기는 별도로 확인해야 한다.
자체적으로 안정된 결과가 reference에 더 정확하다는 뜻은 아니다.

| 장면 | ① | ② | ③ | ④ | ⑤ | ⑥ |
|---|---:|---:|---:|---:|---:|---:|
| bistro | 0 | 0 | 2 | 2 | 1 | 1 |
| minecraft | 0 | 0 | 2 | 2 | 1 | 1 |

## 결과 해석

두 장면에서 ⑤·⑥은 frame 181부터 후기 정지 결과와 일치했고, ④는 frame 182부터
일치했다. 마지막 40-frame의 실제 RGB 변화는 모든 mode에서 0이었다. 이번 캡처에서
⑤·⑥의 지속적인 정지 떨림은 확인되지 않았다. 지터를 끈 영상이 안정적이라는 사실과
원본 T2X의 시간적 supersampling에 의한 세부 복원 품질이 같은지는 별개의 문제다.

같은 Off 조건에서 선택 처리로 바꾸면 전체 화면의 평균 RGB 오차는 줄었지만,
MSE에 기반한 PSNR은 두 장면 모두 낮아졌다. 일부 큰 오차와 시간적 안정화를
평균 RGB 오차 하나로 설명할 수 없다. 이동 구간의 flow 정렬 오류 변화는 다음과 같다.

| 장면 | Off full | ⑥ 선택 처리 | 선택으로 인한 변화 |
|---|---:|---:|---:|
| bistro | 0.5544 | 0.6150 | +10.94% |
| minecraft | 1.2230 | 1.3958 | +14.12% |

즉 원본 ④와 비교한 시간 변화 감소를 모두 선택 처리의 이점으로 설명하면 안 된다.
같은 Off full에 대해서는 이 보조 지표가 오히려 증가했다. 고스팅을 줄이는 동시에
깜빡임까지 일관되게 줄였다고 결론내릴 근거는 아직 부족하다.

이동 중 고정 ROI에서도 차이가 난다. Bistro 의자 다리의 RGB MAE는 ④ 대비 조금
줄었지만 창살의 MAE·SSIM은 나빠졌다. Minecraft의 세 ROI는 ④ 대비 MAE·SSIM이
개선됐으나, 이 비교에는 pattern 변경이 함께 들어 있다. Frame 110 확대와
179~182 연속 PNG로 구조 차이를 확인했으며, MP4/GIF는 동기화된 육안 비교 자료다.
주관적 사용자 평가나 독립 물체의 잔상 길이 측정을 완료한 것으로 표시하지 않는다.

## 비교 자료와 해석 범위

각 장면에 6-case overview, reference/1X/④/⑥ 확대, ④/Off full/⑥ 분리 비교,
앞쪽 경계 확대 MP4를 만들었다. 60 FPS와 전체 frame 수 및 PTS 간격을 decode해 검증했다.
느린 GIF와 이동/정지 전환의 원본 크기 연속 PNG도 제공한다. Bistro 확대 영상만 표시용
밝기 3배를 사용하며 모든 정량 수치는 변경하지 않은 PNG에서 계산했다.

- bistro: `D:\SMAAResearchCaptures\first-edge-stencil-quality-20260929\bistro\Playback`
- minecraft: `D:\SMAAResearchCaptures\first-edge-stencil-quality-20260929\minecraft\Playback`

시간별 그래프: `D:\SMAAResearchCaptures\first-edge-stencil-quality-20260929\Summary`.

같은 pattern/spatial 조건의 성능 실험에서 ⑥의 전체 AA 시간은 Bistro 15.10%, Minecraft
3.73% 감소했다. 품질은 위와 같이 장면·구간에 따라 달라져 전반적인 품질 우위로
결론내리지 않는다. 이 수치를 jitter On 원본 대비의 순수 temporal 선택 효과로 바꾸어
설명하지 않는다. 성능 원자료는 `53ff61d:Docs/Spatial-First-Edge-Stencil`에 있다.

이번 캡처는 camera-motion 장면이다. 빠르게 움직이는 독립 물체, 크게 새로 드러나는
표면, 정확한 잔상 길이·유지 시간의 object-tracked ground truth는 미검증이다.
Flow가 유효하지 않은 위치를 확정 disocclusion으로 부르지 않으며, 속도나 CGVQM
하나만으로 global ghosting이 해소됐다고 결론내리지 않는다.

[평가 방법과 사전 ROI](method.md), `*-cgvqm.json`, `*-metrics.json`, `*-metrics-frames.csv`,
`*-visuals.json`에 설정·입력 hash·원시 산출물 위치·세부 수치를 보존했다.
`*-sources.json`은 재사용한 고정 commit/path/SHA-256을 기록한다.
