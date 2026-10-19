# ⑰ 코드 정리·출력 보존 최적화: 2026-10-19 인계 재개

기존 `experiment/edge-history-color-blend-optimization`의 `1b7eaca`에서 이어받았다.
정리본 의존성은 `d2a6315`, 원래 ⑰ 기준은 `5bdd189`이다. 기본 checkout의 사용자 변경과
`c17-before` runner의 의도된 변경을 건드리지 않았다. 이번 변경은 실행·검증 도구에만 적용한다.

## 확인과 수정

- `c17-opt`와 `c17-cleanup`은 인계 당시 커밋 및 추적 브랜치와 일치했고 수정 파일이 없었다.
- Release x64 재빌드 PASS. `535d0b3`의 프레임별 1920×1061 검사가 포함됐다.
  실행 파일 SHA-256은 `C83A5E29CB5A5F79ECF1BC3F2850CE4763FD921C957B4328DBDCDA8BE35C2638`이다.
  기존 코드에서 C4834(반환값 미사용), C4100(매개변수 미사용) 경고 2개가 나왔다.
- runner의 Git 조회는 sandbox와 소유자의 Windows SID 차이로 실패했다. 선택한 worktree만
  해당 호출의 `safe.directory`로 지정하고, Git 실패 시 실행 전에 중단하도록 수정했다.
  전역 Git 설정과 공유 저장소의 손상 object는 수정하지 않았다.
- `ApplicationSettings.xml`에는 제외된 실행의 1902×1001 창 크기가 실제로 남아 있었다.
  runner가 실행 전에 기존 기준과 같은 1920×1061, windowed(소스 enum 값 1), 자동 위치(-1/-1)를
  복원하고 receipt에 예상 해상도를 남기도록 수정했다. 파일 내 키가 없거나 중복이면 실행하지 않는다.
  실행 중 창 변경을 막아주는 기능은 아니므로 프레임별 해상도 검사를 계속 사용한다.
- 기존 RGB verifier는 발견된 모드만 검사해서 결합 모드 누락을 허용했고, RGB 불일치를 출력해도
  프로세스 종료값은 0이었다. 이제 정확히 6개 모드와 모드당 f0~239 전체 PNG/위상 행을 요구한다.
  ④ jitter는 짝/홀 `(0.25,0.25)`/`(-0.25,-0.25)`, ⑰ 후보들은 `(0,0)`이어야 한다.
  중복 행, frame 누락, 해상도/형식, report hash와 scene, 원본 기록 길이/scene도 확인한다.
  불일치 프레임을 모두 기록하고, PNG가 있는 상대와의 비교에서는 처음 20개 불일치의
  변경 픽셀 수·최대 채널 차이·bounding box를 기록한다. 실패 또는 불일치는 종료값 1이다.
- reference capture hash는 mode마다 반복 decode하던 구조에서 두 control을 한 번씩 읽는 구조로 바꿨다.
  RGB 비교식과 렌더링 코드는 바꾸지 않았다.

## 도구 검증 범위

GPU 없이 작은 무손실 PNG로 12개 테스트 PASS: 정상 6-mode, 결합 모드 누락, 검사 행 누락/중복,
native 시작 위상 오류, 크기 변경, PNG 누락, 짧은 원본 hash 목록, report 변조, 거짓 Aggregate PASS,
결합 모드 1픽셀 차이(최대 7·좌표 일치), ④ 회귀. PowerShell 구문 검사와 창 설정의 메모리 내
복원/키 누락 거부도 PASS했다. 실제 창 설정 파일은 이 테스트에서 변경하지 않았다.

기존 Bistro `opt-b`를 새 도구에 넣으면 결합 모드가 없는 과거 5-mode 실행이므로 예상대로
실패한다. 이는 과거에 검증한 5개 모드의 RGB 동일성을 철회하는 것이 아니라 새 6-mode gate를
완료했다고 오인하지 않게 하는 검사다. 이전 기록과 원시 자료는 그대로 보존했다.

실제 제외 자료 `opt-c`도 다시 읽어, Aggregate PASS였던 Bistro 캡처를
`OPT-NeighborhoodNoDepth/frame_00057.png`의 RGB 1902×1039 크기에서 실패로 거부했다.
이는 기존 파일의 CPU 재검증이며 CMAA2 재실행이나 새 품질·성능 결과가 아니다.

이번 세션에서 CMAA2 실행, 새 출력 캡처, 원본 프레임 직접 검사, 성능 측정은 아직 하지 않았다.
12개 테스트는 검증 도구 테스트이며 GPU 출력 동일성 검증을 대신하지 않는다.
O3와 결합 모드의 visible alpha 변경에 대한 채택 결정도 하지 않았다.

## 다음 실행

인계문의 사용자 지시대로 캡처 허용/PC 미사용 확인 및 별도 성능 허용을 기다린다.
각 명령 전후 CMAA2 0개, 독립 프로세스, 1,200초 timeout 조건을 유지한다.

새 capture 저장 계획은 `C:/Users/USER/Desktop/research/tmp/c17-resume-20261019`이다.
두 장면×6모드×240장=2,880 PNG다. 실제 `opt-b` native PNG 평균에 근거한 예상은 약 5.82 GiB이며,
decoded RGB 총량은 약 16.39 GiB다. 20 GiB 여유를 잡는다. 시작 시 C 약 178.83 GiB,
D 약 730.45 GiB를 확인했다. 새 capture 폴더는 아직 만들지 않았고 기존 자료 삭제도 없다.

worktree `C:/Users/USER/Desktop/research/tmp/worktrees/c17-opt`에서 장면별로 순차 실행한다.
명령 사이 대기가 Minecraft 초기 정지를 줄이는지는 여전히 미확인 가설이다.

```powershell
# 캡처 허용 후, scene을 bistro / minecraft로 각각 실행
Tools/SMAA/run_color_blend_preservation.ps1 -Harness Optimization -Phase Capture -Scene bistro -Label opt-d -OutputRoot C:/Users/USER/Desktop/research/tmp/c17-resume-20261019

$env:COLOR_BLEND_RUNS = Join-Path (Get-Location) 'tmp/cleanup-runs.json'
& 'C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' Tools/SMAA/verify_color_blend_optimization.py opt-d --reference after-a --record Docs/Edge-History-Source-Color-Blend/bistro-capture.json --scene bistro --out Docs/Edge-History-Color-Blend-Optimization/verify-opt-d-bistro.json
```

Windows Store의 `python`/`py`는 sandbox에서 실행되지 않았으므로 위 bundled Python 3.12.14,
NumPy 2.3.5, Pillow 12.3.0을 확인해 사용했다.
결합 모드 검증 후 이동 f126~131, 실패 주변 f124~133, 전환 f178~183, 정지 f230의 원본 PNG와
nearest 확대를 직접 확인한다. 이후 사용자 허용 범위 내에서 장면별 Smoke→Benchmark와 정리 전후
ABBA를 진행한다. 과거 Bistro 수치는 `interim-performance.json`의 이전 측정이며 이번 새 결과가 아니다.
