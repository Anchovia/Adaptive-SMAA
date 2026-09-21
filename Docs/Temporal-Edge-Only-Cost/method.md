# T2X-R 계산을 제거한 edge-only 비용 실험

브랜치 `experiment/temporal-edge-only-cost`, 시작점 `b97d7a0`.
원본 baseline은 보존하고 새 진단 shader에서만 T2X-R 계산을 제거한다.

## 같은 실행에서 비교할 네 조건

1. `O-T2X-R` (0): 기존 원본 resolve.
2. `ABL-EdgeReadOne-R` (56): 직전 실험의 원본 T2X-R + 첫-pass RG Load + runtime-zero sink.
3. `DIAG-OutputOnly` (59): texture 읽기 없이 runtime-zero × 기존 cbuffer RG를 출력.
4. `DIAG-EdgeOnly` (60): 첫-pass RG Load 한 번과 runtime-zero × RG 출력.

59/60은 `float4(scale * RG, 0, 1)`이고 본 timing의 scale은 0이다. 둘 다 같은 검정색을
출력해 색상 내용에 따른 render-target 저장 비용 차이를 통제한다. 읽기 삭제를 막기 위해
scale은 컴파일 상수가 아닌 기존 runtime cbuffer `padding0`를 사용한다.
출력 대조군에도 같은 RG 곱셈이 있으며 raw edge 출력(scale 1)은 capture-only다.

새 두 shader에는 current color, velocity, history texture 읽기, reprojection,
history weight와 blending이 없다. DXBC에서 native sample 수=0, edge-only t8 Load=1,
output-only texture read=0을 검사한다. 원본 shader 8개와 combined 실행 명령은 불변이다.

SMAA spatial 1~3 pass는 edge를 실제로 생성하고 통상적인 cache 상태를 유지하기 위해 남긴다.
camera-velocity 생성과 spatial-frame history ping-pong 역시 upstream에서 유지한다.
따라서 전체 AA가 temporal 계산 제거만큼 가벼워지는지는 보조 계측으로 기록하지만,
검정색을 출력하는 진단을 AA 최적화/품질 보존 결과로 표현하지 않는다.
CPU-side 공통 current/history/velocity SRV 연결 호출도 유지하고, 새 두 mode 모두 t8를 연결한다.
shader가 실제로 읽는 resource와 host의 binding 호출을 구분한다.

## 검증과 해석

- Native/combined는 기존 화면과 hash 일치해야 한다.
- Output-only/edge-only의 zero-scale RGB는 모든 pixel이 0이고 파일 hash가 서로 같아야 한다.
- 같은 edge-only shader에 scale 1을 넣어 실제 edge가 출력되는지 확인하고,
  직전 최적화 실험의 직접 RG diagnostic에서 기록한 edge와 채널별 exact 비교한다.
  이 capture는 timing에서 제외하며 alpha는 PNG에 없으므로 RGB만 검증한다.
- Pattern, viewport, 해상도, 장면, path와 shader helper는 유지한다.
- `EdgeOnly−OutputOnly`는 whole-screen 실행·같은 출력 조건 위에서 읽기 경로의 증분이다.
  좌표/의존성/register/cache와 cbuffer 대조군의 차이를 포함하며 순수 DRAM latency가 아니다.
- `Combined−EdgeOnly`는 전체 shader를 바꾼 비교다. GPU 실행 비용은 단순 가산이 아니므로
  이를 후보 비율에 선형 비례시키거나 선택적 temporal의 미래 속도로 예측하지 않는다.

Bistro/Minecraft, RTX 3060 Ti, DX11, Ultra, 1920×1061 hidden, VSync Off.
240-frame fixed path, 30초 preconditioning, mode별 300 warm-up,
4800-frame × 4회 정순/역순 교차. Fresh process·timeout·PASS 결과·종료를 runner로 검사한다.
Timing에는 PNG/후보 readback/동시 CPU 영상 분석이 없다. 출력은 sparse 10 frame씩 별도 검증한다.
이번 범위는 edge-only 비용 측정까지다. 선택 분기나 품질 변경 구현은 포함하지 않는다.
