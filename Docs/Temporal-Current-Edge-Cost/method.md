# 현재 spatial 색상 출력에서의 첫-pass edge 읽기 비용

브랜치 `experiment/temporal-current-edge-cost`, 시작점 `4ea2422`.
검은 화면을 출력했던 직전 진단과 구분하여 실제 현재 색상을 읽고 출력하는 비용을 측정한다.
Original 공간 처리, camera/depth reprojection On 경로, paired jitter, spatial-frame history를
그대로 유지한다. Object motion은 포함하지 않는다. 최종 8-case가 아닌 engineering ablation이다.

## 네 비교군

| Mode | Kind | Shader 작업 |
|---|---:|---|
| O-T2X-R | 0 | 기존 원본 temporal resolve |
| ABL-EdgeReadOne-R | 56 | 기존 원본 resolve + 실제 첫-pass RG Load + runtime-zero sink |
| DIAG-CurrentOutput | 61 | 현재 spatial color Point 읽기 + cbuffer RG runtime-zero sink |
| DIAG-CurrentEdge | 62 | 같은 현재 color 읽기 + 실제 첫-pass RG Load + runtime-zero sink |

새 두 shader는 `current.rg += padding0 * value`를 사용하고 BA는 그대로 출력한다.
본 측정에서 padding0=0, 대조군의 value는 기존 subsampleIndices.xy,
edge군의 value는 기존 RG8 edge texture의 현재 pixel RG다.
scale은 runtime cbuffer여서 FXC가 읽기를 제거할 수 없다.
61은 순수 복사에 matched sink를 더한 대조군이며 그 산술 비용까지 0이라고 주장하지 않는다.
둘 다 t8을 연결하며 같은 target/fullscreen draw를 사용한다. 새 pass/texture/copy는 없다.

새 두 shader에서 velocity/history texture 읽기, 재투영 좌표 계산, history weight와
blending만 빠진다. 앞선 spatial 세 pass, camera velocity 생성, history ping-pong 및
공통 CPU-side resource binding은 남긴다. jitter가 남으므로 current-only는 안정화된 T2X가 아니다.

## 검증

- Native spatial/resolve 8개 DXBC 및 기존 combined 명령을 변경 전과 비교한다.
- 새 shader에 current t2 Point 읽기 1회, edge군에만 t8 Load 1회가 있고 t4/t7 읽기와 분기가 없는지 확인한다.
- Capture-only 기존 kind 3 current spatial 출력을 기준으로 61/62의 RGB PNG hash를 비교한다.
- Native는 역사적 같은 경로 capture와 hash bridge, combined는 native와 hash 비교한다.
- Capture-only 기존 kind 60 scale 1의 raw edge RG를 이전 직접 RG 진단과 exact 비교한다.
- 실제 새 kind 62 scale 1도 캡처하여 edge 채널 이외에는 변화가 없고, 양수 edge 기여가 출력에 남는지 확인한다.
  양자화/포화 때문에 모든 edge 채널이 반드시 바뀌어야 한다고 요구하지 않는다.
- PNG는 RGB만 저장하므로 alpha의 GPU 출력 동일성을 PNG로 검증했다고 표현하지 않는다.

## 측정 및 해석

Bistro/Minecraft, RTX 3060 Ti, DX11, Ultra, 1920×1061 hidden, VSync Off.
240-frame fixed path (60 still + 120 move + 60 still), 30초 precondition,
mode별 300 warm-up, 4,800 frame × 4회 정순/역순 교차. Smoke는 240 frame × 1회다.
Fresh process, timeout, 완성된 PASS report 및 잔류 프로세스 0을 clean runner로 확인한다.
Timing 중 PNG 저장/후보 readback/CPU 영상 분석은 하지 않는다.

`CurrentEdge−CurrentOutput`은 현재 색상을 출력할 때의 edge access 증분이며,
`Combined−Native`는 T2X-R에 edge access 및 sink를 추가한 증분이다.
전자는 matched sink, 후자는 원본 자체가 기준이므로 sink 통제 수준도 다르다.
서로 다른 shader의 좌표/의존성/register/cache 차이를 포함하며 순수 메모리 전송 지연이 아니다.
후보 비율로 선형 축소하거나 선택 분기를 추가한 미래 성능으로 예측하지 않는다.
이번 범위에는 후보 선택, 품질 개선, Adaptive 결합이나 확장 옵션이 없다.
