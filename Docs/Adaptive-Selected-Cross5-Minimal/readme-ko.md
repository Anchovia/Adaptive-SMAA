# Adaptive 1% 단계 + 선택 경로 + (c') Cross5 정리 브랜치

브랜치 `tooling/adaptive-selected-cross5-minimal`은 `baseline/selected-temporal`(b6c3ebc)에서 분기했다. 최종 조합으로 추천된 Adaptive 1% 단계 + 선택 경로 + (c') Cross5에 필요한 코드만 기준선 위에 넣은 정리 구현이다. 결합 브랜치 `experiment/adaptive-selected-cross5`에 함께 있던 거르기 (a)(b)(c), (c'), Keep, Footprint12, 19번 변형과 `PreviousDepthUnpack` 칸은 넣지 않았다. 2026-11-20에 만들었고 push하지 않았다. `-R`은 계속 camera/depth reprojection만 뜻한다.

## 관련 브랜치

| 브랜치 | 끝 커밋(작성 시점) | 이 브랜치와의 관계 |
|---|---|---|
| `baseline/selected-temporal` | `b6c3ebc` | 이 브랜치의 기반이다. ④, 선택 경로, 19번 기준선이다. |
| `tooling/adaptive-tier-minimal` | `644f836` | Adaptive 1% 단계 정리 구현이다. 코드 커밋 `4c30ee7`과 하니스 커밋 `a3e4b01`을 가져왔다. |
| `experiment/adaptive-selected-cross5` | `c55db4f` | 같은 조합의 결합 브랜치다. 출력과 시간 결과의 비교 대상이다. |
| `experiment/selected-history-velocity-footprint` | `74338ff` | (c') Cross5가 처음 만들어진 곳이다. 이 브랜치의 Cross5 코드는 여기서 필요한 부분만 다시 썼다. |
| `experiment/selected-history-velocity-pingpong`, `experiment/selected-history-rejection` | `f927d1a`, `2bbef55` | (c') velocity ping-pong과 거르기 (a)(b)(c)의 연구 기록이다. |
| `experiment/adaptive-tier-validation`, `experiment/adaptive-tier-cost-reduction`, `experiment/adaptive-tier-weights-cost`, `experiment/adaptive-edge-threshold` | `47e1a63`, `7794f0f`, `fb22d4b`, `08e799f` | Adaptive 단계 연구다. |
| `tooling/selected-temporal-minimal` | `5348c42` | 선택 경로 정리 구현이다. |

## 넣은 것

| 커밋 | 내용 |
|---|---|
| `f73bdee` | `4c30ee7`(Adaptive 코드)을 `cherry-pick -x`로 가져왔다. 충돌은 없었다. 프리셋별 1% 단계, offset[2] 탐색 끝 좌표 수정, 단계 값 지우기 없음, Adaptive일 때 RGBA8 edge 타깃의 세 번째 채널에 단계를 담는 것이다. |
| `76e4642` | `a3e4b01`(Adaptive 하니스와 SpatialCapture 단계)을 `cherry-pick -x`로 가져왔다. 충돌은 없었다. 이 두 커밋까지의 SMAA 폴더와 하니스는 `644f836`과 같다. |
| `ae8c0d1` | (c') Cross5. 아래에 설명한다. |
| `4888e2f`, `394cb0b` | 하니스에 선택 경로+Cross5를 Original과 Adaptive로 더했다. `4888e2f`는 보고서 문자열 안의 세미콜론에서 치환이 잘려 뒷부분이 한 번 더 붙은 채 커밋되어 컴파일되지 않았다. `394cb0b`에서 고쳤다. 기존 커밋을 고치지 않는 규칙에 따라 두 커밋을 그대로 두었다. |

Cross5(`ae8c0d1`)에 넣은 것은 다음 네 가지뿐이다.

- `SelectedTemporal.hlsl`: 이전 velocity 텍스처(t12)와 resolve 진입점 `SelectedResolveVelocityCross5PS`. 비중은 공식 SMAA reprojection 식 0.8 × saturate(1 − sqrt(| |v| − |v_prev| |) × 30)이다. v_prev는 history 위치 아래 texel과 상하좌우 네 이웃의 이전 velocity 가운데 현재 속도와 크기 차이가 가장 큰 값이다. 좌표는 history 샘플러처럼 텍스처 범위로 자른다.
- `SMAA.cpp`/`SMAA.h`: Cross5 technique 하나와 `resolveSelected`의 `previousVelocity` 인자. 인자가 있으면 t12에 묶고 Cross5 resolve를 쓴다. seed 프레임에는 쓰지 않는다.
- `vaSMAAWrapperDX11.cpp`: 이전 velocity 텍스처 한 장. 처음 쓰거나 크기가 바뀌면 만들고 그 프레임은 seed로 시작한다. resolve 뒤에 현재 velocity 텍스처와 맞바꾼다. `CleanupTemporaryResources`에서 비운다.
- `vaSMAAWrapper.h`: 스위치 `SetSelectedCross5(bool)`/`GetSelectedCross5()`. 값이 바뀌면 history를 지운다. 비교를 위해 선택 경로를 Cross5 없이 돌릴 수 있게 남긴 최소 스위치다.

연구 버전과 다른 점은 셰이더 두 군데다. 19번용 '모르는 이전 velocity' 검사(표지 값 1024)를 뺐다. 선택 경로는 카메라 velocity 패스가 매 프레임 모든 화소를 쓰므로 이 검사가 참이 되는 일이 없다. 또 거르기 공용 함수(`SelectedBlend`, `SelectedPreviousSpeedDelta`) 없이 blend를 진입점 안에 풀어 썼고 다섯 texel은 반복문으로 읽는다. 계산 순서와 식은 같다.

19번은 기준선 코드 그대로 두었다. 19번에서 Cross5를 켜면 오류를 내고 그리지 않는다. 19번은 velocity를 남는 화소에만 쓰므로 Cross5를 붙이려면 매 프레임 velocity 타깃을 표지 값으로 지우는 clear와 표지 값 검사가 더 필요하다. footprint 실험에서 그 clear는 1.7~1.9 µs였고, 그렇게 붙여도 드러난 첫 1~2프레임의 얼룩이 남고 이음매의 O-1X 조각 무늬가 일부 돌아왔다. 그래서 코디네이터의 제안대로 넣지 않았다.

## 셰이더 검사

`Tools/SMAA/audit_adaptive_selected_cross5_minimal_shaders.py`로 FXC 바이트를 비교했다(`fxc-audit.json`). SMAA 진입점 11개는 reprojection 유무, 선택 경로 진입점 11개는 reprojection만, 모두 Original과 Adaptive × 프리셋 4개로 컴파일했다.

| 비교 대상 | 결과 |
|---|---|
| Adaptive 정리 브랜치 `644f836` | 264/264 같음 |
| 결합 브랜치 `c55db4f` (Cross5 resolve 포함) | 232/272 같음 |

결합 브랜치와 다른 40개는 두 가지다. 하나는 19번 velocity edge 셰이더 4종(× Original/Adaptive × 프리셋 4 = 32개)으로, 결합 브랜치의 reprojection 상수 버퍼에만 있는 `PreviousDepthUnpack` 칸 때문이다. 이 셰이더는 정리 브랜치와는 같다. 다른 하나는 Cross5 resolve(8개)로, 위에 적은 대로 다시 썼기 때문이다. 그 밖의 진입점은 모두 같았다. Release x64 빌드의 경고는 기존 두 개(C4834, C4100)뿐이었다.

## 출력 검증

이 브랜치의 실행 파일(SHA-256 `6E869E8A…0FC4AE`, git head `394cb0b`, 렌더러 소스 변경 없음)로 장면마다 temporal 캡처(Capture)와 SMAA 1X 캡처(SpatialCapture)를 독립 clean process로 찍었다. 조건은 이전과 같다(Ultra, fixed 60 Hz, 정지 60 / 이동 120 / 정지 60프레임, warm-up 60, 1920×1061 숨김 창). 출력 폴더는 `D:\SMAAResearchCaptures\c29`이고 가장 긴 PNG 경로는 237자다.

| 레이블 | 단계 | 장면 | 보고서 | 결과 |
|---|---|---|---|---|
| `acm` | Capture | Bistro | `20261120_234106` | PASS (23:41–23:44) |
| `acm` | Capture | Minecraft | `20261120_234452` | PASS (23:44–23:48) |
| `acm-1x` | SpatialCapture | Bistro | `20261120_234822` | PASS (23:48–23:52) |
| `acm-1x` | SpatialCapture | Minecraft | `20261120_235212` | PASS (23:52–23:55) |

실행 전마다 CMAA2 0개, GPU P8(사용률 0~5%), 게임이나 영상 프로그램 없음을 확인했고 끝난 뒤 남은 CMAA2는 0개였다. temporal 캡처에는 ④, 선택 경로, 선택 경로+Cross5, 19번과 각각의 Adaptive 쪽 여덟 mode가, SMAA 1X 캡처에는 Original과 Adaptive의 네 프리셋 여덟 mode가 들어 있다.

`Tools/SMAA/verify_adaptive_selected_cross5_minimal.py`로 PNG를 SHA-256으로 비교했다(`verify-bistro.json`, `verify-minecraft.json`). 새 PNG는 모두 240장이고 chunk CRC가 맞았다.

| 이 브랜치 mode | 비교 대상 | Bistro | Minecraft |
|---|---|---:|---:|
| O-1X, A-1X | 결합 브랜치 캡처 c28 `ac` | 240/240 | 240/240 |
| ④, 선택 경로, 선택 경로+Cross5, A+선택 경로, A+선택 경로+Cross5 | 결합 브랜치 캡처 c28 `ac` | 240/240 (다섯 mode 모두) | 240/240 (다섯 mode 모두) |
| 19번, A-T2X-R, A+19번 | Adaptive 정리 브랜치 temporal 캡처(Bistro `min-r2`, Minecraft `min`) | 240/240 | 240/240 |
| O/A Low, Medium, High | Adaptive 정리 브랜치 SMAA 1X 캡처 `min-spatial` | 240/240 (여섯 mode 모두) | 240/240 (여섯 mode 모두) |

c28 `ac`와 비교한 일곱 mode는 두 장면 모두 240/240 같았다. Cross5 resolve의 셰이더 바이트는 결합 브랜치와 다르지만 출력은 같다. 19번과 다른 프리셋도 Adaptive 정리 브랜치와 같아, Cross5를 더해도 그 경로들은 바뀌지 않았다.

## 줄 수

SMAA 폴더의 .cpp .h .inl .hlsl .hlsli 변경을 `git diff -w --ignore-blank-lines`로 셌다(정리 브랜치의 `Tools/SMAA/count_smaa_lines.py`). 코드 줄은 추가된 줄 가운데 빈 줄과 주석을 뺀 줄이다. 결과는 `line-counts.json`에 있다.

원본 SMAA(`baseline/original-smaa`, ee0020d) 대비

| 구성 | 추가 | 삭제 | 코드 줄 |
|---|---:|---:|---:|
| 선택 경로 기준선 (`b6c3ebc`: ④ + 선택 경로 + 19번) | 545 | 61 | 439 |
| Adaptive 정리 브랜치 (`644f836`: 기준선 + Adaptive) | 647 | 81 | 523 |
| 이 브랜치 (`ae8c0d1`: 기준선 + Adaptive + Cross5) | 693 | 81 | 560 |
| 결합 브랜치 (`c55db4f`) | 913 | 81 | 724 |

기준선(b6c3ebc) 대비

| 구성 | 추가 | 삭제 | 코드 줄 | 셰이더 (추가/삭제/코드) | C++ (추가/삭제/코드) |
|---|---:|---:|---:|---|---|
| Adaptive 정리 브랜치 (`644f836`) | 109 | 27 | 91 | 90 / 22 / 75 | 19 / 5 / 16 |
| 이 브랜치 (`ae8c0d1`) | 160 | 32 | 133 | 111 / 22 / 89 | 49 / 10 / 44 |
| 결합 브랜치 (`c55db4f`) | 383 | 35 | 300 | 256 / 22 / 192 | 127 / 13 / 108 |

Cross5 몫(`f73bdee` → `ae8c0d1`)은 +51/−5줄, 코드 42줄이다. 셰이더 +21줄(코드 14줄), C++ +30/−5줄(코드 28줄)이다. 파일별로는 `SelectedTemporal.hlsl` +21(코드 14), `vaSMAAWrapperDX11.cpp` +16/−1(코드 15), `SMAA.cpp` +7/−2(코드 7), `SMAA.h` +3/−2(코드 3), `vaSMAAWrapper.h` +4(코드 3)다. 이 브랜치의 기준선 대비 변경은 Adaptive(코드 91줄)와 Cross5(코드 42줄)를 더한 것과 같다. 결합 브랜치보다 기준선 대비 코드 줄이 167줄 적다.

## 시간

따로 재지 않았다. 출력이 결합 브랜치와 바이트까지 같으므로 결합 브랜치의 측정(`experiment/adaptive-selected-cross5`, 2026-11-20, RTX 3060 Ti, 1920×1061, 300 warm-up + 4,800프레임 × 6회)을 그대로 인용한다. 다만 이 브랜치의 Cross5 resolve는 결합 브랜치와 셰이더 바이트가 다르므로 시간이 같다는 것은 재서 확인하지 않은 가정이다. 결합 브랜치에서 A+선택 경로+Cross5의 AA 시간은 ④ 대비 Bistro −22.64%, Minecraft −3.08%였다. 같은 경로 Original(선택 경로+Cross5) 대비 −6.34% / −4.71%이고, Cross5 없는 A+선택 경로 대비 +1.68% / +3.67%였다.

## 자료

- 캡처: temporal `D:/SMAAResearchCaptures/c29/acm/capture/{bistro/20261120_234106, minecraft/20261120_234452}`, SMAA 1X `D:/SMAAResearchCaptures/c29/acm-1x/spatial/{bistro/20261120_234822, minecraft/20261120_235212}`
- 비교한 캡처: 결합 브랜치 `D:/SMAAResearchCaptures/c28/ac/capture/{bistro/20261120_210101, minecraft/20261120_210421}`, Adaptive 정리 브랜치 `D:/SMAAResearchCaptures/c24-minimal/min-r2/capture/bistro/20261119_214900`, `D:/SMAAResearchCaptures/c24-minimal/min/capture/minecraft/20261119_213505`, `D:/SMAAResearchCaptures/c24-minimal/min-spatial/spatial/{bistro/20261119_213752, minecraft/20261119_214145}`
- 수치: 이 폴더의 `fxc-audit.json`, `line-counts.json`, `verify-*.json`, `runs.json`
- 도구: `Tools/SMAA/audit_adaptive_selected_cross5_minimal_shaders.py`, `Tools/SMAA/verify_adaptive_selected_cross5_minimal.py`, 줄 수는 `tooling/adaptive-tier-minimal`의 `Tools/SMAA/count_smaa_lines.py`
