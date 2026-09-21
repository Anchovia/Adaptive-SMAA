# 기존 temporal 패스 속도 한계 검증

출발점 af2c35b, experiment/temporal-pass-speed-limits. 품질 개선 작업은 보류한다.
Original SMAA, camera/depth reprojection On, paired sample pattern, raw spatial history,
Linear current/history와 luma derivative threshold .01인 paired Scalar(kind33)의 출력을 고정한다.
원본 O-T2X-R도 비교한다. 최종8-case, object motion 또는 원본 TSCMAA 재현 결과가 아니다.

## 후보와 새 검증의 근거

| kind | 후보 | 가설 |
|---:|---|---|
|34|SpeedBranch|비선택의 velocity/history와 weight 계산을 실제로 생략|
|35|SpeedUniformScalar|phase 선택과 normalized jitter 계산을 기존 cbuffer update에서 재사용|
|36|SpeedUniformBranch|위 두 변경의 결합 효과|
|37|SpeedUniformPrefetch|velocity 의존성을 앞당기고 history만 조건부 접근|
|38|SpeedUniformWarp|기존 NVAPI vote-any로 전부 비선택인 warp만 반환하고 픽셀별 weight 유지|
|39/40|SpeedPhaseScalar|두 위상별 compile-time jitter shader를 기존 draw에서 선택, per-pixel phase/offset 계산 제거|

이전 Point 입력에서 분기/prefetch/warp는 공통 속도 이득이 없었다. 이번에는 Linear sampling과
보정 위치에서의 달라진 mask 때문에 생략 비용이 달라진 가설에 한정해 재검증한다.
같은 DXBC가 나오면 중복 실험하지 않는다. CPU uniform은 기존 48-byte cbuffer의 padding1/2와
기존 SetVariablesB upload를 사용한다. 새 pass/texture/copy/upload는 없다.

분기 전 luma 미분을 끝내며 조건부 읽기는 명시적 LOD0다.
[Microsoft if/branch/flatten](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if),
[SampleLevel](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel),
[NVIDIA warp intrinsics](https://developer.nvidia.com/blog/reading-between-the-threads-shader-intrinsics/)
및 동봉 NVAPI 구현을 근거로 한다. 실행 시간과 명령 수를 동일시하지 않는다.

## 검증 순서와 중단 기준

1. FXC native/paired bytecode 불변, 실제 조건부 history와 미분 위치/샘플 수 검사.
2. Release x64 빌드. 두 장면 각각 전체240 frame을 렌더하고 5-frame 간격과
   1/61/179/181/201의 총53 frame만 PNG로 저장해 기존 capture 및 kind33과 byte 비교한다.
   first-frame seed, 이동 시작/종료와 정지 두 위상을 포함한다. 이는 제한된 정확성 검사이며
   전체240 frame의 동일성 증명이나 새로운 품질 평가가 아니다.
3. Smoke 후 2400 frame×3회 교차 screening. PNG·readback·CPU 영상 분석과 분리한다.
4. 유망한 후보만 4800 frame×4회 정/역 교차 확인. 전체 AA와 resolve, spatial과 WholeFrame,
   median/p95/p99, run 분산 및 wall FPS/1% low를 확인한다.
5. 측정상 이득이 없거나 장면별 상충이면 기본값으로 채택하지 않는다. 선택식/출력/필터/
   precision 변경 및 다른 pass로의 이동은 별도 알고리즘 변경이므로 이번 속도 성과에 넣지 않는다.

기존 max/any, fixed threshold, 혼합 산술 재배열, Point→Load, 컴파일 최적화 레벨과 단순 소스
재배치는 이전 검증 및 DXBC를 확인해 반복 여부를 결정한다. GPU 카운터는 필요한 후보에서만
별도 replay로 확인하며 실시간 timing과 섞지 않는다. 제한된 DX11/GPU 범위의 결과를 모든
가능한 구현의 불가능 증명으로 확대하지 않는다.

## 컴파일 gate 기록

초기 공통 schedule 함수는 FXC /WX에서 X4000(잠재적 미초기화 반환값)으로 거부됐다.
경고를 무시하지 않고 각 entry의 실행 흐름을 명시한 뒤 전체 compile gate를 통과했다.
UniformPrefetch는 R Off/On 모두 UniformBranch와 동일 명령열로 최적화되어 runtime matrix에서 제외했다.
위상 특화는 별도 pass가 아니라 같은 draw에서 positive/negative PS 중 하나를 선택한다.
Pattern Off에서는 기존 uniform offset0 경로로 돌아가며 실제 장면 실험은 Pattern On/R On만 수행한다.

## 실행 묶음과 밀도 후속 screen

첫 screen에서 per-pixel branch와 warp-any는 Bistro에서 빠르지만 Minecraft에서 느렸다.
같은 선택 결과에서 실행 묶음만 4/8/16 lane으로 제한하는 Group4/8/16과,
warp 내 선택 lane이 8/16 미만일 때만 per-pixel early return을 하는 Density8/16을 검증한다.
이는 연구용 실행 휴리스틱이며 NVIDIA의 권장 알고리즘이라고 표현하지 않는다.
NvBallot와 NvGetLaneId의 32-bit vote 의미를 사용하며 lane 순서를 화면의 quad/tile 배치로
가정하지 않는다. 선택 lane은 항상 살아남고 비선택 출력은 기존 current를 유지한다.
미분은 vote와 분기 전에 계산한다. 별도 패스나 후보 변경은 없다.
동일한 53-frame 출력 gate와 두 장면 smoke 후 2400×3 screen을 수행하고,
공통 이득 후보만 최종 확인 matrix에 포함한다. scene 이름에 따른 shader 선택은 하지 않는다.
