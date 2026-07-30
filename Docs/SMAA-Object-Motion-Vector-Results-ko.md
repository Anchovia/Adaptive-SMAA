# SMAA rigid opaque object-motion vector 진단 결과

## 1. 목적과 분류

기존 `O-T2X-R`과 최종 8개 case의 `-R` mode는 depth와 이전·현재 camera matrix로
만든 **camera-motion velocity만** 사용한다. 따라서 카메라가 고정된 상태에서 움직이는
회전 날개나 occluder는 이전 위치의 history를 그대로 섞어 이중 잔상을 만든다.

이번 작업은 현재 엔진에서 object motion vector를 생성·전달할 수 있는지 확인하고,
`O-T2X-R`에 rigid opaque object motion만 추가한 통제 진단을 만드는 것이 목적이다.

- 진단 ID: `ABL-O-T2X-R-ObjectMotion`
- 코드 mode: `SMAA_O_ABLATION_T2X_R_OBJECT_MOTION`
- 분류: engineering ablation
- 최종 8개 case에는 포함하지 않음
- 기존 `O-T2X-R`, `O-ET2X-R`, `A-*`의 의미와 출력은 변경하지 않음

## 2. 통제 조건

`O-T2X-R-CameraOnly`와 `ABL-O-T2X-R-ObjectMotion`은 다음 조건을 동일하게
유지한다.

| 항목 | 설정 |
|---|---|
| Spatial SMAA | Original |
| Temporal coverage | Standard full-screen T2X |
| Projection jitter | SMAA T2X On |
| History sampler | Bilinear |
| History clipping | Off |
| History weight | 0.5 |
| Camera reprojection | On |

바뀌는 요소는 현재 화면에 보이는 rigid opaque mesh의 object transform motion
velocity 하나다.

## 3. 구현

### 3.1 이전 객체 변환

`vaSceneObject`가 직전 scene tick의 world transform을 보존하고, render draw-list
entry가 현재·이전 transform을 함께 전달하도록 확장했다. 첫 tick 또는 temporal
history reset 직후에는 previous=current로 취급해 가짜 속도가 생기지 않게 했다.

### 3.2 Object velocity MRT

Forward opaque pass에서 다음 두 render target을 동시에 기록한다.

1. 기존 radiance
2. `R16G16B16A16_FLOAT` object velocity + mask

각 rigid mesh vertex에서 현재 object transform + 현재 unjittered camera matrix와,
이전 object transform + 이전 unjittered camera matrix의 clip position을 계산한다.
Pixel shader는 두 위치를 UV로 변환해 `currentUV - previousUV`를 저장한다.

### 3.3 Camera/object velocity 결합

SMAA wrapper는 기존 depth 기반 camera velocity를 먼저 만든다. 이후 full-screen merge
pass에서 object mask가 있는 픽셀은 object velocity를, 그 외 sky/background 픽셀은
camera velocity를 선택한다. 합성 velocity는 기존 Standard T2X spatial/temporal
resolve에 그대로 전달한다.

이 구조에서 object velocity는 camera motion과 object motion이 합쳐진 전체
screen-space motion이며, 배경의 camera reprojection 경로는 유지된다.

### 3.4 Reset 연동

기존 mode/scene/camera-cut/resize history reset이 previous camera matrix를
무효화한다. Object velocity pass는 이 상태를 확인해 reset 뒤 첫 프레임에서
previous object/camera를 current와 같게 사용한다.

## 4. 지원 범위와 한계

현재 진단이 지원하는 범위:

- `vaSceneObject`의 rigid transform으로 움직이는 opaque mesh
- 현재 화면에서 보이는 표면의 camera + object motion
- 절차적 `SMAA Temporal Stress Test`의 이동 occluder와 회전 날개

현재 지원하지 않는 범위:

- skinned mesh와 vertex deformation
- transparent object motion
- particle motion
- 이전 프레임에만 보였던 표면의 별도 motion
- disocclusion depth/history rejection
- 일반 엔진 전체 asset에 대한 object-motion 정합성 인증

현재 프레임 object velocity는 움직이는 물체 표면의 history를 정렬할 수 있지만,
물체 뒤에서 새로 드러난 배경 픽셀의 잘못된 history까지 자동으로 거부하지는 않는다.
따라서 object motion vector와 disocclusion rejection은 별도 문제로 취급한다.

## 5. 자동 검증

Release x64 build 후 `-smaaTemporalLifecycleTest`를 실행했다.

| 항목 | 결과 |
|---|---:|
| Reset | 39 |
| Completed frame | 174 |
| Seed | 20 |
| Resolve | 154 |
| Reprojection | 59 |
| Failure | 0 |
| 종합 | PASS |

기존 8개 mode, component/hybrid ablation과 새 object-motion 진단의 mode 전환,
첫 프레임 seed, history ping-pong, jitter/subsample pairing, camera matrix,
scene/camera-cut/resize reset이 모두 통과했다.

## 6. 120프레임 engineering 품질 캡처

캡처:

- 루트: `Projects/CMAA2/AutoBench/20260730_214020`
- GPU: RTX 3060 Ti
- API: DirectX 11
- 해상도: 1920×1017
- SMAA Ultra, VSync Off
- fixed 60 Hz
- 시나리오: `object-motion`
- mode별 warm-up 60프레임
- mode별 저장 120프레임
- 비교: `O-1X`, `O-T2X-R-CameraOnly`, `ABL-O-T2X-R-ObjectMotion`

세 mode 모두 00000~00119의 연속 PNG를 확보했다. 고정 카메라의 절차적 이동에서
`O-1X`는 raster quantization으로 동일 PNG 한 쌍이 있어 119개 고유 hash였고,
두 temporal mode는 각각 120개 고유 hash였다.

### 6.1 Rotor

| 지표 | O-1X | Camera-only T2X-R | Object-motion T2X-R |
|---|---:|---:|---:|
| 인접 frame RGB MAE | 3.807895 | 2.998082 | 3.794132 |
| 2차 시간 차분 Luma MAE | 0.946281 | 0.817290 | 0.992001 |
| Edge strength | 1.776469 | 1.761639 | 1.758705 |
| O-1X 대비 same-frame RGB MAE | 0 | 2.307124 | 0.602932 |

Object-motion 진단은 camera-only T2X-R보다 O-1X 대비 same-frame 오차가
73.87% 작았다. 대표 프레임에서 camera-only T2X-R의 이전 날개 위치가 반투명하게
남는 이중 잔상이 object-motion 진단에서는 제거됐다.

다만 camera-only T2X-R의 낮은 temporal MAE에는 올바른 안정화뿐 아니라 잘못 정렬된
history의 blur/ghost smoothing도 포함된다. Object-motion 진단의 temporal 변화량이
O-1X에 가까워졌다는 사실만으로 temporal supersampling 품질 우위를 주장하지 않는다.

### 6.2 Occluder

| 지표 | O-1X | Camera-only T2X-R | Object-motion T2X-R |
|---|---:|---:|---:|
| 인접 frame RGB MAE | 0.974879 | 0.935656 | 0.975051 |
| 2차 시간 차분 Luma MAE | 1.864458 | 1.186398 | 1.922622 |
| Edge strength | 2.414089 | 2.394278 | 2.401438 |
| O-1X 대비 same-frame RGB MAE | 0 | 1.040668 | 0.635191 |

Object-motion 진단은 camera-only T2X-R보다 O-1X 대비 same-frame 오차가
38.96% 작았다.

Occluder trail 휴리스틱:

| 지표 | O-1X | Camera-only T2X-R | Object-motion T2X-R |
|---|---:|---:|---:|
| Mean darkness | 0.537781 | 0.980408 | 0.474822 |
| Width (px) | 0.575000 | 1.608333 | 0.408333 |

Object-motion 진단은 camera-only T2X-R 대비 darkness가 51.57%, width가
74.61% 작았다. 이 값은 절차적 장면의 휴리스틱이며 절대 ghosting ground truth가
아니다. 특히 새로 드러난 배경의 disocclusion rejection 완료를 뜻하지 않는다.

## 7. Combined smoke

`Projects/CMAA2/AutoBench/20260730_214342`에서 camera와 object가 동시에 움직이는
`combined` 시나리오를 mode별 warm-up 12프레임, 저장 12프레임으로 실행했다.
화면 전체 밀림·깨짐 없이 background camera velocity와 rigid object velocity가
동시에 적용됐고, 회전 날개의 camera-only 이중 잔상 감소 방향도 재현됐다.

이 실행은 기능 smoke이며 정식 품질 또는 성능 결과가 아니다.

## 8. 분석 도구와 대표 자료

분석기:

- `Tools/SMAA/analyze_object_motion_vector_quality.py`

120프레임 분석 산출물:

- `Projects/CMAA2/AutoBench/20260730_214020/ObjectMotionVectorAnalysis/SMAA-Object-Motion-Vector-Analysis-ko.md`
- `Projects/CMAA2/AutoBench/20260730_214020/ObjectMotionVectorAnalysis/object_motion_vector_metrics.csv`
- `Projects/CMAA2/AutoBench/20260730_214020/ObjectMotionVectorAnalysis/object_motion_rotor_frame_00060.png`
- `Projects/CMAA2/AutoBench/20260730_214020/ObjectMotionVectorAnalysis/object_motion_rotor_three_way.gif`
- `Projects/CMAA2/AutoBench/20260730_214020/ObjectMotionVectorAnalysis/object_motion_occluder_path_frame_00060.png`
- `Projects/CMAA2/AutoBench/20260730_214020/ObjectMotionVectorAnalysis/object_motion_occluder_path_three_way.gif`

## 9. 현재 결론과 다음 작업

현재 엔진에서 rigid opaque object motion vector를 생성해 SMAA Standard T2X에
전달하는 것은 가능하며, 통제된 stress 장면에서 camera-only reprojection의
object-motion 이중 잔상을 크게 줄였다.

그러나 다음은 아직 결론내리지 않는다.

- 일반 장면의 object-motion 지원 완료
- object motion vector 적용의 최종 성능
- disocclusion 해결
- temporal supersampling 품질의 종합 우위
- 최종 8-case의 정의 변경

다음 작업은 다음 순서가 타당하다.

1. object velocity/mask GPU readback 진단으로 정적·이동 rigid object의 부호와 범위를
   수치 검증한다.
2. supersample spatial-reference proxy와 연결해 ghost 감소와 현재 edge 품질을
   분리한다.
3. depth mismatch/disocclusion history rejection을 별도 ablation으로 추가한다.
4. 필요할 때만 transparent/skinned motion 지원 범위를 확장한다.
5. 기능·품질 근거가 확보된 뒤 별도 performance smoke로 추가 MRT와 merge pass 비용을
   측정한다.
