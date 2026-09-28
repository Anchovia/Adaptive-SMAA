# First-pass edge selective native resolve

Times are ms. Exact any(first-pass RG>0) selection; native temporal semantics. Not a quality ranking.

## bistro

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.210735 ± 0.000602 | 0.033334 ± 0.000017 | 0.153346 | 2.511010 |
| ABL-EdgeReadOne-R | 0.212956 ± 0.000355 | 0.035282 ± 0.000013 | 0.153624 | 2.517220 |
| DIAG-CurrentEdge | 0.197885 ± 0.000328 | 0.020433 ± 0.000014 | 0.153419 | 2.500152 |
| ABL-FirstEdge-Reuse-R | 0.205514 ± 0.000278 | 0.028014 ± 0.000016 | 0.153462 | 2.507832 |
| ABL-FirstEdge-Legacy-R | 0.210257 ± 0.000266 | 0.032705 ± 0.000010 | 0.153518 | 2.509594 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeReadOne-R − O-T2X-R | Resolve | +0.001948 | +5.844% | +0.001946, +0.001970, +0.001944, +0.001933 |
| ABL-EdgeReadOne-R − O-T2X-R | SMAA | +0.002221 | +1.054% | +0.002649, +0.002367, +0.001440, +0.002430 |
| ABL-EdgeReadOne-R − O-T2X-R | WholeFrame | +0.006211 | +0.247% | +0.005211, +0.002785, +0.015192, +0.001656 |
| ABL-FirstEdge-Reuse-R − DIAG-CurrentEdge | Resolve | +0.007582 | +37.106% | +0.007586, +0.007601, +0.007581, +0.007559 |
| ABL-FirstEdge-Reuse-R − DIAG-CurrentEdge | SMAA | +0.007629 | +3.855% | +0.007017, +0.008158, +0.007216, +0.008125 |
| ABL-FirstEdge-Reuse-R − DIAG-CurrentEdge | WholeFrame | +0.007680 | +0.307% | +0.011454, -0.003619, +0.008448, +0.014437 |
| ABL-FirstEdge-Reuse-R − O-T2X-R | Resolve | -0.005320 | -15.958% | -0.005319, -0.005295, -0.005306, -0.005358 |
| ABL-FirstEdge-Reuse-R − O-T2X-R | SMAA | -0.005221 | -2.478% | -0.004703, -0.005064, -0.005958, -0.005159 |
| ABL-FirstEdge-Reuse-R − O-T2X-R | WholeFrame | -0.003178 | -0.127% | +0.001815, -0.007144, -0.006311, -0.001072 |
| ABL-FirstEdge-Reuse-R − ABL-EdgeReadOne-R | Resolve | -0.007267 | -20.598% | -0.007264, -0.007265, -0.007250, -0.007291 |
| ABL-FirstEdge-Reuse-R − ABL-EdgeReadOne-R | SMAA | -0.007443 | -3.495% | -0.007353, -0.007431, -0.007398, -0.007589 |
| ABL-FirstEdge-Reuse-R − ABL-EdgeReadOne-R | WholeFrame | -0.009389 | -0.373% | -0.003396, -0.009928, -0.021503, -0.002728 |
| ABL-FirstEdge-Legacy-R − O-T2X-R | Resolve | -0.000629 | -1.887% | -0.000621, -0.000617, -0.000639, -0.000640 |
| ABL-FirstEdge-Legacy-R − O-T2X-R | SMAA | -0.000478 | -0.227% | +0.000538, -0.000819, -0.000800, -0.000831 |
| ABL-FirstEdge-Legacy-R − O-T2X-R | WholeFrame | -0.001415 | -0.056% | +0.001205, -0.002430, -0.002174, -0.002263 |
| ABL-FirstEdge-Reuse-R − ABL-FirstEdge-Legacy-R | Resolve | -0.004690 | -14.341% | -0.004697, -0.004679, -0.004668, -0.004718 |
| ABL-FirstEdge-Reuse-R − ABL-FirstEdge-Legacy-R | SMAA | -0.004743 | -2.256% | -0.005242, -0.004245, -0.005158, -0.004328 |
| ABL-FirstEdge-Reuse-R − ABL-FirstEdge-Legacy-R | WholeFrame | -0.001763 | -0.070% | +0.000609, -0.004713, -0.004137, +0.001191 |

| Phase | Run directory |
|---|---|
| capture | `20260928_152834` |
| Smoke | `20260928_153007` |
| Benchmark | `20260928_153424` |

## minecraft

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.284041 ± 0.001566 | 0.034849 ± 0.000122 | 0.225315 | 1.221004 |
| ABL-EdgeReadOne-R | 0.288355 ± 0.001075 | 0.038516 ± 0.000034 | 0.225943 | 1.224942 |
| DIAG-CurrentEdge | 0.273407 ± 0.000512 | 0.023698 ± 0.000037 | 0.225810 | 1.211062 |
| ABL-FirstEdge-Reuse-R | 0.287545 ± 0.000682 | 0.037930 ± 0.000074 | 0.225728 | 1.226233 |
| ABL-FirstEdge-Legacy-R | 0.293541 ± 0.000455 | 0.043904 ± 0.000068 | 0.225745 | 1.231261 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeReadOne-R − O-T2X-R | Resolve | +0.003668 | +10.524% | +0.003789, +0.003570, +0.003727, +0.003584 |
| ABL-EdgeReadOne-R − O-T2X-R | SMAA | +0.004314 | +1.519% | +0.005102, +0.004271, +0.003505, +0.004378 |
| ABL-EdgeReadOne-R − O-T2X-R | WholeFrame | +0.003938 | +0.323% | +0.007576, +0.003207, +0.002669, +0.002301 |
| ABL-FirstEdge-Reuse-R − DIAG-CurrentEdge | Resolve | +0.014233 | +60.059% | +0.014166, +0.014287, +0.014145, +0.014332 |
| ABL-FirstEdge-Reuse-R − DIAG-CurrentEdge | SMAA | +0.014138 | +5.171% | +0.013836, +0.014523, +0.013241, +0.014950 |
| ABL-FirstEdge-Reuse-R − DIAG-CurrentEdge | WholeFrame | +0.015172 | +1.253% | +0.016549, +0.014428, +0.015334, +0.014376 |
| ABL-FirstEdge-Reuse-R − O-T2X-R | Resolve | +0.003082 | +8.844% | +0.003162, +0.003026, +0.003073, +0.003067 |
| ABL-FirstEdge-Reuse-R − O-T2X-R | SMAA | +0.003504 | +1.234% | +0.004995, +0.003278, +0.002337, +0.003406 |
| ABL-FirstEdge-Reuse-R − O-T2X-R | WholeFrame | +0.005229 | +0.428% | +0.011530, +0.002668, +0.005517, +0.001203 |
| ABL-FirstEdge-Reuse-R − ABL-EdgeReadOne-R | Resolve | -0.000586 | -1.521% | -0.000627, -0.000544, -0.000654, -0.000517 |
| ABL-FirstEdge-Reuse-R − ABL-EdgeReadOne-R | SMAA | -0.000810 | -0.281% | -0.000107, -0.000993, -0.001168, -0.000972 |
| ABL-FirstEdge-Reuse-R − ABL-EdgeReadOne-R | WholeFrame | +0.001291 | +0.105% | +0.003954, -0.000540, +0.002848, -0.001098 |
| ABL-FirstEdge-Legacy-R − O-T2X-R | Resolve | +0.009056 | +25.986% | +0.009239, +0.008898, +0.009165, +0.008921 |
| ABL-FirstEdge-Legacy-R − O-T2X-R | SMAA | +0.009501 | +3.345% | +0.011743, +0.008520, +0.009159, +0.008581 |
| ABL-FirstEdge-Legacy-R − O-T2X-R | WholeFrame | +0.010257 | +0.840% | +0.018940, +0.006545, +0.009652, +0.005892 |
| ABL-FirstEdge-Reuse-R − ABL-FirstEdge-Legacy-R | Resolve | -0.005974 | -13.607% | -0.006077, -0.005872, -0.006092, -0.005854 |
| ABL-FirstEdge-Reuse-R − ABL-FirstEdge-Legacy-R | SMAA | -0.005997 | -2.043% | -0.006748, -0.005242, -0.006822, -0.005175 |
| ABL-FirstEdge-Reuse-R − ABL-FirstEdge-Legacy-R | WholeFrame | -0.005028 | -0.408% | -0.007411, -0.003877, -0.004135, -0.004689 |

| Phase | Run directory |
|---|---|
| capture | `20260928_152754` |
| Smoke | `20260928_152920` |
| Benchmark | `20260928_153135` |

Four alternating-order repeats within one process; no cross-device or independent-day claim.
Selective−CurrentEdge changes branch, history work and removes the diagnostic sink; not isolated branch latency.
Selected output equals native T2X-R and nonselected equals current spatial RGB. Sparse coverage is not the benchmark-wide average. Jitter stability and quality ranking remain untested in this gate.
