# 선택적 temporal 기준선 두 가지

2026-11-07부터 ⑱ 대신 아래 두 구성을 기준선으로 쓴다. 둘 다 브랜치 `baseline/selected-temporal`에 있고 `vaSMAAWrapper::ApplyTemporalRoute`로 고른다. ⑱은 `baseline/selected-temporal-case18`에 그대로 보존한다. `-R`은 계속 camera/depth reprojection만 뜻한다.

| 기준선 | 경로 값 | 하니스 모드 이름 |
|---|---|---|
| 선택 경로 (주 기준선) | `TemporalRoute::Selected` | `ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend+OPT-NeighborhoodNoDepth+PresentHistory+NoVelocityAlpha` |
| 19번 | `TemporalRoute::SelectedVelocityInEdge` | 위 이름 `+VelocityInEdge` |

## 두 구성의 공통점

- 공간 처리는 원본 SMAA 1X의 세 패스이며 `SMAA.hlsl`을 바꾸지 않는다. projection jitter는 쓰지 않는다.
- edge 패스가 현재 raw edge와 카메라 재투영한 이전 raw edge를 stencil에 표시하고, 표시된 픽셀만 resolve한다.
- resolve는 Catmull-Rom 5-tap history, 고정 비중 0.8, encoded gamma2 혼합이다. 결과를 다음 history로 쓰고 그 history를 화면에 표시한다.
- neighborhood 패스는 depth를 쓰지 않고 velocity alpha도 계산하지 않는다.

## 다른 점

선택 경로는 SMAA 앞의 전용 패스가 화면 전체 velocity를 만들고, SMAA는 그것을 입력으로 받는다. 원본 SMAA의 temporal 입력 구조와 같고 화면 RGB가 ⑱과 240/240 프레임 같다. SMAA를 보존한 edge 선택 temporal이라는 연구 설명에 맞는 구성이라 주 기준선으로 둔다.

19번은 전용 패스를 없애고 SMAA edge 패스가 velocity를 계산해 선택된 픽셀에만 기록한다. 두 패스의 uv 보간 차이(최대 1.2e-7) 때문에 ⑱과 RGB가 소수 픽셀 다르다(Minecraft 이동 중 프레임당 약 0.11%, 최대 채널 차이 109). 직접 확인한 프레임에서 선 소실이나 새 단절은 찾지 못했다. edge 패스가 depth와 카메라 행렬에 묶이고 velocity가 선택 픽셀에서만 유효하다는 제약이 있다. 이 구조를 받아들이는 성능 우선 기준선으로 둔다.

## 현재 수치 (2026-11-03, 같은 실행 짝 비교)

RTX 3060 Ti, 1920×1061 숨김 창, 300 warm-up 뒤 4,800프레임 6회.

| 기준선 | Bistro AA (④ 대비) | Minecraft AA (④ 대비) |
|---|---:|---:|
| ④ `O-T2X-R` | 0.1568 ms | 0.2347 ms |
| 선택 경로 | 0.1275 ms (-18.71%) | 0.2309 ms (-1.60%) |
| 19번 | 0.1121 ms (-28.53%) | 0.2180 ms (-7.10%) |

SMAA 폴더 코드 변화량은 원본 SMAA 대비 +545/-61줄이고 그중 19번에만 필요한 줄은 약 20줄이다. 자세한 근거는 `Docs/Selected-Temporal-Minimal/readme-ko.md`와 `Docs/Case19-Velocity-Edge-Merge/readme-ko.md`를 따른다.

## 이후 비교 규칙

- 새 실험은 이 브랜치에서 독립 분기한다.
- 성능은 같은 실행 안의 ④, 선택 경로, 19번과 짝지어 비교한다. 다른 날이나 다른 프로세스의 절대 시간은 비교 분모로 쓰지 않는다.
- 출력 보존 최적화라고 말하려면 대응 기준선과 240프레임 화면 RGB가 같아야 한다. 선택 경로를 바꾸는 실험은 선택 경로와, 19번을 바꾸는 실험은 19번과 비교한다.
- ⑱의 Minecraft 이음매 약화(f128·f130)는 두 기준선에도 그대로 남아 있다. ④와 품질이 같다고 쓰지 않는다.
