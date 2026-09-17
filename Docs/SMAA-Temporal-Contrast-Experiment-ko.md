# 현재 색상 대비에 따른 선택적 Standard T2X 실험

완료한 두 장면의 성능·정지 안정성 결과는
[초기 비교 결과](Temporal-Contrast-Initial/report.md)에 정리했다.

## 연구 질문과 구현

원본 `baseline/smaa-t2x`의 `88893da`에서 분기한
`experiment/standard-t2x-reuse`의 독립 실험이다. 기존의 첫-pass edge-mask 실험이나
TSCMAA 후보 목록·compute resolve 코드를 가져오지 않았다.

현재 temporal resolve에서 원래 읽는 공간 SMAA 색상을 먼저 한 번 읽는다. 해당 RGB에서
밝기 `Y = dot(RGB, (0.2126, 0.7152, 0.0722))`를 계산한 뒤
`C = max(abs(ddx_fine(Y)), abs(ddy_fine(Y)))`를 대비 근사치로 사용한다.
`C < threshold`이면 현재 색상을 반환하고, 나머지는 원본 T2X의 velocity/history 읽기,
alpha 기반 가중치 및 색상 결합을 수행한다. 대비는 native current SRV가 제공하는
색 공간에서 계산한다. 일반 장면의 sRGB SRV에서는 디코딩된 linear RGB다.

- 추가 edge/contrast 텍스처, 후보 목록, atomic, indirect dispatch, GPU pass와 history 복사 없음.
- 현재 색상은 한 번만 샘플링하고, derivative는 분기 전에 계산한다.
- 선택된 경우의 velocity와 history는 mip 0을 명시한다. 해당 텍스처는 1 mip이며,
  divergent branch 안의 implicit LOD 의존을 피한다.
- 기존 native shader entry는 그대로 유지한다. 대비 경로와 진단 셰이더만 ps_5_0을 사용한다.
- 임계값은 기존 상수 버퍼의 미사용 `padding0`을 사용한다. 새로운 상수 버퍼가 없다.
- Original spatial SMAA, paired jitter/subsample, camera-depth reprojection, point history
  sampler, adaptive weight 0..0.5, spatial-frame history ping-pong은 유지한다.
- 기본값은 Off. 재투영 Off는 셰이더 컴파일만 검사하고, 이번 GPU gate는 On만 다룬다.
- 실제 object motion, depth rejection, 확장 마스크, AXAA 탐색 조절은 이번 범위에 없다.

이 대비는 AXAA의 local contrast 식이나 시간 변화량이 아니다. 2×2 pixel quad의
screen-space fine derivative 근사이며 얇은 구조나 quad 경계의 변화를 놓칠 수 있다.
threshold 판정이 프레임마다 바뀌는 현상과 global jitter를 남긴 채 temporal 결합을
생략하는 영향은 품질 검증 대상으로 남긴다. 선택률 감소가 곧 GPU 시간 감소를 뜻하지 않는다.

## 비교 설정

| ID | resolve | threshold |
|---|---|---:|
| O-T2X-R | 변경하지 않은 native Standard | 해당 없음 |
| ABL-Contrast-All-R | 대비 계산·분기 포함, 모두 선택 | 0 |
| ABL-Contrast-0005-R | 대비 선택 | 0.005 |
| ABL-Contrast-001-R | 대비 선택 | 0.01 |
| ABL-Contrast-002-R | 대비 선택 | 0.02 |
| ABL-Contrast-None-R | 모두 생략하는 경계 진단 | 2 |

0과 2는 처리 경계 및 오버헤드 확인용이다. 실용적인 최적 threshold로 취급하지 않는다.
All과 native의 시간 차이는 대비/분기뿐 아니라 ps_5_0, 샘플 순서와 explicit mip 0을 포함한
실험 경로 전체의 차이다. derivative 한 명령의 단독 비용으로 해석하지 않는다.
진단 캡처에는 `DBG-CurrentSpatial-R`, `DBG-ContrastMask-001-R`, `O-T2X-R-Repeat`도 포함한다.
진단은 같은 resolve draw의 출력만 바꾸며 별도 mask 생성 패스가 아니다.

## 실행 조건과 검증

원본 flythrough의 시간 2초 pose에서 시작한다. 60 frame 정지, 120 frame 이동(2→4초),
60 frame 정지의 240-frame 경로를 fixed 60 Hz로 실행한다. Mode마다 리소스 warm-up 후
frame 0에서 history와 jitter를 명시적으로 초기화한다. 앞의 정지 구간에서 history가
안정화된 뒤 이동을 시작한다. 이 경로는 이전 브랜치의 wide-yaw 경로와 다르므로 기존
성능·품질 절댓값을 직접 비교하지 않는다.

캡처는 장면별 9 mode × 240 frame이다. GPU 측정은 PNG와 debug/readback 없이 6개 설정을
300 warm-up + 4,800 frame × 3 repeats로 실행하며 mode 순서는 정방향/역방향/정방향이다.
모든 실행은 clean runner를 사용하고, 새 프로세스의 시작 전과 종료 후 CMAA2가 0개인지
검사한다. 이번 runner는 hidden window로 실행하며 full-screen 성능 주장을 하지 않는다.

원본 기준선의 `OnTick`에는 한 렌더 frame에 `BeginFrame`을 두 번 부르는 코드가 있었다.
GPU profiler frame 경계를 일치시키기 위해 두 번째 호출만 제거했다. 원본·실험 모든 mode에
같이 적용했다. 새 GPU timestamp scope는 공간 SMAA와 temporal resolve를 분리한다.

검증 도구:

- `validate_temporal_contrast_shaders.py`: native 8개 DXBC byte 일치, 실험 6개 entry/재투영
  조합 컴파일, fine derivative 명령과 current 샘플 재사용 및 추가 edge texture 부재 검사.
- `analyze_temporal_contrast.py`: 240-frame index/해상도, 원본 반복, 모두 선택=원본,
  모두 생략=공간 결과를 검사한다. 별도 mask를 캡처한 threshold 0.01에서는
  선택된 pixel=원본, 생략 pixel=공간 결과의 RGB 일치도 검사한다.
- 품질 보조 지표: native 대비 RGB 차이, 후기 정지 luma 시간 차분, 출력 hash 주기,
  threshold 0.01 GPU mask의 실제 선택 비율. Native 차이를 절대 품질 점수로 표현하지 않는다.
- Reference 기반 CGVQM/PSNR 측정은 이번 초기 검증에 포함하지 않았다.

초기 실패 캡처 `20260917_133425`는 첫 mode와 반복 mode의 이동 중 출력이 달랐다.
리소스 로딩 중 Tick이 정지한 상태에서도 렌더가 추가되어 jitter 위상이 달라지는 조건을
확인하고, timeline frame 0의 명시적 reset을 추가했다. 해당 초기 캡처와 단회 smoke timing은
결론에서 제외한다. 이후 정확성 gate를 통과한 자료만 결과에 사용한다.

Minecraft 첫 실행 `20260917_134224`는 9개 sequence와 PASS report를 저장한 뒤 종료 중
`0xc0000409`로 실패했다. dump의 예외 위치는 `abort`이며, 예외 thread의 stack 후보에는
`_purecall`과 `vaShader::CreateShader`를 부르는 background lambda가 있었다. 검증 완료 후
AutoBench가 이전 scene/settings를 복원한 상태에서 한 frame을 추가 렌더하고 다음 Tick에
종료하는 흐름을 제거했다. 이것은 temporal shader 변경이 아니라 자동 실행 종료 수정이다.
실패한 process는 정식 실행으로 취급하지 않고, 수정 후 독립 process의 정상 종료를 검증한다.
수정 후 Minecraft 실행 `20260917_134852`가 정상 종료됐고 이전 실행과 PNG 2,160개가 모두
SHA-256 일치했다. CPU 영상 분석은 이 완전 일치 검증 후 재사용했으며 유효 실행의 provenance로
기록했다. Bistro의 정상 캡처 바이너리와 이후 바이너리의 차이는 이 종료 흐름 수정이며,
실제 렌더 경로와 셰이더는 같다. 성능은 두 장면 모두 종료 수정 후의 동일 바이너리로 측정한다.

참고: [HLSL derivative의 quad 동작](https://microsoft.github.io/DirectX-Specs/d3d/HLSL_SM_6_6_Derivatives.html).
이 문서의 compute/mesh 확장을 사용하는 것은 아니며 이번 구현은 DX11 pixel shader다.

## 재현

저장소 루트에서 Release x64로 빌드한 뒤 실행한다. 기존 mode와 default는 그대로이며
아래 명령이 실험용 설정을 순회하고 자동 종료한다.

```powershell
python Tools/SMAA/validate_temporal_contrast_shaders.py
Tools/SMAA/run_temporal_contrast.ps1 -Phase Capture -Scene bistro
Tools/SMAA/run_temporal_contrast.ps1 -Phase Capture -Scene minecraft
Tools/SMAA/run_temporal_contrast.ps1 -Phase Benchmark -Scene bistro
Tools/SMAA/run_temporal_contrast.ps1 -Phase Benchmark -Scene minecraft
python Tools/SMAA/analyze_temporal_contrast.py --capture <capture-directory> --output <analysis-directory>
python Tools/SMAA/analyze_temporal_contrast.py --performance <results.csv> --output <analysis-directory>
```

GPU 작업은 순차 실행한다. 캡처·CPU 영상 분석과 성능 측정도 분리한다. 실행 receipt는
`tmp/temporal-contrast-runs.json`에 바이너리 해시와 함께 저장된다. PNG/GIF, raw CSV,
실행 파일은 Git에 포함하지 않는다.
