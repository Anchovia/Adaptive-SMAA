# Iris 셰이더 팩으로 옮긴 Adaptive SMAA + 선택 경로 + Cross5

브랜치

- `experiment/iris-adaptive-selected-cross5` (이 문서, `tooling/adaptive-selected-cross5-minimal` 60bae94에서 시작)
- `tooling/adaptive-selected-cross5-minimal` 60bae94 (옮긴 데모 코드)
- `experiment/adaptive-selected-cross5` c55db4f (결합 브랜치)
- `validation/adaptive-selected-cross5-formal-timing` 2b33eab (정식 전체 화면 시간 측정)
- `experiment/reshade-adaptive-smaa` 4254c61 (ReShade 묶음, 공간 SMAA만)

## 목적

ReShade는 카메라 행렬을 받지 못해 카메라/깊이 재투영을 할 수 없다. 그래서 셰이더 팩 규격이 깊이와 현재·이전 행렬을 주는 Minecraft Java Edition + Iris로 최종 조합(Adaptive 1% 단계 + 선택 경로 + (c') Cross5)을 옮겼다. 실제 게임에서 temporal 처리까지 화질을 보려는 것이다. 성능 수치는 계속 CMAA2 데모 정식 측정을 기준으로 하고 Minecraft는 화질 확인에만 쓴다.

팩은 gbuffers 프로그램 없이 composite와 final만 가진 후처리 전용 팩이다. `-R`은 이 팩에서도 카메라/깊이 재투영만 뜻한다. 물체 motion vector는 Iris가 지원하지 않는다(ShaderDoc unsupported-features).

사용자용 묶음은 `C:\Users\USER\Downloads\Iris-AdaptiveSMAA\`에 두었다. Fabric과 Iris는 받지 않았고 README에 공식 주소만 적었다.

## Iris 문서와 소스에서 확인한 것

문서는 shaders.properties(https://shaders.properties/current/reference/)와 IrisShaders/ShaderDoc을 읽었다. 문서에 없는 내용은 IrisShaders/Iris 소스(26.1 브랜치)에서 확인했다.

| 항목 | 확인한 내용 | 출처 |
|---|---|---|
| gbuffers가 없을 때 | 문서의 대체 표는 gbuffers_terrain → textured_lit → textured → basic으로 이어지고 basic의 대체는 없다(N/A). 사슬 전체가 없을 때는 문서에 없다. 소스에서는 프로그램 소스가 비면 `createFallbackShader`로 넘어가고 대체 셰이더 생성기(`ShaderSynthesizer`)는 텍스처 × 정점 색 × 라이트맵과 바닐라식 안개를 계산한다. 그 결과가 colortex0에 쓰이는지는 소스에서 끝까지 확인하지 못했다 | programs/gbuffers, `IrisRenderingPipeline.java`, `pipeline/fallback/ShaderSynthesizer.java` |
| 패스 순서 | gbuffers(불투명) → deferred → 반투명 gbuffers → composite → final. 반투명(gbuffers_water, weather, hand_water)은 deferred 뒤에 그린다 | programs/overview, programs/gbuffers |
| 버퍼 뒤집기 | deferred/composite는 main을 읽고 alt에 쓴 뒤 뒤집는다. 한 패스에서 같은 버퍼를 읽고 쓸 수 있다. final 뒤에 그 프레임에 뒤집힌 버퍼를 alt에서 main으로 복사한다(Clear 대상 버퍼 제외). 그래서 `Clear=false` 버퍼를 한 패스에서 읽고 쓰면 다음 프레임 같은 패스는 이번에 쓴 값을 읽는다 | shadersproperties/rendering, buffers/colortex, `FinalPassRenderer.java`(SwapPass), `BufferFlipper.java` |
| 버퍼 유지 | `const bool colortexNClear = false;`면 다음 프레임까지 값을 유지한다. 형식은 블록 주석 안의 `const int colortexNFormat = RGBA16F;`로 정한다. sRGB 형식은 목록에 없다 | constants/buffer_clear, constants/buffer_format, buffers/image_format |
| colortex 표본 추출 | 정수 형식이 아니면 LINEAR, 주소는 CLAMP_TO_EDGE, 밉맵 없음. SMAA가 쓰는 쌍선형 경계 읽기와 같은 조건이다 | `targets/RenderTarget.java` |
| 깊이 | depthtex0은 모든 형상, depthtex1은 반투명 제외, depthtex2는 반투명과 손 제외 | buffers/depthtex |
| 사용자 텍스처 | `customTexture.<이름> = <경로>`(Iris 전용)가 `uniform sampler2D <이름>`을 만든다. PNG 기본값은 nearest + 반복이고 `<파일>.png.mcmeta`의 blur/clamp가 적용된다. PNG는 RGBA8로 읽는다 | buffers/custom_textures, `ShaderPack.java`(readTexture), `NativeImageBackedCustomTexture.java` |
| 행렬·카메라 | gbufferModelView(Inverse), gbufferProjection(Inverse), gbufferPreviousModelView, gbufferPreviousProjection은 mat4, cameraPositionInt/previousCameraPositionInt는 ivec3, …Fract는 vec3(Iris 전용). 첫 프레임의 이전 모델뷰 행렬은 0이다 | uniforms/camera, uniforms/matrices, ShaderDoc uniforms.md |
| 셰이더 옵션 | `#define 이름 값 // [값 목록]`, 불리언은 주석 처리한 `#define`. 화면 구성은 shaders.properties의 `screen`. 언어 파일 `lang/<코드>.lang`은 UTF-8로 읽는다 | shadersproperties/shader_settings, `LanguageMap.java` |
| 프로필 | compatibility 프로필을 권장한다 | how-to/compatibility_vs_core |
| 기본 키 | 셰이더 다시 불러오기 R, 셰이더 켜기/끄기 K, 셰이더 팩 화면 O | `Iris.java` |
| 물체 motion vector | Iris는 지원하지 않는다("Entity motion vectors … Not implemented") | ShaderDoc unsupported-features.md |

gbuffers 대체 셰이더가 바닐라와 같은 화면을 colortex0에 그린다는 것은 소스의 생성기 내용으로 미루어 본 것이다. 실제 Minecraft에서 처음 적용할 때 확인해야 하므로 사용자 README에 화면이 이상하면 셰이더를 끄고 알려 달라고 적었다.

## 팩 구성

`Tools/Iris/AdaptiveSMAA-Iris/shaders/`가 팩의 소스다. `lib/SMAA.glsl`은 `Tools/Iris/make_iris_assets.py`가 데모의 `Projects/CMAA2/SMAA/SMAA.hlsl`(60bae94, git blob af2383aa)에서 만든다. 바꾼 것은 줄 끝을 LF로, 주석 그림의 비ASCII 문자 두 개를 '.'로 바꾼 것, 백슬래시로 끝나는 배너 주석 다섯 줄 끝에 '.'을 붙인 것(GLSL 3.30에는 줄 이음이 없어 glslang이 주석 안에서도 오류를 낸다), 단계 최댓값 스위치(`SMAA_ADAPTIVE_TIERS_AT_MAX`)를 넣은 것이다. SMAA 식과 Adaptive 1% 단계 블록은 그대로다. AreaTex.png와 SearchTex.png도 같은 스크립트가 `AreaTex.h`, `SearchTex.h`에서 만든다(추가 다운로드 없음). 첫 행이 헤더 데이터의 첫 행이며 데모가 D3D11에 올리는 메모리 순서와 같다.

| 패스 | 하는 일 | 읽기 | 쓰기 | 데모 대응 |
|---|---|---|---|---|
| composite | 경계용 루마, 카메라 속도, 지난 프레임 속도 복사 | colortex0, colortex3(지난 속도), depthtex0~2 | colortex2, 3, 4 | RGBToLumaForEdges, `DX10_SMAAGenerateCameraVelocityPS`, Cross5 속도 ping-pong |
| composite1 | SMAA 루마 경계, Adaptive 단계, 선택 플래그 | colortex2, 3, 5(지난 경계) | colortex5 | `Selected…EdgePS`(스텐실 대신 A 채널) |
| composite2 | 블렌딩 가중치 | colortex5, AreaTex, SearchTex | colortex6 | `SMAABlendingWeightCalculationPS` |
| composite3 | 이웃 블렌딩(공간 결과) | colortex0, 6 | colortex7 | `SelectedNeighborhoodPS` |
| composite4 | 선택 화소 resolve(출력이자 다음 history) | colortex3, 4, 5, 7, 8(지난 history) | colortex8 | `SelectedResolvePS`, `…Cross5PS`, `SelectedSeedResolvePS` |
| final | 출력 또는 디버그 보기 | colortex0, 3, 5, 8 | 화면 | 출력 표시 |

| 버퍼 | 형식 | 내용 | 다음 프레임까지 유지 |
|---|---|---|---|
| colortex0 | RGBA8(기본) | Iris가 그린 장면(sRGB 인코딩 값) | 아니요 |
| colortex2 | R8 | 경계용 루마 | 아니요 |
| colortex3 | RGBA16F | rg 카메라 속도(현재 UV − 이전 UV), b history 사용 가능 | 예(Cross5의 지난 속도) |
| colortex4 | RG16F | 지난 프레임 속도 | 아니요 |
| colortex5 | RGBA8 | rg 현재 경계, b Adaptive 단계, a 선택 플래그 | 예(지난 원시 경계) |
| colortex6 | RGBA8 | 블렌딩 가중치 | 아니요 |
| colortex7 | RGBA8 | 공간 SMAA 결과 | 아니요 |
| colortex8 | RGBA8 | 출력이자 다음 history, a=1이면 유효 | 예 |

모든 패스는 화면 전체를 그리고 모든 화소에 값을 쓴다. 유지 버퍼는 이전 내용이 남아 있으므로 `discard`를 쓰면 지난 값이 섞인다. 그래서 경계 패스는 데모의 선택 경로처럼 `discard`를 0 반환으로 바꿔 SMAA 경계 함수를 포함한다.

셰이더 설정 화면(`shaders.properties`의 `screen`, `lib/settings.glsl`)

| 옵션 | 값 |
|---|---|
| AA 방식(`AA_MODE`) | 0 끔, 1 원본 SMAA 1X, 2 Adaptive SMAA 1X, 3 원본 선택 경로, 4 Adaptive 선택 경로, 5 원본 선택 경로+Cross5, 6 Adaptive 선택 경로+Cross5(기본값) |
| 디버그 보기(`DEBUG_VIEW`) | 0 끔, 1 경계, 2 탐색 단계, 3 선택 화소, 4 카메라 속도 |
| 단계 최댓값(`TIERS_AT_MAX`) | 켜면 Adaptive의 세 단계가 모두 Ultra 최대(32)를 쓴다. 동일성 확인용이다 |

옵션 이름과 값 설명은 `lang/en_us.lang`, `lang/ko_kr.lang`에 있다. 모든 모드는 SMAA Ultra 고정이다.

## 데모와 다르게 옮긴 부분

| 항목 | CMAA2 데모 | Iris 팩 | 근거와 영향 |
|---|---|---|---|
| 경계 루마 | 톤매핑 직후 float 선형 색의 제곱근에 Rec.601 가중치, R8_UNORM | 8비트 sRGB 값을 선형으로 바꾼 뒤 같은 식, R8 | 식은 같다. 입력이 이미 8비트로 양자화된 값이라 문턱 근처 경계가 일부 달라질 수 있다 |
| 블렌딩 공간 | sRGB 뷰로 읽고 써서 쌍선형 필터와 블렌딩이 선형 공간에서 일어난다 | RGBA8에 sRGB 형식이 없어 네 텍셀을 직접 읽어 선형으로 바꾼 뒤 쌍선형 보간하고 다시 인코딩한다(이웃 블렌딩, history Catmull-Rom 다섯 탭) | 하드웨어 필터는 보간 비율을 8비트 정밀도로 쓰고 직접 보간은 float을 쓴다. 차이는 1/255 수준이다 |
| resolve 식 | sRGB 인코딩 값의 제곱을 섞은 뒤 제곱근 | 같은 식. 버퍼가 인코딩 값을 담으므로 변환 없이 계산한다 | 출력 값은 같은 8비트 양자화를 거친다 |
| 스텐실 | 경계 패스가 스텐실을 쓰고 가중치·resolve 패스가 스텐실 테스트를 한다 | 선택 플래그를 colortex5의 A에 쓰고 resolve에서 분기한다. 가중치 패스는 현재 경계가 없으면 SMAA 안에서 0을 낸다 | Iris 문서에 스텐실 테스트가 없다. 결과는 같고 스텐실의 조기 탈락 이득은 없다 |
| 손 | 해당 없음 | depthtex1 < depthtex2인 화소를 손으로 보고 속도 0, history 사용 안 함 | 손은 카메라와 함께 움직여 재투영 위치가 틀린다 |
| 반투명 | 장면 깊이 하나 | 재투영에 depthtex0(반투명 포함) | 반투명 화소에 보이는 색과 경계는 앞면이 대부분 정한다. 물이나 유리 뒤 물체의 경계는 앞면 깊이로 재투영되어 조금 어긋날 수 있다. depthtex1을 쓰면 반대로 물 표면 무늬와 물가 경계가 어긋난다 |
| 화면 좌표 | D3D, 위가 v=0 | OpenGL, 아래가 v=0. AreaTex/SearchTex는 같은 메모리 순서 | SMAA는 화면을 위아래로 뒤집은 영상에 적용한 것과 같다. SMAA가 위쪽 이웃으로 다루는 화소(texcoord.y − 1화소)가 화면에서는 아래 화소다. 같은 화면이라도 데모와 화소가 완전히 같지 않다. 디버그 경계 보기의 초록도 아래 화소와의 가로 경계다 |
| 카메라 속도 | 현재 view-projection 역행렬로 월드 위치를 구해 이전 view-projection으로 투영 | Iris의 player 공간(카메라 기준)으로 되돌린 뒤 카메라 이동량(`cameraPositionInt/Fract` 차)을 더해 이전 행렬로 투영 | 같은 의미다. 정수부와 소수부를 따로 빼서 큰 좌표에서 정밀도 손실을 줄였다 |
| 첫 프레임 | 시드 resolve(history = 현재 공간 결과) | 이전 행렬이 0이라 속도를 쓰지 않고 공간 결과를 낸다. 버퍼가 다시 만들어져 history의 a가 0이면 데모와 같은 시드 resolve를 한다 | 데모의 첫 프레임도 속도 0의 시드라 출력은 공간 결과와 같다 |
| 카메라 끊김 | 장면 전환 시 history 초기화 | 한 프레임에 카메라가 16블록 이상 움직이면 그 프레임은 history를 쓰지 않는다 | 순간이동, 리스폰, 차원 이동에 대응하려고 더했다. 데모에는 없는 규칙이다 |
| SearchTex 필터 | linear sampler | nearest(.mcmeta blur false) | SMAA가 텍셀 중심만 읽으므로 같은 값이다 |
| 처리 범위 | 데모 UI 전 장면 | GUI는 final 뒤에 그려져 처리하지 않는다 | 메뉴, 채팅, F3 화면은 AA를 받지 않는다 |

## 검증

Minecraft는 이 PC에서 실행하지 않았다. 대신 컴파일러 두 개와 Iris 처리 순서를 흉내 낸 시험 프로그램으로 확인했다.

### 컴파일

`Tools/Iris/iris_expand.py`가 Iris처럼 `#include`를 풀고 `lib/settings.glsl`의 옵션 값을 바꿔 프로그램 원문을 만든다. AA 방식 7 × 디버그 보기 5 × 단계 최댓값 2 = 70개 조합, 조합마다 여섯 프로그램의 정점·프래그먼트 셰이더를 확인했다.

| 검사 | 도구 | 결과 |
|---|---|---|
| GLSL 규격 검사 | glslangValidator(Vulkan SDK 1.3.275.0에 이미 설치된 것, 새로 받지 않음) | 프로그램 단계 840개(서로 다른 원문 633개) 모두 오류와 경고 없음 |
| 실제 드라이버 컴파일과 링크 | `Tools/Iris/iris_gl_harness.cpp`, NVIDIA GeForce RTX 3060 Ti, OpenGL 4.6.0 NVIDIA 621.14 | 70개 조합의 여섯 프로그램 모두 컴파일·링크 성공, 드라이버 메시지 없음 |

처음 glslang 검사에서 SMAA 배너 주석의 줄 끝 백슬래시가 줄 이음 오류로 잡혔다. NVIDIA 드라이버와 Iris 전처리기는 문제 삼지 않는 부분이지만 다른 드라이버를 생각해 `make_iris_assets.py`에서 그 다섯 줄 끝에 '.'을 붙였다. 그 뒤 두 검사가 모두 통과했다.

### 시험 프로그램으로 본 동작

`iris_gl_harness.exe`는 colortex 버퍼마다 텍스처 두 장을 두고 패스가 최신 내용을 읽고 다른 장에 쓴 뒤 그 장을 최신으로 삼는다. 이 팩의 버퍼는 모두 한 프레임에 한 번만 쓰이므로 Iris의 고정 뒤집기 배치와 프레임 끝 복사와 같은 결과다. 형식과 `Clear=false`는 `composite.fsh`에서 읽고 AreaTex/SearchTex는 생성한 PNG를 그대로 올린다. 장면 색은 composite 전에 colortex0에 넣는다.

입력은 CMAA2 데모 화면(AA 없음, ReShade 검증에서 저장한 Minecraft와 Bistro 자세 1)에서 1600×1000을 잘라 썼다. 깊이는 카메라 앞 10블록의 평면, 투영은 시야각 70°로 두었다. 카메라를 옆이나 위로 옮기면 화면이 정확히 정수 화소만큼 움직이도록 이동량을 정했다. 화면 위쪽이 영상 위쪽이 되도록 OpenGL 순서(아래 행부터)로 올렸다. 비교는 가장자리 96화소를 뺀 1,137,664화소에서 했다. 각 경우 6프레임이다.

| 장면 | 경우 | 선택 경로(모드 3~6)와 같은 계열 SMAA 1X의 차이(최대 / 다른 화소 수) | 선택 화소 비율(5프레임) |
|---|---|---|---|
| Minecraft | 정지 | 0 / 0 (6프레임 모두) | 26.0% |
| Minecraft | 옆으로 2화소씩 | 최대 10 / 최대 438 | 26.1% |
| Minecraft | 위로 2화소씩 | 최대 2 / 최대 224 | 25.9% |
| Minecraft | 옆으로 1.5화소씩 | 최대 107 / 최대 335,988 | 30.9% |
| Bistro | 정지 | 0 / 0 (6프레임 모두) | 3.0% |
| Bistro | 옆으로 2화소씩 | 최대 5 / 최대 267 | 3.0% |
| Bistro | 위로 2화소씩 | 최대 5 / 최대 130 | 3.1% |
| Bistro | 옆으로 1.5화소씩 | 최대 110 / 최대 43,154 | 3.5% |

- 정지 화면에서 선택 경로 네 모드는 같은 계열 SMAA 1X와 여섯 프레임 모두 화소 단위로 같았다. history를 같은 자리에서 읽어 섞으면 공간 결과와 같아지는 성질을 그대로 보였다.
- 정수 화소 이동에서도 속도와 history가 맞으면 선택 경로는 SMAA 1X와 같아야 한다. 차이는 최대 10, 화소 수는 내부의 0.04% 이하였다. SMAA 1X끼리 한 프레임 전 결과를 같은 양만큼 옮겨 비교해도 29~384화소가 최대 1~4(Adaptive Minecraft 첫 프레임은 12) 달랐다(`gl-inspect.json`). SMAA의 좌표 계산이 화면 위치에 따라 반올림이 조금씩 달라 공간 결과가 완전히 평행 이동하지 않기 때문이다. 속도 값은 half float이라 2화소 이동이 −0.00125 대신 −0.0012493 UV로 저장됐다(데모의 R16G16_FLOAT도 같다). 차이의 크기와 화소 수가 이 두 원인으로 설명되는 범위였다. 속도 부호가 틀리거나 history 버퍼가 지난 프레임 값을 주지 못했다면 경계 화소 대부분이 달라졌을 것이다.
- 속도 버퍼는 옆 이동에서 (−0.0012493, 0), 위 이동에서 (0, −0.0019989) UV였다. 화면 내용이 왼쪽과 아래로 움직이는 방향과 맞고 history UV = UV − 속도가 지난 프레임의 같은 내용을 가리킨다.
- 1.5화소 이동은 history를 반 화소 위치에서 읽으므로 SMAA 1X와 달라진다. 선택 화소가 많은 Minecraft에서 다른 화소가 많았다. 차이가 가장 큰 곳을 nearest 8배로 확대해 보니 움직이는 방향으로 경계가 조금 더 부드러워졌고 깨진 화소는 없었다(`D:\SMAAResearchCaptures\iris-gl1\<장면>\pan_x1p5_maxdiff_f5.png`). 입력 자체를 쌍선형 보간으로 만든 합성 영상이라 Minecraft 실제 화질 판단에는 쓰지 않는다.
- 손 사각형(320×400, depthtex1 < depthtex2)에서는 선택 화소와 history 사용 화소가 0개였고 그 안의 출력은 SMAA 1X와 완전히 같았다. 사각형 밖은 1.5화소 이동이라 달라졌다.
- 단계 최댓값을 켠 Adaptive(모드 2, 4, 6)는 다섯 경우 × 6프레임 × 두 장면에서 원본(모드 1, 3, 5)과 화소 단위로 같았다.
- Adaptive SMAA 1X와 원본 SMAA 1X를 첫 프레임에서 비교하면 8/255보다 크게 다른 화소가 원본이 바꾼 화소의 Minecraft 0.40%, Bistro 0.69%였다. 데모와 ReShade 검증의 0.3~0.8%와 같은 범위다.

시험 프로그램은 Iris가 아니다. Iris 자체의 전처리기와 소스 변환, gbuffers 대체 셰이더가 그리는 장면, 실제 Minecraft 깊이와 행렬, 손과 반투명이 섞인 화면은 확인하지 못했다.

## 사용자용 묶음

`C:\Users\USER\Downloads\Iris-AdaptiveSMAA\`

| 파일 | 내용 |
|---|---|
| AdaptiveSMAA-Iris.zip | 팩(zip 안 최상위에 shaders/). shaderpacks 폴더에 그대로 넣는다 |
| README-ko.txt | Fabric과 Iris 공식 주소(직접 설치), 팩 넣는 위치, 모드 바꾸는 법, 디버그 보기, F1/F2 스크린샷, 싱글 월드에서만 시험, 제거 방법 |
| MANIFEST-sha256.txt | 묶음 파일과 zip 안 파일 24개의 해시 |

`Tools/Iris/make_iris_bundle.py`가 팩 소스와 생성 파일, SMAA 라이선스로 zip을 만든다. 시각과 순서를 고정해 같은 소스면 같은 바이트가 나온다. zip 안 셰이더는 시험 프로그램이 쓴 빌드와 바이트가 같다(라이선스 파일만 추가). 해시는 이 폴더의 `bundle-manifest.txt`에 있다.

## 한계

- 실제 Minecraft와 Iris에서 실행하지 않았다. 특히 gbuffers가 없을 때 Iris가 바닐라와 같은 화면을 colortex0에 그린다는 것은 소스로 미루어 본 것이다.
- 화면 좌표가 OpenGL 방향이라 같은 영상에서도 데모와 화소가 완전히 같지는 않다. 경계 루마도 8비트 sRGB 값에서 구한다.
- 카메라/깊이 재투영만 한다. 몹, 떨어지는 블록, 흐르는 물처럼 스스로 움직이는 것의 경계에는 잔상이 생길 수 있다.
- 반투명 화소는 앞면 깊이로 재투영한다. 손은 history를 쓰지 않는다.
- Minecraft에서 성능을 재지 않았다. 팩에는 GPU 타이머도 없다.
- 공식 SMAA, SweetFX, TSCMAA 배포본이 아니다.

## 자료

- 팩 소스: `Tools/Iris/AdaptiveSMAA-Iris/shaders/`(`lib/SMAA.glsl`은 생성 파일)
- 생성: `Tools/Iris/make_iris_assets.py`(SMAA.glsl, AreaTex/SearchTex PNG와 .mcmeta), `Tools/Iris/make_iris_bundle.py`(사용자 묶음), `Tools/Iris/README-ko.txt`(묶음 README 원본)
- 검사: `Tools/Iris/iris_expand.py`, `Tools/Iris/check_glsl_glslang.py`, `Tools/Iris/iris_gl_harness.cpp`, `Tools/Iris/build_gl_harness.cmd`, `Tools/Iris/run_gl_checks.py`, `Tools/Iris/inspect_gl_checks.py`
- 결과: 이 폴더의 `glslang-checks.json`, `gl-checks.json`, `gl-inspect.json`, `bundle-manifest.txt`
- 시험 프레임과 출력: `D:\SMAAResearchCaptures\iris-gl1`(Git에 넣지 않음)
