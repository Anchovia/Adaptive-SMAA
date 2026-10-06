# ⑫ 논문·공개 구현 기반 history validation 실험

⑫는 원본 SMAA 공간 처리를 보존한 edge-selective temporal에 rounded color neighborhood
clipping과 밝기 차이에 따른 history 누적을 적용한 독립 실험이다. 문헌·출처·최소 의존성·
식·원본 대비 변경은 [method.md](method.md), 설정은 [case.json](case.json)에 있다.
실험 번호는 최종 Original/Adaptive 8-case semantic matrix와 별개다.

**결론: ⑫는 얇은 선 소실·반짝임을 함께 해결하지 못해 채택하지 않았다.**
공개 기본값은 일부 프레임 변화를 줄였지만 선의 대비와 세부 정보를 잃는 구간이 있었다.
전체 AA 시간은 같은 실행의 ④ 대비 Bistro 약6.20% 감소, Minecraft 약11.31% 증가였다.
빠른 반응 설정에서도 품질과 비용의 문제를 함께 해결하지 못했다.

## 같은 실행의 성능 비교

RTX 3060 Ti, DX11 Release x64, Ultra, 1920×1061, hidden, VSync Off.
장면마다 독립 clean process에서 30초 준비 후 mode마다 300 warm-up,
4,800프레임 × 6회를 정·역순으로 교차 측정했다. PNG/query/readback은 Off다.
전체 AA 시간은 공간 처리·선택 준비, camera velocity와 temporal을 포함한다.
변화율은 동일 run④ 대비의 평균이며 전체 평균 시간을 나눈 비율과 조금 다를 수 있다.
④ Pattern On, 나머지 Off. camera/depth reprojection만 사용한다.

| 장면 | 구성 | 전체 AA ms | ④ 대비 | temporal ms | temporal ④ 대비 |
|---|---|---:|---:|---:|---:|
| bistro | ④ 원본 T2X-R | 0.156918 | +0.00% | 0.033343 | +0.00% |
| bistro | ⑥ 현재 edge | 0.133413 | -14.98% | 0.007409 | -77.78% |
| bistro | ⑨ 현재+직전 edge | 0.134572 | -14.24% | 0.007531 | -77.41% |
| bistro | ⑩ RGB bilinear | 0.134636 | -14.20% | 0.007671 | -76.99% |
| bistro | ⑪ resolved RGB | 0.146386 | -6.71% | 0.010072 | -69.79% |
| bistro | ⑫ clipping+adaptive 기본값 | 0.147181 | -6.20% | 0.010872 | -67.39% |
| bistro | ⑫ 넓은 반응 범위 | 0.147188 | -6.20% | 0.010871 | -67.40% |
| bistro | ⑫ native-weight clipping 대조군 | 0.147001 | -6.32% | 0.010890 | -67.34% |
| minecraft | ④ 원본 T2X-R | 0.227145 | +0.00% | 0.034922 | +0.00% |
| minecraft | ⑥ 현재 edge | 0.217783 | -4.12% | 0.023250 | -33.42% |
| minecraft | ⑨ 현재+직전 edge | 0.227720 | +0.25% | 0.023741 | -32.02% |
| minecraft | ⑩ RGB bilinear | 0.228098 | +0.42% | 0.024057 | -31.11% |
| minecraft | ⑪ resolved RGB | 0.245405 | +8.04% | 0.033127 | -5.14% |
| minecraft | ⑫ clipping+adaptive 기본값 | 0.252821 | +11.31% | 0.039768 | +13.88% |
| minecraft | ⑫ 넓은 반응 범위 | 0.252890 | +11.33% | 0.039735 | +13.78% |
| minecraft | ⑫ native-weight clipping 대조군 | 0.252518 | +11.17% | 0.039574 | +13.32% |

한 scene당 한 process의6 run이며6개 독립 세션이라고 주장하지 않는다. run별표본,
p95/p99, WholeFrame, spatial/camera 비용과 paired95% 구간은 benchmark JSON/CSV에 있다.
⑪↔⑫는 pattern/선택/기본 feedback 구조가 같다. ClippedRGB는 native weight를 유지하지만
clipping과 화면 밖 history 거부를 함께 추가하므로 전역 차이를 clipping 하나의 효과로
해석하지 않는다. 새로운 production draw/fullscreen copy는0개지만,
추가 neighborhood reads와⑪의 current-spatial MRT 비용은 포함한다.

## 품질: 직접 확인한 구조 손실과 수치의 차이

두 scene240frame×8조건. ④·⑩·⑪ 각240frame×2scene의 RGB는 보존 control과 일치했다.
scene별43 진단frame×4feedback 조건에서 입력·선택·history lifecycle과 alpha 보존,
비선택출력, weight범위와 제한된 color/feedback interval witness를 확인했다.
이상적인 CPU filter와 exact GPU filter를 혼동하지 않는다. 최초 CPU mirror 허용치
실패와 최종 오차는 method.md/quality-summary.json에 보존한다.

실제 nearest 확대 PNG의 moving126–131, transition178–183, still190–195를 직접 열었다.
Minecraft 벽 선은⑫ 기본값에서도 흐리거나 약해지는 구간이 남는다. Bistro의 얇은 의자
구조와 바닥 경계도 부드러워지면서 대비·세부 정보가 감소하는 구간이 있다. Response는
일부 현재 선에 더 반응하지만 얇은 구조와 반짝임을 일관되게 해결했다고 판정하지 않는다.
시간 변화의 감소는 camera motion과 blur도 포함하므로 반짝임 개선율로 해석하지 않는다.
전역 ghosting 감소·object motion·disocclusion의 범용 개선도 확인하지 않았다.

아래는 frame60–179의 좁은 ROI 측정이다. Bistro=(1230,582)-(1358,670),
Minecraft=(956,524)-(1020,620). MAE는 supersample **spatial proxy** 대비 오차,
2차 시간 차분은 미보정 화면 변화다. 낮을수록 곧 더 좋은 temporal 품질이라는 뜻이 아니다.

| 장면 | 구성 | ROI RGB MAE | luma 2차 시간 차분 |
|---|---|---:|---:|
| bistro | ④ 원본 T2X-R | 4.381512 | 4.589690 |
| bistro | ⑥ 현재 edge | 5.807495 | 3.715728 |
| bistro | ⑨ 현재+직전 edge | 5.684190 | 3.311098 |
| bistro | ⑩ RGB bilinear | 5.492582 | 3.232228 |
| bistro | ⑪ resolved RGB | 5.312600 | 3.026882 |
| bistro | ⑫ clipping+adaptive 기본값 | 5.624332 | 2.208761 |
| bistro | ⑫ 넓은 반응 범위 | 5.376715 | 2.625423 |
| bistro | ⑫ native-weight clipping 대조군 | 5.343690 | 3.116116 |
| minecraft | ④ 원본 T2X-R | 1.626500 | 2.851158 |
| minecraft | ⑥ 현재 edge | 1.398820 | 3.214362 |
| minecraft | ⑨ 현재+직전 edge | 1.399701 | 2.933147 |
| minecraft | ⑩ RGB bilinear | 1.265436 | 2.791010 |
| minecraft | ⑪ resolved RGB | 1.253528 | 2.761791 |
| minecraft | ⑫ clipping+adaptive 기본값 | 1.654756 | 2.339673 |
| minecraft | ⑫ 넓은 반응 범위 | 1.431846 | 3.004902 |
| minecraft | ⑫ native-weight clipping 대조군 | 1.286480 | 2.833760 |

정지 후⑫ 기본값의 전체 RGB는두scene 모두 마지막239 frame까지 바뀌었다. Response도
Bistro227/Minecraft239까지 변화가 남았다. ⑪는189 이후 동일했다. 일부 작은 변화가
눈에 잘 안 보여도⑫의 출력이 완전히 안정했다고 쓰지 않는다. 이는 global jitter를 켠
조건이 아니며 누적/재표본화 정착을 지터 위상 떨림과 구분해야 한다.
190–195프레임의 raw/current/velocity/edge 파일은 각 조건에서 모두 동일했다.
입력 내용은 고정돼 있지만 출력에는 변화가 남았다. 정확한 수치 메커니즘을
이 검사만으로 단정하지 않으며 [고정 입력 증거](static-input-hashes.json)에 경로와 hash를 보존했다.

Minecraft frame126–138의 같은 현재 spatial 선 좌표를 추적한 encoded RGB 대비의 평균은
⑪ 약23.85, ⑫ 기본값 약9.72, Response 약27.84였다. Response의 인접-frame 대비 변화는
약20.75로 ⑪ 약13.83보다 컸다. 이는 고정 화면 strip의 보조 진단이며 object tracking이나
정답 품질 점수가 아니다. [선 대비 추적](minecraft-line-contrast.json).

## 공식 CGVQM-2 보조 비교

이동60–179/전환160–219, unmodified공식60-frame 호출의 같은30-frame patch 평균이다.
④·⑩·⑪는 decoded RGB/reference hash 일치한 공식 기존점수를 재사용했다.
⑫ 자체의 full-window 모델 재실행은 하지 않았고, 단일 점수로 선 손실을 뒤집지 않는다.

| 장면/구간 | ④ | ⑩ | ⑪ | ⑫ 기본값 | ⑫ 넓은 반응 범위 |
|---|---:|---:|---:|---:|---:|
| bistro/moving | 96.191235 | 96.356331 | 96.376579 | 95.536400 | 95.890236 |
| bistro/transition | 96.719254 | 95.980339 | 96.006439 | 95.756226 | 95.877739 |
| minecraft/moving | 93.911362 | 95.965633 | 95.942749 | 90.511009 | 94.136074 |
| minecraft/transition | 94.905739 | 95.196068 | 95.216866 | 92.724579 | 94.458878 |

## ①–⑫ 전체 비교의 범위

④·⑥·⑨·⑩·⑪·⑫는 위 최신 동일 실행 결과다. 나머지①·②·③·⑤·⑦·⑧는 각 독립
연구 브랜치의 보존된 측정이며, 당시 같은 실행의④를 분모로 한 변화율을 유지한다.
아래 과거 절대시간을 최신④ 절대시간으로 나누지 않는다. [보존 출처](sources/historical-cases-1-8.json).

| 과거 구성 | Bistro 전체 AA ms | 당시④ 대비 | Minecraft 전체 AA ms | 당시④ 대비 |
|---|---:|---:|---:|---:|
| 1 | 0.000000 | -100.00% | 0.000000 | -100.00% |
| 2 | 0.093239 | -40.76% | 0.159555 | -29.83% |
| 3 | 0.079834 | -49.49% | 0.082369 | -63.79% |
| 5 | 0.097097 | -38.40% | 0.117412 | -49.72% |
| 7 | 0.171373 | +5.13% | 0.251434 | +8.07% |
| 8 | 0.147482 | -9.53% | 0.240398 | +3.33% |

과거 temporal 처리 시간만 비교하면 아래와 같다. 역시 당시 대응 ④가 분모다.
①·②는 temporal을 실행하지 않아 이 표에서 제외했다. ⑦·⑧의 보존 비용 분석은
4,800프레임 × 3회이며, ①·②·③·⑤의 six-case 갱신은 4,800프레임 × 6회다.

| 과거 구성 | Bistro temporal ms | 당시④ 대비 | Minecraft temporal ms | 당시④ 대비 |
|---|---:|---:|---:|---:|
| 3 | 0.033892 | +0.40% | 0.035185 | +0.41% |
| 5 | 0.007269 | -78.34% | 0.023548 | -34.39% |
| 7 | 0.010448 | -69.43% | 0.028700 | -19.24% |
| 8 | 0.007645 | -77.63% | 0.024124 | -32.11% |

과거 ①–⑧의 공식 보조 품질 점수도 함께 보존한다. 이는 당시 검증한 영상의 기록이며,
이번에 모든 사례를 다시 캡처·평가했다고 표현하지 않는다. 특히 점수만으로 이동 중
얇은 선 유지나 반짝임의 시각적 우열을 확정하지 않는다.

| 과거 구성 | Bistro 이동 | Bistro 전환 | Minecraft 이동 | Minecraft 전환 |
|---|---:|---:|---:|---:|
| 1 | 95.814602 | 95.577965 | 95.341587 | 94.986603 |
| 2 | 96.062752 | 95.874573 | 95.172501 | 94.916374 |
| 3 | 96.249035 | 96.792473 | 95.092743 | 96.216354 |
| 4 | 96.191238 | 96.719254 | 93.911362 | 94.905739 |
| 5 | 96.033230 | 95.647652 | 95.406033 | 94.968971 |
| 6 | 96.173374 | 95.911629 | 95.234108 | 94.894165 |
| 7 | 96.237839 | 95.941154 | 95.293442 | 94.901237 |
| 8 | 96.237839 | 95.941154 | 95.293442 | 94.901237 |

①AA-Off,②SMAA1X,③full temporal-only,④spatial+nativeT2X-R,⑤current-edge temporal-only,
⑥spatial+current-edge temporal,⑦previous-edge union의depth전달 구현,
⑧동일선택의stencil전달 개선,⑨첫edge단계eager 통합,⑩historyRGBbilinear,
⑪resolvedRGBfeedback,⑫roundedcolor validation+adaptive accumulation.
⑦↔⑧의출력동일성과속도개선,⑨실행구조개선은과거검증범위로 보존한다.
③·④PatternOn과⑤이후PatternOff의품질차이를모두edge선택효과로 단정하지 않는다.

## 자료와 채택 판정

[240-frame 비교](C:/Users/USER/Desktop/research/Deliverables/SMAA_12_Quality_20261006/comparison.html),
[실제720-frame 긴 비교](C:/Users/USER/Desktop/research/Deliverables/SMAA_12_Long_20261006/comparison.html).
GIF25fps/MP460fps를 실제sourceframe으로 만들고 전체decode·frame수·PTS를 검사했다.
보간/짧은source반복은없다. GIFpalette와MP4는손실이있으므로판정은원본PNG를 따른다.
직접 재생을 시청했다고 주장하지 않는다. Long영상은나중pose의정량reference가없는
presentation이고 formal품질표는240-frame같은pose입력만 사용한다.

⑫는 **얇은 선 소실·반짝임 해결의 품질 gate 미통과**로 보존하며 기본Off를 유지한다.
Clipping과높은누적을추가하면자동으로얇은구조가복원된다는가설을채택하지 않는다.
이는이조건의negative result이며edge-selective 연구전체의불가능성증명은 아니다.
사용자의영상검토와후속연구판단을대신해최종논문방법으로확정하지 않는다.

C·D의불필요중복저장은immutable캡처의SHA-256동일파일을같은볼륨hardlink로정리했다.
원본pixel내용·경로·유효reference는보존했고결과는storage-cleanup.json에 있다.
