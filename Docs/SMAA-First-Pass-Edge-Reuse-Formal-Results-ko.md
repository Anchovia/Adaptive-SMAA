# SMAA 1차 패스 edge 재사용 정식 검증 결과

## 1. 검증 목적

기존 edge-selective T2X 경로는 SMAA 공간 처리의 1차 edge detection을 수행한 뒤에도
temporal candidate extraction에서 luminance edge를 다시 계산했다. 이번 controlled
ablation은 다음 두 candidate base-edge source만 바꾸고 나머지 설정을 동일하게 유지했다.

| Source | 의미 |
|---|---|
| `LegacyLumaRedetect` | spatial SMAA 뒤 luminance에서 temporal base edge를 다시 계산 |
| `SMAAFirstPassEdges` | spatial SMAA 1차 패스의 RG 방향 edge mask를 temporal base gate로 재사용 |

원본 SMAA의 edge detection→weight calculation→neighborhood blending 순서와 shader는
수정하지 않았다. `SMAAFirstPassEdges`도 binary edge만으로 Intel-family non-dominant
ranking을 대체하지 않으며, 살아남은 SMAA edge 위치의 contrast ranking에는 기존 luma
strength를 사용한다. 따라서 이번 경로는 **중복 base-edge gate를 줄이는 실험**이지
candidate extraction pass 전체를 제거한 구현은 아니다.

## 2. 구현 및 검증 범위

- branch: `codex/smaa-first-pass-edge-reuse`
- 비교 중심 mode: `O-ET2X`, `O-ET2X-R`
- 직교 고정 항목: Intel-family candidate policy, expansion None, Catmull-Rom 5-tap,
  YCoCg variance clipping, history weight 0.8, 동일 jitter/reprojection/history lifecycle
- 기본값: 기존 연구 결과를 보존하기 위해 `LegacyLumaRedetect`
- 정식 카메라 품질 profile: `flythrough-wide-yaw-360`
- 장면: 저대비 Bistro, 고대비 Minecraft

Engineering gate에서 Release x64, FXC, lifecycle, temporal feedback, static stability,
candidate policy sweep를 통과했다. 고정 pose에서 legacy 대비 first-pass source의 base edge는
Bistro 15.12%, Minecraft 16.57% 감소했고, 최종 candidate는 각각 7.00%, 3.45% 감소했다.

## 3. 정식 성능 측정

### 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- 해상도: 1920×1017, visible window
- DirectX 11, Release x64, SMAA Ultra, VSync Off
- Bistro fixed 60 Hz camera path
- 300-frame warm-up
- mode당 4,800 measurement frame × 3회
- 정방향/역방향 mode 순서 교차
- candidate counter readback Off
- PNG capture 및 UI Off

원시 결과:

- `D:\SMAA-Research-Data\AutoBench\20260827_182835\20260827_182835_results.csv`

검증·집계 결과:

- `D:\SMAA-Research-Data\AutoBench\20260827_CandidateEdgeSourceWide_Formal\Performance\Analysis`

### 평균 GPU/Wall 시간

| Pair | Source | Wall ms | WholeFrame GPU ms | SMAA GPU ms | Extract ms | Resolve ms |
|---|---|---:|---:|---:|---:|---:|
| `O-ET2X` | Legacy | 3.175445 | 3.132435 | 0.419876 | 0.089651 | 0.024586 |
| `O-ET2X` | First-pass | 3.182844 | 3.144133 | 0.421127 | 0.090993 | 0.023934 |
| `O-ET2X-R` | Legacy | 3.287009 | 3.231857 | 0.453788 | 0.089774 | 0.027719 |
| `O-ET2X-R` | First-pass | 3.300065 | 3.250803 | 0.456803 | 0.091098 | 0.026927 |

### First-pass − Legacy 변화

| Pair | Wall | WholeFrame | SMAA | Extract | Resolve |
|---|---:|---:|---:|---:|---:|
| `O-ET2X` | +0.233% | +0.373% | +0.298% | +1.497% | -2.652% |
| `O-ET2X-R` | +0.397% | +0.586% | +0.664% | +1.475% | -2.857% |

Candidate 수가 줄어 resolve는 약 2.7~2.9% 감소했지만, extraction은 약 1.5% 증가했고
SMAA total과 WholeFrame도 감소하지 않았다. 전체 차이는 작은 절대값이며 run 간 변동보다
뚜렷하게 큰 개선도 아니다. 따라서 현재 first-pass source를 **성능 최적화 성공**이라고
판정하지 않는다.

## 4. 정식 카메라 품질 캡처

동일 실행 순서에 의한 상태 영향을 확인하기 위해 각 장면에서 source 순서를 정방향과
역방향으로 바꿔 480-frame sequence를 모두 캡처했다.

| Scene | Forward | Reverse | Source-order stable frame |
|---|---|---|---:|
| Bistro | `20260827_183525` | `20260827_184919` | 189~479 |
| Minecraft | `20260827_183814` | `20260827_185229` | 1~479 |

모든 경로의 상위 root는 `D:\SMAA-Research-Data\AutoBench`다. Bistro에서는 source와
무관하게 초반 출력이 실행 순서에 따라 달라졌고, 189번 frame부터 정·역방향 capture가
byte-identical해졌다. Minecraft는 첫 frame을 제외하면 order-stable했다. warm-up을
240 frame으로 늘린 축소 실험에서도 Bistro 초반 차이가 남았으므로, 원인을 단순 history
warm-up 부족으로 단정하지 않는다. 정식 source 비교와 CGVQM은 order-stable 구간 안에서
수행했다.

분석 결과:

- `D:\SMAA-Research-Data\AutoBench\20260827_CandidateEdgeSourceWide_Formal\Analysis`

### Order-stable full 구간

| Scene | Source | Reference RGB MAE ↓ | O-1X distance ↓ | Adjacent-frame MAE ↓ |
|---|---|---:|---:|---:|
| Bistro 189~479 | Legacy | 1.530826 | 0.424080 | 15.847379 |
| Bistro 189~479 | First-pass | 1.526869 | 0.393576 | 15.862990 |
| Minecraft 1~479 | Legacy | 1.330138 | 0.380155 | 6.469311 |
| Minecraft 1~479 | First-pass | 1.331674 | 0.372290 | 6.472442 |

First-pass의 spatial-reference MAE는 Bistro에서 0.259% 감소했지만 Minecraft에서는
0.115% 증가했다. 두 장면 모두 O-1X distance는 감소하고 adjacent-frame MAE는 소폭
증가했다. 즉 first-pass source는 legacy보다 history 적용 범위를 줄여 결과를 O-1X에
가깝게 만들었지만, 측정된 화면 공간 시간 변화가 줄지는 않았다. 이를 ghosting 감소나
temporal supersampling 유지의 성공으로 해석하지 않는다.

## 5. Intel CGVQM-2 정식 gate

동일 pose supersample spatial reference에 대해 Intel 공식 CGVQM commit
`8302ff45b4ff5a691682baf23f7c007d6b591e98`의 CGVQM-2를 CUDA에서 실행했다.
60 FPS, patch scale 4, mean pooling을 사용했고 모든 test/reference FFV1 왕복 검증에서
픽셀 불일치가 0이었다.

| Scene | Window | Legacy | First-pass | First-pass − Legacy |
|---|---|---:|---:|---:|
| Bistro | stable motion 210~329 | 96.749206543 | 96.757194519 | +0.007987976 |
| Bistro | transition 410~439 | 94.574707031 | 94.560981750 | -0.013725281 |
| Minecraft | stable motion 210~329 | 97.260055542 | 97.252624512 | -0.007431030 |
| Minecraft | transition 410~439 | 93.752891541 | 93.739021301 | -0.013870239 |

결과 및 집계:

- `D:\SMAA-Research-Data\AutoBench\20260827_CandidateEdgeSourceWide_Formal\CGVQM`
- `D:\SMAA-Research-Data\AutoBench\20260827_CandidateEdgeSourceWide_Formal\CGVQM\Analysis`

Bistro 안정 구간만 아주 작게 높고 나머지 세 구간은 아주 작게 낮았다. 방향이 장면과
구간에 따라 달라지며 차이도 매우 작으므로, first-pass source의 일관된 full-reference
품질 개선 근거로 사용하지 않는다. CGVQM 점수도 절대적인 ghosting 판별값은 아니다.

## 6. 최종 판정

1. SMAA 1차 패스 edge 재사용 경로는 원본 SMAA 공간 path를 훼손하지 않고 기능·회귀
   검증을 통과했다.
2. base edge와 temporal candidate 수는 감소했지만, 현재 구조에서는 candidate extraction
   pass와 luma strength 접근이 남아 있다.
3. 정식 반복 성능에서 resolve는 소폭 감소했으나 extraction, SMAA total, WholeFrame은
   개선되지 않았다.
4. reference 품질 변화는 매우 작고 장면 의존적이며, temporal 결과는 일관되게 O-1X에
   가까워졌다. 시간 변화량이 감소했다는 근거도 없다.
5. 따라서 `SMAAFirstPassEdges`는 controlled ablation으로 보존하되 기본 source는
   `LegacyLumaRedetect`로 유지한다.
6. 이번 결과는 “1차 패스 edge를 연결하면 자동으로 TSCMAA overhead가 줄어든다”는 가설을
   지지하지 않는다. 후보 수 감소와 실제 GPU 시간 감소는 별도로 측정해야 한다.

## 7. 후속 작업 기준

추가 최적화를 시도한다면 다음을 별도 ablation으로 분리해야 한다.

1. `SMAAFirstPassEdges + AllBaseEdges`로 luma non-dominant ranking까지 제거했을 때의
   candidate 수·품질·성능 비교
2. SMAA first-pass output과 temporal candidate compaction 사이의 full-screen pass를
   구조적으로 줄일 수 있는지 검토
3. 위 변경이 candidate policy 자체를 바꾸는 효과와 메모리/dispatch 최적화 효과를 한
   버전에 섞지 않도록 단계별 구현

현재 정식 판정만으로 first-pass source를 8-case 기본 설정에 편입하거나 기존 8-case
결과를 교체하지 않는다.
