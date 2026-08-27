# SMAA integrated first-pass candidate 성능 gate 결과

## 1. 목적

기존 edge-selective temporal 경로는 SMAA 공간 패스를 모두 실행한 뒤 후보를 다시
full-resolution compute pass에서 추출했다. 이 gate는 SMAA 1차 edge pixel shader가
동일 draw에서 temporal 후보를 compact하는 integrated 경로가 실제 중복 pass를 제거하고
GPU 시간을 줄이는지 확인한다.

이 구현은 Intel 공개 TSCMAA 자료의 `edge candidate compact → indirect temporal resolve`
구조를 SMAA에 적용한 연구용 adaptation이다. 유실된 Intel 원본 candidate 식을 재현한
공식 포팅으로 표현하지 않는다.

## 2. 비교 구성

reprojection Off/On 각각에서 다음 네 구성을 같은 프로세스와 교차 순서로 측정했다.

| 구성 | 의미 |
|---|---|
| `O-T2X` / `O-T2X-R` | Standard full-screen SMAA T2X control |
| `LegacyLumaRedetect` | SMAA 이후 luma에서 후보 edge를 다시 판정하는 기존 prototype |
| `SMAAFirstPassEdges` | SMAA edge RT를 후속 full-screen compute가 읽는 post-pass source |
| `SMAAFirstPassIntegratedCandidates` | SMAA 1차 edge draw에서 후보를 직접 compact하는 integrated source |

세 edge-selective 구성은 candidate source만 다르다. Standard와 edge-selective 비교는
jitter, sampler, clipping, history weight까지 다른 semantic pipeline 비교이므로 candidate
source 단독 효과로 해석하지 않는다.

## 3. 측정 조건

- GPU: RTX 3060 Ti
- API/빌드: DirectX 11, Release x64
- 해상도: 1920×1017
- SMAA: Ultra
- 장면: 저대비 Bistro, 고대비 Minecraft
- window: visible
- candidate statistics readback: Off
- mode별 300-frame warm-up, 4,800-frame 측정, 3회 반복
- 장면별 독립 clean process
- mode별 14,400 GPU timing sample과 3개 run mean

최종 원시 결과와 분석 산출물:

- Bistro: `D:\SMAA-Research-Data\AutoBench\20260828_062333`
- Minecraft: `D:\SMAA-Research-Data\AutoBench\20260828_063034`
- 분석: `D:\SMAA-Research-Data\AutoBench\20260828_IntegratedSourceOverheadFinalFormal\Analysis`

두 장면 모두 내부 sample/run/timer 검증과 clean-process 조건을 PASS했다.

## 4. 불필요한 integrated 진단 비용 제거

첫 공식 측정에서 integrated 경로가 resolve에 사용하지 않는 full-resolution base/candidate
debug mask와 indirect-args buffer까지 매 frame 초기화하고 기록하는 문제를 확인했다.

다음 최적화를 적용했다.

1. debug view 또는 candidate expansion이 켜진 경우에만 mask를 초기화·기록한다.
2. compute shader가 세 dispatch word를 모두 덮어쓰므로 indirect-args 사전 clear를 없앤다.
3. candidate compact에 필요한 candidate counter atomic은 유지한다.
4. readback-Off 본 측정에서는 선택 결과에 영향을 주지 않는 base-edge 통계 atomic만
   생략한다. readback-On에서는 기존 counter를 그대로 수집한다.

readback-On smoke에서 post-pass와 integrated의 base/candidate/process count는
reprojection Off/On 모두 정확히 일치했다. lifecycle에는 expansion 경로가 포함됐으며
122 frame, 48 reset, failure 0으로 PASS했다.

| 장면·case | 최초 integrated SMAA | mask 최적화 후 | 최종 | 최초 대비 |
|---|---:|---:|---:|---:|
| Bistro Off | 0.364229 ms | 0.332578 ms | 0.313577 ms | -13.91% |
| Bistro On | 0.401983 ms | 0.370539 ms | 0.351718 ms | -12.50% |
| Minecraft Off | 0.438940 ms | 0.406956 ms | 0.356137 ms | -18.86% |
| Minecraft On | 0.478381 ms | 0.447197 ms | 0.396614 ms | -17.09% |

서로 다른 실행의 WholeFrame 절대값은 시스템 변동 영향을 받으므로 위 단계 비교는 SMAA
GPU scope를 중심으로 기록한다.

## 5. 최종 반복 성능 결과

### Bistro

| 구성 | WholeFrame | SMAA | Wall FPS |
|---|---:|---:|---:|
| `O-T2X` | 3.105245 ms | 0.239614 ms | 314.958 |
| integrated `O-ET2X` | 3.166416 ms | 0.313577 ms | 311.967 |
| `O-T2X-R` | 3.152086 ms | 0.284371 ms | 311.251 |
| integrated `O-ET2X-R` | 3.196639 ms | 0.351718 ms | 308.469 |

- integrated는 Legacy보다 SMAA를 Off 25.148%, On 22.854% 줄였다.
- integrated는 post-pass보다 SMAA를 Off 25.709%, On 23.161% 줄였다.
- Standard semantic control 대비 integrated는 SMAA Off +30.868%, On +23.683%,
  WholeFrame Off +1.970%, On +1.413%였다.

### Minecraft

| 구성 | WholeFrame | SMAA | Wall FPS |
|---|---:|---:|---:|
| `O-T2X` | 1.288651 ms | 0.256981 ms | 752.212 |
| integrated `O-ET2X` | 1.406584 ms | 0.356137 ms | 692.178 |
| `O-T2X-R` | 1.342640 ms | 0.302068 ms | 722.943 |
| integrated `O-ET2X-R` | 1.455716 ms | 0.396614 ms | 669.216 |

- integrated는 Legacy보다 SMAA를 Off 24.654%, On 22.671% 줄였다.
- integrated는 post-pass보다 SMAA를 Off 24.854%, On 22.849% 줄였다.
- Standard semantic control 대비 integrated는 SMAA Off +38.585%, On +31.300%,
  WholeFrame Off +9.152%, On +8.422%였다.

## 6. 남은 비용

integrated 경로는 후속 candidate extraction dispatch를 제거했지만 다음 비용은 남는다.

- 현재 spatial 결과를 history로 복사: 약 0.0226~0.0230 ms
- 최종 history를 destination으로 복사: 약 0.0227~0.0239 ms
- indirect args 생성: 약 0.0040 ms
- SMAA edge pass 내부 candidate 판정과 compact atomic
- candidate별 Catmull-Rom 5-tap 및 YCoCg clipping resolve

두 full-screen copy만 합쳐 약 0.045~0.047 ms다. Minecraft에서는 integrated spatial
pass도 Standard spatial pass보다 약 0.0325 ms 더 크며, candidate resolve가 단순 bilinear
full-screen Standard resolve보다 비싸다. 후보 픽셀 수 감소가 곧바로 GPU 시간 감소로
이어지지 않는다는 점을 실제 pass timing이 확인한다.

## 7. 판정

1. integrated first-pass source는 Legacy/post-pass보다 명확히 빠르므로 앞으로의
   TSCMAA-inspired core source로 채택한다.
2. Legacy와 post-pass source는 구조 비교용 ablation으로 보존한다.
3. 불필요한 두 번째 full-screen edge extraction은 최종 core에서 사용하지 않는다.
4. 현재 integrated edge-selective pipeline은 Standard T2X보다 빠르지 않으므로
   “성능 개선 완료”로 주장하지 않는다.
5. 다음 단계의 object motion, 3×3 expansion, Adaptive 결합은 source를 integrated로
   고정하고 각각 독립 toggle/gate로 검증한다.

