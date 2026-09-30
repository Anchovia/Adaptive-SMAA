# ⑥ 선택 범위와 paired sample pattern 대조 결과

**이번 결과는 전체 화면으로 temporal 범위를 넓히는 것만으로 일관된 품질 개선을 얻지
못했음을 보여준다.** 비선택 영역의 temporal 처리는 시간 변화 오차 일부를 줄였지만
종합 품질과 공간 오차에는 장면별 손익이 있었다. 순수 반짝임·고스팅 개선율이나 모든
장면의 원인을 확정한 결과는 아니다.

## 독립 브랜치와 변경 범위

- 브랜치: `validation/spatial-edge-coverage-pattern-control`
- 직접 기준선: `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459` (수정된 ⑥).
- 측정 renderer: `eb1bd0b`. 이전 ⑤ 및 history contribution 진단 브랜치는 합치지 않았다.
- shader 원문 5개는 기준선과 동일하다. 새 대조군은 같은 ⑥ shader, spatial 입력,
  point sampling, native 0..0.5 weight 및 이전 spatial-frame history를 유지하고,
  temporal draw에만 stencil test를 비활성화했다. 별도 선택 패스를 추가하지 않았다.
- 지터 On/Off는 projection jitter와 해당 spatial subsample index의 paired pattern이다.
  Camera/depth reprojection은 모든 조건에서 On이다. Object motion 결과는 아니다.
- 기존 `12f5d56`에서 비대화형 shader compile 실패 종료만 실행 도구로 재사용했다.

## 비교 조건 및 검증

| 표기 | Temporal 범위 | Paired pattern | 용도 |
|---|---|---|---|
| ⑥ Edge Off | 기존 first-pass final RG edge | Off | 검증된 기존 구현 |
| Full Off | 동일 resolve 전체 화면 | Off | 선택 범위만 바꾼 새 대조군 |
| ④ Full On | 기존 native 전체 화면 | On | 원본 T2X-R 기준선 |

보조 검증으로 native full-screen Pattern Off와 새 Full Off의 관측 MRT Off 반복을
같이 실행했다. 두 보조 조건은 알고리즘 후보로 추가한 것이 아니다.

Bistro/Minecraft 각각 새 clean process에서 5개 조건 × 240 frame을 캡처했다.
1920×1061, Ultra, fixed60, warm-up60, still60/move120/still60이다.
모든 프로세스는 timeout 안에 정상 종료했고 잔류 CMAA2 프로세스는 0개였다.

- 전체 캡처: 2,400 RGB frame. 기존 ⑥·④와 기준선 960 frame mismatch 0.
- Full Off ↔ native Full Off 480 frame, Full Off ↔ 관측 Off 반복 480 frame mismatch 0.
- 각 장면의 Off 조건 current/previous RGBA 및 velocity 전체 텍셀 hash가 239 frame에서
  동일했다. Frame0은 seed이므로 이전 history hash 검사에서 제외했다.
- 100/179/180/190 frame의 세 입력 DDS는 네 Off 조건에서 byte 단위로도 같았다.
- 320개 frame의 GPU coverage를 검사했다. ⑥은 final RG>0과 정확히 같고 Full Off는
  전체 2,037,120 pixel에서 실행됐다. PS invocation과 passed sample 수도 대응했다.
- edge 내부의 ⑥/Full Off 출력은 동일하고, edge 외부의 ⑥은 current를 그대로 유지했다.
  이동 중 비선택 픽셀 중 실제 출력이 달라진 비율은 Bistro 30.06%, Minecraft 44.71%다.
- 정지 안정 구간 190..219에서 Edge Off와 Full Off는 전체 화면 RGB가 동일했다.
  세 주요 조건 모두 후기 정지 출력 hash는 한 개였다.

## 품질 비교

CGVQM-2는 높을수록 좋다. 아래 점수 12개는 **현재 캡처와 같은 reference의 해당 window
RGB stream hash가 과거 측정과 완전히 같음을 확인해 재사용**했다. 모델을 새로 실행한
결과가 아니다. 수정된 구현에서 이전 수치의 적용 가능성을 새로 검증한 것이다.
Intel official commit, CUDA, 60 FPS, patch-scale4, mean pooling, FFV1 무손실 round-trip도
기존 기록에서 검사했다. 기록은 `bistro-quality.json`, `minecraft-quality.json`에 있다.

| 장면·구간 | ⑥ Edge Off | Full Off | ④ Full On | Full Off − Edge Off |
|---|---:|---:|---:|---:|
| Bistro 이동 60..179 | 96.1734 | 96.3548 | 96.1912 | +0.1814 |
| Bistro 이동→정지 160..219 | 95.9116 | 95.9736 | 96.7193 | +0.0620 |
| Minecraft 이동 60..179 | 95.2341 | 95.1213 | 93.9114 | −0.1128 |
| Minecraft 이동→정지 160..219 | 94.8942 | 94.8153 | 94.9057 | −0.0789 |

단일 점수에는 선명도, 공간 오차와 시간적 변화가 함께 반영된다. 위 수치만으로
Minecraft에서 ④의 반짝임이 더 심하다거나 Full Off의 고스팅이 감소했다고 해석하지 않는다.
Reference는 동일 pose의 supersample spatial proxy이며 temporal ground truth가 아니다.

원본 PNG로 별도 계산한 이동 구간 ROI의 보조 지표는 다음과 같다. RGB MAE와 reference
오차의 시간 차분은 모두 0..255 색상 단위이며 낮을수록 해당 오차가 작다.

| ROI | RGB MAE Edge → Full Off | Reference 오차 시간 차분 Edge → Full Off |
|---|---:|---:|
| Bistro 의자 다리 | 2.6762 → 2.5484 | 1.7762 → 1.4911 (−16.05%) |
| Bistro 창살 | 2.8284 → 2.7202 | 2.3240 → 2.0837 (−10.34%) |
| Minecraft 얇은 경계 | 1.3165 → 1.3988 | 1.2693 → 1.0324 (−18.66%) |

시간 차분은 `mean(abs((Y_test−Y_ref)_t−(Y_test−Y_ref)_(t−1)))`이다.
Optical-flow 정렬이나 순수 flicker metric이 아니며 카메라 이동 중 오차 변화도 포함한다.
따라서 −16%/−19%를 '반짝임이 그만큼 줄었다'로 표현하지 않는다. Minecraft는 이 보조
지표가 줄면서 공간 오차와 CGVQM이 악화되어, 안정화와 세부 보존의 손익을 함께 봐야 한다.

후기 정지 전체 화면 RGB MAE는 Edge/Full Off가 Bistro 0.7092, Minecraft 1.5694로 같고,
④는 각각 0.5828, 1.4717이었다. 같은 native full-screen Off 출력과 ④ On을 비교하므로
이 차이는 coverage 확대와 분리된 paired sample-pattern 차이다.

## 같은 세 장면의 영상

`Projects/CMAA2/Captures/coverage-pattern-control-20260930/`에 저장했다.
좌측 ⑥ Edge Off, 중앙 Full Off, 우측 ④ Full On이다. 각 파일은 같은 frame/ROI의
60-frame sequence, 2배 nearest 확대다. 이동은 0.5배속, 이동→정지는 0.25배속이다.

- `bistro-chairs-moving.webp` / `.gif`: 의자 다리, frame100..159.
- `minecraft-thin-edges-moving.webp` / `.gif`: 얇은 경계, frame100..159.
- `bistro-window-stop.webp` / `.gif`: 창살, frame160..219.

WebP는 모든 decode RGB pixel이 원본 합성 frame과 동일한 무손실 영상이다.
GIF는 전체 clip에 하나의 고정 팔레트를 쓰며 색 양자화가 있다. 두 포맷 모두 frame 수와
재생 시간을 검사했다. 지표 계산에는 GIF가 아닌 원본 PNG만 썼다. 경로/hash는 `media.json`.

## 결론과 남은 질문

1. 동일 입력에서 선택 범위만 바뀌는 대조 조건을 확보했다. ⑥ edge 내부의 계산 오류나
   새 대조군의 history 차이로 이번 비교를 설명할 근거는 없다.
2. 현재 edge 밖의 결합이 시간적 안정화에 일부 기여할 여지는 관측됐다. 그러나 전체 화면
   적용은 장면별 종합 품질을 일관되게 높이지 않았고 공간 오차가 증가하기도 했다.
3. coverage만으로 현재 모든 현상을 설명하거나, 단순 확대를 해결책으로 채택하지 않는다.
   source TSCMAA의 filtering·feedback·weight 같은 처리 차이는 이후 독립 실험의 대상이다.
   이번 브랜치에서는 그 요소, dilation 및 새 jitter 방식을 구현하지 않았다.
4. 새로운 성능 benchmark는 수행하지 않았다. 관측용 GPU query/MRT/readback을 사용한
   실행 시간으로 속도를 비교하지 않는다. 기존 여섯 기준선과 성능 결론은 변경하지 않는다.
