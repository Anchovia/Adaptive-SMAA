# 원본 대비 속도 검증: 작은 resolve 비용과 전체 시간의 순서 영향

**ScalarWeight의 원본 SMAA T2X-R 대비 가속은 확인되지 않았다.** 전체 SMAA 평균 차이는 작지만 실행 순서에 따라 방향이 바뀌었다. 반면 temporal resolve는 Bistro/Minecraft 각각 6개 독립 실행 쌍 전부에서 ScalarWeight가 느렸다. 이전의 약 0.1% 전체 시간 차이를 확정적인 알고리즘 비용이나 동등성으로 해석해서는 안 된다.

## 측정 결과

RTX 3060 Ti, DX11, Original SMAA Ultra, camera/depth reprojection, 1920×1061, hidden, Vsync Off다. 장면마다 별도 프로세스 6개를 실행했으며 각 프로세스에 원본(A)과 ScalarWeight(B) 두 mode만 포함했다. AB/BA 각각 3회, 공통 원본 30초 예열, mode마다 300-frame warmup과 4,800-frame 측정이다. 전체 12개 benchmark 및 사전 smoke 4개가 정상 종료/보고서 검증을 통과했다. 본 측정의 제외 실행은 없다.

| 지표 | Bistro 원본 → ScalarWeight | Minecraft 원본 → ScalarWeight |
|---|---:|---:|
| 전체 SMAA 평균 | 0.208664 → 0.208947 ms (+0.136%) | 0.283225 → 0.284136 ms (+0.321%) |
| Temporal resolve 평균 | 0.033418 → 0.033688 ms (+0.809%) | 0.035078 → 0.035236 ms (+0.451%) |
| Resolve 추가 시간 | +0.270 µs | +0.158 µs |
| 전체 SMAA가 느린 실행 | 3/6 | 3/6 |
| Resolve가 느린 실행 | 6/6 | 6/6 |

전체 SMAA의 B−A paired 95% 구간은 Bistro `[-0.001128, +0.001694] ms`, Minecraft `[-0.000829, +0.002650] ms`로 0을 포함한다. Resolve 구간은 각각 `[+0.000221, +0.000319] ms`, `[+0.000085, +0.000232] ms`였다. 단일 GPU/세션, 작은 표본 및 순차 실행의 한계가 있으며, 여러 보조 지표의 검정을 독립적인 성공 증거로 세지 않는다. 사전 동등성 허용 폭을 정하지 않았으므로 **통계적 동등성 확인**이라는 표현은 사용하지 않는다.

## 실행 순서가 보여준 것

두 장면 모두 AB에서는 ScalarWeight의 전체 SMAA가 3/3 느렸고, BA에서는 3/3 빨랐다. 즉 이번 전체 시간은 두 번째로 측정한 mode가 느려지는 방향이었다. 변경하지 않은 Spatial scope에도 같은 방향의 순서 차이가 나타났다.

| B−A 평균 | Bistro AB / BA | Minecraft AB / BA |
|---|---:|---:|
| 전체 SMAA | +0.001440 / −0.000874 ms | +0.002342 / −0.000522 ms |
| 미변경 Spatial | +0.001106 / −0.001104 ms | +0.002174 / −0.000692 ms |
| Resolve | +0.000293 / +0.000247 ms | +0.000155 / +0.000162 ms |

전체 차이에는 순서에 연결된 변동이 섞여 있다. GPU 클럭·온도·캐시·하드웨어 stall counter를 계측한 실험은 아니므로 원인을 특정하지 않는다. Spatial 값을 빼서 보정한 전체 시간을 정식 성능 수치로 만들지도 않는다. Resolve의 작은 증가가 양쪽 순서에서 유지된다는 사실은 별도로 기록할 수 있다.

## 구현 관점의 판단

ScalarWeight는 기존 픽셀별 luma 대비 선택과 선택된 픽셀의 혼합 결과를 보존한다. 다만 모든 픽셀의 velocity/history를 읽은 뒤 비후보의 history weight만 0으로 만든다. 따라서 후보 감소가 texture 접근 감소로 이어지지 않으며, 선택 계산도 남는다. 기존 분기 구현의 Minecraft 손해를 줄였지만, 원본 대비 연산 생략의 이점을 확보한 구현은 아니다. 이 코드 구조와 관측 결과가 부합하더라도 정확한 GPU 병목의 하드웨어 원인을 증명한 것은 아니다.

현재까지 같은 선택식과 출력을 유지하면서 검증한 소스 순서 변경, 분기 형태, Load 접근, scalar 혼합, 공식 NVAPI warp 투표 중 **두 장면 모두에서 원본보다 빠른 공통 구현은 없다**. 현재 DX11 구현 범위의 가속 목표는 미달이다. 모든 GPU에서 이 아이디어가 불가능하다는 결론으로 확대하지 않는다.

이번 작업은 속도 검증으로 마무리한다. 기본 렌더링 설정을 바꾸지 않고 ScalarWeight와 다른 실험 경로를 대조 옵션으로 보존한다. 이후 품질상 이점의 채택 여부는 별도 판단이며 이번 결과로 품질 우위를 주장하지 않는다. 후보 확장이나 다른 선택 기준을 이번 최적화의 성과로 섞지 않는다.

## 재현과 변경 범위

- 측정 코드: `e06d955`, 기준 렌더링 코드: `ea2bff1`.
- 실행파일 SHA-256: `1E8D968117CE2364124AA12732E06E6D05CD1707F53678022928410B38A21172`.
- `Projects/CMAA2/SMAA` 및 `Modules/Rendering/DirectX`의 기준 commit 대비 diff는 없다. 변경은 측정 순서·공통 예열·기록·분석 도구에 한정한다.
- 이전 [Cost 검증](../Temporal-Contrast-Cost/conclusion.md)과 [Warp 검증](../Temporal-Contrast-Warp/conclusion.md)의 ScalarWeight 대 기존 선택 출력 hash 일치를 인용한다. 원본 T2X-R과 동일한 출력이라는 의미는 아니다. 이번에 새 품질 캡처는 수행하지 않았다.
- [사전 방법과 초기 smoke 실패](method.md), [개별 pair·분포·원시 보고서 hash](results.json), [전체 표](report.md).
- 최초 실패 smoke `20260921_022133`은 새 보고 문구 처리 오류로 측정 전에 종료됐고 제외했다. 해당 호출 수정 후 동일 실행파일로 4개 smoke와 12개 본 측정을 모두 완료했다.

실행 예: `Tools/SMAA/run_temporal_pair.ps1 -Phase Benchmark -Scene bistro -Order AB -PairIndex 0 -Receipt tmp/new-pair-runs.json`. 재현 시 method.md의 전체 순서를 따르고, 완료된 receipt의 index를 덮어쓰지 않는다. 분석: `Tools/SMAA/analyze_temporal_pair.py --receipts tmp/temporal-pair-runs.json`.
