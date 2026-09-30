# 직전 raw edge 유지 비용 감사

- 브랜치: `validation/edge-persistence-cost-audit`.
- 직접 기준선: 수정된 ⑥ `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459`.
- 명시적 의존성: 감사 대상 ⑦ 렌더러 `2d4d0ccba06f6f9882c16abffd7489bed52030d7`만 cherry-pick.
- 기존 `experiment/spatial-edge-persistence-depth`와 품질/성능 결과는 수정하지 않는다.
- ④는 원본 spatial SMAA + T2X-R, paired pattern On. ⑥은 current-edge selective,
  ⑦은 current OR camera-reprojected previous RAW edge selective, 모두 pattern Off.
  Object motion, dilation, 지터, sampling/weight/feedback 정책 변경은 범위 밖이다.

## 정적 감사

raw RG8 texture 두 개를 swap하므로 매 프레임 edge CopyResource나 CPU 전송은 없다.
기존 ⑦은 3차 spatial pass에서 현재 raw edge, point velocity, 재투영한 previous raw
edge를 읽고 OR 결과를 SV_Depth=0/1로 전달한다. Temporal은 early depth EQUAL로 거부된다.
SF_Spatial은 세 spatial pass 합계이며 개별 3차 pass timestamp가 아니다.

`m_DisableDepthStencil`이라는 이름과 달리 실제 상태는 DepthEnable=TRUE,
DepthFunc=ALWAYS, DepthWriteMask=ALL이다. 원래 ⑥도 3차 pass에서 raster depth=1을 쓴다.
따라서 depth 쓰기 유무와 shader depth export 차이를 혼동하지 않는다.

## 비용 분리 조건

| 이름 | 수행하는 변경 | 최종 출력 기준 |
|---|---|---|
| A | 기존 ⑥ | 보존된 ⑥ |
| S | raw edge ping-pong만 사용 | A |
| K | S + 고정 1을 SV_Depth로 출력, temporal은 current stencil | A |
| D | current edge를 SV_Depth로 출력, depth-gated temporal | A |
| P | ⑦의 union depth 준비, temporal은 current stencil 유지 | A |
| B | 기존 ⑦, union depth-gated temporal | 보존된 ⑦ |
| L | B의 depth semantic만 SV_DepthLessEqual로 교체 | B |
| E | 1차 pass에서 union을 stencil에 표시, 원래 3차 pass 유지 | B |
| O-T2X-R | 원본 ④ | 보존된 ④ |

E는 raw edge 계산식의 early discard를 zero return으로 대체한 별도 함수를 사용한다.
현재 raw edge가 없을 때만 point velocity/previous raw edge를 검사하여 stencil의
생존 여부를 정한다. Raw texture에는 현재 RG만 쓰므로 union이 다음 프레임 raw edge로
누적되지 않는다. Previous-only 위치에서는 raw RG가 0이고 2차 pass의 blending weight도
0이어야 한다. 별도 draw/dispatch, color copy, temporal shader의 mask 읽기는 없다.

동일 출력은 지표나 육안 유사도가 아니라 전체 1920×1061 RGB byte hash로 검사한다.
진단 capture에서는 실제 temporal coverage와 PS invocation을 별도 확인한다.
출력 동일성은 새로운 품질 개선 주장과 구분한다.

## 실행 및 측정

RTX 3060 Ti, DX11 Release x64, Ultra, 1920×1061, hidden, VSync Off.
성능: 30초 준비, 조건별 300 warm-up, 4,800 frame × 3회, 홀수 반복은 역순.
PNG, GPU readback, invocation query는 성능 실행에서 Off. 장면별 독립 clean process.
성능 표의 변화율은 같은 실행의 ④/A/B를 분모로 계산한다. 초기 smoke와 본 측정을 구분한다.

첫 conservative-depth compile은 centroid position 선언이 없어 FXC validation에서
자동 종료됐다 (`20261001_032510`). 필수 선언을 고친 뒤 Test가 통과했다.
실패 실행을 성능/출력 결과로 사용하지 않았다. `earlydepthstencil`을 depth-export
shader에 강제로 붙이면 export 의미를 훼손하므로 그렇게 수정하지 않는다.

## 참고 자료와 해석 범위

- [NVIDIA shader performance guidance](https://developer.nvidia.com/blog/advanced-api-performance-shaders/):
  하드웨어 depth/stencil rejection, shader depth export와 Early-Z 제약, 분기/texture latency.
- [Microsoft HLSL semantics](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-semantics):
  SV_Depth 및 conservative depth의 계약. Fullscreen raster depth=1에 출력 0/1은 <=를 만족한다.
- [Microsoft stencil operations](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_stencil_op):
  살아남은 pixel의 stencil을 reference 값으로 REPLACE하는 기존 상태를 재사용한다.
- [MJP의 Early-Z 직접 실험](https://therealmjp.github.io/posts/to-earlyz-or-not-to-earlyz/):
  depth export 및 forced early depth와의 상호작용. 다른 GPU/DX12 실험을 현재 GPU 수치의 증거로 쓰지 않는다.

문서는 원인 후보와 구현 계약의 근거다. 현재 3차 pass는 ALWAYS여서 제거할 pixel이 없으므로,
관측된 비용을 단순히 'Early-Z가 꺼져서 더 많은 pixel이 실행됨'이라고 설명하지 않는다.
대조 실험은 shader depth export 경로의 비용을 분리하지만 세부 ROP/cache stall 원인까지
확정하려면 hardware counter가 필요하다.
