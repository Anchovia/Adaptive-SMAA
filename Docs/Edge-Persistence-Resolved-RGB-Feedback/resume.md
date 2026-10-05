# ⑪ GPU 검증 재개 지점

## 2026-10-06 취침 전 추가 승인과 진행 작업

사용자가 성능 측정 보류를 해제하고 아래 작업을 모두 이어서 진행하도록 승인했다.
⑪의 두 scene eligible Smoke와 정식 Benchmark를 완료했다. 장면별 benchmark.json을 따른다.

1.⑪ 저장 진단50 ROI frame의 실패 위치 추적 완료: `failure-trace.json`과 report의
단계별 추적을 따른다. 선택·weight·feedback 검증 PASS와 품질 gate 미통과를 구분한다.
2.⑪ scene별 정식 Benchmark, 보조 CGVQM 및 비교 자료를 마무리한다.
3. 논문과 공개 구현을 조사해 얇은 선 소실·반짝임에 적합한 방법을 선정한다. TSCMAA
또는 기존 선택 구조에 미리 한정하지 않는다. **⑫는 새 독립 브랜치에서 구현**하고
속도·품질을 기존 방식과 비교하며 원본 연속 frame·GIF를 제공한다.
4.C·D의 불필요한 임시 자료를 정리한다. 유효한 원본 capture·reference·재현 자료는
보존한다. 초기 여유 공간은C 약34GiB/D 약67GiB였다.

아래 '게임 중 보류'는 이전 실행의 배경 기록이며 현재 작업 중단 지시가 아니다.

사용자가 게임 실행 중이라고 알려 GPU 작업을 보류했다. 진행 중이던 Bistro benchmark의
해당 CMAA2 PID만 종료했으며, 부분 timing은 사용하지 않는다. 관련 Smoke도 정식 성능
결과로 해석하지 않고 새 idle-GPU Smoke 뒤에만 Benchmark를 허용한다.

현재 구현 branch: `experiment/edge-persistence-resolved-rgb-feedback`.
AA 구현: `b793b74`; 실행 격리 수정: `573ecfa`.
실행 파일 SHA-256: `6369C6621C9389D65E4BD125B6BDE2A7A9DFFB52F966F542DEF007D3C0D95677`.

완료: 두 scene seed/reset Test6, 240-frame capture, ④·⑩ 총960 RGB frame bridge,
⑪ RGB feedback/velocity-alpha 보존/비선택 출력/연속 history 연결 검사, 원본 PNG 직접 검사.
게임 중에는 보존 입력의 CPU 분석과 presentation 생성만 진행했다.

게임 종료 후 아래 순서로 각각 별도 clean CMAA2 process를 실행한다. 작업 디렉터리는
`C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse`다.

1. `run_edge_resolved_rgb_feedback.ps1 -Phase Smoke -Scene bistro -RetryReason 'Concurrent game ended; idle GPU smoke'`
2. 같은 명령의 `-Scene minecraft`.
3. scene별 `-Phase Benchmark`; 완료 후 `analyze_edge_resolved_feedback_performance.py --scene <scene>`.
4. CMAA2 process가0개인 상태에서 `evaluate_resolved_feedback_cgvqm.py --scene <scene>`를
   CGVQM CUDA 전용 환경으로 실행한다. 기존④·⑩ 점수는 decoded RGB/reference bridge
   확인 뒤 재사용한다. 이번 실행 전에는⑪ CGVQM을 측정했다고 쓰지 않는다.
5. scene별 `-Phase Capture -Frames 720 -StartTime 2`,
   `verify_resolved_feedback_long_capture.py --scene <scene>`로 원본 long control을 대조한다.
6. 별도 long 출력 디렉터리에 `create_resolved_feedback_playback.py --frames 720 --output <dir>`.
7. paired 전체 AA/temporal 시간과 직접 원본 프레임 검사를 함께 보고한다.

240-frame GIF/MP4는 현재 캡처로 만들 수 있다. 720-frame은 실제 추가 렌더를 해야 하며,
짧은 frame을 반복하거나 보간해서 긴 실험이라고 표현하지 않는다.
