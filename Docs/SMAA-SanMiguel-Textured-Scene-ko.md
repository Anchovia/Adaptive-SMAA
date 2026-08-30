# San Miguel 2.1 textured real-scene 연결

## 1. 목적과 현재 분류

절차적으로 만든 `thin-lines`와 texture가 없는 UNC Power Plant만으로는 실제 렌더링
장면의 식생 alpha edge, 가구·난간, 복합 재질을 충분히 대표하기 어렵다. 이를 보완하기
위해 San Miguel 2.1의 저폴리 버전을 CMAA2 DX11 데모에 외부 textured scene으로
연결했다.

현재 단계는 다음과 같이 분류한다.

- 원본 ZIP·저폴리 OBJ 무결성 및 사용 조건 확인: 완료
- diffuse texture와 alpha-test 재질을 보존한 외부 cache 변환: 완료
- CMAA2 로딩, 렌더링 및 고정 camera preview: 완료
- 기존 camera-motion scene token 연결: 완료
- Release x64 engineering preview 검증: 완료
- current-edge dilation/downsample-upsample ablation 본 측정: 아직 시작하지 않음
- 최종 논문 품질·성능 결과: 아님

## 2. 출처와 외부 데이터

- 배포 페이지: https://casual-effects.com/data
- 다운로드 URL:
  https://casual-effects.com/g3d/data10/research/model/San_Miguel/San_Miguel.zip
- 원 저작자: Guillermo M. Leal Llaguno
- 2017 개선: Morgan McGuire, Guedis Cardenas, Michael Mara, Nicholas Hull
- 원본 `license.txt`: attribution을 포함한 research/educational use
- ZIP SHA-256:
  `85874077735808150e679b3c71d70a37a270cb8833f4911325aa1099da3f7d4a`
- 저폴리 OBJ SHA-256:
  `7142519da39589857d7dfcd3143a7b41bd444279f65dd5177c3adfad29a1ecc9`

원본 ZIP, OBJ, texture와 생성 cache는 라이선스 및 용량 때문에 Git에 포함하지 않는다.
출처와 통계는 다음 manifest에 기록한다.

- `Docs/ExternalScenes/SanMiguel/san_miguel_source_manifest.json`
- `Docs/ExternalScenes/SanMiguel/san_miguel_source_manifest-ko.md`

현재 외부 데이터 배치는 다음과 같다.

```text
D:/SMAA-Research-Data/Scenes/SanMiguel/
├─ San_Miguel.zip
├─ SourceLowPoly/
└─ PreparedLowPoly/
   ├─ san-miguel-low-poly.obj
   ├─ san-miguel-low-poly.mtl
   ├─ textures/
   ├─ san-miguel-low-poly.smaasm
   └─ san-miguel-low-poly.manifest.json
```

`Projects/CMAA2/AutoBench`는 `D:/SMAA-Research-Data/AutoBench` junction이므로
캡처 결과는 D 드라이브에 저장된다.

## 3. 변환 구조

저폴리 OBJ도 약 599 MiB이고 현재 저장소의 Assimp source가 활성화되어 있지 않으므로,
런타임 OBJ import 대신 검증된 외부 `.smaasm` v1 cache를 사용한다.

1. `Tools/SMAA/prepare_san_miguel_scene.py`
   - ZIP과 저폴리 OBJ SHA-256 검증
   - geometry, material, texture와 실제 alpha channel 분석
   - 원본을 복제하지 않고 hardlink 기반 `PreparedLowPoly` 구성
2. `Tools/SMAA/convert_san_miguel_scene.py`
   - object/material 단위 streaming OBJ 변환
   - source Y-up을 CMAA2 Z-up으로 변환하고 바닥/중심 정렬
   - position, normal, UV, index, diffuse texture 상대 경로와 alpha-test flag 저장
3. `CMAA2Sample::LoadSanMiguelTexturedScene`
   - magic/version, 문자열·개수 상한, 유한 AABB, index 범위, 총합과 trailing byte 검증
   - texture를 GPU resource registrar에 등록한 뒤 material GUID로 연결
   - alpha texture material은 alpha test와 double-sided rendering 사용
   - ambient light, directional light와 skybox 추가

생성 cache 통계는 다음과 같다.

| 항목 | 값 |
|---|---:|
| cache 크기 | 255,051,301 bytes |
| object | 1,098 |
| material chunk | 1,563 |
| GPU vertex | 5,861,789 |
| triangle | 5,617,451 |
| material | 281 |
| diffuse texture | 265 |
| alpha-test material | 97 |

cache SHA-256은
`5d9dd502751ac144745138d7ddf6e7c48057459cd82d414ba6ec7cdf441ecc0d`다.

## 4. 실행 및 clean-process 규칙

CMAA2는 장시간 실행 시 메모리 사용량과 GPU 부하가 누적될 수 있으므로, 외부 장면
실험도 명령마다 새 프로세스로 실행한다. 실행 전후 `CMAA2.exe`가 0개인지 확인하며,
timeout 시 그 실행에서 시작한 PID만 강제 종료하고 부분 결과는 사용하지 않는다.
일반 자동 명령은 `Tools/SMAA/run_clean_cmaa2.ps1`, 단일 San Miguel preview는 아래의
장면별 runner를 사용한다.

준비와 변환 예시는 다음과 같다.

사전 조건은 Python 3와 Pillow다. Windows Store의 `python.exe` alias 대신 설치된
Python Launcher를 사용하는 예시는 다음과 같다.

```powershell
py -3 -m pip install Pillow
```

```powershell
py -3 Tools/SMAA/prepare_san_miguel_scene.py `
  D:\SMAA-Research-Data\Scenes\SanMiguel `
  --output Docs\ExternalScenes\SanMiguel `
  --prepared-output D:\SMAA-Research-Data\Scenes\SanMiguel\PreparedLowPoly

py -3 Tools/SMAA/convert_san_miguel_scene.py `
  D:\SMAA-Research-Data\Scenes\SanMiguel `
  --output D:\SMAA-Research-Data\Scenes\SanMiguel\PreparedLowPoly\san-miguel-low-poly.smaasm `
  --source-manifest Docs\ExternalScenes\SanMiguel\san_miguel_source_manifest.json
```

검증용 preview는 clean runner를 사용한다.

```powershell
.\Tools\SMAA\run_clean_san_miguel_preview.ps1 `
  -CachePath "D:\SMAA-Research-Data\Scenes\SanMiguel\PreparedLowPoly\san-miguel-low-poly.smaasm" `
  -WarmupFrames 60 `
  -TimeoutSeconds 240
```

`-smaaSanMiguelCache`가 있어야 `sanmiguel` camera-motion scene을 사용할 수 있다.
지원 profile은 기존 `yaw-slow-360`, `yaw-fast-360`, `yaw-extreme-360`,
`strafe-fast`, `yaw-strafe-fast`와 동일하다.

Supersample spatial reference와 `O-1X`, `O-T2X-R`, 무확장 `O-ET2X-R`, 3×3,
ARM Dual Filter를 같은 camera frame 구간에서 비교하는 paired workflow는 다음 runner를
사용한다. 두 capture는 AGENTS.md의 clean-process 규칙에 따라 서로 다른 CMAA2
프로세스로 실행된다.

```powershell
.\Tools\SMAA\run_san_miguel_expansion_controls.ps1 `
  -CachePath "D:\SMAA-Research-Data\Scenes\SanMiguel\PreparedLowPoly\san-miguel-low-poly.smaasm" `
  -CameraProfile yaw-fast-360 `
  -FirstProfileFrame 60 `
  -CaptureFrames 60 `
  -WarmupFrames 60 `
  -ArmThreshold 0.25 `
  -TimeoutSeconds 7200
```

`-ArmThreshold`는 ARM mask reconstruction의 연구용 runtime parameter이며 허용 범위는
`0.0~1.0`이다. 기본 `0.25`는 ARM 원문이나 Intel TSCMAA 원본의 SMAA용 공개값이 아니라
binary candidate mask adaptation에 사용한 초기 연구 가정이다. Reference를 이미 확보한
threshold sweep에서는 `-SkipReference`를 사용해 중복 supersample capture를 피한다.

두 실행에서 생성된 control root와 reference root는 다음과 같이 분석한다.

```powershell
py -3 Tools/SMAA/analyze_san_miguel_expansion_controls.py `
  D:\SMAA-Research-Data\AutoBench\<CONTROL_ROOT> `
  D:\SMAA-Research-Data\AutoBench\<REFERENCE_ROOT> `
  --expected-frames 60
```

분석기는 full frame과 화면 좌측·하단의 thin-geometry ROI를 각각 비교한다. 동일 pose의
supersample sequence는 spatial-reference proxy이며 temporal ground truth로 표현하지 않는다.

## 5. Engineering 검증 결과

- Release x64 DX11 빌드 PASS
- cache header와 전체 5,617,451 triangle 로딩 PASS
- 281개 material, 265개 diffuse texture와 97개 alpha-test material 연결 PASS
- shader/resource 준비 뒤 preview PNG 저장 PASS
- scene/camera provenance 기록 PASS
- 고정 courtyard camera `(-5.0, -10.5, 2.3)` 적용 확인
- preview 명령 정상 종료 및 종료 후 잔류 `CMAA2.exe` 0개 확인
- `yaw-slow-360` Original 5-way 1-frame engineering smoke PASS:
  `O-1X`, `O-T2X`, `O-T2X-R`, `O-ET2X`, `O-ET2X-R` 각각 PNG 1장
- 대표 AutoBench root:
  `Projects/CMAA2/AutoBench/20260813_164145`
- camera-motion smoke root:
  `Projects/CMAA2/AutoBench/20260813_164555`

초기 실행은 `AssetsStillLoading` 상태에서 계속 대기했다. 직접 생성한 texture가 global
UID registrar에 등록되지 않아 material이 매 프레임 texture GUID를 해석하지 못한 것이
원인이었다. texture를 material에 연결하기 전에 UID tracking을 명시적으로 수행해
해결했다.

두 번째 진단에서는 자유 카메라의 저장 pose가 연구용 pose를 다시 덮어썼다. 기존
camera-motion test state를 preview에도 재사용하여 controller 입력 뒤에 고정 pose와
camera matrix를 다시 적용하도록 수정했다. 최종 report의 scene ID와 camera 좌표가
요청값과 일치하고, courtyard·식생·난간·가구가 함께 보이는 이미지를 확인했다.

## 6. 한계와 다음 단계

- 현재는 diffuse/albedo와 alpha test를 우선 연결했다. source의 bump/normal/specular map은
  아직 CMAA2 material에 연결하지 않았다.
- ambient/directional lighting과 shadow 비활성화는 안정적인 첫 integration을 위한
  engineering 설정이며 최종 장면 조명으로 확정하지 않았다.
- 장면에는 식생과 얇은 난간이 충분하지만, 어떤 camera path와 ROI가 subpixel 단절을 가장
  잘 드러내는지는 연속 frame screening으로 선정해야 한다.
- `-R` mode는 기존과 동일하게 camera-motion reprojection이며 object motion vector는 없다.
- 현재 preview는 scene integration 증거이며 dilation 품질 개선의 증거가 아니다.

다음 품질 gate는 San Miguel 동일 경로에서 `O-1X`, `O-T2X-R`, 무확장 `O-ET2X-R`,
3×3, ARM을 supersample spatial reference와 함께 비교하는 것이다. 이후 ARM threshold를
미세 sweep하고 후보 coverage를 맞춘 3×3/ARM 비교를 수행한다. Power Plant는 미완성
renderer이므로 정식 근거에서 제외하고, synthetic thin-lines는 회귀 진단에만 사용한다.
