# 셰이더 수명 및 DX11 계측 검증

## 범위

`experiment/standard-t2x-reuse`의 Original SMAA / Standard T2X-R와 temporal-pass
contrast ablation을 보존한다. R은 camera/depth reprojection이다. 선택식, jitter,
spatial-frame history, threshold, HLSL, pass와 GPU resource는 변경하지 않는다.
최종 8-case 측정이나 새로운 성능 개선 결과가 아니다.

## 수명 감사와 수정

이전 시작 실패 `20260920_103030`의 주소 후보에는 `_purecall`과 background shader
compile lambda가 포함됐다. 정식 unwind나 실패 객체 식별을 수행한 자료가 아니므로
정확한 원인 확정 또는 모든 시작 오류 해결로 표현하지 않는다.

별도로 확인한 코드 결함은 `CreateShaderFromFile/Buffer`와 `Reload`가 raw `this`를
비동기 작업에 전달하고, shared owner의 기본 delete가 시작된 뒤 DX11 base destructor에서
작업을 기다린다는 점이다. 그 사이 most-derived virtual dispatch 대상의 수명이 끝날 수 있다.
derived destructor 첫 줄에 wait를 추가하는 것만으로도 소멸 시작 이전의 동기화를 보장하지 못한다.

`VA_RENDERING_MODULE_CREATE_SHARED`와 `vaAutoRMI`의 shared_ptr custom deleter가
`PrepareForDestruction()`을 호출한 뒤 delete하도록 수정한다. 기본 rendering module은 no-op,
shader는 기존 background task 완료를 기다린다. 기존 destructor의 방어 wait는 유지한다.
대기 중 shader data mutex를 잡지 않아 worker가 같은 mutex를 얻을 수 있다.
작업마다 shared ownership을 capture하지 않으므로 마지막 해제가 worker thread로 옮겨가지 않는다.
기존 main-thread 소유권/생성·해제 계약을 유지한다.

저장소의 생산 shader 생성은 두 shared factory 경로로 확인했다. raw factory 결과를 외부에서
기본 deleter로 감싸거나 직접 delete하는 새로운 경로에는 자동 적용되지 않는다. 그런 코드는
공통 deleter를 사용해야 한다. DX12도 공통 헤더를 사용하지만 이번 런타임 검증은 DX11만 수행한다.

## 검증

후속 반복에서 수명 수정만 적용한 EXE의 Minecraft 실행 `20260920_182136`이 멈췄다.
live thread unwind에서 main은 shader join, worker들은 `CompileShaderFromFile`의
MessageBox 대기였다. 해당 프로세스의 compiler diagnostic은 `vaMaterialBasic.hlsl:158`
`VA_RM_INPUT_LOAD_Albedo` 미선언 오류였다. 창 선택 도구에는 오류 창이 노출되지 않았다.
이 실행과 부모 반복 루프만 확인 후 종료했고 결과에서 제외했다.

재질 APACK/unpacked loader는 `CreateRenderMaterial` 단계에서 UID를 등록한 뒤 데이터를
읽고 있었다. renderer는 UID lookup으로 아직 초기화 중인 입력을 볼 수 있다. 두 loader만
`trackUID=false`로 생성하고, 기존 `InsertAndTrackMe`에서 로딩 성공 후 등록하도록 바꾼다.
일반 생성 API의 기본 동작은 유지한다. 이 publication 결함은 코드로 확인했지만 이전 crash의
모든 원인을 동일시하지 않는다. 완료 후 동일한 등록 mutex를 통해 조회하므로 초기화 쓰기의
공개 순서도 보존된다.

clean runner는 `-smaaNonInteractiveShaderCompile`을 추가한다. DX11 compiler의 file,
embedded, buffer 오류는 진단과 입력 매크로를 로그에 기록하고 작업을 반환한다. main tick이
종료를 요청하고 WinMain은 실패 count가 있으면 1을 반환한다. interactive 실행의 확인 창은
유지한다. 없는 include 등 별도 `VA_ERROR` 경로 전체를 무인화한 수정은 아니다.

- Release x64 전체 연결.
- `-smaaShaderLifetimeTest`: 실제 shader task manager에 지연된 probe compile을 넣고,
  외부 coordinator는 owner가 join을 시작한 뒤에만 작업을 풀어준다. 32회 모두 worker 완료가
  most-derived destructor보다 앞서야 한다. 5초 제한의 실패는 report FAIL로 처리한다.
- 여섯 shader stage의 shared macro / auto owner에 공통 deleter가 실제 설치됐는지 확인한다.
- 미완성 재질의 UID 조회가 실패하고 초기화 후 명시적 등록 때만 성공하는지 확인한다.
- 의도적으로 잘못된 file/buffer fixture가 무인 실행에서 종료 코드 1과 오류 로그를 남기는지 검사한다.
- 실제 PS/CS 각 32회 asynchronous buffer compile 직후 해제, PS 16회 reload 직후 해제를 수행한다.
  작업 수 0 및 shader list의 이전 개수 복원을 확인한다. 모든 fixture의 GPU 렌더 정확성 검사는 아니다.
- 독립 프로세스로 lifecycle 검사를 반복하고 Bistro/Minecraft smoke에서 시작·종료를 확인한다.
- 두 장면 각 7 mode ×240 frame을 수정 전 capture와 PNG SHA-256으로 비교한다.
  일치하면 저장된 모든 RGBA/metadata 바이트가 동일한 강한 출력 회귀 검사다.
  기존 고스팅·깜빡임의 품질 한계가 개선됐다는 뜻은 아니다.

```powershell
Tools/SMAA/run_clean_cmaa2.ps1 -CMAA2Arguments @('-smaaShaderLifetimeTest') -Hidden -TimeoutSeconds 120
Tools/SMAA/run_temporal_dependency.ps1 -Phase Capture -Scene bistro -Receipt tmp/lifetime-capture-runs.json
Tools/SMAA/run_temporal_dependency.ps1 -Phase Capture -Scene minecraft -Receipt tmp/lifetime-capture-runs.json
python Tools/SMAA/validate_shader_lifetime.py --report <lifetime-csv> --capture <new-capture> --prior <old-capture> --output <json>
Tools/SMAA/probe_dx11_profiler.ps1
Tools/SMAA/probe_dx11_profiler.ps1 -Trace
Tools/SMAA/run_shader_lifetime_gate.ps1 -Capture
```

## 공식 근거와 계측 해석

2026-09-20 확인:

- Microsoft [_purecall](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/purecall?view=msvc-170):
  pure virtual 호출의 오류 처리 함수다. 이것만으로 발생 객체나 원인을 특정할 수 없다.
- Microsoft [shared_ptr](https://learn.microsoft.com/en-us/cpp/standard-library/shared-ptr-class?view=msvc-170):
  마지막 owner 해제 시 등록된 deleter를 호출한다. 이번 수정은 이 표준 소유권 기능을 사용한다.
- NVIDIA [Nsight Graphics 지원표](https://docs.nvidia.com/nsight-graphics/UserGuide/appendix.html):
  현행 Shader Profiling의 지원 API는 D3D12/Vulkan이며 DX11은 지원 표시가 없다.
- NVIDIA [Nsight Systems 설명서](https://docs.nvidia.com/nsight-systems/UserGuide/):
  DX11 API trace는 API 함수 실행 시간, marker, frame 정보를 제공한다. 이는 temporal shader의
  warp divergence, cache miss 또는 instruction stall 계측과 다르다. GPU Metrics는 전체 GPU
  범위의 sampled counter이며 다른 GPU 작업을 포함할 수 있다.
- NVIDIA [성능 카운터 권한](https://developer.nvidia.com/nvidia-development-tools-solutions-err_nvgpuctrperm-permission-issue-performance-counters):
  관리자 권한 또는 성능 카운터 접근 허용 설정이 필요하다. 시스템 전체 접근 정책을 자동 변경하지 않는다.

현재 resolve는 약 25~39 us이므로 전체 GPU의 기본 10 kHz 샘플만으로 특정 shader의 stall 원인을
단정할 수 없다. API trace의 CPU Draw 시간도 GPU resolve 시간으로 바꾸어 보고하지 않는다.
프로파일러를 붙인 실행은 기존 정상 성능 benchmark와 분리한다. 계측에 실패하면 그 오류와
미측정 범위를 그대로 남기며, 미지원 도구를 설치하거나 API를 바꾼 결과로 기준선을 대체하지 않는다.
