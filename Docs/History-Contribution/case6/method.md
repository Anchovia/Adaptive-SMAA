# ⑥ 실제 history 혼합 비중 진단

수정 기준선 `304f749`에서 직접 분기했다. 지터 Off, native point history,
velocity-alpha 기반 weight 0..0.5, spatial-frame history, first-pass 최종 RG와
동일한 stencil 선택을 유지했다. 후보 확장이나 TSCMAA 알고리즘 변경은 없다.

기존 resolve의 계산 결과를 capture 전용 R32_FLOAT MRT에 기록한다. 선택 밖은
-1로 초기화하고 실행된 픽셀은 실제 weight를 기록한다. 따라서 미실행과 weight 0을
구분한다. 같은 프레임의 temporal 직전 공간 SMAA 결과와 final RGB를 함께 저장한다.
RGB 변화는 양자화된 8-bit RGB 각 채널의 절대 차이 중 최댓값이며 품질 점수가 아니다.

각 장면은 별도 clean process로 실행한다. 240-frame target(진단 On), native ④,
target repeat(진단 Off)를 기존 기준선 RGB hash와 비교했다. 두 장면 각각 720 frame,
합계 1,440 frame mismatch 0이다. 100..219의 240개 weight/coverage 기록에서는 기존
선택 영역이 보존됐고, 비선택 픽셀의 current→final 변화는 0이다.

100/179/180/190 frame의 current/previous RGBA와 velocity도 저장해 point reprojection과
weight의 CPU mirror를 검사했다. DXBC의 `mul` 다음 `mad`를 반영한 단일 반올림 계산을
사용한다. 단순 float32 곱셈 두 번은 동일 alpha에서 GPU의 미세 잔차를 재현하지 못한다.
texel 경계에 가까운 좌표는 이 CPU 보조 검사에서만 제외하고 제외 수를 기록한다.
GPU 시각화와 통계에는 전체 실제 readback을 사용한다.

production entry 6개의 DXBC는 기준선과 동일하다. 직접 macro 인자와 엔진의 virtual
macro include 두 경로를 검사했다. 최초 실행은 virtual include 순서를 놓쳐 컴파일에
실패했으며 `excluded-startup.json`으로 제외했다. 원래 출력 캡처 전 실패였고,
그 실행에서 성능·품질 결과를 채택하지 않았다. 비대화형 실패 종료는 기존 `12f5d56`의
실행 도구 부분만 재사용했다.

이동 구간(100..179)에서 선택된 픽셀의 평균 실제 weight는 Bistro 0.4773,
Minecraft 0.4918이다. 따라서 이 장면에서 반짝임이 남는 현상을 '실제 weight가
거의 0이라서'로 일반화할 수 없다. 정지 안정 구간(190..219)은 weight 0.5지만
current와 history가 같아서 RGB 변화가 0이다. weight와 출력 변화는 다른 정보다.
후보가 빠지는 위치, 점 샘플링, 두 프레임 history, 지터 차이 등의 원인별 기여는
이 진단만으로 확정하지 않는다. 새 속도 또는 품질 개선 결과도 아니다.

재현: `verify_history_contribution_shaders.py`, `build_baseline.py`,
`run_history_contribution.ps1 -Scene bistro|minecraft`,
`analyze_history_contribution.py --scene bistro|minecraft`.
완료 run receipt는 덮어쓰지 않으며 원본 자료와 분석 JSON을 함께 보존한다.
