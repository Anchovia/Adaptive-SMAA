# 확보 소스 후보 생성 비용 분리와 진단 출력 최적화

기준 commit은 `d54c46c`, 작업 branch는 `research/tscmaa-source-candidate-reuse`다.
Original SMAA + source 후보 + source temporal + camera/depth reprojection On,
expansion None을 고정한다. Standard `O-T2X-R`과 source 별도 CS는 미변경 대조군이다.
현재 단계는 3주차 후보 생성 비용 조사이며 temporal 품질 요소나 최종 8-case 설정을 바꾸지 않는다.

## 조사 및 채택 조건

기존 integrated RGB 후보 PS에는 정적 Load 33개가 남아 있다. 9개 입력을 명시적으로
재사용하거나 Texture.Load의 범위 밖 0 반환을 이용하면 컴파일된 Load가 9개로 감소했다.
그러나 두 장면의 same-draw 후보 집합 검증에서 소수 차이가 발생했다. 산술 재배치와
곱셈-덧셈 최적화의 수치 영향을 추가로 분리해야 하므로 이 안들은 적용하지 않는다.
실패 실행과 셰이더는 로컬 `tmp/recovered-candidate-reuse`에 보존한다.
Microsoft Texture.Load 문서: https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load

이번 채택 후보는 수식을 그대로 유지하고, compact/indirect resolve에서 읽지 않는
base/selected 진단 mask와 base-edge 통계 atomic을 필요할 때만 출력하는 변경이다.
Readback On, forced-count 검증, debug mask 요청에서는 필요한 출력을 유지한다.
List, candidate count, indirect args, history 및 temporal kernel은 유지한다.
`SMAA_RECOVERED_OPTIONAL_DIAGNOSTICS=0`은 기존 unconditional 출력 대조군이고 1은 개선안이다.
후보 추출의 RGB Load 수는 이 변경에서 줄지 않는다.

## 검증 및 사전 성능 절차

- Release x64, FXC Original/Adaptive 및 RGB/raw 4개 PS 컴파일.
- 미변경 공간 PS 4개, source extraction/resolve CS bytecode 동일성.
- 두 장면 same-draw 후보/list/indirect/mask, 기본 8-case, lifecycle/feedback 검사.
- 두 장면 전체 480-frame final을 별도 CS 및 이전 source sequence와 비교.
- 최적화가 실제 활성화되는 readback Off 전체 final과 debug mask, forced count 검사.
- smoke 통과 후 fresh 교차 반복 측정. 각 장면 3 pair, 전→후/후→전/전→후 순서.
  각 독립 실행은 Standard/Source-Separate/Source-Integrated 3 mode, warm-up 300,
  4,800 frame, repeat 1이다. 전후 각각 장면별 3회 측정이며 과거 절대 수치로 대체하지 않는다.
- DX11 Release x64 Ultra 1920×1017, 기존 flythrough fixed 60 Hz, visible,
  VSync/UI/PNG/readback Off. 실행파일과 두 shader 파일 hash를 실행별로 기록한다.
- 전체 AA와 WholeFrame, spatial+candidate, resolve/copy 비용, 각 pair 변화와
  미변경 control의 변동을 함께 해석한다. 작은 표본의 통계적 한계를 기록한다.
- 품질 평가는 이번 동일 출력 gate와 구분한다. 출력이 같다면 새 CGVQM 계산은 하지 않는다.

실행 도구: `run_recovered_candidate_overhead.ps1`. 각 명령은 clean runner로 새 프로세스를
사용하고 종료/결과 PASS를 확인한다. 실패·부분 실행은 성능 평균에서 제외한다.
