# ET2X 성능 예산 재계산

검증 PASS. 기존 원시 측정의 재분석이며 새 GPU 측정이 아니다.

| 장면 | Standard ms | ET2X ms | 차이 ms | 필요한 ET2X 감소율 |
|---|---:|---:|---:|---:|
| bistro | 0.277314 | 0.341403 | 0.064089 | 18.77% |
| minecraft | 0.293613 | 0.382936 | 0.089323 | 23.33% |

## 비용 차이 분해

공간 구간 차이에는 jitter/subsample 등 경로 차이도 있어 후보 계산 단독 비용이 아니다.

| 항목 | Bistro ms | Minecraft ms |
|---|---:|---:|
| spatial_path_delta_not_candidate_only_ms | +0.014301 | +0.024627 |
| velocity_delta_ms | +0.000109 | -0.000093 |
| copies_ms | +0.047051 | +0.046670 |
| clear_and_args_ms | +0.008336 | +0.007926 |
| resolve_delta_ms | -0.009219 | +0.007089 |
| timer_residual_delta_ms | +0.003511 | +0.003104 |

## 조건부 비용 삭제 가정

나머지 비용 고정, 대체 비용 0이라는 산술 가정이다. 구현 가능한 하한이나 실측 가속률이 아니다.

| 가정 | Bistro ms / Standard 대비 | Minecraft ms / Standard 대비 |
|---|---:|---:|
| output_copy_zero | 0.317497 / +14.49% | 0.359078 / +22.30% |
| both_copies_zero | 0.294352 / +6.14% | 0.336266 / +14.53% |
| both_copies_clear_args_zero | 0.286016 / +3.14% | 0.328340 / +11.83% |
| candidate_resolve_zero | 0.313520 / +13.06% | 0.337963 / +15.10% |

## 동일 temporal 계산의 기존 비교

8월 결과의 내부 짝 비교만 사용한다. 위 9월 절대 시간과 합산하지 않는다.

| 장면 | 경로 | Full-screen ms | Selective ms | 변화 |
|---|---|---:|---:|---:|
| bistro | legacy | 0.445663 | 0.349862 | -21.50% |
| minecraft | legacy | 0.454113 | 0.391691 | -13.75% |
| bistro | dual | 0.451351 | 0.356000 | -21.13% |
| minecraft | dual | 0.464066 | 0.407268 | -12.24% |
