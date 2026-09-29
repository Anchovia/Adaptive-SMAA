# ⑤ First-edge temporal-only: sample-pattern Off ablation

## 독립 브랜치

- `experiment/first-edge-temporal-only-pattern-off`를 공통 기준선 `c51ca28`에서 생성했다.
- 최소 의존성만 명시적으로 가져왔다: `7c2feeb` → `d3ede22` (raw temporal-only 준비), `a774772` → `b28790e` (원본 첫 edge 검출과 선택 resolve).
- ⑥의 spatial 구현을 상속하지 않았다. `experiment/spatial-first-edge-pattern-off`의 `556f226`에서 검사 harness/분석 코드만 파일 단위로 재사용하고 ⑤의 의미에 맞췄다.

## 구현

원본 SMAA 첫 edge detection으로 RG8 edge를 만든다. 공간 혼합 보정은 수행하지 않고, raw 현재 RGB와 native velocity-alpha를 기존 prepare 단계에 저장한다. 이 기존 실행 구조에서 projection jitter만 끄는 조건을 추가했다. Raw 경로에는 원래 area-texture pass가 없으므로 바꿀 spatial subsample index도 없다. 원본 spatial 경로의 fallback은 ⑥과 마찬가지로 projection과 area pattern을 함께 전환한다.

선택식 `any(edge.rg > 0)`, native temporal 식, camera/depth reprojection, point history와 raw-current-frame history를 보존한다. 새 패스나 dilation을 넣지 않는다. 기본 pattern은 On이다. 원본 공간 SMAA가 적용된 ⑥과 달리, ⑤가 spatial AA를 하지 않는 것은 비교 행렬의 의도된 조건이다.

## 비교 및 검증

On full/On selective/Off full/Off selective의 네 temporal-only 조건을 비교한다. Full에도 동일한 edge detection을 실행하므로 selection의 비용을 분리할 수 있다. 이 full의 AA 비용을 원본 spatial SMAA T2X-R 비용이라고 부르지 않는다. Native T2X-R, 실제 SMAA 1X와 AA-Off는 별도 출력 control로 캡처한다.

각 장면 240프레임, fixed 60 Hz, still60/move120/still60이며 mode와 cycle 시작 시 history를 초기화한다. 다음을 검사한다.

- On 두 조건과 원본 control 세 조건의 기존 240프레임 hash 연결.
- Off selective 독립 재실행 hash 일치.
- current RGB = 실제 AA-Off RGB; full/selected current 및 velocity-alpha 입력 동일.
- selected output = Off full output; nonselected output = current RGB.
- ⑤와 독립 ⑥ Off 구현의 모든 첫 edge RG8 파일 일치.
- 초반 20~59 및 후반 200~239 정지 구간의 고유 RGB 프레임 수, 인접 차이, mask 전환.

품질은 동일한 supersample spatial reference와 공식 CGVQM-2를 사용한다. ⑥에서 검증한 최대 60프레임 단위 실행을 재사용해 원본의 30프레임 inference 경계를 유지한다. 기존 native 120프레임 점수와의 bridge 기록은 `reused-native-bridge-*.json`에 출처·commit·hash와 함께 보존한다. 전체 test/reference pixel hash가 같은 경우에만 사용한다. 평가 구간은 이동 60~179, 전환 160~219다. 이를 절대 고스팅 ground truth로 표현하지 않는다.

성능은 캡처와 별도 clean process로 측정한다. 30초 사전 실행, 300 warmup, 4,800프레임×4회 정·역 교차 순서이며, WholeFrame/SMAA/camera/edge detection/prepare/resolve GPU 시간과 wall interval을 기록한다. Raw 캡처는 D 드라이브, 실행 receipt와 요약은 이 브랜치에 보존한다.
