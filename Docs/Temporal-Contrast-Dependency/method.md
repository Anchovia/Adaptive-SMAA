# Temporal 대비 판정 의존 관계와 texel 접근 검증

## 목적과 범위

Original SMAA + camera/depth R, threshold 0.01, paired jitter, spatial-frame history를
고정한다. 이전 실행 비용 gate 다음 단계이며 final 8-case나 object-motion 구현이 아니다.
추가 pass, texture, 후보 목록, history copy는 없다. 기존 native/contrast entry를 보존한다.

## 공식 자료와 설계

2026-09-20 다음 Microsoft 자료를 확인했다.

- [Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load):
  정수 texel 좌표와 mip를 사용하며 sampler filtering을 사용하지 않는다. 범위 밖 읽기는 0이므로,
  기존 point/clamp sampler와 맞추기 위해 좌표를 명시적으로 clamp한다.
- [Sample](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-sample):
  기존 point sampler, SRV format과 normalized UV 접근의 기준이다.
- [SampleGrad](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplegrad),
  [sample_d](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/sample-d--sm4---asm-):
  명시적 좌표 미분을 전달하는 기능이다. 더 빠른 기능이라고 가정하지 않는다.
- [if](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if):
  분기 속성과 gradient 사용 제약을 확인한다. 최종 후보는 기존 방식대로 luma 미분을 분기 전에,
  history SampleLevel을 선택 분기 안에 둔다.

## 먼저 제외한 prefetch 시도

velocity를 SampleLevel 대신 Sample로 앞에서 읽는 코드와, history UV의 ddx_fine/ddy_fine을
앞에서 계산해 SampleGrad에 전달하는 코드를 각각 FXC /O3로 컴파일했다.
두 경우 모두 실제 DXBC는 velocity를 선택 분기 안으로 옮겼다. 후자는 좌표 미분도 옮겼다.
소스 배치만으로 실행 순서를 보장하지 못하므로 실제 GPU 실험에는 연결하지 않았다.
`validate_temporal_dependency_shaders.py`가 두 probe를 재생성하고 위치와 hash를 기록한다.
이는 컴파일러 오류 판정이 아니라 이번 prefetch 설계의 정적 검증 실패다.
가짜 데이터 의존 관계나 불필요한 메모리 쓰기로 컴파일러를 강제하지 않는다.

## 실제 구현한 대조군

| ID | 변경 |
|---|---|
| O-T2X-R | 원본 기준선 |
| ABL-Contrast-001-R | 기존 조기 반환 선택 경로 |
| ABL-Structured-001-R | 이전 gate의 공통 반환 branch, 아래 Load 후보의 직접 대조군 |
| ABL-LoadCurrent-001-R | current만 SV_POSITION 정수 좌표의 Load로 변경 |
| ABL-LoadCurrentVelocity-001-R | current와 선택된 velocity를 같은 정수 좌표로 Load |
| DBG-ContrastMask-001-R | 기존 mask, 캡처 전용 |
| DBG-LoadContrastMask-001-R | Load 입력의 mask, 캡처 전용 |

후보 수식과 threshold는 그대로다. Load의 화면 바깥 helper lane도 clamp하여 홀수 높이
1061의 마지막 줄에서 미분이 달라지지 않게 한다. fractional history UV는 기존
point/clamp SampleLevel을 보존한다. 같은 SRV를 사용하되 sRGB decoding 및 좌표 변환의
실제 동일성은 GPU mask/final 비교로 검증한다. 다른 format/viewport 조건까지 일반화하지 않는다.
Load도 메모리를 읽으며 sampler 생략이 곧 성능 향상을 뜻하지 않는다. 기존 의존 관계를
제거한 구현이라고 표현하지 않는다.

## 검증과 실행

- 기존 native 8개 shader byte identity, 이전 execution 12 variant 검증, 신규 Load 6 variant 검사.
- Release x64 DX11 / Ultra / RTX 3060 Ti / 1920×1061 / hidden / VSync Off.
- 독립 clean process, timeout, 정상 종료와 finalized PASS report. EXE 해시를 전후 기록.
- 60 Hz 타임라인, 60 정지 +120 이동 +60 정지, frame 0 history/phase reset, warmup 60.
  7개 mode ×240 frame으로 prior capture bridge와 final/mask byte identity를 확인한다.
  마지막 행/열 mask mismatch를 별도로 확인한다.
- 성능은 PNG/후보 readback/CPU 영상 분석 없이 300 warmup +4,800 frame ×3회,
  정/역/정 mode 순서. 기존 timestamp·wall interval 및 분포 계측을 재사용한다.
- 같은 출력이면 기존 품질 평가를 그대로 적용한다. 깜빡임이나 고스팅을 개선했다고 주장하지 않는다.
- 원본보다 빨라지지 않거나 장면별로 손해라면 기본 구현에 넣지 않는다.

```powershell
python Tools/SMAA/validate_temporal_dependency_shaders.py
Tools/SMAA/run_temporal_dependency.ps1 -Phase Smoke -Scene bistro
Tools/SMAA/run_temporal_dependency.ps1 -Phase Capture -Scene bistro
Tools/SMAA/run_temporal_dependency.ps1 -Phase Capture -Scene minecraft
python Tools/SMAA/analyze_temporal_dependency.py --capture <new> --prior <prior-execution-capture> --output tmp/dependency-<scene>-capture.json
Tools/SMAA/run_temporal_dependency.ps1 -Phase Benchmark -Scene bistro
Tools/SMAA/run_temporal_dependency.ps1 -Phase Benchmark -Scene minecraft
python Tools/SMAA/analyze_temporal_dependency.py --performance <csv> --output tmp/dependency-<scene>-performance.json
```

기존 execution capture: Bistro `20260920_094311`, Minecraft `20260920_094824`.
raw PNG/CSV, executable과 임시 DXBC는 Git에 넣지 않는다.
