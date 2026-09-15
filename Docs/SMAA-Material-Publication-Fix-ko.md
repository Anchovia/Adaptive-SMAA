# 재질 로딩 완료 전 UID 공개 수정

2026-09-15, 후보식 비교 실험 중 발견. AA 셰이더 수식 변경과 구분한다.

## 관측과 코드 경로

Minecraft mask 준비에서 두 독립 프로세스가 정체했다. 첫 PID 3824는 약 214초,
두 번째 PID 20184는 로컬 덤프 수집 후 수동 종료했다. 자동 timeout 600초 이전의
중단이며 두 시도 모두 결과에서 제외한다. 첫 시도에는 CPU 이미지 분석이 병행됐고
두 번째에는 병행되지 않았으므로 CPU 분석만의 원인으로 설명하지 않는다.

두 번째 덤프에는 `vaMaterialBasic.hlsl:158`의 `error X3004: undeclared identifier
'VA_RM_INPUT_LOAD_Albedo'` 및 비어 있는 VS entry를 포함한 컴파일 오류 메시지가 있었다.
컴파일러 오류 경로는 background worker에서 재시도 MessageBox 응답을 기다리도록 되어 있다.
Computer Use에는 해당 숨겨진 창이 노출되지 않아 창 조작 없이 로컬 진단 덤프로 확인했다.
덤프 전체는 로컬에만 보존한다. 이 증거를 이전 블루스크린 원인 규명으로 확대하지 않는다.

확인한 코드 경로:

1. Sample은 asset pack을 비동기로 로드한다.
2. `CreateAndLoadAPACK`은 `CreateRenderMaterial(uid)` 다음에 `LoadAPACK`을 호출한다.
3. 기존 factory는 `UIDObject_Track()`을 즉시 호출한다. 재질 생성자는 shader entry와
   기본 input을 초기화하지 않으므로 이 시점은 deserialization 완료 전이다.
4. Renderer는 UID로 찾은 재질이 nullptr가 아니면 `SetToRenderItem`을 호출할 수 있다.
   입력과 entry가 아직 채워지지 않은 재질을 조회할 수 있는 경쟁 경로다.
5. Pack의 `InsertAndTrackMe`는 이미 로딩이 끝난 뒤 UID를 등록하는 경로를 갖고 있다.

## 수정과 검증

Factory에 기본값 true인 `trackUID`를 추가했다. APACK/unpacked asset loader만 false로
생성하고, 기존 pack 삽입 시점에 공개한다. 일반 factory 호출과 default material은 기존의
즉시 등록을 유지한다. 실패한 deserialization 결과는 UID에 공개되지 않는다.

`-smaaMaterialPublicationTest`는 메모리 stream에 저장한 기본 재질을 **실제 APACK loader**로
읽는다. 모든 stream Read 직전에 UID 조회를 삽입해 로딩 도중 renderer가 조회하는 상황을
검사한다. 로딩 완료 직후에도 비공개이며 pack Add 후에는 조회 가능하고, unload 후에는
사라지는지 확인한다. 일반 factory의 즉시 등록도 대조한다.

두 독립 실행 `20260915_200849`, `20260915_200856`에서 stream reads 3,
premature visibility 0, 로딩 후 비공개/pack 공개/unload/일반 factory 대조 모두 PASS다.
Release x64 빌드가 통과했다. 이후 실제 장면 재캡처와 AA 출력 회귀 결과는
[후보식 비교 결과](SMAA-Candidate-Selection-Gate-Results-ko.md)에 기록한다.

이번 수정은 관측 오류와 부합하는 재질 조기 공개 경로를 제거한다. 모든 종류의 asset
loading 경쟁, compiler 오류 또는 운영체제 오류가 해결됐다는 보장은 아니다.
