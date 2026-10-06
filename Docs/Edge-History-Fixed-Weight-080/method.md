# ⑭: TSCMAA 문서 가중치 0.8의 단독 실험

브랜치 `experiment/edge-history-fixed-weight-080`, 검증된 ⑬ 커밋
`ebe68da448c79fb468dc55684d744a5eaf854788`에서 분기한다.
Semantic ID: `ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080`.

Original SMAA Ultra, 현재 OR camera-reprojected 직전 raw spatial edge,
Pattern Off, normalized Catmull–Rom 5-fetch RGB, point alpha와
resolved-output RGB/current-spatial velocity alpha feedback을 유지한다.
비선택 RGB는 현재 spatial 결과를 그대로 출력·저장한다.

변경은 selected history weight를 native adaptive 0..0.5에서 고정 0.8로
교체하는 것 하나다. `output = 0.2*current + 0.8*history`를 계산한다.
visible alpha도 해당 혼합을 따르지만 다음 history alpha는 current spatial alpha다.
History가 invalid인 첫 프레임/reset은 기존 current-spatial seed와 좌표 초기화를 유지한다.
추가 production draw/copy/texture는 없고 clipping, 후보 변경, object motion,
previous-depth disocclusion rejection은 추가하지 않는다. Default Off다.

근거는 [Intel TSCMAA 문서](https://www.intel.com/content/dam/develop/external/us/en/documents/tscmaa-codesample-v1.pdf)
4쪽의 후보 weight 0.8/noncandidate 0 및 resolved feedback이다.
확보 원본 소스의 활성 계수 약 0.789473712와 동일한 literal이라고 표현하지 않는다.
이 연구는 문서의 0.8 누적 강도 ablation이며 전체 TSCMAA 포팅이 아니다.

비교: ④ O-T2X-R / ⑬ native adaptive 0..0.5 / ⑭ fixed 0.8.
④는 Pattern On과 spatial-frame history이므로 ⑭와의 차이를 weight 하나의 효과로
해석하지 않는다. 원인 비교는 설정이 일치하는 ⑬↔⑭다.

검증: Release x64, 기존 24 shader entry bytecode 보존과 새 4 entry compile,
두 장면 seed/reset, 실제 same-draw mask/current/velocity 일치, selected weight 0.8,
nonselected weight0·RGB현재값, RGB feedback/alpha/연속 history chain.
품질: 각 장면 동일240프레임의 control RGB hash bridge, supersample spatial proxy,
이동·전환·정지 연속6프레임 직접 검사와 nearest 확대, 동일 원본 GIF/60fps 영상.
Raw 시간 차분은 motion과 blur를 포함하는 보조 지표이며 절대 shimmer/ghosting 지표가 아니다.
성능: 새 clean process Smoke 뒤 PNG/query/readback Off, 30초 precondition,
300 warm-up +4800 frame×6회 교차 순서; 전체 AA·spatial·camera·resolve를 구분한다.
사용자가 이번 실행에서 다른 GPU 작업이 없다고 확인했다.

⑮ 후보식, ⑯ clipping, ⑰ sampling/color mixing은 별도 후속 실험이다.
⑭ 결과에 섞지 않으며 세 실험은 공통 기준에서 독립 분기한다.
