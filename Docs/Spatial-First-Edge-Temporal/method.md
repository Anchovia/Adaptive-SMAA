# ⑥ 원본 공간 SMAA + 첫 edge 선택 temporal

`experiment/spatial-first-edge-temporal`는 검증된 공통 기준 `e14f122`에서 직접 분기했다.
⑤ 전체 브랜치나 temporal-only 준비/검출 경로를 가져오지 않았다. `a774772`의 선택 HLSL,
resolve draw helper와 진단용 snapshot 코드를 필요한 범위에서 재사용했다. 선택 shader의
주석/entry 이름을 제외한 내용은 ⑤와 동일하며 감사 script가 이를 검사한다.

## 바뀌는 부분

원본 `SMAA::go`의 edge detection, blending-weight calculation, neighborhood blending은
그대로 실행한다. Temporal 단계에서 이미 생성된 RG8 edge를 정수 texel Load하여 RG 중
하나라도 양수인 픽셀에 원본 T2X-R 수식을 적용한다. 비선택은 **현재 프레임 공간 SMAA
출력**이다. 추가 검출/준비/복사/compact/dilation 패스는 없다.

History는 원본처럼 프레임별 spatial RGBA를 저장한다. Resolve feedback, history weight,
point sampler, camera/depth velocity, paired projection jitter/subsample index를 바꾸지 않는다.
비선택 spatial 출력에도 원본 T2X jitter가 있으므로 일반 unjittered SMAA 1X와 동일시하지 않는다.
⑤에서 확인한 두 위상 떨림이 공간 처리 후에도 남는지 직접 검사한다. Object motion은 범위 밖이다.

## 비교와 검증

- ④ `O-T2X-R` / ⑥ `ABL-SpatialFirstEdge-T2X-R`만 성능 matrix에 넣는다.
- 캡처에는 실제 `AA-Off`, 실제 `O-1X`, ⑥ reset 후 반복을 추가한다.
- 장면별 240프레임, 1920×1061, Ultra, fixed60Hz, 정지60/이동120/정지60, capture warm-up60.
- 세 원본 control은 독립 baseline 캡처와 전 프레임 RGB 대조한다.
- ④와 ⑥의 spatial current를 모든 프레임에서 비교한다. 선택 RGB=④ resolve,
  비선택 RGB=동일 프레임 spatial current인지 모든 픽셀에서 확인한다.
- 실제 첫 edge는 ⑤의 저장된 edge와 전 프레임 대조하고 ④/⑥ 반복의 10 probe와 대조한다.
- 10 probe의 spatial RGBA/scene input/velocity가 ④/⑥/반복 사이에서 같은지 검사한다.
  Raw input과 spatial RGB가 실제로 달라지는 픽셀도 기록하여 공간 보정 효과를 확인한다.
- 정지 시 고유 RGB frame 수, lag-2 일치, 연속 변화, 선택 전환의 기여를 기록한다.
  이것을 CGVQM 또는 이동 중 고스팅 품질 평가 완료로 표현하지 않는다.

## 성능 조건

별도 clean process의 smoke240×1 이후 30초 precondition, warm-up300,
4,800프레임×4회 순서를 교차한다. 각 240프레임 경로 회귀 시 history를 reset한다.
⑤ benchmark는 매 cycle reset이 없었으므로 서로 다른 실행의 전체 timing을 직접 비교하지 않는다.

이미지/마스크 readback을 끄고, 기존 WholeFrame와 SMAA GPU scope에 camera/spatial/resolve
timer를 추가한다. Steady-clock tick 간격의 평균·median·표준편차·p95/p99와
`1000/평균 간격` FPS, `1000/가장 느린 ceil(N*0.01) 간격 평균` 1% low도 기록한다.
숨김 창 engineering 조건이며 visible presentation FPS나 최종 8-case 결과는 아니다.

선택 resolve 차이는 edge 접근·분기·생략된 sampling/계산의 합이다. 순수 데이터 전송 비용이나
하드웨어 warp 효율을 직접 측정한 값으로 해석하지 않는다.

Microsoft [if/branch](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if)와
[Texture Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load)를
확인했으며 FXC ps_4_1의 R Off/On을 검사한다. 실제 runtime 측정은 camera R-On이다.
