# ⑰ 출력 보존 최적화: 중단 시점과 재개 절차 (2026-10-16 22:35 KST)

브랜치 `experiment/edge-history-color-blend-optimization`, 의존성: 정리 완료 커밋 `d2a6315`
(`tooling/edge-history-color-blend-cleanup`). 사용자 요청으로 일시 중단했다.
**성능 측정은 사용자가 허용할 때까지 실행하지 않는다**(게임 실행 중이라는 사용자 지시, 2026-10-16).

## 커밋 상태

| 커밋 | 내용 | 출력 검증 |
|---|---|---|
| `e785a43` | 진단용 pass별 GPU timer(기본 Off), paired harness `-smaaColorBlendOptimization{Capture,Profile,Smoke,Benchmark}` | — |
| `6b851df` | O1: SMAA DSV depth+stencil 동시 clear (기본 Off, ⑰ feedback 경로만) | 양 장면 240프레임 RGB가 ⑰와 같음 (`opt-a`) |
| `2827827` | O2: feedback neighborhood pass depth 비활성 (기본 Off) | 양 장면 240프레임 RGB가 ⑰와 같음 (`opt-a`) |
| 다음 커밋 | O3: history를 직접 표시하고 visible slot을 unbind (기본 Off). HLSL 무변경 | **미검증**: Bistro `opt-b` 캡처만 완료, Minecraft는 중단 |

O3는 neighborhood 3 MRT → 2 MRT, resolve 2 MRT → 1 MRT로 쓰기를 줄인다. 화면 RGB는 같아야 하지만
visible alpha가 resolve lerp alpha에서 spatial alpha로 바뀐다(PNG·화면에는 쓰이지 않음). 채택 여부는 사용자 결정 사항이다.
처음 시도한 단일 target 전용 shader 방식은 FXC 명령 순서가 달라 산술 동일성을 증명할 수 없어 폐기했다.

## 재개 순서

1. 실행 전 `CMAA2.exe` 0개 확인. 이 worktree binary는 `BF305959…`(O3 포함).
2. Bistro `opt-b` 검증:
   `COLOR_BLEND_RUNS=<c17-opt>/tmp/cleanup-runs.json python Tools/SMAA/verify_color_blend_optimization.py opt-b --reference after-a --record Docs/Edge-History-Source-Color-Blend/bistro-capture.json --scene bistro`
3. Minecraft `opt-b` 재캡처: `Tools/SMAA/run_color_blend_preservation.ps1 -Harness Optimization -Phase Capture -Scene minecraft -Label opt-b -RetryReason "first attempt stopped by user pause"` 후 같은 검증.
4. O3 원본 프레임 직접 검사(이동 f126~131, 전환 f178~183, 실패 주변 f124~133, 정지 f230).
5. **사용자 허용 후** 성능: 장면별 `Profile`(pass 분해, 진단) → `Smoke` → `Benchmark`(300 warm-up + 4,800 × 6, 정/역 교차),
   그리고 정리 전/후 binary ABBA(`c17-before` = `CA01DD…`, `c17-cleanup` = `47E69F…`, Preservation harness Benchmark).
6. 분석: `Tools/SMAA/analyze_color_blend_performance.py <reports>` (같은 실행의 ④·⑰ 대비 paired 변화율, t95).

## 예상(측정 전, 확정 아님)

기존 재측정표 기준으로 feedback 구조(⑩→⑪)가 Minecraft에서 약 +7.8%p, Bistro에서 약 +7.2%p의 AA 비용을 더했다.
O3는 그 쓰기 수를 ⑩ 수준으로 줄인다. O1·O2는 수 µs 이하로 예상한다. edge union(⑥→⑨, Minecraft 약 +4.6%p)은
출력 동일성을 보장하는 방법을 찾지 못했다.
