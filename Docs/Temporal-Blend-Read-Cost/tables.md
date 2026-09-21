# Output-preserving blendRT read: measured tables

Times are ms. Binding is not a CPU-to-GPU texture copy.

## bistro

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.209777 ± 0.001349 | 0.033244 ± 0.000083 | 0.152669 | 2.631313 |
| ABL-BlendBindOnly-R | 0.210328 ± 0.000343 | 0.033279 ± 0.000035 | 0.153168 | 2.629345 |
| ABL-BlendReadControl-R | 0.210422 ± 0.000174 | 0.033359 ± 0.000016 | 0.153188 | 2.637674 |
| ABL-BlendReadOne-R | 0.212409 ± 0.000109 | 0.035182 ± 0.000023 | 0.153334 | 2.646107 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-BlendBindOnly-R − O-T2X-R | Resolve | +0.000035 | +0.105% | +0.000107, -0.000009, +0.000011, +0.000029 |
| ABL-BlendBindOnly-R − O-T2X-R | SMAA | +0.000551 | +0.263% | +0.002063, +0.000140, -0.000057, +0.000057 |
| ABL-BlendBindOnly-R − O-T2X-R | WholeFrame | -0.001968 | -0.075% | +0.013428, +0.005295, -0.003068, -0.023527 |
| ABL-BlendReadControl-R − ABL-BlendBindOnly-R | Resolve | +0.000081 | +0.242% | +0.000113, +0.000088, +0.000070, +0.000052 |
| ABL-BlendReadControl-R − ABL-BlendBindOnly-R | SMAA | +0.000094 | +0.045% | +0.000359, -0.000070, +0.000128, -0.000040 |
| ABL-BlendReadControl-R − ABL-BlendBindOnly-R | WholeFrame | +0.008329 | +0.317% | +0.020480, +0.003644, -0.002586, +0.011776 |
| ABL-BlendReadOne-R − ABL-BlendReadControl-R | Resolve | +0.001823 | +5.464% | +0.001815, +0.001789, +0.001848, +0.001840 |
| ABL-BlendReadOne-R − ABL-BlendReadControl-R | SMAA | +0.001987 | +0.944% | +0.002087, +0.001992, +0.001866, +0.002003 |
| ABL-BlendReadOne-R − ABL-BlendReadControl-R | WholeFrame | +0.008433 | +0.320% | +0.008970, +0.006452, +0.010046, +0.008266 |
| ABL-BlendReadOne-R − O-T2X-R | Resolve | +0.001938 | +5.830% | +0.002036, +0.001868, +0.001929, +0.001921 |
| ABL-BlendReadOne-R − O-T2X-R | SMAA | +0.002632 | +1.255% | +0.004509, +0.002062, +0.001937, +0.002019 |
| ABL-BlendReadOne-R − O-T2X-R | WholeFrame | +0.014794 | +0.562% | +0.042879, +0.015391, +0.004392, -0.003485 |

| Phase | Run directory |
|---|---|
| capture | `20260921_230931` |
| Smoke | `20260921_231208` |
| Benchmark | `20260921_231700` |

## minecraft

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.282799 ± 0.002306 | 0.034870 ± 0.000096 | 0.224320 | 1.243642 |
| ABL-BlendBindOnly-R | 0.283195 ± 0.000621 | 0.034870 ± 0.000055 | 0.224699 | 1.245993 |
| ABL-BlendReadControl-R | 0.283588 ± 0.000701 | 0.034965 ± 0.000043 | 0.224968 | 1.251834 |
| ABL-BlendReadOne-R | 0.286847 ± 0.000706 | 0.038158 ± 0.000041 | 0.225050 | 1.249851 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-BlendBindOnly-R − O-T2X-R | Resolve | +0.000000 | +0.001% | +0.000067, -0.000044, +0.000029, -0.000051 |
| ABL-BlendBindOnly-R − O-T2X-R | SMAA | +0.000396 | +0.140% | +0.003189, -0.001255, +0.001011, -0.001362 |
| ABL-BlendBindOnly-R − O-T2X-R | WholeFrame | +0.002351 | +0.189% | +0.004150, +0.005118, -0.000252, +0.000390 |
| ABL-BlendReadControl-R − ABL-BlendBindOnly-R | Resolve | +0.000094 | +0.270% | +0.000125, +0.000115, +0.000019, +0.000118 |
| ABL-BlendReadControl-R − ABL-BlendBindOnly-R | SMAA | +0.000393 | +0.139% | +0.000126, +0.001026, -0.000750, +0.001169 |
| ABL-BlendReadControl-R − ABL-BlendBindOnly-R | WholeFrame | +0.005840 | +0.469% | +0.002055, +0.005538, +0.013457, +0.002311 |
| ABL-BlendReadOne-R − ABL-BlendReadControl-R | Resolve | +0.003194 | +9.134% | +0.003220, +0.003133, +0.003260, +0.003162 |
| ABL-BlendReadOne-R − ABL-BlendReadControl-R | SMAA | +0.003259 | +1.149% | +0.004233, +0.002188, +0.004403, +0.002212 |
| ABL-BlendReadOne-R − ABL-BlendReadControl-R | WholeFrame | -0.001983 | -0.158% | +0.009865, -0.008948, -0.007597, -0.001254 |
| ABL-BlendReadOne-R − O-T2X-R | Resolve | +0.003288 | +9.430% | +0.003412, +0.003205, +0.003308, +0.003228 |
| ABL-BlendReadOne-R − O-T2X-R | SMAA | +0.004048 | +1.431% | +0.007548, +0.001959, +0.004664, +0.002020 |
| ABL-BlendReadOne-R − O-T2X-R | WholeFrame | +0.006208 | +0.499% | +0.016070, +0.001708, +0.005607, +0.001448 |

| Phase | Run directory |
|---|---|
| capture | `20260921_230744` |
| Smoke | `20260921_231038` |
| Benchmark | `20260921_231353` |

Four alternating-order repeats within one process; no cross-device or independent-day claim.
ReadOne−ReadControl includes Load, coordinates, dependency, register/cache effects and different probe source; it is not isolated DRAM transfer time.
ReadOne−Native includes the artificial sink arithmetic. No quality or candidate policy changes.
