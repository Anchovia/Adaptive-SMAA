# UNC Power Plant 실제 thin-geometry 장면 연결

## 1. 목적과 현재 분류

절차적으로 만든 `SMAA Temporal Stress Test/thin-lines`는 변수 통제가 쉬운 engineering
control이지만 실제 3D 장면을 대표하지 않는다. 이를 보완하기 위해 실제 석탄 발전소를
모델링한 UNC Power Plant를 별도 외부 장면으로 연결했다.

현재 단계의 결과는 다음과 같이 분류한다.

- 장면 출처·파일 무결성 검증: 완료
- CMAA2 외부 캐시 변환과 렌더링: 완료
- 17개 section 미리보기와 주 후보 선정: 완료
- 기존 camera-motion/Original 5-way 캡처 연결: engineering smoke 완료
- dilation 품질·성능 ablation: 아직 시작하지 않음
- 최종 논문 품질·성능 결과: 아님

## 2. 출처와 사용 조건

- 장면: UNC Power Plant
- 원 저작권: University of North Carolina at Chapel Hill, 1999
- 사용 조건: non-commercial use only
- 원 출처/acknowledgements: http://gamma.cs.unc.edu/POWERPLANT/#acknowledgements
- 배포 페이지: https://casual-effects.com/data
- 다운로드 URL:
  https://casual-effects.com/g3d/data10/research/model/powerplant/powerplant.zip

원본 ZIP, OBJ 및 변환 캐시는 라이선스와 용량 때문에 Git에 포함하지 않는다. 해시와
구역별 통계는 다음 두 파일만 커밋한다.

- `Docs/ExternalScenes/PowerPlant/powerplant_source_manifest.json`
- `Docs/ExternalScenes/PowerPlant/powerplant_source_manifest-ko.md`

검증된 원본은 21개 section, 정점 5,984,083개, 법선 794,066개, 삼각형
12,759,246개다. OBJ SHA-256은
`1bda60ac06a11a6299799c95f4caac63b5c2a3654464040ff5b7d4bb8db190a8`이다.

## 3. 외부 데이터 배치

현재 로컬 배치는 다음과 같다. `<ResearchDataRoot>`는 현재
`D:\SMAA-Research-Data`다.

```text
<ResearchDataRoot>/Scenes/PowerPlant/
├─ powerplant.zip
├─ Source/
│  ├─ powerplant.obj
│  ├─ powerplant.mtl
│  └─ copyright.txt
├─ Cache/
├─ PreviewCaptures/
└─ PreviewAnalysis/
```

Git 저장소의 `Projects/CMAA2/AutoBench`는 D 드라이브의
`<ResearchDataRoot>/AutoBench`로 연결되어 있으므로 이후 캡처도 C 드라이브를 다시
채우지 않는다.

## 4. 변환 구조

CMAA2의 일반 OBJ importer는 현재 빌드에서 활성화되어 있지 않고 원본 OBJ는 약 780 MiB다.
따라서 런타임에서 OBJ를 파싱하지 않고 다음 두 단계로 분리했다.

1. `Tools/SMAA/prepare_powerplant_scene.py`
   - 원본 ZIP/OBJ SHA-256 확인
   - OBJ를 스트리밍하여 21개 section의 정점·법선·삼각형·재질·AABB 기록
2. `Tools/SMAA/convert_powerplant_scene.py`
   - 지정한 `secN`만 스트리밍 변환
   - 재질별 position/normal/index를 `.smaapp` v1 캐시에 저장
   - source Y-up을 engine Z-up으로 회전
   - section별 최장 AABB를 20 engine unit으로 정규화
   - 원본 MTL의 `Kd` 색상을 사용하되 preview에서는 opaque로 렌더링

캐시는 header, UTF-8 section name, material chunk별 float3 position, float3 normal,
uint32 index로 구성한다. CMAA2 로더는 magic/version, 문자열 길이, chunk/vertex/index
상한, 유한 AABB/material 값, index 범위, 총합과 trailing byte를 검증한다.

예시 변환 명령:

```powershell
python Tools/SMAA/convert_powerplant_scene.py `
  D:\SMAA-Research-Data\Scenes\PowerPlant `
  --cache-output D:\SMAA-Research-Data\Scenes\PowerPlant\Cache `
  --sections sec4,sec10
```

## 5. section 선별 결과

초대형 `sec1`, `sec7`, `sec11`, `sec13`은 첫 선별에서 제외하고 나머지 17개 section을
동일 1920×1017, SMAA Ultra 1X, 동일 카메라로 캡처했다. 비교표와 단순 luma-gradient
screening 지표는 다음 위치에 있다.

- `D:\SMAA-Research-Data\Scenes\PowerPlant\PreviewAnalysis\powerplant_preview_contact_sheet.png`
- `D:\SMAA-Research-Data\Scenes\PowerPlant\PreviewAnalysis\powerplant_preview_metrics.csv`

gradient 비율은 장면 후보를 거르는 보조값이지 AA 품질 점수가 아니다.

| 구역 | 역할 | 삼각형 | 화면 edge 비율 | 선정 판단 |
|---|---|---:|---:|---|
| `sec4` | 주 실제 thin-geometry 후보 | 366,404 | 4.545% | 배관·프레임·난간형 구조가 함께 보이며 화면 포화가 덜함 |
| `sec10` | 극단 반복선 stress 보조 후보 | 167,012 | 12.215% | 수직 반복선이 화면을 과도하게 채워 주 장면보다 극단 조건에 적합 |
| `sec20` | 보조 후보 | 152,586 | 3.655% | 다수의 배관과 연결 구조를 포함하지만 현재 시점이 내부에 가까움 |
| `sec15` | 보조 후보 | 382,062 | 3.390% | 실제 배관 구조가 있으나 화면 분포가 한쪽에 치우침 |

주 후보 `sec4.smaapp`은 311,471 정점, 366,404 삼각형, 3개 material chunk이며
SHA-256은 `20fbd599a7e6efbcf090e2236035e05e36cc769b977b467c3b32308f19cdfa50`이다.

## 6. CMAA2 실행 방법

단일 미리보기 캡처:

```powershell
.\CMAA2.exe `
  -smaaPowerPlantPreviewCache "D:\SMAA-Research-Data\Scenes\PowerPlant\Cache\sec4.smaapp" `
  -smaaPowerPlantPreviewCapture "60"
```

부드러운 60 Hz 360도 화면 미리보기:

```powershell
.\CMAA2.exe `
  -smaaPowerPlantPreviewCache "D:\SMAA-Research-Data\Scenes\PowerPlant\Cache\sec4.smaapp" `
  -smaaCameraMotionPreview "powerplant yaw-slow-360 O-1X 1"
```

기존 Original 5-way 축소 캡처:

```powershell
.\CMAA2.exe `
  -smaaPowerPlantPreviewCache "D:\SMAA-Research-Data\Scenes\PowerPlant\Cache\sec4.smaapp" `
  -smaaCameraMotionOriginalFiveCapture "powerplant yaw-slow-360 60 3 2"
```

`powerplant`는 기존 `bistro`, `minecraft`와 같은 camera-motion scene token으로
추가됐다. `yaw-slow-360`, `yaw-fast-360`, `yaw-extreme-360`, `strafe-fast`,
`yaw-strafe-fast`를 그대로 사용할 수 있다. Power Plant 선택 시 cache 인자가 없으면
빈 장면을 측정하지 않도록 명시적으로 거부한다.

## 7. Engineering 검증 결과

- Release x64 DX11 빌드 PASS
- 17개 section cache 변환 PASS
- 17개 preview 모두 1920×1017 PNG 저장 및 정상 종료
- `sec4`, `O-1X`, `yaw-slow-360` 60 Hz preview 정상 종료
- `sec4`, profile frame 60~62의 Original 5-way 축소 캡처:
  5 mode × 3 frame = 15 PNG 생성
- 기존 temporal lifecycle 회귀 검사 PASS:
  reset 36회, 처리 frame 112개, reprojection 44개, failure 0
- 검증 AutoBench root:
  `Projects/CMAA2/AutoBench/20260813_145911`
- lifecycle AutoBench root:
  `Projects/CMAA2/AutoBench/20260813_151524`

대량 preview 첫 실행에서 PNG 저장 후 완료 보고 문자열 포맷 때문에 접근 위반이 한 번
발생했다. minidump의 예외 스택에서 잘못된 `PASS` 포인터를 확인했고 가변 인자 `%s`를
문자열 결합으로 교체했다. 수정 후 `sec2` 단독 재실행과 17개 batch가 모두 exit code
0으로 끝났다. 렌더 메시 크기나 GPU 메모리 문제는 아니었다.

## 8. 한계와 다음 단계

- 원본은 실제 발전소 형상이지만 texture가 없는 오래된 geometry dataset이다.
- 현재 material은 source `Kd`를 opaque로 사용하고 double-sided 렌더링한다.
- section별 독립 정규화이므로 section 간 실제 크기 비교에는 사용하지 않는다.
- 현재 `-R` mode는 기존과 마찬가지로 camera-motion reprojection만 제공하며 object
  motion vector는 없다.
- 지금까지의 PNG는 장면/도구 검증 자료이며 dilation 효과의 근거가 아니다.

다음 구현은 기존 controlled `thin-lines`와 선정된 `sec4`를 함께 사용하여 current-frame
edge mask의 3×3/5×5/7×7 dilation 및 filtered downsample-upsample을 독립 toggle로
추가하는 것이다. 이후 O/A-1X, 대응 Standard T2X, 기존 ET2X와 비교해 얇은 구조 복구,
history 적용률, temporal variation/flicker, 고스팅과 GPU pass 시간을 함께 측정한다.
