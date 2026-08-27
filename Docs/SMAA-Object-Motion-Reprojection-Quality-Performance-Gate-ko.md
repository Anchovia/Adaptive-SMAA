# SMAA rigid-object motion reprojection 품질·성능 gate

## 1. 목적과 범위

현재 8-case의 `-R`은 depth와 이전·현재 camera matrix로 계산한 **camera-motion
reprojection**만 의미한다. 이 gate는 움직이는 opaque rigid object의 이전 world
transform을 이용해 해당 surface의 velocity를 덮어쓰는 default-Off 확장이 실제로
고스팅을 줄이는지, 비용은 어느 정도인지 분리해 확인한다.

이번 결과는 절차적 moving-occluder/rotor engineering fixture에서 얻었다. 따라서
실제 textured dynamic scene의 논문 결과가 아니며, 기존 8-case의 `-R` 정의를 변경하지
않는다. Skinned/deforming/transparent motion과 previous-depth disocclusion rejection도
범위에 포함되지 않는다.

## 2. 구현 및 비교 구성

공통 조건은 Release x64, DirectX 11, Original SMAA Ultra, 1920×1017, fixed 60 Hz다.
ET2X는 integrated first-pass candidate source, `IntelFamilyNonDominant`, removal `0.50`,
expansion `None`을 고정했다.

| 구성 | Temporal 방식 | Reprojection |
|---|---|---|
| `O-1X` | 없음 | 없음 |
| `O-T2X-R / camera-only` | Standard T2X | camera/depth만 |
| `O-T2X-R / camera+rigid` | Standard T2X | camera/depth + rigid transform |
| `O-ET2X-R / camera-only` | edge-selective T2X | camera/depth만 |
| `O-ET2X-R / camera+rigid` | edge-selective T2X | camera/depth + rigid transform |

`camera+rigid`는 full-screen camera velocity를 먼저 생성한 뒤, 현재 depth와 일치하는
움직이는 opaque rigid mesh 픽셀만 object velocity로 덮어쓴다. 토글 변경 시 temporal
history를 reset하며, 기본 실행에서는 Off다.

## 3. 자동 검증

다음 검증을 모두 독립 clean process에서 통과했다.

- Release x64 빌드 PASS. 기존 C4834/C4100 경고 외 새 오류 없음.
- `-smaaRigidObjectVelocityTest`: camera-only significant pixel 0, rigid On 21,284픽셀
  (1.090011%), history UV in-bounds 100%, PASS.
- `-smaaTemporalLifecycleTest`: 129 frames, 48 resets, failures 0, PASS.
- `-smaaTemporalFeedbackTest`: output/history mismatch bytes 0, previous-history hash
  mismatch 0, PASS.
- `-smaaStaticStabilityTest`: `O-ET2X`, `O-ET2X-R` 각각 32개 resolve hash 변화 0, PASS.
- `-smaaTemporalVelocityTest`: 정적 camera velocity 0, +right camera 이동의 X 부호와
  `historyUV=currentUV-velocity` in-bounds 99.955%, PASS.

## 4. 품질 gate

### 조건

- 시나리오: `object-motion`
- mode당 warm-up 60, capture 240 frames
- reference: 2× linear resolution, frame당 3×3 within-frame subpixel grid와 8×MSAA를
  사용하는 supersample **spatial proxy**
- reference는 temporal ground truth가 아니므로 MAE, PSNR, SSIM과 연속 GIF 및 trail
  휴리스틱을 함께 해석한다.

### Occluder ROI

| Mode | Reference RGB MAE | PSNR | Luma SSIM | Trail darkness | Trail width px |
|---|---:|---:|---:|---:|---:|
| `O-1X` | 0.497008 | 40.1940 dB | 0.991151 | 0.561651 | 0.579167 |
| `O-T2X-R / camera-only` | 0.936618 | 35.1113 dB | 0.982262 | 0.942569 | 1.462500 |
| `O-T2X-R / camera+rigid` | 0.587717 | 40.0836 dB | 0.992132 | 0.504664 | 0.420833 |
| `O-ET2X-R / camera-only` | 0.525666 | 39.5286 dB | 0.990357 | 0.573294 | 0.600000 |
| `O-ET2X-R / camera+rigid` | 0.515972 | 39.8096 dB | 0.990798 | 0.539006 | 0.537500 |

- Standard camera+rigid의 reference MAE는 camera-only보다 `37.251%` 낮았다.
- ET2X camera+rigid의 개선은 `1.844%`로 작았다.
- Trail 지표는 알려진 이동 방향 뒤의 darkness/폭 휴리스틱이며 절대 ghosting
  ground truth가 아니다.

### Rotor ROI

| Mode | Reference RGB MAE | PSNR | Luma SSIM | Adjacent-frame MAE |
|---|---:|---:|---:|---:|
| `O-1X` | 0.500726 | 38.1763 dB | 0.993440 | 3.804550 |
| `O-T2X-R / camera-only` | 2.248942 | 27.5211 dB | 0.983856 | 2.993003 |
| `O-T2X-R / camera+rigid` | 0.653812 | 36.4277 dB | 0.993445 | 3.790908 |
| `O-ET2X-R / camera-only` | 0.516384 | 37.8986 dB | 0.993068 | 3.789845 |
| `O-ET2X-R / camera+rigid` | 0.511367 | 38.0870 dB | 0.993285 | 3.791367 |

- Standard camera+rigid의 reference MAE는 camera-only보다 `70.928%` 낮았다.
- ET2X camera+rigid의 개선은 `0.971%`로 작았다.
- 연속 frame과 sheet에서 Standard camera-only의 반투명 이전 날개 위치가 rigid
  보정 후 크게 줄었다. ET2X camera-only는 이미 non-candidate history를 거부해
  O-1X에 가까웠으므로 rigid toggle의 추가 변화가 작았다.

## 5. 반복 성능 gate

### 조건

- RTX 3060 Ti, 1920×1017, window visible, VSync Off
- mode당 warm-up 300 frames
- 4,800 measurement frames × 3 repeats
- forward/reverse mode order 교차
- PNG·UI·candidate readback Off
- mode당 14,400 timing sample과 3 run mean, 내부 validation PASS

| Mode | Wall FPS | WholeFrame ms | SMAA ms | Rigid pass ms |
|---|---:|---:|---:|---:|
| `O-T2X-R / camera-only` | 1205.035 | 0.777259 | 0.141377 | - |
| `O-T2X-R / camera+rigid` | 1188.521 | 0.793754 | 0.142622 | 0.000362 |
| `O-ET2X-R / camera-only` | 1137.893 | 0.841343 | 0.181823 | - |
| `O-ET2X-R / camera+rigid` | 1124.444 | 0.850845 | 0.182449 | 0.000371 |

camera+rigid의 camera-only 대비 변화:

| Profile | WholeFrame | SMAA | 직접 rigid pass |
|---|---:|---:|---:|
| Standard | +0.016495 ms (+2.122%) | +0.001245 ms (+0.881%) | 0.000362 ms |
| Edge-selective | +0.009502 ms (+1.129%) | +0.000626 ms (+0.344%) | 0.000371 ms |

Rigid pass는 매우 짧아 많은 frame에서 timestamp 해상도 미만의 0 ms가 기록됐다. 이
0은 누락시키지 않고 유효한 below-resolution/empty-work 표본으로 보존했다. WholeFrame과
SMAA 차이는 직접 rigid pass보다 크고 run 간 변동도 있으므로, 모든 차이를 object draw
비용이라고 단정하지 않는다.

## 6. 판정

1. Rigid-object velocity는 Standard T2X의 움직이는 surface history 오정렬을 실제로
   교정했다. 특히 rotor reference MAE가 70.928% 감소해 기능적 유효성이 명확하다.
2. Edge-selective T2X에서는 camera-only 출력이 이미 O-1X에 가까워 추가 개선이 1~2%
   수준이었다. 이는 object motion을 올바르게 처리했다는 뜻과 별개로, ET2X가 history를
   충분히 보존하는지는 계속 독립 평가해야 한다.
3. 직접 rigid pass 평균은 약 0.00036~0.00037 ms였고 SMAA 증가는 0.00063~0.00125 ms였다.
   기능 대비 작은 비용이지만 실제 장면 mesh 수·draw 수에 따라 달라질 수 있다.
4. 따라서 구현은 **default-Off engineering ablation으로 보존**한다. 실제 textured
   dynamic scene, previous-depth disocclusion rejection, skinned/transparent 범위가 없는
   상태에서 최종 8-case `-R`을 camera+object로 재정의하지 않는다.
5. 기존 8-case는 camera/depth reprojection 범위로 core를 freeze하고 fresh 측정을
   진행할 수 있다. Rigid-object 확장은 별도 후속 연구 축으로 보고한다.

## 7. 산출물

- 품질 capture: `D:\SMAA-Research-Data\AutoBench\20260828_064415`
- 품질 분석: `D:\SMAA-Research-Data\AutoBench\20260828_ObjectMotionReprojectionQuality\Analysis`
- 정식 성능 raw: `D:\SMAA-Research-Data\AutoBench\20260828_070434`
- 정식 성능 분석: `D:\SMAA-Research-Data\AutoBench\20260828_ObjectMotionReprojectionFormal\Performance`
- GPU rigid velocity 재검증: `D:\SMAA-Research-Data\AutoBench\20260828_070604`
- lifecycle: `D:\SMAA-Research-Data\AutoBench\20260828_070622`
- feedback: `D:\SMAA-Research-Data\AutoBench\20260828_070650`
- static stability: `D:\SMAA-Research-Data\AutoBench\20260828_070714`
- camera velocity: `D:\SMAA-Research-Data\AutoBench\20260828_070756`
