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

## 2026-10-01: 직전 raw edge 유지 GPU 단독 실험

- `experiment/spatial-edge-persistence-depth`는 수정된 ⑥ `304f749`에서 직접 분기했다.
  구현은 `2d4d0cc`, 기준 문서는 `Docs/Edge-Persistence-GPU/results-ko.md`다.
- 현재 raw edge와 재투영한 직전 raw edge만 union한다. 누적 union feedback, 지터 변경,
  dilation, sampler/weight 변경은 없다. 기존 3차 패스의 SV_Depth 출력과 temporal의
  early depth rejection을 쓰며 추가 draw/dispatch를 만들지 않았다.
- 기존 ⑥·원본 ④의 960프레임 hash, current-only depth control 480프레임,
  새 구현 진단 On/Off 반복 480프레임이 일치했다. 부분 raw trace의 GPU/CPU 검증은
  texel 경계 인접 차이를 별도로 기록하므로 모든 픽셀 bit-exact라고 표현하지 않는다.
- 1920×1061, RTX 3060 Ti, 4,800프레임×6회에서 새 구현 전체 AA 시간은 원본 ④ 대비
  Bistro +5.28%, Minecraft +8.23%였다. 기존 ⑥ 대비는 +24.02%, +12.80%이며
  증가분 대부분이 공간 3차 패스 구간이다. 순수 데이터 전송 비용으로 해석하지 않는다.
- Minecraft 일부 프레임의 선 단절 복원은 확인했으나 다른 위치·프레임의 단절은 남았다.
  정지 후에는 기존 ⑥과 같다. 기본 경로로 채택하거나 전체 품질 개선 성공으로 부르지 않는다.
- 이후 다른 가설은 다시 검증된 기준선에서 분기한다. 이 실험 전체를 무조건 상속하지 않는다.

### 같은 구현의 추가 품질 평가 (2026-10-01)

- 렌더러를 바꾸지 않고 검증된 GPU PNG로 새 구현 CGVQM-2 4회 평가를 완료했다.
  기존 ⑥·원본 ④ 점수 8개는 해당 입력/공간 참조 stream hash가 정확히 같을 때만
  재사용했다. 새 GPU 점수와 과거 CPU 예상 영상의 점수를 혼동하지 않는다.
- 이동 f60~179 / 정지 전환 f160~219에서 새−기존 ⑥ CGVQM은 Bistro
  +0.064465/+0.029526, Minecraft +0.059334/+0.007072점이다. 모두 RGB FFV1
  round-trip mismatch 0이며 공식 model 2/patch scale 4/mean/CUDA 조건이다.
- 원본 full PNG 8장, 세 ROI의 6연속 sheet 9개와 Minecraft 추가 6프레임을 다시 열었다.
  f131/f134의 부분 복원과 별개로 f132/f135/f137에는 구조 보존 실패가 남는다.
  CGVQM 상승을 원본 T2X-R 수준의 반짝임 억제나 global ghosting 해결로 해석하지 않는다.
- 재현 도구는 `Tools/SMAA/evaluate_edge_persistence_cgvqm.py`, 결과·입력 hash는
  `Docs/Edge-Persistence-GPU/{bistro,minecraft}-cgvqm.json` 및 `results-ko.md`다.
