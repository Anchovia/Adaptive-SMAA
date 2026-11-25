# 개선된 SMAA 데모에 SMAA T2x-R 비교 항목 추가

base 커밋은 `experiment/improved-smaa-demo-temporal-toggle` 192a2ab(사용자가 돌려 보는 Temporal 켜기/끄기 데모)다. 기준선 `baseline/improved-smaa-demo`, toggle 브랜치, 화면 밖 history 브랜치는 옮기지 않았다. 화면 밖 history 거부 수정(b616dbc)은 넣지 않았으므로 나중에 따로 합칠 수 있다.

브랜치

- `experiment/improved-smaa-demo-t2x-r` (이 문서, 192a2ab에서 시작)
- `validation/improved-smaa-demo-t2x-r` (afbaaca 위에 이 커밋을 옮겨 온 검증 harness와 결과)
- `tooling/adaptive-selected-cross5-minimal` 60bae94 (옮겨 온 T2x-R 경로. c29의 O-T2X-R을 만든 브랜치다)

## 바꾼 것

AA 목록 맨 아래에 `SMAA T2x-R` 항목을 더했다. 연구에서 ④ 또는 O-T2X-R로 부르던 것으로 공식 SMAA T2x에 카메라/깊이 재투영을 더한 방식이다. `SMAA Adaptive + Temporal`과 바로 바꿔 가며 비교하려고 넣었다.

- 공간 처리는 원본 SMAA 탐색이다. Adaptive 단계는 쓰지 않는다.
- 장면을 프레임마다 (+0.25, +0.25)와 (−0.25, −0.25) projection jitter로 번갈아 그리고 SMAA는 T2x 모드에서 같은 짝의 subsample index를 쓴다.
- 속도는 깊이와 카메라 행렬로 구한다. 깊이는 jitter가 들어간 행렬로 위치를 복원하고 현재와 이전 위치는 jitter 없는 행렬로 비교한다.
- 공식 SMAA resolve(SMAA_REPROJECTION, 속도 차이 가중치)가 이번 프레임과 이전 프레임의 공간 결과를 섞는다. history는 이전 프레임의 공간 결과 하나다.
- SMAA 창의 Quality preset(LOW~ULTRA)이 그대로 적용된다. 단축키는 `R`이다. 데모와 프레임워크에서 R은 Ctrl+R(셰이더 다시 읽기)로만 쓰였고 AA 키는 Ctrl, Shift, Alt가 눌려 있지 않을 때만 읽으므로 겹치지 않는다. 연구 브랜치에서도 T2x Reprojected가 R이었다.
- 정적 이미지 장면에서는 고를 수 없다.

jitter, 프레임 번호, T2x-R history는 이 항목을 골랐을 때만 생긴다. 다른 항목으로 바꾸거나 이 항목으로 돌아오면 history를 다시 시작한다. Temporal 체크박스는 계속 `SMAA Adaptive + Temporal`에만 나온다. T2x-R에서 temporal만 뺀 짝은 기존 `SMAA`(1x)다.

## 구현

- `SMAA::reproject()`는 원본 코드에 주석으로만 남아 있던 것을 60bae94와 같은 모습으로 옮겼다. `SMAA::resetFrame()`을 더했다.
- `vaSMAAWrapper`에 `SetNativeT2xR`, `GetTemporalJitterOffset`을 더했다. DX11 wrapper는 T2x-R일 때 SMAA를 SMAA_REPROJECTION으로 만들고 history 두 장과 속도 텍스처를 쓴다. 매 프레임 SMAA 스텐실을 지우고 go()(T2x 모드)와 reproject()를 부른다. 순서와 값은 60bae94와 같다.
- `CMAA2Sample`은 T2x-R일 때 jitter를 넣은 카메라 복사본으로 장면을 그리고 그 카메라를 SMAA에 넘긴다.
- 선택 경로(Adaptive + Temporal)의 카메라에는 jitter가 없으므로 속도 행렬 값이 전과 같다. 셰이더 파일은 바꾸지 않았다.

## 실행 방법

1. Visual Studio 2022에서 `CMAA2.sln`을 열고 Release x64로 빌드한다(명령줄은 `MSBuild CMAA2.sln -p:Configuration=Release -p:Platform=x64`).
2. `Projects\CMAA2\CMAA2.exe`를 실행한다.
3. AA 목록에서 `SMAA T2x-R`을 고르거나 `R` 키를 누른다. `T` 키는 `SMAA Adaptive + Temporal`, `4` 키는 원본 `SMAA`라서 세 항목을 UI를 숨긴 채(F1)로도 키로 바로 바꿔 볼 수 있다. `Y`는 계속 `SMAA Adaptive + Temporal`의 Temporal만 켜고 끈다.

## 원본 대비 줄 수

`git diff -w --ignore-blank-lines` 기준(문서 제외)이다.

| 비교 | 파일 | 추가 | 삭제 |
|---|---|---:|---:|
| 192a2ab → c044670 | `Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp` | 50 | 10 |
| | `Projects/CMAA2/CMAA2Sample.cpp` | 22 | 4 |
| | `Projects/CMAA2/SMAA/SMAA.cpp` | 17 | 29 |
| | `Projects/CMAA2/SMAA/vaSMAAWrapper.h` | 10 | 0 |
| | `Projects/CMAA2/CMAA2Sample.h` | 1 | 0 |
| | `Projects/CMAA2/SMAA/SMAA.h` | 1 | 0 |
| | 합계(6개 파일) | 101 | 43 |
| ee0020d → c044670 | 합계(11개 파일) | 663 | 77 |

`SMAA.cpp`의 삭제 29줄은 주석으로 남아 있던 옛 reproject() 코드다.

## 검증 요약

자세한 내용은 `validation/improved-smaa-demo-t2x-r`의 `Docs/Improved-SMAA-Demo-T2x-R-Validation/readme-ko.md`에 있다. 시간 측정은 하지 않았다.

- Release x64 빌드가 성공했다(바꾸지 않은 줄의 기존 경고만 있다).
- FXC로 컴파일한 셰이더 162개가 모두 같았다. 원본 SMAA와 Adaptive SMAA·선택 경로는 192a2ab와, T2x-R 빌드(SMAA_REPROJECTION)는 60bae94와 같은 DXBC다.
- c28, c29와 같은 240프레임 타임라인에서 Bistro와 Minecraft 모두 다음이 SHA-256까지 같았다. 새 항목(Ultra)은 c28과 c29의 O-T2X-R과 240/240 같았다. 원본 SMAA 1x 네 프리셋은 c29와, Adaptive + Temporal Ultra는 c28·c29 최종 조합과, High·Medium·Low는 c30과, Temporal 끔 네 프리셋은 c29 Adaptive 1X와 같았다.
- T2x-R을 그리다 90프레임에서 SMAA 1X나 Adaptive + Temporal로 바꾸고 150프레임에 돌아오는 실행에서 바꾼 뒤의 프레임이 그 항목의 정상 실행(또는 history를 다시 시작한 실행)과 같았고 T2x-R로 돌아온 뒤는 history를 다시 시작한 T2x-R과 같았다. jitter와 history가 다른 항목에 남지 않는다.
- T2x-R High·Medium·Low도 정상으로 돌았고 Ultra와 출력이 달라 프리셋이 적용된다.
- 실제 키 입력으로 R, T, R, F1, T, F1을 눌러 항목 전환과 UI를 숨긴 상태의 전환이 모두 기대한 대로 바뀌었다.

## 사용자가 보게 될 모습

원본 PNG를 nearest로 확대해 직접 보았다. T2x-R은 두 jitter 표본을 섞어 정지 화면에서도 SMAA 1X보다 부드럽다. 움직이는 동안에는 더 부드럽고 Bistro 창 안쪽 같은 세부가 조금 번진다. Minecraft 나뭇잎처럼 세부가 많은 곳에서는 짝수와 홀수 프레임의 선명도가 번갈아 달라 보였다(그 자리 edge strength가 124, 134, 122, 133처럼 번갈아 바뀜). 연구의 O-T2X-R과 같은 출력이다. SMAA Adaptive + Temporal은 SMAA 1X에 가까운 선명도였다.

## 커밋

- c044670 feat(cmaa2): add SMAA T2x-R as an AA option for comparison
