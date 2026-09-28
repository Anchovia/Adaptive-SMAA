# 첫 edge 선택 공간 처리 감사 및 표본 패턴 안정성

시작점 `f1cc620`, 브랜치 `experiment/first-edge-pattern-stability`.
기존 No-TAA는 지터 On의 spatial-frame 출력이며 일반 SMAA 1X 비교를 대신하지 못했다.
기존 점수는 그 진단 조건으로 보존하되 일반 SMAA 대비 개선 근거로 사용하지 않는다.

## 우선 확인

- 실제 `AAType::SMAA`로 Original SMAA 1X를 캡처한다. Temporal mode, projection jitter,
  T2X area subsample pattern이 모두 Off인지 검사한다. 실제 `AAType::None`도 분리한다.
- 기존 native, edge-selective, current-spatial On은 기존 전체 240프레임과 hash bridge한다.
- 진단 kind 65는 기존 spatial 3-pass를 실행한 뒤 resolve 입력만 **AA 전 색상 SRV**로
  바꾸어 current-only shader로 출력한다. 동일 지터의 AA 전/후 RGB를 비교해 기존
  current-spatial이 AA 전 영상을 잘못 읽고 있었는지 확인한다. 성능 결과로 사용하지 않는다.
- Pattern-Off current-spatial과 실제 SMAA 1X의 RGB를 비교한다. AA Off/1X의 차이도 기록한다.

## 안정성 대조 실험

- 첫 edge `any(RG>0)` 선택과 현재 재사용·native 결합 shader는 수정하지 않는다.
- 별도 진단 mode에서 기존 paired-pattern toggle을 Off로 설정한다. Projection jitter=0,
  공간 패스는 SMAA 1X area indices=0. Camera/depth reprojection, spatial-frame history 유지.
- 이는 **지터 없는 edge-selective temporal 대조군**이며 공식 SMAA T2X 또는 지터를
  유지한 기존 알고리즘의 단순 속도 최적화로 부르지 않는다. Supersampling 효과는 달라진다.
- 같은 Pattern-Off의 full-screen/current/raw-edge/repeat로 선택 계산과 재현성을 검사한다.
- 두 장면 각 240 frame, 60 still+120 moving+60 still, 60 Hz, 1920×1061, Ultra.
  기존 clean runner의 fresh process, timeout 및 종료 후 잔류 0 검사를 적용한다.
- 초기 20~59와 후기 200~239에서 RGB hash와 인접 변화량을 검사한다. 정지 개선을 이동
  품질 개선으로 일반화하지 않는다. 기존 참조와 hash bridge 후 같은 CGVQM-2 window로
  실제 O-1X/원본/기존 edge On/edge Off를 구분하고 비교 영상을 다시 만든다.
- 이번 단계는 공간 AA 적용·정지 안정성·품질 검증이며 이전 속도 수치를 새 Off 모드에 전용하지 않는다.
