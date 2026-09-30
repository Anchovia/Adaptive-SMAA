# 직전 raw edge 유지: 비용 원인과 동일 출력 개선

검증 브랜치: `validation/edge-persistence-cost-audit`. 렌더러 커밋: `9b9953e`.
기존 ⑥/⑦ 및 ④는 서로 다른 case다. ⑦의 개선 전후는 선택 결과·출력이 같은 구현 변형이다.

## 결과

RTX 3060 Ti, DX11 Release x64, Ultra, 1920×1061, hidden, VSync Off. 장면별 같은 실행에서
9조건을 300 warm-up + 4,800프레임 × 3회 측정했다. 반복별 정/역순을 교차했다.
PNG·readback·invocation query는 Off. 변화율은 해당 실행의 ④를 분모로 계산하며 이전 실행의 절대값을 혼용하지 않는다.

| 장면 | 구성 | 전체 AA ms | ④ 대비 | spatial ms | camera ms | temporal ms | temporal ④ 대비 |
|---|---|---:|---:|---:|---:|---:|---:|
| bistro | ④ 원본 SMAA T2X-R | 0.163014 | +0.00% | 0.104315 | 0.024496 | 0.034181 | +0.00% |
| bistro | ⑥ 현재 edge | 0.138467 | -15.06% | 0.106625 | 0.024378 | 0.007443 | -78.22% |
| bistro | ⑦ 기존 depth 전달 | 0.171373 | +5.13% | 0.136408 | 0.024492 | 0.010448 | -69.43% |
| bistro | ⑦ 개선 stencil 전달 | 0.147482 | -9.53% | 0.115345 | 0.024471 | 0.007645 | -77.63% |
| minecraft | ④ 원본 SMAA T2X-R | 0.232652 | +0.00% | 0.172612 | 0.024481 | 0.035536 | +0.00% |
| minecraft | ⑥ 현재 edge | 0.222902 | -4.19% | 0.174729 | 0.024427 | 0.023726 | -33.24% |
| minecraft | ⑦ 기존 depth 전달 | 0.251434 | +8.07% | 0.198174 | 0.024539 | 0.028700 | -19.24% |
| minecraft | ⑦ 개선 stencil 전달 | 0.240398 | +3.33% | 0.191782 | 0.024471 | 0.024124 | -32.11% |

## 비용 분리

| 장면 | 버퍼 교대 S−A | 고정 depth export K−S | union 준비 P−K | union temporal/gate B−P | 기존 ⑦−⑥ | 개선 ⑦−⑥ | 개선 ⑦ vs 기존 ⑦ |
|---|---:|---:|---:|---:|---:|---:|---:|
| bistro | -0.000068 ms | +0.028941 ms | +0.000832 ms | +0.003200 ms | +0.032906 ms | +0.009015 ms | -13.94% |
| minecraft | -0.000404 ms | +0.022050 ms | +0.001041 ms | +0.005845 ms | +0.028532 ms | +0.017496 ms | -4.39% |

원인 분리의 핵심은 K다. 후보 판정용 이전 edge/velocity 읽기나 재투영 계산을 추가하지 않고 raster depth와 같은
상수 1만 셰이더에서 출력한다. 원래 ⑥도 depth 쓰기는 켜져 있으므로 이 차이는 단순한 depth
write On/Off가 아니다. FXC 명령 슬롯은 원래 38, K는 39이며 임시 레지스터 수는 5로 같다.
고정 depth export만으로 큰 비용 증가가 재현되므로, 기존 ⑦의 추가 비용 대부분을 edge 저장/읽기의
불가피한 비용으로 설명했던 해석은 정정한다. GPU의 세부 ROP/cache stall은 별도 counter로 확인하지 않았다.

S−A 같은 작은 차이는 buffer 교대뿐 아니라 자원 주소/캐시 배치 등의 영향을 포함하며 순수 전송시간이 아니다.
P−K는 union 계산과 데이터 의존 depth 출력 패턴 차이를 포함한다. B−P는 선택 영역 확대와 depth/stencil
gate 차이를 함께 포함한다. 모든 차이를 개별 texture fetch의 독립 비용으로 환산하지 않는다.

## 개선 코드

원래 ⑦은 3차 spatial pass에서 union을 계산해 SV_Depth로 전달했다. 개선안은 1차 edge pass에서
현재 edge가 없는 위치만 이전 raw edge를 point velocity로 재투영해 검사하고 기존 stencil에 union을 표시한다.
raw RG에는 현재 프레임 edge만 저장한다. 3차 pass는 원래 NeighborhoodRetainPS로 돌아가며 temporal은
기존 early stencil 검사 뒤 native resolve를 실행한다. 추가 draw/dispatch나 color copy는 없다.

2차 spatial pass는 previous-only 위치에서도 실행되지만 raw RG=0으로 weight=0을 생성해야 한다.
이로 인한 출력 변화가 없는지 raw edge와 current spatial DDS 및 최종 RGB로 검사했다.
이는 SMAA edge 계산식, history sampler/weight/feedback, jitter/dilation을 바꾸는 품질 기법이 아니다.

## 검증 및 범위

- bistro: A/B/E/④ 각 240프레임. E−B RGB mismatch 0; A/B/④와 보존된 캡처 mismatch 0. 43개 trace에서 E/B coverage, raw RG, current spatial DDS가 같고 비선택 출력은 current spatial과 같다. Pipeline query passing samples도 coverage와 일치했다.
- minecraft: A/B/E/④ 각 240프레임. E−B RGB mismatch 0; A/B/④와 보존된 캡처 mismatch 0. 43개 trace에서 E/B coverage, raw RG, current spatial DDS가 같고 비선택 출력은 current spatial과 같다. Pipeline query passing samples도 coverage와 일치했다.
- 기존 native shader 14개 DXBC가 기준 ⑥과 같다. 복사된 4종 edge 함수는 early discard→zero return 외 계산식이 같다.
- 최초 8조건 Bistro capture 1,920프레임은 `bistro-depth-controls-capture.json`에 보존했다. A/S/K/D/P 동등성과 B/L 동등성도 240프레임으로 확인했다.
- 최종 Bistro capture 이후 변경은 harness 보고 문구/설명 주석/공백 정리였다. renderer 계산식을 수정하지 않았고 최종 benchmark EXE SHA는 source-audit와 일치한다. Minecraft는 최종 EXE로 캡처했다.
- 출력 동일성만 검증했으며 새 CGVQM 또는 품질 개선을 주장하지 않는다. 기존 ⑦에서 남아 있던 얇은 선 단절/반짝임 문제도 그대로다.
- 이 두 camera-motion 장면/해상도/GPU의 제한된 검증이다. Resize/camera cut/object motion과 다른 GPU를 포함한 범용 검증 또는 최적 속도 한계 도달을 주장하지 않는다.

## 반복별 전체 AA 변화율

| 장면 | 비교 | run 0 | run 1 | run 2 |
|---|---|---:|---:|---:|
| bistro | 개선 ⑦ vs ④ 원본 SMAA T2X-R | -9.71% | -9.25% | -9.62% |
| bistro | 개선 ⑦ vs ⑥ 현재 edge | +7.08% | +6.45% | +6.01% |
| bistro | 개선 ⑦ vs ⑦ 기존 depth 전달 | -14.02% | -13.83% | -13.97% |
| minecraft | 개선 ⑦ vs ④ 원본 SMAA T2X-R | +2.83% | +4.24% | +2.92% |
| minecraft | 개선 ⑦ vs ⑥ 현재 edge | +7.55% | +8.76% | +7.24% |
| minecraft | 개선 ⑦ vs ⑦ 기존 depth 전달 | -4.29% | -4.35% | -4.52% |

## 출처

구현 계약과 GPU 처리 원리는 [NVIDIA shader guidance](https://developer.nvidia.com/blog/advanced-api-performance-shaders/),
[Microsoft HLSL semantics](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-semantics),
[Microsoft stencil operations](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_stencil_op)를 확인했다.
[MJP의 depth export 실험](https://therealmjp.github.io/posts/to-earlyz-or-not-to-earlyz/)은 보조 근거다.
현재 pass3는 DepthFunc ALWAYS로 모든 pixel을 실행하므로 단순히 Early-Z culling 상실이라고 단정하지 않는다.
Conservative depth도 같은 선택을 유지하지만 이 구성의 주요 비용을 제거하지 못했다. 상세 조건은 [method.md](method.md).

- bistro benchmark: `C:\Users\USER\Desktop\research\tmp\worktrees\standard-t2x-reuse\Projects\CMAA2\AutoBench\20261001_034415\20261001_034415_results.csv`
- minecraft benchmark: `C:\Users\USER\Desktop\research\tmp\worktrees\standard-t2x-reuse\Projects\CMAA2\AutoBench\20261001_035634\20261001_035634_results.csv`
