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

## 2026-10-01: 품질 판단 전 원본 프레임 직접 검사 필수

사용자의 지시에 따라 AA 품질 평가는 시각적 결함 확인을 우선한다. 기존 문서의
CGVQM 주 지표 지정과 충돌하면 이 규칙을 따른다.

- 품질 비교·동등성·개선 여부를 보고하기 전에 같은 장면, 카메라 시점, frame index,
  해상도와 ROI의 원본 무손실 PNG를 직접 열어 확인한다. 이미지 생성이나 지표 계산만
  완료하고 육안 검사를 했다고 보고하지 않는다. 비교 방식과 jitter/subsample 조건을 표기한다.
- 전체 화면과 얇은 선·고대비 경계·고스팅 의심 영역의 확대 화면을 함께 검사한다.
  대표 이동 구간과 이동→정지 구간에서 각 방식의 연속 6프레임 이상을 나란히 확인하고,
  정지 안정 구간도 별도로 확인한다. 문제가 보이면 해당 구간의 전후 프레임까지 확장한다.
- 확대는 기본적으로 nearest 방식으로 원본 픽셀을 유지한다. 밝기·색상 보정이나
  차이 증폭 영상은 원본 비교와 구분하고, 좌표·frame index·배율·재생 속도를 기록한다.
  동일 구간 영상도 제공하되 실제로 본 정지 프레임과 재생 영상을 구분해 설명한다.
- 얇은 선의 소실·단절, 프레임별 출현/소멸, 반짝임, 계단 현상, 잔상과 흐림을 각각
  점검한다. 선 자체가 사라지거나 끊기는 결함을 '조금 거침'이나 '선명도 차이'로 축소하지
  않는다. 확인한 위치와 프레임을 제시하고 구조 보존 실패로 명확하게 기록한다.
- CGVQM은 보조 정량 지표다. 점수가 비슷하거나 높더라도 명백한 시각적 결함이 있으면
  품질 동등·개선 성공으로 판정하지 않는다. 지표가 해당 결함이나 체감 차이를 반영하지
  못하면 이번 비교의 판단 지표로 한계가 있음을 명시한다. 모든 용도에서 무의미하다고
  일반화하거나 기존 수치를 삭제하지 않는다.
- 코드·출력 동일성 검증 통과와 품질 검증 통과는 별개다. 정지 구간 hash가 같거나
  안정적이라는 사실로 이동 중 반짝임, 선 소실 또는 기준선 대비 품질 문제를 덮지 않는다.
- 비교 PNG/연속 프레임 sheet와 원본 경로·ROI·프레임 번호를 보존한다. 불일치하는
  정량 결과와 시각적 관찰을 함께 보고하고, 원인을 검증하기 전에는 추정을 확정하지 않는다.

## Thin-line loss trace scope

- This branch is validation/spatial-edge-thin-line-trace, directly based on 304f749.
- Follow Docs/Thin-Line-Trace/method.md. Diagnostic readback only; no AA math changes.
- Keep full-screen coverage controls, source kernels, jitter and dilation experiments separate.
