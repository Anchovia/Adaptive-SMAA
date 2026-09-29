# 실패 실행 보존

2026-09-29 `20260929_151146` smoke와 `20260929_151320` Bistro capture는
stencil을 매 프레임 초기화하지 않은 최초 구현이다. 완료 CSV의 내부 Aggregate PASS는
저장/모드 설정 검사를 의미하며 실행 범위 검증 PASS가 아니다. **성능·품질 결론에서 제외한다.**

`D:/SMAAResearchCaptures/first-edge-stencil-20260929/item6/bistro/20260929_151320`
의 frame 100에서 edge=50,610, coverage=900,018, 비선택 추가 통과=849,408이었다.
선택 edge 누락은 0이지만 과거 frame의 stencil 값이 남아 moving output도 기존 mask
구현과 달랐다. 정지 RGB는 우연히 같을 수 있어 출력 정지 검사만으로 검출할 수 없었다.
실제 coverage witness가 문제를 검출했다.

원인: baseline wrapper는 전용 stencil을 할당하지만 매 frame ClearDepthStencilView를
호출하지 않는다. Native spatial weights는 zero-edge에서 zero를 출력하므로 stale superset이
공간 RGB에 반드시 영향을 주는 것은 아니다. Temporal execution gate에는 이를 사용할 수 없다.

수정: 새 stencil 선택 route의 첫 edge pass 직전에 stencil만 0으로 clear한다.
기존 ①~④ route는 변경하지 않는다. Clear 비용도 전체 SMAA scope에 포함한다.
