# SMAA Filtered 1/4 Candidate Expansion Engineering Smoke

> **2026-08-27 구현 감사 정정:** 최초 구현은 bilinear 복원값만 threshold해 raw
> current-edge candidate 일부를 지웠다. 따라서 아래 2026-08-20 후보 배수·품질·성능
> 수치는 수정 전 구현의 역사적 engineering 기록이며, `candidate expansion`의 정식
> 근거로 사용할 수 없다. 현재 구현은 `rawCandidate OR reconstructed >= 0.25`로
> 고쳤고, 수정 후 결과는 9절에 별도로 기록한다.

## 1. 목적과 분류

교수님이 제안한 downsampling-upsampling 방식이 정확한 3×3 dilation보다 적은 후보 증가와
낮은 GPU 비용으로 현재 프레임 edge 주변의 temporal coverage를 넓힐 수 있는지 확인했다.
이 구현은 Intel 원본 TSCMAA의 확인된 구성요소가 아니라 별도 직교 ablation이며, 최종
8-case mode에는 포함하지 않는다.

이번 단계는 정식 품질·성능 결론이 아닌 engineering gate다. 먼저 축소 smoke에서 3×3보다
낮은 mask 비용과 후보 증가율을 동시에 확인하고, 두 조건이 유망할 때만 60-frame 실제 장면
품질·CGVQM 및 3회 반복 성능 측정으로 확대하도록 정했다.

## 2. 구현 정의

`CandidateExpansion::FilteredQuarter`는 다음 두 compute pass로 구성된다.

1. full-resolution raw candidate mask를 `ceil(width/4) × ceil(height/4)` R8_UNORM texture로
   축소한다. 각 texel은 대응하는 유효 4×4 source block의 정확한 평균이다.
2. quarter mask를 half-pixel 좌표 규칙의 bilinear interpolation으로 full resolution에
   복원한다. raw candidate 또는 복원값이 `0.25` 이상인 픽셀을 candidate list에
   compact한다.

```text
finalCandidate = rawCandidate OR reconstructed >= 0.25
```

이 합집합은 `expansion`이 원래 current edge를 지우지 않아야 한다는 불변조건이다.

Nearest-neighbor는 사용하지 않는다. 이전 프레임 edge mask와 object motion vector도
추가하지 않았다. 비교 mode는 Candidate-Jitter와 document profile 각각의 `None`, `3×3`,
`FilteredQuarter` 총 6개다.

## 3. 추가한 자동 검증 경로

- `-smaaFilteredQuarterAblationCapture`: 6-mode 동일 camera path PNG capture
- `-smaaFilteredQuarterPerformanceSmoke` / `Benchmark`: raw extraction, 3×3,
  quarter downsample, bilinear upsample/compact, indirect resolve와 SMAA total을 분리
- temporal lifecycle test: 두 filtered mode와 기존 두 3×3 mode의 reset/seed 검증
- `Tools/SMAA/analyze_filtered_quarter_quality.py`: sequence, 3×3 CPU reference,
  filtered CPU mirror, 후보 배수, 반복 픽셀 차이와 6-way sheet 검증
- `Tools/SMAA/analyze_filtered_quarter_performance.py`: mode/metric/sample/run 수와 내부 PASS를
  검증하고 profile별 비용을 비교

## 4. 최초 기능 검증 결과 — 수정 전, 정식 근거 사용 금지

- Release x64 build: 성공
- runtime HLSL compilation 및 6-mode 순회: 성공
- lifecycle: reset 44, completed frame 121, seed 23, resolve 98, reprojection 56,
  failure 0으로 PASS
- 모든 실행 전후 잔류 `CMAA2.exe`: 0개
- 3×3 GPU mask와 CPU max-filter: Bistro/Minecraft 모든 smoke frame에서 0 pixel mismatch
- Filtered GPU mask와 CPU float32 mirror의 최대 mismatch:
  - Bistro: 0.015364%
  - Minecraft: 0.012240%

당시 분석기는 GPU와 같은 reconstruction-only CPU mirror를 사용했기 때문에 GPU/CPU
일치만 확인했을 뿐, `raw ⊆ expanded` 불변조건을 검사하지 않았다. 후속 감사에서 San
Miguel mask 60/60 frame 모두 raw 후보 유실을 재현했으며 frame당 평균 23,395.683개,
최대 58,171개가 지워졌다. 따라서 이 절의 PASS는 구현 의도에 대한 correctness PASS가
아니다.

## 5. 최초 후보 확장 smoke — 수정 전 수치

장면은 저대비 Bistro와 고대비 Minecraft, 경로는 `yaw-fast-360`, profile frame 60~62를
사용했다. 아래 값은 3-frame engineering subset 평균이다.

| 장면 | Profile | 3×3 후보 배수 | Filtered 후보 배수 |
|---|---|---:|---:|
| Bistro | Document | 2.833× | 1.570× |
| Bistro | Candidate-Jitter | 2.836× | 1.575× |
| Minecraft | Document | 3.121× | 1.567× |
| Minecraft | Candidate-Jitter | 3.124× | 1.566× |

이 평균 배수만으로는 모든 raw 후보가 보존됐음을 알 수 없다. 실제로 frame별 공간 위치를
대조하면 일부 raw 후보가 지워지고 다른 주변 후보가 추가된 결과였다. 따라서 이 표를
`확장 범위`나 post-fix 구현의 후보 배수로 인용하지 않는다.

## 6. 최초 성능 smoke — 수정 전 수치

RTX 3060 Ti, 1920×1017, Release x64, DirectX 11, SMAA Ultra, VSync Off에서
60-frame warm-up + 120-frame measurement 1회로 측정했다. candidate readback이 켜진
engineering smoke이므로 정식 성능 수치로 사용하지 않는다.

| Profile | 3×3 후보 배수 | Filtered 후보 배수 | 3×3 mask | Filtered mask | 3×3 SMAA 변화 | Filtered SMAA 변화 | Filtered vs 3×3 SMAA |
|---|---:|---:|---:|---:|---:|---:|---:|
| Document | 3.305× | 1.072× | 0.045525 ms | 0.063053 ms | +20.159% | +24.337% | +3.477% |
| Candidate-Jitter | 3.304× | 1.073× | 0.045244 ms | 0.062806 ms | +18.786% | +23.214% | +3.728% |

Filtered mask 비용은 downsample과 upsample/compact의 합이다. 다만 이 수치는 raw union이
없는 다른 알고리즘을 측정했으므로 수정된 candidate expansion의 비용으로 사용할 수 없다.

## 7. 최초 판단의 정정

최초 구현은 expansion 불변조건을 만족하지 않았으므로 그 결과만으로 수정된
FilteredQuarter의 채택 여부를 결정할 수 없다. 수정 구현을 후보로 계속 비교하려면 품질·
성능 결과를 다시 생성해야 한다. 이전 캡처에서 None·3×3 등 영향을 받지 않은 mode는
보존할 수 있지만, FilteredQuarter가 포함된 pair·표·결론은 재사용하지 않는다.

## 8. 산출물

- Bistro final smoke: `AutoBench/20260820_050923`
- Bistro independent repeat: `AutoBench/20260820_050934`
- Bistro candidate mask: `AutoBench/20260820_045437`
- Minecraft final smoke: `AutoBench/20260820_050759`
- Minecraft candidate mask: `AutoBench/20260820_050806`
- Performance smoke: `AutoBench/20260820_045705`
- Lifecycle validation: `AutoBench/20260820_050353`

대용량 AutoBench 산출물은 Git에 포함하지 않고 `D:\SMAA-Research-Data\AutoBench`에
보존한다.

## 9. 2026-08-27 감사 수정 및 재검증

수정 사항:

- GPU upsample pass에 full-resolution raw mask SRV를 다시 연결
- `rawCandidate OR reconstructed >= 0.25` 적용
- Python CPU mirror에도 같은 union 적용
- FilteredQuarter 및 ARM 비교 분석기에 raw 후보 유실 hard-fail 추가

Bistro `yaw-fast-360` frame 60~62의 수정 후 3-frame engineering smoke에서 두 profile
모두 raw 후보 유실 최대값이 0이었다. GPU/CPU 최대 mask mismatch 비율은 0.012240%로
기존 허용 한계 0.05% 안이었고, 후보 배수는 Document 1.928×, Candidate-Jitter 1.931×였다.
16-frame 축소 performance smoke도 모든 timing 표본과 내부 validation을 통과했다. 이
짧은 실행은 correctness와 측정 경로 회귀만 확인하며, 품질·성능 우위를 뜻하지 않는다.

- post-fix final capture: `D:/SMAA-Research-Data/AutoBench/20260827_071852`
- post-fix candidate mask: `D:/SMAA-Research-Data/AutoBench/20260827_071945`
- post-fix performance smoke: `D:/SMAA-Research-Data/AutoBench/20260827_072150`
