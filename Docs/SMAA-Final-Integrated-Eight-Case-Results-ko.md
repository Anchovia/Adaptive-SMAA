# Final integrated SMAA 8-case 결과

## 1. 목적과 판정 범위

별도 full-screen temporal edge 재판정을 제거하고 SMAA 1st-pass edge 결과를 직접
candidate source로 사용하는 integrated core에서 최종 8개 mode를 같은 조건으로 다시
측정했다.

비교 축은 다음 세 가지다.

1. 공간 처리: Original SMAA / Adaptive SMAA
2. temporal coverage: Standard full-screen T2X / TSCMAA-inspired edge-selective T2X
3. motion reprojection: Off / On

`-R`은 현재 depth와 이전·현재 camera matrix로 만든 camera/depth reprojection이다.
Object motion vector는 이 camera-motion capture에 연결하지 않았다. 따라서 이 문서는
현재 integrated camera-motion core의 formal gate이며, 모든 object motion과
disocclusion 문제를 해결했다는 최종 논문 결론은 아니다.

## 2. 최종 8개 mode

| ID | Spatial | Temporal coverage | Camera/depth reprojection |
|---|---|---|---|
| `O-T2X` | Original | Standard | Off |
| `O-T2X-R` | Original | Standard | On |
| `O-ET2X` | Original | Edge-selective | Off |
| `O-ET2X-R` | Original | Edge-selective | On |
| `A-T2X` | Adaptive | Standard | Off |
| `A-T2X-R` | Adaptive | Standard | On |
| `A-ET2X` | Adaptive | Edge-selective | Off |
| `A-ET2X-R` | Adaptive | Edge-selective | On |

품질 비교에는 별도 최종 mode가 아닌 spatial control `O-1X`와 `A-1X`도 포함했다.

## 3. 실험 조건과 무결성

### 성능

- GPU: NVIDIA GeForce RTX 3060 Ti
- API/preset: DirectX 11, SMAA Ultra
- 해상도: 1920×1017
- VSync Off, visible window
- 장면: Bistro 저대비 / Minecraft 고대비
- 300 frames warm-up, 4,800 frames × 3 repeats
- mode별 필수 metric 14,400 samples, run mean 3개
- Candidate GPU→CPU readback Off
- 장면마다 독립 clean CMAA2 process
- 내부 benchmark와 분석기 validation 모두 PASS

### 품질

- camera profile: `flythrough-wide-yaw-360`
- fixed 60 Hz, 약 3.72 m translation + smooth 360° yaw
- mode별 첫 pose warm-up 60 frames
- 각 장면 10 modes × 480 PNG, 총 9,600 test PNG
- 같은 pose의 480-frame supersample spatial-reference proxy
- reference: 2× linear resolution, 3×3 within-frame subpixel grid, 8× MSAA
- 10-mode index·해상도·frame count와 reference provenance validation PASS

### Intel CGVQM

- IntelLabs/CGVQM official commit
  `8302ff45b4ff5a691682baf23f7c007d6b591e98`
- CGVQM-2, CUDA, 60 FPS, patch scale 4, mean pooling
- central motion 150–329와 motion→still 410–439를 독립 clip 집합으로 평가
- 2 scenes × 2 windows × 10 modes = 40 formal jobs
- 모든 최종 FFV1 decode의 RGB pixel mismatch 0
- 40개 result의 commit, CUDA, mode, index, 해상도, round-trip validation PASS
- 1920×1017 높이가 4의 배수가 아니어서 공식 도구의 error-map resolution warning이
  발생했다. Official score는 유지하되 시각화 error-map의 경계 해석에는 주의한다.

## 4. Formal 성능 결과

| Scene | Mode | WholeFrame GPU ms | SMAA GPU ms | Wall FPS |
|---|---|---:|---:|---:|
| Bistro | `O-T2X` | 2.969507 | 0.238517 | 330.264 |
| Bistro | `O-T2X-R` | 3.004134 | 0.282650 | 327.447 |
| Bistro | `O-ET2X` | 3.009501 | 0.311944 | 327.230 |
| Bistro | `O-ET2X-R` | 3.031888 | 0.348173 | 325.422 |
| Bistro | `A-T2X` | 2.956229 | 0.204769 | 329.211 |
| Bistro | `A-T2X-R` | 2.999409 | 0.249527 | 327.102 |
| Bistro | `A-ET2X` | 3.007380 | 0.279628 | 327.794 |
| Bistro | `A-ET2X-R` | 3.027519 | 0.315180 | 325.220 |
| Minecraft | `O-T2X` | 1.285647 | 0.255364 | 754.592 |
| Minecraft | `O-T2X-R` | 1.344468 | 0.299646 | 723.780 |
| Minecraft | `O-ET2X` | 1.405598 | 0.353806 | 692.978 |
| Minecraft | `O-ET2X-R` | 1.455795 | 0.393526 | 670.240 |
| Minecraft | `A-T2X` | 1.268434 | 0.234850 | 763.317 |
| Minecraft | `A-T2X-R` | 1.327775 | 0.279235 | 733.230 |
| Minecraft | `A-ET2X` | 1.387436 | 0.334046 | 700.526 |
| Minecraft | `A-ET2X-R` | 1.432300 | 0.372915 | 679.301 |

### Adaptive 공간 처리 효과

대응하는 Original mode 대비 Adaptive mode의 SMAA GPU 시간은 모든 case에서 감소했다.

| Scene | T2X | T2X-R | ET2X | ET2X-R |
|---|---:|---:|---:|---:|
| Bistro | -14.149% | -11.719% | -10.360% | -9.476% |
| Minecraft | -8.033% | -6.812% | -5.585% | -5.238% |

WholeFrame 감소는 Bistro -0.070~-0.447%, Minecraft -1.242~-1.614%였다.
Adaptive SMAA 자체의 pass 비용 감소는 재현됐지만, 전체 frame 개선 폭은 장면과 주변
렌더 부하에 의존한다.

### Edge-selective temporal 비용

Integrated first-pass source는 두 번째 full-screen edge extraction을 제거했지만,
대응 Standard T2X보다 아직 느렸다.

| Scene | Comparison | SMAA Δ | WholeFrame Δ |
|---|---|---:|---:|
| Bistro | `O-T2X → O-ET2X` | +30.785% | +1.347% |
| Bistro | `O-T2X-R → O-ET2X-R` | +23.182% | +0.924% |
| Bistro | `A-T2X → A-ET2X` | +36.558% | +1.730% |
| Bistro | `A-T2X-R → A-ET2X-R` | +26.311% | +0.937% |
| Minecraft | `O-T2X → O-ET2X` | +38.550% | +9.330% |
| Minecraft | `O-T2X-R → O-ET2X-R` | +31.330% | +8.280% |
| Minecraft | `A-T2X → A-ET2X` | +42.238% | +9.382% |
| Minecraft | `A-T2X-R → A-ET2X-R` | +33.549% | +7.872% |

따라서 candidate 수가 줄었다는 사실만으로 성능 최적화 성공을 주장할 수 없다.
현재 구현은 quality/coverage 연구 core로는 유효하지만, compact·indirect·candidate
resolve 비용을 포함한 전체 성능 목표는 미달이다.

## 5. 전체 480-frame spatial-reference 결과

| Scene | Mode | RGB MAE ↓ | PSNR ↑ | Luma SSIM ↑ | Edge/Ref |
|---|---|---:|---:|---:|---:|
| Bistro | `O-1X` | 1.577217 | 35.7525 | 0.981365 | 1.005293 |
| Bistro | `O-T2X` | 8.022534 | 26.6926 | 0.849793 | 0.856677 |
| Bistro | `O-T2X-R` | 2.045134 | 33.9554 | 0.970465 | 0.961248 |
| Bistro | `O-ET2X` | 1.997577 | 33.2724 | 0.967955 | 0.973348 |
| Bistro | `O-ET2X-R` | 1.649645 | 35.3612 | 0.979603 | 0.984055 |
| Bistro | `A-1X` | 1.574130 | 35.7700 | 0.981413 | 1.006525 |
| Bistro | `A-T2X` | 8.014116 | 26.7233 | 0.850078 | 0.857915 |
| Bistro | `A-T2X-R` | 2.031125 | 34.0213 | 0.970866 | 0.962670 |
| Bistro | `A-ET2X` | 1.995297 | 33.2805 | 0.968023 | 0.974274 |
| Bistro | `A-ET2X-R` | 1.645479 | 35.3856 | 0.979708 | 0.985026 |
| Minecraft | `O-1X` | 1.330643 | 33.6656 | 0.975452 | 1.007587 |
| Minecraft | `O-T2X` | 3.989191 | 28.3147 | 0.896789 | 0.832673 |
| Minecraft | `O-T2X-R` | 1.577457 | 33.3814 | 0.968138 | 0.944279 |
| Minecraft | `O-ET2X` | 1.596263 | 32.1820 | 0.962318 | 0.958065 |
| Minecraft | `O-ET2X-R` | 1.332599 | 33.8800 | 0.974865 | 0.970783 |
| Minecraft | `A-1X` | 1.330992 | 33.6652 | 0.975455 | 1.007793 |
| Minecraft | `A-T2X` | 3.986136 | 28.3218 | 0.896916 | 0.832974 |
| Minecraft | `A-T2X-R` | 1.573949 | 33.3919 | 0.968277 | 0.944607 |
| Minecraft | `A-ET2X` | 1.596576 | 32.1814 | 0.962322 | 0.958251 |
| Minecraft | `A-ET2X-R` | 1.332839 | 33.8798 | 0.974874 | 0.970977 |

중앙 이동 150–329에서 `O-ET2X-R`의 reference MAE는 `O-T2X-R`보다 Bistro
31.545%, Minecraft 29.786% 낮았다. Adaptive 대응 pair도 각각 31.354%, 29.722%
낮았다. 같은 구간의 adjacent-frame MAE 변화는 Original +0.124%, Adaptive
+0.106%(Bistro), Original +0.391%, Adaptive +0.388%(Minecraft)로 작았다.

이는 ET2X-R이 단순히 모든 history를 버려 1X로 돌아간 것만으로 설명되지는 않는다는
보조 근거다. 그러나 adjacent difference에는 실제 camera motion이 포함되므로 temporal
supersampling 보존의 절대 증명으로 사용하지 않는다.

## 6. Formal CGVQM-2 결과

### Central motion 150–329

| Scene | Spatial | 1X | T2X | T2X-R | ET2X | ET2X-R |
|---|---|---:|---:|---:|---:|---:|
| Bistro | Original | 96.9816 | 49.7428 | 94.1330 | 94.7890 | 96.6886 |
| Bistro | Adaptive | 97.0121 | 49.7909 | 94.2116 | 94.8065 | 96.7201 |
| Minecraft | Original | 97.5651 | 76.1054 | 95.9865 | 96.2020 | 97.5158 |
| Minecraft | Adaptive | 97.5804 | 76.1199 | 96.0102 | 96.2109 | 97.5312 |

- Reprojection 없는 full-screen T2X는 moving camera history 오정렬로 두 장면에서 가장
  낮았다.
- Reprojection 없는 ET2X도 완전한 TSCMAA 동작은 아니지만, 비후보 픽셀에 현재 spatial
  AA를 유지해 no-reprojection full-screen history의 피해 범위를 크게 제한했다.
- `O-ET2X-R`은 `O-T2X-R`보다 Bistro +2.5556, Minecraft +1.5293점 높았다.
- `A-ET2X-R`은 `A-T2X-R`보다 Bistro +2.5085, Minecraft +1.5210점 높았다.
- ET2X-R은 각 공간 1X control보다 Bistro 약 0.292~0.293점, Minecraft 약
  0.049점 낮아 central motion에서는 1X에 매우 가까웠다.

### Motion→still transition 410–439

| Scene | Spatial | 1X | T2X | T2X-R | ET2X | ET2X-R |
|---|---|---:|---:|---:|---:|---:|
| Bistro | Original | 94.4109 | 95.1455 | 95.1268 | 93.8633 | 94.5610 |
| Bistro | Adaptive | 94.4756 | 95.2692 | 95.2520 | 93.9263 | 94.6225 |
| Minecraft | Original | 93.4093 | 94.6848 | 94.6468 | 93.2418 | 93.7390 |
| Minecraft | Adaptive | 93.4301 | 94.7236 | 94.6858 | 93.2601 | 93.7549 |

- 전환 구간에서는 Standard T2X/T2X-R이 가장 높았다.
- `O-ET2X-R`은 `O-T2X-R`보다 Bistro -0.5658, Minecraft -0.9078점 낮았다.
- `A-ET2X-R`은 `A-T2X-R`보다 Bistro -0.6295, Minecraft -0.9309점 낮았다.
- 즉 central motion의 우위가 motion→still까지 일반화되지 않는다. Edge-selective가
  history를 제한해 움직임 중 오정렬은 줄이지만, 정지 직후 Standard의 넓은 temporal
  accumulation 이득은 충분히 유지하지 못하는 trade-off로 해석한다.

## 7. 종합 판정

1. **Integrated source 구조 검증:** SMAA 1st-pass edge를 직접 이용하는 core에서 final
   8-case 성능·품질·CGVQM 행렬을 모두 완료했다. 이전 이중 edge detection 구조를 최종
   core 결과로 사용하지 않는다.
2. **Camera motion 품질:** ET2X-R은 두 장면의 central motion에서 Standard T2X-R보다
   spatial reference와 CGVQM 모두 개선됐다. 움직임 중 넓은 history 오정렬과 blur를
   제한하는 방향은 지지된다.
3. **Temporal retention:** ET2X-R은 중앙 이동에서 1X에 매우 가까우면서 Standard와
   유사한 화면 공간 시간 변화량을 보였다. 따라서 단순 1X 복귀만으로 단정할 수는 없지만,
   temporal supersampling을 1X보다 확실히 개선했다고 주장할 증거도 아직 부족하다.
4. **전환 trade-off:** motion→still에서는 Standard가 더 높았다. 현재 candidate
   coverage/history policy가 정지 직후 accumulation 기회를 과도하게 제한할 수 있다.
5. **Adaptive 통합:** Adaptive는 품질을 거의 유지하면서 모든 대응 mode의 SMAA pass
   시간을 줄였다. 따라서 공간·시간 기법 결합 자체는 기능적으로 성립한다.
6. **성능 목표 미달:** Integrated ET2X는 이중 full-screen detection을 제거했지만
   Standard보다 SMAA와 WholeFrame 모두 느리다. 현재 결과를 TSCMAA식 성능 최적화
   성공으로 표현하면 안 된다.

## 8. 후속 작업

1. Integrated ET2X의 candidate compact, indirect args/dispatch, selective resolve와
   history feedback 비용을 pass별로 다시 분석한다.
2. 현재 후보 수에서 indirect path가 손익분기점을 넘지 못하는 원인을 확인하고,
   tile/stencil 또는 직접 masked resolve 같은 대체 실행 구조를 독립 ablation한다.
3. Motion→still에서 history accumulation을 유지하도록 candidate persistence 또는
   history confidence를 별도 축으로 설계하되, central-motion 품질 회귀와 고스팅을 함께
   측정한다.
4. 기존 current-edge 3×3, FilteredQuarter, ARM Dual Filter 결과는 final core와 섞지
   않고 필요할 때 thin-geometry coverage ablation으로만 사용한다.
5. Rigid object-motion engineering gate는 별도 결과로 유지한다. 실제 textured rigid
   object, skinned/deforming geometry와 previous-depth disocclusion rejection을 지원한
   뒤에만 최종 8-case `-R` 의미 확장을 검토한다.
6. 결과 문구는 “Intel TSCMAA 공개 문서에 부합하는 SMAA adaptation”으로 유지하며,
   유실된 공식 sample source와 동일한 포팅이라고 표현하지 않는다.

## 9. 산출물

### Raw performance/capture

- Bistro performance: `D:\SMAA-Research-Data\AutoBench\20260828_071530`
- Minecraft performance: `D:\SMAA-Research-Data\AutoBench\20260828_072219`
- Bistro 10-mode capture: `D:\SMAA-Research-Data\AutoBench\20260828_072817`
- Minecraft 10-mode capture: `D:\SMAA-Research-Data\AutoBench\20260828_073715`
- Bistro SS-Reference: `D:\SMAA-Research-Data\AutoBench\20260827_014143`
- Minecraft SS-Reference: `D:\SMAA-Research-Data\AutoBench\20260827_014612`

### Analysis

- Combined performance:
  `D:\SMAA-Research-Data\AutoBench\20260828_FinalIntegratedEightCase\CombinedPerformance`
- Wide 10-mode spatial/temporal diagnostics:
  `D:\SMAA-Research-Data\AutoBench\20260828_FinalIntegratedEightCase\WideQuality`
- Formal CGVQM raw results:
  `D:\SMAA-Research-Data\AutoBench\20260828_FinalIntegratedEightCase\CGVQM`
- Formal CGVQM aggregate:
  `D:\SMAA-Research-Data\AutoBench\20260828_FinalIntegratedEightCase\CGVQMAnalysis`
