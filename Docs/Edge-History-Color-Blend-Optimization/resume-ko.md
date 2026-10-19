# ⑰ 화면 RGB 출력 보존 최적화: 측정 완료 (2026-10-19)

브랜치 `experiment/edge-history-color-blend-optimization`, 의존성: 정리 완료 커밋 `d2a6315`.
사용자의 "성능측정까지 다 진행해줘" 지시에 따라 두 장면 출력 검증, 본 benchmark, 정리 전후 ABBA,
세부 pass 진단을 완료했다. 신규 20개 clean process 모두 PASS, timeout/제외 실행 0개, 잔류 CMAA2 0개다.
최종 결과는 [report-ko.md](report-ko.md), 실행별 식별 정보는 [runs-20261019.json](runs-20261019.json),
완성도 검사는 [completion-audit-20261019.json](completion-audit-20261019.json)을 먼저 읽는다.

2026-10-19: 저장소 상태를 다시 확인하고 Release x64 재빌드에 성공했다(해상도 검사 포함).
새 exe SHA-256은 `C83A5E29CB5A5F79ECF1BC3F2850CE4763FD921C957B4328DBDCDA8BE35C2638`이다.
이 exe로 Bistro/Minecraft `opt-d` 캡처를 완료했고, 두 장면 모두 결합 모드 포함 6×240 RGB 검증 PASS다.
원본 full frame과 moving/transition/failure-window/settled nearest ROI를 직접 확인했다. 기존 구조 단절은 그대로다.
`verify-opt-d-*.json`, `visual-inspection-opt-d.json`, `inspection-opt-d-manifest.json`이 근거다.
두 장면 `opt-smoke-b`와 before/after의 네 smoke가 PASS했다. 본 benchmark 10개 process는 각각 mode당
300 warm-up + 4,800×6회, 별도 profile 두 process는 2,400×3회다. 측정 head는 `6ef1564`다.
초기 도구 보강 당시의 상태는 `continuation-*`에 과거 기록으로 보존한다. 렌더러/HLSL 변경과 기본값 채택은 없다.

## 이번 새 결과

- O2+O3 전체 AA: Bistro 0.135725 ms(동일 실행 ⑰ 대비 −8.468%, ④ 대비 −14.569%),
  Minecraft 0.233648 ms(⑰ 대비 −6.529%, ④ 대비 +2.178%). AA는 6회 반복 모두 감소했다.
- WholeFrame 평균: Bistro −0.631%, Minecraft −1.568%. AA와 같은 비율로 프레임이 빨라진 것은 아니다.
- O3 단독 대비 결합의 추가 AA 변화: Bistro −1.257%로 재현, Minecraft −0.729%이나 95% 구간이 0을 포함해 확정하지 않는다.
- O1은 일관된 개선이 없어 제외한다. O2 단독 AA 감소는 Bistro −0.547%, Minecraft −0.672%로 작다.
- 정리 전후 ABBA의 각 process 자체 ④ 기준 정규화 AA 변화는 Bistro −0.457%, Minecraft −0.057%다.
  build당 독립 process 2개인 작은 차이이므로 코드 정리 자체의 확정적인 속도 개선으로 주장하지 않는다.
- Minecraft 잔여 양의 비용은 새 profile에서 edge scope가 가장 컸다(④ 대비 +0.006756 ms).
  pattern/edge population 차이도 있어 raw-edge union의 순수 효과라고 단정하지 않는다.
- 기존 `interim-performance.json`과 과거 제외 실행은 2026-10-17 기록이며 이번 결과로 섞지 않는다.

## 남은 사용자 결정

측정과 분석은 완료했다. O3/결합의 채택만 사용자 결정 사항이다. 중간 visible texture의 alpha가
resolve lerp에서 current spatial alpha로 바뀐다. history alpha는 유지하고, 최종 표시 shader는 RGB와 alpha=1을 출력한다.
현재 후보 기본값은 모두 Off다. 채택 시 ⑰ 전용 설정에 적용하는 별도 커밋과 출력 재검증을 한다.
다른 연구 mode나 최종 8-case의 기본값을 함께 바꾸지 않는다. 새 성능 실행이 필요하면 사용자의 허용 및 GPU 유휴를 다시 확인한다.

원시 캡처는 `C:/Users/USER/Desktop/research/tmp/c17-resume-20261019/opt-d/capture/`에 2,880 PNG, 약 5.86 GiB다.
inspection 폴더에는 원본 픽셀 sheet와 0.5배속 GIF가 있다. 원본 자료 삭제·전체 옛 capture 복구는 하지 않았다.
