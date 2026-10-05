# History RGB만 bilinear로 변경한 결과

**최종 품질 해법으로 채택하지 않는다.** ⑨의 선택 조건과 가중치를 그대로 둔 필터 실험은
일부 ROI 오차를 줄였고 추가 비용도 작았다. 그러나 Minecraft 벽의 얇은 선이 약해지고
부분적으로 사라지는 구조 보존 실패가 남았다. 기본 설정은 point 유지, 새 필터는 Off다.
실험 구현·비교·영상 작성은 완료됐지만 연구의 반짝임/선 소실 해결 목표는 미달성이다.

브랜치 `experiment/edge-persistence-bilinear-history-rgb`, 구현 `0be83a7`, 최소 의존성 `9f46c9a`.
검증된 공통 기준선에서 직접 분기했고, 다른 항목의 depth/stencil-ref/실패한 속도
최적화는 가져오지 않았다. 이번 변경은 history **RGB** bilinear 하나이며 point alpha,
adaptive history weight, current+previous raw-edge stencil, spatial-frame history,
Original spatial SMAA와 camera/depth reprojection은 보존했다. 새 렌더링 패스는 없다.

## 동일 실행의 반복 성능

RTX3060Ti, DX11 Release x64, Ultra, 1920×1061, hidden/VSync Off.
장면별 clean process에서 30s precondition, 300 warm-up, 4,800 frame×6회,
정/역순 교차. PNG, diagnostic MRT/query/readback 모두 Off.
전체 AA는 `SMAA` scope, temporal은 `SR_Resolve` scope다. 아래 변화율은 실행별
대응 run의 원본④ 또는 ⑨를 분모로 계산한 평균이다.

| 장면 | 방식 | 전체 AA ms | ④ 대비 | Temporal ms | ④ temporal 대비 |
|---|---|---:|---:|---:|---:|
| Bistro | 원본④ T2X-R | 0.157998 | 기준 | 0.033345 | 기준 |
| Bistro | ⑨ 직전 raw edge + point | 0.135631 | −14.16% | 0.007557 | −77.34% |
| Bistro | 새 구현: ⑨ + RGB bilinear | 0.135835 | −14.03% | 0.007662 | −77.02% |
| Minecraft | 원본④ T2X-R | 0.225537 | 기준 | 0.034786 | 기준 |
| Minecraft | ⑨ 직전 raw edge + point | 0.225728 | +0.09% | 0.023549 | −32.30% |
| Minecraft | 새 구현: ⑨ + RGB bilinear | 0.226307 | +0.34% | 0.023864 | −31.40% |

| 장면 | 새 구현−⑨ 전체 AA 변화 | paired95% 구간 | 새 구현−⑨ temporal 변화 | paired95% 구간 |
|---|---:|---|---:|---|
| Bistro | +0.15% | −0.16…+0.46% | +1.41% | −0.62…+3.45% |
| Minecraft | +0.26% | −0.52…+1.03% | +1.34% | +0.34…+2.34% |

전체 AA의 작은 증가 평균은 반복 변동 구간과 겹친다. Minecraft temporal 증가는 이번
실행의 paired 구간에서0을 제외하지만 단일 process의6 run이다. 여러 세션의 일반화나
다중 비교 보정을 주장하지 않는다. ⑥은 품질 control로 캡처했으며 이번 timing matrix에
넣지 않았다. 다른 실행의⑥ 절대값을 위 표에 혼합하지 않는다.
Spatial+선택, camera, WholeFrame, WallFrame과 p95/p99/run-mean SD 등은 장면별
`benchmark.json`과 `performance-runs.csv`에 보존했다.

## 품질: 보조 수치 개선과 남은 구조 실패

두 장면 각240 frame×4 mode를 캡처했다. 아래는 frame60–179의 화면 고정 ROI 평균이며,
reference는 기존 supersampled **spatial proxy**다. 절대 temporal/ghosting ground truth가 아니다.

| ROI | 원본④ RGB MAE | ⑥ RGB MAE | ⑨ RGB MAE | 새 구현 RGB MAE | 새 구현−⑨ |
|---|---:|---:|---:|---:|---:|
| Bistro chair (1230,582)-(1358,670) | 4.381512 | 5.807495 | 5.684190 | 5.492582 | −3.37% |
| Minecraft seam (956,524)-(1020,620) | 1.626500 | 1.398820 | 1.399701 | 1.265436 | −9.59% |

Minecraft에서는 새 구현의 평균 오차가④보다 작지만, 직접 본 선의 연속성은④에 못 미친다.
이 수치로 품질 우위를 결론내리지 않는다. ④는 paired pattern On, ⑥·⑨·신규는 Off다.
원본과의 차이에 표본 pattern 효과가 포함되고, 필터 자체의 대조는⑨와 새 구현이다.

실제로 full original PNG f131의 네 mode를 두 장면에서 직접 열었다. Nearest2×로
움직임130–135, 전후127–138, 전환178–183, 정지190–195의 좁은 ROI와 넓은 이동 ROI를
나란히 열어 검사했다. 파일/hash·ROI·검사 범위는 `visual-inspection.json`에 기록했다.

- Minecraft f131/f134: 새로운 bilinear 출력에도 벽의 세로 선 상단이 약해지고,
  일부 구간이 배경과 구별되지 않는 단절·소실이 남는다. f127–138의 출현·소멸은
  해결되지 않았다. 이는 작은 선명도 차이가 아닌 **구조 보존 실패**다.
- f131 (971,544)의 RGB는⑨=(142,140,131), 새=(150,148,138)이다. 이 위치에서는
  필터가 선을 더 약하게 만든다. f134 (973,544)는⑨=(156,156,144), 새=(150,149,139)로
  반대 방향이다. 이미 선택된 픽셀의 결과도 일관되게 좋아지는 것은 아니다.
- Bistro f130–135: 의자 다리와 바닥의 급격한 값 변화가 일부 부드러워지지만,
  native④/SS proxy의 세부 구조를 전체적으로 회복하지 못한다. 검사 범위에서
  point→bilinear만으로 선의 구조와 반짝임이 해결됐다고 판단할 근거는 없다.
- 두 장면 f190–239는 새/⑨ RGB가50 frame 전체 동일하다. 정지한 화면의 부족한
  subpixel 표본을 이 필터 변경만으로 되찾지 못했다. 정지 동일성은 이동 품질 성공이 아니다.
- 시간2차 차분은 좁은 ROI에서⑨→신규 Bistro3.311098→3.232228,
  Minecraft2.933147→2.791010이지만 camera motion과 흐림도 포함한다.
  이를 반짝임 자체의 개선율로 표현하지 않는다. CGVQM은 재실행하지 않았다.

현재 검사로 global ghosting 감소, object motion 처리, disocclusion rejection 효과를
확정하지 않는다. ④와의 품질 격차를 sampling/coverage/filter의 어느 하나만으로
모두 설명했다고도 주장하지 않는다.

## 정확성과 계산 모델

- ④·⑥·⑨ 각240 RGB×두 장면=**1,440 control frame mismatch0**.
- ⑨/신규 각43 trace×두 장면에서 raw/current/previous/velocity/edge/coverage/R32 weight
  모두 byte mismatch0. 비선택 RGB=current spatial, 비선택 weight0, 범위`0..0.5` 검사 통과.
- CPU point weight 최대 오차 Bistro5.59e−8 / Minecraft6.33e−8,
  point RGB 최대1 level. 이는 bilinear exact mirror와 다른 검사다.
- Ideal float bilinear CPU 최대 RGB 오차 Bistro3 / Minecraft4 level이었다. 최초 RGB2
  허용치 분석은 실패했다. 입력/가중치/renderer를 수정하지 않고 유한 정밀도 진단과
  별도로 기록했다. 보수적 진단 envelope 밖0이지만 **exact GPU 재현 주장이 아니다**.
  세부 규격과 한계는 `method.md`를 따른다.
- FXC 10 entry/config compile, 기존 point DXBC4개 byte-exact.
  새 production sample 명령은3→4, diagnostic 경로도 중복 색상 읽기 없이 동일4 sample다.
- Release build, short Test, 두 scene Capture/Smoke/Benchmark 완료. 모든 명령은 독립
  clean process로 정상 종료됐으며 원시 경로와 EXE/shader/report SHA는 `runs.json`에 있다.

## 비교 미디어와 후속 판단

로컬 `tmp/edge-bilinear-history-rgb-media`의 두 장면별 PNG sheet, 느린 GIF(25FPS,
frame60–239/7.2s), 정상 MP4(60FPS/3s)를 만들었다. 각 열은④/⑥/⑨/신규다.
GIF는 공통256 palette, MP4는 H.264 보조 자료이며 품질 계산은 original PNG만 썼다.
180 frame, FPS, monotonic PTS, GIF 길이를 decode로 검증했다. **실시간 재생을 시청했다는
주장은 하지 않는다.** 직접 검사한 자료는 위 PNG full/sheet다.

작은 평균 비용 증가로 일부 ROI 수치는 개선될 수 있으나, 이 실험만으로 연구의 품질
목표를 달성하지 못했다. 기본 point 경로를 유지하고 bilinear는 재현 가능한 독립 ablation으로
보존한다. 다음 판단은 선이 약해지는 frame에서 current sample과 history가 실제로
어떤 구조 정보를 갖는지, 선택/필터/혼합 중 어디에서 소실되는지를 더 분리해야 한다.
새 history weight, feedback, jitter나 확장을 이 결과에 섞지 않는다.

## 2026-10-06: ⑩ 품질 평가 보완

사용자 요청에 따라 이번 RGB bilinear 구현을 **⑩**으로 지정했다. 같은 독립 실험
브랜치에서 ④·⑥·⑨·⑩의 원본 PNG 재검증, 전체 화면·ROI 오차 측정, 공식 CGVQM-2
이동·전환 평가와 사용자 비교 GIF를 보완했다. 초기 보고의 CGVQM 미실행 설명은
초기 검사 범위이며, 보완 측정 결과와 제외 실행은 [품질 재평가](quality-review.md)에 있다.
렌더러와 AA 구현은 변경하지 않았다. 채택 여부는 사용자 비교 자료 검토 후 결정한다.
