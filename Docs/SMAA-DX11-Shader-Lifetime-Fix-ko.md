# DX11 비동기 셰이더 해체 순서 수정

2026-09-15 sharpening/segment 비교 중 앱 시작 단계에서 두 번의 종료가 발생했다.
16:36:42 Minecraft mask, 16:42:44 Minecraft quality 실행은 `0xc0000409`,
실행파일 offset `0x1ea819`로 종료되어 결과에서 제외했다. 이전 startup scene을
Bistro로 바꾸는 우회만으로는 재발을 막지 못했다.

## 확인한 근거

로컬 실행파일/PDB로 종료 주소를 조회한 결과 `abort+0x35`였다. 두 번째 Windows
crash dump의 예외 스레드 stack 메모리에는 `_purecall`, `vaShader.cpp:94`의
shader compile lambda, `vaThreading.cpp:116`의 background task lambda에 대응하는
주소가 있었다. 이 진단은 **stack 메모리에서 찾은 주소와 PDB의 대응**이며 정식 unwind로
확정한 전체 호출 스택은 아니다. Dump 및 PDB는 로컬에 보존하고 저장소에는 포함하지 않는다.

소스에서 독립적으로 다음 결함을 확인했다.

1. `vaShader::CreateShaderFromFile`은 `this`를 캡처한 비동기 작업에서 virtual
   `CreateShader()`를 호출한다.
2. DX11 Pixel/Compute/Hull/Domain/Geometry 파생 클래스는 해당 함수를 구현하지만,
   소멸자가 비어 있어 컴파일 완료 전에 파생 클래스 해체가 끝날 수 있었다.
3. 컴파일 완료 대기는 이후 `vaShaderDX11` 기반 소멸자에서야 수행했다. 이 클래스에는
   concrete `CreateShader` 구현이 없으므로 그 사이 worker의 virtual 호출이 순수가상
   함수에 도달할 수 있다. `vaShader`의 assertion은 Release에서 이 순서를 보장하지 않는다.

## 수정 범위

위 다섯 DX11 concrete 소멸자의 첫 작업으로 `WaitFinishIfBackgroundCreateActive()`를
호출한다. 파생 virtual 구현이 살아 있는 동안 작업을 완료한 뒤 기반 리소스를 해체한다.
Vertex shader는 이미 concrete 소멸자에서 대기하므로 변경하지 않는다.
DX12는 이번 실행 대상이 아니며 변경하지 않는다.

셰이더 수식, 후보, history, 카메라 경로 및 GPU pass 구성은 바꾸지 않는다. 다만 실행파일이
변경되므로 이후 비교는 같은 새 실행파일에서 short/mask/quality를 다시 수집한다.
수정 전 유효 자료는 별도 보존하고 새 캡처와의 hash bridge로 출력 변화를 확인한다.

## 검증 해석

Release x64 빌드와 새 실행파일의 독립 프로세스 캡처, 후보/비후보 및 기존 출력 hash 검증을
후속 결과 보고서에 기록한다. 유한 횟수의 정상 종료만으로 모든 경쟁 상태가 사라졌다고
단정하지 않는다. 이 수정은 실제 코드의 해체 순서 결함을 다루지만, 과거 블루스크린의 원인
확정이나 모든 `0xc0000409` 오류의 유일한 원인 증명은 아니다.
