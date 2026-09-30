# 기존 패스에 직전 edge 유지를 넣을 때의 비용

이 문서는 코드 감사와 장치 capability probe 결과다. GPU 구현/benchmark 결과가 아니며,
읽기 횟수나 후보 수를 ms 또는 속도 변화율로 바꾸지 않는다.

## 현재 경로

수정된 ⑥은 1st-pass 최종 edge를 stencil에 기록하고, 2nd-pass spatial 처리에 쓴다.
3rd-pass `NeighborhoodRetainPS`는 current spatial history와 화면 destination을 함께
출력한다. 이후 `FirstEdgeStencilPS`는 `[earlydepthstencil]`로 선택 위치에서만 native
T2X-R을 실행한다. 비선택 출력은 앞선 spatial 결과로 이미 채워져 있다.

따라서 이전 edge를 temporal 셰이더 안에서 확인하는 것만으로는 현재 stencil에서
탈락한 픽셀을 구할 수 없다. 그 픽셀은 셰이더가 실행되기 전에 제외된다.
이전 edge까지 포함한 선택 결과가 depth/stencil 검사 전에 준비되어야 한다.
이 관계는 Microsoft의 [earlydepthstencil 문서](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/sm5-attributes-earlydepthstencil)에 근거한다.

## 필요한 정보와 자원

| 항목 | 현재 자원/변경 | 비용 또는 제약 |
|---|---|---|
| 직전 raw edge | 기존 RG8 edge를 두 장 ping-pong | 추가 1920×1061×2 bytes = 3.89 MiB, 초기화/reset 필요 |
| 현재 edge 여부 | 현재 RG8 또는 동등한 현재 stencil 정보 | 새로운 선택 계산 단계에 접근 필요 |
| 이전 위치 | native temporal과 같은 current point velocity XY | alpha에는 속도 크기만 있어 XY 복원 불가 |
| 이전 edge 여부 | 재투영 좌표의 previous RG8 point load | 추가 texture 접근과 화면 밖 판정 |
| 선택 전달 | temporal 이전 depth/stencil 또는 mask | 아래 실행 구조에 따라 비용이 달라짐 |
| temporal 실행 | 현재 edge + 추가된 직전 edge | 관측 이동 구간에서 대상이 기존 대비 25~30% 증가 |

Ping-pong을 사용하면 edge 전체 복사 pass를 피하는 설계는 가능하지만, 두 자원을
정확히 교대하고 scene/camera-cut/resize/history reset을 연동해야 한다.
3.89 MiB는 texture payload만이며 드라이버 실제 allocation 크기가 아니다.

3rd-pass는 velocity를 이미 읽지만, spatial blending이 있는 분기에서는 주변 velocity의
가중값을 만든다. native temporal의 현재 픽셀 point velocity와 일반적으로 같다고
가정할 수 없다. 무조건 재사용하면 이번 offline 가설과 재투영 좌표가 달라질 수 있다.
원본 `SMAA.hlsl`의 `SMAANeighborhoodBlendingPS`와 `SMAAResolvePS`를 대조했다.

## 공식 기능과 실제 장치 확인

Microsoft는 [shader-specified stencil reference](https://learn.microsoft.com/en-us/windows/win32/direct3d11/shader-specified-stencil-reference-value)를
D3D11.3의 optional 기능으로 정의하며 `PSSpecifiedStencilRefSupported` 확인을 요구한다.
현재 데모와 같은 11.1/11.0 feature-level 요청으로 별도 무창 장치 probe를 실행했다.
화면 렌더링, draw, CMAA2 실행은 하지 않았다.

| 검사 | 결과 |
|---|---|
| Adapter | NVIDIA GeForce RTX 3060 Ti |
| 생성 feature level | 11.1 (`0xb100`) |
| OPTIONS2 조회 | 성공 (`0x00000000`) |
| PSSpecifiedStencilRefSupported | **false** |
| SV_StencilRef shader compile ps_5_0 / ps_5_1 | 둘 다 성공 |
| CreatePixelShader ps_5_0 / ps_5_1 | 둘 다 `0x80070057` |

컴파일 성공만으로 실행 지원을 판단할 수 없다. 이 장치/런타임에서는 3rd-pass에서
SV_StencilRef를 내보내는 간단한 통합 경로를 채택할 수 없다. 전체 D3D11 또는
다른 GPU에서 불가능하다고 일반화하지 않는다. 원시 결과는 `stencil-ref-probe.txt`다.

## 검토한 전달 구조

| 구조 | 추가 pass | 남는 비용/판정 |
|---|---|---|
| Temporal에서 현재/이전 edge를 읽고 분기 | 없음 | stencil 선거부를 끄면 화면 전체가 판정 shader를 실행. 기존 실패 경로의 비용을 되풀이할 수 있어 기본안에서 제외 |
| 별도 mask/stencil 준비 | 있음 | 재투영과 edge load에 새 draw 비용이 추가됨. 현재 연구 목표의 기본안으로 채택하지 않음 |
| 3rd-pass에서 SV_StencilRef 출력 | 없음 | 현재 장치 미지원 |
| 3rd-pass에서 전용 depth에 0/1 기록, temporal에서 early depth 검사 | 없음이라는 설계 | 공식 기능으로 구성 가능한 대안이나 실제 coverage·공간 출력·성능 검증 전에는 작동/속도 보장 불가 |

마지막 대안은 SMAA 전용 `m_texDepthStencil`의 depth 부분을 사용하는 구상이다.
장면 reprojection용 depth를 덮어쓰는 설계가 아니다. 2nd-pass가 끝난 뒤 3rd-pass에서
원래 spatial 색상과 함께 선택 depth를 쓰고, temporal에서 해당 depth만 검사한다.
픽셀 셰이더의 depth 출력 자체는 Microsoft의
[Pixel Shader Stage](https://learn.microsoft.com/en-us/windows/win32/direct3d11/pixel-shader-stage)와
[depth/stencil 설정](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-depth-stencil)에 정의된 기능이다.
이를 AA 후보 전달에 쓰는 방식은 이 연구의 설계안이며 일반적인 TSCMAA 구현이라고
표현하지 않는다. Late depth write, depth 압축/대역폭, 기존 stencil 상태와의 연결이
추가 비용을 만들 수 있다. 기능/출력·invocation 검증과 paired GPU 측정이 필요하다.

후보 합집합에서 이점이 확인된 부분은 보존하되, 아직 원본 T2X-R 품질에 도달하지
못했고 가려짐 해제 검증도 없다. 따라서 이번 단계에서 비용이 검증되지 않은
전달 구조를 기본 renderer에 붙이지 않았다. 추가 pass 없이 구현할 가능성과
추가 비용이 거의 없다는 주장은 서로 다르다.

Probe 재현: x64 VS2022 개발 환경에서 `probe_stencil_ref_support.cpp`를 C++17로
빌드하고 `d3d11.lib`, `d3dcompiler.lib`에 링크한다. 별도 실행 파일은 무창으로
capability 조회와 shader 생성만 수행하고 종료한다.
