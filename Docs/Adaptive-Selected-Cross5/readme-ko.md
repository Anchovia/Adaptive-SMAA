# Adaptive 1% 단계 + 선택 경로 + (c') Cross5 결합

브랜치 `experiment/adaptive-selected-cross5`는 velocity footprint 브랜치의 끝 `74338ff` 위에 `tooling/adaptive-tier-minimal`의 Adaptive 코드 커밋(`4c30ee7`)을 가져와 만든 결합 브랜치다. 사용자가 최종 temporal 후보로 선택 경로 + (c') Cross5를 고른 뒤 Adaptive 1% 단계와 합쳐 품질과 GPU 시간을 쟀다. Footprint12와 19번 변형은 이번 결합에 넣지 않았다. 2026-11-20에 구현, 캡처, 분석, nearest 확대 검사, 시간 측정을 했고 push하지 않았다. `-R`은 계속 camera/depth reprojection만 뜻한다.

## 관련 브랜치

| 브랜치 | 끝 커밋(작성 시점) | 이 브랜치와의 관계 |
|---|---|---|
| `experiment/selected-history-velocity-footprint` | `74338ff` | 이 브랜치의 기반이다. (c') Cross5와 Footprint12, 그 품질·시간 결과가 있다. |
| `tooling/adaptive-tier-minimal` | `644f836` | Adaptive 1% 단계 정리 구현이다. 코드 커밋 `4c30ee7`만 가져왔다. |
| `experiment/selected-history-velocity-pingpong` | `f927d1a` | footprint 브랜치의 기반이다. (c') velocity ping-pong이 있다. |
| `experiment/selected-history-rejection` | `2bbef55` | ping-pong 브랜치의 기반이다. 거르기 (a)(b)(c)가 있다. |
| `baseline/selected-temporal` | `b6c3ebc` | 위 두 줄기의 공통 기준선이다. 선택 경로와 19번이 있다. |
| `experiment/adaptive-tier-validation`, `experiment/adaptive-tier-cost-reduction`, `experiment/adaptive-tier-weights-cost`, `experiment/adaptive-edge-threshold` | `47e1a63`, `7794f0f`, `fb22d4b`, `08e799f` | Adaptive 단계 연구다. 정리 브랜치가 이 넷에서 채택한 변경만 모았다. |

## 기반을 고른 이유

두 줄기는 모두 `baseline/selected-temporal`(b6c3ebc)에서 갈라졌다. Cross5는 거르기, ping-pong, footprint 세 브랜치에 걸친 여러 커밋(velocity 텍스처 두 장의 교대, 19번 표지 값, resolve 진입점, 하니스의 거르기 선택)에 기대어 있다. Adaptive 정리 구현은 코드 커밋 하나(`4c30ee7`, SMAA 폴더 +109/−27)로 끝난다. 그래서 footprint 끝에서 시작해 Adaptive 커밋 하나를 가져오는 쪽이 옮길 코드가 적었다. 하니스도 거르기 선택을 이미 갖고 있어 Original과 Adaptive를 한 프로세스에서 짝지을 수 있다. 코디네이터의 제안과 같다.

이 기반의 단점도 적는다. 이 브랜치에는 이번에 쓰지 않는 거르기 (a)(b)(c), (c'), Keep, Footprint12와 19번 변형이 기본 꺼짐 상태로 함께 있다. 또 거르기 브랜치가 reprojection 상수 버퍼에 더한 `PreviousDepthUnpack` 한 칸도 있다. 결합만 담은 브랜치가 필요하면 기준선에서 Cross5에 필요한 커밋만 골라 다시 만들어야 한다.

## 구현

- `006846c`: `4c30ee7`을 `cherry-pick -x`로 가져왔다. 충돌은 `vaSMAAWrapper.h`의 멤버 선언 두 줄(거르기 선택과 Adaptive 플래그)이 같은 자리에 있던 것 하나뿐이었고 둘 다 남겼다. 변경 크기는 원래 커밋과 같은 +109/−27이다. 넣은 것은 정리 브랜치와 같다. 프리셋별 1% 단계, offset[2] 탐색 끝 좌표 수정, 단계 값 지우기 없음, Adaptive일 때 RGBA8 edge 타깃의 세 번째 채널에 단계를 담는 것이다. Original은 RG8 edge를 그대로 쓴다.
- `0e2817d`: 하니스. 각 mode에 Adaptive 여부를 더하고 캡처 일곱 mode와 시간 측정 다섯 mode를 넣었다. 이 커밋은 셰이더 검사를 준비하던 중 임시 메시지(`wip-harness-for-audit`)와 `--no-verify`로 잘못 만들었다. 내용은 의도한 하니스 변경 그대로다. 이 저장소에는 hook이 없어 건너뛴 검사는 없다. 기존 커밋을 고치지 않는 규칙에 따라 그대로 두었다.
- `536512d`: 셰이더 검사 도구.

Adaptive 여부는 래퍼의 `SetAdaptiveSearch`로 고른다. 값이 바뀌면 SMAA 객체를 다시 만들고 `SMAA_ADAPTIVE_SEARCH` 정의로 셰이더를 다시 컴파일한다. Cross5 resolve는 이 정의를 쓰지 않는다.

## 셰이더 검사 (536512d)

`Tools/SMAA/audit_adaptive_selected_cross5_shaders.py`로 FXC 바이트를 비교했다. 결과는 `fxc-audit.json`에 있다.

| 비교 | 대상 | 결과 |
|---|---|---|
| Original 진입점(SMAA 11개, 선택 경로 11개, 거르기 8개) × 프리셋 4 × reprojection 유무 | footprint 브랜치 `74338ff` | 240/240 같음 |
| Adaptive 진입점(SMAA 11개 × reprojection 유무, 선택 경로 11개 × reprojection) × 프리셋 4 | 정리 브랜치 `644f836` | 116/132 같음, 나머지 16개 설명됨(아래) |
| Cross5 resolve, Adaptive 정의 유무 | 같은 브랜치 | 프리셋 4개 모두 같음 |

다른 16개는 모두 19번의 velocity edge 셰이더(LumaRaw, Luma, Color, Depth × 프리셋 4)였다. 이 셰이더는 reprojection 상수 버퍼를 읽는데, 이 브랜치의 버퍼에는 거르기 브랜치가 더한 `PreviousDepthUnpack` 한 칸이 있다. 정리 브랜치 소스에 같은 칸을 더해 다시 컴파일하자 16개가 모두 같아졌다. 이번 캡처와 측정은 19번을 쓰지 않는다. Release x64 빌드의 경고는 기존 두 개(C4834, C4100)뿐이었다.

## 하니스와 실행

캡처는 한 프로세스에서 일곱 mode를 찍는다. 모두 Ultra다.

| mode | 공간 SMAA | temporal | 이름 |
|---|---|---|---|
| O-1X | Original | 없음(SMAA 1X) | `O-1X` |
| A-1X | Adaptive 1% | 없음(SMAA 1X) | `A-1X` |
| ④ | Original | O-T2X-R | `O-T2X-R` |
| 선택 경로 | Original | 선택 경로 | `ABL-…NoVelocityAlpha` |
| 선택 경로+Cross5 | Original | 선택 경로+(c') Cross5 | `ABL-…NoVelocityAlpha+HistoryVelocityPingPongCross5` |
| A+선택 경로 | Adaptive 1% | 선택 경로 | `A-ABL-…NoVelocityAlpha` |
| A+선택 경로+Cross5 | Adaptive 1% | 선택 경로+(c') Cross5 | `A-ABL-…NoVelocityAlpha+HistoryVelocityPingPongCross5` |

A+선택 경로는 이전 최종 조합(Adaptive 1% RGBA8 + 선택 경로)이다. Smoke와 Benchmark는 O-1X와 A-1X를 뺀 다섯 mode를 잰다. 조건은 이전 실험과 같다(fixed 60 Hz, 정지 60 / 이동 120 / 정지 60프레임, 캡처 warm-up 60, 1920×1061 숨김 창).

| 레이블 | 단계 | 장면 | 보고서 | 결과 |
|---|---|---|---|---|
| `ac` | Capture | Bistro | `20261120_210101` | PASS (21:01–21:04) |
| `ac` | Capture | Minecraft | `20261120_210421` | PASS (21:04–21:07) |

출력 폴더는 `D:\SMAAResearchCaptures\c28`이고 가장 긴 PNG 경로는 236자다. 실행 파일 SHA-256은 `DE4E8DF2…1B02EE`, git head는 `536512d`이고 렌더러 소스 변경은 없었다. 실행 전마다 CMAA2 0개, GPU P8(사용률 0~1%), 게임이나 영상 프로그램 없음을 확인했고 끝난 뒤 남은 CMAA2는 0개였다. 새 PNG는 두 장면 일곱 mode 모두 240장이고 chunk CRC가 맞았다.

## 출력 검증

새 캡처의 PNG를 이전 캡처와 SHA-256으로 비교했다. 두 장면 모두 아홉 쌍이 240/240 같았다.

| 이 브랜치 mode | 비교 대상 | Bistro | Minecraft |
|---|---|---:|---:|
| O-1X, ④, 선택 경로, 선택 경로+Cross5 | footprint 캡처 c27 `fp` | 240/240 (네 mode 모두) | 240/240 (네 mode 모두) |
| A-1X, O-1X | 정리 브랜치 SMAA 1X 캡처 `min-spatial` | 240/240 | 240/240 |
| A+선택 경로, 선택 경로, ④ | 정리 브랜치 temporal 캡처(Bistro `min-r2`, Minecraft `min`) | 240/240 | 240/240 |

정리 브랜치의 두 캡처는 그 브랜치에서 연구 1% RGBA8 캡처(c24-1pE4 `e4`, `tier-in-edges-rgba8`)와 바이트가 같다고 확인한 것이다. 그래서 A-1X와 A+선택 경로는 이전 Adaptive 결과와 출력이 같다. Original 네 mode는 footprint 실험과 같다. 비교 캡처의 경로는 아래 자료에 적었다.

## 품질 결과

잔상 화소는 이전 문서와 같은 정의다. |mode − S| > 24이고 기준 오차가 S보다 24 넘게 큰 화소이며 기준은 SS-Reference(c20-ref)다. 이전 문서와 같이 S는 모든 mode에서 O-1X다. Adaptive mode는 S를 A-1X로 둔 값도 함께 적었다(괄호). A-1X 자체가 O-1X와 조금 다르므로 같은 공간 SMAA의 1X와 비교한 값이 Adaptive의 temporal 잔상에 해당한다. 구간은 이동 f60–179, 이동→정지 f180–209, 정지 f220–239다.

Bistro

| mode | 이동 잔상 평균 / 최대 | 이동 MAE | 이동 PSNR | 이동→정지 잔상 평균 | 정지 MAE |
|---|---:|---:|---:|---:|---:|
| O-1X | 0 / 0 | 0.6926 | 39.688 | 0 | 0.7092 |
| A-1X | 0 / 0 | 0.6921 | 39.688 | 0 | 0.7082 |
| ④ O-T2X-R (참고) | 1,466 / 1,955 | 0.7350 | 40.391 | 842 | 0.5828 |
| 선택 경로 | 2,189 / 2,687 | 0.7218 | 39.300 | 196 | 0.7022 |
| 선택 경로+Cross5 | 612 / 856 | 0.6680 | 40.866 | 18 | 0.7000 |
| A+선택 경로 | 2,189 (2,197) / 2,691 | 0.7206 | 39.307 | 196 (196) | 0.7006 |
| A+선택 경로+Cross5 | 612 (612) / 856 | 0.6663 | 40.880 | 18 (18) | 0.6985 |

Minecraft

| mode | 이동 잔상 평균 / 최대 | 이동 MAE | 이동 PSNR | 이동→정지 잔상 평균 | 정지 MAE |
|---|---:|---:|---:|---:|---:|
| O-1X | 0 / 0 | 1.5174 | 34.779 | 0 | 1.5694 |
| A-1X | 0 / 0 | 1.5174 | 34.773 | 0 | 1.5711 |
| ④ O-T2X-R (참고) | 7,904 / 10,128 | 1.9874 | 34.424 | 3,983 | 1.4717 |
| 선택 경로 | 14,299 / 34,508 | 1.8545 | 33.873 | 622 | 1.5715 |
| 선택 경로+Cross5 | 2,421 / 5,027 | 1.5543 | 35.970 | 90 | 1.5308 |
| A+선택 경로 | 14,339 (14,288) / 34,486 | 1.8533 | 33.876 | 695 (617) | 1.5726 |
| A+선택 경로+Cross5 | 2,468 (2,418) / 5,027 | 1.5530 | 35.974 | 168 (90) | 1.5322 |

A-1X를 기준으로 세면 Adaptive를 넣어도 잔상 화소 수는 같은 경로의 Original과 거의 같았다. Cross5는 Adaptive에서도 이동 잔상 평균을 Bistro 2,197 → 612, Minecraft 14,288 → 2,418로 줄였다. Original에서는 2,189 → 612, 14,299 → 2,421이었다. 이동 MAE도 Cross5로 0.7206 → 0.6663, 1.8533 → 1.5530만큼 줄어 Original의 0.7218 → 0.6680, 1.8545 → 1.5543과 같은 폭이다.

O-1X를 기준으로 셀 때 Minecraft Adaptive mode에 더 잡히는 화소(이동 +40~47, 이동→정지 +73~78, 정지 +77~78)는 A-1X 자체가 O-1X와 다른 화소다. 정지 f230에서 A-1X가 O-1X보다 기준에서 24 넘게 먼 화소는 77개였고 반대는 23개였다. 대부분 물과 풀 사이의 길고 거의 수평인 경계(x 940–1040, y 약 750) 근처에 모였다. 6배 확대에서는 O-1X와 구분하기 어려웠다. Adaptive의 짧아진 탐색이 긴 경계의 AA 기울기를 조금 바꾼 것으로, Adaptive 단계 연구에서 본 것과 같은 성질이고 Cross5와는 관계가 없다.

출력 차이는 디코딩한 RGB의 채널 최대 차이로 쟀다(다른 화소 비율 / 8 넘게 다른 화소 비율 / 최대 차이).

| 비교 | 장면 | 이동 | 이동→정지 | 정지 |
|---|---|---|---|---|
| A-1X vs O-1X | Bistro | 0.40% / 0.014% / 65 | 0.37% / 0.017% / 45 | 0.37% / 0.017% / 45 |
| A-1X vs O-1X | Minecraft | 0.41% / 0.045% / 136 | 0.41% / 0.047% / 85 | 0.41% / 0.047% / 85 |
| A+선택 경로 vs 선택 경로 | Bistro | 0.67% / 0.006% / 55 | 0.44% / 0.013% / 41 | 0.42% / 0.014% / 41 |
| A+선택 경로 vs 선택 경로 | Minecraft | 0.85% / 0.028% / 89 | 0.53% / 0.043% / 82 | 0.49% / 0.046% / 82 |
| A+선택 경로+Cross5 vs 선택 경로+Cross5 | Bistro | 0.65% / 0.006% / 55 | 0.44% / 0.014% / 41 | 0.43% / 0.014% / 41 |
| A+선택 경로+Cross5 vs 선택 경로+Cross5 | Minecraft | 0.77% / 0.031% / 89 | 0.50% / 0.045% / 82 | 0.48% / 0.046% / 82 |
| 선택 경로+Cross5 vs 선택 경로 | Bistro | 2.68% / 0.281% / 130 | 2.24% / 0.081% / 109 | 2.05% / 0.000% / 6 |
| 선택 경로+Cross5 vs 선택 경로 | Minecraft | 16.66% / 1.579% / 141 | 18.43% / 0.271% / 138 | 17.90% / 0.000% / 6 |
| A+선택 경로+Cross5 vs A+선택 경로 | Bistro | 2.70% / 0.284% / 130 | 2.23% / 0.081% / 109 | 2.04% / 0.000% / 6 |
| A+선택 경로+Cross5 vs A+선택 경로 | Minecraft | 16.67% / 1.580% / 141 | 18.43% / 0.272% / 138 | 17.89% / 0.000% / 6 |

Adaptive가 같은 경로에서 바꾸는 화소는 0.4~0.9%이고 Cross5가 바꾸는 화소는 2~18%다. Cross5가 바꾸는 비율은 Original과 Adaptive에서 거의 같았다(Bistro 이동 2.68%와 2.70%, Minecraft 16.66%와 16.67%).

지정된 ROI의 값은 아래와 같다(기준 MAE / 잔상 화소 / 프레임 간 변화, 잔상은 O-1X 기준).

| ROI, 프레임 | 선택 경로 | 선택 경로+Cross5 | A+선택 경로 | A+선택 경로+Cross5 | O-1X | A-1X |
|---|---|---|---|---|---|---|
| Minecraft 나뭇잎 (7,718)-(135,806), f85–95 | 17.72 / 2,855 / 10.35 | 3.85 / 18 / 10.35 | 17.72 / 2,855 / 10.35 | 3.85 / 18 / 10.35 | 4.60 / 0 / 11.59 | 4.60 / 0 / 11.59 |
| Minecraft 왼쪽 (0,96)-(96,144), f116–125 | 8.73 / 774 / 9.66 | 1.01 / 0 / 10.36 | 8.73 / 774 / 9.66 | 1.01 / 0 / 10.36 | 0.84 / 0 / 10.60 | 0.84 / 0 / 10.60 |
| Minecraft 이음매 (956,524)-(1020,620), f126–131 | 1.26 / 1.8 / 1.87 | 1.21 / 0.7 / 1.91 | 1.25 / 1.8 / 1.88 | 1.22 / 0.7 / 1.92 | 1.46 / 0 / 2.43 | 1.52 / 0 / 2.43 |
| Minecraft 이음매, 이동 f60–179 | 1.37 / 15.4 / 2.56 | 1.27 / 0.4 / 2.61 | 1.36 / 15.4 / 2.57 | 1.27 / 0.4 / 2.61 | 1.47 / 0 / 3.09 | 1.48 / 0 / 3.10 |
| Bistro 창틀 (946,466)-(1074,554), f120–125 | 9.93 / 1,084 / 6.60 | 6.75 / 338 / 6.93 | 9.93 / 1,084 / 6.60 | 6.75 / 338 / 6.93 | 7.11 / 0 / 8.26 | 7.11 / 0 / 8.26 |
| Bistro 의자 다리 (1230,582)-(1358,670), f120–125 | 5.34 / 22 / 2.06 | 5.26 / 12 / 2.22 | 5.34 / 22 / 2.06 | 5.26 / 12 / 2.23 | 6.15 / 0 / 3.24 | 6.15 / 0 / 3.24 |
| Bistro 의자 다리, 이동 f60–179 | 5.22 / 18 / 1.96 | 5.19 / 7 / 2.11 | 5.22 / 18 / 1.96 | 5.18 / 7 / 2.11 | 6.04 / 0 / 3.13 | 6.04 / 0 / 3.13 |

Adaptive temporal mode의 ROI 값은 같은 경로 Original과 기준 MAE와 프레임 간 변화가 ±0.01 안이었고 잔상 화소는 같았다.

## 1px 선 열 검사

footprint 문서에서 (c')의 1px 선이 있던 다섯 열을 다시 쟀다. 값은 그 열의 행들에 대한 |mode − 같은 공간 SMAA의 1X| 채널 최대 차이의 평균이다(Original mode는 O-1X, Adaptive mode는 A-1X). 0.0은 그 열이 1X와 같다는 뜻이다.

| 열, 프레임 | 선택 경로 | 선택 경로+Cross5 | A+선택 경로 | A+선택 경로+Cross5 |
|---|---:|---:|---:|---:|
| x97 f119 | 69.2 | 0.0 | 69.0 | 0.0 |
| x64 f120 | 71.8 | 0.0 | 71.3 | 0.0 |
| x64 f121 | 25.7 | 1.0 | 25.6 | 1.0 |
| x30 f121 | 65.6 | 0.0 | 65.6 | 0.0 |
| x30 f122 | 30.8 | 1.3 | 30.8 | 1.3 |
| x30 f124 | 18.3 | 2.4 | 18.2 | 2.4 |
| x32 f87 (나뭇잎) | 100.5 | 0.0 | 100.5 | 0.0 |
| x32 f88 | 68.1 | 12.1 | 68.1 | 12.1 |
| x110 f86 (나뭇잎) | 109.5 | 0.0 | 109.5 | 0.0 |
| x110 f87 | 66.7 | 5.9 | 66.7 | 5.9 |

A+선택 경로+Cross5는 다섯 열 모두 선택 경로+Cross5와 같은 값이었다. 선이 생기던 프레임에서 그 열은 A-1X와 같았고 다음 프레임부터는 footprint 문서의 (c) 수준이었다. 선택 경로와 A+선택 경로의 큰 값은 거르기 없는 선택 경로에 남는 벽 색 얼룩이다.

## 직접 본 내용

원본 PNG를 nearest로 확대해 보았다. 열은 O-1X, A-1X, 선택 경로, 선택 경로+Cross5, A+선택 경로, A+선택 경로+Cross5, SS-Reference다. Bistro는 어두워서 밝기를 2~3배 올린 확대본(진단용)으로 보았고 Minecraft는 색을 바꾸지 않았다. 이동, 이동→정지, 정지 구간마다 6프레임 이상 보았다.

- Minecraft 왼쪽 x20–76, f119–126(6배): 선택 경로와 A+선택 경로는 드러난 흙 위에 벽 색 점무늬와 x30, x64 열의 선이 f120–126 동안 남았다. 두 Cross5 mode는 O-1X, A-1X와 같이 깨끗했고 1px 선도 없었다.
- Minecraft 나뭇잎 (7,730)-(135,800), f85–90(3배): 같은 모습이었다. 선택 경로와 A+선택 경로는 벽 색 점무늬가 f90까지 남았고 두 Cross5 mode에는 점무늬와 x110(f86), x32(f87–88) 선이 없었다. 정지 f230–235는 mode 사이 차이가 없었다.
- Minecraft 이음매 f126–131(5배)과 이동→정지 f178–183(4배): 네 temporal mode 모두 위아래로 이어진 옅은 선을 유지했다. O-1X와 A-1X는 짧은 조각이 프레임마다 자리를 바꿨다. Adaptive를 넣어도 이음매 모습은 같은 경로의 Original과 같았다.
- Bistro 의자 다리 f120–125(5배), f178–183(3배): 두 Cross5 mode의 다리는 선택 경로처럼 이어졌고 조각나지 않았다. Adaptive 쪽은 같은 경로 Original과 구분되지 않았다.
- Bistro 창틀 f120–125(2배, 4배): 네 temporal mode 모두 큰 결함은 없었다. A+선택 경로+Cross5는 선택 경로+Cross5와 구분되지 않았다.
- Minecraft 물가 경계 f230–232(6배): 위에 적은 A-1X와 O-1X의 차이 위치다. 길고 거의 수평인 물·풀 경계에서 두 1X의 계단 모양이 조금 달랐지만 확대해도 구분하기 어려웠고, 두 Cross5 mode도 각자의 1X와 같은 모습이었다.

## 시간 측정

사용자가 이번 결합 작업의 측정을 허락했다. 조건은 이전 측정과 같다. 같은 실행 파일(DE4E8DF2)로 장면마다 Smoke 다음 Benchmark를 독립 clean process로 돌렸다. Benchmark는 30초 대기와 warm-up 300프레임 뒤 4,800프레임씩 6회 재며 반복마다 mode 순서를 정방향과 역방향으로 바꾼다. 숨김 창이라 engineering 분류다. RTX 3060 Ti, 드라이버 621.14, 1920×1061이다. 대괄호는 반복 6회의 95% 구간이다.

| 레이블 | 단계 | 장면 | 보고서 | 결과 |
|---|---|---|---|---|
| `ac-smoke` | Smoke | Bistro | `20261120_211014` | PASS (40초) |
| `ac-smoke` | Smoke | Minecraft | `20261120_211104` | PASS (35초) |
| `ac-bench` | Benchmark | Bistro | `20261120_211149` | PASS (476초) |
| `ac-bench` | Benchmark | Minecraft | `20261120_211955` | PASS (214초) |

실행 전마다 CMAA2 0개, GPU P8(사용률 0~2%), 게임이나 영상 프로그램 없음, 60초 이상 키보드·마우스 입력 없음을 확인했다. 네 실행 모두 실행 중 입력이 없어 다시 잰 것은 없다. 끝난 뒤 남은 CMAA2는 0개였다.

Bistro AA(SMAA) 시간

| mode | AA 시간 (µs) | ④ 대비 | 같은 경로 Original 대비 (Adaptive 효과) | 같은 공간 SMAA의 Cross5 없는 경로 대비 (Cross5 비용) |
|---|---:|---:|---:|---:|
| ④ O-T2X-R | 157.27 | | | |
| 선택 경로 | 127.95 | −18.64% [−18.91, −18.37] | | |
| 선택 경로+Cross5 | 129.91 | −17.40% [−17.76, −17.03] | | +1.53% [+1.36, +1.69] |
| A+선택 경로 | 119.66 | −23.92% [−24.16, −23.67] | −6.49% [−6.60, −6.37] | |
| A+선택 경로+Cross5 | 121.67 | −22.64% [−23.07, −22.20] | −6.34% [−6.56, −6.13] | +1.68% [+1.26, +2.11] |

Minecraft AA(SMAA) 시간

| mode | AA 시간 (µs) | ④ 대비 | 같은 경로 Original 대비 (Adaptive 효과) | 같은 공간 SMAA의 Cross5 없는 경로 대비 (Cross5 비용) |
|---|---:|---:|---:|---:|
| ④ O-T2X-R | 226.01 | | | |
| 선택 경로 | 222.28 | −1.65% [−2.39, −0.90] | | |
| 선택 경로+Cross5 | 229.88 | +1.71% [+1.55, +1.88] | | +3.42% [+2.61, +4.23] |
| A+선택 경로 | 211.30 | −6.51% [−7.30, −5.71] | −4.94% [−5.12, −4.77] | |
| A+선택 경로+Cross5 | 219.05 | −3.08% [−3.27, −2.89] | −4.71% [−4.80, −4.62] | +3.67% [+2.81, +4.54] |

이전 측정과 겹치는 값은 다시 맞았다. 선택 경로의 ④ 대비는 −18.64% / −1.65%(footprint 측정 −18.83% / −1.42%), 선택 경로+Cross5의 선택 경로 대비는 +1.53% / +3.42%(+1.62% / +3.36%)였다.

전체 프레임(WholeFrame)은 Bistro 2.38~2.42 ms, Minecraft 1.14~1.16 ms다. A+선택 경로+Cross5는 ④ 대비 Bistro −1.68% [−1.98, −1.39], Minecraft −0.41% [−0.53, −0.29]이고, 선택 경로+Cross5 대비 −0.36% [−0.57, −0.15], −0.92% [−1.12, −0.72]이며, A+선택 경로 대비 +0.01% [−0.26, +0.28], +0.71% [+0.49, +0.93]이다.

늘어나거나 줄어든 시간을 범위별로 나누면 아래와 같다(µs, 대괄호는 95% 구간). 범위 밖은 SMAA 전체에서 카메라 velocity, 공간 SMAA, resolve를 뺀 값이다.

| 장면 | 비교 | 공간 SMAA | resolve | 카메라 velocity | 범위 밖 |
|---|---|---:|---:|---:|---:|
| Bistro | A+선택 경로 vs 선택 경로 | −8.75 [−8.92, −8.59] | +0.06 [−0.07, +0.18] | +0.40 [+0.35, +0.44] | 0.00 |
| Bistro | A+선택 경로+Cross5 vs 선택 경로+Cross5 | −8.60 [−8.69, −8.50] | −0.03 [−0.31, +0.25] | +0.38 [+0.34, +0.42] | 0.00 |
| Bistro | 선택 경로+Cross5 vs 선택 경로 | −0.11 [−0.39, +0.17] | +2.06 [+1.96, +2.17] | 0.00 [−0.03, +0.03] | 0.00 |
| Bistro | A+선택 경로+Cross5 vs A+선택 경로 | +0.05 [−0.21, +0.31] | +1.98 [+1.77, +2.19] | −0.02 [−0.09, +0.06] | 0.00 |
| Bistro | A+선택 경로+Cross5 vs ④ | −12.83 [−13.38, −12.28] | −23.16 [−23.63, −22.69] | +0.38 [+0.32, +0.45] | 0.00 |
| Minecraft | A+선택 경로 vs 선택 경로 | −11.01 [−11.31, −10.71] | −0.02 [−0.10, +0.06] | +0.04 [−0.01, +0.09] | 0.00 |
| Minecraft | A+선택 경로+Cross5 vs 선택 경로+Cross5 | −10.98 [−11.18, −10.77] | +0.09 [−0.05, +0.24] | +0.05 [+0.02, +0.08] | 0.00 |
| Minecraft | 선택 경로+Cross5 vs 선택 경로 | +0.21 [−1.15, +1.57] | +7.35 [+6.94, +7.77] | +0.03 [−0.01, +0.08] | 0.00 |
| Minecraft | A+선택 경로+Cross5 vs A+선택 경로 | +0.25 [−1.25, +1.74] | +7.47 [+7.17, +7.77] | +0.04 [+0.01, +0.07] | 0.00 |
| Minecraft | A+선택 경로+Cross5 vs ④ | −7.97 [−8.14, −7.79] | +0.91 [+0.57, +1.25] | +0.10 [+0.06, +0.14] | 0.00 |

범위 밖의 0.00은 −0.01~+0.01 µs다. Adaptive는 공간 SMAA를 Bistro 8.6~8.8 µs, Minecraft 11.0 µs 줄였고 resolve에는 영향이 없었다. Cross5는 resolve를 Bistro 2.0~2.1 µs, Minecraft 7.4~7.5 µs 늘렸고 공간 SMAA에는 영향이 없었다. 두 효과는 서로 다른 범위에서 나와 거의 그대로 더해졌다. Bistro에서 Adaptive mode의 카메라 velocity가 0.4 µs 늘었는데 원인은 확인하지 않았다.

Minecraft에서는 선택 경로+Cross5가 ④보다 1.71% 느렸지만 Adaptive를 더하면 ④보다 3.08% 빨라졌다. Adaptive가 줄인 공간 SMAA 11.0 µs가 Cross5가 늘린 resolve 7.5 µs보다 크기 때문이다.

## 정리

채택 여부는 사용자가 정한다. 확인한 사실만 적는다.

- Adaptive 1% 단계와 선택 경로+(c') Cross5를 한 브랜치에 합쳤다. Original 셰이더는 footprint 브랜치와 240/240 바이트가 같았다. Adaptive 셰이더는 정리 브랜치와 116/132가 같았고, 나머지 16개(19번 velocity edge)는 상수 버퍼의 한 칸 차이로 설명되었다. 출력은 Original 네 mode가 footprint 캡처와, A-1X와 A+선택 경로가 정리 브랜치 캡처와 두 장면 240/240 같았다.
- Adaptive를 넣어도 Cross5의 효과는 같았다. 다섯 1px 선 열은 A+선택 경로+Cross5에서도 선이 생기던 프레임에 A-1X와 같았다. A-1X 기준 잔상 화소는 Bistro 612, Minecraft 2,418로 Original+Cross5(612, 2,421)와 같은 수준이었고, 나뭇잎과 왼쪽 얼룩도 똑같이 사라졌다. 얇은 선(이음매, 의자 다리)은 Original처럼 유지되었다.
- A+선택 경로+Cross5의 AA 시간은 ④ 대비 Bistro −22.64%, Minecraft −3.08%였다. 같은 경로 Original(선택 경로+Cross5) 대비 −6.34% / −4.71%, Cross5 없는 A+선택 경로 대비 +1.68% / +3.67%다.
- 이전 최종 조합 A+선택 경로(④ 대비 −23.92% / −6.51%)보다 Bistro 1.68%, Minecraft 3.67% 느리다. 그 대신 Minecraft 이동 잔상 화소를 14,288에서 2,418로, 나뭇잎 ROI 기준 MAE를 17.72에서 3.85로 줄였다.
- Adaptive가 바꾸는 화소는 A-1X와 O-1X처럼 화면의 0.4~0.9%이고, Minecraft 물가의 긴 수평 경계에 일부 모였다. 확대해도 구분하기 어려웠다.

## 자료

- 캡처: `D:/SMAAResearchCaptures/c28/ac/capture/bistro/20261120_210101`, `D:/SMAAResearchCaptures/c28/ac/capture/minecraft/20261120_210421`
- 비교한 이전 캡처: footprint `D:/SMAAResearchCaptures/c27/fp/capture/{bistro/20261120_165626, minecraft/20261120_170128}`, 정리 브랜치 temporal `D:/SMAAResearchCaptures/c24-minimal/min-r2/capture/bistro/20261119_214900`, `D:/SMAAResearchCaptures/c24-minimal/min/capture/minecraft/20261119_213505`, 정리 브랜치 1X `D:/SMAAResearchCaptures/c24-minimal/min-spatial/spatial/{bistro/20261119_213752, minecraft/20261119_214145}`
- 수치: 이 폴더의 `quality-*.json`(요약과 열 검사, 프레임별 값은 `D:/SMAAResearchCaptures/c28/analysis/`), `roi-*.json`, `timing.json`(Benchmark), `timing-smoke.json`(Smoke), `fxc-audit.json`, `runs.json`
- 시트: `D:/SMAAResearchCaptures/c28/sheets/`(원본 PNG nearest 확대, 색 보정 없음. `*-ghost-map-*.png`만 1/2 크기 오버레이). 확대 검사본은 `D:/SMAAResearchCaptures/c28/sheets/zoom/`(`v_ac_*.png`, 만든 스크립트 `ac_zoom.py`)이며 제목에 밝기 배율이 적힌 것은 진단용이다.
- 도구: `Tools/SMAA/audit_adaptive_selected_cross5_shaders.py`, `Tools/SMAA/analyze_adaptive_selected_cross5.py`, `Tools/SMAA/adaptive_selected_cross5_roi_sheets.py`, `Tools/SMAA/analyze_adaptive_selected_cross5_timing.py`
