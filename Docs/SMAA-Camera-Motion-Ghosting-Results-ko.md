# SMAA 급격한 카메라 회전 고스팅 평가 결과

## 1. 실험 범위

교수 피드백에 따라 새 asset을 추가하기 전에 기존 저대비 Bistro와 고대비 Minecraft에서
결정적인 `yaw-fast-360` camera profile을 적용했다. 이 단계는 최종 8-case가 아니라
Original 공간 처리의 평가 파이프라인을 전체 길이로 검증하는 **engineering 결과**다.

- GPU: NVIDIA GeForce RTX 3060 Ti
- DirectX 11, Release x64, SMAA Ultra, VSync Off
- 1920×1017, fixed 60 Hz
- profile: 60-frame pre-still + 60-frame 360° yaw + 60-frame post-still
- mode별 60-frame warm-up
- 비교: `O-1X`, `O-T2X`, `O-T2X-R`, `O-ET2X`, `O-ET2X-R`
- reference: 2× linear resolution, 3×3 within-frame grid, 8×MSAA의
  temporal-history-free supersample spatial proxy
- CGVQM: IntelLabs/CGVQM commit `8302ff45`, CGVQM-2, CUDA, patch scale 3,
  mean pooling

`-R`은 depth와 이전·현재 camera matrix를 이용한 camera-motion reprojection이며 object
motion vector를 의미하지 않는다. 순수 yaw이므로 이번 결과는 일반적인 parallax 또는
disocclusion 성능으로 확대 해석하지 않는다.

## 2. 캡처 및 검증

### Bistro

- 5-way capture: `Projects/CMAA2/AutoBench/20260812_184742`
- reference/CGVQM: `Projects/CMAA2/AutoBench/20260812_185018`
- 각 mode 180 PNG, reference 180 PNG
- 모든 sequence index 00000~00179 연속, 누락 0
- 모든 test/reference FFV1 RGB round-trip mismatch 0

### Minecraft

- 5-way capture: `Projects/CMAA2/AutoBench/20260812_193331`
- reference/CGVQM: `Projects/CMAA2/AutoBench/20260812_193514`
- 각 mode 180 PNG, reference 180 PNG
- 모든 sequence index 00000~00179 연속, 누락 0
- 모든 test/reference FFV1 RGB round-trip mismatch 0

## 3. CGVQM-2 및 회전 구간 결과

점수는 높을수록 reference에 가깝다. `회전 error mean`은 낮을수록 좋다. `O-1X MAE`는
현재 spatial control과의 같은-frame 차이이므로 작다고 무조건 temporal 품질이 좋은 것은
아니다. 1X로 회귀한 경우에도 작아질 수 있다.

### Bistro 저대비 장면

| Mode | CGVQM-2 ↑ | 전체 error mean ↓ | 회전 error mean ↓ | 회전 O-1X MAE ↓ | 회전 2차 luma diff ↓ | Recovery |
|---|---:|---:|---:|---:|---:|---:|
| `O-1X` | 94.398033 | 5.601962 | 3.082100 | 0.000000 | 57.031053 | 0 |
| `O-T2X` | 71.426331 | 28.573662 | 75.328761 | 17.677998 | 25.769528 | 0 |
| `O-T2X-R` | 94.284134 | 5.715862 | 6.669650 | 2.398998 | 56.945341 | 0 |
| `O-ET2X` | 93.626579 | 6.373410 | 5.223690 | 0.694319 | 55.449138 | 0 |
| `O-ET2X-R` | 94.414253 | 5.585742 | 3.212687 | 0.470493 | 56.610599 | 0 |

### Minecraft 고대비 장면

| Mode | CGVQM-2 ↑ | 전체 error mean ↓ | 회전 error mean ↓ | 회전 O-1X MAE ↓ | 회전 2차 luma diff ↓ | Recovery |
|---|---:|---:|---:|---:|---:|---:|
| `O-1X` | 97.817940 | 2.182052 | 0.809685 | 0.000000 | 47.090112 | 0 |
| `O-T2X` | 82.948639 | 17.051365 | 46.181318 | 14.336844 | 20.857147 | 0 |
| `O-T2X-R` | 97.438858 | 2.561137 | 2.641186 | 1.158026 | 47.049499 | 2 |
| `O-ET2X` | 97.390831 | 2.609166 | 1.932351 | 0.360321 | 46.299568 | 2 |
| `O-ET2X-R` | 97.740921 | 2.259071 | 1.088510 | 0.232715 | 46.921585 | 0 |

Recovery는 각 mode와 O-1X의 pre-still CGVQM error `mean + 3σ` 중 큰 값을 threshold로
정하고, post-still에서 5프레임 연속 threshold 이하가 되는 최초 offset이다. 두 장면
모두 0~2프레임이므로 이번 pure-yaw 경로에서는 장시간 post-stop trail보다 **회전 중
history 오정렬**이 핵심 문제였다.

## 4. 관찰과 해석

1. `O-T2X`는 두 장면 모두 회전 중 이전 시점 화면이 반투명하게 겹쳤다. 낮은 2차 시간
   차분은 올바른 안정화만이 아니라 심한 history blending/ghost blur를 포함하므로 품질
   이득으로 해석하면 안 된다.
2. `O-T2X-R`은 CGVQM-2가 Bistro 71.4263→94.2841, Minecraft
   82.9486→97.4389로 회복됐다. camera reprojection이 pure yaw의 큰 history 좌표
   오정렬을 실제로 교정했다.
3. `O-ET2X`도 no-reprojection Standard보다 훨씬 reference에 가까웠다. 이는 현재 edge
   후보만 history를 적용해 오정렬 history의 피해 범위를 제한한 결과로 볼 수 있다.
   그러나 O-1X MAE가 Bistro 0.6943, Minecraft 0.3603에 불과하므로 temporal 효과를
   일부 잃고 1X에 가까워진 영향도 함께 존재한다.
4. `O-ET2X-R`은 두 장면 모두 O-1X에 가장 가까운 temporal mode였고 눈에 띄는 360°
   회전 고스팅이 보이지 않았다. 다만 회전 2차 luma difference도 O-1X와 거의 같아,
   고스팅 억제와 별개로 temporal supersampling 이득을 충분히 유지했다고 단정할 수 없다.
5. 따라서 이번 결과만으로 이전-frame edge mask 교집합·dilation을 추가할 근거는 약하다.
   먼저 최종 8-case에서 같은 경향을 확인하고, current-edge expansion은 얇은 선 복구
   ablation으로 별도 검증하는 것이 타당하다.

## 5. 대표 자료

### Bistro

- 보고서:
  `Projects/CMAA2/AutoBench/20260812_185018/CGVQM-CameraMotion-Bistro-yaw-fast-360/CameraMotionAnalysis/SMAA-Camera-Motion-Original-Five-Analysis-ko.md`
- 대표 시트: `camera_motion_representative_sheet.png`
- 회전 6-way GIF: `camera_motion_rotation_comparison.gif`
- CGVQM error-map: 각 mode 폴더의 `CGVQM-2-ErrorMap.mkv`

### Minecraft

- 보고서:
  `Projects/CMAA2/AutoBench/20260812_193514/CGVQM-CameraMotion-Minecraft-yaw-fast-360/CameraMotionAnalysis/SMAA-Camera-Motion-Original-Five-Analysis-ko.md`
- 대표 시트: `camera_motion_representative_sheet.png`
- 회전 6-way GIF: `camera_motion_rotation_comparison.gif`
- CGVQM error-map: 각 mode 폴더의 `CGVQM-2-ErrorMap.mkv`

## 6. Python access violation과 수정

첫 Bistro 180-frame 분석은 `CGVQM-2-PerFrame.csv`를 쓴 뒤 error-map 영상 생성 중
Windows native access violation으로 종료됐다. 당시 adapter는 180개 context PNG,
전체 error tensor와 전체 colorized heatmap을 동시에 메모리에 유지했다. 계산 자체는
끝났지만 최종 JSON이 생성되기 전이었다.

`run_cgvqm_png_sequences.py`의 error-map 색상화를 frame streaming 방식으로 변경했다.
각 frame의 context와 heatmap만 메모리에 두고 즉시 FFV1로 encode한다. 수정 후 2-frame
smoke, Bistro 5개 mode와 Minecraft 5개 mode의 180-frame 전체 실행, error-map MKV와
결과 JSON 생성을 모두 통과했고 access violation은 재발하지 않았다.

공식 CGVQM 본체는 여전히 입력 두 영상을 한꺼번에 float tensor로 읽으므로 mode는 반드시
순차 실행한다. 한 mode가 끝나 RAM이 반환된 뒤 다음 mode를 시작하며, 여러 CGVQM
프로세스를 병렬 실행하지 않는다.

## 7. 다음 작업

1. 같은 camera profile을 `O-1X`/`A-1X` control과 최종 8-case로 확장한다.
2. 두 장면을 분리해 Original↔Adaptive, Standard↔Edge-selective,
   Reprojection Off↔On 축을 비교한다.
3. `yaw-extreme-360`, `strafe-fast`, `yaw-strafe-fast`는 yaw-fast 결과에서 드러나지 않은
   큰 UV 이동, parallax와 disocclusion의 stress profile로 후속 측정한다.
4. 현재-frame edge dilation과 filtered downsample-upsample은 별도 thin-geometry
   ablation으로 진행한다. 이전-frame edge mask는 추가 camera-motion 고스팅 근거가
   확인될 때만 검토한다.
