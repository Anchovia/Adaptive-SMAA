# ⑰ 코드 정리본: 출력 보존 검증

- 브랜치: `tooling/edge-history-color-blend-cleanup`, ⑰ 기준 `5bdd189`에서 직접 분기.
- 커밋: `c7514c2` 검증 harness(렌더러 무변경, 정리 전 빌드) → `113a6ad` 검증 도구 → `b86573c` C++ 정리.
- 대상: ⑰ `ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend`와 같은 실행의 native ④ `O-T2X-R`.
- 실행 흐름·분류·변경 이유: [audit-ko.md](audit-ko.md). 원래 ⑰은 비교 기준으로 남기며, 새 결과는 "⑰ 코드 정리본"으로 부른다.

## 출력 검증

RTX 3060 Ti, DX11 Release x64, SMAA Ultra, 1920×1061, hidden/windowed, fixed 60 Hz, still60/move120/still60 (play time 2.0부터).
각 명령은 독립 clean process이며 전후 CMAA2 0개와 Aggregate PASS를 확인했다. RGB는 PNG를 decode한 배열의 SHA-256이다.

| 검사 | Bistro | Minecraft |
|---|---|---|
| 정리 전 binary → 원래 ⑰ capture 기록 (⑰·④ 각 240프레임) | mismatch 0 | mismatch 0 |
| 정리 전 binary 반복 실행 (같은 binary) | mismatch 0 | mismatch 0 |
| **정리 전 → 정리 후 (⑰·④ 각 240프레임)** | **mismatch 0** | **mismatch 0** |
| 정리 후 → 원래 ⑰ capture 기록 | mismatch 0 | mismatch 0 |
| 시작 phase (f0 jitter) | ④ (0.25,0.25), ⑰ 0 | 같음 |
| 진단 36프레임 불변식 (정리 전/후) | PASS / PASS | PASS / PASS |
| 진단 파일 984개 byte 비교 | 계산에 쓰이는 파일 차이 0 | 차이 0 |

진단 프레임은 f0~2, 59~61, 124~133, 150~152(f150 명시 reset), 178~183, 200~202(f200 자원 재생성), 210~215, 230, 239다.
불변식: 선택 weight 정확히 0.8, 비선택 weight 0, next-history alpha = spatial alpha, 비선택 visible/history RGB = spatial,
선택 visible RGB = history RGB, 현재 raw edge ⊂ 선택 영역. reset·재생성 프레임에서는 선택 픽셀도 spatial과 같다.

Bistro에서 다른 파일은 reset·재생성 프레임의 "이전 history" 스냅샷뿐이다(⑰ f0, ④ f200). history가 무효인 프레임이라
resolve는 이 텍스처를 읽지 않고 current spatial을 previous로 쓴다. 같은 binary를 두 번 실행해도 같은 종류의 차이가 났다
(⑰ f0 2,533 px 최대 5, f200 재생성 텍스처). 그 밖의 출력·history·coverage·weight·velocity·입력·edge는 byte 단위로 같다.

출력이 같다는 것은 품질 문제가 해결되었다는 뜻이 아니다. Minecraft 얇은 경계 ROI의 f128·f130 약화/단절과 Bistro 의자
다리 단절은 정리 전후에 똑같이 남아 있다. 직접 검사한 sheet와 관찰은 [visual-inspection.json](visual-inspection.json)에 있다.

## 제외 실행

정리 전 Minecraft 반복 캡처 첫 시도는 재질 셰이더 초기 컴파일 로그 이후 프레임을 만들지 못해 1,200초 timeout으로 해당
프로세스만 종료했다. 결과로 쓰지 않았고 같은 binary로 다시 실행해 통과했다. 원인은 확정하지 않았다 ([excluded-runs.json](excluded-runs.json)).
Bistro 정리 전 진단 실행의 영수증은 runner가 `*Diagnostic` 명령의 보고서를 찾지 못해 사후 기록했다(`receipt_note`).

## 성능

아직 측정하지 않았다. 사용자 요청(2026-10-16, 게임 실행 중)에 따라 허용 후 진행한다. 정리는 GPU 명령을 바꾸지 않았으므로
성능 개선을 주장하지 않는다.

## 산출물 위치

- 원시 PNG/DDS: `D:/SMAAResearchCaptures/c17-cleanup-20261016/` (Git 미포함, 약 28 GB).
- 검사 sheet·전체 프레임·GIF: 같은 위치 `inspection/` (manifest: [inspection-media-manifest.json](inspection-media-manifest.json)).
- 실행 영수증: [runs.json](runs.json), 검증 결과: [output-verification.json](output-verification.json).
