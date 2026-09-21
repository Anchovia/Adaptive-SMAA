# 2차 패스 결과를 temporal에서 읽는 비용

기존 SMAA 2차 패스의 blend texture를 temporal에서 한 번 읽되, 원본 T2X-R의 출력을
그대로 유지하는 진단을 구현했다. 후보 선택·분기·품질 개선 기능은 넣지 않았다.
새 패스나 데이터 복사 없이 기존 GPU texture를 다시 읽는 실험이다.

**추가 읽기 경로의 temporal 비용은 대조군 대비 Bistro +5.46%, Minecraft +9.13%였다.**
네 반복 모두 증가했다. 원본 대비로는 측정용 산술까지 포함해 temporal +5.83%/+9.43%,
전체 SMAA +1.25%/+1.43%다. 읽기를 추가하는 비용은 있지만, 아래에 설명한 측정용 의존성과
실제 cache 상태를 포함한 값이며 순수한 메모리 전송 시간이라고 부르지는 않는다.

## 무엇을 비교했는가

브랜치는 `experiment/temporal-blend-weight-selection`, 시작점은 `f3f42cf`다.
설계는 `caa48f2`, 진단 구현은 `427c0ae`에 분리했다. 이전 선택식 실험은 그대로 보존한다.

| 조건 | 추가한 작업 |
|---|---|
| O-T2X-R | 없음. 원래 전체 화면 resolve |
| ABL-BlendBindOnly-R | 기존 blendRT의 SRV 연결/해제만 추가. 원래 shader |
| ABL-BlendReadControl-R | 같은 연결 + 읽기를 유지하기 위한 산술의 대조군 |
| ABL-BlendReadOne-R | 같은 연결·산술 + 현재 위치의 blendRT RGBA 한 번 Load |

2차 패스의 RGBA8_UNORM blendRT는 이미 GPU에 있다. `PSSetShaderResources`로
기존 SRV를 t9에 연결하며 CPU→GPU 전송이나 새 texture 복사는 하지 않는다.
2차 출력의 blend weight를 읽는 것이고, 1차 RG edge texture와는 다른 자원이다.
3차 패스의 이웃 가중치 모으기나 후보 정책은 구현하지 않았다.

사용하지 않는 Load는 컴파일러가 제거할 수 있다. 그래서 기존 상수 버퍼의 runtime 값
`padding0=0`을 이용해 다음과 같이 결과에 연결했다.

```text
native = originalT2XR(...)
probe  = blendRT.Load(currentPixel)
output = native + runtimeZero * probe
```

Control은 probe 대신 기존 cbuffer의 float4를 사용한다. One과 Control은 마지막 vector MAD가
같고 One에 정수 좌표 생성과 t9 Load가 추가된 것을 FXC DXBC에서 확인했다.
그러므로 **One−Control은 읽기 경로의 증분 대용값**, **One−Native는 측정용 산술까지 포함한
관측 추가 비용**이다. 메모리 지연만 완벽히 분리한 값은 아니다. 좌표 계산, 의존성,
register/cache 영향과 probe source 차이를 포함한다. Control/One은 ps_5_0이고
Native/BindOnly는 기존 shader profile을 유지한다. 같은 결과라도 최종 GPU 기계어의 동치를
주장하지 않으며, 순수 읽기 비교의 중심은 같은 profile인 One−Control이다.

본 측정은 scale 0이다. 별도 캡처에서 같은 One shader에 scale 1을 넣어 읽은 값이 실제
출력에 영향을 주는지도 검사했다. 이 진단 결과는 성능·품질 비교에 포함하지 않는다.
DXBC 명령 보존은 확인했지만 Nsight의 native ISA/DRAM 거래 계수 검증은 아니다.

## 정확성 및 실행 조건

- Release x64 빌드 통과. 초기 파일 BOM/함수 선언 순서 문제는 컴파일 단계에서 수정했고
  GPU 실행 전에 FXC 검사를 통과했다.
- 기존 spatial 3개와 temporal shader의 R Off/On 8개 bytecode 불변.
- 새 대조군·읽기와 Native의 R Off/On 6개 variant 검사. R On의 기존 sample 3개는 유지하고
  One에만 t9 Load 1개 존재. 후보 분기, 미분, UAV 쓰기는 추가하지 않았다.
- 두 장면에서 새 3개 경로×10 frame, 총 60개 PNG가 원본과 byte/hash 일치했다.
  Native 20개도 이전 고정 경로 캡처와 hash 일치했다. 첫 frame과 이동·정지 전환을 포함한다.
  PNG 형식은 RGB다. Alpha는 저장하지 않으므로 alpha byte 일치 검사라고 부르지 않는다.
- 총 2,400개 rendered frame의 jitter/subsample pattern 검사 통과. scale 1 진단은 두 장면의
  모든 저장 frame에서 출력에 영향을 주었다. 불일치·무효 texture를 0비용으로 측정하지 않았다.

Original spatial SMAA / camera-depth reprojection On / paired jitter / native Point sampling /
원래 velocity-alpha weight / spatial-frame history다. Object motion, Adaptive와 이전-depth 거부는
추가하지 않았다. 최종 8-case를 바꾸지 않는 default-Off engineering 실험이다.

RTX 3060 Ti, DX11, Ultra, 1920×1061, VSync Off, hidden window다.
기존 flythrough t=2, 60 still + 120 moving + 60 still의 240-frame period를 사용한다.
품질 순위를 새로 측정하지 않고 출력 불변만 검사했다. 각 mode의 전체 240 frame은 렌더하되
0/1/60/61/140/179/180/200/201/239만 PNG로 보존했다. 전체 입력 공간의 동치 증명은 아니다.

각 장면의 smoke 후 30초 공통 예열, mode당 300-frame warm-up, 4,800 frame×4회로
순서를 정방향/역방향 교차했다. GPU 성능 실행에 PNG, 진단 출력이나 후보 readback은 없다.
CPU 캡처 분석은 성능 실행과 분리했다. 명령마다 fresh process이며 종료와 완성된 PASS report를
clean runner가 검사한다. 같은 프로세스 내 4회이지 독립 날짜·여러 GPU 검증이 아니다.
짧은 smoke는 미변경 spatial 구간도 첫 mode에서 다르게 나와 검증용으로만 보존한다.

## 반복 측정 결과

| 장면 | 원본 temporal ms | 연결만 ms | 산술 대조군 ms | 실제 읽기 ms |
|---|---:|---:|---:|---:|
| Bistro | 0.033244 | 0.033279 | 0.033359 | 0.035182 |
| Minecraft | 0.034870 | 0.034870 | 0.034965 | 0.038158 |

| 장면 | 읽기−대조군 temporal | 원본 대비 temporal | 원본 대비 전체 SMAA |
|---|---:|---:|---:|
| Bistro | +0.001823 ms / +5.46% | +0.001938 ms / +5.83% | 0.209777→0.212409 ms / +1.25% |
| Minecraft | +0.003194 ms / +9.13% | +0.003288 ms / +9.43% | 0.282799→0.286847 ms / +1.43% |

동일 repeat의 읽기−대조군 temporal 차이는 Bistro +0.001789~+0.001848 ms,
Minecraft +0.003133~+0.003260 ms로 네 번 모두 양수였다. 차이의 run SD는 각각
0.000027/0.000057 ms다. 정해진 두 장면에서 반복적으로 관측한 비용이며,
다른 GPU·해상도 또는 별도 날짜의 통계적 일반화를 주장하지 않는다.

BindOnly−Native의 temporal 평균은 Bistro +0.10%, Minecraft +0.001%이며
반복별 부호가 섞인다. 큰 증가가 확인된 곳은 SRV 연결만 한 조건이 아니라 실제 Load를 넣은 조건이다.
산술 대조군−BindOnly는 +0.24%/+0.27%다. Binding과 산술을 생략해서도
One−Control의 약 5.5~9.1%를 원본 대비 전체 읽기 비용이라고 잘못 표시하지 않는다.

전체 SMAA에는 미변경 spatial 구간의 반복 변동도 포함된다. WholeFrame은
One−Control에서 장면별 방향이 달라, 전체 프레임의 고정된 증가율로 해석하지 않는다.
Median/p95/p99, WallFrame/1% low와 모든 repeat 수치는 Benchmark JSON 및 전체 표에 있다.

## 해석 범위

측정 대상 texture는 직전 3차 패스에서도 사용했다. 이번 비용은 실제 파이프라인의 cache 상태와
동시 실행에 따른 비용이다. texel byte 수를 DRAM 전송량으로 환산하거나 일반 대역폭 상수로 쓰지 않는다.
BindOnly의 GPU timestamp/WallFrame 차이도 API의 CPU 호출 지연만 독립 측정한 수치는 아니다.

앞선 1차 edge-mask 선택의 temporal +8.45%/+31.32%와 직접 빼서 분기 비용을 구할 수 없다.
그 실험은 RG edge 자원, 후보 판정과 early return, 다른 해상도·경로·window 조건을 포함한다.
이번 자료는 “다른 패스의 결과를 한 번 읽는 것만으로 드는 추가 비용”에 가까운 대조 실험이며
edge 선택 버전의 병목을 모두 설명하는 결과가 아니다.

원본과 같은 RGB 출력을 확인했고 history 저장 경로도 수정하지 않았으므로 품질 향상을 주장하지 않는다.
Shader 식은 finite 입력에서 alpha도 보존하지만, 별도 alpha readback 검증을 수행한 것은 아니다.
읽기 비용이 작거나 크다는 것만으로 향후 후보 선택의 성능·품질을 보장하지 않는다.

## 재현 자료

- [실험 설계와 공식 API 근거](method.md)
- [shader 명령 검증](shader-validation.json)
- [Bistro 출력 검증](bistro-capture.json), [Minecraft 출력 검증](minecraft-capture.json)
- [반복 성능 전체 표](tables.md), [짝 비교 수치](comparisons.json)

`Tools/SMAA/run_temporal_blend_read.ps1 -Phase Capture|Smoke|Benchmark -Scene bistro|minecraft`를
새 receipt와 함께 실행한다. `analyze_temporal_blend_read.py --scene <scene> --phase <phase>`로
각 결과를 검사하고 `--phase Summary`로 검증된 JSON만 집계한다. 기존 receipt는 중복 실행을 거부한다.
빌드/컴파일 검사는 `validate_temporal_blend_read.py`를 사용한다.
Raw AutoBench 보고서/PNG와 실행파일은 Git에 포함하지 않는다. 실행 ID, 실행파일 및 report SHA256은
각 JSON의 receipt에, 비교 PNG hash는 capture JSON에 보존한다.
