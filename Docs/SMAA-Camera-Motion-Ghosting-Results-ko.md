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

## 8. 실시간 재생과 60 FPS 영상 검증

PNG 품질 capture는 각 frame을 GPU에서 CPU로 readback하고 동기적으로 파일에 저장한다.
따라서 캡처 중 보이는 애플리케이션 창이 9~10 FPS까지 떨어지는 것은 기록된 camera
timeline의 frame 누락을 의미하지 않는다. 기존 formal sequence는 mode마다 180개 연속
frame을 포함하지만, 실행 창만 저장 비용 때문에 느리게 보일 수 있다.

이를 분리하기 위해 PNG를 저장하지 않는 `-smaaCameraMotionPreview`를 추가했다. 이
preview는 analytical camera frame을 건너뛰지 않으면서 벽시계 기준 60 Hz로 제한하고,
큰 로딩 stall 뒤에는 catch-up frame을 몰아서 실행하지 않는다.

```powershell
.\CMAA2.exe -smaaCameraMotionPreview "<bistro|minecraft> <profile> [semantic-mode] [repeatCount]"
```

2026-08-13 Bistro `O-ET2X-R` visible-window engineering 검증 결과는 다음과 같다.

| Profile | 회전 구간 | 각도 간격 | 평균 frame-start 간격 | 최소~최대 |
|---|---:|---:|---:|---:|
| `yaw-slow-360` | 240 frame / 4초 | 1.5°/frame | 16.669 ms | 14.836~18.233 ms |
| `yaw-fast-360` | 60 frame / 1초 | 6.0°/frame | 16.669 ms | 15.005~18.240 ms |

따라서 기존 `yaw-fast-360`은 불규칙하게 frame을 건너뛴 경로가 아니라 정확한 60 Hz에서
프레임마다 6°를 이동하는 고속 stress profile이다. CMAA2 기본 flythrough와 비슷한
시각적 부드러움을 확인할 때는 프레임당 1.5°인 `yaw-slow-360`을 사용한다. 두 profile
모두 가감속 없는 등속 회전이므로 시작·종료 경계는 의도적으로 즉시 바뀐다.
기존 formal `O-1X`의 회전 구간 frame 60~119도 Bistro와 Minecraft 각각 60개 중
SHA-256 고유 hash 60개, 인접 중복 0으로 확인했다.

기존 PNG sequence를 발표용으로 확인하기 위해
`Tools/SMAA/create_camera_motion_playback.py`도 추가했다. 원본 frame index와 해상도를
검증하고, 단일 mode 및 지정한 mode 비교 영상을 H.264/MP4 constant 60 FPS로 생성한 뒤
전체 영상을 다시 decode해 frame 수, 평균 frame rate와 PTS 증가를 확인한다.

- Bistro: `Projects/CMAA2/AutoBench/20260812_201017/Playback60fps`
- Minecraft: `Projects/CMAA2/AutoBench/20260812_205656/Playback60fps`
- 각 장면: `O-1X` 단일 영상 + `O-1X | O-T2X | O-ET2X-R` 3-way 영상
- 검증: 180 frame, 60 FPS, constant PTS 1/60초, 3.000초, H.264/yuv420p

MP4는 발표·육안 확인용 손실 압축 영상이다. CGVQM과 정식 수치는 계속 원본 PNG와
RGB-preserving FFV1을 사용한다. `yaw-fast-360`은 2회 연속 반복한 359개
frame-start 간격까지 포함한다. Preview 추가 후 temporal lifecycle도 reset 36,
frame 114, seed 19, resolve 95, reprojection 45, failure 0으로 PASS했다.

## 9. Parallax·복합 camera-motion 후속 formal 결과

2026-08-13에 pure-yaw 결과를 보강하기 위해 Bistro 저대비와 Minecraft 고대비 장면에서
`strafe-fast`와 `yaw-strafe-fast`를 최종 8-case + `O/A-1X` control로 측정했다.
두 profile 모두 fixed 60 Hz의 pre-still 60 frame, motion 120 frame, post-still 60
frame으로 구성된다. 장면·profile마다 10 mode × 240 PNG와 같은 pose의
SS-Reference 240 PNG를 사용했다. CGVQM은 공식 IntelLabs/CGVQM commit `8302ff45`,
model 2, CUDA, patch scale 3, mean pooling으로 mode를 하나씩 순차 실행했다.

### 9.1 산출물

| 장면·profile | 10-way capture/analysis | SS-Reference |
|---|---|---|
| Bistro `strafe-fast` | `Projects/CMAA2/AutoBench/20260813_013331` | `Projects/CMAA2/AutoBench/20260813_013845/SS_Reference` |
| Minecraft `strafe-fast` | `Projects/CMAA2/AutoBench/20260813_023150` | `Projects/CMAA2/AutoBench/20260813_023846/SS_Reference` |
| Bistro `yaw-strafe-fast` | `Projects/CMAA2/AutoBench/20260813_032105` | `Projects/CMAA2/AutoBench/20260813_032603/SS_Reference` |
| Minecraft `yaw-strafe-fast` | `Projects/CMAA2/AutoBench/20260813_041648` | `Projects/CMAA2/AutoBench/20260813_042324/SS_Reference` |

각 capture root의 `CameraMotionAnalysis`에는 `camera_motion_summary.csv`, 전체
frame별 CSV/JSON, 11-way 대표 시트와 `camera_motion_comparison.gif`가 있다. 입력
sequence는 모두 00000~00239 연속이며 최종 CGVQM 입력의 FFV1 RGB round-trip
mismatch는 0이다. Minecraft `yaw-strafe-fast`의 빈 초기화 실패 root
`20260813_041600`과 PNG 0장으로 중단한 reference root `20260813_042034`는 결과에서
제외했다.

### 9.2 CGVQM-2 결과

높을수록 SS-Reference에 가깝다. 이 reference는 한 frame 안의 spatial supersample
proxy이며 절대적인 temporal ghosting ground truth는 아니다.

| Mode | Bistro strafe | Minecraft strafe | Bistro yaw+strafe | Minecraft yaw+strafe |
|---|---:|---:|---:|---:|
| `O-1X` | 93.9107 | 96.3603 | 94.8757 | 97.2766 |
| `O-T2X` | 81.1557 | 81.3310 | 64.6599 | 79.3864 |
| `O-T2X-R` | 94.7023 | 96.4396 | 93.9159 | 96.8836 |
| `O-ET2X` | 91.3870 | 94.8152 | 93.6000 | 96.6377 |
| `O-ET2X-R` | 93.7334 | 96.1257 | 94.7905 | 97.1111 |
| `A-1X` | 93.9340 | 96.3523 | 94.8983 | 97.2708 |
| `A-T2X` | 81.2244 | 81.3657 | 64.7222 | 79.4099 |
| `A-T2X-R` | 94.7792 | 96.4781 | 93.9945 | 96.9102 |
| `A-ET2X` | 91.4072 | 94.8116 | 93.6180 | 96.6323 |
| `A-ET2X-R` | 93.7585 | 96.1190 | 94.8167 | 97.1071 |

Original mode의 motion 구간 error mean은 다음과 같다. 낮을수록 SS-Reference에
가깝다.

| Mode | Bistro strafe | Minecraft strafe | Bistro yaw+strafe | Minecraft yaw+strafe |
|---|---:|---:|---:|---:|
| `O-1X` | 5.1983 | 2.7573 | 3.2682 | 0.9246 |
| `O-T2X` | 32.4255 | 33.8740 | 65.4172 | 37.7633 |
| `O-T2X-R` | 5.2870 | 3.6254 | 6.8581 | 2.7305 |
| `O-ET2X` | 10.1488 | 5.7826 | 5.7262 | 2.1481 |
| `O-ET2X-R` | 5.6142 | 3.2473 | 3.5131 | 1.2722 |

### 9.3 관찰

1. **Camera reprojection은 필수에 가깝다.** `O-T2X`는 네 실험 모두 motion 구간
   reference error가 가장 컸고, 특히 Bistro `yaw-strafe-fast`의 CGVQM-2는
   `64.6599`까지 낮아졌다. 대표 시트에서도 이전 pose가 넓게 겹치는 이중 잔상이
   확인됐다.
2. **단순 strafe에서는 Standard reprojection이 우세했다.** `O-T2X-R`은 Bistro와
   Minecraft에서 각각 `94.7023`, `96.4396`으로 `O-ET2X-R`보다 `0.9689`,
   `0.3139` 높았다.
3. **회전+이동에서는 Edge-selective reprojection이 우세했다.** `O-ET2X-R`은
   Bistro와 Minecraft에서 `O-T2X-R`보다 각각 `0.8746`, `0.2275` 높았고 motion
   error mean도 `6.8581→3.5131`, `2.7305→1.2722`로 낮았다. 큰 복합 camera
   motion에서는 history 적용 범위를 edge 후보로 제한하는 것이 reprojection 오차의
   피해를 줄일 가능성이 있다.
4. **Temporal 이득 유지 여부는 아직 보류한다.** `O-ET2X-R`의 motion 구간 1X 대비
   RGB MAE는 네 실험에서 `0.2516~0.5549`로 매우 작았다. 이는 현재 형상 보존에는
   유리하지만 출력이 1X에 가까워 temporal supersampling을 충분히 유지하지 못했을
   가능성도 뜻한다. CGVQM 우위만으로 flicker/shimmer 개선을 주장하지 않는다.
5. **No-reprojection Edge-selective는 피해를 줄이지만 완전한 대안은 아니다.**
   `O-ET2X`는 `O-T2X`보다 크게 회복됐지만 post-still recovery가 네 조건에서 2~3
   frame이었고, SS-Reference 점수는 reprojection On 또는 1X보다 낮았다.
6. **Adaptive 공간 축은 temporal 결론을 바꾸지 않았다.** 네 실험 전체에서 대응하는
   Original/Adaptive CGVQM-2 차이의 최대 절대값은 `0.0787`이었다.

따라서 현재 자료가 지지하는 결론은 “Edge-selective가 항상 Standard T2X보다 좋다”가
아니다. 단순 평행 이동에서는 `T2X-R`이 우세했고, 더 큰 회전+이동에서는
`ET2X-R`이 우세했다. Edge-selective의 이득은 camera-motion 유형에 의존하며, 1X에
가까워지는 temporal 손실 가능성과 함께 보고해야 한다.

## 10. 다음 작업

1. 교수님 피드백의 다음 핵심인 **현재-frame edge expansion**을 thin-geometry
   ablation으로 진행한다. 먼저 3×3/5×5/7×7 dilation을 비교한다.
2. dilation 비용이 크면 nearest-neighbor가 아닌 filtered downsample-upsample으로
   후보 영역을 확장하는 대안을 비교한다.
3. 기존 `thin-lines` stress 장면과 별도의 공개 thin-geometry 외부 장면을 같은
   1080p급 조건에서 사용한다. 끊어진 얇은 선 복구, history 적용률, flicker,
   고스팅과 GPU 비용을 함께 측정한다.
4. 이전-frame edge mask와 dilation은 현재-frame expansion 및 추가 camera-motion
   결과만으로 부족한 경우에만 후속 ablation으로 추가한다.
5. `yaw-extreme-360`은 더 큰 pure-yaw UV stress가 필요할 때 추가하는 선택적 검증으로
   남긴다. 현재 완료된 `yaw-fast-360`, `strafe-fast`, `yaw-strafe-fast` 결과를
   대체하지 않는다.
