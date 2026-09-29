# ⑥ 원본 공간 SMAA + 첫 edge 선택 temporal 결과

## 실험 범위

`experiment/spatial-first-edge-temporal`를 검증된 공통 기준 `e14f122`에서 직접 만들었다.
구현 커밋은 `8e5a972`다. ⑤ 전체 구현을 상속하지 않고 선택 shader/draw 및 진단 helper만
`a774772`에서 명시적으로 재사용했다. 공간 AA를 생략하는 ⑤와 독립된 연구 항목이다.

⑥은 원본 SMAA의 edge detection → blending-weight calculation → neighborhood blending을
전부 실행한 뒤, **기존 temporal resolve에서 첫 RG edge가 있는 픽셀만 원본 T2X-R 계산**을
수행한다. 비선택은 현재 공간 SMAA 색상이다. 검출/입력 준비/복사/후보 compact 등의 새
렌더 패스는 추가하지 않았다. 별도 contrast 선택식, dilation, Adaptive 결합도 없다.

원본 T2X-R과 같은 paired projection jitter/subsample, point history, velocity-alpha 기반
가중치 0..0.5, 프레임별 spatial history를 유지했다. R은 camera/depth reprojection이며
object motion vector는 포함하지 않는다. Intel TSCMAA 전체 포팅이나 최종 8-case 결과가 아니다.

## 정확성 및 공간 AA 보존

Release x64 빌드 및 FXC ps_4_1 R Off/On 검사가 통과했다. 원본 `SMAA.hlsl`, wrapper shader,
`SMAA::go`, edge/weight/neighborhood 함수와 원본 resolve 함수 본문은 기준선과 동일하다.
실제 runtime은 R-On이다. FXC에서 비선택 경로는 history/velocity sample 명령을 건너뛰도록
컴파일됐음을 확인했지만 실제 GPU ISA/warp 효율은 측정하지 않았다.

각 장면 1920×1061, Ultra, 정지60/이동120/정지60의 240프레임을 캡처했다.

| 검증 | 장면당 범위 | 결과 |
|---|---:|---|
| AA-Off / 실제 O-1X / O-T2X-R와 독립 원본 캡처 | 3×240프레임 | RGB 불일치 0 |
| ⑥ reset 후 반복 | 240프레임 | RGB 불일치 0 |
| ④와 ⑥의 temporal 직전 spatial RGB | 488,908,800픽셀 | 불일치 0 |
| 선택 출력=④ resolve, 비선택 출력=current spatial | 488,908,800픽셀 | 불일치 0 |
| ⑤와 ⑥의 실제 RG edge | 240프레임 | 불일치 0 |
| ④/⑥/반복의 scene input·spatial RGBA·velocity DDS | 10 대응 프레임 | 불일치 0 |
| ④/⑥/반복의 RG edge | 10 대응 프레임 | 불일치 0 |

Raw scene RGB와 spatial RGB가 실제로 달라지는 픽셀도 모든 probe에서 확인했다.
공간 AA가 생략된 출력과 비교해 테스트를 통과시킨 것이 아니다.

| 장면 | probe별 공간 보정으로 달라진 픽셀 수 범위 | 전체 240프레임 평균 edge 선택 비율 |
|---|---:|---:|
| Bistro | 34,654 ~ 38,581 | 2.594% |
| Minecraft | 84,303 ~ 253,740 | 17.368% |

선택 비율의 분모는 화면 전체 2,037,120픽셀이다. 검출 edge 중 50%를 남긴 값이 아니며,
추가 제거 없이 원본 RG edge를 모두 사용했다. 공간 처리 후에도 edge mask 자체는 ⑤와 같다.

## 정지 품질

AA-Off/실제 SMAA 1X/원본 SMAA T2X-R은 초기·후기 정지 구간에서 RGB 고유 프레임이 1개였다.
⑥은 두 프레임을 번갈아 반복했으며 각 구간의 lag-2 비교는 38/38쌍 일치했다.
**공간 SMAA를 보존해도 edge 밖의 지터를 안정화하는 temporal 결합을 생략하면 떨림이 남았다.**
일반 1X는 projection jitter가 없는 별도 원본 경로다. 현재 jittered spatial을 1X라고 부르지 않는다.

후기 정지 200~239의 평균 RGB 절댓값 변화(0~255 단위):

| 장면 | 원본 ④ | ⑤ 공간 보정 없음 | ⑥ 공간 SMAA 유지 | 양쪽 비선택 기여 | 선택 상태 변경 기여 |
|---|---:|---:|---:|---:|---:|
| Bistro | 0.000000 | 1.223442 | 1.255586 | 1.040598 | 0.214988 |
| Minecraft | 0.000000 | 2.797890 | 2.954760 | 1.784873 | 1.169887 |

양쪽 프레임 모두 선택된 픽셀의 변화 기여는 0이었다. 나머지 두 그룹의 합이 표의 ⑥ 변화다.
⑤와 ⑥ 비교는 정렬된 동일 정지 프레임의 변화 진단이며 절대 품질 점수나 공간 AA 일반의
우열이 아니다. 이동 중 고스팅·선명도·CGVQM/초고해상도 reference 평가는 아직 하지 않았다.
이번 구현은 정지 안정성 gate를 통과하지 못했으므로 품질 개선안으로 채택하지 않는다.

## 원본 T2X-R 대비 성능

첫 smoke는 WholeFrame GPU가 0이어서 실패로 제외했다. 공통 기준선의 프레임 루프에서
BeginFrame 중복 호출을 발견해 `tooling/smaa-frame-lifecycle`의 `c51ca28`로 분리 수정하고,
본 브랜치에 `54f85af`로 cherry-pick했다. AA 알고리즘 변경은 없다. 수정 후 장면별 다섯
구성×240프레임, 총 2,400장의 최종 PNG SHA-256이 수정 전과 모두 같음을 확인했다.
이 검증은 두 지정 카메라 경로의 출력 보존이며 모든 실행 조건의 동일성을 보장하지 않는다.
아래 값은 수정된 동일 실행파일 안에서 원본/선택 처리를 다시 측정한 결과다.
이전 브랜치의 프레임 루프·reset·계측 조건이 다른 timing과 직접 비교하지 않는다.

RTX 3060 Ti, DX11, 1920×1061, Ultra, VSync Off, 숨김 창. 장면별 별도 clean process smoke
후 30초 precondition, 300 warm-up, 각 구성 4,800프레임×4회로 정/역 순서를 교차했다.
이미지/마스크 readback은 끄고 timestamp query는 유지했다. 240프레임 경로를 반복하며
회귀 경계마다 history를 reset했다. ⑤와 timing 계측·reset 조건이 달라 그 절대값과 직접 빼지 않는다.

두 구성 모두 원본 공간 SMAA 전체를 실행하므로 이번에는 ④↔⑥을 직접 비교한다.
단위 ms, 4회 run 평균:

| 장면 | 구성 | Camera velocity | 공간 SMAA 세 패스 | Temporal resolve | 전체 AA | WholeFrame GPU |
|---|---|---:|---:|---:|---:|---:|
| Bistro | ④ 원본 SMAA T2X-R | 0.023725 | 0.150803 | 0.033397 | 0.207940 | 2.493567 |
| Bistro | ⑥ SMAA + edge 선택 | 0.023687 | 0.151092 | 0.027855 | 0.202654 | 2.494584 |
| Minecraft | ④ 원본 SMAA T2X-R | 0.023958 | 0.226644 | 0.034977 | 0.285603 | 1.220999 |
| Minecraft | ⑥ SMAA + edge 선택 | 0.023923 | 0.226860 | 0.037932 | 0.288737 | 1.223658 |

| 장면 | Resolve 변화 | 전체 AA 변화 | WholeFrame GPU 변화 | 반복별 전체 AA 변화율 범위 |
|---|---:|---:|---:|---:|
| Bistro | -0.005542 (-16.59%) | -0.005286 (-2.54%) | +0.001018 (+0.04%) | -2.78% ~ -2.26% |
| Minecraft | +0.002954 (+8.45%) | +0.003135 (+1.10%) | +0.002659 (+0.22%) | +0.66% ~ +1.35% |

선택 resolve 차이에는 edge Load·분기·생략한 history/velocity sampling과 계산이 함께 포함된다.
순수 texture 전송 또는 divergence 비용으로 단정하지 않는다. 작은 전체 프레임 차이는
장면 렌더링 및 실행 변동도 포함하며 한 GPU·두 장면의 숨김 창 조건을 넘어 일반화하지 않는다.

반복 산포·꼬리 지연과 wall-clock FPS를 함께 기록했다. p95/p99는 run별 percentile의 평균이며
pooled percentile이 아니다. FPS는 tick 간격의 `1000/mean`; 1% low는 가장 느린 1% 간격 평균의
역수다. 각 표의 FPS도 네 run 값의 평균이며 GPU timestamp 역수와 혼동하지 않는다.

| 장면 | 구성 | AA 평균 ± run 표준편차(ms) | AA p95 / p99(ms) | Wall frame 평균(ms) | 평균 FPS | 1% low FPS |
|---|---|---:|---:|---:|---:|---:|
| Bistro | ④ 원본 | 0.207940 ± 0.000759 | 0.215808 / 0.217856 | 2.907798 | 343.903 | 324.019 |
| Bistro | ⑥ 선택 | 0.202654 ± 0.000317 | 0.208128 / 0.210432 | 2.915271 | 343.023 | 314.569 |
| Minecraft | ④ 원본 | 0.285603 ± 0.000839 | 0.320000 / 0.324864 | 1.230040 | 812.982 | 748.587 |
| Minecraft | ⑥ 선택 | 0.288737 ± 0.000502 | 0.327424 / 0.332544 | 1.232403 | 811.424 | 747.636 |

모든 metric의 mean/median/sample 표준편차/p95/p99, 반복별 평균과 차분은 `*-timings.csv`,
`*-performance.json`에 보존했다. 정지 품질이 나빠진 조건이므로 timing 이득이 있더라도
동등 품질의 최적화 성공이나 논문의 최종 성능 우위로 주장하지 않는다.

## 재현·남은 범위

- [실험 방법](method.md), [소스·DXBC 감사](source-shader-audit.json), [실패/재시도 기록](execution-notes.md)
- `run_spatial_first_edge.ps1 -Phase Capture|BridgeCapture|Smoke|Benchmark -Scene bistro|minecraft`:
  실행 전후 CMAA2=0 검사, timeout 및 완성된 Aggregate PASS 보고서 검증.
- `analyze_spatial_first_edge.py`, `analyze_spatial_first_edge_performance.py`,
  `visualize_spatial_first_edge.py`, `summarize_spatial_first_edge.py`로 재생성한다.
- 각 scene의 capture JSON에 원시 경로·EXE/report hash와 기존 기준선 연결을 기록했다.
  최초 캡처의 실행파일은 `initial-source-shader-audit.json`, 프레임 수정 후 bridge 및
  성능 측정 실행파일은 `source-shader-audit.json`에 각각 대응한다.
  `verify_spatial_frame_bridge.py`와 `*-frame-lifecycle-bridge.json`으로 두 출력을 연결했다.
- `tmp/spatial-first-edge-visuals`에 frame220/221 PNG 및 4 FPS로 느리게 재생한 진단 GIF가 있다.
  변화가 가장 큰 320×320 ROI를 64픽셀 격자에서 선정했으며 원본 1X/④/⑥/edge를 나란히 표시했다.
  공통 256색 palette GIF는 정량 지표에 사용하지 않는다. 좌표와 hash는 `visual-provenance.json`에 있다.
- ①~⑥ 구현 항목은 분리되어 있지만, 동일 조건의 최종 6구성 품질·성능 행렬은 아직 아니다.
  ⑥의 품질 한계를 유지한 채 기록한다. 지터 정책/비선택 출력에 대한 후속 변경은 별도 연구로
  정의해야 하며 이 브랜치에 후보 확장이나 다른 temporal 기법을 누적하지 않는다.
