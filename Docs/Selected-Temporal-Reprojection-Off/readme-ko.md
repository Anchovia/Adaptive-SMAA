# 선택 경로 위의 reprojection Off 구성 (8-case 완성)

브랜치 `experiment/selected-temporal-reprojection-off`는 `experiment/adaptive-selected-temporal`(b7dfa75)에서 분기했다. Adaptive 구성에 Adaptive 코드가 필요해서다. 그 브랜치는 `baseline/selected-temporal`에서 Adaptive 공간 처리(9eda8a0)와 기준 영상 캡처 도구(febfa57)를 더한 것이다. 이 브랜치에서 reprojection Off 네 구성을 더해 8개 구성을 모두 갖췄다.

| 8-case ID | 공간 | temporal | reprojection | 이 브랜치의 모드 |
|---|---|---|---|---|
| `O-T2X` | Original | Standard T2X | Off | `O-T2X` (새로 추가) |
| `O-T2X-R` | Original | Standard T2X | On | `O-T2X-R` (④) |
| `O-ET2X` | Original | 선택 경로 | Off | `ABL-ET2X-...` (새로 추가) |
| `O-ET2X-R` | Original | 선택 경로 | On | `ABL-ET2X-R-...` (선택 경로), 19번은 `+VelocityInEdge` |
| `A-T2X` | Adaptive | Standard T2X | Off | `A-T2X` (새로 추가) |
| `A-T2X-R` | Adaptive | Standard T2X | On | `A-T2X-R` |
| `A-ET2X` | Adaptive | 선택 경로 | Off | `A-ABL-ET2X-...` (새로 추가) |
| `A-ET2X-R` | Adaptive | 선택 경로 | On | `A-ABL-ET2X-R-...` (20번), 21번은 `+VelocityInEdge` |

reprojection Off 구성은 reprojection의 효과를 떼어 보는 no-reprojection ablation이다. 공식 TSCMAA 동작이 아니다. `-R`은 계속 camera/depth reprojection만 뜻한다. 19번과 21번은 velocity를 edge 패스에서 계산하는 구성이라 reprojection Off에서는 선택 경로와 같아지므로 따로 두지 않았다.

## 구현

- O/A-T2X: 원래 있던 SMAA T2x 경로다. 앱의 AA 종류를 `SMAA_T2x`로 두면 camera velocity 패스 없이 paired 지터를 쓰고 같은 좌표의 이전 공간 결과와 0.5씩 섞는다.
- O/A-ET2X: 선택 경로에서 이전 raw edge와 history를 같은 픽셀에서 읽는다. 선택 경로 셰이더가 `SMAA_REPROJECTION`이 있을 때만 velocity 텍스처를 읽도록 매크로 하나로 감쌌다. reprojection On 셰이더는 같은 코드로 펼쳐진다. 선택 경로의 지터 Off, Catmull-Rom 5-tap, 고정 weight 0.8, history 처리는 On과 같다.
- `ApplyTemporalRoute(route, adaptive, reprojection)`이 reprojection 여부를 받는다. 앱은 매 프레임 AA 종류로 reprojection 설정을 덮어쓰므로 Off 구성은 `SMAA_T2x`를 함께 고른다. 앱이 `SMAA_T2x`에서도 선택 경로의 출력을 화면에 내도록 조건을 넓혔다.
- 래퍼는 지터 값을 reprojection 블록 안에서만 기록하고 있었다. 그래서 첫 캡처(c23-a)에서 O-T2X와 A-T2X가 지터가 실제로 걸렸는데도 모든 프레임의 상태 검사에서 실패했다. 기록 위치를 모든 temporal 프레임으로 옮겼고(1cde8ba) 그 실행은 제외했다(`excluded-run.json`).
- 하니스는 Off 네 모드를 더하고, 시간 측정 때 정지 구간(f0~60, f181~239)과 이동 구간(f61~180)을 따로 기록한다.

원본 SMAA(ee0020d) 대비 SMAA 폴더 변경은 +707/-97, 코드 586줄이다. Adaptive 브랜치 대비 증가분은 +26/-9, 코드 16줄이다(`.cpp .h .inl .hlsl .hlsli`, 공백 변경 제외).

## 검증

캡처는 1920×1061 숨김 창, 두 장면, 10개 모드(On 6개, Off 4개), 모드마다 240프레임이다. 실행 파일은 1A9749B1…이고 프레임마다 AA 종류, reprojection 여부, 경로, 지터(Standard ±0.25, 선택 경로 0), 출력 교체 여부를 검사해 모두 통과했다.

- 회귀: On 6개 모드의 240프레임 RGB가 Adaptive 브랜치 캡처(`c20-adaptive-20261107/c20-a`)와 두 장면 모두 일치했다(`regression.json`). 비교 시트 생성과 동시에 돌린 첫 검사에서 Minecraft O-T2X-R f111이 다르다고 나왔지만, 같은 파일을 다시 디코딩하면 픽셀과 파일 크기가 모두 같았다. 따로 다시 돌린 검사에서 불일치는 0이다. 일시적인 읽기 오류로 판단했지만 원인은 확정하지 못했다.
- 정지 구간: 카메라가 멈춰 있으면 velocity가 0이므로 Off와 On이 같아야 한다. O/A-T2X는 f0~60과 f182~239에서 On과 바이트 단위로 같았다. Standard T2X의 history는 직전 공간 결과 하나라서 정지 후 두 프레임이면 다시 같아진다. O/A-ET2X는 f0~60에서만 같았다. 선택 경로의 history는 결과를 누적하므로 이동 중 생긴 차이가 정지 뒤에도 조금 남는다.

## 기준 영상과의 품질 비교

기준 영상은 Adaptive 브랜치에서 같은 경로로 찍은 supersample 공간 기준 영상이다(2배, 3×3 격자, 8×MSAA, history 없음). temporal 정답 영상은 아니다. 구간은 이동 f60~179, 정지 전환 f180~209, 정지 f220~239다(`quality.json`, 계산 `c23_quality.py`).

| 장면 | 구성 | 이동 PSNR | 이동 RGB MAE | 전환 PSNR | 정지 PSNR |
|---|---|---:|---:|---:|---:|
| Bistro | O-T2X-R | 40.391 | 0.735 | 41.737 | 41.864 |
| Bistro | O-T2X | 39.077 | 1.018 | 41.738 | 41.864 |
| Bistro | O-ET2X-R (19번 같음) | 39.300 | 0.722 | 39.590 | 39.429 |
| Bistro | O-ET2X | 36.258 | 0.931 | 39.199 | 39.352 |
| Bistro | A-T2X-R | 40.414 | 0.731 | 41.777 | 41.906 |
| Bistro | A-T2X | 39.091 | 1.014 | 41.778 | 41.906 |
| Bistro | A-ET2X-R (21번 같음) | 39.310 | 0.720 | 39.602 | 39.437 |
| Bistro | A-ET2X | 36.253 | 0.931 | 39.210 | 39.363 |
| Minecraft | O-T2X-R | 34.424 | 1.987 | 36.221 | 36.385 |
| Minecraft | O-T2X | 31.160 | 3.459 | 36.204 | 36.385 |
| Minecraft | O-ET2X-R (19번 같음) | 33.873 | 1.855 | 35.006 | 34.839 |
| Minecraft | O-ET2X | 29.172 | 3.548 | 34.238 | 34.641 |
| Minecraft | A-T2X-R | 34.470 | 1.975 | 36.335 | 36.501 |
| Minecraft | A-T2X | 31.183 | 3.447 | 36.318 | 36.501 |
| Minecraft | A-ET2X-R (21번 같음) | 33.880 | 1.852 | 34.976 | 34.803 |
| Minecraft | A-ET2X | 29.169 | 3.549 | 34.209 | 34.606 |

세 축으로 나눠 보면 다음과 같다.

- reprojection: 이동 구간에서 On이 Off보다 PSNR이 Standard T2X는 Bistro 1.31 dB, Minecraft 3.26 dB, 선택 경로는 3.04 dB, 4.70 dB 높다. 선택 경로가 더 크게 손해 보는 것은 같은 픽셀의 history를 0.8 비중으로 누적하기 때문이다. Standard T2X는 직전 프레임 하나만 0.5 비중으로 섞는다. 정지 구간에서 Standard T2X는 Off와 On이 같고, 선택 경로는 Off가 0.08 dB, 0.20 dB 낮다.
- temporal 방식: reprojection On에서 선택 경로는 Standard보다 이동 1.09 dB, 0.55 dB, 정지 2.43 dB, 1.55 dB 낮다(20·21번 문서의 결과와 같다). reprojection Off에서는 이동 구간 차이가 2.82 dB, 1.99 dB로 커진다.
- 공간 방식: Adaptive와 Original의 차이는 모든 쌍에서 0.12 dB 이하다.

얇은 선 ROI의 이동 구간 기준 영상 RGB MAE는 Bistro 의자(1230,582–1358,670)에서 O-T2X-R 4.382, O-T2X 4.357, O-ET2X-R 5.224, O-ET2X 5.632이고, Minecraft 이음매(956,524–1020,620)에서 각각 1.626, 1.883, 1.366, 1.770이다.

## 원본 프레임 직접 검사

시트는 `D:/SMAAResearchCaptures/c23-reprojection-off-20261111/inspection/`에 있다. 행은 T2X-R, T2X, ET2X-R, ET2X, 기준 영상이다.

- Off와 On의 차이가 가장 큰 구역을 프레임 차이로 찾아 f126~131을 2배로 봤다. Minecraft는 화면 오른쪽 아래 잎 구역(1481,823–1681,973)이다. O-T2X는 잎 무늬가 가로로 두 겹으로 겹쳐 보이고, O-ET2X는 경계마다 사선으로 끌린 자국이 생겨 더 크게 번진다. O-T2X-R과 O-ET2X-R은 기준 영상처럼 또렷하다. Bistro 창문(875,454–1075,604)에서는 O-ET2X의 창틀이 흐리게 겹치고 O-T2X는 그보다 약하게 겹친다.
- Minecraft 이음매와 Bistro 의자 구역은 화면에서 느리게 움직이는 곳이라 이동 중에도 Off와 On이 비슷하게 보인다.
- 정지 직후 f180~185: O-T2X는 f182부터 O-T2X-R과 같다. O-ET2X는 f180~181에 오른쪽 이음매가 조금 흐리게 남다가 O-ET2X-R과 거의 같아진다.
- 1/2로 줄인 전체 화면 f130에서는 Off와 On의 차이가 잘 보이지 않았다.
- Adaptive 시트 중 이동 구간 두 장(Minecraft 이음매, Bistro 의자 다리)을 확인했고 Original 시트와 같은 모습이었다. T2X 계열은 이음매가 끊기고 의자 주변에 점이 흩어지며, ET2X 계열은 이음매가 이어지지만 흐리고 의자 다리가 계단 모양이다. A-ET2X는 A-ET2X-R보다 의자 주변이 조금 더 번진다.

## 시간 측정

2026-11-11, RTX 3060 Ti, 1920×1061 숨김 창, 드라이버 621.14. 실행 파일은 위 품질 캡처와 같다(1A9749B1…). 측정 전 GPU는 P8, 사용률 0~18%였다. 장면마다 독립 프로세스 하나에서 10개 모드를 번갈아 돌렸고 300 warm-up 뒤 4,800프레임씩 6회 반복했다. validation은 모두 PASS다. 정지 구간(f0~60, f181~239)과 이동 구간(f61~180)은 각각 120프레임이다. 변화율은 같은 실행의 반복마다 짝지어 계산한 뒤 평균했고 괄호는 95% 구간이다(다중 비교 보정 없음). reprojection Off 구성은 camera velocity 패스가 없어 그 지표의 비율은 계산하지 않았다. 원시 수치는 `performance.json`, 계산은 `c23_time.py`다.

선택 경로, 19번, A-④, 21번의 ④ 대비 변화는 Bistro -18.96%, -28.65%, -4.74%, -33.15%, Minecraft -1.35%, -6.82%, -3.88%, -10.00%로 이전 측정과 0.5%포인트 안쪽에서 같았다.

AA 시간(ms)이다.

| 구성 | Bistro 전체 | Bistro 정지 | Bistro 이동 | Minecraft 전체 | Minecraft 정지 | Minecraft 이동 |
|---|---:|---:|---:|---:|---:|---:|
| O-T2X-R | 0.156594 | 0.152209 | 0.160980 | 0.227528 | 0.208119 | 0.246938 |
| O-T2X | 0.116654 | 0.117061 | 0.116246 | 0.186501 | 0.171782 | 0.201221 |
| O-ET2X-R | 0.126905 | 0.123134 | 0.130676 | 0.224462 | 0.197332 | 0.251591 |
| O-ET2X | 0.097020 | 0.096465 | 0.097574 | 0.191425 | 0.167944 | 0.214906 |
| A-T2X-R | 0.149166 | 0.144429 | 0.153903 | 0.218691 | 0.199844 | 0.237539 |
| A-T2X | 0.109194 | 0.109257 | 0.109131 | 0.177681 | 0.163729 | 0.191632 |
| A-ET2X-R | 0.119481 | 0.115412 | 0.123549 | 0.216953 | 0.191388 | 0.242519 |
| A-ET2X | 0.089604 | 0.088867 | 0.090342 | 0.183704 | 0.162006 | 0.205403 |
| 19번 | 0.111725 | 0.111197 | 0.112254 | 0.212020 | 0.188047 | 0.235993 |
| 21번 | 0.104686 | 0.103982 | 0.105390 | 0.204774 | 0.182232 | 0.227317 |

세 축의 짝지은 변화다(전체 AA 시간).

| 축 | 비교 | Bistro | Minecraft |
|---|---|---:|---:|
| temporal | O-ET2X-R − O-T2X-R | -18.96% [-19.18, -18.74] | -1.35% [-2.11, -0.58] |
| temporal | O-ET2X − O-T2X | -16.83% [-16.96, -16.70] | +2.64% [+1.72, +3.57] |
| temporal | A-ET2X-R − A-T2X-R | -19.90% [-20.07, -19.73] | -0.79% [-1.76, +0.18] |
| temporal | A-ET2X − A-T2X | -17.94% [-18.13, -17.75] | +3.40% [+2.13, +4.66] |
| 공간 | A-T2X-R − O-T2X-R | -4.74% [-5.08, -4.41] | -3.88% [-4.63, -3.13] |
| 공간 | A-ET2X-R − O-ET2X-R | -5.85% [-5.97, -5.73] | -3.34% [-4.29, -2.40] |
| 공간 | A-T2X − O-T2X | -6.39% [-6.62, -6.17] | -4.73% [-4.94, -4.52] |
| 공간 | A-ET2X − O-ET2X | -7.64% [-7.87, -7.42] | -4.03% [-4.18, -3.88] |
| reprojection | O-T2X-R − O-T2X | +34.24% [+33.72, +34.75] | +22.00% [+21.83, +22.17] |
| reprojection | O-ET2X-R − O-ET2X | +30.80% [+30.54, +31.07] | +17.26% [+17.14, +17.38] |
| reprojection | A-T2X-R − A-T2X | +36.61% [+36.26, +36.95] | +23.09% [+21.76, +24.41] |
| reprojection | A-ET2X-R − A-ET2X | +33.34% [+32.88, +33.80] | +18.11% [+16.78, +19.43] |

- reprojection은 AA 시간에 Bistro 0.030~0.040 ms, Minecraft 0.033~0.041 ms를 더한다. 이 중 camera velocity 패스가 약 0.024 ms이고, Standard T2X는 resolve도 Off보다 약 0.01 ms 길다. 나머지 구성은 나누지 않았다. 전체 프레임 시간으로는 Bistro 1.6~2.1%, Minecraft 3.5~4.7%다. 그 대가로 이동 구간 PSNR이 1.3~4.7 dB 오르고 빠르게 움직이는 곳의 겹침과 끌림이 사라진다(위 품질 절).
- temporal 축에서 선택 경로는 Bistro에서 Standard보다 17~20% 빠르다. Minecraft에서는 reprojection On에서 0.8~1.4% 빠르거나 차이가 없고, Off에서는 2.6~3.4% 느리다. Minecraft의 선택 경로는 정지 구간에서 빠르고(On -4.2~-5.2%) 이동 구간에서 느리다(On +1.9~+2.1%, Off +6.8~+7.2%).
- 공간 축에서 Adaptive는 모든 쌍에서 3.3~7.6% 빠르다.
- 가장 빠른 구성은 A-ET2X(④ 대비 Bistro -42.8%)지만 reprojection이 없어 이동 품질이 가장 낮다. reprojection On 구성 중에서는 21번(④ 대비 Bistro -33.15%, Minecraft -10.00%)이 가장 빠르다.

## 한계

- RTX 3060 Ti 한 대, 1920×1061 숨김 창, 한 카메라 경로에서만 확인했다. CGVQM은 계산하지 않았다.
- 이 경로는 이동이 비교적 느리고 정지 구간이 절반이다. 빠른 회전이나 물체 움직임이 있는 장면의 reprojection Off 결과는 재지 않았다.
