# SMAA Filtered 1/4 Candidate Expansion Engineering Smoke

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
   복원한다. 복원값이 `0.25` 이상인 픽셀만 candidate list에 compact한다.

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

## 4. 기능 검증 결과

- Release x64 build: 성공
- runtime HLSL compilation 및 6-mode 순회: 성공
- lifecycle: reset 44, completed frame 121, seed 23, resolve 98, reprojection 56,
  failure 0으로 PASS
- 모든 실행 전후 잔류 `CMAA2.exe`: 0개
- 3×3 GPU mask와 CPU max-filter: Bistro/Minecraft 모든 smoke frame에서 0 pixel mismatch
- Filtered GPU mask와 CPU float32 mirror의 최대 mismatch:
  - Bistro: 0.015364%
  - Minecraft: 0.012240%

Filtered mismatch는 R8 양자화 뒤 0.25 임계값 부근의 GPU 부동소수점 분류 차이이므로
bit-identical이라고 표현하지 않는다. 60-frame warm-up 독립 Bistro 반복에서는 18개 PNG 중
7개의 파일 hash가 달랐지만 실제 차이는 총 10 pixel, 최대 channel delta 1이었다.

## 5. 후보 확장 smoke

장면은 저대비 Bistro와 고대비 Minecraft, 경로는 `yaw-fast-360`, profile frame 60~62를
사용했다. 아래 값은 3-frame engineering subset 평균이다.

| 장면 | Profile | 3×3 후보 배수 | Filtered 후보 배수 |
|---|---|---:|---:|
| Bistro | Document | 2.833× | 1.570× |
| Bistro | Candidate-Jitter | 2.836× | 1.575× |
| Minecraft | Document | 3.121× | 1.567× |
| Minecraft | Candidate-Jitter | 3.124× | 1.566× |

Filtered 방식은 두 실제 장면 pose에서 3×3보다 후보 증가를 크게 억제하면서 raw mask보다는
넓은 coverage를 만들었다. 다만 후보가 적다는 사실만으로 구조 복구나 품질 우위를 뜻하지
않는다.

## 6. 성능 smoke

RTX 3060 Ti, 1920×1017, Release x64, DirectX 11, SMAA Ultra, VSync Off에서
60-frame warm-up + 120-frame measurement 1회로 측정했다. candidate readback이 켜진
engineering smoke이므로 정식 성능 수치로 사용하지 않는다.

| Profile | 3×3 후보 배수 | Filtered 후보 배수 | 3×3 mask | Filtered mask | 3×3 SMAA 변화 | Filtered SMAA 변화 | Filtered vs 3×3 SMAA |
|---|---:|---:|---:|---:|---:|---:|---:|
| Document | 3.305× | 1.072× | 0.045525 ms | 0.063053 ms | +20.159% | +24.337% | +3.477% |
| Candidate-Jitter | 3.304× | 1.073× | 0.045244 ms | 0.062806 ms | +18.786% | +23.214% | +3.728% |

Filtered mask 비용은 downsample과 upsample/compact의 합이다. 후보 수는 3×3보다 훨씬
적었지만 두 pass 합산 mask 비용은 3×3보다 약 38.5~38.8% 높았고, SMAA total도 3×3보다
약 3.5~3.7% 높았다.

## 7. 판단

이번 구현은 “3×3보다 낮은 후보 증가율” 조건은 만족했지만 “3×3보다 낮은 mask 생성
비용” 조건은 만족하지 못했다. 따라서 현재 구현을 성능 개선안으로 채택하지 않으며,
60-frame 정식 품질·CGVQM 및 600-frame×3회 성능 측정으로 확대하지 않는다.

이 결정은 filtered 확장 개념 전체가 무효라는 뜻이 아니다. 현재 full-resolution bilinear
upsample/compact pass가 병목이라는 뜻이며, 향후 재검토하려면 두 pass fusion, group-shared
tile 처리, lower-resolution candidate resolve처럼 구조가 실제로 달라져야 한다. 단순히
동일 구현의 측정 길이만 늘리는 것은 우선순위가 낮다.

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
