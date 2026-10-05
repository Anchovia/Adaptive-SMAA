# ②·③·④·⑤·⑨·⑩ 긴 비교 영상 (2026-10-06)

요청한 여섯 구현을 같은 카메라 시점·frame index로 12초씩 새로 캡처했다. 기존 3초 자료의 약 4배이며, 움직이는 구간을 실제로 늘렸다. 프레임 반복·motion interpolation·타임라인 복제로 길이를 늘리지 않았다. AA 알고리즘, 성능 측정 조건 및 기존 품질 판정은 변경하지 않는다.

## 비교 구성

| 번호 | 처리 | Spatial SMAA | Temporal 범위 | Paired pattern |
|---|---|---|---|---|
| ② | 원본 SMAA 1X (`O-1X`) | On | 없음 | Off |
| ③ | 전체 화면 Temporal-only | Off | 전체 화면 원본 T2X-R | On |
| ④ | 원본 SMAA T2X-R (`O-T2X-R`) | On | 전체 화면 원본 T2X-R | On |
| ⑤ | 현재 1차-pass exact edge의 Temporal-only | Off | 현재 raw edge | Off |
| ⑨ | 현재·재투영한 직전 raw edge, eager fetch | On | 두 edge mask의 합집합 | Off |
| ⑩ | ⑨ + history RGB bilinear | On | ⑨와 같은 선택 | Off |

⑤는 공간 AA 보정은 생략하지만 선택 마스크를 위한 원본 edge 검출은 실행한다. ⑩의 alpha는 point이고 원본 adaptive history weight, spatial-frame history와 비선택 current 출력은 유지한다. 모두 corrected stencil lifecycle을 사용하며 camera/depth reprojection만 해당한다. ③·④와 ⑤·⑨·⑩의 차이는 edge 선택만의 효과가 아니다. 이 번호는 사용자 지정 비교 구성이며 연구의 최종 Adaptive 8-case 행렬과 구분한다.

## 브랜치와 범위

②·③·⑤는 각각의 수정 기준선에서 직접 분기한 독립 `tooling/*-twelve-second-capture` 브랜치다. ⑨·⑩는 공통 수정 기준선 `304f749`에서 분기한 `tooling/six-case-long-rgb-history`에 필요한 `9f46c9a`와 `0be83a7`만 가져왔다. capture extension commit은 각 브랜치의 검증 harness와 방법 기록 두 파일만 변경했고 renderer/shader 계산을 수정하지 않았다. 기본 240-frame 캡처와 기존 benchmark 타임라인은 유지했다. 자세한 commit·binary SHA-256은 `case*-method.json`, `case*-runs.json`, `source-validation.json`에 있다.

이 브랜치의 `Docs/Edge-Persistence-Bilinear-History-RGB` 결과 문서는 이전 확정 기록 `64e7021`에서 복원한 참조 자료다. 해당 이전 구현의 나머지 코드나 실험을 이 미디어 브랜치에 누적하지 않았다. 이번 요청에는 CGVQM·성능 재측정이나 채택 판정이 포함되지 않는다.

## 새 캡처 타임라인

- DX11 Release x64, RTX 3060 Ti, 원본 SMAA Ultra, 1920×1061, VSync Off, hidden capture.
- frame 0–719, fixed 60 Hz: 시작 정지 1초, 이동 10초, 이동 후 정지 약 1초. frame 60은 출발 pose, 660은 도착 pose다.
- 장면: Bistro·Minecraft, native camera time 2–12초와 14–24초의 두 경로씩.
- 명령마다 독립 CMAA2 프로세스, 실행 전·후 잔류 프로세스 0, clean runner timeout 900초. 요청 장면으로 저장 설정을 맞춘 뒤 시작했다.
- 각 브랜치에 native ④ 대조군을 함께 저장했다. extended presentation에서만 반복 mode와 무거운 trace DDS를 생략했다.

검증: 전체 원본 PNG 25,920장을 decode하여 해상도·index·mode-check PASS를 확인했다. 기존 확정 캡처와 겹치는 3,240개 frame은 RGB hash가 일치했다. 나머지 브랜치의 native ④ 8,640개 frame은 대응하는 ② 브랜치 ④와 일치했다. 표시할 고유 선택 원본은 17,280장이다. 일부 baseline/control 파일은 byte-identical immutable 자료의 hardlink로 물리 공간을 공유한다.

## 보기

`C:/Users/USER/Desktop/research/Deliverables/SMAA_2_3_4_5_9_10_Long_20261006/comparison.html`

- 배치: 위쪽 **②·③·④**, 아래쪽 **⑤·⑨·⑩**. 모든 panel은 동일 index·시점이다.
- 전체 화면 MP4 4개, ROI MP4 8개: 720 frames, 60 fps, 12초. 전체 decode로 frame 수·FPS·PTS 단조 증가를 검증했다.
- 느린 GIF 8개: 720 frames, 25 fps, 28.8초, 0.417배속. duration과 decoded palette RGB를 frame마다 검사했다.
- 8개 ROI: 의자/테이블, 창살, 꽃/잎, 차양/금속, 벽 이음선, 식생, 블록 경계, 나뭇잎/배경.
- ROI는 지정된 원본 좌표를 nearest 2배로 확대했다. 대표 PNG와 이동130–135·후반 이동480–485·이동→정지658–663·정지700–705의 연속6-frame sheet 32개를 함께 저장했다.

MP4는 H.264 CRF12/yuv420p, GIF는 공유256색 palette·dither Off로, 둘 다 손실이 있는 표시용 자료다. 원본은 `D:/SMAAResearchCaptures/six-case-long-20261006`, 구현·capture root는 `source-validation.json`과 media manifest에 기록했다. 품질 판단은 원본 PNG를 우선하며 이 미디어 검증 통과를 품질 개선 성공으로 표현하지 않는다. 실제 검사한 정지/연속 프레임과 실시간 재생 시청은 별개의 기록이다.

## 저장 공간

사용자가 요청한 C드라이브 정리를 완료했다. 연구 폴더의 완료된 임시 캡처 중복 14,585개 경로와 오래된 실패 덤프를 정리해 C 여유 공간이 약 9.9 → 67.7 GiB로 증가했다. 기존 캡처 이름과 내용은 유지했고 정리 후 전체 경로 hash mismatch 0이었다. 방법·복구 기록은 `storage-cleanup.md`와 `storage-cleanup.json`에 있다.
