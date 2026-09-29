# 실행 중 진단 기록

- 최초 소스 감사 스크립트에 별도 `SMAAReprojection.hlsl`이라는 잘못된 파일명을 넣어
  파일 찾기 검사가 실패했다. 실제 reprojection은 `SMAAWrapper.hlsl`에 있으므로
  검사 대상 경로를 교정했고 원본 wrapper/HLSL/공간 함수 동일성과 FXC 검사가 통과했다.
  Renderer 코드를 고친 것이 아니라 감사 도구의 파일명 오류를 교정한 것이다.
- Minecraft 첫 capture `20260929_084434`(PID 6408)는 캡처 폴더 생성 뒤 mode PNG가
  0개인 상태로 수분간 진행하지 않았다. CPU 누적 약 2.27초, 로그 0바이트, 완료 report가
  없었으며 노출된 앱 목록에서도 해당 프로세스의 오류창은 확인하지 못했다.
  원인을 shader/driver 또는 알고리즘 오류로 단정하지 않는다.
- 프로세스 이름과 실행파일 경로를 확인해 이 PID만 종료했다. Runner는 exit -1로 실패했고
  성공 receipt에 포함되지 않았다. 동일 실행파일로 clean-process 재시도를 수행했다.
  이 실행의 빈 폴더는 실패 흔적으로 유지하며 품질/성능 수치에 사용하지 않는다.
- 재시도 `20260929_084926`(PID 11356)는 5 mode×240프레임을 모두 저장하고 Aggregate PASS,
  정상 종료 및 잔류 CMAA2=0을 통과했다. 소스/실행파일/설정 변경 없이 재시작만 수행했으며
  앞선 무진행의 원인은 미확정으로 남긴다.
- 최초 Bistro timing smoke `20260929_085552`는 세부 AA scope와 wall interval은 기록했으나
  WholeFrame GPU가 0이어서 Aggregate FAIL로 거부했다. 일부 값을 성공 결과로 사용하지 않는다.
  원본 `CMAA2Sample::OnTick`에서 BeginFrame을 두 번 호출하고 EndAndPresentFrame은 한 번
  호출하는 구조를 확인했다. 첫 WholeFrame scope가 끝나지 않는 계측 문제를 별도 tooling
  브랜치로 교정하며, 출력 동일성을 다시 확인한 뒤 성능을 재측정한다. 앞선 무진행과의
  인과관계는 아직 단정하지 않는다.
