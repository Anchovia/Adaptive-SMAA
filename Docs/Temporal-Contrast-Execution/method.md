# Temporal contrast 실행 비용 분리

## 범위

`experiment/standard-t2x-reuse`, Original SMAA Ultra + camera/depth reprojection On.
기존 대비 threshold 0.01, paired jitter, spatial-frame history, weight 계산을 보존한다.
최종 8-case 또는 확보 TSCMAA 원본 구현이 아닌 별도 engineering ablation이다.
선택 mask texture를 resolve에 추가하지 않으며 GPU pass/resource도 추가하지 않는다.

## 공식 근거와 검증 규칙

- [Microsoft HLSL if](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if):
  branch는 조건부 실행, flatten은 양쪽 평가 후 선택이다. 후자는 sample 생략이 아니다.
- [Microsoft ddx_fine](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/ddx-fine):
  SM5 이상 pixel shader에서 지원한다. 기존 gradient 계산은 비균일 분기 전에 유지한다.
- [Microsoft SampleLevel](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel):
  LOD 0을 명시한다. 현재 한 mip texture의 point/clamp sampling과 실제 출력 일치를 검사한다.
- [NVIDIA graphics optimization](https://developer.nvidia.com/blog/optimize-gpu-workloads-for-graphics-applications-with-nvidia-nsight-graphics/):
  분기는 그룹 내부 조건 일치도, 비활성 lane, memory latency를 함께 보아야 한다.
  픽셀 선택률을 instruction/transaction 감소율로 간주하지 않는다.
- [Nsight Shader Profiler](https://docs.nvidia.com/nsight-graphics/UserGuide/shader-profiler.html):
  현재 문서는 D3D12/Vulkan 지원을 명시한다. DX11에서 사용하지 않은 hardware counter를
  측정했다고 표현하지 않는다. 본 gate는 DXBC와 timestamp 대조 실험이다.

2026-09-20 공식 문서 확인. 특정 분기 문법의 보편적 성능 우위를 가정하지 않는다.
DXBC는 드라이버 이전 중간 코드다. slot 수는 GPU cycle 수가 아니며 순서도 하드웨어
실행 순서를 보장하지 않는다.

## 대조군

| ID | 차이 | 예상 출력 |
|---|---|---|
| O-T2X-R | 기존 ps_4_1 원본 | native |
| ABL-NativeSM5-R | 같은 원본 entry를 ps_5_0으로 컴파일 | native |
| ABL-Lod-R | velocity/history만 explicit LOD 0 | native |
| ABL-CurrentFirst-R | 위 코드에서 current를 먼저 작성 | native |
| ABL-Contrast-All-R | 기존 gradient/early-return, threshold 0 | native |
| ABL-Contrast-001-R | 기존 gradient/early-return, threshold 0.01 | 기존 선택 출력 |
| ABL-Structured-001-R | 선택 시 계산하는 branch block, 공통 return | 기존 선택 출력 |
| ABL-Flatten-001-R | 같은 block에 flatten: fullscreen fetch 후 선택 | 기존 선택 출력 |
| ABL-PrefetchVelocity-001-R | velocity를 branch 앞에 작성한 시도 | 기존 선택 출력 |

FXC /O3에서 CurrentFirst와 Lod가 동일 DXBC이고 PrefetchVelocity와 Structured도
동일 DXBC다. 후자의 velocity fetch는 실제로 branch 안으로 이동했다. 따라서 이름만으로
읽기 순서 최적화 또는 unconditional prefetch 성공으로 해석하지 않는다.
동일 DXBC 대조군의 시간 차이는 측정 변동을 살피는 보조 자료다.

## 실행 및 판정

- Release x64 / DX11 / RTX 3060 Ti / 1920×1061 / hidden / VSync Off.
- 각 명령은 clean runner의 독립 프로세스, exit 0 및 finalized PASS report 필요.
- 동일 60 Hz 타임라인: 60 정지 + 120 이동 + 60 정지. capture 240 frame,
  warmup 60 및 frame 0 history/phase reset. native와 기존 대비 출력의 이전 capture hash bridge.
- 9 control과 current/mask 2개 진단을 캡처하여 모든 frame hash를 비교한다.
  shader 원본 8 variant byte identity와 신규 12 variant 컴파일/분기/texture 명령 검사.
- mask의 2×2, 8×4, 4×8 화면 tile 혼합률을 계산한다. 아래쪽 불완전 tile은 제외한다.
  화면 tile은 warp 배치가 아니며 이 수치로 실제 branch efficiency를 주장하지 않는다.
- 성능: PNG/readback/분석 작업 없이 300 warmup, 4,800 frame ×3회, 정/역/정 순서.
  각 mode의 SMAA/spatial/resolve/WholeFrame GPU 시간 및 실제 wall frame interval을 기록한다.
  평균, median, sample std, p95/p99, 반복 평균 표준편차를 구분한다.
  FPS=1000/평균 wall ms, 1% low=1000/가장 느린 ceil(N/100) wall interval 평균.
- 출력 동일성을 먼저 통과한 control만 같은 품질의 비용 비교로 판단한다.
  세 반복 및 한 GPU의 결과로 일반 GPU 성능이나 통계적 유의성을 단정하지 않는다.
  기존 선택 방식의 정지 후 2-frame flicker와 미확정 ghosting 우위는 해결한 것으로 보지 않는다.
