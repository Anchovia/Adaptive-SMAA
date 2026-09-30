# ⑥ coverage와 sample pattern 분리 대조

브랜치: `validation/spatial-edge-coverage-pattern-control`

직접 기준선: `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459` (stencil lifecycle 수정 ⑥).
기존 history 기여 진단 브랜치는 결과 참고만 하며 renderer를 합치지 않는다.
실행 도구 의존성: 기존 `12f5d56`의 비대화형 shader compile 실패 처리만 재사용한다.

| ID | 공간 처리 | Temporal 범위 | Paired jitter/subsample pattern |
|---|---|---|---|
| ABL-Spatial-FirstEdge-Stencil-PatternOff-R | Original SMAA | 기존 first-pass final RG stencil | Off |
| ABL-Spatial-FullScreen-PatternOff-R | A와 동일 | 동일 resolve에서 stencil test만 Off | Off |
| O-T2X-R | 원본 공간 SMAA | 기존 native full-screen | On |

두 내부 검증 조건은 native full-screen Pattern Off 및 새 full-screen Off의 관측 MRT Off
반복이다. 새로운 연구 기법이 아니며 첫 세 조건의 비교 정합성만 검사한다.

전체 화면 대조군은 depth test를 끈 기존 selective state를 복제해 StencilEnable만 FALSE로
바꾼 상태를 사용한다. shader·SRV·sampler·RTV·current/previous spatial history는 그대로다.
이 state는 기존 spatial stencil에 쓰지 않고 temporal draw에만 바인딩한다.
공식 API 근거: [OMSetDepthStencilState](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-omsetdepthstencilstate),
[D3D11_DEPTH_STENCIL_DESC](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_depth_stencil_desc).

Bistro/Minecraft, 1920×1061, Ultra, fixed60, 60-frame warm-up, 각 조건 240 frame을 캡처한다.
기존 still60/move120/still60 경로를 그대로 사용하며 매 mode에서 history를 초기화한다.
장면마다 독립 clean process, 준비 timeout 및 실행 wall-clock timeout을 적용한다.
관측은 캡처에서만 활성화하고 이번 실행의 시간을 성능 결과로 사용하지 않는다.

통과 조건:

1. 모든 SMAA HLSL 원문이 기준선과 동일하고 Release x64 build 성공.
2. 기존 ⑥와 ④의 240-frame RGB hash가 수정 기준선과 동일.
3. Off 비교 조건들의 current/previous RGBA 및 velocity 전체 텍셀 readback hash가 동일.
   XXH64는 기존 엔진 구현을 쓰고 row padding을 제외한다. probe DDS는 byte 비교로 보완한다.
4. 새 full Off와 native full Off, 새 full Off와 관측 Off 반복의 최종 RGB가 동일.
5. 기존 edge 안에서 selective/full Off 출력 동일, 밖에서 selective=current 보존.
6. GPU execution coverage는 selective에서 final RG>0과 같고 full control에서 모든 픽셀.

비교는 기존 세 detail ROI의 GIF, supersample spatial-reference 오차, 필요 시 동일
reference의 CGVQM-2를 사용한다. 단순 연속 frame 차이는 카메라 이동을 포함하므로
절대 shimmer/ghosting 지표로 표현하지 않는다. Reference도 spatial proxy다.
full Off에서 개선되면 coverage 기여를, 여전히 차이가 남으면 native temporal과
sample pattern의 한계를 구분한다. jitter/dilation/source filter/feedback 변경은 하지 않는다.
