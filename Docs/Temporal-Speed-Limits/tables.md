# Speed-only 측정표

전체 AA와 Resolve의 단위는 ms다. 퍼센트는 같은 실행의 비교군 대비다. Screen의 3회와 최종 확인의 4회는 한 프로세스 안의 교차 반복이며 독립 세션 표본이 아니다.

## bistro / ScreenBenchmark

| Mode | 전체 AA | Resolve | AA vs 기존 선택 | Resolve vs 기존 선택 | AA vs 원본 |
|---|---:|---:|---:|---:|---:|
| O-T2X-R | 0.209716338 | 0.033501582 | -0.996% | -2.619% | +0.000% |
| ABL-ScalarPairedDeJitter-001-R | 0.211825351 | 0.034402560 | +0.000% | +0.000% | +1.006% |
| ABL-SpeedBranch-R | 0.201428338 | 0.024401635 | -4.908% | -29.070% | -3.952% |
| ABL-SpeedUniformScalar-R | 0.211669333 | 0.034393316 | -0.074% | -0.027% | +0.931% |
| ABL-SpeedUniformBranch-R | 0.201328640 | 0.024328818 | -4.955% | -29.282% | -4.000% |
| ABL-SpeedUniformWarp-R | 0.201872498 | 0.024811804 | -4.699% | -27.878% | -3.740% |
| ABL-SpeedPhaseScalar-R | 0.211402951 | 0.034373120 | -0.199% | -0.086% | +0.804% |

## bistro / GroupScreenBenchmark

| Mode | 전체 AA | Resolve | AA vs 기존 선택 | Resolve vs 기존 선택 | AA vs 원본 |
|---|---:|---:|---:|---:|---:|
| O-T2X-R | 0.207393707 | 0.033475271 | -1.038% | -3.023% | +0.000% |
| ABL-ScalarPairedDeJitter-001-R | 0.209568711 | 0.034518613 | +0.000% | +0.000% | +1.049% |
| ABL-SpeedPhaseScalar-R | 0.209616355 | 0.034519751 | +0.023% | +0.003% | +1.072% |
| ABL-SpeedGroup4-R | 0.199923627 | 0.024957440 | -4.602% | -27.699% | -3.602% |
| ABL-SpeedGroup8-R | 0.199754667 | 0.025031538 | -4.683% | -27.484% | -3.683% |
| ABL-SpeedGroup16-R | 0.200053902 | 0.025121991 | -4.540% | -27.222% | -3.539% |
| ABL-SpeedDensity8-R | 0.199956622 | 0.025047751 | -4.587% | -27.437% | -3.586% |
| ABL-SpeedDensity16-R | 0.199792356 | 0.025019875 | -4.665% | -27.518% | -3.665% |

## bistro / Benchmark

| Mode | 전체 AA | Resolve | AA vs 기존 선택 | Resolve vs 기존 선택 | AA vs 원본 |
|---|---:|---:|---:|---:|---:|
| O-T2X-R | 0.210604267 | 0.033417600 | -0.596% | -2.683% | +0.000% |
| ABL-ScalarPairedDeJitter-001-R | 0.211866400 | 0.034339040 | +0.000% | +0.000% | +0.599% |
| ABL-SpeedUniformScalar-R | 0.211895573 | 0.034305013 | +0.014% | -0.099% | +0.613% |
| ABL-SpeedPhaseScalar-R | 0.212006827 | 0.034325333 | +0.066% | -0.040% | +0.666% |

### 최종 반복 차이와 실행 순서

| 비교 | 지표 | 평균 차이 µs | 느린 반복 | 정순 차이 µs | 역순 차이 µs | 차이의 표준편차 µs |
|---|---|---:|---:|---:|---:|---:|
| ABL-ScalarPairedDeJitter-001-R − O-T2X-R | SMAA | +1.262133 | 4/4 | +1.676906 | +0.847360 | 0.705948 |
| ABL-ScalarPairedDeJitter-001-R − O-T2X-R | Resolve | +0.921440 | 4/4 | +1.135574 | +0.707306 | 0.247339 |
| ABL-ScalarPairedDeJitter-001-R − O-T2X-R | Spatial | +0.326560 | 3/4 | +0.507413 | +0.145707 | 0.556214 |
| ABL-ScalarPairedDeJitter-001-R − O-T2X-R | WholeFrame | +8.336301 | 3/4 | +8.663124 | +8.009479 | 13.118689 |
| ABL-SpeedUniformScalar-R − ABL-ScalarPairedDeJitter-001-R | SMAA | +0.029174 | 3/4 | -0.070400 | +0.128747 | 0.153078 |
| ABL-SpeedUniformScalar-R − ABL-ScalarPairedDeJitter-001-R | Resolve | -0.034027 | 2/4 | -0.260374 | +0.192320 | 0.262218 |
| ABL-SpeedUniformScalar-R − ABL-ScalarPairedDeJitter-001-R | Spatial | +0.064960 | 2/4 | +0.212907 | -0.082986 | 0.188622 |
| ABL-SpeedUniformScalar-R − ABL-ScalarPairedDeJitter-001-R | WholeFrame | +0.133662 | 2/4 | -5.169680 | +5.437003 | 12.163628 |
| ABL-SpeedUniformScalar-R − O-T2X-R | SMAA | +1.291307 | 4/4 | +1.606507 | +0.976107 | 0.554049 |
| ABL-SpeedUniformScalar-R − O-T2X-R | Resolve | +0.887413 | 4/4 | +0.875200 | +0.899627 | 0.026203 |
| ABL-SpeedUniformScalar-R − O-T2X-R | Spatial | +0.391520 | 4/4 | +0.720320 | +0.062721 | 0.578906 |
| ABL-SpeedUniformScalar-R − O-T2X-R | WholeFrame | +8.469963 | 3/4 | +3.493444 | +13.446483 | 23.979506 |
| ABL-SpeedPhaseScalar-R − ABL-ScalarPairedDeJitter-001-R | SMAA | +0.140427 | 2/4 | +0.308160 | -0.027307 | 0.340611 |
| ABL-SpeedPhaseScalar-R − ABL-ScalarPairedDeJitter-001-R | Resolve | -0.013707 | 1/4 | +0.004480 | -0.031893 | 0.035857 |
| ABL-SpeedPhaseScalar-R − ABL-ScalarPairedDeJitter-001-R | Spatial | +0.141599 | 3/4 | +0.275946 | +0.007253 | 0.264745 |
| ABL-SpeedPhaseScalar-R − ABL-ScalarPairedDeJitter-001-R | WholeFrame | +2.848798 | 3/4 | +0.419294 | +5.278303 | 5.117317 |
| ABL-SpeedPhaseScalar-R − O-T2X-R | SMAA | +1.402560 | 4/4 | +1.985067 | +0.820054 | 1.039883 |
| ABL-SpeedPhaseScalar-R − O-T2X-R | Resolve | +0.907733 | 4/4 | +1.140053 | +0.675413 | 0.269430 |
| ABL-SpeedPhaseScalar-R − O-T2X-R | Spatial | +0.468160 | 3/4 | +0.783359 | +0.152960 | 0.810448 |
| ABL-SpeedPhaseScalar-R − O-T2X-R | WholeFrame | +11.185100 | 3/4 | +9.082417 | +13.287783 | 17.492952 |

각 run의 median, p95/p99, Wall FPS와 1% low는 같은 이름의 JSON에 저장했다.

## minecraft / ScreenBenchmark

| Mode | 전체 AA | Resolve | AA vs 기존 선택 | Resolve vs 기존 선택 | AA vs 원본 |
|---|---:|---:|---:|---:|---:|
| O-T2X-R | 0.284536320 | 0.034554453 | -0.987% | -2.725% | +0.000% |
| ABL-ScalarPairedDeJitter-001-R | 0.287373653 | 0.035522560 | +0.000% | +0.000% | +0.997% |
| ABL-SpeedBranch-R | 0.290265600 | 0.039067307 | +1.006% | +9.979% | +2.014% |
| ABL-SpeedUniformScalar-R | 0.287300978 | 0.035503644 | -0.025% | -0.053% | +0.972% |
| ABL-SpeedUniformBranch-R | 0.290281245 | 0.039008569 | +1.012% | +9.814% | +2.019% |
| ABL-SpeedUniformWarp-R | 0.291448462 | 0.039790507 | +1.418% | +12.015% | +2.429% |
| ABL-SpeedPhaseScalar-R | 0.287122631 | 0.035490844 | -0.087% | -0.089% | +0.909% |

## minecraft / GroupScreenBenchmark

| Mode | 전체 AA | Resolve | AA vs 기존 선택 | Resolve vs 기존 선택 | AA vs 원본 |
|---|---:|---:|---:|---:|---:|
| O-T2X-R | 0.281650916 | 0.034873031 | -0.749% | -2.488% | +0.000% |
| ABL-ScalarPairedDeJitter-001-R | 0.283776853 | 0.035762773 | +0.000% | +0.000% | +0.755% |
| ABL-SpeedPhaseScalar-R | 0.283663787 | 0.035750400 | -0.040% | -0.035% | +0.715% |
| ABL-SpeedGroup4-R | 0.287836018 | 0.039912533 | +1.430% | +11.604% | +2.196% |
| ABL-SpeedGroup8-R | 0.287899165 | 0.040033707 | +1.453% | +11.942% | +2.218% |
| ABL-SpeedGroup16-R | 0.288320427 | 0.040166684 | +1.601% | +12.314% | +2.368% |
| ABL-SpeedDensity8-R | 0.288026169 | 0.040247893 | +1.497% | +12.541% | +2.264% |
| ABL-SpeedDensity16-R | 0.288283022 | 0.040164835 | +1.588% | +12.309% | +2.355% |

## minecraft / Benchmark

| Mode | 전체 AA | Resolve | AA vs 기존 선택 | Resolve vs 기존 선택 | AA vs 원본 |
|---|---:|---:|---:|---:|---:|
| O-T2X-R | 0.283520534 | 0.034883147 | -0.526% | -2.928% | +0.000% |
| ABL-ScalarPairedDeJitter-001-R | 0.285019200 | 0.035935307 | +0.000% | +0.000% | +0.529% |
| ABL-SpeedUniformScalar-R | 0.284994080 | 0.035914720 | -0.009% | -0.057% | +0.520% |
| ABL-SpeedPhaseScalar-R | 0.285043893 | 0.035903733 | +0.009% | -0.088% | +0.537% |

### 최종 반복 차이와 실행 순서

| 비교 | 지표 | 평균 차이 µs | 느린 반복 | 정순 차이 µs | 역순 차이 µs | 차이의 표준편차 µs |
|---|---|---:|---:|---:|---:|---:|
| ABL-ScalarPairedDeJitter-001-R − O-T2X-R | SMAA | +1.498666 | 4/4 | +1.392213 | +1.605120 | 0.807625 |
| ABL-ScalarPairedDeJitter-001-R − O-T2X-R | Resolve | +1.052160 | 4/4 | +1.065707 | +1.038614 | 0.026151 |
| ABL-ScalarPairedDeJitter-001-R − O-T2X-R | Spatial | +0.426720 | 3/4 | +0.283520 | +0.569920 | 0.796967 |
| ABL-ScalarPairedDeJitter-001-R − O-T2X-R | WholeFrame | +0.638208 | 2/4 | +1.890560 | -0.614143 | 8.573372 |
| ABL-SpeedUniformScalar-R − ABL-ScalarPairedDeJitter-001-R | SMAA | -0.025120 | 2/4 | +0.762240 | -0.812481 | 0.911665 |
| ABL-SpeedUniformScalar-R − ABL-ScalarPairedDeJitter-001-R | Resolve | -0.020587 | 1/4 | -0.000960 | -0.040214 | 0.024065 |
| ABL-SpeedUniformScalar-R − ABL-ScalarPairedDeJitter-001-R | Spatial | +0.007253 | 2/4 | +0.756374 | -0.741867 | 0.866300 |
| ABL-SpeedUniformScalar-R − ABL-ScalarPairedDeJitter-001-R | WholeFrame | -1.762632 | 2/4 | -0.482693 | -3.042570 | 6.814461 |
| ABL-SpeedUniformScalar-R − O-T2X-R | SMAA | +1.473546 | 4/4 | +2.154453 | +0.792639 | 1.117825 |
| ABL-SpeedUniformScalar-R − O-T2X-R | Resolve | +1.031573 | 4/4 | +1.064747 | +0.998400 | 0.047413 |
| ABL-SpeedUniformScalar-R − O-T2X-R | Spatial | +0.433973 | 3/4 | +1.039893 | -0.171947 | 1.040592 |
| ABL-SpeedUniformScalar-R − O-T2X-R | WholeFrame | -1.124424 | 1/4 | +1.407866 | -3.656713 | 3.508019 |
| ABL-SpeedPhaseScalar-R − ABL-ScalarPairedDeJitter-001-R | SMAA | +0.024693 | 2/4 | +0.199360 | -0.149974 | 0.242272 |
| ABL-SpeedPhaseScalar-R − ABL-ScalarPairedDeJitter-001-R | Resolve | -0.031573 | 1/4 | -0.005120 | -0.058026 | 0.032359 |
| ABL-SpeedPhaseScalar-R − ABL-ScalarPairedDeJitter-001-R | Spatial | +0.057707 | 2/4 | +0.184853 | -0.069440 | 0.184900 |
| ABL-SpeedPhaseScalar-R − ABL-ScalarPairedDeJitter-001-R | WholeFrame | +0.463539 | 2/4 | +0.374897 | +0.552180 | 5.696058 |
| ABL-SpeedPhaseScalar-R − O-T2X-R | SMAA | +1.523360 | 4/4 | +1.591573 | +1.455146 | 0.932406 |
| ABL-SpeedPhaseScalar-R − O-T2X-R | Resolve | +1.020587 | 4/4 | +1.060587 | +0.980587 | 0.053513 |
| ABL-SpeedPhaseScalar-R − O-T2X-R | Spatial | +0.484427 | 3/4 | +0.468373 | +0.500480 | 0.891435 |
| ABL-SpeedPhaseScalar-R − O-T2X-R | WholeFrame | +1.101747 | 2/4 | +2.265457 | -0.061963 | 5.629073 |

각 run의 median, p95/p99, Wall FPS와 1% low는 같은 이름의 JSON에 저장했다.

## 검증과 출처

패턴 검사 7200개, PNG 비교 1590개에서 불일치 0. 각 mode의 전체 240 frame 중 53개를 저장한 제한된 정확성 검사다.

| 장면 | 단계 | AutoBench ID | 실행파일 SHA-256 |
|---|---|---|---|
| bistro | Capture | 20260921_174249 | `8CC55DD283AF6280B8FF2A7C5FF6CC455B4DA76FCD75EDCBAB31134E6A00E95E` |
| bistro | Smoke | 20260921_174526 | `8CC55DD283AF6280B8FF2A7C5FF6CC455B4DA76FCD75EDCBAB31134E6A00E95E` |
| bistro | ScreenBenchmark | 20260921_174835 | `8CC55DD283AF6280B8FF2A7C5FF6CC455B4DA76FCD75EDCBAB31134E6A00E95E` |
| bistro | GroupCapture | 20260921_175953 | `8E58733BE03841A30AA87E377032977CE9D8E42621BAA42E842ED0F8E2192A40` |
| bistro | GroupSmoke | 20260921_180225 | `8E58733BE03841A30AA87E377032977CE9D8E42621BAA42E842ED0F8E2192A40` |
| bistro | GroupScreenBenchmark | 20260921_180545 | `8E58733BE03841A30AA87E377032977CE9D8E42621BAA42E842ED0F8E2192A40` |
| bistro | Benchmark | 20260921_181253 | `8E58733BE03841A30AA87E377032977CE9D8E42621BAA42E842ED0F8E2192A40` |
| minecraft | Capture | 20260921_174109 | `8CC55DD283AF6280B8FF2A7C5FF6CC455B4DA76FCD75EDCBAB31134E6A00E95E` |
| minecraft | Smoke | 20260921_174422 | `8CC55DD283AF6280B8FF2A7C5FF6CC455B4DA76FCD75EDCBAB31134E6A00E95E` |
| minecraft | ScreenBenchmark | 20260921_174633 | `8CC55DD283AF6280B8FF2A7C5FF6CC455B4DA76FCD75EDCBAB31134E6A00E95E` |
| minecraft | GroupCapture | 20260921_175719 | `59D1765B718914D6C842ABD0B4619F24A9E6E055FF7D4D15C7A945C356FD1768` |
| minecraft | GroupSmoke | 20260921_180110 | `8E58733BE03841A30AA87E377032977CE9D8E42621BAA42E842ED0F8E2192A40` |
| minecraft | GroupScreenBenchmark | 20260921_180331 | `8E58733BE03841A30AA87E377032977CE9D8E42621BAA42E842ED0F8E2192A40` |
| minecraft | Benchmark | 20260921_181019 | `8E58733BE03841A30AA87E377032977CE9D8E42621BAA42E842ED0F8E2192A40` |
