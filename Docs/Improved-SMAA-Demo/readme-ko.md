# 개선된 SMAA를 더한 CMAA2 데모 기준선

브랜치

- `baseline/improved-smaa-demo` (이 문서, `origin/baseline/original-smaa` ee0020d에서 시작)
- `validation/improved-smaa-demo-equivalence` (이 기준선 위의 검증 harness와 결과)
- `tooling/adaptive-selected-cross5-minimal` 60bae94 (옮겨 온 최종 조합의 정리 브랜치)
- `tooling/adaptive-tier-minimal` 644f836 (Adaptive 1% 단계 정리 브랜치)
- `experiment/adaptive-selected-cross5` c55db4f (결합 브랜치)
- `validation/adaptive-selected-cross5-formal-timing` 2b33eab (전체 화면 정식 시간 측정)

## 무엇을 만들었나

원본 CMAA2 데모(ee0020d, SMAA 1x와 S2x만 있는 상태)에 지금까지 확정한 공간 개선(Adaptive 1% 단계)과 temporal 개선(선택 경로 + (c') Cross5) 두 가지만 더했다. AA 목록에 `SMAA Adaptive + Temporal` 항목 하나가 생기고 나머지 AA 옵션과 원본 SMAA 1x, S2x는 그대로다. 데모 시연에 쓰는 기준선이다.

## 실행 방법

1. Visual Studio 2022에서 `CMAA2.sln`을 열고 Release x64로 빌드한다(명령줄은 `MSBuild CMAA2.sln -p:Configuration=Release -p:Platform=x64`).
2. `Projects\CMAA2\CMAA2.exe`를 실행한다.
3. UI의 AA option 목록에서 `SMAA Adaptive + Temporal`을 고르거나 `T` 키를 누른다. 원본 SMAA는 목록의 `SMAA`나 `4` 키다.
4. 아래에 나오는 SMAA 창의 Quality preset(LOW, MEDIUM, HIGH, ULTRA)이 새 항목에도 그대로 적용된다. 연구 측정은 ULTRA로 했다.
5. Bistro에서는 Play animation을 켜면 카메라가 움직인다. 다른 장면에서는 마우스 오른쪽 버튼을 눌러 카메라 조작을 켜고 W, A, S, D, Q, E로 움직인다. 정적 이미지(screenshot) 장면에서는 깊이와 카메라 움직임이 없어 새 항목을 고를 수 없다.

## 포함한 것

| 커밋 | 내용 |
|---|---|
| c1455c8 공간 | Adaptive 1% 단계. 경계 패스가 finalDelta의 대비 단계를 RGBA8 경계 타깃의 세 번째 채널에 쓰고 가중치 패스가 그 단계로 직교 탐색 길이를 고른다(Ultra 3/8/20, High 2/6/12, Medium 3/6/8, Low 2/3/4). 최상위 단계는 원본의 탐색 끝(offset[2])을 쓴다. 셰이더 변경은 644f836과 같다 |
| b5b2a8e temporal | 선택 경로 + (c') Cross5. SMAA 1X 뒤에 현재 원시 경계와 카메라 재투영한 이전 원시 경계를 스텐실로 표시하고 그 화소만 resolve한다. history는 이전 최종 출력, Catmull-Rom 5-tap, 가중치 0.8에 Cross5 속도 검사를 곱한다. 카메라/깊이 재투영만 하고 jitter는 없다. reset 뒤 첫 프레임은 seed다. 이 경로에서는 매 프레임 SMAA 스텐실을 지운다 |
| b15c89b UI | AA 목록의 `SMAA Adaptive + Temporal`(`SuperSampleReference` 뒤에 둬서 기존 정지 이미지 autobench가 돌지 않는다), `T` 키, SMAA 프리셋 창, 장면 깊이와 카메라 전달, 선택 경로의 다음 history를 최종 색으로 표시. 카메라 로드, 정적 이미지 변경, 장면 변경에서 history를 다시 시작한다(해상도 변경은 SMAA 자원을 새로 만든다) |
| e309268 수정 | OnTick이 RenderTick과 ImGui 사이에서 BeginFrame을 한 번 더 불러 첫 전체 프레임 GPU 타이머가 열린 채 남았다. 그래서 데모 안의 프레임 시간 표시가 0으로 나왔다. Intel 공식 루프처럼 한 번만 부른다. 렌더링과 AA는 바뀌지 않는다(54f85af와 같은 수정) |

공간 처리와 temporal 처리는 각각 `vaSMAAWrapper::SetAdaptiveSearch`, `SetSelectedTemporal`로 켜고 새 AA 항목이 둘을 함께 켠다. 다른 AA 항목에서는 둘 다 꺼져 원본 코드 경로를 탄다.

## 뺀 것

- native T2x, T2x Reprojected 모드와 jitter, subsample 처리
- 19번(속도를 경계 패스에서 계산하는 경로)
- Cross5를 끄는 선택지와 Cross5 없는 resolve. 새 항목은 늘 Cross5를 쓴다
- AutoBench 확장, fixed delta, 캡처 harness, 연구 문서와 도구 일체. 검증 harness는 `validation/improved-smaa-demo-equivalence`에만 있다
- shader lifetime 수정(PrepareForDestruction). 이 수정은 연구 harness가 SMAA를 반복해서 다시 만들 때 백그라운드 셰이더 컴파일이 끝나기 전에 셰이더가 지워지는 문제를 막으려던 것이다. SMAA와 선택 경로의 셰이더는 모두 즉시 컴파일되고 데모에서는 프리셋이나 AA 항목을 바꿀 때만 다시 만들어지므로 넣지 않았다
- 원본 SMAA 1x, S2x 경로의 스텐실 초기화. 원본 경로는 ee0020d 그대로 두었다. 지우지 않아도 남은 스텐실 화소에는 경계가 없어 가중치가 0이므로 출력은 같다

`P` 키 스크린샷(ee0020d에 이미 있던 기능)은 G-buffer 출력 색을 저장하므로 SMAA 계열에서는 AA 전 화면이 저장된다. 원본 동작이라 고치지 않았다.

## 원본 대비 줄 수

`git diff -w --ignore-blank-lines ee0020d e309268`(공백과 빈 줄 변화 제외, 문서 제외) 기준이다.

| 파일 | 추가 | 삭제 |
|---|---:|---:|
| `Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp` | 156 | 9 |
| `Projects/CMAA2/SMAA/SelectedTemporal.hlsl`(새 파일) | 87 | 0 |
| `Projects/CMAA2/SMAA/SMAA.hlsl` | 80 | 12 |
| `Projects/CMAA2/SMAA/SMAA.cpp` | 67 | 11 |
| `Projects/CMAA2/SMAA/CatmullRomHistory5Tap.hlsli`(새 파일) | 48 | 0 |
| `Projects/CMAA2/SMAA/SMAAWrapper.hlsl` | 46 | 4 |
| `Projects/CMAA2/CMAA2Sample.cpp` | 26 | 5 |
| `Projects/CMAA2/SMAA/SMAA.h` | 25 | 4 |
| `Projects/CMAA2/SMAA/vaSMAAWrapper.h` | 21 | 1 |
| `Projects/CMAA2/CMAA2Sample.h` | 2 | 0 |
| 합계(10개 파일) | 558 | 46 |

커밋별로는 공간(c1455c8) +105/−21, temporal(b5b2a8e) +425/−20, UI(b15c89b) +27/−3, BeginFrame 수정(e309268) +1/−2다.

## 검증 요약

검증 harness와 결과는 `validation/improved-smaa-demo-equivalence`의 `Docs/Improved-SMAA-Demo-Validation/readme-ko.md`에 있다. 기준선에는 검증 코드를 넣지 않았다.

- Release x64 빌드는 네 커밋 모두 성공했다.
- FXC로 컴파일한 셰이더 바이트가 117/117 같았다. 원본 SMAA 경로는 ee0020d와, 새 항목의 SMAA와 선택 경로는 60bae94와 같다.
- c28, c29와 같은 타임라인(고정 60 Hz, 정지 60 / 이동 120 / 정지 60프레임, 1920×1061)으로 찍은 240프레임 PNG가 SHA-256까지 같았다. 원본 SMAA 1X는 프리셋 네 개 모두 c29와, 새 항목(Ultra)은 c29와 c28의 최종 조합(Adaptive + 선택 경로 + Cross5)과 Bistro, Minecraft 모두 240/240 같았다.
- 새 항목을 High, Medium, Low로 바꾸면 정지 구간 60프레임이 같은 프리셋의 Adaptive SMAA 1X와 같고 움직이면 달라져 프리셋이 적용됨을 확인했다.
- UI를 켠 실제 데모 화면에서 AA 목록의 새 항목을 고르고 카메라를 움직였을 때 장면이 정상으로 그려지고 GPU 시간 표시가 0이 아니게 나오는 것을 저장한 화면으로 확인했다.

시간 측정은 하지 않았다. 연구의 시간 결과는 `validation/adaptive-selected-cross5-formal-timing`(④ 대비 AA 시간 Bistro −23.3%, Minecraft −3.4%)을 따른다.

## 커밋

- c1455c8 feat(smaa): add Adaptive SMAA 1% search tiers
- b5b2a8e feat(smaa): add the selected temporal route with Cross5
- b15c89b feat(cmaa2): add the SMAA Adaptive + Temporal AA option
- e309268 fix(cmaa2): open the frame once per tick
