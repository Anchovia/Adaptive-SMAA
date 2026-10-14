# 2026-10-15 생성 미디어 정리

사용자가 코드·측정 기록·원본 장면 자료와 최소한의 ④·⑰ 시각 자료를 보존한 뒤
오래된 캡처·GIF·영상을 정리하도록 승인했다. 작업 브랜치는 tooling/generated-media-storage-cleanup이다.

## 완료

- ④·⑰: Bistro/Minecraft 각각 moving 126~131, transition 178~183, settled 230.
  52개 원본 PNG, 비교 GIF 2개, 연속 PNG sheet 2개, PDF 및 메일 요약 ZIP을 보존했다.
- Reports/Preserved-Baselines-20261015의 58개 파일은 복사 전후 SHA-256 일치다.
- 해시가 기존 artifact receipt와 일치하는 전체 미디어 ZIP 1개를 삭제했다.
- Deliverables 3개 폴더의 보기용 PNG·GIF·영상 3,295개, 이름과 위치가 명확한
  page/contact-sheet 비교 이미지 및 Playback/CGVQM 변환 중간 영상 615개를 삭제했다.
- 선택된 파생 미디어 3,910개는 모두 없어졌고 오류는 0개였다. 대표 파일 58개 해시는 재검증 PASS다.
- CSV/JSON/로그, 코드, 문서, 실행 파일, Git 추적 파일, 장면·원본 TSCMAA 자료는 삭제 대상에서 제외했다.
- 2026-10-09 00:00 KST 이전 자료만 적용했다. 새로운 파일·파일 변경은 삭제하지 않는다.
- 폴더 전체 재귀 삭제나 junction 경유 삭제를 수행하지 않았다. 실제 경로의 파일만 검증 후 삭제했다.

## 자동 검토에 따른 보류

463,930개·약 1.14TiB logical, 33개 경로의 광범위 삭제는 automatic approval review가 거절했다.
규모·되돌리기 어려움·DDS/RG8/RDC 등 진단 자산의 승인 범위가 이유다. 거절된 삭제를 우회하지 않았다.
안전한 대안은 파생 보기용 미디어와 변환 중간 영상에 한정했다. 원시 frame PNG와 DDS/RG8/RDC는 남아 있다.

추가 승인을 요청할 범위는 전용 원시 출력 3개 폴더의 2026-10-09 이전 파일 417,102개다.
정확한 종류·파일 크기 합계와 경로는 pending-approval.json에 기록했다. 파일 크기 합계는
hardlink 등 저장 공간 공유를 포함하므로 실제 확보 공간으로 해석하지 않는다.

## 보관 기록

자세한 목록·삭제 결과·실패 목록은 tmp/storage-media-cleanup-20261015에 보관한다.
모든 원본 이미지가 삭제됐다고 보고하거나 기존 갤러리가 온전하다고 가정하지 않는다.
기존 시각적 판정과 측정값은 과거 조건의 기록이며 논문용 자료는 정리된 코드로 새로 측정한다.
대표 자료는 Reports/Preserved-Baselines-20261015에 있다. 코드 정리 전후의 회귀 확인에 재사용할 수 있다.

Tools/SMAA/cleanup_generated_media.ps1은 날짜·실제 경로·보호 파일·계획 해시를 확인하고
생성된 일반 이미지/영상만 처리한다. Raw DDS/RG8/RDC 처리는 이 도구의 현재 허용 확장자에 없다.
본 task의 임시 config/TSV와 원시 AutoBench 결과·미디어는 Git에 올리지 않는다.
