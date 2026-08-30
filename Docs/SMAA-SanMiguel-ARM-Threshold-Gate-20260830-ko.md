# San Miguel ARM threshold 및 3×3 control gate

## 1. 목적

기존 ARM Dual Filter candidate expansion의 reconstruction threshold `0.25`는 binary
candidate mask에 적용한 연구 가정이다. 단일 임의값에 결론이 종속되지 않도록 San Miguel
동일 camera path에서 threshold 품질·coverage sweep을 수행하고, 3×3 dilation과
single-process paired 성능을 비교했다.

이 결과는 Intel/ARM의 공식 SMAA/TSCMAA 파라미터를 복원한 것이 아니라 연구 adaptation의
파라미터 gate다.

## 2. 공통 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- 해상도: 1920×1017
- API/preset: DirectX 11, SMAA Ultra
- 장면: San Miguel 2.1 textured scene
- camera profile: `yaw-fast-360`, profile frame 60~119
- quality: mode당 60 frame, warm-up 60 frame
- performance: warm-up 300 frame, measurement 60 frame×3 repeats
- candidate counter readback: performance에서는 Off
- 모든 CMAA2 실행은 독립 clean process로 실행

Supersample sequence는 동일 pose의 spatial-reference proxy이며 temporal ground truth가 아니다.

## 3. 5-way control

| Mode | Full RGB MAE | Thin ROI RGB MAE | Full temporal-delta residual | Thin ROI temporal-delta residual |
|---|---:|---:|---:|---:|
| O-1X | 2.594906 | 2.529502 | 4.008667 | 4.020181 |
| O-T2X-R | 3.509749 | 3.428525 | 5.452368 | 5.464682 |
| O-ET2X-R None | 2.409020 | 2.366078 | 3.688699 | 3.732479 |
| O-ET2X-R 3×3 | 2.140897 | 2.094132 | 3.220279 | 3.234697 |
| O-ET2X-R ARM 0.20 | 2.133977 | 2.086779 | 3.212002 | 3.224444 |

ARM `0.20`은 3×3보다 RGB MAE가 full frame에서 약 0.323%, thin ROI에서 약 0.351%
낮았다. temporal-delta residual도 각각 약 0.257%, 0.317% 낮았다. 차이는 작지만 이
San Miguel 구간에서는 ARM `0.20`이 3×3보다 근소한 품질 우위를 보였다.

## 4. Candidate coverage

| Expansion | Full coverage | Thin ROI coverage |
|---|---:|---:|
| None | 9.759% | 9.463% |
| 3×3 | 24.471% | 22.819% |
| ARM 0.20 | 22.826% | 21.712% |

ARM `0.20`은 3×3보다 후보 수가 full frame에서 약 6.72%, thin ROI에서 약 4.85%
적었다. raw candidate preservation 위반은 0 pixel이었다.

## 5. Threshold sweep

- 범위: `0.00~1.00`, 간격 `0.05`, 총 21개 설정
- 2,343,168,000 pixel의 인접 threshold mask 부분집합 검사
- candidate-mask 단조성 위반: 0 pixel
- `0.00`은 사실상 full-screen diagnostic이므로 실용 후보에서 제외
- 최소 reference 오차: `0.15`
- 품질·coverage·성능 절충 후보: `0.20`
- `0.75` 이상은 None과 사실상 동일하여 expansion 효과가 사라짐

`0.15`는 최저 오차였지만 `0.20`보다 얻는 추가 오차 감소가 full 약 0.105%, ROI 약
0.026%에 불과했다. 반면 paired 성능에서 SMAA 비용은 약 0.644%, WholeFrame은 약
0.690% 높았다. 따라서 현재 San Miguel gate에서는 `0.20`을 Pareto 절충 후보로 본다.

## 6. Single-process paired 성능

| Mode | SMAA ms | run-mean stddev | Mask ms | Resolve ms | vs 3×3 SMAA | WholeFrame ms | vs 3×3 WholeFrame |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3×3 | 0.384262 | 0.000591 | 0.048077 | 0.044749 | 기준 | 4.100446 | 기준 |
| ARM 0.10 | 0.484318 | 0.001054 | 0.132585 | 0.047650 | +26.038% | 4.158944 | +1.427% |
| ARM 0.15 | 0.483988 | 0.002130 | 0.133132 | 0.045392 | +25.953% | 4.190721 | +2.202% |
| ARM 0.20 | 0.480893 | 0.002187 | 0.132586 | 0.042655 | +25.147% | 4.162000 | +1.501% |
| ARM 0.25 | 0.479471 | 0.002560 | 0.132444 | 0.040647 | +24.777% | 4.148685 | +1.176% |

ARM `0.20`은 3×3보다 후보 coverage가 작지만 4-pass dual-filter pyramid 비용 때문에
SMAA 시간은 약 25.15%, WholeFrame은 약 1.50% 높았다. 후보 수 감소가 곧 성능 향상으로
이어지지 않는다는 점을 확인했다.

## 7. 현재 결론

1. ARM threshold `0.25`를 그대로 고정할 근거는 없으며, San Miguel에서는 `0.15`가
   최소 오차, `0.20`이 더 합리적인 절충점이었다.
2. ARM `0.20`은 3×3보다 후보 수를 적게 사용하면서 품질이 아주 근소하게 좋았다.
3. 그러나 ARM 4-pass mask 생성 비용이 커서 현재 구현의 성능은 3×3보다 명확히 느리다.
4. 따라서 ARM을 기본 방식으로 채택하기보다 `0.20` research ablation으로 유지하고,
   기본 후보는 여전히 3×3으로 두는 것이 타당하다.
5. 이 결론은 San Miguel 한 장면의 camera-motion 구간에 대한 engineering gate이며,
   다른 textured scene과 object-motion 결과 없이 일반화하지 않는다.

## 8. 결과 위치

- threshold 0.20 final control: `D:\SMAA-Research-Data\AutoBench\20260830_185936`
- threshold 0.20 candidate masks: `D:\SMAA-Research-Data\AutoBench\20260830_185724`
- supersample spatial reference: `D:\SMAA-Research-Data\AutoBench\20260830_181334`
- 21-value threshold sweep: `D:\SMAA-Research-Data\AutoBench\ARM-Threshold-Sweep-20260830_182630`
- paired performance: `D:\SMAA-Research-Data\AutoBench\ARM-Threshold-Paired-Performance-20260830_185509`
