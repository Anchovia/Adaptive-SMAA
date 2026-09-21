# Output-preserving edgesRT read: measured tables

Times are ms. Binding is not a CPU-to-GPU texture copy.

## bistro

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.209952 ± 0.000800 | 0.033390 ± 0.000017 | 0.152767 | 2.474315 |
| ABL-EdgeBindOnly-R | 0.210293 ± 0.000014 | 0.033378 ± 0.000024 | 0.153111 | 2.474721 |
| ABL-EdgeReadControl-R | 0.210284 ± 0.000119 | 0.033421 ± 0.000020 | 0.153057 | 2.474650 |
| ABL-EdgeReadOne-R | 0.212071 ± 0.000179 | 0.035284 ± 0.000033 | 0.153007 | 2.488685 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeBindOnly-R − O-T2X-R | Resolve | -0.000012 | -0.035% | -0.000017, +0.000035, -0.000053, -0.000012 |
| ABL-EdgeBindOnly-R − O-T2X-R | SMAA | +0.000341 | +0.162% | +0.001536, -0.000122, +0.000097, -0.000148 |
| ABL-EdgeBindOnly-R − O-T2X-R | WholeFrame | +0.000406 | +0.016% | +0.006876, -0.000833, -0.008679, +0.004258 |
| ABL-EdgeReadControl-R − ABL-EdgeBindOnly-R | Resolve | +0.000044 | +0.131% | +0.000063, -0.000008, +0.000089, +0.000031 |
| ABL-EdgeReadControl-R − ABL-EdgeBindOnly-R | SMAA | -0.000009 | -0.004% | -0.000135, +0.000144, -0.000098, +0.000053 |
| ABL-EdgeReadControl-R − ABL-EdgeBindOnly-R | WholeFrame | -0.000071 | -0.003% | +0.004202, -0.000739, -0.000260, -0.003487 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | Resolve | +0.001863 | +5.574% | +0.001817, +0.001918, +0.001835, +0.001881 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | SMAA | +0.001787 | +0.850% | +0.001745, +0.001859, +0.001950, +0.001595 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | WholeFrame | +0.014036 | +0.567% | +0.024785, -0.002750, +0.010339, +0.023769 |
| ABL-EdgeReadOne-R − O-T2X-R | Resolve | +0.001895 | +5.674% | +0.001863, +0.001944, +0.001871, +0.001900 |
| ABL-EdgeReadOne-R − O-T2X-R | SMAA | +0.002119 | +1.009% | +0.003145, +0.001882, +0.001949, +0.001500 |
| ABL-EdgeReadOne-R − O-T2X-R | WholeFrame | +0.014370 | +0.581% | +0.035863, -0.004322, +0.001400, +0.024540 |

| Phase | Run directory |
|---|---|
| capture | `20260921_235717` |
| Smoke | `20260921_235852` |
| Benchmark | `20260922_000205` |

## minecraft

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.285291 ± 0.001049 | 0.035349 ± 0.000076 | 0.225995 | 1.183070 |
| ABL-EdgeBindOnly-R | 0.285465 ± 0.000560 | 0.035321 ± 0.000081 | 0.226240 | 1.186808 |
| ABL-EdgeReadControl-R | 0.285778 ± 0.000131 | 0.035373 ± 0.000061 | 0.226469 | 1.184857 |
| ABL-EdgeReadOne-R | 0.289454 ± 0.000424 | 0.038941 ± 0.000032 | 0.226564 | 1.188653 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeBindOnly-R − O-T2X-R | Resolve | -0.000027 | -0.077% | +0.000102, -0.000183, +0.000090, -0.000119 |
| ABL-EdgeBindOnly-R − O-T2X-R | SMAA | +0.000174 | +0.061% | +0.001349, -0.000584, -0.000489, +0.000420 |
| ABL-EdgeBindOnly-R − O-T2X-R | WholeFrame | +0.003737 | +0.316% | -0.003998, +0.016615, -0.001523, +0.003855 |
| ABL-EdgeReadControl-R − ABL-EdgeBindOnly-R | Resolve | +0.000052 | +0.146% | -0.000033, +0.000196, -0.000096, +0.000139 |
| ABL-EdgeReadControl-R − ABL-EdgeBindOnly-R | SMAA | +0.000313 | +0.110% | +0.000805, +0.000607, +0.000289, -0.000450 |
| ABL-EdgeReadControl-R − ABL-EdgeBindOnly-R | WholeFrame | -0.001951 | -0.164% | +0.004557, -0.017671, +0.008968, -0.003658 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | Resolve | +0.003568 | +10.086% | +0.003633, +0.003487, +0.003659, +0.003492 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | SMAA | +0.003676 | +1.286% | +0.003095, +0.003951, +0.003436, +0.004220 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | WholeFrame | +0.003797 | +0.320% | +0.000274, +0.005357, -0.000510, +0.010066 |
| ABL-EdgeReadOne-R − O-T2X-R | Resolve | +0.003592 | +10.162% | +0.003702, +0.003501, +0.003654, +0.003512 |
| ABL-EdgeReadOne-R − O-T2X-R | SMAA | +0.004163 | +1.459% | +0.005250, +0.003974, +0.003236, +0.004191 |
| ABL-EdgeReadOne-R − O-T2X-R | WholeFrame | +0.005583 | +0.472% | +0.000833, +0.004301, +0.006935, +0.010262 |

| Phase | Run directory |
|---|---|
| capture | `20260921_235643` |
| Smoke | `20260921_235802` |
| Benchmark | `20260921_235945` |

Four alternating-order repeats within one process; no cross-device or independent-day claim.
ReadOne−ReadControl includes Load, coordinates, dependency, register/cache effects and different probe source; it is not isolated DRAM transfer time.
ReadOne−Native includes the artificial sink arithmetic. No quality or candidate policy changes.
