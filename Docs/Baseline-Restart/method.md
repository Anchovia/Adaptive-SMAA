# 독립 원본 SMAA 기준선 재검증

## 브랜치 경계

사용자의 2026-09-28 지시에 따라 **연구 항목 하나당 브랜치 하나**를 할당한다.
후속 항목을 직전 실험 브랜치에서 연달아 분기해 실험 코드를 누적시키지 않는다.
검증된 공통 기준선에서 항목별로 분기하며, 항목 결합은 별도 통합 브랜치에서 검증한다.

- 원본 공간 SMAA: `baseline/original-smaa`, tag `baseline-original-smaa`, `ee0020d`.
- 원본 공간 SMAA + Standard T2X/R: `baseline/smaa-t2x`, `88893da`.
- **현재:** `validation/smaa-baseline-restart`, `88893da`에서 직접 분기.
  범위는 원본 실행/출력/정지 안정성과 성능의 독립 검증뿐이다.
- `experiment/temporal-first-edge-selective`: 기존 누적 실험과 원시 데이터를 보존한다.
  `214ab43`에서 일반 SMAA 비교·채택 결론에 정정 표시를 추가했다.
- `experiment/first-edge-pattern-stability`: 중단된 미검증 코드 `0084306`을 보존했다.
  빌드/측정 성공으로 취급하지 않는다. 현재 기준선 브랜치에는 포함하지 않는다.
- Edge 선택, 지터 처리 및 결합 실험은 **현재 검증이 끝난 뒤 각각 별도 브랜치**에서 다룬다.

## 이번 실행

`Projects/CMAA2/SMAA`의 알고리즘·shader·binding 코드를 `88893da`와 동일하게 유지한다.
유일한 header 추가는 UI와 같은 preset을 자동 선택하는 `GetSettings()` accessor다.
원본 기본값 High와 최근 실험 Ultra를 혼동하지 않고 동일 Ultra로 실행한다. 신규 알고리즘과 shader는 없다.
실행 자동화만 추가해 실제 AA enum을 선택한다. AA-Off(None), O-1X(SMAA), O-T2X,
O-T2X-R을 구분한다. O-1X와 O-T2X-R은 별도 mode 실행으로 반복 캡처한다.

- Bistro/Minecraft, Ultra, 같은 해상도, fixed 60 Hz.
- 60 warmup 후 frame0 history reset; 240 frame=60 still+120 moving+60 still.
- 기존 카메라 경로 t=2+clamp(frame-60,0,120)/60을 재사용한다.
- 모든 frame의 temporal/reprojection 설정과 PNG 저장 성공 여부를 기록한다.
- O-1X는 실제 spatial-only 코드 경로를 사용한다. 현재색 출력 진단으로 대체하지 않는다.
- AA-Off와 O-1X 차이, 정지 hash, O-1X/R 반복 hash, 과거 T2X-R와 pixel bridge를 검사한다.
- 원본 SMAA 코드가 같아도 전체 실행 출력이 같다는 주장은 독립 capture bridge 후에만 한다.
- 성능은 별도 clean process에서 30초 precondition, 300 warmup, 4800 frame×4회 교차 순서.
  기존 SMAA/WholeFrame scope를 사용한다. 숨김 실행은 engineering GPU timing이다.
- 원본 소스 유지가 우선이며, 출력 bridge가 실패하면 장면·preset·render 설정과 초기화 차이를
  조사한다. 실패를 가리고 기준선 shader를 바꾸지 않는다.

## 재사용할 기존 결론과 한계

- `experiment/temporal-contrast-jitter-ablation` (`0bc13ed`): 지터/area pattern Off에서
  당시 luma 선택 방식의 정지 두 위상 변동이 사라졌다. Temporal supersampling 조건은 달라진다.
- `experiment/temporal-pass-paired-dejitter` (`af2c35b`): 전체 화면 paired 보정은 정지
  안정화를 보였으나 선택적 출력에는 변동이 남았다. 보정만으로 해결됐다고 재해석하지 않는다.
- `experiment/temporal-first-edge-selective`: 실제 첫 edge를 썼지만 비선택 현재색에 지터가
  남았다. 선택/nonselection 수식 일치는 연구 요구 충족이나 품질 향상의 증거가 아니다.
- 과거 지터 On current-spatial CGVQM은 그 진단 조건의 기록이다. 일반 SMAA 1X의 점수로
  재사용하지 않는다. 기존 Adaptive SMAA 연구까지 폐기하는 것은 아니다.
