# 픽셀별 luma 선택의 비용 최적화 결과

선택 기준과 후보 픽셀을 유지하고 temporal PS의 계산/접근 비용만 변경했다. 후보 확장, 새 선택 단위, 추가 pass 및 metadata 접근은 없다. 조건과 공식 근거는 [method.md](method.md)를 따른다.

각 장면 smoke/capture/benchmark 독립 실행. 성능은 300 warmup, 4,800 frame×3회, 품질 저장/분석과 분리했다. 원본 shader 8 variant 불변과 새 shader 14 variant 검사를 통과했다.

기존 early-return은 선택되지 않은 픽셀의 velocity/history 읽기를 생략한다. ScalarWeight 계열은 모든 픽셀을 읽되 비후보 weight만 0으로 하여 같은 화면을 만든다. 실제 fetch 수 감소와 같은 품질의 실행 시간 감소를 구별한다.

## bistro

11 mode×240 frame. 선택률 1.512189%. 기존 원본/선택/mask hash bridge 불일치 0.

| Mode | 변경 픽셀 합계 | 최대 채널 오차 /255 | 비후보 변경 | PNG 불일치 frame |
|---|---:|---:|---:|---:|
| ABL-Flatten-001-R | 0 | 0 | 0 | 0 |
| ABL-ScalarWeight-001-R | 0 | 0 | 0 | 0 |
| ABL-ScalarReassociated-001-R | 0 | 0 | 0 | 0 |
| ABL-BranchReassociated-001-R | 0 | 0 | 0 | 0 |
| ABL-HistoryLoad-001-R | 2091 | 100 | 0 | 120 |
| ABL-SelectorAny-001-R | 0 | 0 | 0 | 0 |
| ABL-FixedThreshold-001-R | 0 | 0 | 0 | 0 |
| ABL-ScalarFixedThreshold-001-R | 0 | 0 | 0 | 0 |

변경 픽셀은 240 frame에 걸친 합계이며 같은 위치가 여러 frame에서 달라지면 각각 센다. HistoryLoad 및 재배열 산술은 비동일 출력을 별도로 표시하고 동일 품질 최적화로 채택하지 않는다.

| Mode | 두 장면 byte-exact | SMAA ms | 원본 대비 | 기존 선택 대비 | Resolve ms | Resolve 반복 표준편차 ms |
|---|---|---:|---:|---:|---:|---:|
| O-T2X-R | control | 0.210338 | +0.000% | +3.994% | 0.033210 | 0.000127 |
| ABL-Contrast-001-R | control | 0.202260 | -3.841% | +0.000% | 0.024762 | 0.000056 |
| ABL-Flatten-001-R | yes | 0.213100 | +1.313% | +5.359% | 0.035302 | 0.000069 |
| ABL-ScalarWeight-001-R | yes | 0.211351 | +0.481% | +4.495% | 0.033486 | 0.000032 |
| ABL-ScalarReassociated-001-R | no | 0.211451 | +0.529% | +4.544% | 0.033571 | 0.000033 |
| ABL-BranchReassociated-001-R | no | 0.202706 | -3.629% | +0.221% | 0.024823 | 0.000022 |
| ABL-HistoryLoad-001-R | no | 0.202866 | -3.553% | +0.300% | 0.025028 | 0.000026 |
| ABL-SelectorAny-001-R | yes | 0.202714 | -3.625% | +0.225% | 0.024800 | 0.000008 |
| ABL-FixedThreshold-001-R | yes | 0.202690 | -3.636% | +0.212% | 0.024828 | 0.000018 |
| ABL-ScalarFixedThreshold-001-R | yes | 0.211528 | +0.565% | +4.582% | 0.033542 | 0.000013 |

| Mode | Resolve 반복 ms | SMAA 원본 대비 반복 차이 ms |
|---|---|---|
| ABL-Contrast-001-R | 0.024707, 0.024820, 0.024761 | -0.006777, -0.008645, -0.008815 |
| ABL-Flatten-001-R | 0.035222, 0.035340, 0.035344 | +0.004251, +0.001972, +0.002061 |
| ABL-ScalarWeight-001-R | 0.033449, 0.033509, 0.033498 | +0.002627, +0.000233, +0.000177 |
| ABL-SelectorAny-001-R | 0.024793, 0.024809, 0.024799 | -0.005583, -0.008477, -0.008813 |
| ABL-FixedThreshold-001-R | 0.024832, 0.024809, 0.024844 | -0.005406, -0.008732, -0.008808 |
| ABL-ScalarFixedThreshold-001-R | 0.033555, 0.033529, 0.033543 | +0.003337, +0.000157, +0.000074 |

불변 spatial 시간, p95/p99, wall FPS 및 전체 반복 분포는 results.json에 보존했다. 원본보다 작은 시간 차이만으로 개선을 확정하지 않으며 first-mode 초기 변동을 함께 본다.

## minecraft

11 mode×240 frame. 선택률 50.449044%. 기존 원본/선택/mask hash bridge 불일치 0.

| Mode | 변경 픽셀 합계 | 최대 채널 오차 /255 | 비후보 변경 | PNG 불일치 frame |
|---|---:|---:|---:|---:|
| ABL-Flatten-001-R | 0 | 0 | 0 | 0 |
| ABL-ScalarWeight-001-R | 0 | 0 | 0 | 0 |
| ABL-ScalarReassociated-001-R | 9 | 1 | 0 | 8 |
| ABL-BranchReassociated-001-R | 9 | 1 | 0 | 8 |
| ABL-HistoryLoad-001-R | 71328 | 156 | 0 | 120 |
| ABL-SelectorAny-001-R | 0 | 0 | 0 | 0 |
| ABL-FixedThreshold-001-R | 0 | 0 | 0 | 0 |
| ABL-ScalarFixedThreshold-001-R | 0 | 0 | 0 | 0 |

변경 픽셀은 240 frame에 걸친 합계이며 같은 위치가 여러 frame에서 달라지면 각각 센다. HistoryLoad 및 재배열 산술은 비동일 출력을 별도로 표시하고 동일 품질 최적화로 채택하지 않는다.

| Mode | 두 장면 byte-exact | SMAA ms | 원본 대비 | 기존 선택 대비 | Resolve ms | Resolve 반복 표준편차 ms |
|---|---|---:|---:|---:|---:|---:|
| O-T2X-R | control | 0.284025 | +0.000% | -1.527% | 0.035196 | 0.000113 |
| ABL-Contrast-001-R | control | 0.288430 | +1.551% | +0.000% | 0.038879 | 0.000117 |
| ABL-Flatten-001-R | yes | 0.286594 | +0.905% | -0.636% | 0.036956 | 0.000088 |
| ABL-ScalarWeight-001-R | yes | 0.285517 | +0.525% | -1.010% | 0.035427 | 0.000054 |
| ABL-ScalarReassociated-001-R | no | 0.285526 | +0.528% | -1.007% | 0.035463 | 0.000042 |
| ABL-BranchReassociated-001-R | no | 0.288955 | +1.736% | +0.182% | 0.038895 | 0.000059 |
| ABL-HistoryLoad-001-R | no | 0.289444 | +1.908% | +0.352% | 0.039315 | 0.000111 |
| ABL-SelectorAny-001-R | yes | 0.289170 | +1.812% | +0.257% | 0.038917 | 0.000137 |
| ABL-FixedThreshold-001-R | yes | 0.289057 | +1.772% | +0.218% | 0.038923 | 0.000084 |
| ABL-ScalarFixedThreshold-001-R | yes | 0.285994 | +0.693% | -0.845% | 0.035465 | 0.000078 |

| Mode | Resolve 반복 ms | SMAA 원본 대비 반복 차이 ms |
|---|---|---|
| ABL-Contrast-001-R | 0.038761, 0.038882, 0.038995 | +0.006045, +0.002927, +0.004242 |
| ABL-Flatten-001-R | 0.036856, 0.037017, 0.036996 | +0.003928, +0.001868, +0.001912 |
| ABL-ScalarWeight-001-R | 0.035366, 0.035445, 0.035469 | +0.003946, -0.000546, +0.001077 |
| ABL-SelectorAny-001-R | 0.038893, 0.038793, 0.039064 | +0.007956, +0.002253, +0.005228 |
| ABL-FixedThreshold-001-R | 0.038826, 0.038973, 0.038970 | +0.007273, +0.003299, +0.004525 |
| ABL-ScalarFixedThreshold-001-R | 0.035400, 0.035443, 0.035552 | +0.004799, -0.000691, +0.001799 |

불변 spatial 시간, p95/p99, wall FPS 및 전체 반복 분포는 results.json에 보존했다. 원본보다 작은 시간 차이만으로 개선을 확정하지 않으며 first-mode 초기 변동을 함께 본다.

## 검토에서 제외한 중복과 범위

- 기존 current-first/velocity-prefetch 소스 재배치는 동일 DXBC이거나 sample이 branch 안으로 이동했으므로 반복하지 않았다. 이전 Execution/Dependency 보고서의 근거를 유지한다.
- 기존 branch↔flatten 비교는 control로만 재사용했다. 이번 새 변경은 RGBA 결과 선택 대신 scalar weight 제어와 별도의 산술/읽기/선택식 비용 변경이다.
- ScalarMultiply probe는 ScalarWeight보다 같은 경로에 multiply 명령을 하나 더 추가했다. 더 짧은 scalar weight masking을 GPU 후보로 선택했다.
- 기존 선택/ScalarWeight/ScalarFixedThreshold의 /O1,/O2,/O3 instruction stream은 각각 모두 동일했다. compiler-levels.json 참조. 최적화 수준 변경을 새 GPU 개선으로 세지 않았다.
- DXBC slot 감소는 하드웨어 시간 감소가 아니다. FP 산술 재배치와 history Load는 출력 검증을 통해 별도 판정한다.
- Nvidia warp/cache/stall counter는 이전 권한 제한으로 미측정이다. 이 결과로 지배적인 하드웨어 원인을 확정하거나 모든 가능한 구현의 불가능을 증명했다고 표현하지 않는다.
- 다른 selector, 후보 확장, 추가 pass, 다른 graphics API로 연구 질문을 바꾸지 않는다.
