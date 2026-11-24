# 개선된 SMAA 데모: 화면 밖 history 거부

base 커밋은 `experiment/improved-smaa-demo-temporal-toggle` 192a2ab(Temporal 켜기/끄기 데모)다. 기준선 `baseline/improved-smaa-demo` 1d54b7f와 toggle 브랜치는 옮기지 않았다.

브랜치

- `experiment/improved-smaa-demo-offscreen-history` (이 문서, 192a2ab에서 시작)
- `validation/improved-smaa-demo-offscreen-history` (검증 harness와 결과, `validation/improved-smaa-demo-translation-stability` 57910e0 위에 이 수정을 옮겨 왔다)
- `validation/improved-smaa-demo-translation-stability` 57910e0 (이 수정을 고른 평행 이동 안정성 검증)

## 바꾼 것

선택 경로의 Cross5 resolve(`SelectedResolveVelocityCross5PS`)에서 history 위치(uv − v)가 화면 밖이면 가중치를 0으로 한다. 판정은 경계 패스가 이전 원시 경계를 볼 때 쓰는 것과 같은 `all(previousUV >= 0) && all(previousUV < 1)`이다.

카메라가 움직이면 화면 가장자리로 새 내용이 들어온다. 이 화소의 history 위치는 화면 밖인데 지금까지는 Catmull-Rom 표본과 Cross5의 이전 속도 표본이 모두 가장자리 화소로 clamp되었다. 그래서 이전 프레임 가장자리 줄이 세로나 가로 줄무늬로 늘어나 섞였고 Cross5도 이를 거부하지 못했다. 이제 그런 화소는 이번 프레임의 공간 결과만 쓴다. 다음 프레임부터는 화면 안의 history를 정상으로 쓴다.

평행 이동 안정성 검증에서 찾은 원인 두 가지 가운데 이것만 고쳤다. 다른 원인인 Minecraft 픽셀 아트 질감이 history 재표본화로 흐려지고 출렁이는 문제는 그대로다.

## 원본 대비 줄 수

`git diff -w --ignore-blank-lines` 기준(문서 제외)이다.

| 비교 | 파일 | 추가 | 삭제 |
|---|---|---:|---:|
| 192a2ab → 이 수정 | `Projects/CMAA2/SMAA/SelectedTemporal.hlsl` | 5 | 1 |
| ee0020d → 이 수정 | 합계(11개 파일) | 578 | 46 |

192a2ab 대비 5줄 중 코드는 2줄이고 나머지는 주석이다.

## 실행 방법

toggle 데모와 같다. Release x64로 빌드한 뒤 `Projects\CMAA2\CMAA2.exe`에서 `SMAA Adaptive + Temporal`(`T` 키)을 고르고 Temporal 체크박스나 `Y` 키로 켜고 끈다.

## 검증 요약

자세한 내용은 `validation/improved-smaa-demo-offscreen-history`의 `Docs/Improved-SMAA-Demo-Offscreen-History-Validation/readme-ko.md`에 있다. 시간 측정은 하지 않았다.

- Release x64 빌드가 성공했다(바꾸지 않은 줄의 기존 경고만 있다).
- FXC로 컴파일한 셰이더 116개 가운데 바뀐 것은 Cross5 resolve의 프리셋 네 개뿐이다. 원본 SMAA, Adaptive SMAA, 다른 선택 경로 진입점 112개는 192a2ab와 같은 DXBC다.
- 평행 이동 안정성 검증과 같은 카메라 경로 일곱 개(Minecraft 수직 둘, 수평 둘, yaw 하나, Bistro 수평과 수직)를 네 가지 프레임 시간 조건으로 다시 찍었다. Off 프레임과 정지 상태 On 프레임은 이전 캡처와 바이트까지 같았다.
- 화면 가장자리 32화소 띠의 1/60초 흔들림(tde60)은 수정 전 On보다 Minecraft에서 fixed60 2~20%, fixed300 2~10%, 약 1 kHz 0.2~2.6% 줄었다. 가장자리 띠 밖은 바뀌지 않았고 28개 경우 어디서도 나빠지지 않았다.
- Minecraft 2.0 수직 fixed300의 화면 맨 위(x=568, y=0)에서 125~127프레임에 보이던 초록 세로 줄이 사라지고 Off, SSRef와 같은 모습이 되었다.

## 커밋

- b616dbc fix(smaa): no history for pixels whose history position is off screen
