# Spatial / temporal 6구성 진단 계획

공통 기준은 `validation/smaa-baseline-restart`의 `e14f122`다. 원본 공간 SMAA 계보는
`ee0020d`, 원본 T2X/R 기준은 `88893da`다. 기준선 검증과 shader 수명 수정만 포함하며
기존 누적 selective 실험은 상속하지 않는다. 이 비교는 최종 8-case를 대체하지 않는다.

| 구성 | ID | Spatial 보정 | Temporal | 브랜치 |
|---|---|---|---|---|
| 1 | AA-Off | 없음 | 없음 | 검증된 기준선 |
| 2 | O-1X | 원본 3단계 | 없음 | 검증된 기준선 |
| 3 | ABL-TemporalOnly-R | 없음 | 원본 전체 화면 resolve | experiment/temporal-only-control |
| 4 | O-T2X-R | 원본 3단계 | 원본 전체 화면 resolve | 검증된 기준선 |
| 5 | ABL-FirstEdge-TemporalOnly-R | 검출만, 보정 없음 | 실제 첫 edge에서만 | 별도 독립 브랜치, 미구현 |
| 6 | ABL-FirstEdge-Spatial-R | 원본 3단계 | 실제 첫 edge에서만 | 별도 독립 브랜치, 미구현 |

현재 브랜치에서는 **3번만 구현**하고 1/2/4를 회귀 기준으로 사용한다. 5/6은 각각 같은
검증된 기준에서 분기한다. 3번 코드를 필요로 하면 해당 최소 의존성을 명시적으로 가져온다.
영역별 지터 렌더링, 후보 확장, Adaptive 결합은 범위 밖이다.

## Temporal-only의 의미

- 지터가 있는 원본 장면 RGB를 그대로 사용한다. edge/weight/spatial blend를 실행하지 않는다.
- 원본 neighborhood shader의 zero-weight 경로와 같은 linear level-zero current/velocity
  sampling과 `sqrt(5*length(velocity))` alpha packing을 준비 draw에서 수행한다.
- 이는 scene RGB의 공간 보정이 아니다. 준비 draw의 GPU 비용을 전체 SMAA scope에 포함한다.
- 원본 `SMAAResolvePS`를 수정 없이 호출한다. point current/history/velocity, alpha 기반
  가변 history weight 0..0.5, camera/depth 재투영, 공간 프레임형 ping-pong history와
  첫 프레임 seed를 유지한다. resolved-output feedback으로 바꾸지 않는다.
- 이 경우 history에 저장되는 '공간 프레임'은 spatial AA 전 RGB + packed alpha다.
- spatial 보정을 없애므로 원본의 이웃 기반 velocity 보정도 제외한다. native no-blend
  경로의 velocity를 사용하며, 원본과 alpha까지 동일하다고 주장하지 않는다.
- 전역 T2X projection jitter는 유지한다. area subsample index를 사용하는 공간 보정은
  실행하지 않으므로 3번에는 area pattern 적용 자체가 없다. 원본 SMAA T2X로 명명하지 않는다.
- R은 camera-motion만 의미한다. object velocity, clipping, 추가 history filter는 없다.

원본 근거: 저장소 `SMAA.hlsl`의 neighborhood zero-weight와 resolve 함수 및
[SMAA 공식 소스](https://github.com/iryoku/smaa/blob/master/SMAA.hlsl).
현재 연구는 고정한 로컬 원본을 기준으로 하며 upstream 최신 코드로 교체하지 않는다.

## 검증 및 측정

- 기존 기준선과 같은 DX11/Ultra/1920x1061, fixed 60Hz, 60정지+120이동+60정지 경로.
- AA-Off/O-1X/O-T2X-R 각 240 frame을 기존 독립 캡처와 RGB 비교한다.
- ABL 240 frame 반복, native neighborhood에 zero blend texture를 준 REF 240 frame을 비교.
  REF는 검증용이며 production 성능에는 포함하지 않는다.
- 10개 프레임에서 원본 입력, 준비 RGBA와 velocity를 DDS로 저장한다. ABL의 입력 RGB
  보존, native REF와 RGBA 일치, 반복 일치 및 first-frame seed를 검증한다.
- 지터/정지 안정성은 직접 측정한다. 차이가 나오면 실패 원인을 조사하고 감추지 않는다.
- PNG/DDS 저장 없는 독립 clean-process smoke 후 300 warmup, 4800 frame x4회 교차 측정.
  전체 SMAA 시간이다. 과거 서로 다른 실행의 절대 timing 차이를 최적화 효과로 사용하지 않는다.
- 5/6에서 비선택 영역은 **지터가 있는 현재 색상**이다. 이를 일반 SMAA 1X라고 부르지 않는다.
  raw edge mask와 temporal 전/후 출력을 대응시켜 떨림 위치를 검증한 후, pattern-Off를
  별도 실험으로 다룬다. 원본 조건의 실패 결과도 그대로 보존한다.
