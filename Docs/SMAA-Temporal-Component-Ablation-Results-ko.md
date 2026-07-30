# SMAA Edge-selective temporal 구성요소 ablation 결과

## 1. 목적

이 실험은 현재 `O-ET2X-R` document profile의 결과가 candidate selection,
Catmull-Rom history sampling, YCoCg variance clipping, history weight 0.8,
deliberate projection jitter 비활성화 중 어느 요소에서 비롯되는지 분리한다.

Intel 원본 TSCMAA sample source를 확보하지 못했으므로 이 결과는 공식 구현 재현이
아니라 `Intel TSCMAA 공개 문서에 부합하는 SMAA adaptation`의 원인 분석이다.
아래 ablation mode는 최종 8-case를 늘리지 않는 진단 설정이다.

## 2. 통제된 누적 profile

| 순서 | Mode | 직전 단계에서 바뀌는 요소 |
|---:|---|---|
| 0 | `O-T2X-R` | Standard full-screen T2X, camera reprojection 기준선 |
| 1 | `ABL-CandidateOnly-R` | Intel-family edge candidate coverage만 적용 |
| 2 | `ABL-Candidate+Catmull-R` | Catmull-Rom 5-tap 적용 |
| 3 | `ABL-Candidate+Catmull+Clip-R` | YCoCg variance clipping 적용 |
| 4 | `ABL-Candidate+Catmull+Clip+W0.8-R` | history weight 0.5에서 0.8로 변경 |
| 5 | `O-ET2X-R-Document` | deliberate projection jitter 비활성화 |

`ABL-CandidateOnly-R`은 `O-T2X-R`과 다음 조건이 같다.

- Original SMAA spatial input
- camera depth와 이전·현재 matrix 기반 reprojection
- SMAA T2X projection jitter와 subsample index
- bilinear history sampler
- history clipping Off
- history weight 0.5

따라서 첫 인접 비교의 유일한 temporal 차이는 full-screen history resolve를
Intel-family candidate compact/indirect resolve로 제한한 것이다. 이후 인접 단계도
표의 구성요소 하나만 추가한다.

## 3. 구현 및 검증

추가한 실행 경로는 다음과 같다.

```text
-smaaCandidateOnlyAblationCapture
-smaaCandidateOnlyAblationPerformanceSmoke
-smaaCandidateOnlyAblationPerformanceBenchmark
-smaaTemporalComponentAblationCapture
-smaaTemporalComponentAblationPerformanceSmoke
-smaaTemporalComponentAblationPerformanceBenchmark
```

Edge-selective mode에서 deliberate jitter가 켜진 경우에도 spatial SMAA가
`MODE_SMAA_T2X`와 올바른 subsample index를 사용하도록 교정했다. 또한 resize 시
이전 viewport의 jitter를 선택한 뒤 history를 reset하던 순서를 바로잡아 viewport
변경을 먼저 감지하고 reset한 뒤 새 frame jitter를 선택한다.

확장된 자동 lifecycle 검증 결과는 다음과 같다.

- 결과 경로: `Projects/CMAA2/AutoBench/20260730_125431`
- reset 34회
- completed frame 104개
- history seed 17개
- temporal resolve 87개
- camera reprojection 39개
- failure 0
- 최종 판정: PASS

7-way 품질 capture와 6-way 성능 smoke도 각각
`20260730_125505`, `20260730_125541`에서 PASS했다.

## 4. 정식 품질 측정

공통 조건은 DirectX 11, Release x64, SMAA Ultra, fixed 60 Hz, mode별
60-frame warm-up과 240-frame PNG 저장이다.

| 시나리오 | 결과 경로 | 주요 평가 대상 |
|---|---|---|
| `thin-lines` | `Projects/CMAA2/AutoBench/20260730_125659` | camera motion의 얇은 선 |
| `object-motion` | `Projects/CMAA2/AutoBench/20260730_125853` | 고정 camera의 occluder와 rotor |
| `combined` | `Projects/CMAA2/AutoBench/20260730_130049` | camera와 object motion 결합 |

모든 정식 capture는 7개 mode × 240장의 연속 index와 동일 1920×1017 해상도를
검증했다. 품질 분석기는
`Tools/SMAA/analyze_candidate_only_ablation.py --full-components`이며 각 결과
경로의 `ComponentAblationAnalysis`에 CSV, JSON, 한글 보고서, GIF와 sequence
sheet를 생성한다.

### 4.1 Candidate coverage의 단독 효과

`ABL-CandidateOnly-R`과 `O-T2X-R`의 비교 결과다.

| ROI | 인접 frame MAE 변화 | 2차 시간 차분 변화 |
|---|---:|---:|
| `thin-lines` | +23.599% | +52.761% |
| `object-motion / occluder` | +95.340% | +209.269% |
| `object-motion / rotor` | +42.093% | +140.795% |

Occluder trailing-halo 대용값은 반대 방향으로 감소했다.

| Mode | Trail darkness | Trail width |
|---|---:|---:|
| `O-1X` | 0.561651 | 0.579 px |
| `O-T2X-R` | 0.942569 | 1.462 px |
| `ABL-CandidateOnly-R` | 0.682631 | 0.579 px |

즉 candidate coverage 단독 적용은 Standard T2X의 object trail을 줄였지만 시간
변화량을 크게 늘렸다. 현재 구현에서는 비후보 픽셀이 spatial current를 유지하는 반면
projection jitter는 화면 전체에 적용된다. 따라서 jitter 위상이 바뀌는 비후보가
history resolve로 안정화되지 않는 것이 강한 temporal variation의 주된 원인으로
해석된다.

### 4.2 Catmull-Rom

Catmull-Rom 추가의 변화는 다음과 같이 작았다.

- `thin-lines`: temporal MAE -0.224%, 2차 차분 -0.422%
- 고정 camera `occluder`와 `rotor`: 표시 정밀도에서 사실상 0%
- Candidate resolve GPU 시간: +0.000689 ms, +2.959%

이 stress path에서는 Catmull-Rom이 ghosting 또는 flicker trade-off를 설명하는
주요 요소가 아니었다. 특히 고정 camera에서는 reprojection coordinate가 bilinear와
Catmull-Rom 차이를 거의 만들지 않았다.

### 4.3 YCoCg variance clipping

Clipping은 object trail을 줄였지만 temporal variation은 조금 증가했다.

| ROI | 인접 frame MAE 변화 | 2차 시간 차분 변화 |
|---|---:|---:|
| `thin-lines` | +2.152% | +5.774% |
| `object-motion / occluder` | +7.500% | +9.240% |
| `object-motion / rotor` | +1.763% | +8.834% |

Occluder trail darkness는 `0.682631 → 0.549726`, width는
`0.579 → 0.504 px`로 감소했다. 따라서 clipping은 잘못된 history 범위를 제한해
trail을 낮추는 대신 history가 frame마다 더 자주 제한되어 변화량을 늘릴 수 있다.

### 4.4 History weight 0.8

History weight를 0.5에서 0.8로 높인 인접 단계는 모든 대표 ROI의 시간 변화량을
줄였다.

| ROI | 인접 frame MAE 변화 | 2차 시간 차분 변화 |
|---|---:|---:|
| `thin-lines` | -3.690% | -13.863% |
| `object-motion / occluder` | -12.491% | -13.756% |
| `object-motion / rotor` | -3.272% | -14.665% |

이는 candidate에서 유효한 history가 유지될 때 더 높은 history weight가 안정성을
일부 회복한다는 근거다. 다만 clipping 뒤의 history만 누적하므로 Standard T2X와 같은
형태의 무제한 잔상이 그대로 돌아온다는 뜻은 아니다.

### 4.5 Deliberate jitter 비활성화

마지막 no-jitter 단계가 temporal variation을 가장 크게 줄였다.

| ROI | 인접 frame MAE 변화 | 2차 시간 차분 변화 |
|---|---:|---:|
| `thin-lines` | -18.903% | -33.320% |
| `object-motion / occluder` | -43.651% | -48.047% |
| `object-motion / rotor` | -9.469% | -49.383% |

이 결과는 현재 document profile의 1X 유사성이 candidate selection 하나 때문이
아니라 selective coverage와 full-screen T2X jitter의 구조적 부조화를 피하기 위해
no-jitter를 사용한 영향이 크다는 것을 보여준다.

그러나 no-jitter는 두 jitter phase의 temporal supersampling 자체를 제거한다. 따라서
현재 document profile이 object-motion에서 1X에 가까워지는 현상을 안정화 성공으로만
표현할 수 없다. Ghost trail 감소와 temporal supersampling 상실 가능성을 함께
기록해야 한다.

## 5. 정식 성능 측정

성능 측정 경로는 `Projects/CMAA2/AutoBench/20260730_130441`이다.

- visible/windowed 렌더 창
- 앱 내부 UI 숨김
- PNG Off
- candidate statistics readback Off
- warm-up 300프레임
- measurement 4,800프레임 × 3회
- mode별 14,400 표본
- 내부 validation PASS

분석기는 `Tools/SMAA/analyze_temporal_component_ablation_performance.py`이며 결과는
`ComponentPerformanceAnalysis`에 생성된다.

| Mode | Wall FPS | WholeFrame GPU | SMAA GPU | Candidate resolve |
|---|---:|---:|---:|---:|
| `O-T2X-R` | 325.100 | 3.035608 ms | 0.283675 ms | - |
| `ABL-CandidateOnly-R` | 318.975 | 3.099416 ms | 0.442705 ms | 0.023281 ms |
| `ABL-Candidate+Catmull-R` | 318.349 | 3.095796 ms | 0.445841 ms | 0.023970 ms |
| `ABL-Candidate+Catmull+Clip-R` | 316.305 | 3.121146 ms | 0.449788 ms | 0.027816 ms |
| `ABL-Candidate+Catmull+Clip+W0.8-R` | 316.895 | 3.117292 ms | 0.450050 ms | 0.027834 ms |
| `O-ET2X-R-Document` | 318.347 | 3.104216 ms | 0.450458 ms | 0.027835 ms |

Candidate coverage 단계는 Standard 대비 다음과 같이 느렸다.

- Wall interval +1.920%
- WholeFrame GPU +2.102%
- SMAA GPU +56.061%

후속 인접 단계의 SMAA GPU 변화는 Catmull-Rom +0.708%, clipping +0.885%,
history weight +0.058%, no-jitter +0.091%였다. Clipping은 candidate resolve 자체를
+16.045% 늘렸지만 절대 증가는 0.003846 ms였다.

현재 구현에서 가장 큰 성능 비용은 Catmull-Rom이나 history weight가 아니라
candidate texture 준비, compact와 indirect dispatch를 포함한 edge-selective 실행
구조로 전환하는 데서 발생한다. Candidate 수 감소만으로 성능 향상을 주장할 수 없으며,
현재 edge-selective adaptation은 Standard T2X보다 빠르지 않다.

## 6. 결론과 한계

이번 ablation으로 다음을 분리해 확인했다.

1. Candidate coverage는 object-motion ghost trail을 줄이는 방향이지만 deliberate
   T2X jitter를 유지하면 비후보의 시간 변화가 크게 증가한다.
2. Catmull-Rom은 이번 stress path에서 품질과 성능 모두 작은 영향만 보였다.
3. Variance clipping은 trail을 추가로 줄이는 대신 시간 변화량과 resolve 비용을
   조금 늘렸다.
4. History weight 0.8은 candidate의 temporal 안정성을 일부 회복했다.
5. No-jitter는 현재 selective 구조에서 가장 큰 안정화 효과를 만들지만 temporal
   supersampling을 약화하거나 제거한다.
6. 현재 성능 병목은 candidate compact/indirect 구조이며 edge-selective path는
   Standard보다 느리다.

따라서 현재 결과는 `O-ET2X-R`이 종합적으로 성공했다는 결론이 아니다. 더 정확한
결론을 위해 다음이 남아 있다.

- supersample reference 또는 optical-flow 정렬 지표로 ghosting과 temporal
  variation을 분리
- jitter를 후보에만 공간적으로 적용하거나 비후보를 안정화할 수 있는 구조 검토
- 필요하면 object motion vector를 camera reprojection과 별도 연구 축으로 구현
- 개선안을 만들 경우 현재 8-case 결과와 섞지 않고 별도 실험으로 검증
