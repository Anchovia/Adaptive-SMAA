# 2026-10-15 생성 미디어 정리

사용자는 코드·측정 기록·원본 장면 자료와 최소한의 ④·⑰ 시각 자료를 보존하고
오래된 캡처·GIF·영상을 정리하도록 승인했다. 이후 세 전용 출력 폴더의 10월 9일 이전
원시 PNG·DDS·RG8·RDC도 명시적으로 삭제 승인했다.
작업 브랜치는 tooling/generated-media-storage-cleanup이다.

## 보존 자료

④·⑰의 Bistro/Minecraft 각각 moving 126~131, transition 178~183, settled 230에서
52개 원본 PNG를 보존했다. 비교 GIF 2개, 연속 PNG sheet 2개, PDF와 메일 요약 ZIP을
합해 58개, 165,103,376 bytes다. 실제 보관 위치는 다음과 같다.

`C:/Users/USER/Desktop/research/Reports/Preserved-Baselines-20261015`

복사 전후와 모든 삭제 완료 후 SHA-256이 일치했다. 이 제한된 표본을 전체 시각 자료가
보존된 것으로 해석하지 않는다. 기존 전체 캡처의 재분석은 이제 재캡처가 필요하다.

## 삭제 완료

- 전체 미디어 ZIP 1개: 기존 artifact receipt의 SHA-256과 일치한 파일만 삭제.
- Deliverables 3개 폴더의 보기용 PNG·GIF·영상 3,295개.
- 명확히 식별된 page/contact-sheet 비교 이미지, Playback/CGVQM 중간 영상 615개.
- 아래 세 실제 출력 폴더의 오래된 원시 PNG·DDS·RG8·RDC 417,102개.

| 실제 원시 출력 폴더 | 삭제 파일 수 | 파일 크기 합계 bytes |
|---|---:|---:|
| D:/SMAAResearchCaptures | 146,558 | 400,734,699,127 |
| D:/SMAA-Research-Data/AutoBench | 188,750 | 422,569,852,951 |
| C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench | 81,794 | 161,796,946,316 |

원시 파일은 PNG 396,191개, DDS 14,190개, RG8 6,715개, RDC 6개다.
모두 last-write UTC가 2026-10-08 15:00:00 미만, 즉 2026-10-09 00:00:00 KST 이전이다.
새 원시 삭제의 파일 크기 합계는 985,101,498,394 bytes(917.45 GiB)이며,
앞선 정리를 포함한 누적 삭제는 421,013개다. Hardlink 등 저장 공간 공유 때문에
파일 크기 합계를 실제 확보 공간으로 해석하지 않는다.

원시 삭제의 오류와 이미 없던 파일 수는 모두 0이다. 삭제 목록의 모든 파일이 없음을
확인했고, 같은 날짜·경로·확장자 조건으로 다시 검색해 대상 0개를 확인했다.
세 폴더의 보존 파일 3,040개는 존재·크기·수정 시각이 모두 삭제 전과 동일했다.
CSV/JSON/로그·코드·문서·실행 파일·Git 추적 파일·장면·확보한 TSCMAA 원본은 제외했다.
④·⑰ 대표 자료 58개는 최종 해시 검사 PASS다.

원시 삭제 직전/직후 여유 공간 관측값은 deletion receipt에 기록했다. 직후 기준
C 약 224.9 GiB, D 약 768.8 GiB다. 정리 중 다른 활동의 영향도 있을 수 있으므로
순수 파일 삭제 효과나 파일 크기 합계와 동일한 값이라고 단정하지 않는다.

## 승인 및 실행 범위

최초 463,930개·약 1.14 TiB logical, 33개 경로의 광범위 삭제는 automatic approval
review가 규모·되돌리기 어려움·DDS/RG8/RDC 자산 승인 범위를 이유로 거절했다.
그 계획을 실행하거나 우회하지 않았다. 먼저 보기용 파생 미디어를 정리했고,
사용자가 위 세 폴더와 네 원시 확장자·날짜를 명시적으로 승인한 뒤 그 범위만 진행했다.
이 승인과 결과는 raw-capture-completion.json에 기록했다.

삭제 전에 실제 절대 경로·확장자·날짜·Git 보호 목록·계획 해시를 검증하고,
각 파일의 크기·수정 시각이 계획과 동일한 경우에만 삭제했다.
폴더 전체 재귀 삭제와 junction 경유 삭제는 수행하지 않았다.
메인 checkout의 AutoBench junction 대신 D의 실제 AutoBench 폴더를 한 번만 처리했다.

## 보관 기록과 재측정

summary.json은 전체 결과, raw-capture-completion.json은 추가 승인된 원시 삭제 결과다.
pending-approval.json은 처음 요청한 범위와 완료 상태를 보관한다.
자세한 파일별 계획·삭제 결과·실패 목록·보존 메타데이터는
`tmp/storage-media-cleanup-20261015`에 있다. 원시 삭제 ledger의 SHA-256과 집계도 기록했다.

Tools/SMAA/cleanup_generated_media.ps1의 원시 모드는 위 세 폴더와 고정된 날짜,
명시적인 승인 기록을 요구하며 네 확장자만 허용한다. 일반 생성 미디어 모드와 분리했다.
임시 config/TSV 및 원시 AutoBench 결과·미디어는 Git에 올리지 않는다.

기존 시각적 판정과 측정값은 과거 실행 조건의 기록으로 남긴다.
논문용 자료는 정리된 코드로 다시 측정한다. 기존 갤러리가 온전하다고 가정하지 않는다.