# 1차 edge 결과를 temporal에서 읽는 추가 비용

Original SMAA 1차 패스가 검출한 edge texture를 기존 temporal pass에서 그대로
읽는 진단을 구현했다. 새 pass, texture 복사, 후보 판정, 분기, temporal 생략은 없다.
이전 luma 미분 선택식이나 2차 blending weight와 다른 실험이다.

**원본 대비 temporal 시간은 Bistro +5.67%, Minecraft +10.16% 증가했다.**
절대 증가량은 각각 약 0.001895ms/0.003592ms이며 진단용 산술을 포함한다.
같은 산술 대조군과 비교한 읽기 경로의 증분은 +5.57%/+10.09%다.
원본 대비 전체 SMAA는 +1.01%/+1.46%였다. 읽기 추가 비용은 확인됐지만,
이는 선택적 temporal 완성 구현의 속도나 순수 메모리 전송 시간은 아니다.

| 장면 | 원본 temporal | 연결만 | 산술 대조군 | edge 읽기 | 원본 대비 temporal | 원본 대비 전체 SMAA |
|---|---:|---:|---:|---:|---:|---:|
| Bistro | 0.033390ms | 0.033378ms | 0.033421ms | 0.035284ms | +5.67% | +1.01% |
| Minecraft | 0.035349ms | 0.035321ms | 0.035373ms | 0.038941ms | +10.16% | +1.46% |

| 장면 | 읽기−대조군 temporal 증분 | 반복 차이의 표준편차 | 4회 차이 범위 |
|---|---:|---:|---:|
| Bistro | +0.001863ms (+5.57%) | 0.000046ms | +0.001817~+0.001918ms |
| Minecraft | +0.003568ms (+10.09%) | 0.000091ms | +0.003487~+0.003659ms |

연결만 한 temporal 차이는 -0.035%/-0.077%로 반복마다 부호가 달라, 측정에서
일관된 증가를 구분하지 못했다. 이는 CPU API 비용이 0임을 증명하지 않는다.
읽기−대조군의 temporal/SMAA 차이와 읽기−원본의 temporal/SMAA 차이는 모두
두 장면 각각 4회 양수였다. WholeFrame 차이는 다른 렌더링 구간의 변동도 포함하므로
읽기 지연의 직접 근거로 사용하지 않는다.

## 무엇을 측정했는가

| 조건 | temporal에 추가한 작업 |
|---|---|
| O-T2X-R | 없음. 원래 전체 화면 T2X-R |
| ABL-EdgeBindOnly-R | 원래 shader에 기존 edgesRT SRV 연결/해제만 추가 |
| ABL-EdgeReadControl-R | 같은 연결 + RG 두 채널의 runtime-zero 산술 |
| ABL-EdgeReadOne-R | 같은 연결·산술 + 현재 정수 좌표의 실제 edge RG 한 번 Load |

이미 1차 패스가 GPU에 저장한 texture를 t8에 연결한다. CPU→GPU 전송이나
다른 texture에 다시 저장하는 작업이 아니다. 현재 픽셀의 검출 결과 RG를 그대로
shader 값으로 읽으며, 새 edge 판정식·threshold·필터를 적용하지 않는다.
이 wrapper는 adapterDesc와 ExternalStorage를 지정하지 않아 `edgesRT`는 RG8_UNORM이다.
SMAA.cpp에 있는 NVIDIA용 RGBA8 분기는 adapterDesc=nullptr인 이 경로에서 실행되지 않는다.
Temporal draw 전에 render target을 해제하고 최종 색상 target을 설정하므로 edgeRT의
동시 SRV/RTV 사용은 없다. draw 후 t8 연결을 해제한다.

아무 데도 쓰지 않는 읽기는 컴파일러가 제거할 수 있다. 이를 방지하기 위해
다음 진단을 사용했다. runtimeZero는 기존 상수 버퍼의 padding0이며 측정 중 0이다.

```text
native = originalT2XR(...)
edgeRG = edgesRT.Load(currentPixel).rg
output.rg = native.rg + runtimeZero * edgeRG
output.ba = native.ba
```

Control은 edgeRG 대신 기존 상수 RG를 사용한다. **One−Control**은 texture 읽기,
좌표 생성, 의존성·register/cache와 probe 출처 변경을 포함한 증분 추정치다.
**One−Native**는 진단용 산술까지 포함한 실제 관측 증가량이다. 순수 DRAM 지연으로
해석하지 않는다. Native/BindOnly는 원래 shader profile, Control/One은 ps_5_0이므로
읽기 분리의 중심은 같은 profile의 One−Control이다. DXBC는 확인했지만
GPU native ISA/실제 DRAM transaction 수를 새로 측정한 실험은 아니다.

별도 capture에서 runtimeZero를 1로 바꿔 같은 Load가 화면에 영향을 주는지도 확인했다.
이 진단 출력은 본 timing과 품질 비교에서 제외한다.

## 출력·빌드 검증

- Release x64 빌드 성공. 기존 spatial 3개 및 resolve의 reprojection Off/On,
  총 8개 shader bytecode가 기존 기준과 동일하다.
- 새 shader와 Native의 Off/On 6개 variant에서 기존 texture sample 2/3회를 유지했다.
  One에만 t8 Load 한 번과 RG 사용이 존재한다. 추가 후보 분기·미분·UAV 쓰기는 없다.
- Bistro/Minecraft 각각 10 frame × 3개 zero-scale 진단, 총 60개 PNG가 Native와
  파일 hash까지 일치했다. Native 20개도 이전 고정 경로 capture와 일치했다.
- PNG는 RGB이며 alpha는 저장하지 않는다. Alpha 불변은 shader 구조/DXBC로 확인하며
  PNG alpha byte 일치라고 표현하지 않는다. 전체 입력 공간의 동치 증명도 아니다.
- 2,400개 rendered frame의 jitter/subsample pairing 검사가 통과했다.
  scale 1의 20개 저장 frame 모두 RGB 변화가 있어 실제 입력 사용도 확인했다.

## 실행 조건과 결과 해석

Original spatial SMAA, camera/depth reprojection On, paired jitter/subsample pattern,
원래 Point sampling과 velocity-alpha 혼합 가중치 및 spatial-frame history를 유지했다.
Object velocity, Adaptive, resolved-output feedback, clipping은 추가하지 않았다.
최종 8-case를 변경하지 않는 default-Off 진단이다.

RTX 3060 Ti / DX11 / Ultra / 1920×1061 / VSync Off / hidden window에서 실행했다.
경로는 기존 60프레임 정지 + 120프레임 이동 + 60프레임 정지의 반복이며,
capture는 전체 240프레임을 진행하고 지정한 10프레임만 저장했다.
본 측정은 장면마다 30초 공통 예열, 조건별 300 warm-up,
4,800프레임 × 4회 정순/역순 교차다. 동일 프로세스 내 반복이며
독립 날짜 또는 여러 GPU에 걸친 검증은 아니다.

각 명령은 별도 clean process로 실행했고 완성된 PASS 결과와 프로세스 종료를 검사했다.
성능 실행에는 PNG·후보 카운터 readback이 없고 CPU 영상 분석도 동시에 수행하지 않았다.
짧은 smoke에서는 변경하지 않은 spatial 구간도 첫 조건에서 낮게 나왔으므로
기능 검증으로만 보존하며 속도 결론은 반복 본 측정에서 산출한다.

평균·반복 표준편차·반복별 차이는 [tables.md](tables.md), 원본 표본 통계와 실행
영수증은 장면별 `*-Benchmark.json`, 출력 검증은 `*-capture.json`에 보존한다.
이전 first-edge 선택 실험의 +8.45%/+31.32%는 읽기 외에 판정·분기·temporal 생략까지
포함하며 해상도/실행 조건도 달라 이번 값에서 직접 빼 분기 비용을 추정할 수 없다.

이번 결과만으로 edge 선택 방식의 채택/폐기를 확정하지 않는다. 읽기 자체의 추가 비용을
알았으므로, 선택으로 절약할 수 있는 temporal 비용이 이를 상쇄하는지 같은 조건에서
따로 검증할 수 있다. 이는 다음 후보 선택 실험의 기준이며 이번에는 구현하지 않았다.

## 재현과 기록

브랜치 `experiment/temporal-edge-read-cost`, 시작점 `178e6b5`.
설계 커밋 `a916cad`, 진단 구현 및 shader 검증 커밋 `4e1feff`.
재현 순서는 `validate_temporal_edge_read.py`, Release 빌드,
`run_temporal_edge_read.ps1 -Phase Capture|Smoke|Benchmark -Scene bistro|minecraft`,
`analyze_temporal_edge_read.py --phase Capture|Smoke|Benchmark --scene ...`,
마지막 `--phase Summary`다. 이 표기에서 |는 선택지를 뜻한다.
기존 receipt와 중복 scene/phase 실행은 거부하므로 재실행 자료는 별도 receipt/출력으로 보존한다.
재실행 시 runner의 `-Receipt`, analyzer의 `--receipt`를 같은 경로로 지정하고
analyzer의 `--output`으로 기존 결과와 분리한다.
API 근거와 사전 계획은 [method.md](method.md)에 기록했다.
