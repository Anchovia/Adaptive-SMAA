# SMAA optical-flow 정렬 temporal 품질 분석 결과

## 1. 목적

기존 인접 frame MAE와 2차 시간 차분에는 실제 camera/object motion이 포함된다.
이번 분석은 spatial-only 1X control에서 추정한 optical flow로 이전 frame을 현재
frame에 정렬한 뒤 남는 residual을 계산해 다음을 확인한다.

1. Candidate-only 단계의 큰 시간 변화가 장면 motion만으로 설명되는지
2. Standard T2X와 Edge-selective T2X의 차이가 motion 보정 뒤에도 유지되는지
3. 최종 8-case에서 edge selection, camera reprojection과 Adaptive 공간 축의 방향

이 지표는 supersample ground truth나 절대 ghosting 점수가 아니라 기존 trail
휴리스틱과 sequence 비교를 보강하는 motion-compensated 보조 지표다.

## 2. 방법과 근거

Dense flow에는 Gunnar Farneback의 polynomial expansion 기반 two-frame motion
estimation을 사용했다.

- [Farneback 원 논문](https://www.diva-portal.org/smash/get/diva2%3A273847/fulltext01.pdf)
- [OpenCV calcOpticalFlowFarneback 문서](https://docs.opencv.org/4.7.0/dc/d6b/group__video__track.html)
- [OpenCV remap 문서](https://docs.opencv.org/4.12.0/d1/da0/tutorial_remap.html)

OpenCV 문서의 flow 관계에 따라 `previous → current` forward flow와
`current → previous` backward flow를 모두 계산했다. Current 좌표에 backward flow를
더한 source coordinate로 previous frame을 `remap`한다.

```text
previous(y, x) ≈ current(y + flow_y, x + flow_x)
warped_previous(current_xy) = previous(current_xy + backward_flow)
```

Forward/backward consistency는 다음과 같이 검사한다.

```text
|backward(current_xy) + forward(previous_xy)| ≤ threshold
```

화면 밖 좌표와 consistency threshold를 넘는 좌표는 residual에서 제외한다. 기본
threshold는 1/2 ROI 해상도에서 1.0px다.

### 공통 Farneback 설정

| 설정 | 값 |
|---|---:|
| `pyr_scale` | 0.5 |
| `levels` | 3 |
| `winsize` | 15 |
| `iterations` | 3 |
| `poly_n` | 5 |
| `poly_sigma` | 1.2 |
| `flags` | 0 |

### Flow source 분리

- Component ablation: 모든 mode에 `O-1X` flow를 공통 적용
- 최종 Original 4개: `O-1X` flow를 공통 적용
- 최종 Adaptive 4개: `A-1X` flow를 공통 적용

Temporal mode 자체에서 flow를 계산하지 않으므로 history blur나 ghosting이 mode마다
서로 다른 flow를 만들어 비교를 왜곡하는 문제를 줄인다.

## 3. 분석기와 검증

추가한 도구는 다음과 같다.

- `Tools/SMAA/analyze_optical_flow_temporal_quality.py`
- `Tools/SMAA/analyze_eight_case_optical_flow_quality.py`
- `Tools/SMAA/requirements-optical-flow.txt`

고정 의존성은 `opencv-python-headless==4.12.0.88`이다.

### 합성 이동 self-test

알려진 `(3,-2)px` forward translation을 가진 texture를 만들고 backward flow와
정렬 오차를 확인했다.

| 항목 | 결과 |
|---|---:|
| 기대 backward flow | `(-3,+2)px` |
| 측정 중앙값 | `(-2.999911,+1.999938)px` |
| Vector error | `0.000108px` |
| 유효 픽셀 | `94.209%` |
| 정렬 전 MAE | `29.479216` |
| 정렬 후 MAE | `0.036219` |
| 오차 감소 | `99.877%` |
| 판정 | PASS |

## 4. Component ablation 정식 결과

공통 조건은 1920×1017 원시 PNG, ROI 1/2 해상도 분석, mode별 60-frame warm-up과
240-frame capture다.

| 시나리오 | 입력 경로 | 분석 결과 |
|---|---|---|
| `thin-lines` | `Projects/CMAA2/AutoBench/20260730_125659` | `OpticalFlowTemporalAnalysis` |
| `object-motion` | `Projects/CMAA2/AutoBench/20260730_125853` | `OpticalFlowTemporalAnalysis` |
| `combined` | `Projects/CMAA2/AutoBench/20260730_130049` | `OpticalFlowTemporalAnalysis` |

모든 ROI에서 flow valid ratio는 78.166~92.763%, O-1X 전체 평균 MAE 기준 정렬
오차 감소는 29.474~43.080%로 보조 검증을 통과했다.

### Candidate coverage 단독 효과

| ROI | Candidate-only vs Standard aligned MAE |
|---|---:|
| `thin-lines / thin_line_field` | +32.304% |
| `object-motion / occluder_path` | +310.764% |
| `object-motion / rotor` | +49.881% |
| `combined / thin_line_field` | +23.814% |
| `combined / occluder_path` | +26.354% |
| `combined / rotor` | +20.612% |

Motion 정렬 뒤에도 Candidate-only의 residual이 일관되게 높다. 따라서 기존 2차
시간 차분 증가를 장면 motion만으로 설명할 수 없으며, full-screen T2X jitter가
남은 상태에서 비후보가 history resolve를 받지 않는 구조의 instability가 실제로
포함된다는 근거다.

### 후속 구성요소

- Catmull-Rom: aligned residual 변화가 `-0.398~0.000%`로 매우 작음
- Variance clipping: 대표 ROI에서 `+0.010~+10.957%`
- History weight 0.8: 대표 ROI에서 `-0.456~-18.663%`
- No-jitter document endpoint: 직전 단계 대비 `-10.371~-73.381%`

이 방향은 motion 보정 전 ablation과 일치한다. Candidate+jitter 단계가 가장 큰
variation을 만들고 history weight와 no-jitter가 안정화를 회복한다.

## 5. Forward/backward threshold 민감도

Object-motion에서 consistency threshold를 0.5/1.0/2.0px로 바꿨다.

| Threshold | ROI | Valid ratio | Candidate vs Standard | Document vs Candidate |
|---:|---|---:|---:|---:|
| 0.5px | occluder | 89% | +363.67% | -78.33% |
| 1.0px | occluder | 90% | +310.76% | -75.98% |
| 2.0px | occluder | 91% | +273.06% | -73.88% |
| 0.5px | rotor | 90% | +52.50% | -21.63% |
| 1.0px | rotor | 93% | +49.88% | -20.41% |
| 2.0px | rotor | 95% | +47.48% | -19.84% |

임계값이 느슨해질수록 occlusion 경계가 더 포함되어 절대 변화율은 달라지지만 결론
방향은 유지됐다.

## 6. 최종 8-case 정식 결과

1X control과 temporal 8-case는 동일 fixed timeline이며 기존 별도 재실행 SHA-256
검증에서 control PNG mismatch가 0이었다.

| 시나리오 | Control 입력 | Temporal 입력 | 결과 |
|---|---|---|---|
| `thin-lines` | `20260730_042245` | `20260730_030857` | `EightCaseOpticalFlowAnalysis` |
| `object-motion` | `20260730_042343` | `20260730_031939` | `EightCaseOpticalFlowAnalysis` |
| `combined` | `20260730_042414` | `20260730_032435` | `EightCaseOpticalFlowAnalysis` |

### Camera-motion thin-lines

Edge-selective와 camera reprojection은 aligned residual을 줄이는 방향이었다.

| 비교 축 | Original | Adaptive |
|---|---:|---:|
| Edge-selective Off vs Standard Off | -12.103% | -14.055% |
| Edge-selective On vs Standard On | -11.984% | -9.365% |
| Standard Reprojection On vs Off | -5.943% | -9.500% |
| Edge Reprojection On vs Off | -5.815% | -4.561% |

`O-ET2X-R`은 `O-1X`보다 aligned residual이 21.203% 높았지만 `O-T2X-R`보다는
11.984% 낮았다. 이 수치만으로 ET2X-R이 1X보다 나쁘다고 단정하지 않으며 기존
2차 차분, edge strength와 연속 frame을 함께 본다.

### 고정 camera의 독립 object motion

Occluder의 8개 temporal mode는 대응 spatial 1X보다 aligned residual이
1.261~4.714% 높았고 Edge-selective와 Standard 차이는 -2.458~+0.299%로 작았다.
Forward/backward mask가 움직이는 occlusion 경계 일부를 제외하므로 기존 trailing-halo
감소를 이 ROI 평균만으로 대체할 수 없다.

Rotor에서는 다음 차이가 명확했다.

| 비교 | Aligned residual 변화 |
|---|---:|
| `O-T2X` vs `O-1X` | -16.419% |
| `O-T2X-R` vs `O-1X` | -16.248% |
| `O-ET2X` vs `O-1X` | -0.090% |
| `O-ET2X-R` vs `O-1X` | -0.090% |
| `A-T2X` vs `A-1X` | -16.519% |
| `A-ET2X` vs `A-1X` | +0.043% |

Standard T2X는 낮은 residual을 보이지만 sequence에서 이전 rotor 위치가 겹치는 이중
잔상이 확인됐다. 낮은 residual은 temporal smoothing과 ghost blur로도 만들어질 수
있다. Edge-selective는 1X와 거의 동일해 ghost를 줄였지만 temporal supersampling을
거의 잃었다는 기존 해석을 강화한다.

### Combined

Camera와 object가 함께 움직일 때 thin-line과 occluder는 다음 방향이었다.

- Edge-selective vs Standard: `-8.692~-12.196%`
- Camera reprojection On vs Off: `-2.808~-7.242%`

Rotor에서는 Edge-selective가 Standard보다 `+7.566~+11.410%` 높았고 대응 1X보다
`+3.626~+7.024%` 높았다. Camera motion 구간에서는 ET2X와 reprojection의 보조
안정화가 보이지만, 독립 rotor의 temporal benefit은 Standard보다 작다는 trade-off가
재현됐다.

## 7. 종합 해석

Optical-flow 정렬 결과는 기존 결론을 다음과 같이 보강한다.

1. Candidate-only의 큰 variation은 실제 장면 motion만의 결과가 아니다.
2. Current ET2X document profile은 camera-motion thin-line에서 Standard 대비
   motion-compensated residual을 줄이는 방향을 보인다.
3. 독립 object motion에서 Standard는 temporal residual을 낮추지만 visible ghost
   blur가 크다.
4. Current ET2X는 visible ghost를 줄이지만 rotor에서 1X와 거의 같아 temporal
   supersampling 효과를 상당 부분 잃는다.
5. Camera reprojection은 camera-motion/combined에서는 residual을 줄이지만 고정
   camera object-motion에서는 Off/On 결과가 같거나 거의 같다. 이는 현재 `-R`이
   camera motion만 처리한다는 코드 구조와 일치한다.
6. Adaptive 공간 축은 대응 temporal 거동을 크게 바꾸지 않는다는 기존 same-frame
   결과와 대체로 일치한다. 단, Original과 Adaptive가 서로 다른 flow source를
   사용하므로 아주 작은 직접 차이는 해석하지 않는다.

## 8. 한계와 다음 단계

- Farneback flow는 추정치이며 반사·저텍스처·회전 경계에서 오차가 있다.
- Forward/backward 불일치 영역을 제외하므로 disocclusion ghosting을 완전히 재지 않는다.
- 1X aliasing이 flow source에 포함된다.
- 낮은 aligned residual은 blur/history 누적으로도 발생한다.
- 따라서 이 지표는 trailing-halo, 1X same-frame 비교와 sequence sheet의 보조 근거다.

다음 구현 연구는 candidate-aware jitter 또는 비후보 안정화다. 다만 새 개선안을
시작하기 전에 필요하면 supersample ground truth를 추가해 disocclusion과 blur/ghosting
구분을 더 강화할 수 있다. Object motion vector는 camera reprojection과 분리한 후속
연구 축으로 유지한다.
