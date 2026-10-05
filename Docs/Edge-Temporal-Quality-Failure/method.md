# ④·⑥·⑨의 품질 실패 원인 분리

검증 브랜치: `validation/edge-temporal-quality-failure`

직접 출발 기준선: `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459`

분류: 기존 무손실 GPU 캡처의 재검증·분석. 새 AA 구현·GPU 실행·성능 측정이 아니다.

## 비교 대상

| 대상 | 공간 처리 | 선택 | 표본 패턴 | history |
|---|---|---|---|---|
| ④ `O-T2X-R` | 원본 SMAA | 전체 화면 | 원본 paired projection jitter/subsample On | 직전 공간 프레임 |
| ⑥ | 원본 SMAA | 현재 1차 패스의 exact edge | paired pattern Off | 직전 공간 프레임 |
| ⑨ `F-EagerPreviousFetch` | 원본 SMAA | 현재 edge와 재투영한 직전 raw edge의 합집합 | paired pattern Off | 직전 공간 프레임 |
| 전체 화면 Off 대조군 | 원본 SMAA | 전체 화면 | paired pattern Off | 직전 공간 프레임 |

모두 camera/depth reprojection을 사용한다. Object-motion vector 지원 결과가 아니다.
⑥·⑨·전체 화면 Off의 temporal 색상 계산은 point history sampling, velocity-alpha로
구한 `0..0.5` history weight, 선형 색상 혼합이다. Clipping·후보 확장·Adaptive 공간
탐색은 이번 비교에 추가하지 않는다. 전체 화면 Off는 기존 coverage-only 대조군을 재사용한다.
최종 Adaptive 8-case 행렬과 이 번호별 진단 구성을 혼동하지 않는다.

이 브랜치의 렌더러는 출발 기준선 그대로다. ⑨의 구현 커밋을 가져오지 않고 기록된
실제 ⑨ GPU 출력·진단 입력을 분석한다. renderer dependency 없이 다른 연구 구현이
섞이지 않는 검증 브랜치로 유지한다. 재현 실행에는 각 출처 브랜치의 캡처를 사용해야 한다.

## 자료와 검증

`source-provenance.json`에 기존 기록의 전체 commit, 저장소 경로와 snapshot SHA-256을
보존한다. 각 snapshot은 실행 ID, EXE/shader hash, 원본 디스크 경로를 포함한다.
새 분석은 다음을 자동 검사하며 하나라도 실패하면 결과를 생성하지 않는다.

1. Snapshot hash 일치.
2. 장면별 240프레임 전체의 RGB SHA-256: 수정 기준선의 ④·⑥, 과거 thin trace,
   coverage control과 최신 ⑨ 캡처의 연결. ⑨는 기존 spatial-cost 실행과도 연결한다.
3. 32 trace 프레임의 ⑥·⑨ raw/current/previous/velocity 입력 및 current edge 일치.
   기존 thin trace의 DDS 파일 hash도 다시 확인한다.
4. ⑨의 실제 GPU 선택 mask는 현재 edge를 보존하며, point 재투영 직전 raw edge와
   합집합인지 검사한다. 화면 밖 직전 edge는 0이다. History 색상 샘플의 clamp 경계
   처리와 이 edge 경계 규칙은 구분한다.
5. 실제 GPU-to-GPU 비교: ⑥·⑨의 선택 픽셀 출력은 무지터 전체 화면 대조군과
   byte-exact 일치해야 한다. 비선택 출력은 current spatial RGB와 byte-exact 일치해야 한다.
6. 검증된 CPU mirror로 point history 좌표와 history weight를 재구성한다.
   Point 셀 경계의 0.01 pixel 이내를 제외하고 실제 ⑨ 출력과 최대 RGB 1 level 이내인지 검사한다.
   GPU끼리의 byte 비교에는 이 경계 제외나 1 level 허용을 적용하지 않는다.

CPU mirror는 이전 검증 도구의 함수를 변경 없이 분리했다. ⑨의 weight를 새 GPU MRT로
측정한 것이 아니다. 대표 픽셀과 sheet의 history/weight에는 **CPU 진단**임을 표기한다.
전체 화면 Off가 비선택 픽셀을 바꾸는 수는 대응 대조군 차이를 나타낼 뿐, 올바른 픽셀 수나
고스팅·깜빡임의 절대 정답으로 해석하지 않는다. `RGB 최대 차이 >= 8`은 진단용 임계값이다.

## 프레임 검사

- Bistro ROI: `(1230,582)-(1358,670)`, 의자/얇은 구조.
- Minecraft ROI: `(956,524)-(1020,620)`, 벽 경계/얇은 선.
- 이동: 130~135 및 앞뒤 127~132/133~138.
- 이동→정지: 178~183. 정지 안정 구간: 190~195.
- 원본 무손실 전체 PNG와 위 6프레임 연속 sheet를 직접 열어 확인한다.
- 확대는 nearest 2배, 원본 RGB를 유지한다. Weight와 mask는 별도 진단 영상이다.
- 동일 60~239 구간을 fixed 60 FPS MP4로 제공한다. 영상은 H264 시각화 보조 자료로서
  무손실 PNG의 수치 검증을 대체하지 않는다. 프레임 수·PTS·평균 frame rate를 decode해 검사한다.
- SS reference는 동일 pose의 supersample **공간 reference proxy**다. Temporal ground truth가
  아니다. 단일 픽셀 reference 오차로 전체 구조 보존·깜빡임의 우열을 확정하지 않는다.

## 분석 재실행

Python 환경에 NumPy, Pillow, PyAV가 필요하다. 원본 캡처는 manifest의 디스크 경로에 있어야 한다.

```powershell
& 'C:/Users/USER/Desktop/research/.research-tools/quality-venv/Scripts/python.exe' `
  'Tools/SMAA/analyze_edge_temporal_quality_failure.py' --scene both --video
```

추가 게임 렌더링, CGVQM 모델 실행 또는 benchmark는 수행하지 않는다. 기존 실행 조건의
품질 원인을 분리하는 단계이며, 결과만으로 새 개선 구현의 성공을 주장하지 않는다.
