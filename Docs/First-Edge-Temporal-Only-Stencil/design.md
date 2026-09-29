# ⑤ 재구현: 공간 혼합 없이 첫 edge에서만 temporal 실행

상태: 두 장면의 실행 범위/출력 및 입력 동일성 gate 통과. 반복 성능 결과는 report.md로
별도 기록한다. ①~④는 보존한다. 과거 전체 화면 mask-read
⑤의 완료 판정은 `research/six-case-results-summary`의 `937b347`에서 철회했다.

## 독립 브랜치와 의존성

- branch `experiment/first-edge-temporal-only-stencil`, 직접 base `c51ca28`.
- 필요한 항목만 `7c2feeb`(원본 temporal-only control과 raw alpha 준비), `a774772`
  (첫 edge 검출/진단), `543e657`(paired sample pattern 설정/캡처)에서 가져왔다.
- ⑥의 `037fd8b`에서는 exact stencil, early-test native resolve, coverage/query 계측
  구성 요소만 명시적으로 재사용했다. ⑥의 spatial MRT 구현이나 go() 변경은 가져오지 않았다.
- 과거 구현 문서/JSON은 의존성 이력이다. 새 구현 검증으로 사용하지 않는다.

## 실행

Camera/depth velocity 생성 → native first-edge 검출 및 exact stencil 기록 → 기존 raw
준비에서 history와 visible destination을 MRT로 저장 → stencil 통과 edge에서만 native
T2X-R resolve를 실행한다. Spatial weight calculation과 neighborhood blending은 실행하지
않는다. RGB는 raw current를 유지하며 alpha에는 기존 ③과 같은 속도 정보를 저장한다.

Temporal shader는 current/velocity/history를 선택 위치에서만 읽으며 edge texture 읽기와
선택 분기가 없다. 비선택 visible color는 raw 준비 단계에서 이미 저장돼 있다. Jitter Off,
native point history와 adaptive 0..0.5 weight, raw-frame history를 사용한다. Resolved feedback,
clipping, dilation, luma 근사 선택식은 추가하지 않는다.

⑤에는 선택을 위한 edge detection이 필요하다. 따라서 edge 검출 자체가 없는 ③과 pass
수가 같다고 주장하지 않는다. 기존 ⑤ 대비 추가 render/copy pass는 없으며 stencil clear와
raw MRT store 비용은 전체 AA에 포함한다. Camera velocity 생성 및 raw history 준비는
기존 입력 준비 단계로 유지된다. 화면 전체 렌더링까지 edge에 한정했다는 뜻은 아니다.

## 채택 조건

- 최종 native RG edge와 coverage 출력 및 passing samples가 모두 동일.
- PSInvocations를 전체 화면 mask 경로와 별도로 기록.
- 모든 nonedge final은 raw current, selected final은 같은 Off full resolve와 일치.
- Raw current와 실제 AA-Off, 기존 지터 Off ⑤, native ①·②·④ hash bridge 및 진단 Off repeat.
- 두 장면 각각 240 frame + 반복/controls, 초기/후반 정지 안정성.
- 성능에는 query/coverage/image readback을 끄고 300 warmup, 4,800 frame×4회 교차 순서 사용.
- 같은 executable의 capture gate가 통과하기 전에는 benchmark runner가 실행을 거부한다.
- Raw RGBA/velocity probe 및 ⑤/⑥ native RG edge 동일성도 benchmark 전에 확인한다.

③과 spatial filtering 자체를 뺀 차이, ④와 spatial 유무 차이를 temporal 최적화 효과로
계산하지 않는다. 같은 raw 입력과 edge 검출을 사용하는 full-Off control도 함께 비교한다.
⑥에서 발견한 stale stencil에 의한 2차 spatial 비용 문제는 ⑤에 그 pass가 없으므로 해당하지
않는다. ⑥의 공간 효과 분리 matrix를 ⑤에 억지로 적용하지 않는다.

공식 근거:
- [earlydepthstencil](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/sm5-attributes-earlydepthstencil)
- [Depth/stencil 및 MRT](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-depth-stencil)
- [PSInvocations](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_query_data_pipeline_statistics)

## 재현 순서

`Tools/SMAA/build_baseline.py`로 Release x64를 빌드하고
`Tools/SMAA/audit_first_edge_stencil.py`로 원본 보존과 shader를 확인한다. 각 장면에서
`run_first_edge_stencil.ps1 -Phase Capture -Scene bistro|minecraft`를 clean process로
실행하고 receipt의 결과 CSV를 `analyze_first_edge_stencil.py --phase Capture`에 전달한다.
`verify_first_edge_stencil_inputs.py --scene ...`가 입력과 ⑥ mask bridge를 검증한다.
그 다음에만 `run_first_edge_stencil.ps1 -Phase Benchmark -Scene ...`를 실행하고
동일 분석기의 `--phase Benchmark`로 결과를 확인한다. `report_first_edge_stencil.py`는
검증된 두 장면 JSON을 읽어 보고서를 생성한다.

원시 capture는 D:/SMAAResearchCaptures의 report별 하위 폴더에, 원시 CSV는 AutoBench에
보존했다. 다른 환경에서 재현하려면 분석기에 명시된 기존 기준선과 ⑤/⑥ 캡처도 필요하다.
기존 receipt를 덮어쓰지 않고 독립 실행에는 `-Receipt`를 새 경로로 지정한다.
