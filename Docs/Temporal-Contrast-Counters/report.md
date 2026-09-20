# Temporal draw 하드웨어 카운터

동일 frame 90에서 캡처한 temporal draw를 각 3회 재생한 진단이다. 실시간 benchmark 평균이 아니다.

| 장면 | 방식 | warp 명령 수 | 원본 대비 | thread 명령 수 | 원본 대비 | texture 요청 수 | 원본 대비 | 명령당 활성 thread |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| bistro | O-T2X-R | 1,784,181.0 | +0.00% | 57,094,655.3 | +0.00% | 764,834.0 | +0.00% | 32.000 |
| bistro | ABL-Contrast-001-R | 1,137,798.0 | -36.23% | 35,244,661.3 | -38.27% | 266,180.0 | -65.20% | 30.976 |
| bistro | ABL-ScalarWeight-001-R | 2,421,381.0 | +35.71% | 77,484,372.7 | +35.71% | 764,834.0 | +0.00% | 32.000 |
| minecraft | O-T2X-R | 1,784,181.0 | +0.00% | 57,092,585.7 | +0.00% | 764,834.0 | +0.00% | 31.999 |
| minecraft | ABL-Contrast-001-R | 2,003,355.0 | +12.28% | 57,025,376.0 | -0.12% | 576,046.0 | -24.68% | 28.465 |
| minecraft | ABL-ScalarWeight-001-R | 2,421,381.0 | +35.71% | 77,480,361.3 | +35.71% | 764,846.7 | +0.00% | 31.998 |

## 대기 지표

아래 값은 활성 warp 기준의 대기 비율 평균이다. 해당 이유가 전체 GPU 시간에서 차지하는 비율이 아니며 인과 기여율로 더하지 않는다.

| 장면 | 방식 | L1TEX 의존성 대기 | texture queue 대기 | branch target 대기 |
|---|---|---:|---:|---:|
| bistro | O-T2X-R | 0.894670 | 0.009863 | 0.004429 |
| bistro | ABL-Contrast-001-R | 0.782882 | 0.005743 | 0.008444 |
| bistro | ABL-ScalarWeight-001-R | 0.952789 | 0.011813 | 0.004998 |
| minecraft | O-T2X-R | 0.900887 | 0.007866 | 0.004096 |
| minecraft | ABL-Contrast-001-R | 0.858494 | 0.001883 | 0.006490 |
| minecraft | ABL-ScalarWeight-001-R | 0.883146 | 0.009165 | 0.004060 |

## 검증 범위

- 각 장면의 current/history/velocity 3개 입력 texture가 세 방식에서 모두 byte-hash 일치했다. sRGB/velocity view 형식도 같다.
- 기존 분기와 ScalarWeight의 사용 상수 버퍼가 동일하며 threshold는 float32의 0.01이다. 원본 PS에는 사용되는 상수 버퍼가 없다.
- 6 capture, capture당 temporal draw 1개, 15 counter×3회, PS Invocations 2,037,120 및 debug 오류 없음 검증.
- 동일 capture의 세 번 재생은 독립적인 장면·프레임 반복이 아니다. 단일 이동 pose의 진단으로 한정한다.
- replay GPU Duration은 results.json에 보존하되 실시간 성능 표에 합치지 않는다. 캐시 상태·draw 직렬화·계측이 실행 조건을 바꿀 수 있다.
- 활성 thread 지표는 명령 전반의 평균이며 후보 비율이나 분기 효율 그 자체가 아니다. 32 근처의 미소 초과도 원시 값 그대로 기록한다.
- 카운터는 하드웨어 명령 실행량을 제공하지만 NVIDIA SASS disassembly는 확보하지 못했다. 노출된 DXBC/AMD GCN 선택지를 NVIDIA SASS로 표현하지 않는다.
