# Contrast-tier compact 목록·정책 전환 검증

작성일: 2026-09-10. 구현 기준: `ee14ff7`.
분류: **정확성/회귀 engineering gate. 품질·성능 측정 아님.**

## 1. 목적과 구현

전날 추가한 High/MediumHigh/Low 정책이 실제로 만든 후보 목록을 검증했다.
기존 forced-count 경로는 실제 후보 선별을 우회하므로 재사용하지 않았다.

새 `ReadCandidateSnapshot`은 검증 요청이 있을 때만 완료된 draw의 다음 리소스를
staging으로 복사한다.

1. 현재 control counter buffer
2. 현재 packed candidate list
3. 실제 DispatchIndirect argument buffer
4. 현재 base-edge mask
5. 현재 selected-candidate mask

다섯 CopyResource를 다음 프레임 전에 같은 immediate context에 제출한 뒤 Map한다.
오래된 프레임일 수 있는 비동기 통계 ring의 CPU 결과는 사용하지 않는다.
Map의 RowPitch를 적용해 R8 mask를 해석하며, 실패 시 Valid=false로 검사에 실패한다.
임시 리소스는 함수 종료 시 해제한다. 일반 Draw/성능 benchmark는 이 함수를 호출하지
않으므로 진단용 GPU 동기화·readback·CPU 목록 검사는 timing에 포함되지 않는다.

이 API는 integrated source, expansion None, CompactIndirect, forced-count Off,
counter readback On 및 BaseEdges/SelectedCandidates debug view에서만 사용할 수 있다.
임의 설정의 general-purpose capture API가 아니다.

`-smaaContrastTierSnapshotTest`는 Original SMAA + camera/depth reprojection On으로
Bistro/Minecraft를 고정 카메라에서 검사한다. 순서는 각 장면에서
Intel → AllBase → High → MediumHigh → Low → High → Intel이다.
정책 변경 시 reset counter 증가를 확인하고 다음 draw의 history seed/phase 0을 검사한
뒤, 8번째 정상 draw에서 resolve가 수행된 snapshot을 읽는다.

테스트가 바꾸는 candidate policy/source/expansion은 enabled flag와 **저장된 override
값**을 각각 보존한다. readback, direct-mask toggle, debug view, lifecycle-enabled 상태도
복원하고 검사한다. 비활성 override의 저장값을 현재 mode의 effective 값으로 바꾸지 않는다.
종료되지 않고 work item이 해제되는 경우에도 destructor에서 override 복원을 시도한다.
이 검사는 모든 애플리케이션/UI 상태의 bit-exact 복원 인증은 아니다.

## 2. 검증 결과

환경: RTX 3060 Ti, DX11, SMAA Ultra, 1920×1017, hidden engineering 실행.
각 명령은 별도 CMAA2 프로세스, timeout 180초, 종료 후 잔류 프로세스 0.

최종 실행:

- `20260910_113501`: 기본 초기 설정, 14개 snapshot PASS.
- `20260910_113549`: policy 2/source 1/debug 3/direct-mask On override를 준 상태로
  시작한 독립 재실행, 14개 snapshot과 종료 시 override 복원 PASS.
- 두 실행의 14개 snapshot 결과 행은 모두 동일했다.

검사 항목과 결과:

|항목|결과|
|candidate count = process count|모두 일치|
|groups = ceil(candidate/64)|모두 일치|
|실제 indirect args = (groups, 1, 1)|모두 일치|
|compact 좌표 중복 / 범위 밖 / capacity overflow|각각 0|
|목록 좌표 집합과 selected mask 차이|0|
|base/selected mask 픽셀 수와 counter 차이|0|
|binary mask 위반 / base 밖 selected|0|
|High ⊆ MediumHigh|PASS|
|Low ∩ MediumHigh = 공집합|PASS|
|Low ∪ MediumHigh = AllBase = base|PASS|
|다른 정책 방문 후 High/Intel로 돌아온 mask|동일|
|정책 전환 직후 seed/phase 0|14단계 PASS|
|테스트가 변경한 override 복원|PASS|

한 고정 pose의 후보 수는 다음과 같다. 이 값은 장면 평균이나 성능/품질 결과가 아니다.

|정책|Bistro|Minecraft|
|---|---:|---:|
|AllBase|48,346|544,952|
|Intel-family|27,759|342,046|
|High|3,564|15,295|
|MediumHigh|14,557|255,520|
|Low|33,789|289,432|

## 3. 기존 렌더링 회귀

- Release x64 빌드 성공. 기존 C4834/C4100 및 `pwsh.exe` 미설치 메시지는 남는다.
- `20260910_113619`: 기본 8-case, start 1초/warm-up 30/capture 12/readiness 1.
  이전 `20260909_170111`과 **96 PNG hash mismatch 0**, phase failure 0.
- `20260910_113653`: 기존 feedback 검사에서 output/history 및 visible mismatch 0 byte,
  previous-history hash mismatch 0, Aggregate PASS.
- 이번 변경에는 HLSL 후보식, SMAA 공간 처리 및 일반 temporal resolve 변경이 없다.

## 4. 중간 실패 기록

최초 `20260910_113204`에서는 14개 목록/마스크 검사와 seed가 모두 통과했지만
override restoration 검사만 실패했다. 비활성 override 저장값 대신 현재 mode의
effective 값을 저장/비교한 진단 구현 문제였다. raw override getter를 추가해 flag와
저장값을 별도로 보존한 뒤 `20260910_113343`에서 통과했다.
이후 실제 indirect args 검사까지 보강한 최종 두 실행을 위의 유효 결과로 사용한다.
실패 실행을 정상 결과로 덮어쓰거나 집계하지 않는다.

## 5. 해석과 다음 단계

**현재 대비 정책의 후보 목록 생성·indirect 실행 연결·정책 reset/복원 검증을 통과했다.**
따라서 후보 수 감소가 잘못된 compact 또는 오래된 통계값에서 비롯됐다는 문제는
검사한 조건에서 관찰되지 않았다. 이것이 temporal 품질이나 속도 개선을 뜻하지는 않는다.

아직 전체 영상에 대해 production finalDelta를 직접 readback한 exact CPU classifier
mirror는 없다. 전날 GPU 경계 검사와 실제 영상 mask 불변식, 이번 목록 snapshot은
각기 다른 검증이며 이를 전체 수학적/시각적 정확성 증명이라고 표현하지 않는다.

다음은 Original + camera/depth R + expansion None으로 5정책(Intel/AllBase/High/
MediumHigh/Low)을 비교하는 작은 품질 gate다. Bistro/Minecraft의 wide 경로에서
central-motion 60프레임 및 motion-to-still 30프레임을 같은 초기 warm-up과 prefix
pre-roll로 캡처해야 한다. O-1X와 O-T2X-R을 해석 control로 포함한다.
후보 감소뿐 아니라 history 영향, 얇은 구조 보존, flicker 및 reference 오차를 함께 본다.
Adaptive 결합, 3×3/ARM, threshold sweep과 정식 성능 확대는 아직 하지 않는다.

원시 자료는 모두 `D:/SMAA-Research-Data/AutoBench/<실행 ID>/`에 보존한다.
96장 회귀 분석 JSON은 `tmp/contrast-tier/snapshot-regression.json`이다.
