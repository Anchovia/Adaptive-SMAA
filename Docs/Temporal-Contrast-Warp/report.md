# 동일 선택 결과를 보존한 warp 실행 측정

조건과 공식 근거는 [method.md](method.md), 최종 판정은 [conclusion.md](conclusion.md)를 따른다.

별도 실행에서 두 장면 각 6 mode×240 frame 출력 검사, 4 mode×4,800 frame×5회 성능 측정을 완료했다. 성능은 30초 미측정 렌더링과 각 mode 300-frame warmup을 거쳤다. 정방향/역방향 순서를 교차했고 PNG 저장과 이미지 분석을 성능 실행에서 분리했다.

## bistro

기존 control hash/새 output hash 불일치 0. 선택률 1.512189%, 별도 debug PS vote coverage 4.421425%.
Vote coverage는 debug PS의 값이며 실제 resolve의 hardware counter로 해석하지 않는다.

| Mode | SMAA ms | 원본 대비 | 기존 선택 대비 | Resolve ms | Resolve 원본 대비 |
|---|---:|---:|---:|---:|---:|
| O-T2X-R | 0.210667 | +0.000% | +4.512% | 0.033597 | +0.000% |
| ABL-Contrast-001-R | 0.201573 | -4.317% | +0.000% | 0.025127 | -25.210% |
| ABL-ScalarWeight-001-R | 0.211006 | +0.161% | +4.680% | 0.033834 | +0.705% |
| ABL-NvWarp-001-R | 0.202584 | -3.837% | +0.502% | 0.025666 | -23.607% |

| 반복 | Warp−원본 SMAA ms | Warp−기존 선택 SMAA ms | Warp−원본 resolve ms | Warp−기존 선택 resolve ms |
|---|---:|---:|---:|---:|
| 1 | -0.008108 | +0.002761 | -0.007884 | +0.000638 |
| 2 | -0.007511 | +0.000499 | -0.007951 | +0.000497 |
| 3 | -0.008444 | +0.000607 | -0.007931 | +0.000551 |
| 4 | -0.007706 | +0.000417 | -0.007947 | +0.000487 |
| 5 | -0.008649 | +0.000771 | -0.007943 | +0.000520 |

median, p95/p99, 반복 분산, 불변 spatial 및 WholeFrame/wall FPS는 results.json에 보존했다.

## minecraft

기존 control hash/새 output hash 불일치 0. 선택률 50.449044%, 별도 debug PS vote coverage 68.907796%.
Vote coverage는 debug PS의 값이며 실제 resolve의 hardware counter로 해석하지 않는다.

| Mode | SMAA ms | 원본 대비 | 기존 선택 대비 | Resolve ms | Resolve 원본 대비 |
|---|---:|---:|---:|---:|---:|
| O-T2X-R | 0.281753 | +0.000% | -1.272% | 0.034714 | +0.000% |
| ABL-Contrast-001-R | 0.285382 | +1.288% | +0.000% | 0.038741 | +11.599% |
| ABL-ScalarWeight-001-R | 0.282080 | +0.116% | -1.157% | 0.034897 | +0.526% |
| ABL-NvWarp-001-R | 0.286309 | +1.617% | +0.325% | 0.039427 | +13.575% |

| 반복 | Warp−원본 SMAA ms | Warp−기존 선택 SMAA ms | Warp−원본 resolve ms | Warp−기존 선택 resolve ms |
|---|---:|---:|---:|---:|
| 1 | +0.004680 | +0.003426 | +0.004739 | +0.000825 |
| 2 | +0.004916 | -0.000979 | +0.004632 | +0.000479 |
| 3 | +0.004284 | +0.000880 | +0.004725 | +0.000721 |
| 4 | +0.004973 | +0.000555 | +0.004702 | +0.000702 |
| 5 | +0.003930 | +0.000752 | +0.004764 | +0.000703 |

median, p95/p99, 반복 분산, 불변 spatial 및 WholeFrame/wall FPS는 results.json에 보존했다.
