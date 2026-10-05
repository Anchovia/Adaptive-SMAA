# Edge-selective temporal 품질 실패 분석

## 결론

⑨의 직전 raw edge 재사용은 ⑥의 **선택 누락 일부를 실제로 보완한다**. 그러나 이미 선택된
선에서도 현재 선 색상과 직전 배경색이 섞여 약해지는 문제가 남는다. 정지 안정 구간에는
current와 history가 같아서 temporal 출력이 공간 SMAA 결과와 같아진다. 따라서 선택 mask
정확성 검증 통과만으로 반짝임·얇은 선 소실 해결이나 ④ 대비 품질 동등을 주장할 수 없다.

이번 작업은 `validation/edge-temporal-quality-failure`의 **원인 분석**이다. ⑨의 AA 코드를
수정하거나 새 성능·CGVQM 결과를 측정하지 않았다. 기존 GPU 캡처를 hash로 연결하여 사용했다.
조건·출처·재실행 절차는 [method.md](method.md), 자동 검증 결과는
[Bistro JSON](bistro-analysis.json) / [Minecraft JSON](minecraft-analysis.json)에 있다.

## 무엇을 검증했는가

두 장면 각각 240프레임에서 ④·⑥·⑨와 과거 대조군의 RGB hash를 연결했다. 장면별
2,160건의 hash 비교가 모두 통과했다. 이는 중복 대조를 포함한 검사 건수이며 서로 다른
2,160프레임을 새로 렌더링했다는 뜻이 아니다. 상세 진단은 각 장면 32프레임이다.

| 검사 | Bistro | Minecraft |
|---|---|---|
| ⑥·⑨의 raw/current/previous/velocity 입력 및 현재 edge 일치 | PASS | PASS |
| ⑨의 현재 edge 보존·재투영 직전 raw edge 합집합 | PASS | PASS |
| 실제 선택 픽셀 출력 = 무지터 전체 화면 대조군 | byte mismatch 0 | byte mismatch 0 |
| 실제 비선택 출력 = current spatial RGB | byte mismatch 0 | byte mismatch 0 |
| CPU point/weight mirror → 실제 ⑨ 출력 | safe 픽셀 최대 RGB 1 level | safe 픽셀 최대 RGB 1 level |

마지막 행만 point 경계 제외와 RGB 1 level 허용을 사용한다. GPU끼리의 실제 출력 비교는
허용 오차 없는 byte 비교다. CPU mirror와 원본 GPU weight 진단은 구분한다.

## ⑨가 해결한 부분: 선이 빠지는 프레임의 선택 누락

Minecraft 벽 경계의 frame 131 `(971,544)`에서 current spatial RGB는 `(163,162,150)`이다.
그 프레임의 raw 렌더 입력부터 같은 배경색이었다. ⑥은 해당 위치의 현재 edge가 없어서
temporal을 실행하지 않고 배경색을 그대로 출력한다.

⑨는 재투영한 직전 raw edge를 통해 그 위치를 선택한다. 실제 출력은 `(142,140,131)`로
바뀌었고 이전 선 색상 일부가 살아난다. Frame 134에서도 같은 유형의 보완을 확인했다.
단순히 선택 mask만 증가한 것이 아니라 실제 temporal 출력이 달라졌음을 검증한 결과다.

## 남은 부분: 선택된 픽셀에서도 선 색상이 약해짐

대표 픽셀의 실제 값은 아래와 같다. History RGB와 weight만 CPU 진단이며 point 경계에서
충분히 떨어진 위치다. 출력 RGB와 선택 mask는 실제 GPU 캡처다.

| Frame / 좌표 | 현재 공간 RGB | 직전 point RGB | ⑥ 선택 | ⑨ 선택 | ⑥ 출력 | ⑨ 출력 |
|---|---|---|---|---|---|---|
| 130 / (971,544) | 115,111,107 | 113,107,97 | On | On | 114,109,102 | 114,109,102 |
| 131 / (971,544) | 163,162,150 | 115,111,107 | Off | On | 163,162,150 | 142,140,131 |
| 132 / (972,544) | 114,108,101 | 161,161,149 | On | On | 140,138,128 | 140,138,128 |
| 134 / (972,544) | 163,163,150 | 113,109,105 | Off | On | 163,163,150 | 141,140,130 |
| 135 / (973,544) | 108,103,100 | 162,162,149 | On | On | 138,137,127 | 138,137,127 |

위 이동 픽셀의 history weight는 약 `0.499993`이다. Temporal이 꺼졌거나 weight가
거의 0인 상황이 아니다. Frame 132/135의 현재 어두운 선은 직전 밝은 배경색과 섞여
밝아진다. Frame 131/134에서 빠진 선을 살리는 것과, 다시 나타난 선을 약하게 만드는 것이
같은 0.5 부근 혼합에서 함께 발생한다.

**무지터 전체 화면 대조군도 위 픽셀에서 ⑨와 정확히 같은 색상**을 냈다. 이 위치의 문제는
선택 범위만 늘려서는 달라지지 않는다. 또 ⑨는 직전 *raw edge*를 유지하며, 선택 합집합을
재귀적으로 저장하거나 temporal 출력 색상을 다음 history로 누적하는 구현은 아니다.

전체 대표 값, raw 입력 및 ④/reference 값은 [representative-pixels.csv](representative-pixels.csv)에
보존했다. 예컨대 frame 131의 공간 reference RGB `(133,131,123)`에 대해 ④는
`(104,99,96)`이므로 **모든 픽셀에서 ④가 reference에 더 가깝다**고 주장하지 않는다.
픽셀 오차와 연속 프레임의 선 구조·밝기 안정성은 구분해서 판단한다.

## 여전히 temporal을 생략하는 영역

아래는 이동 frame 127~138의 전체 화면 평균이다. 해상도는 `1920×1061`, 총 2,037,120픽셀이다.

| 장면 | ⑥ 선택 평균 | ⑨ 선택 평균 | 추가 선택 평균 | 전체 Off가 바꾸는 비선택 픽셀: ⑥ | 같은 진단: ⑨ |
|---|---:|---:|---:|---:|---:|
| Bistro | 52,892 | 69,409 | 16,516 | 10,691 | 6,700 |
| Minecraft | 518,491 | 651,266 | 132,775 | 40,646 | 18,384 |

마지막 두 열은 `전체 화면 Off 출력과 current spatial의 최대 RGB 차이 >= 8`인 비선택
픽셀 수다. 선택 누락의 잠재 범위가 줄었다는 진단이지, 줄어든 수만큼 반짝임이 해결됐다는
품질 점수가 아니다. 여기에는 올바른 보정과 잘못된 혼합 모두 포함될 수 있다.

## 정지 안정 구간의 한계

두 장면의 frame 190~195에서 camera velocity는 전체 화면 0이고, current RGB와 재투영
history RGB가 다른 픽셀도 전체 화면 0이다. ⑥·⑨·무지터 전체 화면 Off는 모두 current
spatial RGB와 같다. ⑨의 추가 edge 선택 수 역시 0으로 돌아온다.

이 조건에서 혼합식은 `lerp(C,C,w)=C`다. 입력에 없는 선 신호를 mask나 weight만 바꿔
생성할 수 없다. ④는 paired projection jitter/subsample On이므로 다른 위치의 표본을
결합한다. 이 차이를 edge 선택 효과에 합산하거나, 지터 Off와 ④의 품질이 동등하다고
표현하면 안 된다. 이는 무지터 방식 전체가 무효라는 결론도 아니다. 현재의 표본·history
조건으로 개선할 수 있는 결함과 추가 표본이 필요한 결함을 구분한 것이다.

## 원본 프레임 직접 검사

원본 전체 PNG는 두 장면의 ④·⑥·⑨ frame 131을 직접 열어 확인했다. 아래 이동/전환/정지
sheet와 이동 앞뒤 sheet도 각각 직접 열었다. 생성 여부나 점수만으로 품질 판정하지 않았다.
열어 본 파일·hash·관찰은 [visual-inspection.json](visual-inspection.json)에 보존한다.

| 구간 | Bistro | Minecraft |
|---|---|---|
| 이동 130~135 | [연속 프레임](media/bistro-moving.png) | [연속 프레임](media/minecraft-moving.png) |
| 이동 앞 127~132 | [프레임](media/bistro-moving-before.png) | [프레임](media/minecraft-moving-before.png) |
| 이동 뒤 133~138 | [프레임](media/bistro-moving-after.png) | [프레임](media/minecraft-moving-after.png) |
| 이동→정지 178~183 | [연속 프레임](media/bistro-transition.png) | [연속 프레임](media/minecraft-transition.png) |
| 정지 190~195 | [연속 프레임](media/bistro-still.png) | [연속 프레임](media/minecraft-still.png) |
| raw→spatial→history→mask→weight→출력 | [원인 진단](media/bistro-causal-moving.png) | [원인 진단](media/minecraft-causal-moving.png) |
| 60~239 / 60 FPS / nearest 2배 | [재생 영상](media/bistro-moving-through-still.mp4) | [재생 영상](media/minecraft-moving-through-still.mp4) |

Minecraft 이동 구간에서는 ⑥의 세로 선이 frame 131/134 등에 중간에서 끊겨 보인다.
⑨가 그 구간을 일부 이어 주지만 frame마다 선의 밝기와 강도가 달라지는 문제가 남는다.
Frame 132/135 등은 선택이 켜진 상태에서도 선이 약해진다. 이는 **구조 보존 실패**이며
'약간의 선명도 차이'로 축소하지 않는다. 전환 이후 세로 선의 모양·강도도 ④와 같아지지 않는다.

Bistro 의자/바닥 구간에서는 ⑥·⑨의 얇은 구조와 고대비 픽셀 패턴이 연속 프레임에서
변하며, ⑨와 전체 화면 Off는 ④와 같은 결과가 아니다. ⑨가 전체 얇은 구조의 소실·반짝임을
해결했다고 판정할 근거가 부족하다. 이 ROI만으로 이동 물체 고스팅을 분리하지 못하므로
고스팅 개선 여부는 미판정이다. 카메라 이동 자체와 반짝임을 같은 현상으로 세지 않는다.

정지 sheet에서는 모든 방식이 이 ROI에서 안정적이지만, ⑥·⑨의 결과가 ④와 다른 공간
구조를 그대로 유지한다. 정지 hash 안정성을 이동 품질 성공으로 해석하지 않는다.
MP4는 decode 검증했으며 이 작업에서는 실제 재생을 보고 품질을 판정했다고 주장하지 않는다.
시각 관찰은 명시한 원본 PNG와 연속 sheet에 근거한다. CGVQM 재실행은 없다.

## 문헌과 다음의 최소 실험

[Yang·Liu·Salvi, A Survey of Temporal Antialiasing Techniques (2020)](https://leiy.cc/publications/TAA/TemporalAA.pdf)의
3.1/3.2/6.1/6.3절은 표본 다양화, fractional reprojection의 history 재표본화,
sampling 부족과 temporal 불안정성을 구분한다. Bilinear 재표본화는 snapping을 피하는
흔한 방법이지만 고주파 세부의 흐림이 생길 수 있다고 설명한다. 이는 기존 GPU 결과의
원인 후보를 해석하는 근거이며 우리 ⑨에서 품질 개선이 입증됐다는 증거가 아니다.

다음 최소 가설은 **⑨의 선택 mask·Pattern Off·history topology·혼합 weight를 고정하고,
history RGB만 point 대신 bilinear로 재표본화하는 것**이다. Fractional history 위치의
불연속한 point 선택이 남은 이동 중 밝기 변동을 얼마나 만드는지 독립적으로 확인한다.
정지 구간의 표본 부족을 해결하는 가설은 아니다.

통제 실험에서는 기존 point alpha에서 구한 weight를 유지해야 한다. RGBA 모두를 linear
sampling으로 바꾸면 alpha와 weight까지 바뀌어 색상 filtering 효과가 섞인다. 따라서 이
엄격한 RGB-only 대조는 point alpha fetch와 bilinear RGB fetch가 필요할 수 있으며, 단순히
'읽기 1회라 비용이 같다'고 약속할 수 없다. 실제 FXC 출력과 temporal/전체 AA 시간을 함께
검사하고, 선 약화·흐림 또는 비용 증가가 효과보다 크면 채택하지 않는다.

별도 `experiment/` 브랜치에서 검증된 ⑥ 기준선에 ⑨의 필요한 구현만 의존성으로 명시해
적용한다. ④·⑥·⑨ 원본은 보존한다. 추가 pass, dilation, 다른 weight, resolved-output
feedback이나 jitter 변경을 이 첫 가설에 함께 넣지 않는다. 이번 분석으로 확정된 것은
실패 원인의 구분이며, 다음 가설의 성공 가능성이나 개선 폭은 아직 미확정이다.
