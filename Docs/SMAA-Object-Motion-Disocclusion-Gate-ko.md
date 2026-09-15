# SMAA rigid-object motion previous-depth disocclusion rejection gate

## 1. 목적과 판정 범위

Rigid-object velocity는 현재 보이는 움직이는 표면을 올바른 이전 위치로 재투영한다. 그러나
물체가 지나간 뒤 새로 드러난 배경에서는 현재 배경 픽셀의 `historyUV`가 이전 프레임의
전경을 가리킬 수 있다. 이 gate는 이 stale history를 이전 프레임 depth로 판별하는
**previous-depth disocclusion rejection**을 별도 축으로 구현하고, Standard SMAA T2X와
edge-selective ET2X에서 품질 효과와 비용을 확인한다.

이번 기능은 `DisocclusionRejection::PreviousDepth`로 분리한 **default-Off engineering
ablation**이다. 기존 최종 8-case의 `-R`은 계속 depth와 camera matrix로 만든
camera-motion reprojection을 뜻한다. Rigid-object velocity와 previous-depth rejection을
기존 `-R`의 기본 동작에 포함시키지 않았으며, 과거 8-case 결과의 의미도 변경하지 않았다.

결과는 generated checker texture를 적용한 절차적 rigid-object 장면에서 얻은 engineering
gate다. 실제 textured dynamic scene의 논문 결과나 Intel 공식 TSCMAA의 완전한 재현으로
분류하지 않는다.

## 2. 구현

### 2.1 Expected previous depth와 raw depth history

Depth rejection을 켜면 velocity 생성 경로에 다음 자원을 추가한다.

- 현재 픽셀의 예상 이전 프레임 device depth를 저장하는 full-resolution `R32_FLOAT` MRT
- 현재 GBuffer raw depth를 프레임별로 보존하는 full-resolution depth history 2장
- color history와 같은 temporal frame index를 사용하는 depth ping-pong validity
- 이전 프레임 projection에 대응하는 depth-unpack 계수

Full-screen camera velocity pass는 현재 raw depth에서 world position을 복원하고 이를 이전
camera로 투영한다. 이때 `velocity = currentUV - previousUV`와
`expectedPreviousDeviceDepth = previousClip.z / previousClip.w`를 함께 출력한다.
Rigid-object velocity가 켜진 경우 현재 depth와 일치하는 움직이는 opaque rigid surface가
velocity와 expected previous depth를 함께 덮어쓴다.

Temporal resolve가 성공하면 현재 raw depth를 현재 color history와 같은 ping-pong index에
복사한다. History reset, mode·scene·camera-cut·해상도 변경 시 depth history와 이전
depth-unpack validity도 함께 무효화한다. 첫 temporal frame은 rejection을 수행하지 않고
현재 color와 depth를 seed하며, 두 번째 frame부터 previous depth가 유효할 때만 rejection을
활성화한다.

### 2.2 현재 DX11 reversed-Z perspective의 view-depth 비교

각 resolve 픽셀에서 다음 순서로 history validity를 계산한다.

```text
historyUV = currentUV - velocity
expectedDeviceDepth = ExpectedPreviousDepth[currentPixel]
actualDeviceDepth   = PreviousRawDepth.PointSample(historyUV)

expectedViewDepth = unpackMul / (unpackAdd - expectedDeviceDepth)
actualViewDepth   = unpackMul / (unpackAdd - actualDeviceDepth)

tolerance = 0.01 + 0.005 * max(abs(expectedViewDepth), 0.001)
accept history iff abs(actualViewDepth - expectedViewDepth) <= tolerance
```

`unpackMul`과 `unpackAdd`는 이전 projection에서 얻는다. 이 식과 lifecycle은 현재 엔진의
DX11 reversed-Z perspective projection/unpack convention에서 검증했다. 다른 projection
형식까지 일반화하지 않는다. Device depth가 `[0, 1]` 밖이거나 유한하지 않은 경우, unpack
분모가 너무 작거나 복원한 view depth가 양의 유한값이 아닌 경우에도 history를 거부한다.
거부된 픽셀은 history weight를 0으로 두고 현재 spatial SMAA 결과를 유지한다.

이 비교는 Standard `O-T2X-R` pixel resolve와 `O-ET2X-R` compute resolve에서 동일한
함수를 사용한다. ET2X에서는 후보 compact와 indirect dispatch가 끝난 뒤 선택된 candidate에만
적용되며, depth toggle은 현재 edge 검출이나 candidate 목록을 변경하지 않는다.

### 2.3 현재 구현의 sampling 범위

Previous raw depth는 `historyUV`의 **중앙 한 점을 point sampling**한다. ET2X의 5-tap
Catmull-Rom color history footprint 각각에 대해 depth를 검사하지 않으며, 3×3 또는 min/max
previous-depth neighborhood도 사용하지 않는다. 따라서 얇은 geometry, depth 경계와 큰
subpixel motion에서는 중앙 표본 하나의 판정 한계가 남는다.

### 2.4 실행 설정과 격리

- 기본값: rejection `Off`
- 이번 gate threshold: absolute `0.01` scene units, relative `0.005`
- 품질·성능 비교: Standard/ET2X × CameraOnly/Rigid × DepthOff/DepthOn
- ET2X 고정값: integrated first-pass candidate, `IntelFamilyNonDominant`, removal `0.50`,
  expansion `None`, compact indirect execution
- 기능 토글 변경 시 temporal history reset
- 품질·성능·lifecycle 명령 종료 시 candidate, history, debug, object-motion, depth 및 readback
  관련 기존 override 상태 복원

Generated rotor texture는 UID registrar에 등록한 뒤 material input에 연결한다. 이 등록이
없던 초기 실행에서는 material texture가 resolve되지 않아 draw가 계속 pending이었고 PNG가
생성되지 않았다. UID tracking을 추가한 뒤 1,080개 PNG의 품질 capture와 120-frame reference,
최종 9-PNG smoke가 정상 완료됐다.

## 3. Gate 구성과 원시 자료

공통 환경은 AMD Ryzen 5 5600, NVIDIA GeForce RTX 3060 Ti, DirectX 11,
1920×1017, VSync Off, SMAA Ultra다.

| 용도 | 결과 root | 조건 |
|---|---|---|
| 품질 9-mode capture | `20260916_014107` | mode당 warm-up 60, capture 120, fixed 60 Hz |
| Supersample spatial reference | `20260916_014232` | warm-up 60, capture 120 |
| Candidate counter | `20260916_014642` | warm-up 30, 120 frames×1, readback On |
| 반복 timing | `20260916_014710` | warm-up 60, 480 frames×3, readback Off, 순서 교차 |

모든 root는 `D:\SMAA-Research-Data\AutoBench` 아래에 있다. 품질 capture는 `O-1X`와
8개 factorial cell을 합친 9개 sequence, 총 1,080개 원본 PNG를 포함한다. Reference는
같은 frame index `0..119`의 PNG 120개다. 분석기는 9개 sequence와 reference의 frame 수,
index, 해상도와 file/pixel SHA-256을 검증했고 validation status는 `PASS`였다.

Supersample reference는 2× 선형 해상도, 한 출력 frame당 3×3 within-frame subpixel grid와
8×MSAA를 사용했다. MIP bias `0.950`, sharpen `0.120`, ddx/ddy bias `0.200`이며 한 출력
frame 동안 scene state를 고정하고 temporal history를 사용하지 않았다. 따라서 이는
고품질 **spatial-reference proxy**이고 absolute temporal ground truth가 아니다.

## 4. 품질 결과

### 4.1 Occluder-path ROI

Trail darkness와 width는 알려진 occluder 이동 방향 뒤를 검사하는 휴리스틱이다. 값이 작아진
경우에도 이를 절대 ghosting 양으로 해석하지 않는다.

| Mode | Reference RGB MAE | PSNR | Luma SSIM | Adjacent MAE | Trail darkness | Trail width px |
|---|---:|---:|---:|---:|---:|---:|
| `O-1X` | 0.493483 | 40.233616 | 0.991215 | 0.969902 | 0.365499 | 0.575000 |
| `O-T2X-R / CameraOnly / DepthOff` | 0.965401 | 34.569299 | 0.981188 | 0.922595 | 0.904749 | 1.658333 |
| `O-T2X-R / CameraOnly / DepthOn` | 0.838447 | 36.409245 | 0.977852 | 1.665089 | 0.351917 | 0.375000 |
| `O-T2X-R / Rigid / DepthOff` | 0.573281 | 40.104205 | 0.992227 | 0.957225 | 0.417934 | 0.425000 |
| `O-T2X-R / Rigid / DepthOn` | 0.831006 | 36.402820 | 0.978131 | 1.677297 | 0.418201 | 0.425000 |
| `O-ET2X-R / CameraOnly / DepthOff` | 0.516140 | 39.773063 | 0.990656 | 0.963184 | 0.365073 | 0.600000 |
| `O-ET2X-R / CameraOnly / DepthOn` | 0.494899 | 40.257953 | 0.991199 | 0.964992 | 0.330898 | 0.541667 |
| `O-ET2X-R / Rigid / DepthOff` | 0.508627 | 39.984645 | 0.991017 | 0.965354 | 0.338059 | 0.550000 |
| `O-ET2X-R / Rigid / DepthOn` | 0.492691 | 40.312871 | 0.991289 | 0.965734 | 0.330898 | 0.541667 |

### 4.2 Textured rotor ROI

| Mode | Reference RGB MAE | PSNR | Luma SSIM | Edge/reference | Adjacent MAE |
|---|---:|---:|---:|---:|---:|
| `O-1X` | 0.991171 | 32.025703 | 0.979340 | 1.032182 | 3.821952 |
| `O-T2X-R / CameraOnly / DepthOff` | 2.262137 | 27.933808 | 0.953773 | 0.969441 | 2.516928 |
| `O-T2X-R / CameraOnly / DepthOn` | 1.393116 | 30.782268 | 0.967064 | 1.029826 | 3.951001 |
| `O-T2X-R / Rigid / DepthOff` | 1.088407 | 32.586204 | 0.980879 | 0.994980 | 3.581486 |
| `O-T2X-R / Rigid / DepthOn` | 1.258918 | 31.915067 | 0.971075 | 1.021650 | 4.020598 |
| `O-ET2X-R / CameraOnly / DepthOff` | 0.947413 | 32.893102 | 0.981739 | 1.008007 | 3.497185 |
| `O-ET2X-R / CameraOnly / DepthOn` | 0.978542 | 32.185734 | 0.979984 | 1.025788 | 3.712917 |
| `O-ET2X-R / Rigid / DepthOff` | 0.844072 | 34.124781 | 0.984582 | 1.009002 | 3.605785 |
| `O-ET2X-R / Rigid / DepthOn` | 0.837851 | 34.020977 | 0.984607 | 1.015330 | 3.634133 |

### 4.3 DepthOn − DepthOff paired 효과

아래 MAE Δ는 frame-aligned cell mean끼리 계산한 `DepthOn − DepthOff` 절대 paired mean
delta다. 프레임별 백분율을 평균한 값은 사용하지 않았다.

| Temporal | Object velocity | Occluder MAE Δ | Rotor MAE Δ | Trail darkness Off→On | Trail width Off→On |
|---|---|---:|---:|---:|---:|
| Standard | CameraOnly | -0.126954 | -0.869021 | 0.904749→0.351917 | 1.658333→0.375000 |
| Standard | Rigid | +0.257725 | +0.170511 | 0.417934→0.418201 | 0.425000→0.425000 |
| ET2X | CameraOnly | -0.021240 | +0.031129 | 0.365073→0.330898 | 0.600000→0.541667 |
| ET2X | Rigid | -0.015936 | -0.006222 | 0.338059→0.330898 | 0.550000→0.541667 |

모든 profile/object 조건에서 DepthOff와 DepthOn의 pixel hash는 `120/120` frame에서 달라
토글이 실제 resolve 결과에 적용됐음을 확인했다.

Standard CameraOnly에서는 depth rejection이 occluder와 rotor의 spatial-reference MAE를
낮추고 trail 휴리스틱도 크게 줄였다. 동시에 adjacent-frame MAE는 occluder
`0.922595→1.665089`, rotor `2.516928→3.951001`로 증가했다. 즉 stale history 억제와
temporal smoothing 감소가 함께 나타났다.

Rigid velocity까지 적용한 Standard에서는 DepthOn이 occluder와 rotor의 paired mean MAE를
각각 `+0.257725`, `+0.170511` 높였고 trail 값도 사실상 개선되지 않았다. 현재 threshold와
중앙 point depth 하나를 사용하는 판정은 이미 정렬된 rigid surface에서 유효한 history
accumulation을 잃게 할 수 있음을 보여 준다. 이 fixture 하나만으로 정확한 원인을
over-rejection으로 확정하지는 않는다.

ET2X에서는 depth 효과가 전반적으로 작고 혼합됐다. Occluder paired mean MAE delta는
CameraOnly `-0.021240`, Rigid `-0.015936`이었지만, rotor는 CameraOnly `+0.031129`,
Rigid `-0.006222`였다. 비후보가 이미 현재 spatial 결과를 유지하는 ET2X의 특성상
previous-depth 판정이 바꿀 수 있는 영역이 Standard보다 제한적이라는 결과와 일치한다.

## 5. 성능 결과

### 5.1 측정 무결성

Timing root `20260916_014710`은 UI hidden, PNG 없음, candidate readback Off에서 각
configuration을 480 frame×3회 측정했다. 각 필수 timer는 configuration당 1,440 sample과
3개 run mean을 가지며 mode 순서를 정방향/역방향으로 교차했다. 원시 CSV SHA-256은
`7351475b2522131479f726a288be41194d641846616f83b1a76d311e7c43e503`이고 내부 benchmark와
분석 validation은 모두 `PASS`다.

Counter root `20260916_014642`는 별도 clean process에서 warm-up 30, 120 frame×1회,
readback On으로 실행했다. 원시 CSV SHA-256은
`d26a5363a8d90263d24cb5f21079eb2031e5293367644680962b63b6b8e7a1dd`이며 validation은
`PASS`다. Readback-On counter run의 절대 timing은 Readback-Off timing run과 직접
결합하지 않는다.

### 5.2 DepthOn의 평균 비용

| Temporal | Object velocity | WholeFrame Off→On | Whole Δ | SMAA Off→On | SMAA Δ | Depth copy On-only |
|---|---|---:|---:|---:|---:|---:|
| Standard | CameraOnly | 0.786252→0.901232 ms | +0.114980 ms (+14.624%) | 0.142940→0.198716 ms | +0.055776 ms (+39.021%) | 0.021548 ms |
| Standard | Rigid | 0.789797→0.873227 ms | +0.083430 ms (+10.563%) | 0.142037→0.200105 ms | +0.058068 ms (+40.882%) | 0.021536 ms |
| ET2X | CameraOnly | 0.846613→0.872216 ms | +0.025603 ms (+3.024%) | 0.183996→0.216892 ms | +0.032896 ms (+17.879%) | 0.020703 ms |
| ET2X | Rigid | 0.839218→0.886812 ms | +0.047594 ms (+5.671%) | 0.183788→0.218750 ms | +0.034962 ms (+19.023%) | 0.020742 ms |

Full-screen velocity pass가 expected-depth MRT까지 쓰면서 `SMAAGenerateCameraVelocity`는
`+0.010728~+0.011072 ms` 증가했다. Standard full-screen temporal resolve의 depth 판정
증가는 CameraOnly `+0.024344 ms`, Rigid `+0.024776 ms`였다. ET2X candidate resolve의
증가는 각각 `+0.000743 ms`, `+0.000814 ms`로 작았지만, full-screen expected-depth 생성과
depth history copy 비용은 그대로 부담한다. Rigid velocity pass의 DepthOn−Off 변화는
Standard `+0.000407 ms`, ET2X `+0.000448 ms`였다.

SMAA delta는 combined run variation 대비 `21.130~54.907`배로 명확했다. WholeFrame delta는
Standard CameraOnly `1.817`배, Standard Rigid `12.433`배, ET2X CameraOnly `0.785`배,
ET2X Rigid `2.689`배였다. 특히 ET2X CameraOnly WholeFrame 차이는 run variation보다 작으므로
그 절대 frame-level 수치를 일반화하지 않고 pass-local 비용을 우선 해석한다.

### 5.3 Candidate/process 불변성

| Object velocity | Depth | Mean base edges | Mean candidates | Mean process count | Candidate/base |
|---|---|---:|---:|---:|---:|
| CameraOnly | Off | 19835.125 | 19510.075 | 19510.075 | 0.983612 |
| CameraOnly | On | 19835.125 | 19510.075 | 19510.075 | 0.983612 |
| Rigid | Off | 19835.125 | 19510.075 | 19510.075 | 0.983612 |
| Rigid | On | 19835.125 | 19510.075 | 19510.075 | 0.983612 |

모든 ET2X cell에서 candidate와 process count가 정확히 같았고 DepthOff/DepthOn의 base edge,
candidate, process count와 candidate/base도 분석 허용치 안에서 차이 `0`으로 PASS했다.
따라서 위 성능 차이는 후보 수 변화가 아니라 expected-depth MRT, depth sampling·판정과
history copy에서 발생했다. `0.983612` candidate/base는 checker texture를 사용한 이
절차적 fixture의 값이며 실제 장면 후보 비율로 일반화하지 않는다.

## 6. 최종 회귀 검증

상태 저장·복원과 capture 안정성 보강 뒤 다음 명령을 각각 독립 clean process로 다시
실행했다.

| 결과 root | 검증 | 결과 |
|---|---|---|
| `20260916_021017` | Previous-depth lifecycle | Standard seed/active/reset seed와 ET2X seed/active 모두 PASS; depth seed/resolved `3/2`, mismatch `0`; 현재 DX11 reversed-Z perspective engine unpack convention의 CPU round-trip·threshold boundary PASS |
| `20260916_015239` | 전체 temporal lifecycle | resets `60`, frames `163`, seed `35`, resolve `128`, reprojection `92`, failures `0`, Aggregate PASS |
| `20260916_015320` | Rigid velocity | CameraOnly significant pixel `0`; Rigid `21,284` pixels (`1.090011%`), max abs `0.01061249`, history UV in-bounds `100.000%`, PASS |
| `20260916_015344` | ET2X resolved feedback | completed/output/previous checks `35/35/34`, readback failures `0`, output-history mismatch bytes `0`, previous hash mismatch `0`, Aggregate PASS |
| `20260916_021105` | 9-mode PNG smoke | warm-up/capture `1/1`, 9개 mode에서 PNG 정확히 9개 생성, clean process PASS |

이 결과로 depth history seed/resolve lifecycle, Standard/ET2X 공통 rejection 경로, 기존
rigid velocity, ET2X history feedback과 capture 진입 경로에 새 회귀가 없음을 확인했다.

## 7. 판정

1. Expected previous depth MRT와 raw depth ping-pong이 color history lifecycle에 맞춰
   동작하며, Standard와 ET2X가 현재 DX11 reversed-Z perspective 경로에서 동일한 engine
   view-depth unpack·판정을 사용한다.
2. Standard CameraOnly에서는 spatial-reference 오차와 trail 휴리스틱이 크게 감소했지만
   adjacent-frame 변화가 증가했다. Stale history 억제와 temporal 안정성 사이의 절충이
   확인됐다.
3. Standard Rigid에서는 현재 threshold의 DepthOn이 spatial-reference MAE를 악화시켰다.
   Rigid velocity와 depth rejection을 항상 함께 켜는 것이 우월하다는 근거는 없다.
4. ET2X의 품질 효과는 작고 ROI에 따라 방향이 달랐다. Candidate만 temporal 처리하는
   구조가 이미 disocclusion 영향을 제한하지만, depth rejection의 추가 이득도 제한했다.
5. DepthOn은 SMAA 시간을 Standard에서 `39.021~40.882%`, ET2X에서
   `17.879~19.023%` 증가시켰다. ET2X candidate resolve 자체의 추가 비용은 작았으나
   full-screen expected-depth 생성과 raw depth copy가 공통 고정비로 남았다.
6. 구현은 기능적으로 유효하지만 현재 자료만으로 기본 On을 정당화하지 못한다. 따라서
   default-Off engineering ablation으로 보존하고 최종 8-case의 `-R` 의미를 유지한다.

## 8. 제한과 후속 범위

- 품질 자료는 deterministic procedural engineering fixture 한 장면의 120 frame이다.
- Supersample reference는 동일 pose의 spatial proxy이며 temporal ground truth가 아니다.
- Previous depth는 중앙 `historyUV` 한 점만 검사한다. Catmull-Rom color tap별 depth,
  previous-depth neighborhood, surface/object ID와 reactive mask는 지원하지 않는다.
- Threshold `0.01 + 0.005 × expectedViewDepth` 한 설정만 검증했으며 threshold sweep은 아직
  수행하지 않았다.
- Rigid opaque transform만 지원한다. Skinned mesh, vertex deformation, particles,
  transparent surface와 material animation motion은 지원하지 않는다.
- Timing은 480 frame×3의 engineering benchmark다. 특히 일부 WholeFrame 효과는 run
  variation에 가깝거나 그보다 작다.
- 실제 textured dynamic scene, thin-depth geometry와 빠른 disocclusion에서 threshold와
  중앙 point 판정을 별도로 검증해야 한다.

다음 단계는 기존 8-case 측정과 분리한 상태에서 absolute/relative threshold sweep,
central point 대비 conservative previous-depth neighborhood, rigid On 조건의 false-rejection
분석을 순서대로 수행하는 것이다.

## 9. 분석 산출물

- 품질 보고서: `20260916_014107/analysis/SMAA-Object-Motion-Disocclusion-Quality-ko.md`
- 품질 frame 지표: `20260916_014107/analysis/object_motion_disocclusion_frame_metrics.csv`
- 품질 paired 효과: `20260916_014107/analysis/object_motion_disocclusion_paired_effects.csv`
- 품질 기계 판독 요약: `20260916_014107/analysis/object_motion_disocclusion_summary.json`
- 성능 보고서: `20260916_014710/analysis/object_motion_disocclusion_performance_report_ko.md`
- 성능 mode 요약: `20260916_014710/analysis/object_motion_disocclusion_performance_modes.csv`
- 성능 paired 효과: `20260916_014710/analysis/object_motion_disocclusion_depth_effects.csv`
- Candidate 불변성: `20260916_014710/analysis/object_motion_disocclusion_candidate_invariance.csv`
- 성능 기계 판독 요약: `20260916_014710/analysis/object_motion_disocclusion_performance_summary.json`
