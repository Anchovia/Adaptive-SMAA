# SMAA Motion→Still Temporal Coverage 분리 실험

날짜: 2026-08-30

브랜치: `research/et2x-pipeline-optimization`

## 1. 실험 질문

최종 8-case 결과에서 `O-ET2X-R`은 중앙 camera-motion 구간에서는 `O-T2X-R`보다
좋았지만, motion→still transition에서는 더 낮은 CGVQM-2 점수를 보였다.

이번 실험은 다음 가설을 먼저 검증한다.

> ET2X가 현재 edge candidate에만 history를 적용하기 때문에 정지 전환에서 필요한
> temporal accumulation을 충분히 확보하지 못한 것인가?

이 원인을 확인하지 않은 채 previous-edge persistence나 confidence 확장을 추가하면,
coverage 문제와 temporal kernel 차이를 다시 섞게 된다. 따라서 동일한 document temporal
kernel을 full-screen과 edge-selective로만 나누는 진단 control을 사용했다.

## 2. 통제 비교

| Mode | Spatial input | Jitter | Reprojection | Sampler | Clipping | Weight | Coverage |
|---|---|---|---|---|---|---:|---|
| `O-T2X-R` | SMAA T2X spatial | On | camera/depth | Bilinear | Off | 0.5 | Full-screen |
| `ABL-Document-FullScreen-R` | SMAA 1X | Off | camera/depth | Catmull-Rom 5-tap | YCoCg | 0.8 | Full-screen |
| `O-ET2X-R` | SMAA 1X | Off | camera/depth | Catmull-Rom 5-tap | YCoCg | 0.8 | Integrated first-pass edge candidate |

핵심 pair는 `ABL-Document-FullScreen-R`과 `O-ET2X-R`이다. 두 mode는 temporal
coverage와 실행 구조를 제외한 위 설정 및 history lifecycle을 동일하게 유지한다.
`O-T2X-R`은 Standard 기준선이지만 여러 축이 동시에 다르므로 coverage-only 비교로
사용하지 않는다.

`ABL-Document-FullScreen-R`은 원래 matched-kernel 성능 원인 분리를 위해 존재하던
진단 mode이며, 정식 8-case를 늘리는 아홉 번째 연구 case가 아니다.

## 3. 구현 및 자동화

### 3.1 동일 실행 4-way capture

`Projects/CMAA2/CMAA2Sample.cpp`에 다음 명령을 추가했다.

```text
-smaaMotionToStillCoverageCapture <bistro|minecraft> flythrough-wide-yaw-360
```

한 clean process 안에서 mode마다 history를 초기화하고 다음 네 sequence를 동일한
480-frame fixed-timestep camera path로 저장한다.

```text
O-1X
O-T2X-R
ABL-Document-FullScreen-R
O-ET2X-R
```

### 3.2 연속 프레임 분석

`Tools/SMAA/analyze_motion_to_still_coverage.py`는 다음을 검증·계산한다.

- 장면·profile·classification·480-frame index·해상도
- 동일 pose supersample spatial-reference 대비 RGB MAE, PSNR, luma SSIM, edge strength
- signed temporal delta residual
- central motion, transition, early post-still, late post-still 구간
- 마지막 10 frame plateau에 대한 filter-state recovery offset

Temporal delta는 `uint8` wraparound를 피하기 위해 signed 차분으로 계산한다. Plateau
진단은 float32 RGB MAE와 최소 허용치 `0.01` code value, 5-frame 연속 조건을 사용한다.
Plateau offset은 절대 ghost trail 길이가 아니라 필터 상태 수렴 보조 지표다.

### 3.3 Formal CGVQM-2

- `Tools/SMAA/run_motion_to_still_coverage_cgvqm.py`: 새 full-screen document sequence의
  Bistro/Minecraft central-motion 및 transition 4개 job을 순차 실행
- `Tools/SMAA/analyze_motion_to_still_coverage_cgvqm.py`: 기존 formal control과 새 결과를
  결합하고 공식 commit, CUDA/GPU, frame range, reference hash 및 FFV1 왕복을 검증

## 4. 실행 및 검증

- Release x64 build: PASS
- Temporal lifecycle: `failures 0`, reset 48, frames 130
- 4-frame command smoke: 네 mode 모두 4 PNG, clean exit
- Bistro formal capture: `D:/SMAA-Research-Data/AutoBench/20260830_205412`
- Minecraft formal capture: `D:/SMAA-Research-Data/AutoBench/20260830_205758`
- 각 장면: 4 mode × 480 PNG
- 캡처 종료 후 residual `CMAA2.exe`: 0
- 재사용 formal control hash bridge: 2,880 PNG, byte mismatch 0
- CGVQM-2 result validation: 16/16 PASS
- Test/reference FFV1 decoded RGB mismatch: 0
- IntelLabs/CGVQM official commit:
  `8302ff45b4ff5a691682baf23f7c007d6b591e98`
- GPU: NVIDIA GeForce RTX 3060 Ti / CUDA

## 5. Spatial-reference proxy 결과

Supersample 입력은 동일 pose의 **spatial-reference proxy**이며 절대 temporal ground
truth가 아니다. 아래 값은 coverage-only pair에서 `O-ET2X-R`이
`ABL-Document-FullScreen-R`보다 변화한 비율이다. 음수는 오차 감소다.

| Scene | Window | RGB MAE 변화 | Temporal delta residual 변화 |
|---|---|---:|---:|
| Bistro | Central motion | -8.505% | -7.407% |
| Minecraft | Central motion | -13.971% | -4.704% |
| Bistro | Late post-still | -2.138% | -45.240% |
| Minecraft | Late post-still | -6.166% | -39.795% |

Spatial-reference proxy에서는 edge-selective가 full-screen document보다 중앙 이동과
후기 정지 모두 낮은 reference 오차를 보였다. 따라서 이 지표만으로는 후보 범위를
넓혀야 한다는 근거가 나오지 않았다.

Plateau recovery offset은 다음과 같다.

| Scene | O-1X | O-T2X-R | FullScreenDocument-R | O-ET2X-R |
|---|---:|---:|---:|---:|
| Bistro | 0 | 1 | 7 | 6 |
| Minecraft | 0 | 1 | 9 | 8 |

## 6. Formal CGVQM-2 결과

CGVQM-2는 높을수록 좋다. 이는 full-reference perceptual video metric이며 절대 ghosting
ground truth로 표현하지 않는다.

| Scene | Window | O-1X | O-T2X-R | FullScreenDocument-R | O-ET2X-R | Edge−Full | Edge−Standard |
|---|---|---:|---:|---:|---:|---:|---:|
| Bistro | Central motion | 96.981567 | 94.133018 | 96.483780 | 96.688606 | +0.204826 | +2.555588 |
| Minecraft | Central motion | 97.565102 | 95.986458 | 97.481895 | 97.515762 | +0.033867 | +1.529305 |
| Bistro | Motion→still | 94.410881 | 95.126778 | 94.746887 | 94.560982 | -0.185905 | -0.565796 |
| Minecraft | Motion→still | 93.409264 | 94.646790 | 93.836052 | 93.739021 | -0.097031 | -0.907768 |

### 6.1 Central motion

두 장면 모두 `O-ET2X-R`이 matched `FullScreenDocument-R`보다 높았다. Edge-selective
coverage가 camera motion 구간의 품질 손실 원인이라는 가설은 지지되지 않았다.

### 6.2 Motion→still transition

두 장면 모두 `FullScreenDocument-R`이 `O-ET2X-R`보다 소폭 높았다. 따라서 현재
frame의 edge candidate로 history를 제한하는 것이 정지 전환 손실에 **일부** 관여한다.

다만 FullScreenDocument-R도 Standard `O-T2X-R`보다 Bistro `0.379891`, Minecraft
`0.810738`점 낮았다. Edge-selective→FullScreenDocument의 점수 회복량은
Standard와 edge-selective 사이 점수 격차의 Bistro 약 32.9%, Minecraft 약 10.7%에
해당한다. 이 비율은 비선형 metric의 단순 점수 격차 비교이며 품질 원인의 기여율로
해석하지 않는다.

## 7. 기존 matched-kernel 성능 결과와 결합

동일 document kernel의 4,800 frame × 3회 성능 결과에서 reprojection On pair는 다음과
같았다.

| Scene | FullScreenDocument-R | O-ET2X-R | Edge-selective 변화 |
|---|---:|---:|---:|
| Bistro | 0.445663 ms | 0.349862 ms | -21.50% |
| Minecraft | 0.454113 ms | 0.391691 ms | -13.75% |

따라서 edge candidate 제한은 동일 kernel의 temporal 비용을 실제로 줄인다. 이번 품질
gate에서도 중앙 움직임 품질을 해치지 않았다. 정지 전환에서는 소폭 손실이 있지만,
무조건 full-screen으로 되돌리는 방식은 성능 이점을 잃고 Standard 수준의 transition
품질도 회복하지 못한다.

## 8. 결론

1. Motion→still 손실을 restricted coverage 하나로만 설명할 수 없다.
2. Coverage 제한은 transition 손실에 일부 관여하지만 central motion에서는 오히려
   matched full-screen보다 유리했다.
3. FullScreenDocument-R도 Standard T2X-R에 미치지 못하므로 남은 차이는 Standard의
   projection jitter/sample diversity 또는 sampler, clipping, weight 차이에 있다.
4. 현재 증거로 previous-edge persistence나 full-screen confidence 확장을 바로 기본
   경로에 추가하지 않는다.
5. 다음 gate는 full-screen Standard kernel에서 deliberate jitter만 On/Off로 바꾸는
   `ABL-Standard-NoJitter-R`를 구성해 jitter/sample diversity 효과를 먼저 분리한다.
6. 그 결과에서 restricted coverage의 추가 보완 필요성이 남을 때만 candidate persistence,
   confidence 또는 edge dilation을 각각 독립 ablation으로 검토한다.

## 9. 결과물

- 연속 프레임 분석:
  `D:/SMAA-Research-Data/AutoBench/20260830_MotionToStillCoverage`
- Formal CGVQM 원시 결과:
  `D:/SMAA-Research-Data/AutoBench/20260830_MotionToStillCoverage/CGVQM-FullScreenDocument`
- Formal CGVQM 집계:
  `D:/SMAA-Research-Data/AutoBench/20260830_MotionToStillCoverage/CGVQM-Analysis`
- 핵심 보고서:
  `SMAA-Motion-To-Still-Coverage-Analysis-ko.md`
  및 `CGVQM-Analysis/SMAA-Motion-To-Still-Coverage-CGVQM-ko.md`
