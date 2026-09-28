# Current-spatial output and first-pass edge access cost

Times are ms. Current controls output current spatial color; paired jitter remains. Not a quality comparison.

## bistro

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.210210 ± 0.001042 | 0.033280 ± 0.000071 | 0.152983 | 2.542408 |
| ABL-EdgeReadOne-R | 0.212439 ± 0.000788 | 0.035201 ± 0.000086 | 0.153273 | 2.548899 |
| DIAG-CurrentOutput | 0.196007 ± 0.000525 | 0.019078 ± 0.000049 | 0.153013 | 2.535762 |
| DIAG-CurrentEdge | 0.197374 ± 0.000646 | 0.020422 ± 0.000052 | 0.153043 | 2.559220 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeReadOne-R − O-T2X-R | Resolve | +0.001921 | +5.773% | +0.001899, +0.001927, +0.001944, +0.001915 |
| ABL-EdgeReadOne-R − O-T2X-R | SMAA | +0.002229 | +1.060% | +0.002609, +0.002421, +0.001546, +0.002340 |
| ABL-EdgeReadOne-R − O-T2X-R | WholeFrame | +0.006491 | +0.255% | -0.003881, +0.008463, +0.004406, +0.016974 |
| DIAG-CurrentEdge − DIAG-CurrentOutput | Resolve | +0.001343 | +7.042% | +0.001351, +0.001319, +0.001360, +0.001343 |
| DIAG-CurrentEdge − DIAG-CurrentOutput | SMAA | +0.001367 | +0.697% | +0.001188, +0.001407, +0.001148, +0.001725 |
| DIAG-CurrentEdge − DIAG-CurrentOutput | WholeFrame | +0.023458 | +0.925% | +0.002756, +0.098215, -0.009487, +0.002349 |
| DIAG-CurrentEdge − O-T2X-R | Resolve | -0.012858 | -38.636% | -0.012810, -0.012915, -0.012846, -0.012860 |
| DIAG-CurrentEdge − O-T2X-R | SMAA | -0.012836 | -6.106% | -0.012106, -0.013357, -0.013342, -0.012538 |
| DIAG-CurrentEdge − O-T2X-R | WholeFrame | +0.016812 | +0.661% | -0.020434, +0.115475, -0.013805, -0.013989 |
| DIAG-CurrentEdge − ABL-EdgeReadOne-R | Resolve | -0.014779 | -41.985% | -0.014710, -0.014842, -0.014790, -0.014775 |
| DIAG-CurrentEdge − ABL-EdgeReadOne-R | SMAA | -0.015064 | -7.091% | -0.014714, -0.015777, -0.014888, -0.014878 |
| DIAG-CurrentEdge − ABL-EdgeReadOne-R | WholeFrame | +0.010321 | +0.405% | -0.016553, +0.107012, -0.018211, -0.030963 |

| Phase | Run directory |
|---|---|
| capture | `20260928_150920` |
| Smoke | `20260928_151042` |
| Benchmark | `20260928_151407` |

## minecraft

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.284736 ± 0.001691 | 0.034767 ± 0.000055 | 0.226137 | 1.222070 |
| ABL-EdgeReadOne-R | 0.289173 ± 0.000322 | 0.038460 ± 0.000034 | 0.226825 | 1.226466 |
| DIAG-CurrentOutput | 0.270893 ± 0.000505 | 0.020326 ± 0.000028 | 0.226697 | 1.208122 |
| DIAG-CurrentEdge | 0.274300 ± 0.000361 | 0.023707 ± 0.000032 | 0.226710 | 1.211244 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeReadOne-R − O-T2X-R | Resolve | +0.003693 | +10.621% | +0.003739, +0.003674, +0.003667, +0.003690 |
| ABL-EdgeReadOne-R − O-T2X-R | SMAA | +0.004437 | +1.558% | +0.006810, +0.003228, +0.004205, +0.003503 |
| ABL-EdgeReadOne-R − O-T2X-R | WholeFrame | +0.004396 | +0.360% | +0.011576, +0.001591, +0.002680, +0.001736 |
| DIAG-CurrentEdge − DIAG-CurrentOutput | Resolve | +0.003381 | +16.633% | +0.003433, +0.003330, +0.003401, +0.003359 |
| DIAG-CurrentEdge − DIAG-CurrentOutput | SMAA | +0.003407 | +1.258% | +0.004149, +0.002656, +0.003927, +0.002894 |
| DIAG-CurrentEdge − DIAG-CurrentOutput | WholeFrame | +0.003122 | +0.258% | +0.001942, +0.001717, +0.004276, +0.004551 |
| DIAG-CurrentEdge − O-T2X-R | Resolve | -0.011060 | -31.811% | -0.010967, -0.011115, -0.011032, -0.011126 |
| DIAG-CurrentEdge − O-T2X-R | SMAA | -0.010436 | -3.665% | -0.007880, -0.011650, -0.010512, -0.011704 |
| DIAG-CurrentEdge − O-T2X-R | WholeFrame | -0.010827 | -0.886% | -0.005084, -0.015347, -0.011319, -0.011557 |
| DIAG-CurrentEdge − ABL-EdgeReadOne-R | Resolve | -0.014753 | -38.358% | -0.014706, -0.014789, -0.014698, -0.014816 |
| DIAG-CurrentEdge − ABL-EdgeReadOne-R | SMAA | -0.014873 | -5.143% | -0.014690, -0.014878, -0.014718, -0.015207 |
| DIAG-CurrentEdge − ABL-EdgeReadOne-R | WholeFrame | -0.015222 | -1.241% | -0.016660, -0.016938, -0.013998, -0.013293 |

| Phase | Run directory |
|---|---|
| capture | `20260928_150842` |
| Smoke | `20260928_150949` |
| Benchmark | `20260928_151140` |

Four alternating-order repeats within one process; no cross-device or independent-day claim.
CurrentEdge−CurrentOutput estimates incremental edge access with matched current-color outputs and runtime-zero sinks; not isolated DRAM latency.
Current controls retain one current-color sample and remove history/velocity reads and blending. No candidate selection. Differences are not additive predictions of selective temporal speed.
