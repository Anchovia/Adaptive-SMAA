# SMAA 급격한 카메라 회전 고스팅 평가 결과

## 1. 실험 범위

교수 피드백에 따라 새 asset을 추가하기 전에 기존 저대비 Bistro와 고대비 Minecraft에서
결정적인 `yaw-fast-360` camera profile을 적용했다. 먼저 Original 공간 처리 5-way로
평가 파이프라인을 engineering 검증했고, 이어 같은 profile에서 최종 8-case와
`O/A-1X` control을 포함한 10-way formal 품질 측정을 완료했다.

- GPU: NVIDIA GeForce RTX 3060 Ti
- DirectX 11, Release x64, SMAA Ultra, VSync Off
- 1920×1017, fixed 60 Hz
- profile: 60-frame pre-still + 60-frame 360° yaw + 60-frame post-still
- mode별 60-frame warm-up
- formal 비교: 최종 8-case + `O-1X`/`A-1X` control, 총 10개 sequence
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

## 5. 최종 8-case + O/A-1X formal 결과

Original 5-way engineering 결과의 재현 여부를 확인하면서 Adaptive 공간 축까지 같은
capture와 reference에 추가했다. 각 장면은 10 mode × 180 PNG이며, 모든 mode가
00000~00179 연속 index와 누락 0을 통과했다. 20개 CGVQM 실행은 모두
`classification=formal`, test/reference 180 frame, FFV1 RGB round-trip mismatch 0이다.

### Bistro 저대비 장면

- capture: `Projects/CMAA2/AutoBench/20260812_201017`
- CGVQM: `Projects/CMAA2/AutoBench/20260812_201017/CGVQM-CameraMotion-Bistro-yaw-fast-360-Final`
- analysis: `Projects/CMAA2/AutoBench/20260812_201017/CameraMotionAnalysis`

| Mode | CGVQM-2 ↑ | 회전 error mean ↓ | 회전 대응 1X MAE ↓ | 회전 2차 luma diff ↓ | Recovery |
|---|---:|---:|---:|---:|---:|
| `O-1X` | 94.398033 | 3.082100 | 0.000000 | 57.031053 | 0 |
| `O-T2X` | 71.426331 | 75.328761 | 17.677998 | 25.769528 | 0 |
| `O-T2X-R` | 94.284134 | 6.669650 | 2.398998 | 56.945341 | 0 |
| `O-ET2X` | 93.626579 | 5.223690 | 0.694319 | 55.449138 | 0 |
| `O-ET2X-R` | 94.414253 | 3.212687 | 0.470493 | 56.610599 | 0 |
| `A-1X` | 94.407768 | 3.067560 | 0.000000 | 57.060111 | 0 |
| `A-T2X` | 71.493774 | 75.291968 | 17.683582 | 25.780993 | 0 |
| `A-T2X-R` | 94.362854 | 6.599439 | 2.385119 | 56.972935 | 0 |
| `A-ET2X` | 93.634682 | 5.215792 | 0.698966 | 55.465548 | 0 |
| `A-ET2X-R` | 94.428604 | 3.190328 | 0.475414 | 56.629668 | 0 |

### Minecraft 고대비 장면

- capture: `Projects/CMAA2/AutoBench/20260812_205656`
- CGVQM: `Projects/CMAA2/AutoBench/20260812_205656/CGVQM-CameraMotion-Minecraft-yaw-fast-360-Final`
- analysis: `Projects/CMAA2/AutoBench/20260812_205656/CameraMotionAnalysis`

| Mode | CGVQM-2 ↑ | 회전 error mean ↓ | 회전 대응 1X MAE ↓ | 회전 2차 luma diff ↓ | Recovery |
|---|---:|---:|---:|---:|---:|
| `O-1X` | 97.817940 | 0.809685 | 0.000000 | 47.090112 | 0 |
| `O-T2X` | 82.948639 | 46.181318 | 14.336844 | 20.857147 | 0 |
| `O-T2X-R` | 97.438858 | 2.641186 | 1.158026 | 47.049499 | 2 |
| `O-ET2X` | 97.390831 | 1.932351 | 0.360321 | 46.299568 | 2 |
| `O-ET2X-R` | 97.740921 | 1.088510 | 0.232715 | 46.921585 | 0 |
| `A-1X` | 97.816376 | 0.810864 | 0.000000 | 47.092825 | 0 |
| `A-T2X` | 82.977921 | 46.176576 | 14.337164 | 20.858023 | 0 |
| `A-T2X-R` | 97.470024 | 2.631120 | 1.155891 | 47.051717 | 2 |
| `A-ET2X` | 97.389297 | 1.933694 | 0.360842 | 46.301064 | 2 |
| `A-ET2X-R` | 97.740105 | 1.088482 | 0.233222 | 46.923624 | 0 |

### 세 독립 축의 해석

1. **Reprojection Off→On:** Standard T2X의 회전 중 큰 history 오정렬은 양 공간
   mode에서 camera reprojection으로 대부분 교정됐다. 이 결과는 camera-motion
   reprojection의 필요성을 직접 지지한다.
2. **Standard→Edge-selective:** reprojection Off에서도 edge-selective가 full-screen
   history 오정렬의 피해 범위를 크게 줄였다. 다만 대응 1X MAE와 시간 차분이 1X에
   가까워 temporal supersampling을 충분히 유지했다는 증거는 아니다.
3. **Original→Adaptive:** 대응 mode의 CGVQM-2 변화는 Bistro 최대 약 0.079점,
   Minecraft 최대 약 0.032점으로 작고 방향도 일관되지 않았다. 이 pure-yaw 품질
   profile에서는 Adaptive 공간 축이 temporal 결론을 바꾸지 않았다. 통계적 동등성을
   주장하는 수치는 아니다.
4. **현재 최선의 temporal 경로:** `O/A-ET2X-R`은 두 장면에서 눈에 띄는 회전
   고스팅이 없고 CGVQM도 1X에 가장 가까운 temporal mode였다. 그러나 1X와 매우 가까운
   시간 거동 때문에 고스팅 억제와 temporal 이득 유지 사이의 trade-off는 여전히 남는다.
5. **이전 edge 확장 판단:** 현재 edge만 사용하는 `ET2X-R`에서 pure-yaw 고스팅 근거가
   확인되지 않았으므로 이전-frame edge mask 교집합·dilation을 즉시 추가할 근거는
   약하다. 현재-frame edge 확장은 얇은 선 복구를 위한 별도 ablation으로 유지한다.

이 결론은 `yaw-fast-360` pure rotation에 한정한다. parallax/disocclusion과 더 큰 UV
이동은 다른 camera profile에서 별도로 확인해야 한다.

## 6. 대표 자료

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

### 최종 formal 11-way 자료

- Bistro 대표 시트:
  `Projects/CMAA2/AutoBench/20260812_201017/CameraMotionAnalysis/camera_motion_representative_sheet.png`
- Bistro 회전 GIF:
  `Projects/CMAA2/AutoBench/20260812_201017/CameraMotionAnalysis/camera_motion_rotation_comparison.gif`
- Minecraft 대표 시트:
  `Projects/CMAA2/AutoBench/20260812_205656/CameraMotionAnalysis/camera_motion_representative_sheet.png`
- Minecraft 회전 GIF:
  `Projects/CMAA2/AutoBench/20260812_205656/CameraMotionAnalysis/camera_motion_rotation_comparison.gif`

각 자료의 열은 SS-Reference, Original 1X/4 temporal mode, Adaptive 1X/4 temporal mode의
총 11-way 비교다.

## 7. Python access violation과 수정

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

Bistro formal `O-ET2X-R`의 첫 FFV1 검증에서 약 10억 channel value 중 1개가 일시적으로
다르게 읽혔으나, 같은 파일을 독립적으로 두 번 다시 decode하면 mismatch 0이 재현됐다.
파일 손상과 실제 codec 오차를 구분하기 위해 round-trip verifier는 첫 mismatch가 있을
때 한 번 독립 decode를 반복하고, 두 시도 모두 실패할 때만 오류로 판정하도록 보강했다.
재실행된 formal 결과와 나머지 19개 결과는 최종 mismatch 0이다.

## 8. 다음 작업

1. `yaw-extreme-360`, `strafe-fast`, `yaw-strafe-fast`는 yaw-fast 결과에서 드러나지 않은
   큰 UV 이동, parallax와 disocclusion의 stress profile로 후속 측정한다.
2. 현재-frame edge dilation과 filtered downsample-upsample은 별도 thin-geometry
   ablation으로 진행한다. 이전-frame edge mask는 추가 camera-motion 고스팅 근거가
   확인될 때만 검토한다.
3. 얇은 선 복구 ablation은 3×3/5×5/7×7 dilation과 filtered downsample-upsample을
   비교하고, 품질·history 적용률·flicker·GPU 비용을 함께 측정한다.
