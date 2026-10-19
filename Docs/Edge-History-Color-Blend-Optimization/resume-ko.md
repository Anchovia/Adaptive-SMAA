# ⑰ 출력 보존 최적화: 진행 상태와 재개 절차 (2026-10-19 인계 재개)

브랜치 `experiment/edge-history-color-blend-optimization`, 의존성: 정리 완료 커밋 `d2a6315`.
사용자 요청으로 다시 중단했다. **성능 측정은 사용자가 다시 허용할 때까지 실행하지 않는다.**
PC 사용 중에는 창 크기가 바뀌어 품질 캡처도 무효가 될 수 있으므로 CMAA2 실행 자체를 멈췄다.

2026-10-19: 저장소 상태를 다시 확인하고 Release x64 재빌드에 성공했다(해상도 검사 포함).
새 exe SHA-256은 `C83A5E29CB5A5F79ECF1BC3F2850CE4763FD921C957B4328DBDCDA8BE35C2638`이다.
아직 이 exe로 CMAA2를 실행하지 않았다. 캡처/성능 실행 범위에 대한 사용자 답변을 기다린다.
검증 도구 보완과 테스트, 다음 실행 명령은 [continuation-ko.md](continuation-ko.md), 기계 판독 기록은
[continuation-20261019.json](continuation-20261019.json)에 있다. 렌더러/HLSL 변경과 기본값 채택은 없다.

## 지금까지 확정된 것

- O1/O2/O3 각각 두 장면 240프레임 RGB가 ⑰·정리본 캡처·원래 ⑰ 기록과 동일 (`verify-opt-a-*`, `verify-opt-b-*`).
  O3 원본 프레임 직접 검사(Minecraft f124~133/f178~183/f230, Bistro f126~131/f178~183/f230, full f130)에서 ⑰와 같고
  기존 얇은 구조 문제도 그대로다.
- 진단 pass profile(두 장면)과 Bistro 정식 benchmark(6×4,800): `interim-performance.json`.
  Bistro 전체 AA는 ⑰ 대비 O3 −7.34%, O2 −0.50%, O1 +1.16%(느려짐, 제외). ④ 대비 ⑰ −6.95%, ⑰+O3 −13.78%.
- Minecraft 정식 benchmark는 시작 정지로 제외. 결합 모드(O2+O3) 캡처는 창 크기 변경으로 무효.

## 재개 순서

1. `CMAA2.exe` 0개, GPU 유휴(P8), 게임/PC 사용 없음 확인.
2. 재빌드 완료(`535d0b3` 출력 크기 검사 포함). 실행 전 exe hash가 위 값과 같은지 확인.
3. 캡처 허용 후 새 저장 위치 `C:/Users/USER/Desktop/research/tmp/c17-resume-20261019`를 `-OutputRoot`로 지정해
   6 mode 출력 캡처 `-Label opt-d` (Bistro, Minecraft) → `verify_color_blend_optimization.py`로 결합 모드 포함 RGB 동일성 확인.
   runner는 이전 실행이 남긴 1902×1001 창 설정을 실행 전에 기준 1920×1061, windowed로 복원한다.
   verifier는 이제 6개 모드·240개 PNG·모든 frame 위상 검사를 요구하며 실패/불일치 시 종료값 1을 반환한다.
   이전 5-mode `opt-a/b`는 새 6-mode gate를 통과할 수 없다. 과거 5-mode 검증 결과를 철회하는 뜻은 아니다.
   Minecraft 시작 정지가 이전 프로세스 종료 직후 반복됐으므로 명령 사이 대기를 두는 것을 시도한다(원인은 미확정).
4. **사용자 허용 후**: 장면별 Smoke → Benchmark(`-Label opt-bench-b`), 그다음 Preservation harness ABBA
   (`c17-before` CA01DD… / `c17-cleanup` 47E69F…, 각 장면 전·후·후·전).
5. `analyze_color_blend_performance.py`로 같은 실행의 ④·⑰ 대비 변화율, 반복별 변동, WholeFrame을 정리하고
   최종 보고서·④ vs 최적화본 GIF·커밋/푸시.

O3(및 결합 모드)는 visible alpha를 spatial alpha로 바꾼다(PNG·화면 미사용). 채택 여부는 사용자 결정 사항이다.
