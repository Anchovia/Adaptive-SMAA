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

## 아직 안 한 것

- 새 실행 파일의 성능은 재지 않았다. 지금 인용하는 ⑱ 수치(④ 대비 Bistro -14.23%, Minecraft +2.21%)는 10월 19일 실행 파일 결과이며, 그 빌드에는 꺼진 상태의 O1 코드가 남아 있었다.
- 중간 visible texture의 alpha는 ⑰과 다르다. 동일성 판정 범위는 화면 RGB이고 history alpha는 유지된다.
- ④와의 차이에는 edge 선택 외에 지터, history 표본, 혼합 비중, feedback 구조 차이가 함께 들어 있다.
