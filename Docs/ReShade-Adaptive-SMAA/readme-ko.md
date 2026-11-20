# ReShade용 Adaptive SMAA 묶음

브랜치

- `experiment/reshade-adaptive-smaa` (이 문서, `tooling/adaptive-tier-minimal` 644f836에서 시작)
- `tooling/adaptive-tier-minimal` 644f836 (데모 쪽 Adaptive 1% 단계 정리 브랜치)

## 목적

게임 화면에서 원본 SMAA Ultra와 Adaptive SMAA Ultra를 키 하나로 바꿔 볼 수 있는 ReShade 묶음을 만들었다. 사용자는 묶음의 `game-folder` 안에 있는 파일을 게임 실행 파일 폴더에 넣고 게임을 켜면 된다. ReShade 설치 프로그램은 실행하지 않았다.

묶음 위치는 `C:\Users\USER\Downloads\ReShade-AdaptiveSMAA\`다. 외부 파일은 Git에 넣지 않았고 이 브랜치에는 Adaptive 셰이더 생성 도구, 설정 원본, 묶음 생성 도구, 데모 검증 도구와 문서만 넣었다.

## 외부 파일

모두 공식 출처에서 받았고 사용자 허락을 받은 목록과 크기가 같았다. 원본은 `D:\SMAAResearchCaptures\reshade\`에 보관했다.

| 파일 | 출처 | 크기(B) | SHA-256 |
|---|---|---:|---|
| ReShade_Setup_6.8.0.exe | reshade.me | 4,075,064 | 207aea16…3c0b4 |
| ReShade64.dll | 위 설치 파일 안의 압축 데이터 | 5,255,448 | b2945c29…f02d08da |
| ReShade32.dll | 위 설치 파일 안의 압축 데이터 | 4,136,216 | 538998f6…518b88 |
| ReShade.fxh | crosire/reshade-shaders slim fd00221 | 4,250 | 6dabfbba…b30174f |
| ReShadeUI.fxh | crosire/reshade-shaders slim fd00221 | 9,930 | 78adf672…70eb901 |
| SMAA.fx | CeeJayDK/SweetFX 93ddf39 | 9,523 | fd6591ee…59c0007 |
| SMAA.fxh | CeeJayDK/SweetFX 93ddf39 | 57,679 | ee18b0f3…5818c8310 |
| AreaTex.png | CeeJayDK/SweetFX 93ddf39 | 30,346 | 0044e6b4…3077beed |
| SearchTex.png | CeeJayDK/SweetFX 93ddf39 | 126 | 55a97853…84fd96f3 |
| LICENSE (MIT) | CeeJayDK/SweetFX 93ddf39 | 1,076 | 9b2e0b3f…bce51 |

DLL은 설치 파일을 실행하지 않고 파일 안의 ZIP 데이터에서 꺼냈다. 전체 해시는 `Tools/ReShade/make_reshade_bundle.py`의 `PINNED`와 이 폴더의 `bundle-manifest.txt`에 있다. 묶음 도구는 해시가 다르면 묶음을 만들지 않는다.

## AdaptiveSMAA.fx와 AdaptiveSMAA.fxh

`Tools/ReShade/make_adaptive_smaa_fx.py`가 SweetFX의 `SMAA.fx`, `SMAA.fxh`에서 두 파일을 만든다. 원본 해시를 확인한 뒤 정확히 한 번씩 맞아야 하는 문자열 치환만 한다. 결과는 `Tools/ReShade/Shaders/`에 있다. 원본 대비 `.fxh`는 +82/−15줄, `.fx`는 +42/−87줄이다. `.fx`에서 지운 줄은 대부분 사용자 지정 프리셋 uniform이다.

`.fxh`에서 바꾼 내용은 정리 브랜치의 데모 `SMAA.hlsl` 변경과 같다.

- 네 프리셋 정의 뒤에 프리셋별 1% 단계 블록을 넣었다. Ultra는 T1 19.5/255, T2 51.5/255, 탐색 3/8/20단계이고 최상위 단계 20이 Ultra의 32를 대신한다.
- 경계 검출 함수 다섯 개(루마, 루마 predication, 색, 색 predication, 깊이)가 `float3`를 돌려주고 세 번째 채널에 단계(0, 0.5, 1)를 쓴다. 깊이 경계는 최상위 단계를 쓴다.
- 블렌딩 가중치 패스가 단계를 읽어 `maxSearchSteps`를 고른다.
- 네 방향 탐색의 끝 좌표는 최상위 단계에서 VS가 계산한 `offset[2]`를 그대로 쓰고 낮은 단계에서는 `원점 ± 2·단계·픽셀`을 쓴다(`SMAA_SEARCH_END`).
- `ADAPTIVE_SMAA_TIERS_AT_PRESET_MAX=1`이면 세 단계가 모두 프리셋 최대 탐색 길이를 쓴다. 이 설정의 출력은 원본 `SMAA.fx`와 같아야 하며 검증에만 썼다.

`.fx`는 SweetFX 래퍼의 패스, 샘플러, 스텐실 사용을 그대로 두고 아래만 바꿨다.

- 프리셋 정의가 없으면 Ultra를 쓴다. 단계 기준값이 네 고정 프리셋에만 있으므로 사용자 지정 프리셋과 그 uniform을 지웠다.
- ReShade는 이름이 같은 텍스처를 효과 사이에서 공유하므로 텍스처 이름에 `AdaptiveSMAA_`를 붙였다. 경계 텍스처는 RG8에서 RGBA8로 바꿨다.
- `EdgeDetectionType` 기본값을 1(색)에서 0(루마)으로 바꿨다. 단계 기준값을 루마 경계로 정했기 때문이다.
- 디버그 보기에 단계 보기(파랑 최단, 초록 중간, 빨강 최상위)를 더했다. 경계 보기는 RG 채널만 보여 원본과 같게 했다.
- technique 이름은 `AdaptiveSMAA`다.

## 데모 코드와 다른 점

| 항목 | CMAA2 데모 | ReShade |
|---|---|---|
| 경계 검출 입력 | 톤매핑 직후 선형 RGB의 제곱근에 Rec.601 가중치(0.299, 0.587, 0.114)를 곱한 루마를 따로 저장해 LumaRaw 경계 검출에 쓴다 | 백버퍼의 sRGB 인코딩 값을 그대로 읽고 Rec.709 가중치(0.2126, 0.7152, 0.0722)로 루마를 구한다 |
| 처리 대상 | 데모 UI를 그리기 전 장면 색 | 게임이 Present하는 백버퍼(게임 UI가 있으면 함께 처리) |
| 단계 읽기 | point 샘플러 | SweetFX가 `SMAASamplePoint`를 선형 샘플러로 정의한다. 픽셀 중심에서 읽으므로 같은 값이다 |
| predication | `#if SMAA_PREDICATION` 분기 | 별도 함수 두 개. 둘 다 단계를 쓰도록 바꿨다 |
| 색 경계의 left-left 차이 | `abs(C − Cleftleft)` | `abs(Cleft − Cleftleft)`. 루마 경계를 쓰는 이번 프리셋에는 영향이 없다 |
| 단계 지우기 | 경계 타깃을 지울 때 함께 지워지고 따로 지우지 않는다 | `ClearRenderTargets`가 RGBA8 경계 텍스처 네 채널을 모두 지운다 |
| 프리셋 | 네 고정 프리셋 | 네 고정 프리셋. 정의가 없으면 Ultra |

루마 계산이 달라서 같은 장면이라도 finalDelta 분포와 단계 비율이 데모와 다르다. 단계 기준값은 데모 루마로 정한 값을 그대로 썼다.

## 묶음 구성

```
ReShade-AdaptiveSMAA\
  README-ko.txt                    설치, 키, 시간 보기, 스크린샷, 제거, 다른 게임용 이름 바꾸기
  MANIFEST-sha256.txt
  game-folder\                     게임 실행 파일 폴더에 넣는 파일
    dxgi.dll                       ReShade64.dll
    ReShade.ini
    ReShade-AdaptiveSMAA-Presets\Original-SMAA-Ultra.ini
    ReShade-AdaptiveSMAA-Presets\Adaptive-SMAA-Ultra.ini
    reshade-shaders\Shaders\ReShade.fxh, ReShadeUI.fxh
    reshade-shaders\Shaders\SweetFX\SMAA.fx, SMAA.fxh
    reshade-shaders\Shaders\AdaptiveSMAA\AdaptiveSMAA.fx, AdaptiveSMAA.fxh
    reshade-shaders\Textures\SweetFX\AreaTex.png, SearchTex.png
  other-games\ReShade32.dll        32비트 게임용(이름을 바꿔 쓴다)
  licenses\SweetFX-LICENSE.txt, THIRD-PARTY-ko.txt
```

`ReShade.ini`의 키 값은 ReShade 6.8.0 소스(`runtime.cpp`, `runtime_gui.cpp`)에서 확인했다.

| 설정 | 값 |
|---|---|
| 셰이더·텍스처 경로 | `.\reshade-shaders\Shaders\**`, `.\reshade-shaders\Textures\**` |
| 시작 프리셋 | Original-SMAA-Ultra |
| 프리셋 키 | F7 원본(118), F8 Adaptive(119) |
| 효과 전체 끄기/켜기 | Scroll Lock(145) |
| ReShade 창 | Home(36) |
| 스크린샷 | Print Screen(44), PNG, Before/After 두 장, 오버레이 제외, 알파 255 |
| 스크린샷 폴더와 이름 | `.\ReShade-Screenshots`, `%AppName% %Date% %Time%_%Count% %PresetName% %BeforeAfter%` |
| 튜토리얼 | 건너뜀(`TutorialProgress=4`) |
| 화면 표시 | 왼쪽 위에 프리셋 이름 |
| 성능 모드 | 끔(`PerformanceMode=0`) |
| 꺼진 효과 컴파일 건너뛰기 | 끔(두 효과를 시작할 때 모두 컴파일) |

두 프리셋은 `PreprocessorDefinitions=SMAA_PRESET_ULTRA`가 같고 `EdgeDetectionType=0`이다. 전처리 정의가 같으면 ReShade가 프리셋을 바꿀 때 다시 컴파일하지 않는다. 검증 로그에서도 F7과 F8 사이 전환에는 컴파일이 없었고 전처리 정의가 다른 시험용 프리셋으로 바꿀 때만 컴파일이 있었다.

README는 사용자의 싱글·오프라인 게임에만 쓰고 온라인·안티치트 게임에는 쓰지 않도록 적었다. 32비트, DirectX 9(`d3d9.dll`), OpenGL(`opengl32.dll`)은 DLL 이름만 바꾸면 되도록 안내했고 Vulkan은 설치 프로그램 등록이 필요해 제외했다. 이 세 경우는 데모에서 시험하지 않았다.

## 데모 검증

### 방법

`Tools/ReShade/run_reshade_still.ps1`이 한 장면을 한 CMAA2 프로세스로 실행했다.

1. 실행 전 CMAA2 프로세스 0개, GPU P8, 60초 이상 입력 없음을 확인했다. 첫 시도는 37초 전에 입력이 있어 시작하지 않았고 이후 스크립트가 입력 없는 60초를 기다린 뒤 시작했다.
2. 실행 파일 폴더를 `Projects/CMAA2_RS`에 복사하고 묶음 `game-folder`를 넣었다. 빌드 폴더 `Projects/CMAA2`에는 dxgi.dll이 없음을 실행 전후에 확인했다.
3. 시험용으로 복사본의 `ReShade.ini`만 바꿨다. 스크린샷 키 F9, 파일 이름, 프리셋 사본 저장(`SavePresetFile=1`), 셰이더 캐시를 복사본 안에 두는 설정과 시험용 프리셋 두 개(F5 단계 보기, F6 `ADAPTIVE_SMAA_TIERS_AT_PRESET_MAX=1`)를 더했다.
4. `-smaaReShadeStillCapture`는 데모 AA를 None으로 두고 UI를 숨긴 채 고정 60 Hz 타임라인의 세 자세(play time 2.0, 3.0, 4.0)를 차례로 만든다. 자세마다 90프레임을 그린 뒤 표시 파일을 쓰고 스크립트의 신호를 기다린다. 창은 숨김 상태이고 해상도는 1920×1061이다.
5. 스크립트는 자세마다 F7, F8, F5, F6 순서로 숨김 창에 키 메시지(PostMessage)를 보내 프리셋을 바꾸고 F9로 스크린샷을 찍었다. ReShade가 함께 저장한 프리셋 사본과 파일 이름의 프리셋 이름으로 찍을 때 켜진 프리셋을 확인했다.
6. 실행 후 CMAA2 프로세스 0개를 확인하고 로그와 설정을 보관한 뒤 복사본을 지웠다. `%TEMP%\ReShade`, `%LOCALAPPDATA%\ReShade`, `%APPDATA%\ReShade`, `%ProgramData%\ReShade`는 실행 전후 모두 없었다.

`Tools/ReShade/analyze_reshade_still.py`가 PNG CRC, 자세별 Before 네 장의 일치, 원본 SMAA의 변경 여부, 최대 단계 설정과 원본의 일치, Adaptive와 원본의 차이, 단계 보기의 픽셀 수를 계산했다.

### 결과

두 실행 모두 하네스 보고서 PASS, ReShade 로그 오류와 경고 0건, 효과 컴파일 12회 성공이었다. PNG 48장이 CRC 검사를 통과했고 자세마다 프리셋 네 개의 Before 이미지가 픽셀 단위로 같았다.

| 장면 | 자세 | 원본 SMAA가 바꾼 픽셀 | 최대 단계 설정 = 원본 | Adaptive 차이(전체 화면) | 8/255 초과(전체 화면) | 차이(SMAA 변경 픽셀 중) | 8/255 초과(SMAA 변경 픽셀 중) | 최대 차이 |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| Bistro | 0 | 1.99% | 같음(최대 차이 0) | 0.443% | 0.0167% | 22.31% | 0.84% | 23 |
| Bistro | 1 | 2.08% | 같음(최대 차이 0) | 0.403% | 0.0088% | 19.37% | 0.42% | 18 |
| Bistro | 2 | 2.19% | 같음(최대 차이 0) | 0.375% | 0.0147% | 17.13% | 0.67% | 41 |
| Minecraft | 0 | 3.88% | 같음(최대 차이 0) | 0.063% | 0.0102% | 1.63% | 0.26% | 52 |
| Minecraft | 1 | 13.53% | 같음(최대 차이 0) | 0.477% | 0.0478% | 3.52% | 0.35% | 89 |
| Minecraft | 2 | 11.85% | 같음(최대 차이 0) | 0.407% | 0.0434% | 3.44% | 0.37% | 55 |

최대 단계 설정은 여섯 자세 모두 원본 `SMAA.fx`와 픽셀 단위로 같았다. Adaptive 파일의 변경은 탐색 길이를 고르는 부분 외에는 출력을 바꾸지 않았다.

1% 단계에서 8/255보다 크게 바뀐 픽셀은 원본 SMAA가 바꾼 픽셀의 Bistro 0.42~0.84%, Minecraft 0.26~0.37%였다. 작은 차이까지 세면 Bistro 17.1~22.3%, Minecraft 1.6~3.5%였다. 데모의 1% 기준은 finalDelta 구간별 경계 픽셀 중 8/255보다 크게 바뀐 비율이라 이 표의 비율과 같은 측정이 아니다. 루마 계산도 다르다.

단계 보기에서 경계 픽셀의 단계 비율(최단/중간/최상위)은 Bistro 46.2~49.6% / 37.5~39.5% / 12.9~14.3%, Minecraft 17.1~32.4% / 54.2~58.7% / 13.3~24.1%였다.

### 육안 검사

자세마다 Adaptive와 원본의 차이가 8/255를 넘는 픽셀이 가장 많은 96×64 창 세 곳을 nearest ×6으로 확대했다(Before, 원본, Adaptive, 차이 ×8 증폭, 단계 보기). 또 차이가 가장 큰 픽셀 주변 32×24를 nearest ×12로 확대했고 같은 영역을 밝기 ×3으로 보정한 줄을 따로 붙였다. 차이 증폭과 밝기 보정은 비교 보조 자료이며 원본 캡처와 구분해 표시했다.

- ×6 확대에서 원본과 Adaptive를 나란히 놓으면 차이를 구별하기 어려웠다. 차이 증폭 이미지에서 차이는 길고 거의 수직인 경계(Bistro 어두운 벽, 최단 단계)와 긴 수평 경계(Minecraft 블록 경계, 최상위 단계)를 따라 있었다.
- Minecraft 자세 1(x=256, y=831)의 풀과 돌 사이 긴 수평 경계에서 원본은 계단 왼쪽의 평평한 구간 약 17픽셀에 걸쳐 밝은 블렌딩을 넣었다. Adaptive는 그 구간을 AA 없는 화면에 가깝게 남겨 계단 한 칸이 원본보다 뚜렷했다.
- Bistro 자세 2(x=1220, y=481)의 밝은 수직 경계에서도 원본의 블렌딩이 경계를 따라 더 길게 이어졌고 Adaptive는 더 짧았다.
- Minecraft 자세 2(x=1676, y=913)에서는 블록 모서리 몇 픽셀만 달랐다.
- 확인한 영역에서 선이 사라지거나 끊긴 곳은 없었다. 차이는 긴 경계의 블렌딩이 덜 된 형태였다.

정지 자세 세 개만 봤으므로 움직일 때의 반짝임은 평가하지 않았다.

### GPU 시간

ReShade의 효과별 GPU 시간은 오버레이의 Statistics 탭에만 나오고 로그나 파일로 남지 않는다. 탭을 열려면 오버레이 안에서 마우스로 탭을 눌러야 해서 숨김 창 자동화로는 읽지 않았다. 사용자가 게임에서 직접 보도록 README에 방법을 적었고 참고값으로만 보도록 했다. 정식 시간 비교는 데모 측정(`Docs/Adaptive-Selected-Cross5-Formal-Timing/`)을 기준으로 한다.

## 한계

- ReShade 출력은 루마 계산과 처리 대상이 데모와 달라 데모 픽셀과 같지 않다.
- 단계 기준값은 데모에서 정한 값이다. 게임 화면에서 바뀌는 정도는 게임마다 다를 수 있다.
- 검증은 CMAA2 데모(DirectX 11, 64비트)의 정지 자세 여섯 개로 했다. 32비트, DirectX 9, OpenGL 이름 바꾸기와 실제 게임은 시험하지 않았다.
- ReShade DLL에는 GitHub에서 새 버전을 확인하는 기능이 들어 있고(`api.github.com` 문자열과 버전 알림 코드) 끄는 설정은 찾지 못했다.
- 이 묶음은 공식 SMAA, SweetFX 또는 TSCMAA 배포본이 아니다.

## 자료

- 셰이더 생성: `Tools/ReShade/make_adaptive_smaa_fx.py`, 결과 `Tools/ReShade/Shaders/AdaptiveSMAA.fx`, `AdaptiveSMAA.fxh`
- 설정 원본: `Tools/ReShade/Config/ReShade.ini`, `Tools/ReShade/Config/Presets/*.ini`, `Tools/ReShade/README-ko.txt`, `Tools/ReShade/THIRD-PARTY-ko.txt`
- 묶음 생성: `Tools/ReShade/make_reshade_bundle.py`
- 데모 검증: `Projects/CMAA2/ReShadeStill.inl`(1c994c0), `Tools/ReShade/run_reshade_still.ps1`, `Tools/ReShade/analyze_reshade_still.py`
- 이 폴더의 `still-check.json`(자세별 수치), `runs.json`(실행 기록, ReShade 컴파일 로그 줄, 실행 전후 폴더 확인), `bundle-manifest.txt`(묶음 파일 해시)
- 스크린샷과 확대 이미지: `D:\SMAAResearchCaptures\rs1\bistro-1`, `minecraft-1`, `analysis`(Git에 넣지 않음)
