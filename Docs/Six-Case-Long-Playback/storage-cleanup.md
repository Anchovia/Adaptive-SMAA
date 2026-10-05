# 2026-10-06 연구 저장 공간 정리

사용자의 C드라이브 정리 요청에 따라 연구 폴더에서 완료된 임시 캡처의 중복본과 오래된 실패 프로세스 덤프를 정리했다.

## 확인한 용량과 결과

- 연구 폴더의 논리적 파일 크기: 약 244.6 GiB. C드라이브 전체 사용량이 모두 연구 때문이라는 뜻은 아니다.
- C드라이브 여유 공간: 9.9 GiB → 67.7 GiB. 작업 중 관측된 회수량은 약 57.9 GiB다.
- byte-identical 캡처 중복 14,585개 경로: 기존 이름과 내용을 유지하면서 NTFS hardlink로 동일한 물리 파일을 공유하도록 정리했다.
- 삭제한 실패 프로세스 덤프: `tmp/candidate-selection-gate/stalled-source-mask.dmp`, 2.387 GiB. 해당 실패의 로그와 보고서는 보존했다.
- 정리 후 14,585개 경로의 SHA-256 검증: mismatch 0, PASS.

세 대상은 `tmp/worktrees/standard-t2x-reuse/tmp/spatial-cost-captures`, `eager-spatial-mask-captures`, `velocity-load-captures`의 완료된 PNG/DDS다. 소스 코드, 유일한 기준 영상, 실험 보고서와 제출 자료는 삭제하지 않았다. 링크된 캡처는 변경하지 않고 후속 출력은 새 경로에 생성한다. 폴더의 논리적 크기는 그대로 보일 수 있지만 실제 디스크의 여유 공간은 증가했다.

1024 hardlink 제한에 걸린 한 시도에서는 해당 파일을 즉시 복원했다. 이후 링크 그룹 크기를 제한하여 재실행하고 전체 경로를 검증했다. 실패와 복구 기록은 `storage-cleanup.json`에 보존한다.

새 긴 캡처는 `D:/SMAAResearchCaptures/six-case-long-20261006`에 저장했다. 그중 완료된 ②·③ 캡처의 동일한 정지 프레임·④ 대조군 중복도 같은 방식으로 정리해 약 9.5 GiB의 물리 공간을 회수했다. 기존 D드라이브 연구 자료는 이 정리의 대상이 아니다.
