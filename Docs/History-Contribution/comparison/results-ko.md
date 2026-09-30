# ⑤·⑥ 실제 history 비중과 출력 변화

⑤는 공간 AA 없는 raw 입력, ⑥은 공간 SMAA 결과를 temporal의 current로 사용한다.
두 사례는 각각 수정된 기준선에서 직접 분기한 독립 진단 브랜치다.

| 사례 | 브랜치 | 진단 검증 커밋 |
|---|---|---|
| ⑤ | validation/raw-edge-history-contribution | 9d7fe53 |
| ⑥ | validation/spatial-edge-history-contribution | d603d29 |

실제 native resolve의 계산된 history weight를 GPU R32_FLOAT MRT로 저장하고,
동일 프레임의 current와 final RGB를 비교했다. 변경된 품질 알고리즘의 측정이 아니다.
지터, dilation, sampler, weight 계산, history feedback 구조는 기존 상태를 유지했다.

이동 구간 frame 100..179에서, 전체 화면의 선택된 픽셀만 집계한 프레임 평균이다.

| 장면 | 사례 | 화면 중 선택 비율 | history 비중 | 선택 픽셀 중 RGB 변화 있음 |
|---|---|---:|---:|---:|
| Bistro | ⑤ | 2.62% | 47.89% | 54.24% |
| Bistro | ⑥ | 2.62% | 47.73% | 67.26% |
| Minecraft | ⑤ | 24.26% | 49.24% | 76.21% |
| Minecraft | ⑥ | 24.26% | 49.18% | 81.49% |

이 장면에서는 선택된 픽셀의 history 비중이 대체로 native 최대치인 50% 근처다.
따라서 반짝임이 남는 현상을 '선택 픽셀에서도 history 비중이 거의 0이어서'로 일반화할
수 없다. 단, 평균이 높아도 특정 위치의 낮은 weight 또는 선택 누락을 배제하지 않는다.
위 RGB 변화 비율은 품질 개선 비율이 아니다.

정지 안정 구간 frame 190..219는 두 장면·두 사례 모두 history 비중 50%, current→final
RGB 변화 0이다. frame190 probe의 선택 픽셀 current/previous RGBA는 동일하고 velocity도
정확히 0이었다. History를 읽어 섞어도 입력이 같으면 화면 색상은 바뀌지 않는다.

## 시각화 읽는 법

- 좌측 ⑤, 우측 ⑥. 상단은 실제 history 비중, 하단은 current→final RGB 변화다.
- 상단은 검정 0, 흰색 0.5다. 비선택 영역도 검정이며, 수치 자료에서는 sentinel -1로
  구분해 보존했다. 하단은 `max(abs(RGB_final - RGB_current)) * 16`을 0..255로 제한했다.
- 이전 세 장면의 동일 frame/ROI를 2배 nearest 확대했다. 이동은 0.5배속, 이동→정지는
  0.25배속이다. GIF의 ROI 평균과 위 표의 전체 화면 선택 픽셀 평균은 집계 범위가 다르다.
- 색상 변화가 크다고 품질이 좋거나 고스팅이 감소했다는 뜻은 아니다.

각 GIF 60 frame의 재생 시간과 decode된 모든 grayscale 픽셀을 검증했다.
파일 경로, SHA-256, 원본 분석 커밋은 `media.json`에 기록했다.

## 검증 범위와 오류 기록

각 사례·장면에서 진단 On 240 frame, 원본 ④ 240 frame, 진단 Off 반복 240 frame을
수정 기준선과 비교했다. 총 2,880 frame RGB mismatch 0이다. 480개의 진단 coverage가
기존 자료와 같았고 ⑤·⑥ coverage도 서로 동일했다. 비선택 current→final 변화는 0이다.
각 브랜치 production shader entry 6개의 DXBC는 기준선과 같았다.

⑥ 최초 startup은 진단 변수 선언보다 engine macro include가 늦게 실행되어
`capturedHistoryWeight` 미선언 컴파일 오류가 발생했다. 소유한 실행만 종료하고 해당
run을 제외했다. 수정 뒤 엔진의 virtual macro include 방식도 외부 검사에 추가하고,
실제 앱 캡처 및 RGB 회귀 검증을 수행했다. 상세 제외 기록은 ⑥ 브랜치의
`Docs/History-Contribution/case6/excluded-startup.json`에 있다.

이번 자료는 TSCMAA식 필터/누적 방식 적용 여부를 판단하기 위한 관측이다. 반짝임의
원인별 기여 또는 개선책의 우열, 성능 개선을 확정한 결과가 아니다.
