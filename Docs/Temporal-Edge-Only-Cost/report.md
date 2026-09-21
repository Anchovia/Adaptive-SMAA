# T2X-R 계산 제거 후 첫-pass edge-only 비용

**T2X-R 계산을 제거한 edge-only temporal 시간은 원본보다 Bistro 52.50%,
Minecraft 53.63% 짧았다.** 기존 edge+T2X-R 결합 구현 대비로는 55.09%/57.98% 짧았다.
단, 이 진단은 현재 색상도 읽지 않고 검정색을 출력하므로 완성된 선택적 AA의 속도 개선 결과가 아니다.

| 조건 | Bistro temporal | Minecraft temporal |
|---|---:|---:|
| 원본 T2X-R | 0.033763ms | 0.035097ms |
| 기존 edge 읽기 + T2X-R | 0.035712ms | 0.038734ms |
| 출력만 | 0.015627ms | 0.015677ms |
| **edge 읽기 + 출력만** | **0.016037ms** | **0.016276ms** |
| **edge-only − 출력만** | **+0.000410ms** | **+0.000599ms** |

단독 edge 접근의 증분은 출력 대조군 대비 +2.625%/+3.821%였고, 두 장면 모두
4회 반복에서 양수였다. 출력 대조군 자체에 약 0.0156ms가 남으므로 edge-only의
약 0.016ms 전체를 edge texture를 읽는 데만 소요된 시간으로 표현하면 안 된다.
이는 공통 fullscreen 실행·출력 및 shader 상태 등을 포함한 scope다.

같은 실행의 combined−native temporal 증분은 +0.001950ms/+0.003636ms였다.
이는 edge-only−output-only와 다르다. Shader 구성, 진단 산술과 출력 내용이 달라
접근 비용을 고정된 상수로 취급하지 않는다. GPU 시간만으로 정확한 차이 원인을
cache, 대역폭 또는 register 병목 하나로 단정하지 않는다.

전체 SMAA도 원본 대비 -8.456%/-6.616%로 감소했으나 검정 출력 진단의 보조 수치다.
현재 spatial 색상을 유지하면서 후보에만 T2X-R을 수행하는 구현은 아직 추가하지 않았다.
이번 작업은 T2X-R 제거 후 남는 비용 측정까지 완료했다.

## 무엇을 제거했는가

새 진단 shader는 원본 `DX10_SMAAResolvePS`를 호출하지 않는다. Current color,
velocity, history texture 읽기와 reprojection 좌표 계산, velocity-alpha history weight,
색상 blending을 모두 제거했다. 첫-pass `edgesRT` RG Load 한 번과 출력만 남겼다.
원본 mode는 그대로 보존했고 default 동작을 바꾸지 않았다.

| 조건 | temporal shader의 실제 texture 접근 | 출력 |
|---|---|---|
| O-T2X-R | current/velocity/history 3회 | 원본 AA |
| ABL-EdgeReadOne-R | 원본 3회 + 첫-pass RG Load 1회 | 원본 AA |
| DIAG-OutputOnly | 없음 | 검정 |
| DIAG-EdgeOnly | 첫-pass RG Load 1회만 | 검정 |

edge-only와 출력-only가 같은 색상을 출력하게 하여 출력 내용 차이를 통제했다.
기존 상수 버퍼의 runtime `padding0=0`을 사용하고 다음과 같이 데이터 의존성을 남겼다.

```hlsl
// EdgeOnly: no call to the original temporal resolve
float2 edge = SMAAReadFirstEdgeLoad(position);
return float4(g_SMAA.padding0 * edge, 0.0, 1.0);

// OutputOnly: same multiplication, no texture access
return float4(g_SMAA.padding0 * g_SMAA.subsampleIndices.xy, 0.0, 1.0);
```

사용하지 않는 edge 읽기를 컴파일러가 삭제하지 않게 하는 진단용 곱셈이다.
별도 capture에서 같은 shader의 scale을 1로 바꾸면 읽은 edge RG가 그대로 출력된다.
scale 1은 본 성능 측정에 포함하지 않는다. 두 shader의 출력이 검정이므로
완성된 AA 구현 또는 품질을 유지한 최적화라고 표현하지 않는다.

## 유지한 처리와 측정 범위

실제 edge 생성과 기존 cache 상태를 유지하기 위해 SMAA spatial 1~3 pass를 계속 실행한다.
Camera-velocity 생성 및 spatial-frame history 저장/ping-pong도 upstream에서 유지한다.
따라서 **temporal shader에서 T2X-R을 제거한 것**이며 프로젝트 전체에서 관련 코드를
삭제하거나 camera velocity 생성 pass까지 제거한 실험이 아니다.
CPU-side current/history/velocity SRV 연결도 공통으로 유지하며, 새 두 mode 모두 기존 edge
SRV를 t8에 연결한다. 새 shader가 읽지 않는 SRV 연결 호출을 실제 texture fetch로 세지 않는다.

같은 fullscreen triangle, viewport, render target, format과 pass에서 비교한다.
새 production pass, 복사, 후보 목록이나 edge 선택 분기는 없다.
`EdgeOnly−OutputOnly`는 matched-output 실행에서 edge 접근 경로의 증분이다.
전체 화면 실행/출력 비용 위의 좌표 생성·Load·의존성·register/cache 및 상수 대조군 차이를
포함하므로 순수 DRAM latency 또는 완전히 독립된 데이터 전송 시간이라고 표현하지 않는다.

`Combined−EdgeOnly`는 shader 전체 구성이 달라진 비교다. 두 출력도 원본 영상/검정으로 다르다.
이를 순수 T2X-R의 개별 연산 비용으로 보거나, 원본/edge-only 시간을 선형 가산하여
후보 비율에 따른 선택적 temporal 속도를 예측하지 않는다.
특히 edge-only에는 비후보 픽셀에 필요한 현재 spatial 색상 읽기·출력도 없다.

## 검증

- Release x64 빌드 성공. 기존 native spatial/resolve R Off/On 8개 bytecode 불변.
- Combined shader의 실행 명령이 직전 실험과 동일하다.
- EdgeOnly DXBC: native sample 0, t8 RG Load 1, temp register 1.
  OutputOnly DXBC: texture resource/sample/Load 0. 두 mode 모두 원본 blending/sqrt가 없다.
- Native 20개 RGB PNG는 기존 capture와 hash 일치.
  Combined 20개는 Native와, EdgeOnly의 20개 검정 PNG는 OutputOnly와 hash 일치했다.
- Raw edge 20개 RGB PNG의 RG는 직전 edge 검증 diagnostic의 GB(원래 RG)와 pixel-exact했다.
  **40,742,400 pixel에서 edge 불일치 0**이며 모든 frame에 nonzero edge가 있었다.
  이는 실제 0/1 edge의 PNG 비교다. 임의 float의 bit 동일성 검사라고 표현하지 않는다.
- 2,400개 rendered frame의 jitter/subsample pairing 검사 통과.
  RGB PNG에는 alpha가 없으므로 alpha byte 동일성을 주장하지 않는다.
- DXBC 및 observable dataflow 검증이며 native GPU ISA/DRAM transaction 계수 검사는 아니다.

## 실행 조건

RTX 3060 Ti / DX11 / Ultra / 1920×1061 / VSync Off / hidden window.
Original SMAA / camera reprojection On / paired T2X jitter와 spatial-frame history.
60프레임 정지 + 120프레임 이동 + 60프레임 정지의 240-frame 경로를 반복한다.
Capture에서는 전체 경로를 진행하고 0/1/60/61/140/179/180/200/201/239만 저장한다.

본 측정은 각 장면 30초 공통 예열, mode별 300 warm-up, 4800 frame×4회 정순/역순 교차다.
Capture/Smoke/Benchmark는 각각 fresh process이며 clean runner가 timeout, 완료 PASS 결과와
프로세스 종료를 확인한다. 본 timing에 PNG·후보 readback·동시 CPU 영상 분석은 없다.
같은 프로세스 내 반복이며 여러 날짜/다른 GPU에 걸친 검증은 아니다.
짧은 Smoke는 기능 검증으로 보존하고 속도 결론은 반복 Benchmark에서 산출한다.

## 자료와 재현

- [사전 계획](method.md), `shader-validation.json`: 범위와 compiler 검증.
- `*-capture.json`: 실제 edge 및 화면 검증, 실행 영수증과 hash.
- `*-Benchmark.json`, [tables.md](tables.md), `comparisons.json`: 평균, 반복 편차/차이,
  표본 수와 p95/p99, 실행 조건.

브랜치 `experiment/temporal-edge-only-cost`, 시작점 `b97d7a0`,
사전 계획 `ecc1e8a`, 구현·shader 검증 `8ac49fc`.
`validate_temporal_edge_only.py`, Release 빌드 후 `run_temporal_edge_only.ps1`로
Capture/Smoke/Benchmark와 bistro/minecraft를 각각 실행한다.
`analyze_temporal_edge_only.py`의 해당 phase/scene 및 Summary로 결과를 검사한다.
재실행은 runner `-Receipt`, analyzer `--receipt`와 `--output`으로 기존 자료와 분리한다.
원시 PNG·AutoBench·EXE는 Git에 포함하지 않는다.
