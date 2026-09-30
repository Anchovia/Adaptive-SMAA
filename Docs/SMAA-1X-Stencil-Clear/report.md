# 원본 SMAA 1X: stencil 초기화 단독 비교 결과

**현재 프로젝트의 초기화 누락을 복원한 비교다. SMAA 알고리즘 자체의 새로운 최적화가 아니다.**

SMAA 저자의 공식 DX10 데모는 매 프레임 `clearRenderTargets`에서 `mainDS` stencil을 0으로
초기화하고, 같은 자원을 SMAA 1X에 전달한다. 반면 프로젝트 wrapper는 전용 depth/stencil을
만든 뒤 기존 1X 경로에서 초기화하지 않았다. 원본 core의 `go()` 안에 clear가 없다는 것만으로
공식 데모에도 clear가 없다고 해석하면 안 된다.
같은 누락은 저장소 최초 원본 import `ee0020d`에도 있었다. 이후 temporal 선택 구현에서
새로 생긴 누락은 아니지만, SMAA 저자 구현 전체의 문제로 일반화할 수 없다.

- 공식 commit: `71c806a838bdd7d517df19192a20f0c61b3ca29d`.
- [공식 초기화](https://github.com/iryoku/smaa/blob/71c806a838bdd7d517df19192a20f0c61b3ca29d/Demo/DX10/Code/Demo.cpp#L589),
  [1X 호출](https://github.com/iryoku/smaa/blob/71c806a838bdd7d517df19192a20f0c61b3ca29d/Demo/DX10/Code/Demo.cpp#L685),
  [매 프레임 호출부](https://github.com/iryoku/smaa/blob/71c806a838bdd7d517df19192a20f0c61b3ca29d/Demo/DX10/Code/Demo.cpp#L735).

## 독립 브랜치와 실제 변경

`experiment/smaa-1x-stencil-clear`는 검증된 공통 기준 `c51ca28`에서 직접 분기했다.
기존 SMAA core/셰이더 등 12개 파일은 hash가 같고, ⑤·⑥의 exact-edge discard, MRT,
temporal 선택은 가져오지 않았다. 실제 두 mode의 GPU 작업 차이는 1X 호출 전
`ClearDepthStencilView(..., D3D11_CLEAR_STENCIL, 1.0f, 0)` 한 가지다. 기본값은 Off다.
초기화는 공간 SMAA 실행 범위를 정하는 자원 관리이며 threshold, local contrast, 탐색 길이,
blending weight 또는 색상 계산을 변경하지 않는다. 첫 pass의 원래 discard도 그대로다.

## 출력과 품질

Bistro/Minecraft 각각 같은 240-frame 정지60/이동120/정지60 경로에서 기존/초기화/각 반복
4개 sequence를 캡처했다. 같은 frame index의 전체 RGB를 비교했으며 모두 temporal,
reprojection, jitter Off인 실제 SMAA 1X다. 각 mode는 자원을 새로 생성하고 준비 뒤 진행한다.

| 장면 | 기존↔초기화 불일치 / 240 | 반복 불일치 / 480 | 기존 1X 연결 불일치 / 240 | RGB 최대 차이 |
|---|---:|---:|---:|---:|
| bistro | 0 | 0 | 0 | 0 |
| minecraft | 0 | 0 | 0 | 0 |

두 장면 모두 초기/후기 정지 구간의 고유 RGB 영상 수가 1이다. 측정된 영상에서 품질 차이는
없다. 알고리즘 수식이 같다는 소스 근거와 이 유한한 경로의 pixel-exact 결과를 구분한다.
모든 GPU/해상도/장면에 대한 포괄적인 동일성 증명으로 확장하지 않는다.

기존 1X 캡처와 모든 RGB/index가 같으므로 같은 reference의 CGVQM-2 점수도 그대로 연결한다.
**CGVQM 모델을 이번에 재실행한 값이 아니다.** 픽셀 일치에 근거한 재사용이며 차이는 0이다.

| 장면 | 구간 | 기존 1X | 초기화 1X | 차이 |
|---|---|---:|---:|---:|
| bistro | moving | 96.062752 | 96.062752 | 0 |
| bistro | transition | 95.874573 | 95.874573 | 0 |
| minecraft | moving | 95.172501 | 95.172501 | 0 |
| minecraft | transition | 94.916374 | 94.916374 | 0 |

## 같은 실행에서 비교한 전체 SMAA GPU 시간

RTX 3060 Ti, DX11, Release x64, Ultra, 1920×1061, hidden, VSync Off.
장면별 독립 clean process, 30초 사전 실행, mode별 300 warm-up, 4,800 frame×6회.
정/역순을 교대하며 초기화 비용도 SMAA scope 안에 포함한다. PNG, 통계 query/readback Off.
각 반복은 같은 240-frame 경로를 20회 순회한다. 초기화하지 않은 mode의 stencil은
그 반복 안에서 누적되고, mode 사이에는 자원을 재생성한다. 이 수치는 해당 workload의 결과다.

| 장면 | 기존 ms | 초기화 ms | 감소율 | 기존 반복 평균 SD | 초기화 반복 평균 SD |
|---|---:|---:|---:|---:|---:|
| bistro | 0.141096 | 0.093481 | 33.746% | 0.000203 | 0.000159 |
| minecraft | 0.216874 | 0.160594 | 25.950% | 0.001488 | 0.000756 |

반복별 초기화−기존 변화율:

- bistro: -34.016%, -33.754%, -33.577%, -33.833%, -33.544%, -33.754%
- minecraft: -24.998%, -26.630%, -25.491%, -26.853%, -25.170%, -26.533%

전체 frame 간격은 CPU/GPU/Present/스케줄링을 포함한다. GPU WholeFrame timer가 아니다.
아래 FPS는 평균 frame 간격의 역수이며 SMAA scope의 역수를 게임 FPS로 쓰지 않는다.

| 장면 | 기존 wall ms | 초기화 wall ms | 변화율 | 기존 평균 FPS | 초기화 평균 FPS |
|---|---:|---:|---:|---:|---:|
| bistro | 2.948856 | 2.952661 | +0.129% | 339.11 | 338.68 |
| minecraft | 1.186935 | 1.156900 | -2.530% | 842.51 | 864.38 |

median/p95/p99, 프레임 표준편차와 느린 1% frame 간격에 대응하는 FPS는 각 benchmark JSON에 있다.
성능 실행에서는 기존 전체 SMAA GPU timer만 사용했으므로 개별 1·2·3차 pass 시간을 새로 측정했다고
표현하지 않는다.

## GPU 실행량 근거

성능과 별도인 capture에서 공간 3패스 전체의 D3D11 PSInvocations를 조회했다.
아래는 이동 구간 평균이며, 단독 2차 패스 횟수나 메모리 트랜잭션 수가 아니다.

| 장면 | 기존 spatial PSInvocations | 초기화 spatial PSInvocations | 변화율 |
|---|---:|---:|---:|
| bistro | 4596130.77 | 4129079.58 | -10.162% |
| minecraft | 5500060.68 | 4538066.92 | -17.491% |

기존 edge/weight texture는 매 프레임 0으로 초기화되지만 stencil의 과거 표시가 남으면
현재 edge가 없는 위치에서도 weight shader가 실행될 수 있다. 원본 weight 계산은 해당
위치에서 0을 반환하므로 결과가 같으면서 실행량만 늘어나는 현상을 설명한다.
이번 clear는 과거 표시 누적을 제거한다. 현재 local contrast 처리 후 final RG=0인 위치까지
모두 제거하는 exact-edge shader 변경은 수행하지 않았다.

## 기존 연구 수치에 미치는 영향

과거 원본 1X와 ⑥은 spatial 실행 조건이 같지 않았다. 따라서 기존 ⑥의 큰 전체 AA 절감률을
모두 temporal 선택 효과로 해석하지 않는다. 공간 조건을 맞춘 이전 full/selective 비교는
별도 자료이고, 이번 실험은 temporal이 없는 1X의 초기화 한 가지를 분리한 결과다.
기존 원시 자료/품질 검증은 보존하되, 공정한 후속 temporal 비교는 대응 기준선의 stencil
초기화 조건도 맞춰야 한다. 이번 브랜치에서 ②·④·⑤·⑥ 기준선을 일괄 변경하지 않았다.

## 재현과 보존

- [실험 설계](method.md), `source-audit.json`: 고정 소스, 공식 출처, 변경/불변 파일 hash.
- `*-capture.json`, `*-frames.csv`: 프레임별 RGB 일치, PSInvocations, 기존 1X 연결.
- `*-smoke.json`, `*-benchmark.json`: clean 실행 receipt, 원시 CSV/EXE hash, 반복 통계.
- 실행: `run_smaa_1x_stencil_clear.ps1 -Phase Capture|Smoke|Benchmark -Scene bistro|minecraft`.
- 검증: `analyze_smaa_1x_stencil_clear.py audit|Capture|Smoke|Benchmark --scene ...`.
- 보고서: `report_smaa_1x_stencil_clear.py`. PNG/EXE/원시 AutoBench는 Git에 넣지 않는다.
