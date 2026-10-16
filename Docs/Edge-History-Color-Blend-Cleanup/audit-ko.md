# ⑰ 코드 감사: 실제 호출·pass 순서와 정리 범위

대상: `ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend`
(브랜치 `experiment/edge-history-source-color-blend`, `5bdd189`). 아래 줄 번호는 `5bdd189` 기준이다.

## 1. 한 프레임의 실행 흐름

`CMAA2Sample` 이 매 프레임 `m_SMAA->Draw(mainColorRT, m_exportedLuma, mainDepthRT, &camera)` 를 호출한다
(`CMAA2Sample.cpp:889`, scope timer `SMAA`). 입력 luma가 있으므로 edge 입력은 `INPUT_LUMA_RAW` 다.

| 순서 | CPU 위치 | GPU 작업 | timer |
|---|---|---|---|
| 1 | `UpdateResources` (`vaSMAAWrapperDX11.cpp:345`) | 크기·preset·입력·reprojection 변경 또는 temporal 자원 부재 시 SMAA 객체·DSV·history 2장·spatial 사본·velocity 재생성 | — |
| 2 | `Draw` L436-468 | depth + 현재/이전 unjittered VP → R16G16F camera velocity (전체 화면) | `SR_CameraVelocity` |
| 3 | `SMAA::go` L320-327 | raw edge RT ping-pong swap (`edgesRT` ↔ `previousRawEdgesRT`) | `SF_Spatial` |
| 4 | `SMAA::go` L335-374 | edge RG8·blend RGBA8 clear, 상수 갱신, **SMAA 전용 stencil만 0으로 clear** | `SF_Spatial` |
| 5 | `edgesDetectionPass` → `PersistenceLumaRawEdgePS` | 직전 raw edge를 point velocity로 재투영해 먼저 조회, 현재 edge 계산. 둘 다 없으면 discard. stencil REPLACE 1 = 합집합, RG = 현재 edge만 | `SF_Spatial` |
| 6 | `blendingWeightsCalculationPass` | native weight shader, stencil EQUAL 1(합집합). 이전 edge만 있는 픽셀은 RG=0이라 weight 0 | `SF_Spatial` |
| 7 | `neighborhoodBlendingPass` → `NeighborhoodFeedbackSeedPS` | native blending 결과를 spatial 사본·visible(dstRT)·next history 3 MRT에 전체 화면 기록. stencil 미사용, depth ALWAYS 쓰기 | `SF_Spatial` |
| 8 | `reprojectFirstEdgeStencil` → `SourceComponentPS` | stencil EQUAL 1, `[earlydepthstencil]`. visible·next history 2 MRT | `SR_Resolve` |
| 9 | `Draw` L577-579 | history valid 표시, SMAA/wrapper frame index 진행 | — |

### resolve 수식 (`SourceTemporalComponent.hlsl`, `SourceTemporalMath.hlsli`, `CatmullRomHistory5Tap.hlsli`)

- current: spatial 사본 point sample. velocity point sample, `historyUV = uv - velocity`.
- previous: 이전 history의 point sample(알파 전용) + MJP 계열 정규화 Catmull-Rom 5-fetch bilinear RGB.
- weight 0.8 고정. RGB = `SourceEncodedToLinear(sqrt(lerp(c², h², 0.8)))`, c/h는 saturate 후 표준 sRGB encode.
- visible = (혼합 RGB, `lerp(current.a, previous.a, 0.8)`), next history = (혼합 RGB, current spatial alpha).
- history 무효(첫 프레임, reset, 자원 재생성): previous SRV = current spatial, `sourceTemporalComponent=false`
  → ⑭ `FixedWeightRGBFeedbackPS` 실행. velocity가 0이므로 Catmull-Rom 중심 weight만 남아 결과는 spatial과 같다
  (진단 f0/f150/f200에서 선택 픽셀의 spatial 대비 변경 0으로 확인).

### RGB/alpha 의미

| 텍스처 | RGB | alpha |
|---|---|---|
| spatial 사본 `m_feedbackCurrentSpatial` | 현재 SMAA 1X 공간 결과 | native SMAA reprojection velocity alpha |
| visible `dstRT` | 비선택 = spatial, 선택 = resolve | 비선택 = spatial alpha, 선택 = alpha lerp (PNG에는 저장되지 않음) |
| next history `m_temporalHistory[cur]` | visible RGB와 동일 | 항상 current spatial alpha |

### stencil 수명 (수정된 stencil lifecycle 유지)

- 매 프레임 edge pass 전 `ClearDepthStencilView(dsv, D3D11_CLEAR_STENCIL, 1.0, 0)` (`SMAA.cpp:374`).
- edge pass: `m_DisableDepthReplaceStencil` (depth Off, stencil ALWAYS/REPLACE, ref 1).
- weight pass, resolve: `m_DisableDepthUseStencil` (depth Off, stencil EQUAL, ref 1).
- neighborhood: `m_DisableDepthStencil` (stencil Off, depth ALWAYS + 쓰기). depth plane은 clear되지 않고 이후 어떤 pass도 읽지 않는다.

### history·reset

- `m_temporalHistory[2]` ping-pong, wrapper/SMAA frame index를 assert로 일치 확인.
- reset 경로: 카메라 로드·정지영상 변경·장면 변경 시 `ResetTemporalHistory` (`CMAA2Sample.cpp:294,428,500`), 크기·preset 변경 시 `UpdateResources` 전체 재생성.
- reset 후 `previousValid=false` 이므로 t10(직전 raw edge)은 null로 binding된다.

### ④ (O-T2X-R) 과의 관계

같은 `Draw`/`go` 를 사용하지만 `SpatialFirstEdge=false` 이므로 native edge·weight·blending(blend state) → history,
전체 화면 `DX10_SMAAResolvePS` → dstRT 경로를 탄다. paired jitter/subsample On. ⑰ 전용 플래그는 technique 선택에만
쓰이고 ④ 설정은 harness `Configure()` 가 mode마다 다시 지정한다.

## 2. 분류

**확인된 중복 (코드 구조, GPU 작업 중복 아님)**
- temporal 자원 부재 조건이 `UpdateResources` 안에 두 번 반복 (L352-355, L405-406).
- feedback resolve technique 생성 블록 4개가 파일명만 다름 (L712-741).
- resolve technique 선택이 중첩 삼항식, 13개 위치 인자 중 bool 4개.
- capture 전용 query/coverage/weight 코드가 production `Draw` 흐름 중간에 섞임.

**측정이 필요한 후보 (성능 측정 허용 후)**
- 읽히지 않는 depth plane: stencil-only clear(D24S8)와 3차 pass의 depth ALWAYS 쓰기.
- pass별 비용 분해(준비/1차/2차/3차/velocity/resolve). 측정 전 병목을 단정하지 않는다.

**유지해야 하는 처리**
- 3 MRT neighborhood: resolve가 같은 픽셀의 spatial 값을 SRV로 읽으면서 next history를 RTV로 쓰므로 별도 사본이 필요하다(D3D11은 같은 subresource의 SRV/RTV 동시 binding을 허용하지 않음).
- edge/blend RT clear, 합집합 stencil, 직전 edge 선행 조회, previous point alpha 조회(visible alpha 유지), seed fallback.

**이전 기록상 이미 시도한 방식 (반복하지 않음)**
- 지연→선행 이전 edge 조회: 채택되어 현재 구조 (`Docs` of `experiment/edge-persistence-spatial-cost`).
- 2차 pass current-only gating(depth 표시): 개선 없음, 미채택 (`experiment/edge-persistence-eager-spatial-mask` decision.json).
- shader-specified stencil ref: 실험 장치 미지원. SV_Depth export: 고정 비용 큼 (`validation/edge-persistence-cost-audit`).
- velocity integer Load (edge pass), resolve current/velocity direct Load: 개선 없음.

## 3. 이번 정리에서 바꾼 것 (`b86573c`)

- `ValidateSelectedTemporalConfiguration()`: 기존 네 검사와 메시지·순서를 그대로 옮김.
- `TemporalResourcesMissing()`: 두 곳의 동일 조건 공통화.
- `BeginExecutionDiagnostics()/EndExecutionDiagnostics()`: capture 전용 query·coverage·weight 처리를 분리. 실패 시 같은 지점에서 `UnspecifiedError` 반환.
- `SMAA::FirstEdgeResolveOptions` + `firstEdgeResolveTechnique()`: 중첩 삼항식과 위치 bool 인자를 이름 있는 선택으로 대체. 선택 결과·RT 개수·적용 순서(ApplyStates → OMSetRenderTargets) 동일.
- `stencilGatedFeedbackResolve` helper: 동일한 4개 technique 생성 블록을 공통화. VS/PS 파일·entry·profile·DSS·BS·ref 동일.
- 플래그와 RGB/alpha 의미, 선택 경로 주석.

HLSL, pass 순서, binding, state 객체, clear, resource 형식, history topology, jitter/subsample, reprojection은 바꾸지 않았다.
