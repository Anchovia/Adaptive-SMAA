# ⑱ 선택적 temporal 기준선 확정

2026-11-02. 브랜치 `baseline/selected-temporal-case18`, 코드 커밋 `1db91d1`, 출발점 `d5d3a40`.

⑱은 ⑰(소스 기반 색 혼합)에서 neighborhood 단계의 depth 쓰기를 끄고 최종 history RGB를 화면 표시에
그대로 쓰는 구성이다. semantic ID는 `ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory`이다.

## 바뀐 것

- `vaSMAAWrapper::ApplyTemporalRoute`와 `IsTemporalRoute`가 ④·⑰·⑱ 설정의 유일한 정의가 됐다.
- 효과가 없던 O1(depth+stencil clear) 코드를 지웠다. 측정 결과는 `Docs/Edge-History-Color-Blend-Optimization`에 그대로 있다.
- `ColorBlendOptimization.inl`의 mode를 ⑰·⑱·④ 세 개로 줄였다. O1, O2 단독, O3 단독을 포함한 10월 19일 행렬은 `d5d3a40`에서 재현할 수 있다.
- HLSL은 바꾸지 않았다. 다른 연구 mode와 8-case의 기본값도 그대로다.

## 출력 검증

새 실행 파일(SHA-256 `43FB26D574FFDBF717C472042CDF2ED1D8A642903159681EFAAC8394DF7BAD16`)로 두 장면을 240프레임씩 독립 프로세스에서 캡처했다.
화면 RGB를 프레임별로 비교한 불일치 수는 다음과 같다.

| 장면 | 비교 | ⑰ | ⑱ | ④ |
| --- | --- | ---: | ---: | ---: |
| Bistro | 같은 실행의 ⑰ | 0 | 0 | 해당 없음 |
| Bistro | 10월 정리본 캡처 `after-a` | 0 | 0 | 0 |
| Bistro | 원래 ⑰ 기록 | 0 | 0 | 0 |
| Minecraft | 같은 실행의 ⑰ | 0 | 0 | 해당 없음 |
| Minecraft | 10월 정리본 캡처 `after-a` | 0 | 0 | 0 |
| Minecraft | 원래 ⑰ 기록 | 0 | 0 | 0 |

⑱ 줄의 정리본·원래 기록 비교 기준은 ⑰이다. 원본 프레임도 직접 봤다(`visual-inspection.json`).
Minecraft의 얇은 이음매가 128·130번에서 약해지는 문제와 Bistro 의자 다리가 끊기는 문제는 그대로다. 품질이 좋아진 것은 없다.

## 성능

새 실행 파일로 2026-11-02에 측정했다. RTX 3060 Ti, DX11 Release x64, SMAA Ultra, 1920×1061, 숨긴 창, VSync Off. 장면마다 독립 프로세스에서 300프레임 준비 후 4,800프레임씩 6회, 모드 순서를 교차해 쟀다. PNG·readback·진단 타이머는 껐다.

| 장면 | 구성 | 전체 AA ms | 공간 ms | velocity ms | temporal ms | WholeFrame ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Bistro | ④ | 0.158520 | 0.101476 | 0.023716 | 0.033309 | 2.514987 |
| Bistro | ⑰ | 0.148026 | 0.113943 | 0.023737 | 0.010326 | 2.505793 |
| Bistro | ⑱ | 0.135418 | 0.103378 | 0.023695 | 0.008323 | 2.490700 |
| Minecraft | ④ | 0.227066 | 0.168260 | 0.023813 | 0.034974 | 1.195338 |
| Minecraft | ⑰ | 0.247951 | 0.188811 | 0.023889 | 0.035226 | 1.220183 |
| Minecraft | ⑱ | 0.232010 | 0.179044 | 0.023879 | 0.029066 | 1.202642 |

같은 실행의 대응 반복으로 계산한 변화율이다. 대괄호는 6회 반복의 95% 구간이며 다중 비교 보정은 하지 않았다.

| 장면 | 비교 | 전체 AA | WholeFrame |
| --- | --- | ---: | ---: |
| Bistro | ⑱ vs ④ | -14.574% [-14.688, -14.459] | -0.965% [-1.241, -0.690] |
| Bistro | ⑱ vs ⑰ | -8.517% [-8.686, -8.349] | -0.602% [-0.853, -0.351] |
| Minecraft | ⑱ vs ④ | +2.181% [+1.225, +3.136] | +0.611% [+0.331, +0.891] |
| Minecraft | ⑱ vs ⑰ | -6.426% [-7.285, -5.566] | -1.436% [-2.052, -0.819] |

10월 19일 수치(Bistro -14.23%, Minecraft +2.21%)와 거의 같아 O1 코드를 지운 영향은 보이지 않는다.

## 단계별 시간

별도 프로세스에서 단계 타이머를 켜고 2,400프레임씩 3회 잰 진단값이다. 위 표와 절대값을 섞지 않는다.

| 장면 | 구성 | edge ms | weight ms | neighborhood ms | temporal ms |
| --- | --- | ---: | ---: | ---: | ---: |
| Bistro | ④ | 0.027019 | 0.024221 | 0.042085 | 0.033463 |
| Bistro | ⑱ | 0.027285 | 0.025112 | 0.043218 | 0.008379 |
| Minecraft | ④ | 0.027671 | 0.085051 | 0.048904 | 0.034895 |
| Minecraft | ⑱ | 0.034511 | 0.086679 | 0.050833 | 0.028887 |

Minecraft에서 ⑱이 ④보다 느린 원인은 edge 단계(+0.006839ms)다. 줄어든 temporal(-0.006007ms)이 이 증가분을 거의 상쇄하고, weight(+0.001628ms)와 neighborhood(+0.001929ms)만큼이 남는다.

이 edge 증가의 대부분은 직전 프레임 edge를 함께 고르는 비용으로 보인다. 예전 진단에서 같은 실행 안의 ⑨(F)−⑥이 +0.006634ms(`Docs/Edge-Persistence-Spatial-Cost`), ⑨(F)−④가 +0.006810ms(`Docs/Edge-Persistence-Eager-Spatial-Mask`)였다. 둘을 빼면 ⑥−④는 약 +0.0002ms다. 서로 다른 프로세스의 값을 뺀 추정이므로 지터에 따른 edge 수 차이의 영향이 작다는 정도로만 해석한다.

같은 조회가 Bistro에서는 +0.00016ms뿐이다. 131번 프레임의 선택 픽셀은 Bistro 69,519개, Minecraft 652,244개로 약 9.4배 차이 나지만, 이것이 원인인지는 하드웨어 카운터로 확인하지 못했다.

## 아직 안 한 것

- 중간 visible texture의 alpha는 ⑰과 다르다. 동일성 판정 범위는 화면 RGB이고 history alpha는 유지된다.
- ④와의 차이에는 edge 선택 외에 지터, history 표본, 혼합 비중, feedback 구조 차이가 함께 들어 있다.
- 숨긴 창 측정이므로 화면 FPS로 바꿔 읽지 않는다.
