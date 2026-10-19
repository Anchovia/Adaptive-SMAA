# ⑲ 후속 후보: 이전 edge 조회 지연

**후속 감사 정정:** 기존 `Docs/Edge-History-Color-Blend-Optimization/method-ko.md`에는 지연→선행 이전 edge 조회를 이미 채택한 것으로 기록돼 있다. 이 후보는 새로운 해법이 아니라 ⑱의 색 혼합·MRT 조건에서 과거 선택을 재검증한 실험이다. 최초 선정 때 이 제외 기록을 충분히 반영하지 못했다. 원시 결과는 유지하고 기법의 새로움에 대한 분류만 정정한다.

RGBA8/Gather/결합의 첫 screening은 두 장면에서 전체 AA 이득을 확정하지 못했다. 원자료는 `screening-performance.json`에 보존한다. 이 후속 후보는 ⑱의 RG8·point luma를 유지하고 첫 raw-edge pass의 실행 순서만 바꾼다.

기존은 모든 픽셀에서 velocity와 previous raw edge를 읽은 뒤 `current || previous`로 선택한다. 후속은 current raw edge를 먼저 계산하고, current가 없는 픽셀에서만 이전 두 읽기를 수행한다. 현재 edge가 있으면 union 결과가 이미 true다. current=0/previous=1 픽셀은 계속 유지하므로 이전에 기각한 current-only weight gating이 아니다. raw edge 출력과 stencil union, SMAA weights, temporal resolve 수식은 그대로다.

HLSL `&&`/`||`는 [단락 평가를 하지 않는다](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-operators). 따라서 표현식 재배치만 하지 않고 [명시적인 branch](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if)를 사용한다. current luma 계산은 모든 픽셀에서 먼저 수행하며, 조건부 previous 조회는 기존 `SampleLevel`/`Load`를 유지해 미분 기반 mip 선택을 추가하지 않는다. threshold/LCA·재투영 좌표·바깥 화면 판정도 바꾸지 않는다.

새 기본 Off `SetSelectedLazyPreviousEdge`는 기존 ⑰ feedback/source-component 경로에서만 허용한다. `-smaaCase19SpatialCapture|Smoke|Benchmark|Profile <scene> <root> lazy`는 ④·⑰·⑱·`ABL-ET2X-R-Case19-LazyPreviousEdge` 네 구성을 같은 실행에서 비교한다. runner에서는 `-Variant Lazy`를 명시한다. 기존 6-mode matrix는 `Basic`으로 보존한다.

옵션 Off DXBC 22개가 ⑱ 소스와 동일하고, 옵션 On DXBC의 velocity sample_l·previous-edge ld 두 명령이 실제 조건문 내부에 있는지 검사한다. 실제 2×240프레임 RGB bridge와 같은 binary/matrix smoke 통과 뒤 300 warm-up + 4,800×6회 정/역 반복을 수행한다. pass timer On profile은 별도 실행이다. 조회 감소가 divergence/latency를 이기지 못할 수 있으므로 속도 개선을 미리 가정하지 않는다.
