# SMAA current-edge 3×3 dilation ablation 결과

## 1. 목적과 연구 범위

교수님이 제안한 현재 프레임 edge 영역 확장 가설을 가장 작은 커널부터 검증했다.
얇은 구조의 중심 픽셀이 현재 edge 후보에 포함되지 않더라도 주변 edge가 검출되면
temporal history 적용 대상으로 복구할 수 있는지 확인하는 실험이다.

이 구현은 Intel TSCMAA 원본 source의 재현이 아니며, 공개 문서에 맞춘 기존
TSCMAA-inspired SMAA adaptation에 추가한 **직교 ablation**이다. 이전 프레임 edge mask,
object motion vector, depth disocclusion rejection은 사용하지 않는다. 최종 8개 연구 mode도
변경하지 않았다.

비교한 두 쌍은 다음과 같다.

| Profile | 확장 없음 | 현재 edge 3×3 확장 |
|---|---|---|
| Candidate-Jitter | `ABL-Candidate-Jitter-R` | `ABL-Candidate-Jitter-Dilate3x3-R` |
| Document | `O-ET2X-R-Document` | `ABL-Document-Dilate3x3-R` |

각 쌍은 current-edge 확장 여부만 다르다. Candidate-Jitter는 Standard T2X의 projection
jitter를 유지하고, Document는 deliberate projection jitter가 없는 공개 문서 기반 profile이다.

## 2. 구현

기존 `IntelFamilyNonDominant` raw candidate mask를 먼저 생성한 뒤 별도의 compute pass에서
정확한 3×3 max-filter를 수행한다. 확장된 mask를 compact candidate list와 indirect dispatch에
연결하고 최종 resolve는 기존 history sampling, clipping, history weight 설정을 그대로 사용한다.

GPU timestamp에는 다음을 분리해 기록했다.

- raw candidate extraction
- 3×3 dilation
- indirect dispatch argument 생성
- candidate temporal resolve
- SMAA 전체와 WholeFrame

캡처 시작 시 shader/resource 준비 프레임 수에 따라 첫 mode의 temporal phase가 달라질 수 있던
문제도 수정했다. 준비 프레임이 끝난 다음 history를 다시 초기화하여 모든 mode가 같은 warm-up
phase에서 시작하도록 했고, 독립 반복 캡처의 PNG hash가 모두 일치하는지 확인했다.

## 3. 검증 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- API/빌드: DirectX 11, Release x64
- 해상도: 1920×1017
- preset: SMAA Ultra
- 장면: 저대비 Bistro, 고대비 Minecraft
- camera profile: `yaw-fast-360`
- 품질: mode별 60 warm-up + frame 60~119의 60 PNG
- reference: 같은 pose의 2× linear, 3×3 subpixel grid, 8×MSAA spatial proxy
- CGVQM: Intel 공식 repository commit `8302ff45`, model 2, CUDA, 60 frame
- 성능: hidden-window engineering, 120 warm-up + 600 frame × 3회, candidate readback Off

Supersample reference는 현재 frame의 spatial-reference proxy이지 temporal ground truth가 아니다.
CGVQM도 full-reference 보조 지표이며 절대 ghosting 판별값으로 표현하지 않는다.

## 4. 자동 검증 결과

- GPU dilation mask와 CPU의 정확한 3×3 max-filter 비교: 양 장면·두 profile 모두 mismatch 0 pixel
- 독립 반복 capture: Bistro 4 mode × 60 frame, Minecraft 4 mode × 60 frame 모두 SHA-256 mismatch 0
- CGVQM 입력 FFV1 왕복: 8개 test/reference 조합 모두 pixel mismatch 0
- 성능 CSV 내부 validation: PASS
- 캡처와 측정 종료 후 잔류 CMAA2 process: 0

따라서 3×3 확장 자체와 캡처·계측 경로는 engineering 수준에서 검증됐다.

## 5. 후보 coverage와 temporal 적용 범위

| 장면 | Profile | 전체 화면 후보 배수 | 대표 ROI 구조 recall 증가 | History 영향 증가 |
|---|---|---:|---:|---:|
| Bistro | Candidate-Jitter | 2.924× | +43.069~+47.141%p | +78.554~+90.401% |
| Bistro | Document | 2.922× | +43.440~+47.325%p | +76.915~+82.095% |
| Minecraft | Candidate-Jitter | 3.219× | +17.327~+52.271%p | +87.872~+129.737% |
| Minecraft | Document | 3.217× | +17.266~+51.995%p | +75.936~+129.906% |

3×3은 검출된 edge 주변의 구조 coverage와 실제 화면에 나타난 history 영향을 확실히 늘렸다.
즉 기존 ET2X가 history sample을 전혀 사용하지 않아서 temporal이 약했던 것은 아니며, 현재
후보 영역을 넓히면 temporal 적용 범위가 실제로 커진다. 다만 후보 수가 약 2.9~3.2배가 되어
TSCMAA의 선택적 처리 장점도 크게 감소한다.

## 6. 실제 장면 ROI 품질

아래 변화율은 각 profile의 확장 없음 대비 3×3 결과다. Reference RGB MAE는 낮을수록 좋다.

| 장면/ROI | Candidate-Jitter MAE 변화 | Document MAE 변화 | 2차 시간 차분 변화 범위 |
|---|---:|---:|---:|
| Bistro bar/bottles | -0.796% | +8.487% | -1.107~-0.674% |
| Bistro windows/chairs | -9.135% | -1.367% | -1.043~-0.517% |
| Minecraft distant city | -2.427% | +24.695% | -1.324~-0.894% |
| Minecraft tree/ledge | -5.651% | -0.045% | -0.392~-0.088% |

Candidate-Jitter에서는 네 ROI 모두 reference MAE가 낮아졌다. 반면 Document에서는
Bistro bar/bottles와 Minecraft distant city가 악화됐으며, 특히 distant city는
+24.695%였다. 시간 차분은 모든 ROI에서 소폭 감소했지만 이는 올바른 안정화뿐 아니라
blur 또는 ghosting의 영향일 수도 있으므로 단독 품질 근거가 아니다.

## 7. CGVQM-2 결과

점수가 높을수록 reference와 가까운 결과다.

| 장면 | Profile | 확장 없음 | 3×3 | 변화 |
|---|---|---:|---:|---:|
| Bistro | Candidate-Jitter | 94.2980 | 95.0715 | +0.7735 |
| Bistro | Document | 96.7907 | 96.8269 | +0.0362 |
| Minecraft | Candidate-Jitter | 97.7468 | 97.9589 | +0.2121 |
| Minecraft | Document | 98.9172 | 98.5178 | -0.3994 |

CGVQM도 Candidate-Jitter의 두 장면 개선을 재현했다. Document는 Bistro에서 사실상 작은
변화였고 Minecraft에서는 하락했다. 따라서 `3×3 dilation이 항상 품질을 높인다`고 결론낼
수 없으며, projection jitter 및 장면 특성과 상호작용하는 profile-dependent 결과다.

## 8. GPU 성능

| Profile | SMAA GPU | WholeFrame GPU | Resolve GPU | Dilation pass |
|---|---:|---:|---:|---:|
| Document | +18.639% | +3.882% | +34.571% | 0.044836 ms |
| Candidate-Jitter | +17.306% | +2.315% | +17.522% | 0.044698 ms |

3×3 확장에는 약 0.045 ms의 별도 pass가 필요했고, 늘어난 candidate를 resolve하는 비용도
증가했다. 결과적으로 SMAA GPU 시간이 약 17~19% 늘었다. 이 측정은 hidden-window
engineering benchmark이므로 논문용 FPS 확정값은 아니지만, 3×3이 현재 구현의 성능
최적화가 아니라 품질·coverage 확장이라는 방향은 반복 3회에서 명확하다.

## 9. 결론

1. 현재 edge 3×3 확장은 의도한 mask를 정확히 만들며 temporal history 적용 범위를 늘린다.
2. Candidate-Jitter profile에서는 두 실제 장면의 CGVQM과 네 ROI reference MAE가 모두
   개선되어 얇은 구조 주변의 temporal coverage 확장 가능성을 보였다.
3. Document profile에서는 효과가 일관되지 않고 Minecraft의 일부 구조와 전체 CGVQM이
   악화됐다. 따라서 기존 document profile의 temporal 손실을 dilation만으로 복구할 수 없다.
4. 후보가 약 3배, SMAA GPU 시간이 약 17~19% 증가하므로 TSCMAA의 연산 절감 목표에는
   불리하다.
5. 5×5와 7×7은 3×3보다 후보와 비용을 더 늘릴 가능성이 크므로 즉시 구현하지 않는다.

다음 우선순위는 교수님이 함께 제안한 **nearest-neighbor가 아닌 filtered 1/4
downsample-upsample 후보 확장**이다. 이는 별도 직교 ablation으로 구현해 3×3보다 낮은
mask 생성 비용과 후보 증가율로 구조 coverage를 확보할 수 있는지 먼저 확인한다. 실제
전선처럼 subpixel 구조가 충분한 라이선스 명확한 textured real scene 검증도 별도로
보강하며, 자체 절차적 장면이나 미완성 Power Plant는 논문 근거로 사용하지 않는다.

## 10. 산출물

### Bistro

- capture root: `D:/SMAA-Research-Data/AutoBench/20260813_222336`
- 독립 반복: `D:/SMAA-Research-Data/AutoBench/20260813_222426`
- 품질 분석: `D:/SMAA-Research-Data/AutoBench/20260813_222336/CurrentEdgeDilationQuality`
- CGVQM: `D:/SMAA-Research-Data/AutoBench/20260813_222336/CurrentEdgeDilationCGVQM`

### Minecraft

- capture root: `D:/SMAA-Research-Data/AutoBench/20260813_222822`
- 독립 반복: `D:/SMAA-Research-Data/AutoBench/20260813_223001`
- 품질 분석: `D:/SMAA-Research-Data/AutoBench/20260813_222822/CurrentEdgeDilationQuality`
- CGVQM: `D:/SMAA-Research-Data/AutoBench/20260813_222822/CurrentEdgeDilationCGVQM`

### 성능

- smoke: `D:/SMAA-Research-Data/AutoBench/20260813_223814`
- 3회 반복 engineering: `D:/SMAA-Research-Data/AutoBench/20260813_224159`
- 분석: `D:/SMAA-Research-Data/AutoBench/20260813_224159/CurrentEdgeDilationPerformance`
