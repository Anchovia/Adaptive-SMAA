# ⑬: 선택된 edge의 history RGB 재구성 필터 단독 비교

브랜치: `experiment/edge-history-catmull-rom-reconstruction`.
검증된 공통 기준선 `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459`에서 새 작업 폴더로 분기했다.
⑨의 edge 유지 `3992640`, ⑩ RGB/point-alpha `96c495a`, ⑪ resolved-RGB feedback
`b793b74`, 자동 입력 격리 `573ecfa`, 검증 도구 `cd8844d`를 명시적으로 가져왔다.
⑪ 최종 문서는 `2e7136f`의 해당 문서 디렉터리에서 복원했다.
⑫의 코드·clipping·높은 누적 가중치는 가져오지 않았다.

독립 변수는 **history RGB의 bilinear 1-fetch → normalized Catmull–Rom 5-fetch approximation**이다.
Original SMAA Ultra, 현재 OR 재투영한 직전 raw edge, camera/depth reprojection,
paired sample pattern Off, point history alpha, native adaptive weight 0..0.5,
resolved-output RGB feedback/current spatial velocity alpha 및 비선택 current spatial을 유지한다.
Visible alpha도 기존 혼합을 유지하고, 다음 history alpha는 현재 spatial alpha를 보존한다.

근거:
- [MJP의 Catmull–Rom 구현 및 작성자의 5-tap 설명](https://gist.github.com/TheRealMJP/c83b8c0f46b63f3a88a5986f4fa982b1):
  4×4 Catmull–Rom을 bilinear 9-fetch로 재구성하고 5-fetch에서는 네 모서리를 생략한다.
- [Intel TSCMAA 문서](https://www.intel.com/content/dam/develop/external/us/en/documents/tscmaa-codesample-v1.pdf), 4쪽:
  sharpness-preserving 5-tap history sampling. 획득 소스와 동일한 공식 포팅이라고 표현하지 않는다.

5-fetch에서 남은 가중치 합으로 정규화하여 단색을 보존한다. 정규화와 SMAA linear-sRGB
view 연결은 명시적 adaptation이다. 16-fetch 정확해와 근사 오차를 기록하고,
하드웨어 bilinear 정밀도와 이상적 CPU 부동소수점을 동일시하지 않는다.
Negative lobe는 선명도를 보존할 가능성과 ringing/overshoot 위험을 함께 가진다.
Neighborhood clipping, sharpen pass, 후보 dilation, 새로운 지터, object motion,
previous-depth rejection은 추가하지 않는다. 주소는 기존 clamp sampler를 유지한다.

추가 생산 draw/copy/texture는 0개이며 ⑪의 spatial MRT 및 feedback 쓰기는 남는다.
필터의 history RGB fetch는 1→5로 증가한다. ⑩ 수준의 비용을 보장하지 않는다.

검증 계획: 기존 entry DXBC 보존, actual shared filter GPU/CPU probe, constant/center/
경계/대칭과 16-tap approximation error, 두 장면 Test/reset, 실제 selected mask·입력·weight
동일성, RGB feedback/current alpha/nonselected/chain. 동일 포즈의 ④·⑩·⑪ RGB hash bridge.
별도 fresh process에서 Smoke 후 300 warm-up+4800 frame×6 교차 반복 benchmark.
품질은 240-frame spatial reference proxy, 선 대비와 보조 CGVQM 및 moving/transition/still
각 6개 연속 원본 PNG를 직접 검사한다. 720-frame GIF/MP4는 실제 새 캡처이며 품질 reference가 아니다.
