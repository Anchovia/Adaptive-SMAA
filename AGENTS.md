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

## 2026-10-05: ⑨ 선행 조회와 현재 edge spatial 처리 결합

- `experiment/edge-persistence-eager-spatial-mask`는 수정된 ⑥ `304f749`에서 분기하고
  명시한 `e54f0db` 렌더러 의존성만 가져온 독립 결합 실험이다.
- F=기존 ⑨, H=⑨+현재 edge depth 표시/union weights, J=같은 표시/current-only weights,
  O=원본 ④다. H/J의 temporal coverage는 F와 같은 current+previous raw edge 합집합이다.
- 내부 mode 12/13은 H/J 설정이다. 사용자 비교 case 번호를 새로 확정하지 않는다.
- 표시 비용 H−F, 2차 실행 제한 J−H, 전체 개선 J−F를 구분한다. J의 전체 AA 시간이
  반복 측정에서 감소해야 채택한다. 먼저 raw RG/current spatial/velocity/coverage/final RGB
  및 실제 2차 passing samples를 검증하고 원본 연속 프레임을 직접 확인한다.
- 기존 장치에서 미지원했던 shader stencil reference를 사용하지 않는다. 기존 SMAA 전용
  DSV의 depth 표시를 재사용하며 scene depth 및 temporal 규칙은 변경하지 않는다.
- 방법과 검증·실패 기록은 `Docs/Edge-Persistence-Eager-Spatial-Mask/`에 보존한다.

### 결합 실험 결과

- Release 빌드, 보존 shader DXBC, Bistro/Minecraft 240-frame RGB bridge와 조건별
  43-frame raw/current/velocity/coverage 및 실제 weight/temporal sample query가 PASS다.
  H/J는 F와 RGB mismatch 0이며 원본 전체 PNG와 이동/전환/정지 연속 프레임을 직접 확인했다.
- Clean 4,800-frame×3회에서 J−F 전체 AA는 Bistro +0.770%, Minecraft +0.982%다.
  두 장면의 세 반복 모두 증가했다. 표시 비용을 지불한 H 대비 J는 줄었지만 기본 ⑨보다
  빨라지지 않았으므로 채택하지 않는다. F/⑨를 유지하며 H/J는 negative-result 설정이다.
- 대표 f131의 2차 passing samples는 Bistro 69,519→52,848, Minecraft
  652,244→520,091로 감소하고 temporal 합집합은 유지됐다. Passing sample 감소를
  같은 비율의 shader invocation/시간 감소 또는 품질 개선으로 해석하지 않는다.
- 상세는 `Docs/Edge-Persistence-Eager-Spatial-Mask/results-ko.md`다. 기존 얇은 선
  소실/단절 문제는 그대로다. 이 조합의 실패를 모든 최적화가 불가능하다는 결론으로
  확대하지 않는다. 본 측정 11개 명령은 같은 binary/shader hash의 독립 프로세스에서
  정상 완료했으며 실패/재시도는 없다.
