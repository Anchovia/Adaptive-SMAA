원본 SMAA / Adaptive SMAA 게임 비교 묶음 (ReShade 6.8.0)

게임 화면에서 원본 SMAA Ultra와 Adaptive SMAA Ultra를 키 하나로 바꿔 가며 보기 위한 묶음이다.
ReShade 설치 프로그램은 쓰지 않는다. 설정은 모두 끝나 있으므로 파일을 게임 폴더에 넣고 게임을 켜면 된다.


1. 쓸 수 있는 게임

- 64비트 DirectX 10, 11, 12 게임에 그대로 쓴다. 다른 경우는 6장을 본다.
- 직접 가진 싱글 플레이 또는 오프라인 게임에만 쓴다.
- 온라인 게임과 안티치트가 있는 게임에는 쓰지 않는다. dxgi.dll을 바꿔 넣는 방식이라 계정이 정지될 수 있다.


2. 설치

1) 게임 실행 파일(.exe)이 있는 폴더를 연다. 게임에 따라 bin\x64 같은 하위 폴더에 있다.
2) 그 폴더에 dxgi.dll이 이미 있으면 덮어쓰지 않는다. 다른 모드나 프로그램이 쓰는 파일일 수 있으므로 이 묶음은 쓰지 않는다.
3) 이 묶음의 game-folder 폴더 안에 있는 파일과 폴더를 모두 2)의 폴더에 복사한다.
   dxgi.dll
   ReShade.ini
   ReShade-AdaptiveSMAA-Presets 폴더
   reshade-shaders 폴더
4) 게임 안의 안티에일리어싱(FXAA, TAA, SMAA 등)은 끈다. 켜 두면 게임 AA 위에 SMAA가 한 번 더 걸려 차이를 보기 어렵다.
5) 게임을 켠다. 처음 몇 초 동안 화면 위쪽에 ReShade 안내 문구가 뜨면 제대로 들어간 것이다.
   첫 실행에서는 셰이더를 컴파일하느라 몇 초 걸린다.


3. 키

- F7 원본 SMAA Ultra (SweetFX SMAA.fx)
- F8 Adaptive SMAA Ultra
- Scroll Lock 효과 전체 끄기와 켜기 (AA 없는 화면과 비교할 때)
- Home ReShade 창 열기와 닫기
- Print Screen 스크린샷

처음에는 원본 SMAA로 시작한다. 지금 켜진 프리셋 이름은 화면 왼쪽 위에 작게 나온다.
두 프리셋은 같은 Ultra 설정과 같은 루마 경계 검출을 쓰고 탐색 길이만 다르다.
같은 장면에서 F7과 F8을 번갈아 누르며 얇은 선, 계단 현상, 경계의 흐림을 본다.
CMAA2 데모에 이 묶음을 넣어 본 결과 차이는 길고 거의 수평이나 수직인 경계에서 가장 컸다.
그런 경계의 일부를 Adaptive가 원본보다 덜 부드럽게 처리해 계단 한 칸이 조금 더 남았다.


4. 시간 보기

Home으로 ReShade 창을 열고 Statistics(통계) 탭을 누르면 효과별 GPU 시간이 나온다.
카메라를 멈춘 같은 장면에서 F7과 F8을 바꿔 가며 숫자를 본다.
숫자는 프레임마다 흔들리고 게임과 드라이버 상태의 영향을 받으므로 참고로만 본다.
연구에서 쓴 정식 측정과 같은 조건이 아니다.


5. 스크린샷

Print Screen을 한 번 누르면 게임 폴더의 ReShade-Screenshots 폴더에 PNG 두 장이 생긴다.
파일 이름 끝이 Before인 것은 효과를 넣기 전 화면이고 After인 것은 효과를 넣은 화면이다.
파일 이름에 프리셋 이름(Original-SMAA-Ultra 또는 Adaptive-SMAA-Ultra)이 들어간다.
비교할 때는 카메라를 움직이지 않고 F7을 누른 뒤 찍고 F8을 누른 뒤 다시 찍는다.
ReShade 창이나 안내 문구는 스크린샷에 들어가지 않는다.


6. 다른 게임에 쓸 때

game-folder의 dxgi.dll 하나만 바꾸고 나머지 파일은 그대로 복사한다.

- 32비트 DirectX 10, 11, 12 게임
  other-games\ReShade32.dll을 게임 폴더에 복사하고 이름을 dxgi.dll로 바꾼다.
- DirectX 9 게임
  64비트 게임은 game-folder\dxgi.dll의 이름을 d3d9.dll로 바꾼다.
  32비트 게임은 other-games\ReShade32.dll의 이름을 d3d9.dll로 바꾼다.
- OpenGL 게임
  같은 방식으로 이름을 opengl32.dll로 바꾼다.
- Vulkan 게임
  이 묶음으로는 쓸 수 없다. Vulkan은 ReShade 설치 프로그램으로 시스템에 등록해야 해서 제외했다.

게임이 어떤 API를 쓰는지 모르면 dxgi.dll로 먼저 해 보고 안내 문구가 뜨지 않으면 지운 뒤 다른 이름으로 해 본다.


7. 제거

게임을 끄고 게임 폴더에서 아래 항목을 지운다.

   dxgi.dll (또는 바꾼 이름의 dll)
   ReShade.ini
   ReShade.log
   ReShade-AdaptiveSMAA-Presets 폴더
   reshade-shaders 폴더
   ReShade-Screenshots 폴더 (스크린샷을 보관하려면 다른 곳으로 옮긴다)

ReShade는 컴파일한 셰이더를 임시 폴더에 저장한다. 탐색기 주소창에 %TEMP%\ReShade를 입력해 그 폴더도 지울 수 있다.
게임 파일은 바꾸지 않으므로 위 항목을 지우면 원래 상태로 돌아간다.


8. 문제가 생기면

- 안내 문구가 뜨지 않는다
  .exe가 있는 폴더에 넣었는지 확인한다. 게임 API가 다르면 6장대로 이름을 바꾼다.
  게임 폴더의 ReShade.log에 원인이 적힌다.
- F7, F8 키가 게임 키와 겹친다
  게임을 끈 뒤 ReShade.ini의 PresetShortcutKeys 값을 바꾼다. 네 숫자가 키 하나다.
  첫 네 숫자가 원본, 다음 네 숫자가 Adaptive이고 각 묶음의 첫 숫자만 키 코드로 바꾼다.
  키 코드 예시 F5 116, F6 117, F9 120, F10 121, F11 122, F12 123, Insert 45, Delete 46, End 35, Page Up 33, Page Down 34
  ReShade는 게임을 끌 때 ReShade.ini를 다시 저장하므로 게임이 켜진 동안 고친 내용은 사라진다.
- 프리셋이 바뀌지 않는다
  화면 왼쪽 위 프리셋 이름을 확인한다. ReShade 창이 열려 있으면 Home으로 닫고 다시 누른다.


9. 알아 둘 점

- Adaptive SMAA는 경계의 대비가 낮을수록 탐색 길이를 짧게 잡는다. Ultra에서 대비 단계별 탐색 길이는 3, 8, 20단계다(원본은 모두 32단계).
  단계 기준값은 CMAA2 데모에서 대비 구간마다 바뀐 경계 픽셀이 1% 이하가 되도록 정했다.
  게임마다 화면 내용이 달라 바뀌는 정도도 데모와 다를 수 있다.
- 데모와 ReShade는 루마를 구하는 방법과 경계 검출 함수의 세부가 조금 다르다. 같은 화면이라도 픽셀 값이 데모와 똑같지는 않다.
- ReShade에는 GitHub에서 새 버전이 있는지 확인해 알려 주는 기능이 들어 있다. ReShade 자체 기능이고 끄는 설정은 찾지 못했다.
- 이 묶음은 공식 SMAA나 SweetFX 배포본이 아니다. 출처와 라이선스는 licenses 폴더에 있다.
- 각 파일의 SHA-256은 MANIFEST-sha256.txt에 있다.
