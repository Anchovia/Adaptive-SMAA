# ⑪ 선택적 resolved RGB feedback — 현재 검증 결과

⑪은 독립 브랜치 `experiment/edge-persistence-resolved-rgb-feedback`에 구현했다.
현재 단계의 결론은 **RGB 누적 구현의 정확성은 검증됐으나, 직접 프레임 비교에서
이동 중 얇은 선의 대비 감쇠·재출현이 남아 있어 품질 개선 gate는 통과하지 못했고
정식 성능 측정은 보류**라는 것이다. 사용자가 게임 실행 중이라고 알려
진행 중인 benchmark만 중단했다. 게임 부하가 있는 측정값은 표에 넣지 않았다.

## 구현 차이

| 구성 | Spatial SMAA | 선택 영역 | History RGB | Pattern | History weight |
|---|---|---|---|---|---|
| ④ `O-T2X-R` | Original Ultra | 전체 화면 | 직전 spatial frame | On | 원본 alpha 기반 0..0.5 |
| ⑩ `ABL-ET2X-R-PreviousRawEdge-BilinearRGB` | Original Ultra | 현재 edge + 재투영한 직전 raw edge | 직전 spatial frame, bilinear | Off | 원본 point alpha 기반 0..0.5 |
| ⑪ `ABL-ET2X-R-PreviousRawEdge-ResolvedRGB` | Original Ultra | ⑩와 동일 | 직전 temporal 출력 RGB, bilinear | Off | ⑩와 동일 |

⑪은 alpha에 현재 spatial velocity 정보를 보존한다. 따라서 RGB feedback 변경과
weight 변경을 섞지 않았다. Camera/depth reprojection만 사용하며 object motion을
지원한다고 표현하지 않는다. 지터, 3×3 확장, clipping, 5-fetch나 높은 고정 weight는
이 실험에 추가하지 않았다. 확보한 Intel TSCMAA 전체와 같은 구현이라고 하지 않는다.

기존 3차 spatial pass에서 현재 spatial 입력, 화면 seed, 다음 history seed를 MRT로
함께 저장하고, 기존 선택적 temporal draw에서 화면과 다음 history를 동시에 갱신한다.
비선택 픽셀은 현재 spatial 결과를 유지한다. 추가 draw나 전체 화면 CopyResource는
없지만 **별도 current-spatial texture 한 장과 추가 MRT 쓰기 비용은 있다**. 시간 측정이
끝나기 전에는 이 비용이 작거나 성능을 개선한다고 단정하지 않는다.

## 정확성 확인

- Release x64 build, 16 shader compile, 기존 ⑩ 생산 entry 10개의 DXBC byte 보존: PASS.
- 두 scene Test6의 first-frame seed와 frame3 reset: PASS.
- 두 scene × 240 frame에서 기존 ④·⑩ 대조군 총960 decoded RGB frame mismatch: 0.
- Scene별43 진단 frame에서 raw/current/velocity/edge/coverage/weight 입력 일치: PASS.
- ⑪ 저장 history RGB=실제 화면 출력, alpha=현재 spatial alpha: mismatch0.
- 연속 진단38곳/scene에서 이번 previous history=직전 stored history: mismatch0.
- 비선택 픽셀=current spatial 결과: mismatch0.

캡처 진단용 readback·coverage·weight·query는 정식 timing에서 끈다. 초기 Minecraft
capture의 원본④ mode-check 실패는 해당 실행 전체를 제외했다. 자동 실험 중 AA
단축키로 mode를 바꿀 수 있는 sample 입력 경로를 차단하고, 실패 설정값을 저장하도록
보완한 뒤 위 대조군 bridge를 재검증했다. 기존 실패 로그만으로 실제 입력 원인을
단정하지 않는다. [제외 기록](excluded-runs.json)을 보존한다.

## 직접 프레임 검사와 보조 지표

두 scene의 원본 전체 frame130과 얇은 선 확대를 직접 열었다. 이동130–135,
이동→정지178–183, 안정 정지190–195를 각각 연속6 frame으로 비교했다.
확대는 nearest2×이며 밝기·색상 보정을 하지 않았다. 검사한 경로·해시는
[직접 검사 기록](visual-inspection.json)에 있다. 실시간 영상을 직접 보았다고 주장하지
않으며, 아래 GIF/MP4는 사용자의 재생 확인을 위해 제공한다.

Bistro 의자 다리에서는 ⑩·⑪이 시각적으로 매우 가깝고, ④의 얇은 선 디테일을
회복했다고 판정할 수 없다. Minecraft 이음선에서도 ⑩·⑪의 가는 경계 대비가
프레임마다 바뀌며, ⑪에서 선 연속성이 확실히 개선됐다는 증거는 확인하지 못했다.
안정 정지 구간의 안정성은 이동 중 반짝임 제거를 의미하지 않는다. 현재로서는
**feedback 하나만으로 반짝임 해결 성공 또는 기본 채택으로 판정하지 않는다**.

### 사용자 요청에 따른 ④·⑪ 직접 비교 확대 (2026-10-06)

새 기법을 제안하기 전에 보존된 원본 PNG로 ④와 ⑪을 직접 대조했다. 새 GPU 실행,
렌더 캡처, CGVQM 또는 성능 측정은 하지 않았다. 두 장면에서 이동126–131·150–155,
이동→정지178–183, 안정 정지190–195의 연속6 frame씩을 확인했다. Bistro의 의자 다리와
창틀, Minecraft의 벽 이음선과 나뭇잎을 각각 nearest2×로 검사했다. 전체 화면130·180도
열었다. 문제가 보인 Minecraft 이음선은124–135로 전후를 확장해 nearest4×로 확인했다.
Bistro 의자 다리의 세부 ROI는126–131을 nearest3×로 확인했다. 밝기·색상 보정은 없다.

| 검사 대상 | 직접 확인한 현상 | 판정 범위 |
|---|---|---|
| Minecraft 벽 이음선124–135 | ⑪에서 세로 선의 구간별 대비가 크게 바뀐다.129의 아래쪽 선은④보다 약하다. 이후 좌표 추적에서 고정 하단 구간은130에 더 약해짐을 확인해, 이전의 '130에 아래쪽 선이 다시 뚜렷해진다'는 위치·변화 방향 해석을 정정했다. | 이동 중 선 연속성·대비 보존 문제는 유효하나, 서로 다른 선 구간을 같은 구간의 재출현으로 해석하지 않는다. 아래 단계별 추적을 따른다. |
| 같은 이음선의④ | ④도127·132 등에서 선 일부가 약해진다.150–155에는⑪이 선을 더 유지하는 프레임도 있다. | 모든 프레임에서⑪이④보다 나쁘거나④가 완전히 안정적이라고 일반화하지 않는다. |
| Bistro 의자 다리126–131·150–155 | ⑪에서도 가는 다리의 픽셀 계단과 대비 변화가 남는다.④의 회색 부분 표본과 다른 강한 경계가 나타난다. | 안정화 성공은 확인되지 않았다. 이 ROI에서 의자 다리 전체가 사라졌다고 판정한 것은 아니다. |
| 창틀·나뭇잎 |⑪의 미세 경계·텍스처 변동이 남으며, 구조 유지의 일관된 우위를 확인하지 못했다. | 잔상 길이·고스팅 감소의 확정 근거로 사용하지 않는다. |
| 안정 정지190–195 | 두 장면 모두 각 case의 전체 RGB가 연속5쌍에서 완전히 동일하다. | 검사한 안정 정지 구간의 떨림은 없으며, 이동 중 결함과 구분한다. |

따라서⑪은 **이동 중 얇은 구조 유지와 반짝임 해결을 위한 품질 gate 미통과**로 기록한다.
GPU feedback 저장과 비선택 출력 검증의 PASS는 그대로 유효하지만, 품질 PASS를 뜻하지
않는다.④는 Pattern On,⑪은 Off이고 선택 영역·sampling·feedback도 다르므로, 이 관찰만으로
선택 마스크·누적 weight·지터 중 어느 요소가 원인인지 확정하지 않는다. 후속 판단은 실패
위치의 current spatial·실제 선택 여부·history·혼합 후 출력을 연결해서 조사한 뒤 한다.

[직접 검사 기록](frame-review-4-vs-11.json)에 원본·확대 좌표·frame·hash를 보존했다.
[④·⑪ 비교 PNG와 동일 구간 GIF](C:/Users/USER/Desktop/research/Deliverables/SMAA_4_11_FrameReview_20261006/comparison.html)
는 사용자 검토용이다. GIF는76 frame(120–195)을25fps로 재생하고 팔레트 손실이 있으므로
판정은 무손실 PNG를 기준으로 했다. GIF의 실제 재생을 직접 보았다고 주장하지 않는다.

### 실패 위치의 단계별 추적 (2026-10-06)

저장된 두 장면의 moving126–138, transition178–183, still190–195를 사용해
scene별25개, 총50개 ROI frame의 raw → current spatial → 실제 GPU 선택·weight →
재투영 history → 실제 출력·다음 history를 연결했다. 새 렌더나 셰이더 변경 없이 CPU로
분석했다. History 확대 패널만 저장된 입력으로 계산한 **이상적 CPU bilinear 표본**이다.
나머지는 실제 GPU 캡처다. CPU 표본은 GPU filtering과 byte-exact라고 표현하지 않는다.
안전한 point 주소의 weight 최대 오차는2.98e-8, ideal RGB 최대 오차는2 level이었다.
기존 bilinear gate의 보수적 진단 허용 범위 밖 channel은0이었다.

- 실제 선택은 검증 가능한48 frame에서 `current raw edge OR reprojected previous raw edge`와
  일치했다. 경계 근처 point 주소는 제외했고,126은125의 raw 진단이 없어 union 검사를 하지 않았다.
- 다음 history RGB=화면 출력, alpha=current spatial alpha, 비선택=current spatial의
  ROI mismatch는 모두0이었다. 확인 가능한48 frame의 previous/직전 next 연결도 일치했다.
- 두 ROI의 검사한 선택 픽셀에서 weight0인 사례는0이었다. 따라서 확인된 실패를
  'temporal이 실행되지 않음' 또는 '혼합 weight가0임'으로 설명할 수 없다.

Minecraft 하단 strip의 `y=578..611`, `x=966..983`에서 current spatial의 평균
display luma가 가장 낮은 열을 진단 대상으로 골랐다. 매 frame의 열·양쪽 배경 좌표를
기록했으며 이는 **화면 고정 strip 대용값이고 객체 추적·temporal ground truth가 아니다**.
대비는 배경 평균 luma에서 해당 열의 평균 luma를 뺀 값이다.

| frame | 검사 열x | 실제 선택 | history weight | spatial 대비 | CPU history 대비 | 최종 대비 |
|---|---:|---:|---:|---:|---:|---:|
|128|971|34/34|0.499993|4.991|20.366|12.258|
|129|972|34/34|0.499993|47.257|11.448|27.098|
|130|972|34/34|0.499993|5.008|16.239|10.245|
|131|973|34/34|0.499993|48.180|9.297|26.175|
|132|973|34/34|0.499993|49.680|20.189|34.110|
|133|973|34/34|0.499993|4.880|19.913|12.032|

129에서는 **선이 spatial에 존재하고 전체34 pixel이 선택됐지만, 약한 history를
약50% 섞어 최종 대비가42.66% 줄었다**.130은 raw 대비8.758, spatial 대비5.008로,
이미 입력부터 약했다. History는 오히려 최종 대비를10.245로 높였으나 강한 선을
지속적으로 복원하지는 못했다. 즉 선택 누락 하나의 문제가 아니라, 입력 표본의
프레임별 변화와 history 재표본화·혼합이 함께 관여한다.

정확한129 pixel `(972,590)`의 raw RGB는(93,87,83), spatial은(122,118,111),
CPU sampled history는(152,151,140), 실제 출력은(138,136,127)이었다. 네 bilinear
source pixel은 모두 직전 frame에 선택돼 있었고 실제 저장 resolved RGB를 읽었다.
이 위치의 손실을 직전 비선택 영역의 history seed 탓으로 단정할 수 없다.

현재 증거는 **정상 실행되는 결합의 얇은 구조 보존 한계를 확인한 것**이다.
전체 장면에 구현 오류가 없다는 증명이나④·⑪ 차이의 단일 원인 규명은 아니다.
④는 Pattern On이고 sampling·feedback도 다르다. 높은 고정 weight, jitter 또는
clipping이 자동으로 해결한다는 결론은 내리지 않았다.

[좌표별 추적·검증 수치](failure-trace.json),
[단계별 무손실 비교](C:/Users/USER/Desktop/research/Deliverables/SMAA_11_FailureTrace_20261006/comparison.html)
에 원본 경로·SHA-256, 실제 weight와 네 history texel을 기록했다. Linear filtering의
half-texel 주소·정밀도는 [D3D11 규격7.18.8·7.18.16](https://microsoft.github.io/DirectX-Specs/d3d/archive/D3D11_3_FunctionalSpec.htm)을
참고하며, 허용 범위 검증을 exact GPU sample 재현으로 표현하지 않는다.

아래는 supersample **spatial proxy** 대비 ROI RGB MAE다. 낮을수록 해당 참조와 가까우나
절대 temporal ground truth 또는 반짝임 점수가 아니다. Bistro ROI=(1230,582,1358,670),
Minecraft ROI=(956,524,1020,620). Moving60–179, transition172–189, still190–239.

| Scene/window | ④ RGB MAE | ⑩ RGB MAE | ⑪ RGB MAE |
|---|---:|---:|---:|
| bistro moving | 4.3815 | 5.4926 | 5.3126 |
| bistro transition | 4.0526 | 5.5773 | 5.4382 |
| bistro still | 3.8968 | 5.8828 | 5.8197 |
| minecraft moving | 1.6265 | 1.2654 | 1.2535 |
| minecraft transition | 1.7016 | 1.7712 | 1.7589 |
| minecraft still | 1.2391 | 1.9865 | 1.9773 |

⑪의 MAE가 ⑩보다 조금 낮아도 이것만으로 체감 품질 우위를 확정하지 않는다.
보조 CGVQM은 아래에 별도 기록한다. 무손실 프레임의 선 손실 관찰을 점수로 뒤집지 않는다.

## 2026-10-06 정식 paired 성능

취침 전 사용자가 게임 중 성능 측정 보류를 해제했다. 이전 중단 실행은 제외하고,
동일 실행파일의 새 eligible Smoke 이후 장면마다 독립 clean process를 실행했다.
RTX 3060 Ti, DX11 Release x64, 1920×1061, Ultra, hidden, VSync Off.
30초 conditioning, mode마다300 warm-up, 4,800 frame×6회이며 순서를 교차했다.
PNG·진단 query·readback은 Off다. 전체 AA에는 spatial/선택 준비, camera velocity와
temporal resolve를 포함한다. 변화율은 같은 run의④ 대비다.

| 장면 | 구성 | 전체 AA ms | ④ 대비 | temporal ms | temporal ④ 대비 |
|---|---|---:|---:|---:|---:|
| bistro | 4 | 0.158775 | +0.00% | 0.033398 | +0.00% |
| bistro | 10 | 0.136042 | -14.32% | 0.007585 | -77.29% |
| bistro | 11 | 0.147500 | -7.10% | 0.010069 | -69.85% |
| minecraft | 4 | 0.228102 | +0.00% | 0.034966 | +0.00% |
| minecraft | 10 | 0.228390 | +0.13% | 0.023925 | -31.58% |
| minecraft | 11 | 0.245825 | +7.77% | 0.032900 | -5.91% |

⑪는④보다 Bistro에서7.10% 짧지만 Minecraft에서는7.77% 길다. ⑩보다 전체 AA가
각각8.42%/7.63% 늘었다. 따라서 모든 장면의 성능 개선으로 채택하지 않는다.
한 장면당 한 프로세스의6개 run이며6개 독립 세션이라고 표현하지 않는다.
각 run·표본 수·paired 신뢰구간은 장면별 `benchmark.json`/`performance-runs.csv`에 있다.

## 보조 CGVQM-2

Supersample spatial proxy 기준의 공식 모델 점수다. Moving60–179,
transition160–219이며 위 ROI transition172–189와 범위가 다르다.
변경하지 않은 공식60-frame 호출을 동일30-frame patch 경계에서 평균했다.
④의 기존 full-window pooling bridge를 확인했으며⑪ 자체의 full-window 모델
재실행은 하지 않았다. ④·⑩의 점수는 현재 decoded RGB/reference hash가 일치하는
보존 결과를 재사용했다. 점수를 고스팅·선 연속성의 단독 판정으로 사용하지 않는다.

| 장면/구간 | ④ | ⑩ | ⑪ |
|---|---:|---:|---:|
| bistro/moving | 96.191235 | 96.356331 | 96.376579 |
| bistro/transition | 96.719254 | 95.980339 | 96.006439 |

## 결론과 후속⑫

⑪의 GPU lifecycle과 저장은 검증됐지만 이동 중 얇은 구조·반짝임의 품질 gate는
미통과다. 논문·공개 구현을 참고한 새 방법은⑫ 독립 브랜치에 분리한다.
⑪의720-frame presentation은⑫ 비교 캡처에⑪ control을 포함해 실제 렌더한다.
240-frame 반복으로 대체하지 않는다. 재현 정보는 `case.json`과 `resume.md`에 있다.
