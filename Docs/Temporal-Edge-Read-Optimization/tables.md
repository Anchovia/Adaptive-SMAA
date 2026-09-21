# Identical first-pass edge RG: Load vs Point

Times are ms. No texture copy or candidate selection.

## bistro

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.211203 ± 0.001015 | 0.033573 ± 0.000150 | 0.153791 | 2.479607 |
| ABL-EdgeReadControl-R | 0.211488 ± 0.000130 | 0.033609 ± 0.000100 | 0.154029 | 2.483429 |
| ABL-EdgeReadOne-R | 0.213605 ± 0.000168 | 0.035471 ± 0.000121 | 0.154257 | 2.481657 |
| ABL-EdgeReadPoint-R | 0.213527 ± 0.000167 | 0.035433 ± 0.000103 | 0.154228 | 2.480969 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeReadControl-R − O-T2X-R | Resolve | +0.000036 | +0.107% | +0.000269, -0.000194, +0.000226, -0.000157 |
| ABL-EdgeReadControl-R − O-T2X-R | SMAA | +0.000285 | +0.135% | +0.001659, -0.000202, -0.000323, +0.000007 |
| ABL-EdgeReadControl-R − O-T2X-R | WholeFrame | +0.003822 | +0.154% | +0.009563, +0.006527, +0.012510, -0.013310 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | Resolve | +0.001862 | +5.541% | +0.001689, +0.002034, +0.001658, +0.002068 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | SMAA | +0.002117 | +1.001% | +0.002228, +0.002004, +0.001999, +0.002236 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | WholeFrame | -0.001772 | -0.071% | +0.004256, -0.004520, -0.002265, -0.004559 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadOne-R | Resolve | -0.000038 | -0.108% | +0.000172, -0.000215, +0.000135, -0.000245 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadOne-R | SMAA | -0.000079 | -0.037% | +0.000088, -0.000253, +0.000268, -0.000417 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadOne-R | WholeFrame | -0.000689 | -0.028% | -0.004434, +0.009154, -0.008617, +0.001142 |
| ABL-EdgeReadPoint-R − O-T2X-R | Resolve | +0.001860 | +5.540% | +0.002129, +0.001625, +0.002020, +0.001666 |
| ABL-EdgeReadPoint-R − O-T2X-R | SMAA | +0.002323 | +1.100% | +0.003976, +0.001548, +0.001944, +0.001826 |
| ABL-EdgeReadPoint-R − O-T2X-R | WholeFrame | +0.001362 | +0.055% | +0.009386, +0.011161, +0.001628, -0.016727 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadControl-R | Resolve | +0.001824 | +5.427% | +0.001861, +0.001818, +0.001794, +0.001823 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadControl-R | SMAA | +0.002038 | +0.964% | +0.002317, +0.001750, +0.002267, +0.001819 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadControl-R | WholeFrame | -0.002461 | -0.099% | -0.000178, +0.004634, -0.010882, -0.003416 |

| Phase | Run directory |
|---|---|
| capture | `20260922_002250` |
| Smoke | `20260922_002441` |
| Benchmark | `20260922_002829` |

## minecraft

| Mode | SMAA mean ± run SD | Resolve mean ± run SD | Spatial | WholeFrame |
|---|---:|---:|---:|---:|
| O-T2X-R | 0.287234 ± 0.001286 | 0.034917 ± 0.000072 | 0.228399 | 1.187514 |
| ABL-EdgeReadControl-R | 0.287823 ± 0.000984 | 0.034952 ± 0.000056 | 0.228956 | 1.186896 |
| ABL-EdgeReadOne-R | 0.291534 ± 0.000673 | 0.038623 ± 0.000035 | 0.228980 | 1.189976 |
| ABL-EdgeReadPoint-R | 0.291408 ± 0.000694 | 0.038562 ± 0.000029 | 0.228917 | 1.188913 |

| New − control | Metric | Delta ms | Delta % | Same-repeat deltas ms |
|---|---|---:|---:|---|
| ABL-EdgeReadControl-R − O-T2X-R | Resolve | +0.000034 | +0.099% | +0.000001, +0.000057, +0.000087, -0.000007 |
| ABL-EdgeReadControl-R − O-T2X-R | SMAA | +0.000589 | +0.205% | +0.001143, +0.001108, -0.000423, +0.000529 |
| ABL-EdgeReadControl-R − O-T2X-R | WholeFrame | -0.000618 | -0.052% | +0.001725, +0.000826, -0.005753, +0.000729 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | Resolve | +0.003671 | +10.503% | +0.003709, +0.003651, +0.003697, +0.003627 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | SMAA | +0.003710 | +1.289% | +0.004698, +0.002641, +0.004883, +0.002619 |
| ABL-EdgeReadOne-R − ABL-EdgeReadControl-R | WholeFrame | +0.003080 | +0.260% | +0.006327, -0.001319, +0.006157, +0.001158 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadOne-R | Resolve | -0.000061 | -0.157% | -0.000073, -0.000017, -0.000094, -0.000058 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadOne-R | SMAA | -0.000126 | -0.043% | -0.000919, +0.000775, -0.000854, +0.000496 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadOne-R | WholeFrame | -0.001064 | -0.089% | -0.003323, +0.001327, -0.003132, +0.000874 |
| ABL-EdgeReadPoint-R − O-T2X-R | Resolve | +0.003645 | +10.438% | +0.003637, +0.003690, +0.003690, +0.003562 |
| ABL-EdgeReadPoint-R − O-T2X-R | SMAA | +0.004174 | +1.453% | +0.004922, +0.004525, +0.003606, +0.003644 |
| ABL-EdgeReadPoint-R − O-T2X-R | WholeFrame | +0.001399 | +0.118% | +0.004729, +0.000833, -0.002728, +0.002761 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadControl-R | Resolve | +0.003610 | +10.329% | +0.003636, +0.003633, +0.003603, +0.003568 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadControl-R | SMAA | +0.003585 | +1.245% | +0.003779, +0.003417, +0.004029, +0.003115 |
| ABL-EdgeReadPoint-R − ABL-EdgeReadControl-R | WholeFrame | +0.002017 | +0.170% | +0.003004, +0.000007, +0.003025, +0.002031 |

| Phase | Run directory |
|---|---|
| capture | `20260922_002139` |
| Smoke | `20260922_002356` |
| Benchmark | `20260922_002608` |

Four alternating-order repeats within one process; no cross-device or independent-day claim.
Point−Load compares the same first-pass RG with the same sink; both include a live read. Control estimates sink overhead. Not isolated DRAM transfer time.
Read variants−Native include the artificial sink arithmetic. No quality or candidate policy changes.
