# Edge-only temporal microbenchmark

Times are ms. Edge-only/output-only output black; not a quality comparison.

## bistro

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.211523 ± 0.000843 | 0.033763 ± 0.000009 | 0.153886 | 2.479240 |
| ABL-EdgeReadOne-R | 0.213821 ± 0.000278 | 0.035712 ± 0.000015 | 0.154239 | 2.485295 |
| DIAG-OutputOnly | 0.193288 ± 0.000315 | 0.015627 ± 0.000013 | 0.153838 | 2.453008 |
| DIAG-EdgeOnly | 0.193638 ± 0.000277 | 0.016037 ± 0.000015 | 0.153785 | 2.462487 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeReadOne-R − O-T2X-R | Resolve | +0.001950 | +5.774% | +0.001928, +0.001963, +0.001954, +0.001954 |
| ABL-EdgeReadOne-R − O-T2X-R | SMAA | +0.002298 | +1.086% | +0.003427, +0.001561, +0.002740, +0.001464 |
| ABL-EdgeReadOne-R − O-T2X-R | WholeFrame | +0.006055 | +0.244% | +0.007747, +0.013233, -0.003228, +0.006469 |
| DIAG-EdgeOnly − DIAG-OutputOnly | Resolve | +0.000410 | +2.625% | +0.000397, +0.000420, +0.000442, +0.000381 |
| DIAG-EdgeOnly − DIAG-OutputOnly | SMAA | +0.000350 | +0.181% | +0.000816, -0.000218, +0.000901, -0.000100 |
| DIAG-EdgeOnly − DIAG-OutputOnly | WholeFrame | +0.009479 | +0.386% | +0.008488, +0.001562, +0.006257, +0.021608 |
| DIAG-EdgeOnly − O-T2X-R | Resolve | -0.017725 | -52.500% | -0.017739, -0.017715, -0.017699, -0.017749 |
| DIAG-EdgeOnly − O-T2X-R | SMAA | -0.017886 | -8.456% | -0.016516, -0.018645, -0.017566, -0.018816 |
| DIAG-EdgeOnly − O-T2X-R | WholeFrame | -0.016752 | -0.676% | -0.011753, -0.023219, -0.030830, -0.001207 |
| DIAG-EdgeOnly − ABL-EdgeReadOne-R | Resolve | -0.019675 | -55.093% | -0.019667, -0.019677, -0.019653, -0.019703 |
| DIAG-EdgeOnly − ABL-EdgeReadOne-R | SMAA | -0.020184 | -9.440% | -0.019943, -0.020206, -0.020306, -0.020281 |
| DIAG-EdgeOnly − ABL-EdgeReadOne-R | WholeFrame | -0.022808 | -0.918% | -0.019500, -0.036451, -0.027602, -0.007676 |

| Phase | Run directory |
|---|---|
| capture | `20260922_004554` |
| Smoke | `20260922_004842` |
| Benchmark | `20260922_005153` |

## minecraft

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.287780 ± 0.001652 | 0.035097 ± 0.000064 | 0.228709 | 1.189424 |
| ABL-EdgeReadOne-R | 0.291960 ± 0.001122 | 0.038734 ± 0.000076 | 0.229242 | 1.195677 |
| DIAG-OutputOnly | 0.268150 ± 0.000449 | 0.015677 ± 0.000045 | 0.228561 | 1.163839 |
| DIAG-EdgeOnly | 0.268742 ± 0.001082 | 0.016276 ± 0.000048 | 0.228543 | 1.165716 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeReadOne-R − O-T2X-R | Resolve | +0.003636 | +10.361% | +0.003623, +0.003661, +0.003589, +0.003673 |
| ABL-EdgeReadOne-R − O-T2X-R | SMAA | +0.004180 | +1.452% | +0.005237, +0.004586, +0.002238, +0.004660 |
| ABL-EdgeReadOne-R − O-T2X-R | WholeFrame | +0.006253 | +0.526% | -0.003939, +0.007576, +0.014046, +0.007327 |
| DIAG-EdgeOnly − DIAG-OutputOnly | Resolve | +0.000599 | +3.821% | +0.000612, +0.000557, +0.000655, +0.000572 |
| DIAG-EdgeOnly − DIAG-OutputOnly | SMAA | +0.000592 | +0.221% | -0.000435, +0.000945, +0.000167, +0.001690 |
| DIAG-EdgeOnly − DIAG-OutputOnly | WholeFrame | +0.001877 | +0.161% | +0.009018, +0.000660, -0.002981, +0.000810 |
| DIAG-EdgeOnly − O-T2X-R | Resolve | -0.018822 | -53.627% | -0.018780, -0.018859, -0.018810, -0.018837 |
| DIAG-EdgeOnly − O-T2X-R | SMAA | -0.019039 | -6.616% | -0.018080, -0.019432, -0.020290, -0.018352 |
| DIAG-EdgeOnly − O-T2X-R | WholeFrame | -0.023708 | -1.993% | -0.024193, -0.024757, -0.020544, -0.025340 |
| DIAG-EdgeOnly − ABL-EdgeReadOne-R | Resolve | -0.022458 | -57.981% | -0.022403, -0.022520, -0.022399, -0.022511 |
| DIAG-EdgeOnly − ABL-EdgeReadOne-R | SMAA | -0.023218 | -7.953% | -0.023317, -0.024018, -0.022527, -0.023012 |
| DIAG-EdgeOnly − ABL-EdgeReadOne-R | WholeFrame | -0.029961 | -2.506% | -0.020254, -0.032334, -0.034590, -0.032666 |

| Phase | Run directory |
|---|---|
| capture | `20260922_004528` |
| Smoke | `20260922_004653` |
| Benchmark | `20260922_004933` |

Four alternating-order repeats within one process; no cross-device or independent-day claim.
EdgeOnly−OutputOnly estimates incremental edge access with matched black outputs; not isolated DRAM latency.
EdgeOnly removes native samples and blending but still runs a fullscreen draw. Black diagnostic output is not valid AA. Differences are not additive predictions of selective temporal speed.
