# O-T2X 캡처 시작 위상 차이 조사 및 교정

작성일: 2026-09-09. Engineering 회귀 검증이며 새 품질·성능 측정이 아니다.
기준: `075fc7f`, `research/et2x-pipeline-optimization`.

## 1. 결론

이전 luma 재사용 검증에서 남았던 Bistro O-T2X의 12-frame 차이는
**캡처 시작 T2X 위상 차이**로 재현·분리했다.
같은 새 실행파일의 legacy 캡처 대조는 위상 1에서 시작했고,
readiness를 warm-up과 분리한 경로는 의도한 위상 0에서 시작했다.
교정 후 준비 대기를 1/2/7 stable tick으로 바꾼 세 독립 실행의 8 mode×12 PNG는
모두 byte-identical이며 phase 검사 실패도 0이다.

SMAA/TSCMAA 셰이더, 후보 수식, jitter 두 위치, history blending, feedback,
카메라 경로와 성능 benchmark는 이번 변경에서 수정하지 않았다.

## 2. 왜 이런 일이 발생했는가

`CMAA2Sample::OnTick`은 직전 draw에 shader/resource 준비 flag가 있으면 AutoBench의
논리 frame 진행을 멈추지만 렌더링 자체는 계속 수행한다.
기존 `BenchItemRecordSMAATemporalMatrix`는 첫 mode를 선택한 tick부터 warm-up을 세며,
준비 렌더 뒤 명시적으로 history/phase를 초기화하는 경계가 없었다.
그림자 준비를 위한 frame -1 대기 역시 렌더 횟수와 논리 frame 수를 분리할 수 있다.

따라서 같은 capture frame index라도 실제 T2X가 처리한 준비 프레임 수에 따라
projection jitter/subsample의 시작 위상이 달라질 수 있다.
이번 대조는 시작 위상과 출력 차이를 확인한 것이며, 과거 각 실행의 추가 렌더가
shader compilation 때문인지 shadowmap 때문인지까지 사후 확정한 것은 아니다.
warm-up을 단순히 30→31로 늘리는 실험만으로는 과거 두 hash가 분리되지 않았다.

## 3. 변경한 부분

`Projects/CMAA2/CMAA2Sample.cpp`의 기존 temporal-matrix 캡처 제어만 수정했다.

1. 각 mode 선택 후 첫 warm-up pose에서 준비 렌더를 먼저 수행한다.
2. 기존 AutoBench draw-readiness 검사와 shadowmap 준비가 끝나기를 기다린다.
3. 준비 구간이 끝나면 history를 reset한다.
4. 그때부터 요청한 warm-up과 capture frame을 진행한다.
5. `CapturePhase` 행에 mode, capture index, 실제 phase, jitter XY, seed/resolve를 기록한다.

각 mode마다 같은 경계를 적용한다. Lifecycle 진단은 캡처 중 활성화하고 종료 때
기존 활성 상태를 복원한다. 성능 측정 경로에는 이 진단 비용을 추가하지 않았다.

기존 명령의 첫 세 인자는 유지하고 네 번째 optional 인자를 추가했다.

```text
-smaaEightCaseCapture "1 12 30"
-smaaEightCaseCapture "1 12 30 2"
```

순서는 startTimeSeconds, captureFrames, warmupFrames, readinessFrames다.
마지막 값의 기본값은 1이고 1..120은 준비 stable tick 수다.
`0`은 원인 비교를 위한 **legacy 진단 전용**이며 정식 캡처로 승인하지 않는다.
OriginalFour 및 CandidateEdgeSource capture도 같은 class를 사용한다.
다른 camera-motion capture class나 기존 formal 성능 matrix는 변경하지 않았다.

## 4. 실행 결과

RTX 3060 Ti, 1920×1017, Ultra, 기존 Bistro flythrough start 1.0 s,
30 warm-up + mode당 12 PNG. 모든 캡처는 Hidden, 독립 clean process다.

| Run | 구성 | 결과 |
|---|---|---|
| 20260909_150639 / 150720 | 수정 전 기존 실행파일 반복 | O-T2X는 기존 74e9…와 일치, 다른 7 mode도 반복 동일 |
| 20260909_150836 | 수정 전 OriginalFour, warm-up 31 | O-T2X는 여전히 74e9…; 단순 warm-up 증가만으로 분리 불가 |
| 20260909_151322 | 새 경로, 준비 1 tick | 모든 mode의 capture 시작 phase 0 |
| 20260909_151407 | 새 경로, 준비 2 tick | 위 96 PNG와 hash mismatch 0 |
| 20260909_151552 | 같은 새 실행파일, legacy 0 | O-T2X 시작 phase 1, 대응 12 PNG 차이; 나머지 7 mode 동일 |
| 20260909_151651 | 새 경로, 준비 7 tick | 위 96 PNG와 hash mismatch 0 |
| 20260909_151742 | temporal lifecycle 회귀 | resets 60, frames 157, seed 35, resolve 122, reprojection 92, failures 0 |

새 경로의 phase는 `(warmupFrames + captureFrame) % 2`와 일치했다.
Standard의 phase 0 jitter는 (+0.25,+0.25), phase 1은 (-0.25,-0.25)이며
document ET2X의 deliberate jitter는 0이다. 모두 valid history resolve였다.
검증된 세 실행은 총 288 PNG이고 두 실행을 첫 실행과 대조한 192쌍 모두 동일했다.

더 중요한 회귀 확인: 새 경로 `151322`의 96 PNG 전체가 luma 변경 전
`20260909_141949`와 일치했다. O-T2X 첫 hash는 `9f5bfe4be601ed54…`다.
이는 앞선 ET2X 출력 보존 결과와 함께, 당시 O-T2X 차이를 luma 변경의 화질 회귀로
해석해서는 안 된다는 근거다.

## 5. 검증 도구와 빌드

`Tools/SMAA/validate_temporal_capture_repeatability.py`는 다음을 검사한다.

- mode별 정확한 PNG index 집합과 finalized report 존재
- frame당 CapturePhase 행 1개, 예상 phase/jitter와 valid history
- 동일 mode/warm-up/frame 조건끼리 PNG SHA-256 일치
- legacy 경로 또는 불일치는 기본적으로 실패 반환

`--allow-legacy`는 원인 조사 결과를 기록하기 위한 옵션일 뿐 PASS로 바꾸지 않는다.
실제 legacy 대조는 phase 실패 12, hash mismatch 12로 기록됐다.
결과 JSON은 로컬 `tmp/luma-reuse/readiness-three-repeat.json` 및
`readiness-legacy.json`, 원시 capture는 `D:\SMAA-Research-Data\AutoBench`에 있다.

Release x64 MSBuild는 단일 node와 기존 환경 정규화 스크립트로 성공했다.
기존 C4834/C4100 warning과 pwsh 경로 경고는 있었으며 warning-free라고 표현하지 않는다.
산출 실행파일로 모든 위 GPU 검증을 통과했고, 각 실행 뒤 잔류 CMAA2는 0개였다.

## 6. 적용 범위와 다음 작업

이 gate는 짧은 Bistro temporal-matrix 캡처의 시작 위상 결정성을 교정한다.
모든 장면·다른 캡처 class·전체 timeline의 결정성을 일괄 보증하지 않는다.
기존 자료를 전부 폐기할 필요는 없지만, 이 legacy class의 O-T2X 자료를 정확한
픽셀 회귀 기준으로 재사용할 때는 phase/hash bridge를 먼저 확인해야 한다.

다음은 luma 재사용 전후의 긴 교차 성능 측정이다. 약 0.5%의 예비 차이를
실제 가속으로 주장하기 전에 실행 간 변동과 분리한다.
이번에는 새 성능 결과나 새 candidate policy를 추가하지 않았다.
