# 개선된 SMAA 데모 기준선 검증

브랜치

- `validation/improved-smaa-demo-equivalence` (이 문서, `baseline/improved-smaa-demo` e309268 위)
- `baseline/improved-smaa-demo` (검증 대상, ee0020d에서 시작)
- `tooling/adaptive-selected-cross5-minimal` 60bae94 (비교 캡처 c29를 만든 정리 브랜치)
- `experiment/adaptive-selected-cross5` c55db4f (비교 캡처 c28을 만든 결합 브랜치)

검증 대상 코드는 기준선의 e309268이다. 기준선의 다음 커밋은 문서뿐이라 렌더러 코드는 같다. 시간 측정은 요청받지 않아 하지 않았다.

## 확인한 것

| 항목 | 방법 | 결과 |
|---|---|---|
| Release x64 빌드 | MSBuild `CMAA2.sln`, Release x64 | 기준선 네 커밋 모두 빌드 성공(새 경고 없음). 기준선 실행 파일 SHA-256 `81D5D34C…`, 검증 빌드 `985B3EFC…`(캡처), `2B2EB10E…`(스크린샷 모드) |
| 셰이더 바이트 | `Tools/Validation/audit_improved_smaa_demo_shaders.py`, FXC 10.0.26100.0, 데모와 같은 매크로 | 117/117 같음. 원본 SMAA 진입점 11개 × 프리셋 4개는 ee0020d와, 새 항목의 SMAA 진입점 11개와 선택 경로 진입점 7개 × 프리셋 4개는 60bae94와, 카메라 속도 셰이더는 60bae94와 같은 DXBC다 |
| 기존 SMAA 1X 출력 | 프리셋 네 개(O-1X는 Ultra) 240프레임 PNG를 c29 SpatialCapture와 SHA-256 비교 | Bistro, Minecraft 모두 4 × 240/240 같음 |
| 새 항목 출력(Ultra) | `SMAA Adaptive + Temporal` 240프레임을 c29와 c28의 최종 조합(Adaptive + 선택 경로 + Cross5)과 비교 | Bistro, Minecraft 모두 c29 240/240, c28 240/240 같음 |
| 새 항목의 프리셋 적용 | High, Medium, Low 240프레임. 정지 구간 0~59프레임은 카메라가 그대로라 같은 프리셋의 Adaptive SMAA 1X(c29 A-High 등)와 같아야 한다 | 두 장면 모두 세 프리셋의 정지 구간 60/60이 같은 프리셋 Adaptive 1X와 같았다. 움직이기 시작한 61프레임부터는 달라 temporal 처리가 작동했다(이동 구간의 temporal 기준 캡처는 없다) |
| 실제 데모 화면 | UI를 켠 창에서 새 항목을 고르고 Play animation으로 카메라를 움직인 뒤 표시 화면 저장 | 아래 |

새 PNG는 모두 청크 CRC 검사를 통과했다. GPU 드라이버는 c28, c29 때 621.14였고 이번에는 621.24였다. 드라이버가 바뀌었어도 비교한 PNG는 모두 같았다.

## 캡처 조건

검증 harness(`Projects/CMAA2/ImprovedSmaaValidation.inl`)는 c28, c29 캡처와 같은 타임라인을 쓴다. 고정 60 Hz, 1920×1061 숨김 창, mode마다 SMAA 자원과 history를 새로 만들고 flythrough play time 2.0에서 60프레임 warm-up을 한다. 그다음 240프레임 동안 정지 60, 이동 120(play time 2.0→4.0), 정지 60이고 0프레임에서 history를 다시 시작한다. 프레임마다 최종 색을 PNG로 저장한다. mode 순서는 O-1X, O-High, O-Medium, O-Low, AT-Ultra, AT-High, AT-Medium, AT-Low다. c29에서는 같은 mode가 다른 순서 위치에서 찍혔지만 이전 브리지처럼 순서와 상관없이 같았다.

| 실행 | 장면 | git head | 결과 |
|---|---|---|---|
| cap-b | Bistro | 023b2cb(작업 트리 변경 없음) | PASS, 보고서 `20261124_162100` |
| cap-m | Minecraft | 023b2cb | PASS, 보고서 `20261124_162635` |
| show-b | Bistro 쇼케이스(AutoBench) | 023b2cb | PASS |
| screens-b2 | Bistro 일반 UI 스크린샷 | 28c00e1 | PASS |

각 실행은 `Tools/Validation/run_improved_smaa_validation.ps1`로 CMAA2 프로세스 0개, GPU P8, 60초 이상 입력 없음을 확인한 뒤 독립 프로세스 하나로 돌렸고 끝난 뒤 남은 CMAA2 프로세스는 0개였다. screens-b는 커밋 전 코드로 찍은 첫 실행이라 같은 코드를 커밋한 뒤 screens-b2로 다시 찍었다.

## 실제 데모 화면

AutoBench가 돌면 왼쪽 패널이 AA 목록 대신 AutoBench 상태를 보여 준다. 그래서 `-improvedSmaaScreens`는 AutoBench 없이 시작 때 새 항목을 고르고(목록을 누른 것과 같다) Play animation을 켠 뒤 완전히 그린 300, 330, 360번째 프레임의 표시 화면을 UI와 함께 저장하고 끝난다.

저장한 화면(`D:\SMAAResearchCaptures\c30\screens-b2\screen_300.png` 등)을 직접 열어 확인했다.

- AA option 목록 맨 아래에 `SMAA Adaptive + Temporal`이 선택되어 있고 SMAA 패널에 Quality preset ULTRA가 보인다.
- Bistro가 정상으로 그려졌고 카메라가 움직여 세 화면이 서로 다르다(가운데 영역 평균 차이 5.8, 5.7 RGB 단계).
- GPU Profiling 패널의 WholeFrame과 SMAA 줄에 0이 아닌 시간이 표시된다(SMAA 약 0.12 ms). BeginFrame 수정 뒤 전체 프레임 시간이 0으로 나오지 않는다. 이 값은 실시간 표시이며 측정 결과가 아니다.

쇼케이스 실행(show-b)에서는 같은 이동 경로의 SMAA 1X와 새 항목 최종 색을 0, 60, 120, 180, 239프레임에서 저장했다. 120프레임에서 두 출력이 가장 많이 다른 곳(x=977, y=480)을 nearest 4배로 확대해 보니 새 항목은 창틀 경계를 따라 값이 달랐고 깨진 화소나 이상한 색은 없었다. 이 비교는 정상 동작 확인이며 화질 우열 판단이 아니다.

## 검증용으로만 바꾼 것

기준선에는 없고 이 브랜치에만 있다.

- `CMAA2Sample`: 고정 tick(`SetFixedDeltaTime`), UI를 그린 뒤 back buffer 저장, `GetSMAA()`, 검증 명령 연결, `-improvedSmaaScreens`
- `vaSMAAWrapper::GetSettings()`: harness가 프리셋을 정하려고 쓴다
- `Projects/CMAA2/ImprovedSmaaValidation.inl`, `Tools/Validation/*`

## 한계

- 기존 AA 옵션 중 출력을 다시 찍어 비교한 것은 SMAA 1X 네 프리셋이다. FXAA, CMAA2, MSAA, S2x는 코드가 바뀌지 않았고 BeginFrame 수정은 출력에 영향이 없다(54f85af에서 확인)는 근거로 다시 찍지 않았다.
- `T` 키는 입력을 주입해 시험하지 않았다. 스크린샷 모드는 목록 선택과 같은 설정을 코드로 바꿨다.
- 정적 이미지 장면에서는 새 항목을 고를 수 없게 했고 시험하지 않았다.
- 새 항목의 High, Medium, Low 이동 구간은 비교할 temporal 기준 캡처가 없다.

## 자료

- 이 폴더의 `fxc-audit.json`, `verify-bistro.json`, `verify-minecraft.json`, `runs.json`
- 캡처: `D:\SMAAResearchCaptures\c30\cap-b\capture\bistro\20261124_162100`, `cap-m\capture\minecraft\20261124_162635`, 쇼케이스 `show-b\showcase\bistro\20261124_163151`, 확대 시트 `show-b\sheets`, 스크린샷 `screens-b2`(Git에 넣지 않음)
- 비교 기준: c29 `D:\SMAAResearchCaptures\c29\acm\capture\{bistro\20261120_234106, minecraft\20261120_234452}`, `c29\acm-1x\spatial\{bistro\20261120_234822, minecraft\20261120_235212}`, c28 `D:\SMAAResearchCaptures\c28\ac\capture\{bistro\20261120_210101, minecraft\20261120_210421}`
