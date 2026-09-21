# 동일한 첫-pass edge RG의 읽기 방식 비교

**검토한 읽기 명령 교체·소스 순서 변경에서는 뚜렷한 전체 SMAA 속도 개선을 확인하지 못했다.**
Point의 temporal 평균 감소는 Bistro 0.108%, Minecraft 0.157%로 매우 작았다.
Bistro는 temporal 차이 자체가 반복마다 부호가 바뀌었고, 두 장면 모두 전체 SMAA 차이가
반복마다 바뀌었다. 기존 Load를 기준 경로로 유지하고 Point는 동일성 검증을 통과한
진단 옵션으로만 보존한다. 이번 합의 범위의 검토는 완료했으며 모든 가능한 GPU 최적화가
불가능하다는 증명으로 확대하지 않는다.

| 장면 | Load temporal | Point temporal | Point−Load | 전체 SMAA 평균 차이 |
|---|---:|---:|---:|---:|
| Bistro | 0.035471ms | 0.035433ms | -0.000038ms (-0.108%) | -0.037% |
| Minecraft | 0.038623ms | 0.038562ms | -0.000061ms (-0.157%) | -0.043% |

Temporal의 Point−Load 반복 차이는 Bistro에서 +0.000172/-0.000215/+0.000135/-0.000245ms,
Minecraft에서 -0.000073/-0.000017/-0.000094/-0.000058ms였다.
Minecraft의 temporal은 4회 모두 감소했으나 약 0.000061ms의 작은 차이다.
전체 SMAA는 두 장면 모두 2회 증가/2회 감소하여 일관된 개선으로 주장하지 않는다.

읽기 비용 자체도 남아 있다. 같은 실행의 산술 대조군 대비 Point temporal은
Bistro +5.427%, Minecraft +10.329%였다. 원본 대비는 진단용 산술까지 포함하여
+5.540%/+10.438%다. 명령 교체만으로 edge 접근 오버헤드가 사라지지 않았다.
이전 실험의 절대 시간과 직접 빼서 개선량을 계산하지 않고 이번 실행 안의 대응 차이를 사용했다.

## 이번 작업의 범위

기존 `Temporal-Edge-Read-Cost` 실험을 이어서, 첫 spatial pass의 같은 edge texture에서
같은 픽셀의 RG를 읽는 비용을 줄일 여지가 있는지 검토했다.
픽셀 선택, temporal 생략, 새 production pass/복사/texture는 추가하지 않았다.
원본 T2X-R, camera/depth reprojection On, paired jitter와 spatial-frame history를 유지한다.

## 검토한 변경과 컴파일 결과

- 기존: `edgesTex.Load(int3(int2(position.xy),0)).rg`
- 비교: `edgesTex.SampleLevel(PointSampler,uv,0).rg`
- 두 방식에서 읽기를 원본 resolve 호출 앞으로 옮긴 버전도 컴파일했다.
  R On의 EarlyLoad는 Load와, EarlyPoint는 Point와 실행 명령이 정확히 같았다.
  따라서 단순 소스 순서 변경은 별도 GPU 성능 측정에서 제외했다.

Point는 기존 UV와 기존 Point+Clamp sampler를 활용한다. 같은 RG8_UNORM resource,
mip 0이며 두 채널을 모두 읽는다. Load의 정수 변환(ftoi)과 좌표 zw 초기화가 없어지고
Load 대신 SampleLevel 한 번이 생성됐다. R On의 DXBC temp register 선언은 양쪽 모두 3이다.
기존 current/velocity/history 접근 세 번과 runtime-zero sink 산술은 유지한다.
이는 DXBC 분석이며 GPU native register allocation, scheduling 또는 cache/DRAM 계수 측정은 아니다.

## 읽는 값의 동일성

`0 × edge`를 더한 최종 출력만 같아서는 읽은 값이 같다는 증명이 되지 않는다.
따라서 다음 검증을 별도로 수행했다.

1. **공통 접근 함수:** renderer와 독립 GPU probe가 `TemporalEdgeAccess.hlsl`의
   같은 Load/Point 함수를 사용한다.
2. **독립 raster GPU 검사:** production과 같은 fullscreen triangle 위치/UV,
   origin-zero viewport, RG8 resource와 Point+Clamp를 사용했다. RGBA32_FLOAT 출력에
   Load RG와 Point RG를 직접 기록하고 readback에서 두 float 쌍을 비트 단위로 비교했다.
   1×1, 3×5, 1919×1061, 1920×1061, 1920×1080의 5해상도,
   임의 RG8/이진 edge의 2패턴, 서로 다른 입력 2phase로 총 20 fixture다.
   **24,587,180 pixel에서 RG bit mismatch 0, border mismatch 0**이었다.
   CPU가 생성한 texel과 Load 결과도 UNORM 변환 오차 허용 1e-7 이내로 일치했다.
   이 fixture의 phase는 입력 패턴 변화이며 카메라 jitter 재현이라고 부르지 않는다.
3. **실제 장면 검사:** Bistro/Minecraft의 기존 240-frame 경로를 렌더하며 10 frame씩
   저장했다. 진단 shader는 같은 pixel의 Load/Point RG를 직접 비교해 mismatch를
   R=1/0, 원래 edge RG를 GB로 출력한다. 20개 전체 화면,
   **40,742,400 pixel에서 mismatch 0**이며 모든 저장 frame에 실제 nonzero edge가 있었다.
   frame 0/1, 60/61, 140, 179/180, 200/201, 239로 첫 frame·이동·정지와 jitter 두 위상을 포함한다.
4. **기준선 유지:** 원본 8개 spatial/resolve R Off/On shader bytecode 불변.
   기존 Load 실행 명령 불변. 새 3개 진단×10 frame×2장면의 60개 RGB PNG가 Native와
   파일 hash까지 같고, Native 20개도 이전 capture와 일치했다.
   2,400개 rendered frame의 jitter/subsample pairing 검사도 통과했다.
   PNG는 RGB만 저장하므로 alpha byte 동일성으로 표현하지 않는다.

독립 probe는 timing과 분리된 별도 검증 프로그램이다. 실제 화면 검사도 capture-only이며
production 성능 측정에 두 번의 edge 읽기나 readback을 넣지 않는다.
Load의 out-of-bounds zero와 Point Clamp는 일반적으로 다르다. 이번 동치는
현재 pass의 in-bounds pixel-center 접근 범위에 해당하며 임의 UV에 일반화하지 않는다.

## 측정 방법

Native / sink Control / Load / Point의 네 조건을 동일 프로세스에서 비교한다.
RTX 3060 Ti, DX11, Ultra, 1920×1061 hidden window, VSync Off 조건이다.
각 장면은 30초 공통 예열, 조건별 300 warm-up과 4,800 frame×4회 정순/역순 교차를 사용한다.
경로는 60프레임 정지 + 120프레임 이동 + 60프레임 정지의 반복이다.
PNG·진단 mask·후보 readback 및 CPU 영상 분석은 본 성능 실행과 분리한다.
각 Capture/Smoke/Benchmark는 fresh process이며 runner가 timeout/완료 보고서/프로세스 종료를 검사한다.

핵심 비교는 **Point−Load**다. 둘 모두 같은 RG를 실제로 읽고 같은 진단 산술을 수행한다.
Read−Control은 접근 경로의 증분 추정치이며 Read−Native는 진단용 산술까지 포함한다.
이를 순수 DRAM 전송 시간으로 표현하지 않는다. 시간 변동과 부호는 반복별로 보존한다.
짧은 Smoke의 첫 조건에서 미변경 spatial 구간도 낮게 나타나므로 Smoke를 속도 결론에 쓰지 않는다.

## 자료와 재현

- `shader-validation.json`: 원본 보존, 순서 변경 후보 중복, DXBC 명령 전체.
- `raster-probe.json`: 독립 GPU float RG 비교, CPU texel 검사와 소스/실행 파일 hash.
- 장면별 `*-capture.json`: 직접 edge 비교, 최종 RGB/기준선 hash, 실행 영수증.
- 장면별 `*-Benchmark.json` 및 `tables.md`: 반복 timing, 분산, 조건 간 차이와 실행 경로.

브랜치는 `experiment/temporal-edge-read-cost`, 시작점은 `6899477`,
사전 계획 `1efb60a`, 구현 및 선행 검증 `158d9ae`다.
독립 검사는 `build_edge_read_probe.cmd` 후 `run_edge_read_probe.ps1`로 실행한다.
Main renderer는 Release 빌드 후 `run_temporal_edge_read_optimization.ps1`의
Capture/Smoke/Benchmark와 bistro/minecraft를 각각 실행한다.
`analyze_temporal_edge_read_optimization.py`로 각 phase/scene을 검사하고 마지막에 Summary를 생성한다.
재실행은 runner `-Receipt`와 analyzer `--receipt`를 동일 경로로 지정하고
analyzer `--output`으로 기존 결과와 분리한다. 원시 PNG·EXE·AutoBench는 Git에 넣지 않는다.

API 근거는 [사전 계획](method.md)에 기록했다. 이번 종료 범위는 같은 RG의
읽기 방식·소스 배치 검토이며 edge 선택이나 새로운 품질 알고리즘은 후속 범위다.
