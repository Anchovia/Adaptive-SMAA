# CMAA2 이동 + 부드러운 360° 카메라 경로

## 1. 목적과 분류

기존 `yaw-fast-360`은 고정 위치에서 60프레임 동안 360°를 회전하므로 프레임당
6°가 변하는 의도적인 급회전 stress다. 고스팅을 강하게 드러내는 데에는 유효하지만,
CMAA2 기본 benchmark처럼 자연스럽게 이동하는 카메라를 재현하지는 않는다.

이번 작업은 CMAA2 기본 flythrough의 Catmull–Rom 위치·방향 경로를 재사용하면서
부드러운 360° yaw를 더한 **결정적 camera-motion 실험 프로토콜**을 추가한다. 이는
새 SMAA/TSCMAA 알고리즘이나 품질 reference가 아니며 최종 8-case도 변경하지 않는다.

## 2. 추가한 세 control profile

| Profile | 위치 | 방향 | 용도 |
|---|---|---|---|
| `yaw-smooth-360` | 고정 | 부드러운 360° yaw | 회전만의 효과 분리 |
| `flythrough-smooth` | CMAA2 flythrough 곡선 | 원래 flythrough 방향 변화 | 이동만의 효과 분리 |
| `flythrough-smooth-yaw-360` | `flythrough-smooth`와 동일 | flythrough 방향 + 360° yaw | 이동과 회전의 결합 조건 |

세 profile은 fixed 60 Hz에서 다음 480프레임 timeline을 사용한다.

```text
60 frame pre-still
360 frame motion (6 seconds)
60 frame post-still
```

기존 `yaw-slow-360`, `yaw-fast-360`, `yaw-extreme-360`, `strafe-fast`,
`yaw-strafe-fast`는 변경하지 않고 이전 결과의 재현용으로 보존한다.

## 3. 부드러운 시간 함수

이동과 추가 yaw에는 같은 quintic smootherstep을 사용한다.

```text
S(t) = 6t^5 - 15t^4 + 10t^3
theta(t) = 2*pi*S(t)
```

`S'(0)=S'(1)=0`이므로 정지 구간에서 움직임 구간으로 들어갈 때와 움직임이 끝날 때
속도가 0으로 접속된다. 기존 급회전처럼 매 프레임 일정 각도를 갑자기 더하지 않는다.

## 4. CMAA2 기본 flythrough 재사용

`vaCameraControllerFlythrough::EvaluatePose`를 추가해 기존 benchmark controller가
사용하는 Catmull–Rom 위치와 fixed-up 방향을 임의 시간에서 부작용 없이 평가한다.
기존 `CameraTick`도 같은 evaluator를 사용하므로 기본 flythrough 동작과 새 실험 경로가
서로 다른 보간식을 갖지 않는다.

새 profile은 원본 flythrough의 1~7초 구간을 평가한다. 원본 곡선 모양은 유지하고
장면 기준 위치·yaw에 rigid transform으로 배치한다. 다른 장면에 원본 7.45 m 이동 폭을
그대로 옮기면 가구·벽·지형을 통과하므로 Bistro와 Minecraft에서는 위치 변화만
0.25배로 균일 축소했다. 최종 이동 거리는 약 1.86 m다. Minecraft의 기존 overview
위치는 카메라 바로 뒤에 지형이 있어 360° 중 mesh를 관통하므로, 기존 profile은
변경하지 않고 새 smooth profile에서만 높이를 10 m 올린 안전 기준점을 사용한다.

결합 profile의 불변 조건은 다음과 같다.

```text
position(flythrough-smooth-yaw-360) == position(flythrough-smooth)
forward(combined) == yawRotate(forward(flythrough-smooth), addedYaw)
```

## 5. 실행·검증 명령

```text
-smaaSmoothCameraMotionPathValidationTest
-smaaCameraMotionPreview "<scene> <profile> <semantic-mode> [repeatCount]"
-smaaCameraMotionSingleModeCapture "<scene> <profile> <semantic-mode> [firstProfileFrame] [captureFrames] [warmupFrames]"
```

`SingleModeCapture`는 경로 확인용 O-1X 영상처럼 한 mode만 저장해 불필요한 5-way 또는
10-way PNG 생성을 피한다. 품질 비교가 아니라 경로 재생 검증용이다.

## 6. 2026-08-20 engineering 검증 결과

Release x64, DirectX 11, RTX 3060 Ti, 1920×1017, SMAA Ultra에서 빌드와 자동 검증을
통과했다.

| Scene | Profile | 이동 거리 | 최대 위치 변화/프레임 | 최대 시야각 변화/프레임 |
|---|---|---:|---:|---:|
| Bistro | `yaw-smooth-360` | 0.000000 m | 0.000000 m | 1.874924° |
| Bistro | `flythrough-smooth` | 1.861286 m | 0.010701 m | 0.090654° |
| Bistro | `flythrough-smooth-yaw-360` | 1.861286 m | 0.010701 m | 1.785202° |
| Minecraft | `yaw-smooth-360` | 0.000000 m | 0.000000 m | 1.657176° |
| Minecraft | `flythrough-smooth` | 1.861285 m | 0.010700 m | 0.081565° |
| Minecraft | `flythrough-smooth-yaw-360` | 1.861285 m | 0.010700 m | 1.577932° |

두 장면 모두 시작·종료 정지 경계의 각도 step은 0°였다. 이동-only와 결합 profile의
최대 위치 mismatch는 0, 결합 방향의 최대 오차는 `3e-7` 미만, 추가 yaw 최대 step은
1.874955°였다.

보이는 창의 O-1X 실시간 preview 결과는 다음과 같다.

| Scene | 평균 frame-start 간격 | 최소 | 최대 | 결과 |
|---|---:|---:|---:|---|
| Bistro | 16.668 ms | 15.188 ms | 18.074 ms | PASS |
| Minecraft | 16.668 ms | 15.008 ms | 18.339 ms | PASS |

대표 프레임 0, 60, 150, 240, 330, 419, 479를 확인해 두 장면 모두 가구·벽·지형
관통이 없음을 확인했다. 연속 실행 중 Minecraft의 첫 preview가 장면 로딩 단계에서
`0xc0000409`로 한 차례 종료돼 빈 부분 결과를 폐기했다. clean-process와 GPU 메모리
복귀를 확인한 뒤 같은 명령을 독립 재실행해 정상 완료했으며 잔류 `CMAA2.exe`는 0개였다.

## 7. 생성한 전체 경로 자료

각 장면은 O-1X 480 PNG를 저장했으며 프레임 index `00000~00479`가 연속이다.

- Bistro: `D:\SMAA-Research-Data\AutoBench\20260820_060345`
- Minecraft: `D:\SMAA-Research-Data\AutoBench\20260820_060617`

발표·육안 확인용 MP4는 원본 1920×1017의 마지막 한 줄만 복제해 H.264가 요구하는
1920×1018로 만들었다. 두 파일 모두 전체 디코딩 결과 정확히 480프레임, 60 FPS,
8.00초를 통과했다.

- `D:\SMAA-Research-Data\AutoBench\20260820_060345\Playback60fps\O_1X_camera_path_60fps.mp4`
- `D:\SMAA-Research-Data\AutoBench\20260820_060617\Playback60fps\O_1X_camera_path_60fps.mp4`

MP4는 경로 재생과 발표용이다. 이후 정식 품질 지표에는 원본 PNG와 RGB-preserving
입력을 사용한다.

## 8. 현재 결론과 다음 단계

이번 단계에서 결론낼 수 있는 것은 다음뿐이다.

- 기존 6°/frame 고정 위치 회전과 별개로, CMAA2 flythrough 곡선 위에서 이동과
  360° 회전이 동시에 일어나는 부드럽고 결정적인 경로가 준비됐다.
- 이동-only, 회전-only, 결합 control이 수학적으로 대응하며 두 실제 장면에서 렌더
  가능한 시야를 유지한다.
- 아직 이 경로로 Standard T2X와 ET2X의 고스팅·temporal retention을 비교하지 않았으므로
  어느 방식의 품질이 더 좋다는 결론은 내리지 않는다.

다음 측정은 Bistro 저대비와 Minecraft 고대비를 분리해 같은 결합 경로에서 먼저
`O-1X`, `O-T2X-R`, `O-ET2X-R`을 비교한다. 회전-only와 이동-only control을 함께 사용해
카메라 이동, 회전, 결합 motion의 영향을 분리한다. 이 선행 결과에서 새 정보가 확인된
뒤에만 전체 8-case + O/A-1X와 supersample/CGVQM 측정으로 확대한다.

## 9. 3-way 선행 측정 완료

2026-08-20에 위 계획대로 Bistro/Minecraft의 세 profile에서 `O-1X`, `O-T2X-R`,
`O-ET2X-R` 전체 480-frame capture를 완료했다. 전용 명령은 다음과 같다.

```text
-smaaSmoothCameraFocusedThreeCapture "<scene> <profile> [firstProfileFrame] [captureFrames] [warmupFrames]"
```

여섯 조건에서 `O-ET2X-R`의 O-1X 대비 화면 차이는 Standard의 약 23.95~28.56%였고,
결합 profile은 개별 rotation/translation control 범위 안이었다. 세부 수치, 해석 제한,
capture root와 다음 reference gate는 다음 문서를 기준으로 한다.

- `Docs/SMAA-Smooth-Camera-Focused-Results-ko.md`
