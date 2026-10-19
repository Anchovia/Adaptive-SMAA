# 19: 전체 AA 오버헤드 추가 최적화 자료 검토

사용자가 요청한 별도 `experiment/case19-aa-overhead-optimization` 브랜치다. 의존성은 18 후보인 17+O2+O3이며 기존 17/18 및 최종 8-case 기본값은 보존한다. 이 문서의 19는 사용자 요청의 연구 항목 이름이다.

논문·학회 발표·공식 API 계약·제조사 가이드·공개 구현의 관련 본문/소스 구간을 검토했다. 100편의 논문 전체를 정독했다는 의미는 아니다. 중복 URL과 접근 실패, 본문을 읽을 수 없는 자료는 완료 개수에서 제외하며 개별 링크와 적용 판단은 `research-ledger.json`에 보존한다.

## 후속 감사 정정

자료 검토와 이번 네 구성의 실패는 ⑱의 최적화 한계나 가능한 모든 기법의 검증 완료를 의미하지 않는다. 기존 `Docs/Edge-History-Color-Blend-Optimization/method-ko.md`에는 이전 edge 선행 조회를 이미 채택한 기록이 있어, ⑲의 조회 지연은 과거 선택의 재검증으로 분류한다. 또한 기존 cleanup 감사에는 shader-specified stencil ref가 실험 장치 미지원으로 기록돼 있다. 이 두 기록을 최초 후보 선정·보류 사유에 충분히 반영하지 못한 점을 정정하며, 수치나 RGB 증거는 변경하지 않는다.

## 기준과 우선순위

- 18 = `ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend` + `OPT-NeighborhoodNoDepth+PresentHistory`.
- Original 공간 SMAA, camera/depth 재투영, Pattern Off, 기존 선택 mask·5-fetch·0.8 weight·색 혼합·RGB feedback을 고정한다.
- 기존 진단에서 Minecraft의 18은 ④보다 edge +0.006756 ms, weights +0.001540 ms, neighborhood +0.001681 ms, resolve -0.006332 ms였다. 별도 pass timer On 진단으로 본 benchmark 절대값과 섞지 않는다.
- ④와 18은 pattern과 history 의미도 다르므로 공간 차이 전부를 선택 영역 오버헤드로 부르지 않는다.

## 우선 구현할 독립 후보

1. **RGBA8 raw edge 저장**: 공식 SMAA C++ 샘플은 NVIDIA에 RGBA8을 선택한다. 현재 wrapper는 adapterDesc를 전달하지 않아 RG8을 생성한다. RG 각각의 8-bit UNORM 의미를 유지하면서 포맷만 선택하는 default-Off 옵션으로 시험한다. 더 넓은 포맷이 반드시 빠르다고 가정하지 않는다. 기존 ④와 18은 그대로 RG8을 사용한다.
2. **raw luma 이웃 Gather**: Microsoft Gather 계약과 NVIDIA/AMD 가이드가 제시하는 단일 채널 묶음 읽기를 검토한다. L/current/left/top을 한 Gather로 얻되 기존 threshold/LCA 수식과 나머지 이웃 접근은 유지한다. texel swizzle·clamp·odd resolution을 GPU fixture로 먼저 검증한다. 포맷 후보와 독립으로 켜고 결합은 별도 cell로 둔다.

## 보류·제외

- stencil clear 제거: sparse write 뒤 미선택 edge/weight가 반드시 0이어야 하므로 현재 구조에서는 안전하지 않다. DiscardView는 zero clear 대용이 아니다.
- stencil writer에 강제 earlydepthstencil: discard 전에 stencil이 기록되어 선택 mask 의미가 바뀔 수 있다. 기존 resolve의 early test는 유지한다.
- 품질 preset/검색 길이/threshold/weight/pattern 변경, half precision, 새 필터: 현재 RGB 보존 범위 밖이다.
- compute 타일/compaction/async queue: DX11 및 기존 negative 결과와 정확한 좌표·양자화 보존을 고려한다. 단순 전환만으로 이득을 주장하지 않는다.
- 기존 실패한 current-only weight gating, 정수 velocity Load, depth+stencil clear, 단일-target 전용 resolve shader는 근거 없이 반복하지 않는다.

## 검증·측정

같은 실행에 ④·17·18과 각 19 후보를 넣고 장면별 240-frame RGB를 기존 hash와 bridge한다. 불일치가 있으면 프레임·좌표·차이를 보존하고 채택하지 않는다. 원본 전체 화면과 이동/전환/실패/정지 ROI를 직접 확인한다. 통과한 후보만 clean process smoke 후 300 warm-up + 4,800×6 정/역 반복으로 AA/spatial/velocity/resolve/WholeFrame을 비교한다. 추가 pass 진단은 별도 실행이며 production 기본값은 gate 완료까지 변경하지 않는다.
