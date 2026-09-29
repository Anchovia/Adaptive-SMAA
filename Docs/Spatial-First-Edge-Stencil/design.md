# ⑥ 원본 spatial SMAA + first-edge stencil temporal

상태: 구현 및 검증 진행 중. 기존 ⑤·⑥의 채택 철회와 원시 자료 보존은
`research/six-case-results-summary`의 `937b347`에 기록했다. 본 브랜치의 과거
Spatial-First-Edge-Temporal / Pattern-Off 문서는 의존성을 가져오면서 남은 이력이며,
새 실행 구조의 검증 결과로 사용하지 않는다.

## 범위와 독립성

- branch: `experiment/spatial-first-edge-stencil`
- base: `c51ca28` (검증된 원본 + BeginFrame 수명 교정)
- 명시적 의존성: `8e5a972`의 공간/history 연결 및 캡처 도구,
  `28f08fa`의 지터/area index 결합 설정과 검증 도구만 가져왔다.
- ①~④ 원본 알고리즘은 보존한다. ⑤는 별도 baseline-derived 브랜치에서 구현한다.
- 선택식: 원본 1차 패스가 최종 저장한 `any(RG > 0)`. 임의 luma 근사,
  non-dominant 제거, dilation, 다른 history filter/weight를 넣지 않는다.
- 주 실험은 projection jitter와 area subsample pattern 모두 Off다. Native T2X-R은 On.
  지터 변경 효과를 분리하기 위해 Off full-screen control도 유지한다.
- reprojection은 camera/depth만 사용하며 object-motion 지원을 주장하지 않는다.

## 이전 기록을 재사용한 판단

`experiment/temporal-edge-read-cost`의 `b97d7a0`에서는 native resolve에 RG read를
추가했을 때 Bistro +5.67%, Minecraft +10.16%였다. Bind-only의 일관된 증가는
없었으며 Load/Point 변경도 실질적 개선을 입증하지 못했다. 같은 시도를 반복하지 않는다.
`experiment/temporal-edge-only-cost`의 `4ea2422`는 black-output 마이크로벤치마크로,
edge-only와 output-only의 차이가 0.000410/0.000599 ms였지만 native와 결합한 비용은
가산 상수가 아니었다. 이를 완성 AA 성능으로 인용하지 않는다.

이전 compact/indirect 경로는 선택 실행의 참고이지만 후보 compact/args/copy와
다른 temporal 수식까지 가져오면 이번 원본 edge + native resolve 질문이 달라진다.

## 실행 구조

1. 기존 1차 edge pass: 원본 HLSL 함수를 호출한다. local contrast 처리 후 최종 RG가
   0인 픽셀도 discard하여 stencil=1이 실제 RG edge와 정확히 대응하게 한다.
   Native의 초기 threshold discard만으로는 최종 edge와 stencil이 다를 수 있다.
2. 원본 2차 blending-weight 계산. 최종 zero-edge에서 생략되는 계산은 원래 weight=0이며
   target clear 값과 같아야 한다. 실제 RG/공간 결과 비교로 검증한다.
3. 기존 3차 neighborhood blending 계산은 그대로 두고 MRT로 current history와 visible
   destination에 같은 값을 기록한다. 별도 copy pass는 없지만 추가 store 비용은 있다.
4. temporal draw는 동일 fullscreen triangle을 제출하되 stencil==1과
   `[earlydepthstencil]`로 셰이더 실행 전에 비선택 sample을 거부한다.
   resolve에는 edge SRV/selection branch/current-only fallback이 없다.
   선택 sample은 원본 `SMAAResolvePS`를 호출한다. 다음 history는 원본처럼 current
   spatial frame이며 resolved feedback으로 변경하지 않는다.

Microsoft 근거:
- [earlydepthstencil](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/sm5-attributes-earlydepthstencil)
- [Depth/stencil과 MRT](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-depth-stencil)

GPU는 quad/helper lane이나 cache transaction 단위로 동작할 수 있다. 선택 픽셀 수와
물리 메모리 transaction 수가 같다고 주장하지 않는다. 전체 화면 draw 제출과 전체 화면
pixel shader 실행은 구분한다. 실행 감소는 GPU pipeline statistics로 확인한다.

## 통과 전 완료로 표시하지 않을 조건

- Native SMAA.hlsl/SMAAWrapper.hlsl 원문 보존, 새 resolve DXBC에 강제 early-test flag,
  edge load와 선택 분기가 없음을 확인.
- Capture 전용 coverage MRT의 모든 픽셀이 native 최종 RG mask와 일치.
- Occlusion passing-sample count가 해당 mask count와 일치.
- PSInvocations를 native/fullscreen-mask와 비교. helper lane을 포함한 수치를 그대로 기록.
- current spatial RGB가 실제 1X와 일치하며 비선택 final이 current와 일치.
- 새 실행 출력이 같은 조건의 과거 mask 실행과 일치. ①·②·④ 이전 capture hash bridge.
- 진단 MRT/query를 끈 repeat도 동일 출력. 모든 진단은 benchmark에서 비활성.
- 두 장면 clean process smoke 후 paired benchmark. Temporal 단독과 전체 AA를 분리하고
  MRT/first-pass 변경 비용을 전체 AA에 포함.

기존 mask 실행은 `DIAG-Spatial-FirstEdge-Masked-PatternOff-R` 대조군으로만 남기며
새 구현으로 채택하지 않는다. 성능 우위와 품질 우위는 검증 전에 가정하지 않는다.
