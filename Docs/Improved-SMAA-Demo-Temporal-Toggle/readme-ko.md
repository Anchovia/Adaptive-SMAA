# 개선된 SMAA 데모의 Temporal 켜기/끄기

base 커밋은 `baseline/improved-smaa-demo` 1d54b7f다. 이 기준선은 원본 CMAA2 데모(`origin/baseline/original-smaa` ee0020d)에 `SMAA Adaptive + Temporal` 항목 하나를 더한 것이다. 기준선 브랜치는 옮기지 않았다.

브랜치

- `experiment/improved-smaa-demo-temporal-toggle` (이 문서, 1d54b7f에서 시작)
- `validation/improved-smaa-demo-temporal-toggle` (이 브랜치의 a8042ab 위 검증 harness와 결과)
- `baseline/improved-smaa-demo` 1d54b7f, `validation/improved-smaa-demo-equivalence` bc68990 (기준선과 그 검증)

## 바꾼 것

`SMAA Adaptive + Temporal`을 고르면 SMAA 창의 Quality preset 아래에 Temporal 체크박스가 나온다. 처음 값은 켜짐이다.

- 켜짐은 기준선과 같은 동작이다(Adaptive 1% 단계 + 선택 경로 + Cross5).
- 꺼짐이면 같은 프리셋의 Adaptive SMAA 1X만 그린다. temporal 텍스처(history 두 장, 공간 결과 사본, 속도 두 장)를 놓아 주고 속도 패스와 history 출력 교체도 하지 않는다.
- 켜고 끌 때마다 history를 다시 시작한다. 다시 켠 첫 프레임은 seed다.
- F1로 UI를 숨긴 시연에서는 `Y` 키로 바꾼다. `Y`는 `SMAA Adaptive + Temporal`이 선택되어 있을 때만 듣는다. 프레임워크와 데모가 이미 쓰는 키(W, A, S, D, Q, E, 화살표, 숫자, -, =, T, P, F1, Ctrl+R, Ctrl+K, `)와 겹치지 않는다.

체크박스 값은 설정 파일에 저장하지 않으므로 데모를 켤 때마다 켜짐으로 시작한다. UI를 숨긴 상태에서는 현재 값을 화면에 보여 주지 않는다.

## 구현

체크박스 값은 `vaSMAAWrapper`의 `m_temporalEnabled`에 두었다. RenderTick이 이 값을 `SetSelectedTemporal(improvedSMAA && GetTemporalEnabled())`로 넘기므로 켜고 끄는 일은 기준선의 `SetSelectedTemporal`이 맡는다. 이 함수는 값이 바뀌면 history를 다시 시작하고 꺼질 때는 temporal 텍스처를 놓아 준다. 다시 켜면 첫 Draw에서 텍스처를 새로 만든다.

체크박스는 Adaptive 탐색이 켜져 있을 때만 그린다. Adaptive 탐색은 새 항목에서만 켜지므로 다른 AA 항목의 SMAA 창은 그대로다. 셰이더, 원본 SMAA 1x와 S2x 경로, 다른 AA 항목의 코드는 바꾸지 않았다.

## 실행 방법

1. Visual Studio 2022에서 `CMAA2.sln`을 열고 Release x64로 빌드한다(명령줄은 `MSBuild CMAA2.sln -p:Configuration=Release -p:Platform=x64`).
2. `Projects\CMAA2\CMAA2.exe`를 실행하고 AA option 목록에서 `SMAA Adaptive + Temporal`을 고르거나 `T` 키를 누른다.
3. SMAA 창의 Temporal 체크박스나 `Y` 키로 temporal 처리를 켜고 끈다. 체크박스에 마우스를 올리면 같은 설명이 나온다.

## 원본 대비 줄 수

`git diff -w --ignore-blank-lines`(공백과 빈 줄 변화 제외, 문서 제외) 기준이다.

| 비교 | 파일 | 추가 | 삭제 |
|---|---|---:|---:|
| 1d54b7f → a8042ab(이번 변경) | `Projects/CMAA2/CMAA2Sample.cpp` | 5 | 2 |
| | `Projects/CMAA2/SMAA/vaSMAAWrapper.cpp` | 8 | 0 |
| | `Projects/CMAA2/SMAA/vaSMAAWrapper.h` | 5 | 0 |
| | 합계(3개 파일) | 18 | 2 |
| ee0020d → a8042ab(원본 대비) | 합계(11개 파일) | 574 | 46 |

원본 대비 수치는 기준선의 558/46(10개 파일)에 이번 변경을 더한 것이다. 기준선에서 손대지 않았던 `vaSMAAWrapper.cpp`가 열한 번째 파일이다.

## 검증 요약

검증 harness와 결과는 `validation/improved-smaa-demo-temporal-toggle`의 `Docs/Improved-SMAA-Demo-Temporal-Toggle-Validation/readme-ko.md`에 있다. 이 브랜치에는 검증 코드를 넣지 않았다.

- Release x64 빌드가 성공했다. 셰이더 파일은 바뀌지 않았다.
- 기준선 검증과 같은 타임라인(고정 60 Hz, 정지 60 / 이동 120 / 정지 60프레임, 1920×1061)으로 Bistro와 Minecraft를 14 mode × 240프레임씩 찍어 SHA-256으로 비교했다.
- 원본 SMAA 1X는 프리셋 네 개 모두 c29와 240/240 같았다.
- Temporal 켜짐은 프리셋 네 개 모두 기준선 캡처(c30)와 240/240 같고 Ultra는 c29, c28의 최종 조합과도 같았다.
- Temporal 꺼짐은 프리셋 네 개 모두 같은 프리셋의 Adaptive SMAA 1X(c29)와 240/240 같았다. 꺼진 프레임마다 temporal 텍스처와 history 출력 교체가 없음을 확인했다.
- 실행 중 90프레임에서 끄고 150프레임에서 다시 켠 결과는 0~89가 켜짐, 90~149가 꺼짐과 같았다. 150~239는 켠 채로 150프레임에서 history만 다시 시작한 결과와 바이트까지 같았다.
- 실제 키 입력으로 T, Y, F1, Y, F1을 눌러 항목 선택, 끄기, UI 숨기기, UI를 숨긴 채 켜기, UI 다시 보이기가 모두 기대한 상태로 바뀌었다. 저장한 화면에서 체크박스가 켜짐, 꺼짐, 켜짐으로 바뀐 것도 직접 확인했다.

시간 측정은 하지 않았다.

## 커밋

- a8042ab feat(cmaa2): switch the temporal part of SMAA Adaptive + Temporal
