# SMAA supersample spatial-reference 품질 분석 결과

## 1. 목적

기존 stress capture와 optical-flow 분석에서 다음 trade-off가 관측됐다.

- Standard `O-T2X-R`은 회전 물체의 시간 변화량을 줄이지만 이전 위치가 겹치는
  이중 잔상을 만든다.
- `ABL-Candidate-Jitter-R`은 잔상을 줄이지만, 화면 전체 projection jitter와 후보
  한정 temporal resolve의 범위가 달라 높은 temporal variation을 만든다.
- `ABL-Candidate-NoJitter-R`은 variation을 줄이지만 `O-1X`에 가까워져 temporal
  supersampling 효과까지 잃었을 가능성이 있다.

Optical-flow residual만으로는 작은 값이 올바른 안정화인지 blur·ghosting인지 구분하기
어렵다. 이번 실험은 같은 시점의 고품질 spatial reference를 추가해 현재 프레임 형상과의
차이를 측정하고, 기존 시간 지표 및 연속 프레임 자료와 함께 해석하는 것이 목적이다.

## 2. Reference 정의와 한계

이번 reference는 CMAA2 데모의 기존 `SuperSampleReference` 경로를 같은 fixed 60 Hz
stress timeline에 연결해 생성했다.

- 선형 해상도 2배
- 한 출력 프레임 안의 3×3 subpixel grid
- 각 subpixel render에 8× MSAA
- 9회 render 동안 장면 상태 고정
- MIP bias 0.950
- sharpen 0.120
- ddx/ddy bias 0.200
- temporal history와 이전 프레임 feedback 없음

따라서 이것은 현재 프레임 형상을 고품질로 근사하는
**supersample spatial-reference proxy**다. Path-traced 절대 ground truth나 temporal
ground truth가 아니다. 특히 올바른 temporal accumulation도 현재 프레임 reference와
다를 수 있으므로, reference MAE 하나만으로 Standard T2X의 전체 품질이 나쁘다고
결론내리지 않는다.

Reference capture를 같은 조건으로 두 번 실행한 2-frame smoke에서 대응 PNG의 SHA-256
hash가 모두 일치해 deterministic capture를 확인했다.

## 3. 비교 구성과 측정 조건

| ID | 의미 |
|---|---|
| `SS-Reference` | 현재 프레임의 supersample spatial-reference proxy |
| `O-1X` | Original SMAA 1X spatial control |
| `O-T2X-R` | Standard full-screen T2X + camera reprojection |
| `ABL-Candidate-Jitter-R` | Intel-family 후보만 resolve + T2X jitter + camera reprojection |
| `ABL-Candidate-NoJitter-R` | 위 구성에서 deliberate projection jitter만 Off |

공통 조건:

- GPU: NVIDIA GeForce RTX 3060 Ti
- API: DirectX 11
- 해상도: 1920×1017
- SMAA preset: Ultra
- fixed timestep: 60 Hz
- mode별 warm-up: 60프레임
- mode별 저장: 240프레임
- object motion vector: 미지원
- PNG 품질 capture이며 성능 결과로 사용하지 않음

정식 capture:

- `Projects/CMAA2/AutoBench/20260730_152152`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_152246`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_152342`: `combined`

비교 mode capture:

- `Projects/CMAA2/AutoBench/20260730_141450`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_141600`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_141705`: `combined`

분석 지표는 stress ROI를 1/2 해상도로 축소해 계산했다. Same-frame MAE, PSNR, luma
SSIM과 edge strength/reference 비율은 240프레임 전체를 사용하고, adjacent-frame
지표는 239개 프레임 쌍을 사용한다.

## 4. Supersample reference 대비 결과

### 4.1 RGB MAE

낮을수록 같은 시점의 supersample spatial reference에 가깝다.

| 시나리오·ROI | `O-1X` | `O-T2X-R` | Candidate Jitter | Candidate NoJitter |
|---|---:|---:|---:|---:|
| thin-lines · thin line | 0.719308 | 0.845783 | 0.980899 | **0.683393** |
| object-motion · occluder | **0.497008** | 0.936618 | 0.687563 | 0.542440 |
| object-motion · rotor | **0.500726** | 2.248942 | 0.691534 | 0.551653 |
| combined · thin line | **0.764908** | 1.443198 | 1.038566 | 0.778050 |
| combined · occluder | **0.522279** | 0.933988 | 0.778320 | 0.545593 |
| combined · rotor | **0.581120** | 1.974153 | 0.802050 | 0.611566 |

`O-1X` 대비 MAE 변화:

| 시나리오·ROI | `O-T2X-R` | Candidate Jitter | Candidate NoJitter |
|---|---:|---:|---:|
| thin-lines · thin line | +17.583% | +36.367% | **-4.993%** |
| object-motion · occluder | +88.451% | +38.340% | +9.141% |
| object-motion · rotor | +349.136% | +38.106% | +10.171% |
| combined · thin line | +88.676% | +35.777% | +1.718% |
| combined · occluder | +78.829% | +49.024% | +4.464% |
| combined · rotor | +239.715% | +38.018% | +5.239% |

### 4.2 PSNR과 SSIM

| 시나리오·ROI | Mode | PSNR | Luma SSIM |
|---|---|---:|---:|
| thin-lines · thin line | `O-1X` | 38.0117 dB | 0.986505 |
|  | `O-T2X-R` | 37.8573 dB | 0.984339 |
|  | Candidate Jitter | 35.5266 dB | 0.975184 |
|  | Candidate NoJitter | **38.6481 dB** | **0.988718** |
| object-motion · rotor | `O-1X` | **38.1763 dB** | **0.993439** |
|  | `O-T2X-R` | 27.5211 dB | 0.983852 |
|  | Candidate Jitter | 35.3707 dB | 0.988000 |
|  | Candidate NoJitter | 37.3143 dB | 0.992692 |
| combined · rotor | `O-1X` | **37.8044 dB** | 0.991948 |
|  | `O-T2X-R` | 29.0990 dB | 0.983113 |
|  | Candidate Jitter | 34.7259 dB | 0.984705 |
|  | Candidate NoJitter | 37.2350 dB | **0.992190** |

PSNR과 SSIM도 MAE와 같은 방향을 보였다. Object-motion rotor에서는
`O-T2X-R`의 이중 잔상 때문에 reference와의 차이가 가장 컸고, Candidate NoJitter는
`O-1X`에 가장 가까웠다.

## 5. 시각 자료 확인

Object-motion rotor difference sheet에서 `O-T2X-R`은 현재 날개와 이전 날개 위치가
반투명하게 겹쳤고, difference 영상에서도 두 위치에 큰 오차가 나타났다.
Candidate Jitter는 이중 잔상을 줄였지만 현재 형상과 reference 사이의 차이가 남았다.
Candidate NoJitter는 `O-1X`와 거의 같은 현재 날개 형상을 보였다.

Thin-lines difference sheet에서는 Candidate Jitter가 세로선과 교차 대각선 전반에
가장 큰 차이를 보였다. 이는 projection jitter가 화면 전체에 적용되지만 temporal
resolve는 후보에만 적용되는 범위 불일치라는 앞선 ablation 결과와 일치한다.

대표 자료:

- `20260730_152152/SupersampleReferenceAnalysis/supersample_reference_difference_thin_line_field_00120.png`
- `20260730_152246/SupersampleReferenceAnalysis/supersample_reference_difference_rotor_00090.png`
- `20260730_152246/SupersampleReferenceAnalysis/supersample_reference_rotor_00078_00101.gif`
- `20260730_152342/SupersampleReferenceAnalysis/supersample_reference_difference_occluder_path_00090.png`

위 상대 경로의 기준은 `Projects/CMAA2/AutoBench/`다.

## 6. 기존 optical-flow 결과와 함께 본 해석

기존 motion-compensated 분석에서는 고정-camera rotor의 `O-T2X-R`이 `O-1X`보다
aligned residual이 약 16% 낮았다. 그러나 이번 current-frame spatial reference에서는
object-motion rotor MAE가 `O-1X`보다 349.136% 높고, 대표 영상에 이중 잔상이
명확했다. 따라서 Standard의 낮은 시간 변화량 일부는 올바른 temporal 안정화만이
아니라 history smoothing과 ghosting도 포함한다.

Candidate NoJitter는 Jitter On보다 flow residual을 모든 ROI에서 크게 줄였고, 이번
reference에서도 `O-1X` 대비 MAE가 -4.993~+10.171% 범위로 가까웠다. 이는 no-jitter가
범위 불일치를 해결한다는 근거인 동시에, object motion에서 temporal 출력이 거의
spatial 1X로 돌아간다는 근거다.

Candidate Jitter는 Standard의 큰 object ghost를 줄였지만 모든 ROI에서 `O-1X`보다
reference MAE가 35.777~49.024% 높았다. 후보를 Intel-family에서 AllBase로 늘려도
flow residual 변화가 최대 0.124%였던 앞선 결과까지 고려하면, 현재 문제의 주원인은
non-dominant 후보 제거보다 전역 jitter와 후보 한정 resolve의 부조화다.

## 7. 결론

1. Supersample reference capture와 분석 경로를 구현하고 3개 stress 시나리오,
   mode별 240프레임 정식 측정을 완료했다.
2. Standard `O-T2X-R`의 낮은 temporal residual은 회전 물체에서 이중 잔상을 포함하며,
   작은 시간 변화량만으로 더 좋은 temporal 품질이라고 판단할 수 없다.
3. Candidate Jitter는 Standard의 object ghost를 줄이지만 thin-line을 포함한
   비후보 영역의 jitter mismatch를 남긴다.
4. Candidate NoJitter는 reference와 `O-1X`에 매우 가깝다. 이는 안정화 성공만이
   아니라 temporal supersampling 효과 상실을 함께 의미한다.
5. 그러므로 현재 global no-jitter ET2X를 최종 개선안으로 확정하지 않는다.
6. Supersample spatial reference도 temporal ground truth는 아니므로, 같은 프레임
   지표는 optical-flow residual, 1X control, 연속 GIF와 함께 해석한다.

## 8. 다음 연구 범위

다음 구현은 최종 8-case와 분리한 후속 ablation으로 진행한다.

1. 비후보 픽셀에 unjittered spatial base 또는 명시적인 de-jitter resolve 제공
2. 후보에는 temporal sample diversity를 유지하고 비후보의 jitter만 안정화하는
   hybrid resolve
3. 후보 주변 안정화 band 또는 연속적인 history weight 검토
4. object motion vector 연결 후 rotor와 occluder 재검증
5. 같은 supersample reference와 optical-flow 분석으로 temporal 안정화, blur와
   ghosting을 다시 분리

핵심 목표는 ghosting을 줄이기 위해 history를 전부 버리는 것이 아니라,
`O-1X`보다 temporal 안정성을 유지하면서 Standard T2X보다 ghosting을 줄이는 것이다.
