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

## 2026-10-01: 직전 raw edge 유지 비용 감사

- `validation/edge-persistence-cost-audit`는 수정된 ⑥ `304f749`에서 직접 분기하고,
  감사 대상인 ⑦ 렌더러 `2d4d0cc`만 명시적 의존성으로 가져왔다. 기존 ⑦ 브랜치와
  결과는 보존한다. 새 렌더러/진단 커밋은 `9b9953e`다.
- 기준 문서는 `Docs/Edge-Persistence-Cost-Audit/results-ko.md`와 `method.md`다.
  A=기존 ⑥, B=기존 ⑦ depth 전달, E=동일 union의 first-pass stencil 전달, O=④다.
  E를 ⑥으로 부르거나 기존 ⑦ 수치를 E 측정값으로 덮어쓰지 않는다.
- 기존 ⑦은 raw edge를 CopyResource하지 않고 두 RG8 target을 swap한다. 큰 추가
  비용은 shader depth export 경로에서 재현됐다. 고정 1만 SV_Depth로 출력하는
  대조군도 AA 시간이 Bistro +0.028941 ms, Minecraft +0.022050 ms 증가했다.
  이전 edge 보관/읽기의 불가피한 비용 또는 단순 Early-Z culling 상실로 설명하지 않는다.
- E는 native edge 식에서 early discard를 zero return으로 바꾼 별도 함수로 current RG를
  보존하고, current edge가 없을 때만 재투영한 previous raw edge를 검사해 stencil에 union을
  표시한다. Previous-only 픽셀의 raw RG는 0이다. 기존 3차 pass와 native temporal resolve를
  사용하며 추가 draw/dispatch는 없다. 2차 spatial 실행 영역은 넓어지므로 출력 보존을 검증한다.
- 두 장면 각 240프레임에서 E/B 최종 RGB가 완전히 같았다. 86개 trace의 raw RG,
  current spatial DDS, 실제 temporal coverage도 같다. PS invocation 및 passing samples는
  두 구현 모두 coverage pixel 수와 일치했다. Native shader 14 DXBC도 기준선과 같다.
- 1920×1061, RTX 3060 Ti, hidden, 4,800프레임×3회에서 E는 B보다 AA 시간이
  Bistro -13.94%, Minecraft -4.39%였다. 같은 실행의 ④ 대비는 -9.53%, +3.33%다.
  따라서 양 장면 모두 ④보다 빨라졌다고 주장하지 않는다. 기존 ⑥ 대비 E는 여전히 느리다.
- 이번 결과는 동일 출력의 비용 개선이다. 기존 ⑦의 얇은 선 단절/반짝임 문제 해결,
  새로운 품질 개선, 모든 GPU/장면 검증 또는 최적화 한계 도달을 주장하지 않는다.
- 후속 사용자의 비교 표기 지시에 따라 시각 자료는 ④=원본, ⑥=현재 edge,
  ⑦=B(개선 전 depth), ⑧=E(개선 후 stencil)로 표시한다. 기존 감사 문서의
  '개선 ⑦'은 새 표기의 ⑧이다. 별도의 새 품질 기법이나 재측정으로 해석하지 않는다.
