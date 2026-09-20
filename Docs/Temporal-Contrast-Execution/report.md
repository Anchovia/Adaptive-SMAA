# Temporal contrast 실행 비용 분리 결과

## 판단

기본 구현을 유지한다. 같은 선택 결과에서 structured branch는 기존 early-return 대비 두 장면 모두 resolve 평균 변화가 0.1% 미만이다. Flatten은 Minecraft resolve를 5.25%, 전체 SMAA를 0.59% 줄였으나 원본 T2X-R보다 전체 SMAA가 1.26% 느리며, Bistro에서는 기존 선택 대비 resolve가 41.77% 증가했다. 범용 개선으로 채택할 근거가 없다.

SM5와 explicit LOD0 자체의 resolve 차이는 0.000024 ms 이내다. 반면 all-selected 대비 판정/분기 경로는 LOD0 control보다 Bistro 0.010163 ms, Minecraft 0.009499 ms 비싸다. Minecraft의 선택 생략은 그 경로에서 0.005472 ms를 줄여 추가 비용을 상쇄하지 못했다. 판정 연산과 조건부 texture 접근의 의존 관계가 주요 조사 대상이며, divergence와 cache/latency 중 지배적인 hardware 원인은 아직 분리하지 않았다.

다음 설계는 판정 비용 및 current→판정→velocity→history 의존 관계를 낮추는 방향을 검토한다. 선택 기준/공간적 판단 단위를 바꾸는 경우 이번 동일 출력 최적화와 분리하여 mask·깜빡임·고스팅을 다시 검증한다. 별도 pass/목록 생성이나 scene별 임의 전환을 기본 해법으로 도입하지 않는다.

공식 근거와 조건은 [method.md](method.md), DXBC 검증은 [shader-validation.json](shader-validation.json)을 따른다.
픽셀 선택률은 GPU 실행 명령 감소율이 아니다. DXBC와 GPU timestamp로 원인을 좁혔으며 hardware warp/cache/stall counter는 측정하지 않았다.

## bistro

240 frame ×11 mode capture, 기존 5 mode hash bridge와 모든 대조군 출력 hash mismatch 0. 선택률 1.512189%.

| Mode | SMAA ms | native 대비 | Resolve ms | 기존 선택 대비 resolve |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.209130 | +0.000% | 0.033063 | +33.875% |
| ABL-NativeSM5-R | 0.209425 | +0.141% | 0.033069 | +33.902% |
| ABL-Lod-R | 0.209621 | +0.235% | 0.033087 | +33.974% |
| ABL-CurrentFirst-R | 0.210081 | +0.455% | 0.033135 | +34.168% |
| ABL-Contrast-All-R | 0.220354 | +5.367% | 0.043250 | +75.126% |
| ABL-Contrast-001-R | 0.201742 | -3.533% | 0.024697 | +0.000% |
| ABL-Structured-001-R | 0.201861 | -3.476% | 0.024717 | +0.082% |
| ABL-Flatten-001-R | 0.212359 | +1.544% | 0.035013 | +41.771% |
| ABL-PrefetchVelocity-001-R | 0.201921 | -3.447% | 0.024704 | +0.031% |

4,800 frame ×3회 평균. 각 반복의 값, p95/p99, median, 표준편차, WholeFrame 및 wall FPS/1% low는 results.json에 보존한다.

| Resolve 대조 (앞−뒤) | 평균 차이 ms |
|---|---:|
| SM5−원본 | +0.000007 |
| LOD0−SM5 | +0.000018 |
| gradient/branch all−LOD0 | +0.010163 |
| 기존 선택−all | -0.018554 |
| structured−기존 선택 | +0.000020 |
| flatten−기존 선택 | +0.010316 |
| 동일 DXBC: CurrentFirst−LOD0 | +0.000048 |
| 동일 DXBC: Prefetch−Structured | -0.000012 |

gradient/branch 대조는 판정 연산과 그에 따른 실행 의존 관계를 함께 포함한다. 분기 하드웨어 비용만의 분리는 아니다.

| 화면 tile | 혼합 tile 비율 | 선택 pixel이 있는 tile 비율 |
|---|---:|---:|
| 2x2 | 0.607% | 1.750% |
| 4x8 | 4.363% | 4.440% |
| 8x4 | 4.608% | 4.673% |

부분 bottom tile 제외. 화면상의 분포 대용값이며 실제 warp 배치/분기 효율이 아니다.

## minecraft

240 frame ×11 mode capture, 기존 5 mode hash bridge와 모든 대조군 출력 hash mismatch 0. 선택률 50.449044%.

| Mode | SMAA ms | native 대비 | Resolve ms | 기존 선택 대비 resolve |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.282982 | +0.000% | 0.034780 | -10.437% |
| ABL-NativeSM5-R | 0.284091 | +0.392% | 0.034804 | -10.376% |
| ABL-Lod-R | 0.283913 | +0.329% | 0.034806 | -10.371% |
| ABL-CurrentFirst-R | 0.284254 | +0.450% | 0.034818 | -10.340% |
| ABL-Contrast-All-R | 0.293578 | +3.744% | 0.044304 | +14.090% |
| ABL-Contrast-001-R | 0.288243 | +1.859% | 0.038833 | +0.000% |
| ABL-Structured-001-R | 0.288105 | +1.810% | 0.038798 | -0.089% |
| ABL-Flatten-001-R | 0.286555 | +1.263% | 0.036794 | -5.250% |
| ABL-PrefetchVelocity-001-R | 0.288076 | +1.800% | 0.038823 | -0.026% |

4,800 frame ×3회 평균. 각 반복의 값, p95/p99, median, 표준편차, WholeFrame 및 wall FPS/1% low는 results.json에 보존한다.

| Resolve 대조 (앞−뒤) | 평균 차이 ms |
|---|---:|
| SM5−원본 | +0.000024 |
| LOD0−SM5 | +0.000002 |
| gradient/branch all−LOD0 | +0.009499 |
| 기존 선택−all | -0.005472 |
| structured−기존 선택 | -0.000035 |
| flatten−기존 선택 | -0.002039 |
| 동일 DXBC: CurrentFirst−LOD0 | +0.000012 |
| 동일 DXBC: Prefetch−Structured | +0.000024 |

gradient/branch 대조는 판정 연산과 그에 따른 실행 의존 관계를 함께 포함한다. 분기 하드웨어 비용만의 분리는 아니다.

| 화면 tile | 혼합 tile 비율 | 선택 pixel이 있는 tile 비율 |
|---|---:|---:|
| 2x2 | 9.783% | 53.800% |
| 4x8 | 58.382% | 68.871% |
| 8x4 | 56.244% | 67.623% |

부분 bottom tile 제외. 화면상의 분포 대용값이며 실제 warp 배치/분기 효율이 아니다.

## 해석의 범위

- 첫 native 반복의 spatial 시간이 후속 반복보다 낮았다. 모든 반복을 유지했다. 전체 AA의 작은 차이는 이 변동을 포함하며, 불변 spatial 코드의 시간 차이를 알고리즘 개선으로 해석하지 않는다.
- Minecraft flatten의 기존 선택 대비 resolve/전체 SMAA 감소와 원본 대비 열세는 세 반복 모두 같은 방향이었다. 통계적 유의성 또는 다른 GPU에서의 재현을 주장하지 않는다.
- SM5와 explicit LOD control은 native와 동일 출력이다. 실제 측정 차이로만 비용을 해석한다.
- CurrentFirst/Lod와 PrefetchVelocity/Structured는 각 쌍이 동일 DXBC다. 쌍의 timing 차이는 소스 순서 최적화 효과가 아니다.
- Flatten은 history/velocity를 fullscreen으로 읽는다. 빨라지더라도 선택적 sample 절약에 성공한 것은 아니다.
- 출력 동일성이 확인된 구현들은 기존 대비 선택 방식의 품질도 동일하다. 정지 후 두 프레임 교대 깜빡임은 남아 있으며 고스팅 개선을 새로 입증하지 않는다.
- 단일 GPU, 두 장면, 세 반복 결과다. 기본 mode 자동 전환이나 scene별 임의 정책은 추가하지 않았다.
