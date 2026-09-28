> **2026-09-28 정정 / 연구 결론 철회:** 본 자료의 No-TAA는 일반 SMAA 1X가 아니라 지터 On current-spatial 진단이다. 일반 SMAA 대비 품질 우위 및 연구 구현 채택의 근거로 사용하지 않는다. 기존 raw data는 당시 조건의 기록으로 보존하며, baseline/smaa-t2x에서 별도 기준선 재검증을 시작한다. 속도 수치도 당시 지터 On 구현에만 해당한다.

# 실제 첫-pass edge 선택 T2X-R 결과

현재 색상을 분기 전에 공통으로 읽는 Reuse는 이전 edge-first 구현과 RGB 출력이 같고,
temporal 시간이 Bistro 14.341%, Minecraft 13.607% 감소했다. 두 장면 모두 4회 전부 감소했다.
원본 전체 화면 T2X-R 대비로는 Bistro temporal -15.958%, 전체 SMAA -2.478%지만,
Minecraft temporal +8.844%, 전체 SMAA +1.234%다. 각 장면에서 이 부호는 4회 모두 유지됐다.
따라서 이전 선택적 구현의 속도 개선은 확인했으며, 원본보다 항상 빨라야 한다는 목표는
아직 달성하지 못했다. 기본 원본 경로는 변경하지 않고 실험 mode로 보존한다.

전체 frame 시간은 GPU pass 외의 변동도 포함한다. 특히 Bistro Reuse−Native WholeFrame과
Reuse−Legacy WholeFrame은 반복별 부호가 섞였다. 이 gate에서 전체 FPS 향상을 확정하지 않는다.
Warp 효율/실제 texture transaction 계측은 없으므로 Minecraft의 원인을 분기 발산이나
cache 하나로 단정하지 않는다. 이후 검토 시에도 edge 읽기와 조건부 temporal 실행을 구분한다.

## 동일 실행의 반복 측정

| 방식 | Bistro temporal (ms) | Minecraft temporal (ms) |
|---|---:|---:|
| O-T2X-R | 0.033334 | 0.034849 |
| ABL-EdgeReadOne-R | 0.035282 | 0.038516 |
| DIAG-CurrentEdge | 0.020433 | 0.023698 |
| ABL-FirstEdge-Reuse-R | 0.028014 | 0.037930 |
| ABL-FirstEdge-Legacy-R | 0.032705 | 0.043904 |

| 비교: 새 Reuse − 기준 | Bistro temporal | Minecraft temporal | Bistro 전체 SMAA | Minecraft 전체 SMAA |
|---|---:|---:|---:|---:|
| O-T2X-R | -15.958% | +8.844% | -2.478% | +1.234% |
| DIAG-CurrentEdge | +37.106% | +60.059% | +3.855% | +5.171% |
| ABL-FirstEdge-Legacy-R | -14.341% | -13.607% | -2.256% | -2.043% |

부호가 양수이면 시간이 늘어난 것이다. Read-only current control에는 zero sink가 있고
선택적 shader에는 없으므로 차이를 순수 branch 비용으로 표현하지 않는다.
원본과 동일 출력인 것은 edge+native read control이며, 선택적 출력은 비edge에서 원본과 달라진다.
이번 gate는 출력 선택 정확성과 성능이며 정량 품질 우위를 검증하지 않았다.

## 선택 비율과 출력 정확성

- bistro: sparse 10 frame 평균 선택 53,595.6 / 2,037,120 pixel (**2.6309%**), frame별 50,468~56,119 pixel.
- minecraft: sparse 10 frame 평균 선택 326,774.7 / 2,037,120 pixel (**16.0410%**), frame별 131,989~516,585 pixel.

후보 비율은 frame 0/1/60/61/140/179/180/200/201/239의 capture 통계다.
전체 benchmark 평균 또는 처리 warp 비율로 표현하지 않는다. 원본은 전체 화면에서 resolve한다.

- 실제 첫-pass RG>0만 선택하며 새 luma 대비 근사나 다른 threshold를 사용하지 않는다.
- 두 장면 총 40,742,400 pixel에서 selected RGB=native, nonselected RGB=current exact 검증 mismatch 0.
- Legacy/Reuse/Reuse-repeat RGB PNG hash 일치. 기존 native 20장 및 current+edge control 20장의 역사적 bridge 일치.
- Raw edge는 직전 gate의 raw RG와 exact 일치. Rendered-frame 3,840개의 jitter/subsample pattern 검사 PASS.
- RGB PNG에는 alpha가 없다. Alpha GPU byte hash 일치를 주장하지 않는다.

## 구현과 compiler 검증

새 `DX10_SMAAFirstEdgeReusePS`는 current color를 먼저 한 번 읽고 edge Load 후 비edge에서 반환한다.
Edge에서는 원본과 동일한 velocity, point history, velocity-alpha weight 0..0.5와 lerp를 수행한다.
Camera/depth reprojection, spatial-frame history, paired jitter 및 spatial 1~3 pass는 유지했다.
Object motion, clipping, history feedback topology 변경이나 후보 확장은 이번 범위에 없다.
새 pass, texture, buffer, copy, indirect dispatch도 추가하지 않았다.

이전 edge-mask 함수 본문은 이름만 바꿔 `DX10_SMAAFirstEdgeLegacyPS`로 가져왔다.
Legacy의 current 읽기 instruction은 두 경로에 있지만 각 pixel은 한 경로만 탄다.
따라서 이전 구현이 매 pixel의 current를 두 번 읽었다고 설명하지 않는다.
Reuse는 current 읽기를 분기 전에 공통 수행하는 배치 변경이다. 두 R-On DXBC 모두 temp 3과 23 instruction slot이다.
컴파일 결과에는 비edge early return이 있고 velocity/history 읽기는 그 뒤에 위치한다.
선택 pixel 비율만으로 실제 warp 실행이나 memory transaction 감소량을 단정할 수 없다.

Native spatial/resolve R Off/On 8개 DXBC와 두 read-only control 실행 명령은 불변이다.
R Off도 compiler 검증했지만 이번 GPU capture/timing은 R On만 수행했다.
Release x64, 두 장면 capture와 smoke를 통과한 후 benchmark를 실행했다.

Microsoft [HLSL if/branch](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if)와
[Texture Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load)를 근거로 구현하고
DXBC 분기/읽기 위치를 검사했다. 이 검사는 GPU ISA/warp 효율 계측이나 속도 보장이 아니다.

## 실행 조건과 제한

RTX 3060 Ti / DX11 / Ultra / 1920×1061 / VSync Off / hidden window.
240-frame 고정 경로(60 still + 120 move + 60 still), 30초 예열, mode별 300 warm-up,
4,800 frame × 4회 정방향/역방향 교차. Capture/Smoke/Benchmark는 독립 fresh process이며
완료 PASS 보고서와 잔류 process 0을 확인했다. 본 측정에 PNG·후보 readback·CPU 이미지 분석은 없다.
모든 반복과 분포를 보존한다. 단일 GPU/같은 프로세스 내 반복이며 독립 날짜 재현은 아니다.
Hidden engineering 결과로, 논문용 visible-window FPS 측정을 대체하지 않는다.

과거 edge-mask 결과와 해상도 및 경로가 달라 절대 시간을 직접 비교하지 않는다.
현재 표의 Legacy가 동일 조건에서 다시 실행한 과거 함수 대조군이다.
비edge에서는 paired jitter를 temporal 결합으로 안정화하지 않는다. 이전에 관찰한 떨림 문제를
해결했다고 주장하지 않으며 속도 결과와 품질 판정을 분리한다.

## 재현 자료

브랜치 `experiment/temporal-first-edge-selective`, 시작점 `13afeb2`.
계획 `c7bd505`, 구현/출력 검증 `6ec251c`. `method.md`, `shader-validation.json`,
`*-capture.json`, `*-Smoke.json`, `*-Benchmark.json`, `tables.md`, `comparisons.json`에 자료를 보존했다.
`validate_temporal_first_edge.py`와 Release 빌드 후 `run_temporal_first_edge.ps1`로
Capture/Smoke/Benchmark를 장면별 실행하고 `analyze_temporal_first_edge.py`로 각 결과와 Summary를 검증한다.
재실행은 별도 `-Receipt`, `--receipt`, `--output`을 사용한다. 원시 PNG/AutoBench/EXE는 Git에 넣지 않는다.
