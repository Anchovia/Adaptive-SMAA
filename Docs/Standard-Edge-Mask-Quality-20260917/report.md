# Native Standard edge-mask 품질 비교

## 결론

이번 두 장면과 카메라 경로에서는 원본 `O-T2X-R`이 새 `ABL-Standard-EdgeMask-R`보다 품질이 좋았다. 중앙 이동과 이동→정지의 네 CGVQM 비교 모두 원본이 높고, 모든 분석 구간에서 원본의 spatial-reference MAE와 SSIM이 더 좋았다.

가장 큰 문제는 정지 후에도 남는 2-frame 교대 변화다. 원본은 후기 정지 구간에서 출력이 안정됐지만 새 방식은 계속 교대한다. 전 화면의 T2X paired jitter를 유지하면서 첫 패스 edge로 선택되지 않은 픽셀에서는 temporal 결합을 생략한 구조와 일치하는 관측이다. 어떤 비후보 영역이 지배적인지와 jitter·mask 변화의 기여도는 별도 효과 분리 실험을 하지 않았으므로 확정하지 않는다.

앞선 동일 branch 성능 측정에서도 새 방식의 SMAA 시간이 Bistro +1.49%, Minecraft +4.22% 증가했다. 따라서 현재 구현은 속도·품질 개선안으로 채택하지 않고, 첫-pass edge 선택만으로는 충분하지 않았다는 대조 실험으로 보존한다. TSCMAA 원본이나 다른 선택적 temporal 방식 전체에 대한 결론은 아니다.

## 비교 조건

- Original SMAA `O-T2X-R` 대 `ABL-Standard-EdgeMask-R`; 후보 적용 범위만 변경했다.
- 기존 native point sampling, velocity-adaptive weight, paired jitter/subsample과 spatial-frame history를 유지했다.
- Camera/depth reprojection On, object-motion/previous-depth rejection Off, 후보 확장 없음.
- Bistro/Minecraft 각각 두 mode × 480 PNG, 1920×1017, fixed 60 Hz, 60-frame 시작 pose warm-up.
- 전체 `flythrough-wide-yaw-360` timeline 0~479를 캡처했다. 중간 pose에서 history를 새로 시작하지 않았다.
- 두 장면의 원본 960 PNG 전체가 기존 정식 control과 SHA-256 일치했다. 기존 spatial reference와의 비교 조건을 연결했다.
- Reference: 같은 pose의 2× linear resolution, 3×3 within-frame subpixel grid, 8×MSAA. Temporal ground truth는 아니다.
- CGVQM-2: Intel commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`, CUDA, 60 FPS, patch scale 4 / mean pooling.
- 원본 점수는 해당 window의 decoded RGB pixel hash와 reference hash를 다시 확인한 뒤 재사용했다. 새 mode는 네 window를 새로 계산했다.
- 새 결과도 test/reference FFV1 round-trip mismatch 0과 index/해상도/commit/configuration 검증을 통과했다.
- 기존 점수와 새 점수의 torch 2.8.0+cu128, CUDA 12.8, RTX 3060 Ti와 metric 설정은 동일하다. Python patch version은 3.12.13→3.12.14로 다르다.
- RGB MAE/PSNR와 temporal 지표는 매 frame, SSIM은 8-frame 간격, edge strength는 4-frame 간격으로 계산했다.

## CGVQM-2

높을수록 reference에 대한 지각적 영상 품질이 좋다. 절대 고스팅 점수로 해석하지 않는다.

| 장면 | 구간 | Standard | EdgeMask | EdgeMask−Standard |
|---|---|---:|---:|---:|
| bistro | 중앙 이동 150~329 | 94.133018 | 93.741585 | -0.391434 |
| bistro | 이동→정지 410~439 | 95.126778 | 85.071358 | -10.055420 |
| minecraft | 중앙 이동 150~329 | 95.986458 | 95.675346 | -0.311111 |
| minecraft | 이동→정지 410~439 | 94.646790 | 85.479675 | -9.167114 |

## Spatial reference 오차

RGB MAE는 0~255 RGB level 기준이며 낮을수록 좋다.

| 장면 | 구간 | Standard MAE | EdgeMask MAE | 변화 | Standard SSIM | EdgeMask SSIM |
|---|---|---:|---:|---:|---:|---:|
| bistro | 중앙 이동 150~329 | 2.213424 | 2.387522 | +7.866% | 0.9623343 | 0.9552831 |
| bistro | 이동→정지 410~439 | 1.517998 | 2.315460 | +52.534% | 0.9839829 | 0.9621183 |
| bistro | 후기 정지 440~479 | 1.448690 | 2.292457 | +58.243% | 0.9844255 | 0.9623751 |
| minecraft | 중앙 이동 150~329 | 1.223720 | 1.306895 | +6.797% | 0.9719271 | 0.9656752 |
| minecraft | 이동→정지 410~439 | 1.531736 | 2.198823 | +43.551% | 0.9743310 | 0.9459792 |
| minecraft | 후기 정지 440~479 | 1.486788 | 2.180101 | +46.632% | 0.9745463 | 0.9461120 |

## 정지 후 시간 변화

후기 정지 440~479의 luma 1차·2차 시간 차분이다. 작은 값만으로 품질이 좋다고 단정할 수 없지만, 정지 장면의 교대 변화를 확인하는 보조 지표다.

| 장면 | Standard Δ1 | EdgeMask Δ1 | Standard Δ2 | EdgeMask Δ2 | Standard edge/reference | EdgeMask edge/reference |
|---|---:|---:|---:|---:|---:|---:|
| bistro | 0.000000 | 2.749006 | 0.000000 | 5.498012 | 0.955875 | 0.996617 |
| minecraft | 0.000000 | 2.817136 | 0.000000 | 5.634272 | 0.930220 | 0.975018 |

### 후기 정지 출력 주기 확인

440~479의 PNG SHA-256을 비교했다. 같은 hash는 전체 PNG byte 일치를 뜻한다.

| 장면 | Mode | 서로 다른 출력 | 인접 frame 일치 / 39 | 두 frame 간격 일치 / 38 |
|---|---|---:|---:|---:|
| bistro | O-T2X-R | 1 | 39 | 38 |
| bistro | ABL-Standard-EdgeMask-R | 2 | 0 | 38 |
| minecraft | O-T2X-R | 1 | 39 | 38 |
| minecraft | ABL-Standard-EdgeMask-R | 2 | 0 | 38 |

## 해석 범위와 시각 자료

- CGVQM, 동일-pose spatial 오차와 정지 후 변화를 함께 판단한다. 더 높은 edge strength는 aliasing이나 oversharpening일 수도 있다.
- 움직임 중 temporal-delta residual은 기준 영상의 프레임 차분을 뺀 값이다. Optical-flow 정렬이나 절대 고스팅 ground truth가 아니다.
- Camera-motion 두 실제 장면의 결과이며 독립 object motion, 다른 해상도·경로에 일반화하지 않는다.
- 캡처 도구 원시 report의 single-mode visualization 표기는 실행 경로의 기존 이름이다. 이번 분석에서는 전체 frame/index와 정식 control의 완전 일치를 검증해 품질 비교에 사용했다.
- 원시 PNG/CSV와 비교 그림·GIF는 Git에 포함하지 않고 다음 경로에 보존했다.

- bistro: `D:\SMAA-Research-Data\AutoBench\20260917_StandardEdgeMaskQuality\bistro` — frame 240/419/420/479 원본 및 reference 차이 ×8; motion/transition/late-still 고정 ROI GIF.
- minecraft: `D:\SMAA-Research-Data\AutoBench\20260917_StandardEdgeMaskQuality\minecraft` — frame 240/419/420/479 원본 및 reference 차이 ×8; motion/transition/late-still 고정 ROI GIF.

GIF는 60 Hz 원본을 20 FPS로 재생하는 3배 느린 확인용이다. 정식 지표에는 원본 PNG와 무손실 FFV1을 사용했다.

## 재현

```powershell
Tools/SMAA/run_standard_edge_mask_quality.ps1 -Scene bistro
Tools/SMAA/run_standard_edge_mask_quality.ps1 -Scene minecraft
python Tools/SMAA/analyze_standard_edge_mask_quality.py --scene bistro
python Tools/SMAA/analyze_standard_edge_mask_quality.py --scene minecraft
# 아래 두 CGVQM 작업은 기존 cgvqm-venv Python으로 순차 실행
.research-tools/cgvqm-venv/Scripts/python.exe Tools/SMAA/run_standard_edge_mask_quality_cgvqm.py --scene bistro
.research-tools/cgvqm-venv/Scripts/python.exe Tools/SMAA/run_standard_edge_mask_quality_cgvqm.py --scene minecraft
python Tools/SMAA/summarize_standard_edge_mask_quality.py
```

새 실행 묶음에는 캡처·분석의 `--receipt`/`-Receipt`를 같은 새 경로로 지정하고 결과 출력도 별도로 지정한다. 기존 결과를 덮어쓰거나 부분 결과를 재사용하지 않는다.
