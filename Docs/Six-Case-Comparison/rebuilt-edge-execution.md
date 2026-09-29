# ⑤·⑥ 재구현 결과 — 첫 edge에서만 temporal 셰이더 실행

과거 전체 화면 mask-read ⑤·⑥의 채택은 철회한 상태로 보존한다. 새 ⑤·⑥은 검증된
공통 기준선 `c51ca28`에서 각각 독립 분기했다. ⑤는 raw 색상, ⑥은 원본 공간 SMAA
결과를 유지하고, 첫 pass의 최종 RG edge와 같은 stencil을 통과한 위치에만 원본
T2X-R 계산을 실행한다. ①~④ 기준선은 보존한다.

기존 검증은 선택 출력이 맞는지만 확인해 전체 화면 temporal shader 실행을 놓쳤다.
새 검증은 final RGB와 별도로 coverage MRT, stencil passing samples, PSInvocations,
컴파일된 early-depth 플래그와 edge texture load 부재를 확인한다. ⑤·⑥ 각각 두 장면
480 frame의 불일치가 0이며, 비선택 출력과 정지 안정성도 통과했다. ⑤/⑥의 edge도 같다.

주 실험은 jitter/area pattern Off, camera/depth reprojection, 확장 Off다. 원본 ④의
paired pattern On은 그대로다. 현재 렌더링/색상 준비 전체를 edge만 수행한다는 뜻은
아니며, temporal 실행 범위를 제한한 결과다. Native RG edge 전체를 사용하며 Intel의
non-dominant 선택식이나 TSCMAA 전체를 재현했다는 뜻이 아니다.

## 실행 수

1920×1061 화면은 2,037,120 pixel이다. 이전 full/mask의 temporal PSInvocations는
프레임당 2,037,120이었고, 새 ⑤·⑥은 다음과 같다. 물리 cache transaction 수가 아니다.

| 장면 | 평균 temporal PSInvocations | 화면 비율 |
|---|---:|---:|
| bistro | 52,696.90 | 2.5868% |
| minecraft | 353,513.96 | 17.3536% |

## 조건을 맞춘 full-screen 대조군 대비

RTX 3060 Ti, D3D11, 1920×1061 Ultra, hidden, VSync Off. 장면별 clean process,
300 warmup, 4,800 frame×4회 교차 순서, readback/query Off. 단위 ms.
각 행은 같은 실행 안의 비교이며 서로 다른 브랜치/실행의 시간을 빼서 계산하지 않았다.
⑤ 대조군은 raw 준비와 edge 검출 포함, ⑥ 대조군은 동일한 정확한 spatial stencil이다.
둘 다 pattern Off이며 full-screen 대조군에는 불필요한 visible MRT를 넣지 않았다.

| 구성 | 장면 | 대조 전체 AA | 선택 전체 AA | 전체 AA 변화 | temporal 변화 |
|---|---|---:|---:|---:|---:|
| ⑤ | bistro | 0.112980 | 0.098990 | -12.383% | -78.559% |
| ⑤ | minecraft | 0.114805 | 0.114498 | -0.267% | -34.105% |
| ⑥ | bistro | 0.158893 | 0.134902 | -15.099% | -78.427% |
| ⑥ | minecraft | 0.227456 | 0.218968 | -3.732% | -33.576% |

⑤에는 ③과 달리 edge detection이 필요하고 그 비용도 포함된다. 이 표의 ⑤ 대조군은
③ 자체가 아니다. ⑥에서는 원본 wrapper에 과거 edge stencil이 남아 불필요한 2차
공간 처리가 실행되는 것도 확인했다. 위 표는 공간 조건을 맞춘 결과이며 큰 전체 시간
차이를 모두 temporal 선택의 효과로 설명하지 않는다.

⑤의 Minecraft 전체 AA 차이 0.27%는 약 0.000306 ms로 매우 작다. Raw/MRT 준비 비용이
temporal 절감 대부분을 상쇄하므로 실질적으로 비슷한 수준으로 해석한다.

## 원본 ④를 포함한 동일 실행의 수치

아래 표에는 pattern 차이가 포함된다. ⑤는 spatial AA 생략, ⑥은 spatial stencil의
정리 효과도 포함하므로 순수한 temporal 선택 효과로 해석하지 않는다.

| 구성 | 장면 | ④ AA | 선택 AA | 변화 | ④ temporal | 선택 temporal | 변화 |
|---|---|---:|---:|---:|---:|---:|---:|
| ⑤ | bistro | 0.210149 | 0.098990 | -52.895% | 0.033221 | 0.007131 | -78.533% |
| ⑤ | minecraft | 0.283959 | 0.114498 | -59.678% | 0.034889 | 0.023062 | -33.898% |
| ⑥ | bistro | 0.208051 | 0.133725 | -35.725% | 0.033636 | 0.007269 | -78.390% |
| ⑥ | minecraft | 0.283972 | 0.218529 | -23.046% | 0.035395 | 0.023274 | -34.246% |

## 품질과 보존 범위

선택식/지터 Off 출력은 이전 Off 선택 구현과 byte-identical하다. 새 품질 향상을
주장하지 않으며 이번 실행에서 CGVQM 모델을 재실행하지 않았다. 이전 점수의 재사용은
이 출력 동일성에 근거한다. Jitter On 비선택 영역의 떨림을 해결한 새 supersampling
기법은 아니다. 기존 ①·③ CGVQM 미측정 및 최종 6-case 통합 측정은 그대로 남아 있다.

이 보고서는 두 독립 구현의 실행 범위와 성능 수정 결과다. 과거 [6-case 표](report.md)는
철회한 전체 화면 mask 경로의 역사 기록이며 새 구현의 성능표로 사용하지 않는다.
원시 capture/CSV, 실패 결과와 철회 기록은 삭제하지 않았다.

상세 구현·원시 결과 hash·반복 변동·제한사항:

- [⑤ 재구현 보고서](https://github.com/Anchovia/Adaptive-SMAA/blob/ba1761d6a79bbbd84f720fc097e24b726587472f/Docs/First-Edge-Temporal-Only-Stencil/report.md)
- [⑥ 재구현 보고서](https://github.com/Anchovia/Adaptive-SMAA/blob/53ff61dc71e0533461da886f6990dc443ea0b6ce/Docs/Spatial-First-Edge-Stencil/report.md)

재생성: `python Tools/SMAA/summarize_rebuilt_edge_execution.py --item5-commit ba1761d6a79bbbd84f720fc097e24b726587472f --item6-commit 53ff61dc71e0533461da886f6990dc443ea0b6ce`
