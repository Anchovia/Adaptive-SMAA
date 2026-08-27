# SMAA Integrated Candidate Removal 전체 Timeline 품질 결과

## 1. 목적

앞선 60-frame screening과 반복 성능 gate에서 남긴 removal `0.50`, `0.70`, `0.75`를
전체 `flythrough-wide-yaw-360` 경로에서 다시 비교했다. 이번 gate의 목적은 약 50%의
candidate 비율이나 국소 resolve 시간만 보고 값을 선택하지 않고, 카메라 이동·360° 회전·
motion→still 전환을 모두 포함한 연속 품질로 기본값을 결정하는 것이다.

이 실험은 Original SMAA 기반의 parameter quality gate다. 최종 Original/Adaptive 8-case
측정이 아니며, Intel의 공개되지 않은 원본 TSCMAA candidate 식을 재현한 결과도 아니다.

## 2. 비교 구성과 조건

장면별로 다음 9개 출력을 동일한 480-frame 경로에서 캡처했다.

```text
O-1X
O-T2X
O-ET2X    removal 0.50 / 0.70 / 0.75
O-T2X-R
O-ET2X-R  removal 0.50 / 0.70 / 0.75
```

- Bistro 저대비 / Minecraft 고대비
- Original SMAA, Ultra, DirectX 11, 1920×1017, fixed 60 Hz
- `flythrough-wide-yaw-360`, profile frame 0~479
- mode별 첫 pose 60-frame warm-up 후 전체 timeline 캡처
- integrated source, `IntelFamilyNonDominant`, edge threshold `1/22`
- candidate expansion None
- `-R`은 depth와 이전·현재 camera matrix 기반 camera-motion reprojection만 사용
- object motion vector는 이 gate에 연결하지 않음
- 장면별 독립 clean process, 실행 종료 후 잔류 `CMAA2.exe` 0

각 edge-selective 세 값 안에서는 removal만 달라진다. 다만 Standard T2X와 document
profile 사이에는 coverage 외에도 projection jitter, history sampler, variance clipping과
history weight 차이가 있다. 따라서 Standard 대 ET2X 결과를 candidate 선택 하나의
효과라고 표현하지 않는다.

## 3. 캡처·분석 검증

- Bistro와 Minecraft 각각 9 mode × 480 PNG의 index, 해상도, 고유 hash 검증 PASS
- 동일 pose 3×3 subpixel grid + 8×MSAA supersample spatial reference와 비교
- full, motion 60~419, central motion 150~329, motion→still 410~439, post-still
  420~479 구간을 분리
- CGVQM-2는 IntelLabs/CGVQM commit
  `8302ff45b4ff5a691682baf23f7c007d6b591e98`을 CUDA에서 순차 실행
- CGVQM 2 scenes × 2 windows × 9 modes = 36 jobs PASS
- 모든 최종 test/reference FFV1 decode와 원본 PNG의 pixel mismatch 0
- Bistro central `O-ET2X-R 0.75` reference encode에서 첫 decode mismatch가 한 번
  검출됐으나 자동 재시도 후 최종 mismatch 0으로 통과했다. 최종 점수는 검증된 재시도
  입력으로 계산됐다.

Supersample reference는 동일 pose의 spatial-reference proxy이고 temporal ground truth가
아니다. CGVQM-2도 full-reference perceptual video metric이며 절대 고스팅 판별기는 아니다.
O-1X 거리와 optical-flow 미정렬 temporal difference 역시 상대 비교용 대용값으로만 쓴다.

## 4. Full-timeline 핵심 결과

다음 표는 removal `0.50→0.70`의 motion 60~419 변화다. Ref MAE와 O-1X 거리는 낮을수록,
Adjacent MAE와 2차 시간 차분은 이 비교에서 작을수록 시간 변화가 적다.

| Scene | Reprojection | Ref MAE | O-1X 거리 | Adjacent MAE | 2차 시간 차분 |
|---|---|---:|---:|---:|---:|
| Bistro | Off | -2.670% | -10.551% | +0.505% | +0.548% |
| Bistro | On | -0.390% | -10.495% | +0.119% | +0.148% |
| Minecraft | Off | -4.113% | -17.456% | +1.510% | +1.667% |
| Minecraft | On | +0.068% | -16.244% | +0.442% | +0.577% |

`0.70`은 reprojection Off에서는 spatial reference 오차를 줄였다. 그러나 네 비교 모두
O-1X 거리가 10.5~17.5% 감소했고 temporal change는 증가했다. 이는 일부 개선이 더 적은
history 적용과 1X 회귀에서 왔을 가능성을 보여준다. 특히 Minecraft reprojection On에서는
Ref MAE도 0.068% 증가해 장면·reprojection 공통 spatial 개선이 재현되지 않았다.

`0.75`는 같은 방향을 더 강하게 보였다. motion 구간 O-1X 거리는 `0.50`보다
14.1~24.2% 감소했고 temporal change 증가도 `0.70`보다 컸다. 따라서 성능 경계
ablation으로는 유효하지만 기본값 후보로 승격할 근거는 부족하다.

## 5. 공식 CGVQM-2 결과

### 5.1 Central motion 150~329

| Scene | Reprojection | 0.50 | 0.70 | 0.75 | 0.70 Δ vs 0.50 |
|---|---|---:|---:|---:|---:|
| Bistro | Off | 94.788963 | 94.990723 | 95.063255 | +0.201759 |
| Bistro | On | 96.688606 | 96.714584 | 96.724632 | +0.025978 |
| Minecraft | Off | 96.201988 | 96.497162 | 96.596725 | +0.295174 |
| Minecraft | On | 97.515762 | 97.507568 | 97.510361 | -0.008194 |

Off에서는 `0.70`과 `0.75`가 점수를 높였지만 On에서는 차이가 매우 작거나 Minecraft에서
악화됐다. document-based adaptation의 중심인 reprojection On에서 장면 공통 이득이 없다.

### 5.2 Motion→still 410~439

| Scene | Reprojection | 0.50 | 0.70 | 0.75 | 0.70 Δ vs 0.50 |
|---|---|---:|---:|---:|---:|
| Bistro | Off | 93.863335 | 93.915344 | 93.941277 | +0.052010 |
| Bistro | On | 94.560982 | 94.534744 | 94.527451 | -0.026237 |
| Minecraft | Off | 93.241837 | 93.265274 | 93.281013 | +0.023438 |
| Minecraft | On | 93.739021 | 93.658226 | 93.636391 | -0.080795 |

전환 구간에서도 Off는 소폭 개선됐지만 On은 두 장면 모두 악화됐다. `0.75`는 On에서
`0.70`보다 더 낮아져 higher removal의 이득이 포화되고 trade-off가 커지는 경향과
일치한다.

참고로 no-reprojection `O-T2X`의 central-motion CGVQM은 Bistro 49.742794,
Minecraft 76.105438로 매우 낮았다. 카메라가 크게 움직이는 구간에서 같은 화면 좌표의
history를 결합하는 대조군이 잘못 정렬되는 현상을 수치로 확인한 것이다. 반대로
edge-selective Off가 높은 점수를 보인 것은 history를 제한해 이 오차를 피한 효과와
O-1X 회귀가 함께 포함되므로, temporal supersampling 향상만으로 해석하지 않는다.

## 6. 기존 성능 gate와 결합한 판단

반복 성능 측정에서 `0.70`은 `0.50`보다 candidate resolve를 4.102~4.950% 줄였다.
하지만 SMAA total 변화는 Bistro -0.020%/+0.027%, Minecraft -0.624%/-0.817%였고,
WholeFrame 변화는 -0.217~+0.058%로 일관되지 않았다. `0.75`도 WholeFrame 개선을
재현하지 못했다.

즉 removal 증가는 국소 resolve 작업량을 줄이지만, 전체 SMAA나 frame 성능 이득으로
확대되지 않았다. 여기에 full-timeline에서 확인된 O-1X 회귀와 reprojection On 품질
비일관성을 함께 고려해야 한다.

## 7. 최종 파라미터 판정

### 기본 document profile은 removal `0.50`을 유지한다.

근거는 다음과 같다.

1. `0.70`의 명확한 품질 이득은 주로 reprojection Off central motion에 한정됐다.
2. reprojection On에서는 CGVQM 이득이 거의 없거나 두 장면의 motion→still에서 악화됐다.
3. `0.70/0.75`는 출력이 더 O-1X에 가까워지고 temporal change를 증가시켰다.
4. candidate resolve 시간은 줄었지만 WholeFrame 개선은 재현되지 않았다.
5. `0.50`은 Intel 공개 기본 non-dominant removal control이며, 현 근거로 바꿀 만큼
   장면·구간·reprojection에 걸친 일관된 이득이 없다.

`0.70`은 실패한 값이 아니라 **장면 의존적인 cost/quality ablation 후보**로 보존한다.
`0.75`는 더 강한 candidate 제거의 경계 조건으로 보존한다. 이 판정은 parameter gate의
기본값 선택이며 기존 final 8-case 결과를 아직 갱신하지 않는다.

## 8. 다음 작업

1. removal `0.50`을 고정한 fresh matched benchmark에서 Standard T2X와 integrated
   edge-selective T2X의 실제 overhead를 동일 조건으로 다시 비교한다.
2. candidate preparation, indirect args, resolve, reprojection과 SMAA total을 분리해
   integrated core의 남은 병목을 확정한다.
3. 그 결과가 통과한 뒤에만 Adaptive 4개를 포함한 최종 8-case 재측정을 진행한다.
4. object-motion reprojection은 현재 `-R` 정의에 포함하지 않고 별도 gate로 유지한다.

## 9. 산출물

- Bistro 9-mode capture: `D:/SMAA-Research-Data/AutoBench/20260828_022413`
- Minecraft 9-mode capture: `D:/SMAA-Research-Data/AutoBench/20260828_023316`
- full-timeline 분석: `D:/SMAA-Research-Data/AutoBench/20260828_IntegratedCandidateRemovalFullTimeline/Analysis`
- CGVQM 36-job 결과: `D:/SMAA-Research-Data/AutoBench/20260828_IntegratedCandidateRemovalFullTimeline/CGVQM`
- CGVQM 통합 보고서: `D:/SMAA-Research-Data/AutoBench/20260828_IntegratedCandidateRemovalFullTimeline/CGVQM/Analysis/SMAA-Integrated-Candidate-Removal-CGVQM-Results-ko.md`
- 캡처/분석 구현: `Projects/CMAA2/CMAA2Sample.cpp`,
  `Tools/SMAA/analyze_integrated_candidate_removal_full_timeline.py`,
  `Tools/SMAA/run_integrated_candidate_removal_cgvqm.py`,
  `Tools/SMAA/analyze_integrated_candidate_removal_cgvqm.py`
