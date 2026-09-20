# DX11 temporal draw 카운터 수집 방법

## 도구 선택과 권한

2026-09-21 일반 권한의 Nsight Systems 2026.3.1 조회는 `Insufficient privilege / ERR_NVGPUCTRPERM`을 반환했다. 사용자가 관리자 권한 요청을 허용한 후 읽기 전용 관리자 조회가 성공했고 RTX 3060 Ti/GA104 및 `ga10x`, `ga10x-gfxt`, `ga10x-gfxact` metric set을 확인했다. 시스템 전체의 performance-counter 접근 정책은 변경하지 않았다.

NVIDIA의 최신 [Shader Profiler 문서](https://docs.nvidia.com/nsight-graphics/UserGuide/shader-profiler.html)는 D3D12/Vulkan 지원을 명시한다. [Nsight Systems GPU Metrics](https://docs.nvidia.com/nsight-systems/UserGuide/index.html#gpu-metrics)는 device 단위이며 어느 process/context인지 자체적으로 알지 못한다. 따라서 그 평균을 약 30 µs의 DX11 temporal draw 병목으로 직접 귀속하지 않았다.

설치된 **RenderDoc 1.44**의 [공식 카운터 안내](https://github.com/baldurk/renderdoc/blob/v1.44/docs/window/performance_counter_viewer.rst)와 [DX11 NVIDIA 구현](https://github.com/baldurk/renderdoc/blob/v1.44/renderdoc/driver/ihv/nv/nv_d3d11_counters.cpp)을 확인했다. 이 경로는 Nsight Perf SDK로 draw 범위를 replay하며 카운터를 얻는다. Nsight Systems에 이미 설치된 `nvperf_grfx_host.dll`을 작업 폴더의 `tmp/rd-profiler/plugins/nv`에 복사해 로컬에서만 사용했다. RenderDoc 소스가 이 상대 검색 경로를 지원함을 확인했고 필요한 DX11 함수 초기화 및 실제 counter fetch가 성공했다. 최신 독립 Perf SDK 패키지를 새로 설치했다고 표현하지 않는다.

- RenderDoc 1.44 build: `050034a0faa37d606ce1b8cf677dba4bc36984ea`.
- NVIDIA runtime file version: `2026.2.0.26099`.
- runtime SHA-256: `DA2E73083E817A2721093A7B1F5DCF4A93AA62D482DE42CA837E4017B96EA9C7`.
- GPU/driver: NVIDIA GeForce RTX 3060 Ti / 610.88.
- Administrator access is scoped to the profiling process; [NVIDIA 공식 권한 설명](https://developer.nvidia.com/ERR_NVGPUCTRPERM).
- DLL, raw `.rdc`, 로그와 전체 counter catalog는 Git에 넣지 않는다.

## 캡처 조건

`-smaaTemporalCounterCapture bistro|minecraft`는 원본, 기존 대비 분기, ScalarWeight의 세 mode를 순서대로 실행한다. mode마다 300-frame warmup 뒤 history/jitter를 frame 0에서 초기화하고 기존 카메라 경로의 **frame 90**을 RenderDoc API Start/EndFrameCapture로 저장한다. frame 90은 이동 구간이며 camera path t=2.5다. mode마다 121프레임을 진행한다. Report의 mode/frame/PASS를 확인하고 실제 shader entry point와 temporal draw event도 확인한다.

Original SMAA Ultra, camera/depth reprojection, paired sample pattern, spatial-frame history, 1920×1061이다. 두 선택 구현 threshold는 0.01이다. 새 mask·후보 확장·패스·history 변경은 없다. capture API는 이미 주입된 DLL이 있을 때만 opt-in 명령에서 사용한다. API 없는 명령은 FAIL로 종료한다. 일반 실행의 셰이더와 binding은 `030759b` 대비 diff가 없다.

RenderDoc API의 수동 capture는 frame number를 `4294967295`로 기록한다. 이를 연구 timeline frame으로 해석하지 않는다. timeline은 AutoBench의 `renderdoc_capture, <mode>, 90, PASS`와 capture 시점 코드로 식별한다. EndFrameCapture는 AA 비교 지점에서 수행하므로 presentation 이후 전체 frame 캡처와도 구분한다.

Minecraft capture report: `20260921_030358`. Bistro: `20260921_030513`. 두 장면은 별도 CMAA2 프로세스로 실행됐으며 종료 후 replay를 시작했다. 실행파일 SHA-256은 `2d53a0211779d1a93a2e0cb356d2e00d629ec9457cfc9148089891ae20aff66d`다.

## 카운터와 검증

하드웨어 3,508개와 D3D11 기본 13개, 총 3,521개 counter를 열거했다. 그중 GPU Duration, PS Invocations 및 명령·texture·cache·대기 관련 총 15개만 수집했다. 각 capture를 3번 재생하고 `SMAATemporalResolve` 아래의 단일 draw 결과만 보존한다. 실시간 timestamp와 replay timing은 섞지 않는다.

NVIDIA 구현은 counter 조합에 따라 여러 pass를 replay할 수 있다. 카운터 설명·단위·원시 반복값을 저장하며, warp 대기 비율을 전체 시간 비율로 변환하지 않는다. counter ID보다 이 환경의 NVIDIA runtime이 제공한 이름/설명을 기준으로 해석한다. 실제 소스의 range replay가 대상 draw를 구분함을 확인했다.

`inspect_temporal_replay_inputs.py`로 draw 시점에 묶인 current/history/velocity의 byte hash, SRV format 및 선택 threshold 상수 버퍼를 검사했다. 원본 resolve에서는 사용 constant block이 없고, 선택 구현 두 개는 같은 48-byte constant block을 사용한다. 동일 input과 확인한 shader entry를 통해 서로 다른 장면 상태를 비교하는 오류를 배제했다. 최종 분석은 `analyze_temporal_counters.py`로 6 capture hash, 보고서, 3회×15개 값, 입력 hash 및 shader를 검증한다.

## 재현

1. Release x64를 빌드한다. 준비 조회는 `Tools/SMAA/probe_gpu_metrics_access.ps1 -OutputDirectory <local-output>`이다.
2. 관리자 PowerShell에서 `Tools/SMAA/run_renderdoc_counter_probe.ps1 -Scene minecraft`, 이어서 `-Scene bistro`를 각각 실행한다. 기존 CMAA2가 있으면 거부한다. supervisor timeout은 300초이며 자신이 시작한 대상만 정리한다. partial 결과는 제외한다.
3. `Tools/SMAA/run_renderdoc_counter_probe.ps1 -InspectInputs`로 기존 6개 capture 입력만 검사한다. 새 캡처나 counter 재측정은 하지 않는다.
4. 일반 Python으로 `Tools/SMAA/analyze_temporal_counters.py`를 실행한다. 출력은 이 디렉터리의 report.md/results.json이다.

재실행 시 원시 결과 폴더는 별도로 보존한다. 실행 도구는 설치된 RenderDoc/Nsight Systems 경로와 runtime hash를 기록한다. GUI의 명령행 Python은 `__file__`을 정의하지 않으므로 supervisor가 작업 디렉터리를 명시한다.

## 실패 및 제한 기록

최초 관리자 RenderDoc 스크립트는 `__file__` 가정 때문에 데모 실행 전에 멈췄고 제한 시간 후 해당 RenderDoc만 정리했다. 정리 경로의 slash 정규화 문제도 수정했다. 이후 실제 원본 warmup capture 및 counter 열거가 성공했고, 두 장면의 본 counter capture는 모두 성공했다. 입력 검사 중 구 API명 `GetConstantBuffer`는 현 버전의 `GetConstantBlocks`로 수정했다. 실패한 입력 검사는 counter 수집을 다시 수행하지 않았다.

초기 supervisor의 `host_exit_code`가 null인 기록은 성공 코드 0으로 바꿔 적지 않는다. 당시 종료, completed PASS report, replay status와 잔류 CMAA2 0개를 확인했다. 최종 supervisor는 process handle을 보존하고 스크립트 결과 상태까지 검사하며, 후속 입력 검사에서 exit 0 / timeout false / 잔류 0을 확인했다.

서로 다른 pose나 GPU로 일반화하지 않으며, 세 replay를 세 독립 장면 표본으로 세지 않는다. 이번 측정은 원인 후보를 구체화하는 진단이며, 새 가속 구현이나 최종 논문용 8-case 결과가 아니다.
