# 개선된 SMAA 데모 SMAA T2x-R 항목 검증

브랜치

- `validation/improved-smaa-demo-t2x-r` (이 문서, `validation/improved-smaa-demo-temporal-toggle` afbaaca 위에 T2x-R 커밋을 옮겨 왔다)
- `experiment/improved-smaa-demo-t2x-r` c044670 (검증 대상, 192a2ab에서 시작)
- `tooling/adaptive-selected-cross5-minimal` 60bae94 (옮겨 온 T2x-R 경로, c29의 O-T2X-R을 만든 브랜치)

c044670을 760e6ac로 옮겨 와 기존 검증 harness와 함께 빌드했다. 시간 측정은 하지 않았다. 화면 밖 history 거부 수정(b616dbc)은 들어 있지 않다.

## 확인한 것

| 항목 | 방법 | 결과 |
|---|---|---|
| Release x64 빌드 | MSBuild `CMAA2.sln`, Release x64 | 실험 브랜치와 이 브랜치 모두 성공. 경고는 바꾸지 않은 줄의 기존 경고뿐이다. 실험 브랜치 실행 파일 SHA-256 `E0087B5B…`, 검증 빌드 `BE0FA452…` |
| 셰이더 | `Tools/Validation/audit_t2xr_shaders.py`, FXC 10.0.26100.0, 데모와 같은 매크로 | 162/162 같음. 원본 SMAA 진입점 11개 × 프리셋 4개(44)와 Adaptive SMAA·선택 경로 18개 × 4(72)는 192a2ab와, T2x-R 빌드(SMAA_REPROJECTION=1, 원본 탐색) 11개 × 4(44)는 60bae94와, 카메라 속도 셰이더는 두 커밋 모두와 같은 DXBC다 |
| T2x-R(Ultra) 출력 | 240프레임 PNG를 c28과 c29의 O-T2X-R과 SHA-256 비교 | Bistro, Minecraft 모두 c28 240/240, c29 240/240 같음 |
| 기존 항목 출력 | O-1X·High·Medium·Low는 c29, Adaptive + Temporal Ultra는 c28·c29 최종 조합, High·Medium·Low는 c30, Temporal 끔(ATOff-*)은 c29 Adaptive 1X와 비교 | 두 장면 모두 15개 비교가 전부 240/240 같음 |
| 전환 | 아래 | 두 장면 모두 같음 |
| T2x-R High·Medium·Low | 같은 타임라인으로 실행 | 모두 정상 실행. Ultra와 240/240 달라 프리셋이 적용된다 |
| 프레임별 상태 | 매 프레임 AA 항목, 프리셋, Adaptive 여부, 선택 경로, T2x-R, jitter, temporal 텍스처, history 출력 교체를 확인 | 모든 mode와 프레임에서 PASS. jitter와 T2x-R은 T2x-R일 때만, 선택 경로는 Adaptive + Temporal일 때만 켜졌다 |
| 실제 키 입력 | Bistro 창에 R, T, R, F1, T, F1을 실제 키 입력으로 보냄 | 여섯 키 모두 기대한 상태로 바뀌었다(아래) |

새 PNG는 모두 청크 CRC 검사를 통과했다. 판정은 `Tools/Validation/verify_t2xr.py`가 한다(`verify-bistro.json`, `verify-minecraft.json`).

## 전환

전환 실행은 Ultra에서 0~89프레임 T2x-R, 90~149프레임 다른 항목, 150~239프레임 다시 T2x-R을 그린다. 비교 기준은 같은 실행 안의 정상 실행이다.

| 실행 | 구간 | 비교 기준 | Bistro | Minecraft |
|---|---|---|---:|---:|
| Switch-T2xR-AT | 0~89 | T2x-R 정상 실행 | 90/90 | 90/90 |
| | 90~149 | Adaptive + Temporal을 90프레임에서 history만 다시 시작한 실행(AT-Reset90) | 60/60 | 60/60 |
| | 150~239 | T2x-R을 150프레임에서 history만 다시 시작한 실행(T2xR-Reset150) | 90/90 | 90/90 |
| Switch-T2xR-O1X | 0~89 | T2x-R 정상 실행 | 90/90 | 90/90 |
| | 90~149 | SMAA 1X 정상 실행, c29 O-1X | 60/60, 60/60 | 60/60, 60/60 |
| | 150~239 | T2xR-Reset150 | 90/90 | 90/90 |

T2x-R에서 SMAA 1X로 바꾼 직후의 60프레임이 SMAA 1X 정상 실행과 바이트까지 같으므로 jitter나 history가 남지 않는다. Adaptive + Temporal로 바꾼 경우에도 그 항목을 처음부터 다시 시작한 것과 같았다. T2x-R로 돌아온 뒤는 history를 다시 시작한 T2x-R과 같았다. T2x-R의 history는 이전 프레임 하나뿐이라 다시 시작한 실행도 2프레임 뒤에는 정상 실행과 같아진다(T2xR-Reset150 150~239 중 88/90이 정상 실행과 같음).

보고서의 switch_state 줄에 적힌 jitter는 그 프레임을 그린 뒤의 값이라 다음 프레임에 쓰일 offset이다. T2x-R 프레임에서는 늘 (±0.25, ±0.25)였고 다른 항목에서는 (0, 0)이었다.

## 실제 키 입력

`run_improved_smaa_validation.ps1 -Mode Keys`는 60초 이상 입력이 없을 때 CMAA2를 보이는 창으로 띄우고(AA None으로 시작) 그 창이 맨 앞에 있을 때만 `keybd_event`로 키를 보낸다. 앱은 상태가 바뀔 때마다 `keys.log`에 적고 마지막 변화 30프레임 뒤 화면을 UI와 함께 저장한다.

| 화면 | 직전 키 | 기록된 상태 |
|---|---|---|
| screen_0 | 없음 | AA None, T2x-R 꺼짐, jitter 없음, 텍스처 없음, UI 보임 |
| screen_1 | R | SMAA T2x-R, t2xr=1, jitter 있음, 텍스처 있음, history 출력 교체 없음, 선택 경로 꺼짐 |
| screen_2 | T | SMAA Adaptive + Temporal, 선택 경로 켜짐, t2xr=0, jitter 없음 |
| screen_3 | R | SMAA T2x-R |
| screen_4 | F1 | SMAA T2x-R, UI 숨김 |
| screen_5 | T | SMAA Adaptive + Temporal, UI 숨김 |
| screen_6 | F1 | SMAA Adaptive + Temporal, UI 보임 |

키가 눌린 프레임에는 AA 항목만 바뀌고 다음 프레임에 T2x-R, jitter, 선택 경로가 따라 바뀐다. RenderTick 앞부분에서 값을 넘기고 키는 끝부분에서 읽기 때문이다.

저장한 화면을 직접 열어 SMAA 창을 nearest 2배로 확대해 보았다. screen_1과 screen_3에서는 AA 목록 맨 아래 `SMAA T2x-R`이 선택되어 있고 SMAA 창에는 Quality preset ULTRA만 있고 Temporal 체크박스는 없다. screen_2에서는 `SMAA Adaptive + Temporal`이 선택되어 있고 Temporal 체크박스가 켜져 있다. screen_4, screen_5에는 UI가 없고 장면만 정상으로 그려졌다. screen_1에는 T2x-R로 바꿀 때 SMAA를 SMAA_REPROJECTION으로 다시 만들며 생긴 "Compiling shaders" 알림이 위쪽에 보였다.

첫 키 입력 실행은 다섯 번째 키(UI를 숨긴 뒤 T)가 반영되지 않아 실패했다. 앱은 프레임마다 키 상태를 한 번 읽는데 화면 파일이 생기자마자 80 ms 동안 누른 키가 그 화면을 저장하는 긴 프레임 안에서 끝난 것으로 보인다. 키를 200 ms 누르고 화면 파일이 생긴 뒤 0.5초 기다리도록 실행 스크립트를 고친 뒤 다시 돌린 실행은 통과했다. 데모 코드는 바꾸지 않았다.

## 직접 본 T2x-R 프레임

원본 PNG를 nearest 4배로 확대해 SMAA 1X, SMAA T2x-R, SMAA Adaptive + Temporal을 나란히 놓고 이동 구간 117~122프레임과 정지 구간 200~205프레임을 보았다. 자리는 120프레임에서 T2x-R과 Adaptive + Temporal이 가장 다른 곳이다.

- Bistro(x=944, y=496, 창문과 안쪽 진열장): 이동 중 T2x-R은 SMAA 1X보다 눈에 띄게 부드럽고 창틀 가장자리와 안쪽 물건이 조금 번져 보였다. Adaptive + Temporal은 SMAA 1X에 가까운 선명도였다. 정지 구간에서도 T2x-R은 두 jitter 표본을 섞어 SMAA 1X보다 부드러웠고 프레임마다 변하지 않았다.
- Minecraft(x=1432, y=800, 나뭇잎): 이동 중 T2x-R은 118, 120, 122프레임이 117, 119, 121프레임보다 더 흐려 보였다. 이 자리의 edge strength가 프레임마다 124, 134, 122, 133처럼 번갈아 바뀌었고 SMAA 1X는 145, 154, 149, 150처럼 고르게 변했다. 두 jitter 위상이 번갈아 보이는 것이고 연구의 O-T2X-R과 같은 출력이다. 화면 전체로는 짝수와 홀수 프레임 차이가 1% 미만이었다. 정지 구간은 SMAA 1X보다 부드럽고 안정적이었다.
- 두 장면 모두 120, 210프레임 전체 화면에 깨진 화소나 번쩍임은 없었다.

이 관찰은 사용자가 비교할 때 보게 될 모습을 적은 것이며 화질 우열 판정은 아니다. 시트는 `D:\SMAAResearchCaptures\c34\sheets\`에 있다.

## 실행 기록

| 실행 | 장면 | git head | 결과 |
|---|---|---|---|
| cap-b | Bistro, 20 mode × 240프레임(일부 구간만 저장한 기준 둘 포함) | a9efe0d(작업 트리 변경 없음) | PASS, 보고서 `20261125_182416` |
| cap-m(첫 실행) | Minecraft | a9efe0d | 시작 1초 안에 0xC0000409로 종료, 저장된 프레임 없음 |
| cap-m | Minecraft | a9efe0d | PASS, 보고서 `20261125_183943` |
| keys-b(첫 실행) | Bistro 키 입력 | a9efe0d | 다섯 번째 키 미반영으로 FAIL |
| keys-b | Bistro 키 입력 | 0ac179d | PASS |

각 실행은 CMAA2 프로세스 0개, GPU P8, 60초 이상 입력 없음을 확인한 독립 프로세스 하나였고 끝난 뒤 남은 CMAA2 프로세스는 0개였다. Minecraft 첫 실행의 시작 직후 종료는 T2x-R 코드가 없는 평행 이동 검증 빌드에서도 한 번 있었던 것과 같은 코드였고 다시 돌린 실행은 통과했다. 원인은 확인하지 못했다.

## 저장 공간 때문에 지운 프레임

D 드라이브 여유 공간이 20 GB 정도라 장면마다 검증을 마친 뒤 기준 캡처와 바이트까지 같은 12개 mode(O-1X·High·Medium·Low, AT-Ultra·High·Medium·Low, ATOff-Ultra·High·Medium·Low)의 PNG를 지웠다. 지우기 전에 프레임별 SHA-256과 기준 파일 경로를 `pruned-bistro.json`, `pruned-minecraft.json`에 남겼고 기준 파일(c29, c30)은 그대로 있다(`Tools/Validation/prune_identical_modes.py`). T2x-R, 전환, 기준 실행의 프레임은 남겼다.

## 검증용으로만 바꾼 것

- afbaaca에서 이어받은 것: 고정 tick, UI를 그린 뒤 back buffer 저장, `GetSMAA()`, `GetSettings()`, `HasTemporalResources()`, 검증 명령 연결
- 이번에 바꾼 것: harness의 T2x-R mode, 전환 실행과 그 기준, 프레임별 jitter·T2x-R 상태 검사, `-improvedSmaaKeys`의 키 순서와 상태 문자열, 실행 스크립트의 키 순서와 누르는 시간, `verify_t2xr.py`, `audit_t2xr_shaders.py`, `t2xr_sheets.py`, `prune_identical_modes.py`

## 한계

- T2x-R의 High·Medium·Low는 비교할 연구 기준이 없어 실행과 프리셋 적용만 확인했다.
- 실제 키 입력은 Bistro에서 했다. 목록을 마우스로 누르지는 않았고 harness는 목록과 같은 변수를 바꿨다.
- FXAA, CMAA2, MSAA, S2x는 다시 찍지 않았다. 코드와 셰이더가 그대로다.

## 자료

- 이 폴더의 `verify-bistro.json`, `verify-minecraft.json`, `fxc-audit.json`, `runs.json`, `pruned-*.json`
- 캡처: `D:\SMAAResearchCaptures\c34\cap-b\capture\bistro\20261125_182416`, `cap-m\capture\minecraft\20261125_183943`, 키 입력 `keys-b`, 시트 `sheets`(Git에 넣지 않음)
- 비교 기준
  - c28: `D:\SMAAResearchCaptures\c28\ac\capture\bistro\20261120_210101`, `minecraft\20261120_210421`
  - c29 temporal: `D:\SMAAResearchCaptures\c29\acm\capture\bistro\20261120_234106`, `minecraft\20261120_234452`
  - c29 SMAA 1X와 Adaptive 1X: `D:\SMAAResearchCaptures\c29\acm-1x\spatial\bistro\20261120_234822`, `minecraft\20261120_235212`
  - c30: `D:\SMAAResearchCaptures\c30\cap-b\capture\bistro\20261124_162100`, `cap-m\capture\minecraft\20261124_162635`
