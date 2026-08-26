# ARM Dual Filtering 기반 current-edge 후보 확장 engineering 결과

## 1. 목적과 연구 분류

교수님이 제안한 downsample-upsample 기반 edge 영역 확장을 검증하기 위해 ARM
SIGGRAPH 2015 *Bandwidth-Efficient Rendering*의 Dual Filtering kernel을 current-frame
candidate mask에 적용했다. 이는 bloom용 ARM filter를 SMAA/TSCMAA 후보 선택에 맞춘
연구 adaptation이며, ARM 또는 Intel의 공식 SMAA 구현이라고 표현하지 않는다.

최종 8-case mode는 변경하지 않았다. Candidate-Jitter와 document profile 각각에서
`None`, 정확한 `3×3`, 기존 `FilteredQuarter`, 새 `ArmDualFilter`만 비교하는 직교
ablation이다.

## 2. 구현

GPU 경로는 다음 네 filter pass로 구성된다.

1. full raw mask → half R8: ARM 5-tap downsample
2. half R8 → quarter R8: ARM 5-tap downsample
3. quarter R8 → half R8: ARM 8-tap upsample
4. half R8 → full candidate/list: ARM 8-tap upsample와 compact

각 level은 홀수 해상도에서 ceil division을 사용하고 linear-clamp sampling, R8_UNORM
intermediate와 `0.25` threshold를 사용한다. kernel의 가중치와 상대 offset은 ARM
공개 notes를 따르지만, 두-level pyramid, half-pixel 규칙, R8 형식과 threshold는 이
연구의 명시적 가정이다.

첫 reconstruction-only smoke에서는 선택된 raw 후보의 약 43~44%만 남아 expansion이
아니라 erosion에 가까운 결과가 나왔다. 따라서 최종 mask는 다음처럼 수정했다.

```text
finalCandidate = rawCandidate OR dualFilterReconstruction >= 0.25
```

이 규칙으로 원본 current-edge 후보는 보존하고 filter는 주변 coverage만 추가한다.
이 union 역시 binary candidate mask를 위한 연구 adaptation이다.

## 3. 자동 검증 경로

- `-smaaArmDualFilterAblationCapture`: 두 profile × 네 expansion의 8-mode 동일 경로 capture
- `-smaaArmDualFilterPerformanceSmoke` / `Benchmark`: 네 ARM pass와 SMAA total 분리
- temporal lifecycle test: 두 ARM mode의 seed, ping-pong과 reset 포함
- `Tools/SMAA/analyze_arm_dual_filter_quality.py`: 3×3 exact CPU 검증, ARM
  float32/linear-clamp/R8 CPU mirror, raw 보존, reference/temporal 지표와 비교 sheet
- `Tools/SMAA/analyze_arm_dual_filter_performance.py`: timing 표본·pass·counter·내부 PASS 검증

Release x64 build와 runtime HLSL compile가 성공했다. Lifecycle은 reset 48회, completed
frame 130개, seed 25개, resolve 105개, reprojection 62개, failure 0으로 PASS했다.
모든 CMAA2 실행 전후 잔류 프로세스는 0개였다.

## 4. Mask correctness와 후보 coverage

저대비 Bistro와 고대비 Minecraft에서 `yaw-fast-360` profile frame 60~119를 mode당
60 frame 캡처했다.

| 장면 | Profile | 3×3 후보 배수 | Filtered 후보 배수 | ARM 후보 배수 |
|---|---|---:|---:|---:|
| Bistro | Document | 2.922× | 1.502× | 1.693× |
| Bistro | Candidate-Jitter | 2.924× | 1.502× | 1.694× |
| Minecraft | Document | 3.216× | 1.223× | 1.494× |
| Minecraft | Candidate-Jitter | 3.218× | 1.221× | 1.493× |
| San Miguel | Document | 3.009× | 1.270× | 1.659× |
| San Miguel | Candidate-Jitter | 3.038× | 1.261× | 1.660× |

ARM은 세 장면에서 raw mask보다 후보를 늘렸고, 3×3보다는 제한된 범위로 확장했다.
독립 mode capture에서 raw 후보 유실은 Minecraft 0 pixel, Bistro 최대 0 pixel이었다.
표의 후보 배수는 프레임별 배수를 평균한 값이다. 성능 절의 San Miguel 후보 배수는
별도 readback 실행에서 평균 candidate 수를 평균 None candidate 수로 나눈 값이므로,
프레임별 raw 후보 수 변화가 큰 장면에서는 두 집계값이 다를 수 있다.

ARM GPU mask와 CPU mirror의 최대 mismatch는 Bistro 0.109237%, Minecraft
0.080916%, San Miguel 0.066730%였다. `0.25±0.003` threshold 경계 밖 mismatch는
각각 0.007426%, 0.000563%, 0.001332%였다. 따라서 bit-identical이라고 표현하지
않으며 R8/linear filtering과 threshold 경계 오차를 수치로 보존한다.

## 5. 60-frame spatial-reference quality gate

같은 pose의 2× linear resolution, frame당 3×3 subpixel grid, 8×MSAA supersample
spatial-reference proxy와 비교했다. 아래 값은 full-frame RGB MAE 평균이며 낮을수록
reference에 가깝다.

| 장면 | Profile | None | 3×3 | Filtered | ARM |
|---|---|---:|---:|---:|---:|
| Bistro | Document | 1.495521 | 1.523835 | 1.468974 | 1.500302 |
| Bistro | Candidate-Jitter | 2.229041 | 2.079835 | 2.229342 | 2.171713 |
| Minecraft | Document | 0.589198 | 0.744693 | 0.571775 | 0.618599 |
| Minecraft | Candidate-Jitter | 1.078144 | 1.095496 | 1.112543 | 1.070405 |
| San Miguel | Document | 2.391437 | 2.140196 | 2.138561 | 2.138326 |
| San Miguel | Candidate-Jitter | 3.074070 | 2.702365 | 2.779179 | 2.742413 |

해석은 다음과 같다.

- Bistro Candidate-Jitter에서는 ARM이 None보다 MAE를 약 2.57% 낮췄지만 3×3의 약
  6.69% 개선보다 작았다.
- Minecraft Candidate-Jitter에서는 ARM 개선이 약 0.72%로 작았고 3×3/Filtered는
  오히려 악화됐다.
- Document profile에서 ARM은 Bistro 약 0.32%, Minecraft 약 4.99% 악화됐다.
- San Miguel 전체 화면에서는 ARM이 None 대비 reference MAE를 Document 10.58%,
  Candidate-Jitter 10.79% 낮췄다.
- 실제 의자·테이블 다리와 식생 가지가 보이는 frame 0~9 screen-space ROI에서도 ARM은
  각각 9.44%, 13.10% 낮췄다. 같은 ROI에서 3×3은 9.62%, 14.46% 낮춰 ARM보다 약간
  우수했고, Filtered도 Document에서 ARM과 사실상 같은 수준이었다.
- ARM의 adjacent-frame RGB MAE는 None보다 작아진 경우가 있으나 장면 motion을 포함한
  대용값이므로 ghosting 감소나 temporal supersampling 복구로 단정하지 않는다.

즉, Bistro/Minecraft만 보면 ARM의 품질 개선은 작거나 일관되지 않았지만, 얇은 실제
geometry가 많은 San Miguel에서는 current-edge expansion 계열 전체의 의미 있는 reference
개선이 확인됐다. 이는 후보 확장 가설을 지지하지만 ARM kernel 자체의 우위를 뜻하지 않는다.

## 6. 성능 gate

RTX 3060 Ti, 1920×1017, Release x64, DirectX 11, SMAA Ultra, VSync Off에서 60-frame
warm-up 뒤 120 frame을 1회 측정했다. timing 실행은 candidate readback Off이고 후보
배수는 별도 readback-On characterization에서 결합했다.

| Profile | 3×3 mask | Filtered mask | ARM mask | 3×3 SMAA 변화 | Filtered SMAA 변화 | ARM SMAA 변화 |
|---|---:|---:|---:|---:|---:|---:|
| Document | 0.045133 ms | 0.061756 ms | 0.132659 ms | +19.237% | +21.991% | +47.561% |
| Candidate-Jitter | 0.045065 ms | 0.062072 ms | 0.133205 ms | +19.118% | +23.580% | +49.316% |

ARM 4-pass mask는 3×3보다 약 2.94~2.96배, Filtered보다 약 2.15배 비쌌다. 이번 값은
1회 engineering 측정이므로 통계적 유의성을 뜻하지 않지만, formal 600×3 측정을
정당화할 정도의 성능 가능성은 보이지 않았다.

San Miguel `yaw-fast-360` frame 60~119에서도 readback-Off timing과 별도 readback-On
후보 특성화를 1회 수행했다.

| Profile | 3×3 mask | Filtered mask | ARM mask | 3×3 SMAA 변화 | Filtered SMAA 변화 | ARM SMAA 변화 |
|---|---:|---:|---:|---:|---:|---:|
| Document | 0.048333 ms | 0.064308 ms | 0.132779 ms | +17.162% | +20.989% | +40.103% |
| Candidate-Jitter | 0.048401 ms | 0.064443 ms | 0.133120 ms | +14.348% | +17.560% | +37.751% |

San Miguel에서도 ARM mask는 3×3보다 약 2.75배, Filtered보다 약 2.06배 비쌌다.
ARM 후보 수는 None의 약 2.07배였으며 의자 ROI coverage는 약 56%까지 증가했다.
WholeFrame GPU 평균도 ARM이 None보다 Document 3.71%, Candidate-Jitter 4.82% 높았다.
모두 1회 engineering 값이므로 통계적 유의성은 주장하지 않는다.

## 7. 결론

1. ARM Dual Filtering kernel의 GPU adaptation과 자동 검증 경로는 정상 동작한다.
2. raw union 뒤 current-edge candidate coverage는 약 1.49~1.69배로 확장된다.
3. San Miguel의 얇은 실제 geometry에서는 후보 확장 계열이 reference 오차를 약
   9~14% 줄여 current-edge expansion 가설 자체는 지지됐다.
4. 그러나 ARM은 같은 ROI에서 3×3보다 품질이 낫지 않았고 mask 비용은 약 2.75배였다.
5. 따라서 현재 full→half→quarter→half→full ARM 구현은 최종 개선안으로 채택하지 않고,
   최적화 전에는 600×3 성능 및 CGVQM formal 확대를 진행하지 않는다.
6. ARM 구현과 장면 의존 결과는 ablation 근거로 보존한다. 후속으로 재검토한다면 pass fusion,
   group-shared tile, 더 얕은 pyramid 또는 lower-resolution resolve처럼 구조적 비용을
   줄이는 변경이 먼저 필요하다.
7. 후보 확장 연구의 다음 비교 우선순위는 ARM이 아니라 3×3과 FilteredQuarter의
   San Miguel ghosting·temporal retention·반복 성능 trade-off다.

## 8. 산출물

### Bistro

- final capture: `D:/SMAA-Research-Data/AutoBench/20260827_041754`
- candidate mask: `D:/SMAA-Research-Data/AutoBench/20260827_041914`
- analysis: `D:/SMAA-Research-Data/AutoBench/20260827_041754/Analysis-ARM-Dual-Quality`

### Minecraft

- final capture: `D:/SMAA-Research-Data/AutoBench/20260827_041950`
- candidate mask: `D:/SMAA-Research-Data/AutoBench/20260827_042042`
- analysis: `D:/SMAA-Research-Data/AutoBench/20260827_041950/Analysis-ARM-Dual-Quality`

### San Miguel 얇은 실제 geometry

- final capture: `D:/SMAA-Research-Data/AutoBench/20260827_051016`
- candidate mask: `D:/SMAA-Research-Data/AutoBench/20260827_051220`
- supersample reference: `D:/SMAA-Research-Data/AutoBench/20260827_051339/SS_Reference`
- full-frame analysis: `D:/SMAA-Research-Data/AutoBench/20260827_051016/Analysis-ARM-Dual-Quality`
- thin-chair ROI analysis: `D:/SMAA-Research-Data/AutoBench/20260827_051016/Analysis-ARM-Dual-SanMiguel-Thin-ROI`
- readback-Off performance: `D:/SMAA-Research-Data/AutoBench/20260827_055626`
- readback-On characterization: `D:/SMAA-Research-Data/AutoBench/20260827_055702`

### 성능 및 lifecycle

- readback-On characterization: `D:/SMAA-Research-Data/AutoBench/20260827_035402`
- readback-Off 120-frame timing: `D:/SMAA-Research-Data/AutoBench/20260827_041420`
- timing analysis: `D:/SMAA-Research-Data/AutoBench/20260827_041420/Analysis-ARM-Dual-Performance`
- lifecycle validation: `D:/SMAA-Research-Data/AutoBench/20260827_040829`

대용량 PNG와 AutoBench 결과는 Git에 포함하지 않는다.
