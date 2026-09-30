# 연구 항목별 브랜치 분리

상위 AGENTS.md의 연구 규칙과 함께 적용한다. 사용자의 2026-09-28 지시를 기록한다.

- 연구 항목 하나당 브랜치 하나를 사용한다. 이름만 새로 만들고 이전 실험의 모든 변경을
  누적 상속하는 방식을 항목 분리로 간주하지 않는다.
- 새 항목은 검증된 공통 기준선에서 직접 분기한다. 다른 항목의 코드가 필요하면 먼저
  의존성을 명시하고 필요한 커밋만 가져온다. 여러 연구 기법의 결합은 별도 통합 브랜치에서 한다.
- 작업 시작 전에 현재 branch/base/dirty files를 확인한다. 미완료 변경은 원래 항목의
  브랜치에 미검증 상태로 보존하고 다른 항목으로 몰래 가져오지 않는다.
- 분기 이름은 `baseline/`, `validation/`, `experiment/`, `research/`, `tooling/`의
  프로젝트 관례를 따른다. `codex/`는 사용하지 않는다.
- `validation/smaa-baseline-restart`에서는 원본 AA-Off/O-1X/O-T2X/O-T2X-R의 독립
  기준선 검증만 수행한다. Edge 선택, 지터 보정, 후보 확장, Adaptive 결합을 추가하지 않는다.
- 실제 O-1X는 `AAType::SMAA` 경로로 실행한다. 지터 On current-spatial 진단을 일반
  SMAA 1X 또는 AA Off로 대체하거나 그 점수를 재사용하지 않는다.
- 어떤 픽셀에서 temporal을 생략하는 새 연구는 비선택 출력과 지터 정책을 먼저 명시한다.
  수식 일치만으로 품질 검증이 끝났다고 하지 않는다. 기존 지터 실패 실험을 먼저 검토한다.
- 소스 동일성, 실행 출력 동일성, 품질 개선, 성능 개선을 각각 구분한다. 검증되지 않은
  범위를 완료로 표시하지 않는다. 실패 실행과 철회한 해석은 원시 자료와 함께 구분해 보존한다.
- 기본 8-case의 semantic ID와 camera/object-motion 구분, clean process 규칙은 유지한다.


## 2026-09-30: SMAA stencil 초기화 수정 기준선

- Intel CMAA2 sample에 포함된 SMAA DX11 통합 코드의 매 프레임 stencil 초기화 누락을
  수정한 독립 6-case 브랜치를 사용한다. SMAA 알고리즘 자체의 결함이나 새로운 AA
  알고리즘으로 표현하지 않는다. 기존 브랜치와 수치는 과거 실행 조건의 기록으로 보존한다.
- 해당 브랜치의 출발 커밋·대상은 `Docs/Stencil-Lifecycle-Refresh/case.json`, 검증 조건은
  같은 디렉터리 `method.md`, 결과는 장면별 `capture.json`/`benchmark.json`에 기록한다.
- 공간 SMAA는 전용 stencil을 해당 edge pass 전에 초기화한다. ⑤의 raw exact-edge
  초기화와 ⑥의 기존 초기화는 중복 실행하지 않는다. ① AA-Off 및 ③ full temporal-only에는
  사용하지 않는 SMAA stencil clear를 강제로 추가하지 않는다.
- 이후 연구 항목은 대응하는 수정 기준선에서 다시 독립 분기한다. 아래 브랜치를 하나로
  합쳐 여섯 구현을 뒤섞지 않는다. 같은 브랜치의 ④는 비교용 대조군이다.
- ①: `baseline/aa-off-stencil-lifecycle`
- ②: `baseline/smaa-1x-stencil-lifecycle`
- ③: `baseline/temporal-only-stencil-lifecycle`
- ④: `baseline/smaa-t2x-r-stencil-lifecycle`
- ⑤: `experiment/first-edge-temporal-only-stencil-lifecycle`
- ⑥: `experiment/spatial-first-edge-stencil-lifecycle`
- 성능 변화율은 같은 실행의 수정된 ④ 대비로 계산한다. 다른 실행의 절대 시간은 paired
  변화율의 분모로 쓰지 않는다. 초기화 수정에 따른 공간 비용 감소를 temporal 선택의
  효과로 합산하지 않는다. 전체 AA, temporal resolve, camera velocity 시간을 구분한다.
- ③·④는 원본 paired pattern On, ⑤·⑥은 Pattern Off이므로 그 차이를 모두 선택 처리의
  효과라고 주장하지 않는다. 이번 여섯 control은 최종 Adaptive 8-case 행렬과 구분한다.
- 두 장면의 240-frame RGB가 보존된 품질 입력 및 반복 캡처와 동일한 경우에만 기존
  CGVQM-2 점수를 재사용한다. 이를 모델 재실행 또는 새 품질 개선으로 표현하지 않는다.
- 자동 실행 전 저장된 시작 장면을 요청 장면으로 맞춘다. 이 준비는 AA 계산이나 측정
  타임라인을 바꾸지 않는다. 초기 준비가 멈춘 실행은 기록만 보존하고, 정상 완료된
  독립 실행만 채택한다. 자세한 제외 기록은 ①의 excluded-startup-stalls.json에 있다.

## 선택 범위와 sample-pattern 대조 실험

- `validation/spatial-edge-coverage-pattern-control`은 수정된 ⑥ `304f749`에서 직접 분기했다.
  이전 history contribution, ⑤ raw, TSCMAA source kernel 및 dilation 코드를 상속하지 않는다.
- 새 대조군은 ⑥과 동일한 spatial/resolve/input/history 경로를 쓰면서 resolve의 stencil
  test만 비활성화한다. 같은 지터 Off 조건에서 coverage 효과를 분리한다.
- 기존 ④ native Pattern On과 native Pattern Off 보조 대조를 포함한다. matched full Off와
  native full Off의 출력 일치를 검사한 뒤에만 ④와 sample-pattern 차이를 해석한다.
- full Off 반복은 관측 MRT를 끈다. 기존 ⑥·④ RGB 회귀, current/previous/velocity 입력
  hash, 선택 영역 출력 일치, 비선택 current 보존, 실제 GPU coverage를 검사한다.
- camera/depth reprojection, point sampling, native alpha weight 0..0.5 및 spatial-frame
  history를 유지한다. AA 알고리즘의 새 개선안이 아니라 품질 원인 분리 대조 실험이다.
- 공통 실행 도구 의존성으로 `12f5d56`의 비대화형 shader 실패 종료만 가져온다.
  `run_clean_cmaa2.ps1` 및 이전 fixed60/still60-move120-still60 경로를 재사용한다.
