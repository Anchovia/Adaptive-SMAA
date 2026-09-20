# 동일 픽셀 선택의 GPU warp 단위 실행 검증

목표는 현재 temporal PS의 픽셀별 luma 선택과 출력을 유지하면서 원본 T2X-R 대비 속도
손해를 거의 없애거나 가속하는 것이다. 이번 단계는 속도에 집중한다. 품질 검사는 기존
출력의 보존 여부를 확인하며, threshold·후보 확장·history kernel 등의 품질 변경은 없다.

## 실행 구조

1. 현재 공간 색상 한 번의 읽기에서 기존 luma/fine derivative 선택식을 계산한다.
2. 모든 active lane이 분기 전에 공식 `NvAny(selected)`를 호출한다.
3. 선택 lane이 전혀 없는 warp는 current를 반환한다.
4. 선택 lane이 있는 warp는 velocity/history/원본 history weight를 함께 계산하고,
   비선택 lane의 weight만 0으로 만들어 출력한다.

픽셀의 선택 여부는 그대로다. Warp 안의 비선택 픽셀에서 추가 계산이 이루어질 수 있지만
그 픽셀을 temporal 혼합 대상으로 확장하지 않는다. 작업 목록·추가 pass·다른 패스의
metadata 읽기·실제 UAV 버퍼는 추가하지 않는다. 확장 명령용 null UAV slot 설정 호출은
실제 실행에 포함하고 숨기지 않는다.

NVIDIA GPU에 한정된 실행 구조 실험이다. 원본, 기존 픽셀별 분기, ScalarWeight와 함께
측정한다. 이것이 일반 DX11 표준 기능 또는 여러 GPU 제조사에 대한 해결책이라고
표현하지 않는다. 더 빠를지는 미리 가정하지 않는다.

## 공식 근거 및 연결

- [NVIDIA HLSL intrinsics 설명](https://developer.nvidia.com/blog/unlocking-gpu-intrinsics-in-hlsl/):
  DX11 pixel shader 지원, 드라이버의 fake UAV 명령 변환 및 opcode support query.
- [고정한 SDK](https://github.com/NVIDIA/nvapi/tree/70d337db9186e968eab622f7e786de7e437faf3d):
  `nvHLSLExtns.h`의 `NvAny`, `nvapi.h`의 thread-local shader-extension slot API.
- 기존 [단일 픽셀 비용 비교](../Temporal-Contrast-Cost/conclusion.md)의 결과와 선택식을 유지한다.

비동기 shader creation 간 전역 slot 오염을 피하기 위해 같은 스레드에서 slot 설정,
CreatePixelShader, slot 해제를 수행한다. 정상 shader에는 opt-in 매크로를 넣지 않는다.
Warp 실험 시작 시 opcode 지원을 검사하고 미지원이면 FAIL로 끝낸다. 확장 shader 생성
실패도 종료 코드 1로 중단하여 잘못된 대체 셰이더의 성능을 보고하지 않는다.

## 검증과 측정

- 독립 D3D11 pixel shader probe: 129×17의 비선택 전체, 선택 전체, checkerboard,
  단일 선택. NvAny/NvBallot/lane-id 관계와 선택 pixel 보존, 슬롯 해제 후 일반 PS 생성을 확인한다.
  해상도가 quad/warp 배수인 경우에만 한정하지 않는다.
- 원본 spatial/resolve 8 DXBC variant 불변, NVAPI resolve/mask 각각 R Off/On 4개 compile.
  DXBC의 atomic/store는 드라이버 변환용 인코딩이며 실제 GPU 메모리 트래픽 수로 세지 않는다.
- Bistro/Minecraft 각각 6 mode×240 frame. 이전 Cost gate의 원본/기존 선택/scalar/mask와
  hash bridge하고 새 resolve가 기존 선택과 byte-exact인지 검사한다.
- 별도 debug PS의 R은 원래 선택, G는 NvAny 결과다. R 일치와 R⊆G를 검사한다. G는
  해당 debug PS의 vote coverage이며, 별도 resolve의 실제 warp 배치나 성능 실행의
  hardware counter로 동일시하지 않는다.
- RTX 3060 Ti, DX11, Release x64, SMAA Ultra, 1920×1061, hidden, VSync Off.
  Original spatial, camera/depth reprojection, paired jitter, spatial-frame history를 고정한다.
- 성능은 capture/이미지 분석과 분리한다. 30초 미측정 렌더링 후 각 mode 300 warmup,
  4,800 frame×5회, 정/역 순서를 교차한다. Resolve와 전체 SMAA, 불변 spatial 및
  WholeFrame/wall 분포를 함께 기록한다. 동일 프로세스 반복을 독립 GPU 표본으로 취급하지 않는다.
- `run_temporal_warp.ps1`은 명령별 새 CMAA2 process, 종료 후 0개 및 완성된 PASS CSV를 확인한다.

재현: `run_nv_warp_probe.ps1`, `validate_temporal_warp_shaders.py`,
`run_temporal_warp.ps1 -Phase Smoke|Capture|Benchmark -Scene bistro|minecraft`,
`analyze_temporal_warp.py`. 기본 실행 방식은 검증 결과를 확인한 뒤 판단한다.
