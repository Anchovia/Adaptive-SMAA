# 개선된 SMAA 데모 Temporal 켜기/끄기 검증

브랜치

- `validation/improved-smaa-demo-temporal-toggle` (이 문서, `experiment/improved-smaa-demo-temporal-toggle` a8042ab 위)
- `experiment/improved-smaa-demo-temporal-toggle` (검증 대상, `baseline/improved-smaa-demo` 1d54b7f에서 시작)
- `validation/improved-smaa-demo-equivalence` bc68990 (기준선 검증. 이 브랜치는 그 harness 커밋 023b2cb, 28c00e1을 옮겨 와 고쳤다)

검증 대상 코드는 a8042ab다. 시간 측정은 요청받지 않아 하지 않았다.

## 확인한 것

| 항목 | 방법 | 결과 |
|---|---|---|
| Release x64 빌드 | MSBuild `CMAA2.sln`, Release x64 | a8042ab 빌드 성공(실행 파일 SHA-256 `C0CC55CE…`). 경고는 바꾸지 않은 줄의 기존 경고뿐이다. 검증 빌드 `27A45C9F…` |
| 셰이더 | a8042ab와 1d54b7f 사이의 `.hlsl`, `.hlsli` 변경 | 없음. 바뀐 파일은 `CMAA2Sample.cpp`, `vaSMAAWrapper.h`, `vaSMAAWrapper.cpp` 세 개다 |
| 원본 SMAA 1X | O-1X, O-High, O-Medium, O-Low 240프레임 PNG를 c29 SpatialCapture와 SHA-256 비교 | Bistro, Minecraft 모두 4 × 240/240 같음 |
| Temporal 켜짐 | AT-Ultra, AT-High, AT-Medium, AT-Low를 기준선 캡처 c30과 비교, AT-Ultra는 c29와 c28의 최종 조합(Adaptive + 선택 경로 + Cross5)과도 비교 | 두 장면 모두 c30 4 × 240/240, c29 240/240, c28 240/240 같음 |
| Temporal 꺼짐 | ATOff-Ultra, ATOff-High, ATOff-Medium, ATOff-Low를 같은 프리셋의 Adaptive SMAA 1X(c29 A-1X, A-High, A-Medium, A-Low)와 비교 | 두 장면 모두 4 × 240/240 같음 |
| 꺼짐 상태의 자원 | 매 프레임 temporal 텍스처 할당 여부(`HasTemporalResources`, 검증 전용), history 출력 교체, 선택 경로 상태를 확인 | 꺼진 프레임은 모두 텍스처 없음, 출력 교체 없음, 선택 경로 꺼짐이었다. 속도 패스는 선택 경로가 켜졌을 때만 돌고 속도 텍스처도 없으므로 꺼진 동안 돌지 않는다 |
| 실행 중 켜짐→꺼짐→켜짐 | AT-Toggle(Ultra)은 체크박스 값을 90프레임에서 끄고 150프레임에서 다시 켠다. AT-Reset150은 켠 채로 150프레임에서 history만 다시 시작한다 | 두 장면 모두 AT-Toggle 0~89가 AT-Ultra와 90/90, 90~149가 ATOff-Ultra와 c29 A-1X와 60/60, 150~239가 AT-Reset150과 90/90 같았다. AT-Reset150 0~149도 AT-Ultra와 150/150 같았다 |
| 실제 키 입력 | `-improvedSmaaKeys`를 띄운 Bistro 창에 T, Y, F1, Y, F1을 실제 키 입력으로 보내고 각 상태를 기록 | 다섯 키 모두 기대한 상태로 바뀌었다(아래) |

새 PNG는 모두 청크 CRC 검사를 통과했다. 판정은 `Tools/Validation/verify_temporal_toggle.py`가 한다.

## 켜고 끌 때의 출력

AT-Toggle이 다시 켠 150프레임은 seed라 ATOff-Ultra 150프레임과 같다. 151프레임부터는 ATOff-Ultra와 89/89 모두 달라 temporal 처리가 다시 작동했다. AT-Reset150의 150~239는 AT-Ultra와 90/90 달라 150프레임에서 history가 정말 다시 시작했다. 다시 켠 경우와 history만 다시 시작한 경우가 바이트까지 같으므로 꺼질 때 텍스처를 놓아 주고 켤 때 새로 만드는 과정이 출력에 남기는 것은 없다.

90프레임과 150프레임 전후 여섯 프레임씩을 AT-Toggle, ATOff-Ultra, AT-Ultra로 나란히 놓은 시트(nearest 4배, 120프레임에서 켜짐과 꺼짐이 가장 다른 곳)와 89, 90, 149, 150, 151프레임 전체 화면을 직접 열어 보았다. AT-Toggle은 89프레임까지 켜짐, 90~150프레임은 꺼짐과 같은 모습이고 151프레임부터 켜짐 쪽으로 돌아간다. 전환 프레임에 번쩍임, 검은 화면, 깨진 화소는 없었다.

- Bistro 시트: `D:\SMAAResearchCaptures\c31\sheets-b\off_at_90.png`, `on_at_150.png`, `toggle_full_frames.png` (crop x=960, y=571, 64×48)
- Minecraft 시트: `D:\SMAAResearchCaptures\c31\sheets-m\` (crop x=1610, y=955, 64×48)

이 비교는 동작 확인이며 화질 우열 판단이 아니다.

## 실제 키 입력

`run_improved_smaa_validation.ps1 -Mode Keys`는 60초 이상 입력이 없을 때 CMAA2를 보이는 창으로 띄우고(AA None으로 시작) 그 창이 맨 앞에 있을 때만 `keybd_event`로 T, Y, F1, Y, F1을 차례로 보낸다. 앱은 상태가 바뀔 때마다 `keys.log`에 적고 마지막 변화 30프레임 뒤 화면을 UI와 함께 저장한다. 이 PC의 foreground lock timeout은 0ms였다.

| 화면 | 직전 키 | 기록된 상태 |
|---|---|---|
| screen_0 | 없음 | AA None, temporal=1, selected=0, resources=0, presented=0, UI 보임 |
| screen_1 | T | SMAA Adaptive + Temporal, temporal=1, selected=1, resources=1, presented=1, UI 보임 |
| screen_2 | Y | temporal=0, selected=0, resources=0, presented=0, UI 보임 |
| screen_3 | F1 | temporal=0, selected=0, resources=0, presented=0, UI 숨김 |
| screen_4 | Y | temporal=1, selected=1, resources=1, presented=1, UI 숨김 |
| screen_5 | F1 | temporal=1, selected=1, resources=1, presented=1, UI 보임 |

키가 눌린 프레임에는 체크박스 값만 바뀌고 다음 프레임에 선택 경로, 텍스처, 출력 교체가 따라 바뀐다(`keys.log`의 change 줄). RenderTick 앞부분에서 값을 넘기고 키는 끝부분에서 읽기 때문이다.

저장한 화면을 직접 열어 SMAA 창을 nearest 2배로 확대해 보았다. screen_1과 screen_5에는 Quality preset ULTRA 아래 Temporal이 체크되어 있고 screen_2에는 체크가 없다. screen_3, screen_4에는 UI가 없고 장면만 정상으로 그려졌다. screen_1에는 T를 누른 뒤 SMAA를 Adaptive로 다시 만들면서 생긴 "Background tasks in progress, Compiling shaders" 알림이 화면 위쪽에 남아 있었다. 같은 프레임의 상태는 presented=1이라 SMAA 출력은 이미 그려지고 있었다. Y를 누른 뒤의 화면(screen_2, screen_4)에는 이 알림이 없다. Y는 SMAA 자원을 다시 만들지 않는다.

- 화면: `D:\SMAAResearchCaptures\c31\keys-b\screen_0.png` ~ `screen_5.png`, `keys.log`
- 시트: `D:\SMAAResearchCaptures\c31\sheets-keys.png`(여섯 화면 절반 크기), `sheets-keys-panel.png`(SMAA 창 확대), `sheets-keys-banner.png`

## 실행 기록

| 실행 | 장면 | git head | 결과 |
|---|---|---|---|
| cap-b | Bistro, 14 mode × 240프레임 | d4bda6b(작업 트리 변경 없음) | PASS, 보고서 `20261124_183707` |
| cap-m | Minecraft, 14 mode × 240프레임 | d4bda6b | PASS, 보고서 `20261124_184332` |
| keys-b | Bistro, 실제 키 입력 | d4bda6b | PASS |

각 실행은 CMAA2 프로세스 0개, GPU P8, 60초 이상 입력 없음을 확인한 뒤 독립 프로세스 하나로 돌렸고 끝난 뒤 남은 CMAA2 프로세스는 0개였다. 캡처 타임라인은 기준선 검증과 같다(고정 60 Hz, 1920×1061 숨김 창, play time 2.0에서 60프레임 warm-up, 정지 60 / 이동 120 / 정지 60, 0프레임에서 history 재시작). GPU 드라이버는 621.24로 c30과 같고 c28, c29(621.14)와는 다르지만 비교한 PNG는 모두 같았다.

## 검증용으로만 바꾼 것

실험 브랜치에는 없고 이 브랜치에만 있다.

- 기준선 검증에서 옮겨 온 것: 고정 tick, UI를 그린 뒤 back buffer 저장, `GetSMAA()`, `GetSettings()`, 검증 명령 연결, `-improvedSmaaScreens`
- 이번에 더한 것: `vaSMAAWrapper::HasTemporalResources()`, harness의 Temporal 꺼짐, AT-Toggle, AT-Reset150 mode와 프레임별 상태 검사, `-improvedSmaaKeys`, 실행 스크립트의 Keys mode, `verify_temporal_toggle.py`, `toggle_sheets.py`

## 한계

- 실제 키 입력은 Bistro에서 한 번만 했다. 체크박스는 마우스로 누르지 않았고 harness가 체크박스와 같은 변수를 바꿨다.
- 기존 AA 옵션 중 다시 찍어 비교한 것은 SMAA 1X 네 프리셋이다. FXAA, CMAA2, MSAA, S2x 코드는 바뀌지 않아 다시 찍지 않았다.
- AT-High, AT-Medium, AT-Low는 기준선 캡처 c30과 같다는 것까지 확인했다. 이 세 프리셋의 이동 구간은 연구 기준 캡처가 없다.
- AT-Toggle은 Ultra로만 돌렸다.

## 자료

- 이 폴더의 `verify-bistro.json`, `verify-minecraft.json`, `runs.json`
- 캡처: `D:\SMAAResearchCaptures\c31\cap-b\capture\bistro\20261124_183707`, `cap-m\capture\minecraft\20261124_184332`, 키 입력 `keys-b`, 시트 `sheets-b`, `sheets-m`, `sheets-keys*.png`(Git에 넣지 않음)
- 비교 기준
  - c30 기준선 캡처: `D:\SMAAResearchCaptures\c30\cap-b\capture\bistro\20261124_162100`, `c30\cap-m\capture\minecraft\20261124_162635`
  - c29 최종 조합: `D:\SMAAResearchCaptures\c29\acm\capture\bistro\20261120_234106`, `minecraft\20261120_234452`
  - c29 SMAA 1X와 Adaptive 1X: `D:\SMAAResearchCaptures\c29\acm-1x\spatial\bistro\20261120_234822`, `minecraft\20261120_235212`
  - c28 최종 조합: `D:\SMAAResearchCaptures\c28\ac\capture\bistro\20261120_210101`, `minecraft\20261120_210421`
