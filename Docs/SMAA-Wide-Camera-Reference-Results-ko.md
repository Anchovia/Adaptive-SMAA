# SMAA Wide Camera Supersample Reference / CGVQM-2 결과

## 1. 목적

기존 smooth camera 실험에서 `O-ET2X-R`이 `O-T2X-R`보다 `O-1X`에 가까운 출력이라는
사실은 확인했지만, 그 차이가 잘못된 history 감소인지 temporal sample accumulation
손실인지는 spatial reference 없이 구분할 수 없었다.

이번 gate는 이동이 더 뚜렷한 `flythrough-wide-yaw-360` 경로에서 다음 세 mode를
동일 pose의 supersample spatial reference와 비교한다.

- `O-1X`: temporal history가 없는 Original SMAA 1X control
- `O-T2X-R`: full-screen Standard T2X + camera reprojection
- `O-ET2X-R`: current-edge candidate에만 history를 적용하는 TSCMAA-inspired 방식 +
  camera reprojection

## 2. 조건과 입력 검증

- 장면: Bistro 저대비, Minecraft 고대비
- camera: 480 frame, fixed 60 Hz, 약 3.72 m 이동 + 부드러운 360° yaw
- 렌더링: DirectX 11, SMAA Ultra, 1920×1017
- mode별 warm-up: 60 frame
- reference: 2× linear resolution, frame당 3×3 subpixel grid, 8× MSAA
- reference 한 출력 frame 동안 장면 상태 고정, temporal history 미사용
- CGVQM: IntelLabs/CGVQM commit `8302ff45`, model 2, CUDA, 60 FPS,
  patch scale 4, mean pooling

정식 capture root는 다음과 같다.

| Scene | 3-way capture | SS-Reference |
|---|---|---|
| Bistro | `Projects/CMAA2/AutoBench/20260827_013824` | `Projects/CMAA2/AutoBench/20260827_014143` |
| Minecraft | `Projects/CMAA2/AutoBench/20260827_014324` | `Projects/CMAA2/AutoBench/20260827_014612` |

두 장면 모두 mode당 480 PNG가 연속이며 총 3,840 PNG를 검증했다. 새 O-1X와 2026-08-20
visible-window 경로 확인 capture의 대응 480 PNG SHA-256 mismatch는 두 장면 모두 0이다.
CGVQM 입력은 RGB-preserving FFV1로 변환한 뒤 전체 decode 결과를 원본 PNG와 비교했고,
12개 실행 모두 pixel mismatch 0이었다.

분석 결과 root는 다음과 같다.

- `Projects/CMAA2/AutoBench/20260827_WideCameraReference_Formal/Analysis`
- `Projects/CMAA2/AutoBench/20260827_WideCameraReference_Formal/CGVQM`

## 3. 전체 480-frame spatial-reference 결과

SS-Reference는 한 frame 안의 spatial supersampling proxy다. temporal ground truth 또는
절대적인 ghosting ground truth라고 표현하지 않는다.

| Scene | Mode | RGB MAE ↓ | PSNR ↑ | Luma SSIM ↑ | Edge / reference |
|---|---|---:|---:|---:|---:|
| Bistro | `O-1X` | 1.577217 | 35.7525 | 0.981365 | 1.005293 |
| Bistro | `O-T2X-R` | 2.045134 | 33.9554 | 0.970465 | 0.961248 |
| Bistro | `O-ET2X-R` | 1.652512 | 35.3674 | 0.979548 | 0.981994 |
| Minecraft | `O-1X` | 1.330643 | 33.6656 | 0.975452 | 1.007587 |
| Minecraft | `O-T2X-R` | 1.577457 | 33.3814 | 0.968138 | 0.944279 |
| Minecraft | `O-ET2X-R` | 1.331066 | 33.9039 | 0.974925 | 0.970137 |

`O-ET2X-R`의 RGB MAE는 Standard보다 Bistro 19.20%, Minecraft 15.62% 낮다. 그러나
O-1X보다는 Bistro 4.77% 높고 Minecraft 0.03% 높다. Standard의 edge/reference 비율은
두 장면 모두 가장 낮아 더 큰 blur 경향을 보인다.

## 4. 공식 CGVQM-2 결과

메모리 사용과 해석 범위를 통제하기 위해 두 구간을 서로 독립적으로 평가했다.

- central motion: profile frame 150~329, 180 frame
- motion→still transition: profile frame 410~439, 30 frame

두 점수는 합치거나 하나의 평균으로 사용하지 않는다. 높을수록 SS-Reference에 가깝다.

| Scene | Window | O-1X | O-T2X-R | O-ET2X-R | ET − Standard | ET − 1X |
|---|---|---:|---:|---:|---:|---:|
| Bistro | central motion | 96.9816 | 94.1330 | 96.6804 | +2.5474 | -0.3011 |
| Bistro | transition | 94.4109 | 95.1268 | 94.5747 | -0.5521 | +0.1638 |
| Minecraft | central motion | 97.5651 | 95.9865 | 97.5224 | +1.5360 | -0.0427 |
| Minecraft | transition | 93.4093 | 94.6468 | 93.7529 | -0.8939 | +0.3436 |

중앙 motion에서는 Edge-selective가 Standard보다 두 장면 모두 높고 O-1X에 매우 가깝다.
반면 transition clip에서는 Standard가 가장 높다. 이 결과는 motion 종류와 phase에 따라
우위가 바뀐다는 뜻이며, 어느 한 방식이 항상 우수하다고 일반화하지 않는다.

## 5. CGVQM per-frame 경계 처리

공식 구현은 60 FPS 입력에서 30-frame clip을 독립 처리한다. CGVQM-2가 사용하는
R3D-18 stem과 layer1에는 시간축 3×3 convolution이 총 다섯 단계 있으므로, per-frame
error map의 temporal receptive-field radius는 5 frame이다.

이번 180/30-frame 입력은 clip size로 정확히 나누어져 입력 replicate padding은 없었다.
공식 CGVQM 점수는 전체 clip을 변경하지 않고 그대로 사용했다. 다만 per-frame 보조
진단에서는 각 clip 양쪽 5 frame을 제외했다. transition clip에서는 frame 415~419를
motion tail, 420~434를 post-still interior로 분리했다.

O-1X frame 420~439는 두 장면 모두 pixel hash가 하나로 완전히 고정됐다. Minecraft
SS-Reference도 동일했다. Bistro SS-Reference는 20개 hash였지만 첫 frame 대비 최대
차이 2/255, 전체 mean absolute difference 0.00001165의 극소수 GPU 누적 변동이었다.
따라서 error map 마지막 frame 변화는 camera가 다시 움직인 증거로 해석하지 않는다.

## 6. 결론

1. Wide camera supersample/CGVQM gate는 입력 정렬, 독립 재현성, lossless round-trip과
   두 장면 비교를 모두 통과했다.
2. `O-ET2X-R`은 central motion에서 Standard의 넓은 history 오차와 blur를 줄이는
   방향을 보였다.
3. 그러나 spatial reference 기준으로 O-1X를 일관되게 넘지 못했다. 현재 ET2X-R이
   temporal supersampling 이득을 충분히 유지한다고 주장할 근거는 아직 없다.
4. 그러므로 바로 전체 8-case로 확대하지 않고 current-edge candidate expansion을
   통해 얇은 구조의 temporal sample 기회를 늘릴 수 있는지 검증한다.

## 7. 다음 작업

다음 구현은 ARM Dual Filtering의 downsample/upsample kernel을 current-edge candidate
mask 확장에 적용하는 별도 research adaptation이다.

- 기존 `FilteredQuarter`는 4×4 평균 + bilinear 복원인 자체 ablation이므로 ARM Dual
  Filtering이라고 재명명하지 않는다.
- ARM 공개 자료의 kernel, sample offset과 결합식을 먼저 고정하고 구현 가정을 문서화한다.
- `None`, 정확한 `3×3`, 기존 `FilteredQuarter`, 새 `ArmDualFilter`를 같은 raw current-edge,
  threshold, camera path에서 비교한다.
- candidate/coverage와 얇은 구조 회복뿐 아니라 CGVQM, O-1X 대비 temporal retention,
  ghosting/blur 및 pass별 GPU 시간을 함께 기록한다.
- engineering correctness와 비용 smoke를 먼저 통과한 뒤에만 formal 품질 측정으로 확대한다.

## 8. 자동 분석 도구

- `Tools/SMAA/analyze_wide_camera_reference_quality.py`: 480-frame RGB MAE/PSNR/SSIM,
  edge strength, O-1X hash bridge, comparison/difference sheet
- `Tools/SMAA/analyze_wide_camera_cgvqm.py`: 12개 formal CGVQM JSON/CSV와 FFV1 검증,
  공식 점수 집계, clip-boundary-aware per-frame 진단, post-still 입력 안정성
