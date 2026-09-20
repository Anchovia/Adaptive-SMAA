# ScalarWeight 품질 검증 결과

현재 `0.01` 픽셀별 luma 선택 + ScalarWeight는 이번 두 장면에서 원본 T2X-R을
대체할 품질 개선을 입증하지 못했다. 정지 후에도 두 frame이 번갈아 나오는 불안정성이
남고, 공간 기준 오차와 영상 품질 예측 점수도 불리했다. 고스팅 감소는 검토한 연속
PNG에서 명확하게 확인하지 못했으며, 아래 점수만으로 고스팅 악화라고 단정하지 않는다.

선택식, shader, renderer, 기본 mode를 변경하지 않았다. 새 GPU capture나 성능 측정도
하지 않았다. [방법과 해석 범위](method.md), [검증 수치](results.json).

## 현재 구현과 이전 품질 결과의 연결

2026-09-21 Cost capture의 ScalarWeight와 2026-09-17에 품질을 평가한 branch 출력은
두 장면 총 480 frame에서 PNG까지 정확히 같다. Native와 mask, reference capture
control을 포함한 총 2,880회 hash 비교에서도 불일치가 없다. Decode한 전체 RGB stream
hash도 이전 품질 분석과 일치한다. 선택 픽셀은 원본 temporal 결과, 비선택 픽셀은
current spatial 결과라는 조건을 480 frame 모두 통과했다.

CGVQM-2의 이동·전환 총 8개 평가에 대해 현재 test/reference RGB를 다시 읽어 원래
공식 실행의 frame-index 포함 hash와 비교했다. 불일치가 없어 기존 score를 재사용한다.
새로 CGVQM을 실행한 결과로 표현하지 않는다. ScalarWeight가 바꾼 것은 GPU 실행 방식이며,
이번 검증 범위에서 기존 선택 방식의 화면과 품질 특성은 그대로다.

## 정지 후 깜빡임: 감쇠하는 잔상이 아니라 두 frame의 반복

정지 후기 frame 200~239를 검사했다. 원본은 두 장면 모두 RGB 영상이 한 종류로
안정된다. ScalarWeight는 정확히 두 종류이며, 두 frame 간격 비교 38쌍은 모두 일치한다.
즉 정지 후에도 A/B/A/B 출력이 지속된다. 아래 변화량은 인접 39쌍의 **전체 화면**
평균 절댓값 RGB 차이(0~255 단위)이며 지각적 깜빡임 점수가 아니다.

| 장면 | 원본 평균 변화 | ScalarWeight 평균 변화 | ScalarWeight 인접 frame당 변경 픽셀 |
|---|---:|---:|---:|
| Bistro | 0 | 1.287832 | 1,339,687 |
| Minecraft | 0 | 0.580355 | 539,572 |

이 변화가 어디서 발생하는지도 GPU 선택 mask와 대조했다.

| 장면 | 두 frame 모두 비선택인 위치의 변화량 비중 | 선택 여부가 바뀐 위치의 비중 | 두 frame 모두 선택인 위치 |
|---|---:|---:|---:|
| Bistro | 91.0697% | 8.9303% | 변화 0 |
| Minecraft | 25.9640% | 74.0360% | 변화 0 |

비중의 분모는 RGB 절댓값 변화의 전체 합이며 픽셀 비율이 아니다.
Bistro는 계속 생략되는 위치, Minecraft는 선택 여부가 바뀌는 위치의 영향이 크다.
따라서 모든 깜빡임을 후보 mask의 on/off 전환 하나로 설명할 수 없다.

코드상 비선택 픽셀에도 paired projection jitter가 적용되고, temporal 결합만 weight 0으로
꺼진다. 공간 처리 결과의 지터 위상 차이가 그대로 출력될 수 있다. 실제로 모든 비선택
출력이 current-spatial control과 일치하고, 두 frame 모두 선택된 위치는 안정됐다.
이는 선택과 지터의 상호작용에 대한 근거다. ScalarWeight의 산술 오차나 분기 최적화로
새로 생긴 품질 문제로 볼 근거는 없다.

## 이동·전환 영상 품질

CGVQM-2는 높을수록 좋다. 변화는 원본 대비 **점수 차이**이며 백분율이 아니다.
이동은 60~179, 전환은 160~219로 일부 겹친다. 평가자는 사람이 아닌 영상 품질 예측 모델이다.

| 장면 | 구간 | 원본 | ScalarWeight | 변화 |
|---|---|---:|---:|---:|
| Bistro | 이동 | 96.191238 | 93.289406 | -2.901833 |
| Bistro | 이동→정지 | 96.719254 | 89.954178 | -6.765076 |
| Minecraft | 이동 | 93.911362 | 93.135750 | -0.775612 |
| Minecraft | 이동→정지 | 94.905739 | 93.160217 | -1.745522 |

선택 비율은 240 frame 평균으로 Bistro **1.512%**, Minecraft **50.449%**다.
분모는 edge 개수가 아닌 전체 2,037,120 pixel이다. ScalarWeight는 비선택 위치에서도
velocity/history를 읽는다. 이 비율을 접근 생략률 또는 실제 양의 history weight 비율로
해석하면 안 된다.

## 선명도와 고스팅을 구분한 검토

이전부터 사용한 Bistro 의자·메뉴판·바닥 ROI와 Minecraft 벽면·전경 경계 ROI를 그대로
검토했다. Frame 110~113, 179~182, 200~203의 연속 PNG와 원본 크기 crop을 확인했다.
뚜렷한 잔상 감소를 확정할 수 있는 분리된 이전 윤곽은 이 자료에서 확인하지 못했다.
이를 모든 장면에서 고스팅 이득이 없다는 결론으로 확대하지 않는다.

이동 구간 ROI의 세부 구조 수치는 다음과 같다. 차분 크기 비율은 reference가 1이고,
차분 오차는 낮을수록 reference의 국소 변화에 가깝다. 둘 다 순수 선명도 점수는 아니다.

| 장면 | 방식 | RGB MAE | 수평·수직 차분 오차 | 차분 크기/reference |
|---|---|---:|---:|---:|
| Bistro | 원본 | 0.635195 | 0.771295 | 0.980239 |
| Bistro | ScalarWeight | 0.933827 | 1.062893 | 1.104616 |
| Minecraft | 원본 | 1.593993 | 1.690005 | 0.932041 |
| Minecraft | ScalarWeight | 1.676953 | 1.797028 | 0.937093 |

Bistro에서 윤곽 변화가 강해진 것은 기준 영상에 가까워진 선명도 개선으로 보기 어렵다.
변화 크기가 reference를 넘고 국소 차분 오차도 커졌다. Minecraft는 변화 크기가 조금
reference에 가까워지지만 차분 오차와 RGB 오차는 커져 일관된 세부 구조 개선이 아니다.
이동·전환·정지의 두 ROI 모두 ScalarWeight의 RGB/차분 오차가 증가했다.

이 경로에는 별도로 움직이는 물체나 정답 disocclusion mask가 없다. 실제 움직임을
포함한 연속 PNG 검토와 국소 구조 검사는 했지만, 고스팅 감소율이나 잔상의 지속 frame
수를 정량 검증했다고 주장하지 않는다. Supersample도 공간 기준이며 절대 temporal
ground truth가 아니다. 많은 사람이 정속 영상을 보고 평가한 실험도 아니다.

## 비교 자료

각 장면 폴더에 `detail-60fps.mp4`, `moving.gif`, `transition.gif`, `still.gif`,
연속 PNG sheet와 `still-difference-x8.png`를 저장했다.

- [Bistro 자료](../../Projects/CMAA2/AutoBench/ScalarQualityReview/bistro/)
- [Minecraft 자료](../../Projects/CMAA2/AutoBench/ScalarQualityReview/minecraft/)

좌→우는 공간 reference / 원본 / ScalarWeight다. MP4는 240 frame, 실제 60 FPS이며
전체 decode의 frame 수와 PTS를 검사했다. GIF는 0.5배속 보조 자료다. 차이 ×8은
변화 위치를 강조한 진단이며 실제 화면의 체감 강도가 아니다. 압축 영상은 측정에 쓰지 않았다.

## 현재 판단

[최근 독립 짝 비교](../Temporal-Contrast-Pair/report.md)의 ScalarWeight 전체 SMAA 평균은
원본 대비 Bistro +0.136%, Minecraft +0.321%였으며 실행 순서 영향 때문에 동등성이나
가속을 입증한 결과가 아니다. Temporal resolve는 각각 +0.809%, +0.451%였다.
이 성능 수치는 이번 품질 분석과 별도 실행에서 얻었고 예전 branch timing과 구분한다.

현재 선택식과 threshold에서는 **품질 개선을 위해 작은 속도 손실을 받아들일 근거도
확보하지 못했다.** 원본을 대체하는 기본 구현으로 채택하지 않고 비교·실패 분석용으로
보존하는 것이 타당하다. 낮은 현재-frame luma 대비가 temporal 결합이 불필요하다는
뜻은 아니라는 점을 특히 기록한다. 다른 선택식 전체나 선택적 temporal 원리 자체가
불가능하다는 결론은 아니다. 후보 확장이나 새 알고리즘은 이번 작업에서 추가하지 않았다.
