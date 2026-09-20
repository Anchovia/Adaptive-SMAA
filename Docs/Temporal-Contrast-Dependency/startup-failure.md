# 측정 시작 실패 기록

2026-09-20 10:30:30 KST, 첫 Minecraft dependency benchmark 실행
`20260920_103030`이 시작 직후 종료 코드 `-1073740791` (`0xc0000409`)로 종료됐다.
완성된 AutoBench CSV가 없고 clean runner가 실패 처리했다. 정식 수치에서 전부 제외한다.

- EXE SHA-256: `0132c9a3313abf8e31efa8e7774bbe65ebc898d03f1b7e1f10debdb93e3328b0`
- Windows Application Error 1000, CMAA2.exe PID 17224, module offset `0x1add25`.
- 실행 종료 후 CMAA2 프로세스 0개.
- 로그는 장면/설정 읽기와 DX11 초기화 직후 끝났다.
- 로컬 minidump: `C:/Users/USER/AppData/Local/CrashDumps/CMAA2.exe.17224.dmp`.
- 현재 EXE/PDB로 예외 thread 16480의 stack 메모리에서 코드 주소 후보를 해석했다.
  `_purecall`, `mtx_do_lock`, `vaShader.cpp:94`의 shader compile lambda,
  `vaThreading.cpp:116`의 background task lambda가 포함됐다.
  정식 stack unwind가 아닌 return-address 후보 검색이므로 확정 호출 경로나 원인으로 표현하지 않는다.
- 이 브랜치의 기존 `vaShader.cpp`가 capture한 `this`를 background 작업에서 사용하고,
  concrete DX11 shader 일부 destructor가 비어 있으며 base destructor에서 작업을 기다리는 구조를
  확인했다. 수명 경쟁 가능성은 있지만 해당 객체를 특정하거나 재현한 것은 아니다.
  이번 gate에서 renderer 공통 수명 코드는 수정하지 않았다.

동일 EXE로 독립 재실행한 `20260920_103305`는 PID 11084에서 정상 종료(exit 0)했다.
5 mode ×3회 ×4,800 frame의 완성된 PASS CSV와 종료 후 잔류 CMAA2 프로세스 0개를 확인했다.
성공 실행의 receipt/CSV만 분석했으며 실패 실행과 섞지 않았다.
재실행 성공으로 startup 안정성 문제가 해결됐다고 주장하지 않는다.
임시 분석 기록은 `tmp/dependency-startup-stack.txt`, `tmp/dependency-startup-failure.log`이며
개인 메모리를 포함할 수 있는 minidump 자체는 저장소에 올리지 않는다.
