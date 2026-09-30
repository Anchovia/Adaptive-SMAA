# SMAA 1X stencil 초기화 단독 비교

연구 브랜치: `experiment/smaa-1x-stencil-clear`.
기준 커밋: `c51ca2896979c78d7fd10c208303c0420a819c76`.
기존 원본 기준선과 종료 수명/프레임 수명 수정만 포함한 공통 기준에서 직접 분기했다.
⑤·⑥, exact-edge discard, MRT, temporal 선택, Adaptive 변경은 가져오지 않는다.

## 질문과 변경 범위

현재 프로젝트의 원본 SMAA 1X 경로와, 그 경로의 전용 stencil을 매 프레임 0으로
초기화한 경로를 비교한다. 두 경로 모두 실제 `AAType::SMAA`, Ultra, temporal Off,
reprojection Off, jitter Off다. 유일한 실행 정책 차이는 1X spatial 호출 직전의
`ClearDepthStencilView(..., D3D11_CLEAR_STENCIL, 1.0f, 0)`다.
기존 SMAA C++ core, HLSL, texture sampling, edge/weight 식은 변경하지 않는다.
초기화 비용도 기존 SMAA 전체 GPU scope에 포함한다. 기본값은 기존 동작이다.

## 공식 구현과의 관계

SMAA 저자 저장소의 고정 커밋 `71c806a838bdd7d517df19192a20f0c61b3ca29d`를 확인한다.
`Demo/DX10/Code/Demo.cpp`의 `clearRenderTargets`는 `rtc.mainDS` stencil을 0으로 지운다.
동일 `mainDS`가 SMAA 1X `go`에 전달된다. 따라서 현재 프로젝트 wrapper의 초기화
누락을 SMAA 알고리즘 일반의 고질적 한계 또는 새로운 AA 알고리즘으로 표현하지 않는다.
소스 hash와 호출 관계를 결과에 기록한다.

- [SMAA 공식 데모](https://github.com/iryoku/smaa/blob/71c806a838bdd7d517df19192a20f0c61b3ca29d/Demo/DX10/Code/Demo.cpp)
- [SMAA 공식 통합 안내](https://github.com/iryoku/smaa/blob/71c806a838bdd7d517df19192a20f0c61b3ca29d/SMAA.hlsl)
- [Microsoft stencil 초기화 API](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-cleardepthstencilview)
- [Microsoft pipeline statistics](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_query_data_pipeline_statistics)

## 검증과 측정

1. Release x64 빌드. SMAA core와 shader 파일을 기준선과 hash 비교한다.
2. Bistro/Minecraft, 1920×1061, fixed 60 Hz의 동일 240-frame 경로
   (정지 60/이동 120/정지 60)에서 기존/초기화/각 반복을 캡처한다.
   각 mode 시작에는 자원을 다시 생성해 이전 mode의 stencil이 넘어오지 않게 한다.
   렌더 준비가 완료되지 않은 frame은 진행하지 않는다.
3. 전체 프레임의 RGB 일치, 반복 일치, 기존 1X 캡처와의 연결을 검증한다.
   일치하면 같은 reference/지표에서 품질 차이가 없다는 근거로 사용한다.
   불일치하면 위치/오차/시간 변화를 분석하고 품질 우열을 별도로 평가한다.
4. 캡처 실행에만 D3D11 pipeline query를 사용해 spatial 3패스 전체의 PSInvocations를
   기록한다. 단독 2차 패스 counter나 메모리 트랜잭션으로 표현하지 않는다.
   해당 query와 CPU readback은 성능 실행에서 끈다.
5. Smoke 후 30초 사전 실행, mode별 300 warm-up, 4,800 frame×6회 교차 순서로
   같은 실행에서 기존/초기화를 비교한다. PNG·query/readback Off, hidden, VSync Off.
   평균, 반복 변동, median/p95/p99 및 측정 가능한 frame 지표를 함께 기록한다.
6. 각 명령은 clean runner의 독립 프로세스와 timeout으로 실행한다. 실패/부분 결과는
   보존하되 채택하지 않는다. 모든 검증과 원시 결과 hash를 커밋하고 푸시한다.

이번 결과는 공간 1X의 초기화 관리 실험이다. 원본 ④나 새 ⑥의 공정한 재측정 또는
최종 8-case 결과를 대신하지 않는다. 매 프레임 clear만으로 현재 final RG와 stencil이
정확히 같아진다고 가정하지 않는다. 기존 first-pass discard 동작도 그대로 보존한다.
