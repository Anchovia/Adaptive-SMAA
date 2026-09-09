# Contrast-tier 후보 정책: 최소 구현 및 초기 검증

작성일: 2026-09-09. 구현 전 기준: `f88f026`.
상태: **최소 구현·초기 검증 완료. 전체 정확성 gate와 품질/성능 평가는 아직 미완료.**

## 1. 이번 변경

`SMAAWrapper.hlsl`의 integrated first-pass에서 이미 계산한 `finalDelta`를
`TSCMAAIntegratedSelectCandidate`에 전달한다. 기존 정책 0/1/2와 기본값은 보존하고
3개 experimental 정책만 추가했다.

|ID|정책|후보 조건|
|---|---|---|
|3|ExperimentalContrastHigh|surviving baseEdge AND finalDelta >= 1/3|
|4|ExperimentalContrastMediumHigh|surviving baseEdge AND finalDelta >= 0.1|
|5|ExperimentalContrastLow|surviving baseEdge AND finalDelta < 0.1|

이것은 공식 Intel TSCMAA 후보식이 아니다. 기존 Adaptive의 contrast-tier를 이용한
별도의 후보 선택 가설이다. `finalDelta`는 주변 여섯 luma 차이의 최댓값이며 temporal
필요도를 직접 측정하지 않는다. 새 정책에서는 Intel 후보 threshold/removal을 사용하지
않지만, SMAA의 원래 edge threshold와 local-contrast pruning은 유지한다.

새 정책의 판정은 추가 대각선 Load보다 먼저 끝난다. Original에 metadata MRT를
추가하지 않았고, 별도 edge pass나 metadata 재읽기도 없다. SMAA 2/3차 pass,
compact 형식, indirect resolve, sampling/clipping/feedback은 변경하지 않았다.

CLI `-smaaCandidatePolicyOverride 3|4|5`와 기존 진단 UI에서 선택할 수 있다.
Integrated source 2만 지원하며 Legacy/Post-pass 또는 forced-count 조합은 명시적으로
거부한다. CLI는 전체 override를 읽은 뒤 검증해 인자 순서에 의존하지 않는다.
Draw에도 같은 방어 조건을 두었다. 정책/source setter의 기존 history reset을 재사용한다.

기존 8-case 기본 설정은 변경하지 않았다. 이번 Original/Adaptive·reprojection Off/On
캡처는 공통 코드의 회귀 검사일 뿐 최종 8-case 재측정이나 Adaptive 결합 효과 검증이 아니다.

## 2. 컴파일 및 분기 검증

도구: `Tools/SMAA/validate_contrast_tier_compilation.py`.

- FXC `/O3 /Ges /WX`, Ultra, Original/Adaptive × RGB/raw 검사 PASS.
- 기존 spatial edge shader 4종의 변경 전후 bytecode hash 동일.
- 실제 dynamic integrated shader는 7 sample + 3 Load를 포함한다.
- disassembly에서 policy 3/4/5는 각각 비교만 실행하고, 3개 Load는 policy 1 분기 안에 있다.
- 정책을 상수화한 검증 variant에서는 새 정책 모두 7 sample + **0 Load**다.
  상수화 variant는 검사 도구일 뿐 실제 배포 셰이더로 사용하지 않는다.
- CPU float32 0.1/1/3의 아래·같음·위 경계 oracle PASS.

첫 `[branch]` 조기 반환 형태는 FXC `/WX`에서 potentially-uninitialized 경고가 발생했다.
강제 branch annotation을 제거한 최종 형태는 경고 없이 통과했고, 실제 생성된 dynamic
분기가 대각선 Load를 건너뛰는 것을 확인했다. 경고를 무시하거나 `/WX`를 끄지 않았다.

Release x64 최종 빌드 exit 0. 기존 C4834/C4100 및 빌드 후 `pwsh.exe` 미설치 메시지는
남아 있으므로 전체 프로젝트를 warning-free라고 표현하지 않는다.

## 3. 실제 GPU 경계 검사

`Tools/SMAA/contrast_tier_gpu_boundary_test.cpp`와 대응 `.hlsl`은 실제 production
wrapper를 include한 작은 D3D11 hardware compute 검사를 실행한다. 별도 장면이나
창을 만들지 않으며, 후보식의 복제본을 검사하지 않는다.

- 입력: float32 0.1/1/3 바로 아래·같음·바로 위, 0과 1.
- 정책 3/4/5에서 후보 판정 및 false base gate **48개 검사 PASS**.
- constant buffer의 정책 위치는 하드코딩하지 않고 shader reflection으로 찾는다.
- RGB integrated selector 호출의 경계 검사다. 전체 spatial sampling/edge pruning,
  실제 baseEdge 생성, 모든 raw 입력 조건을 증명하는 검사는 아니다.
- 이 작은 harness에서 false base gate는 상수이므로 production draw의 비edge 처리
  증거는 아래의 실제 GPU 마스크/비후보 출력 검사와 함께 해석한다.

재현: x64 VS 개발자 프롬프트에서 C++ 파일을 `/EHsc /W4`로 빌드하고
`d3d11.lib d3dcompiler.lib dxguid.lib`를 링크한다. 실행 시 작업 디렉터리는
`Projects/CMAA2/SMAA`, 인자는 대응 HLSL의 절대 경로다. 경로를 달리하면 nested include
검색이 실패할 수 있다. 실행에는 외부 timeout을 적용한다.

## 4. 실제 장면 GPU 마스크와 출력 검사

RTX 3060 Ti, DX11, Ultra, 1920×1017, Bistro 기본 경로 start 1초.
새 정책 검사는 warm-up 6, capture 3, readiness 1이며 hidden engineering capture다.
성능/FPS 결과로 사용하지 않는다. 각 명령은 독립 CMAA2 프로세스이고 timeout 180초,
정상 종료 및 잔류 프로세스 0을 확인했다.

도구:

- `Tools/SMAA/validate_contrast_tier_masks.py`
- `Tools/SMAA/validate_contrast_tier_outputs.py`
- 기존 `validate_temporal_capture_repeatability.py`의 finalized report/phase/index 검증 재사용.

결과:

- 4개 ET2X mode × 3 frame에서 High ⊆ MediumHigh PASS.
- Low ∩ MediumHigh = 공집합, Low ∪ MediumHigh = AllBase = 실제 base mask PASS.
- 모든 mask는 binary이고 base 바깥 후보 0. 화면 경계도 전체 이미지 검사에 포함.
- High 독립 반복 8 mode × 3 PNG의 phase/hash mismatch 0.
- 세 정책의 4 ET2X mode × 3 frame = **36장**에서 비후보 `final != CurrentSpatial` 픽셀 0.
- 기본 8개 mode는 기존 자료와 동일 start 1초/warm-up 30/capture 12로 재캡처해
  **96 PNG byte-hash mismatch 0**.
- 기존 lifecycle: resets 60, frames 158, seed 35, resolve 123, reprojection 92,
  failures 0. 기존 feedback: output/history 및 visible mismatch 0 byte,
  previous-history hash mismatch 0.

예시 한 프레임의 base는 49,896개이고 High 3,638, MediumHigh 12,754, Low 37,142개다.
이는 기능 확인용 한 pose의 분포일 뿐 장면 평균이나 품질/성능 결과가 아니다.

처음 기존 출력과 비교할 때 검사기가 warm-up 6 대 30의 불일치를 거부했다.
허용오차를 완화하지 않고 30-frame warm-up으로 다시 캡처해 96장 일치를 확인했다.
CurrentSpatial debug는 Standard의 최종 resolve 화면과 다르므로, Standard control은
debug 화면이 아닌 같은 6-frame warm-up의 기본 final capture와 대조했다.

## 5. 유효 실행 및 산출물

아래 ID는 모두 `D:/SMAA-Research-Data/AutoBench/` 아래에 있다.

|실행 ID|용도|
|---|---|
|20260909_164836|High mask|
|20260909_164922|MediumHigh mask|
|20260909_164954|Low mask|
|20260909_165008|AllBase mask|
|20260909_165130|실제 BaseEdges debug|
|20260909_165159|High mask 독립 반복|
|20260909_165700|High final|
|20260909_165713|MediumHigh final|
|20260909_165749|Low final|
|20260909_165818|CurrentSpatial|
|20260909_165904|기본 final, warm-up 6|
|20260909_170111|기본 final, warm-up 30, 기존 151322와 96장 비교|
|20260909_165931|기존 lifecycle|
|20260909_170034|기존 feedback|

컴파일·mask·output JSON과 실행 manifest는 `tmp/contrast-tier/`에 생성했다.
이 디렉터리와 바이너리/PNG는 Git에 올리지 않는다. 재현용 검사 소스와 본 문서만 보존한다.

미지원 source=0 + policy=3 및 integrated + policy=3 + forced-count=1 음성 검사는
`no benchmark queued` 오류를 기록하고 종료했다. 새 results CSV가 없으므로 clean runner는
의도대로 실패로 분류했다. 이 두 실행을 정상 측정 결과로 집계하지 않는다.

## 6. 남은 정확성 gate 및 다음 순서

아래를 완료하기 전에는 품질/성능 비교로 확대하지 않는다.

1. 실제 tier로 생성된 compact list와 control counters를 **동일 GPU frame**에서
   readback해 candidate=process, ceil(count/64), 중복/OOB/overflow 0을 직접 확인.
   기존 forced-count 검사는 실제 contrast 선택을 우회하므로 이것의 대체 증거가 아니다.
   기존 비동기 counter와 다른 frame의 목록을 섞지 않도록 전용 snapshot 설계가 필요하다.
2. 전용 gate 안에서 tier 정책을 전환하면서 reset/override 복원 검증. 이번 기존 lifecycle
   PASS를 새 정책 전환 전체 검사로 확대 해석하지 않는다.
3. 필요 시 production first-pass finalDelta 진단 readback과 CPU 분류 mirror를 추가.
   현재 마스크 집합 불변식과 경계 harness는 전체 영상의 exact classifier mirror와 다르다.
4. 위 gate 이후에만 Original + camera/depth R, expansion None의 5정책(Intel/AllBase/
   High/MediumHigh/Low) 소규모 Bistro/Minecraft 비교. 같은 warm-up과 prefix pre-roll을
   유지하며 central-motion 60 / motion-to-still 30 frame으로 시작한다.

**결론:** 정보 재사용형 후보 정책을 추가하고 초기 경계·마스크·출력 회귀는 통과했다.
후보를 줄일 수 있다는 관측을 temporal 품질 유지나 GPU 속도 향상으로 해석하지 않는다.
