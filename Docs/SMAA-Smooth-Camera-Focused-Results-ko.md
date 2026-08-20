# 부드러운 이동·회전 카메라 3-way 선행 측정 결과

## 1. 목적과 연구 범위

교수 피드백에 따라 제자리 급회전만 사용하는 기존 stress profile과 별도로 CMAA2 기본
flythrough의 Catmull-Rom 이동 위에 부드러운 360도 yaw를 더한 경로를 만들었다. 이번
측정은 이 경로에서 camera-motion reprojection을 사용하는 Standard T2X와
TSCMAA-inspired edge-selective T2X를 먼저 비교하는 선행 gate다.

비교 대상은 다음 세 mode다.

| ID | 의미 |
|---|---|
| `O-1X` | temporal history를 사용하지 않는 Original SMAA 1X spatial control |
| `O-T2X-R` | 전체 화면 Standard T2X + camera-motion reprojection |
| `O-ET2X-R` | current-edge 후보에만 history를 적용하는 document-profile edge-selective T2X + camera-motion reprojection |

`O-1X`는 같은 pose의 spatial control이지 temporal ground truth가 아니다. 따라서 이
문서에서 `O-1X`와의 차이는 화면에 나타난 **temporal 영향 대용값**으로만 사용하며,
절대 고스팅 점수로 표현하지 않는다. 이번 결과는 최종 8-case 또는 Adaptive 결론도
아니다.

## 2. 실험 행렬

장면은 실제 asset인 Bistro와 Minecraft만 사용했다.

| 장면 | 분류 |
|---|---|
| Bistro | 저대비 실제 렌더링 장면 |
| Minecraft | 고대비 실제 렌더링 장면 |

카메라 motion 성분을 다음 세 control로 분리했다.

| Profile | 이동 | 회전 | 목적 |
|---|---|---|---|
| `yaw-smooth-360` | 없음 | 부드러운 360도 yaw | 회전-only 영향 |
| `flythrough-smooth` | CMAA2 flythrough 곡선 | 원래 flythrough 방향 변화 | 이동-only 영향 |
| `flythrough-smooth-yaw-360` | 위와 동일한 위치 | flythrough 방향 + 부드러운 360도 yaw | 이동과 회전의 결합 영향 |

전체 행렬은 `2개 장면 x 3개 profile x 3개 mode = 18 sequence`다. 각 sequence는
fixed 60 Hz에서 60-frame pre-still, 360-frame motion, 60-frame post-still의 총
480 frame으로 구성된다.

공통 조건은 DirectX 11, Release x64, RTX 3060 Ti, 1920x1017, SMAA Ultra,
VSync Off다. PNG 저장이 포함된 품질 측정이므로 화면 표시 FPS나 성능 결과로 사용하지
않는다. `-R`은 depth와 현재·이전 camera matrix로 만든 camera-motion velocity를
사용하며 object motion vector는 연결되지 않았다.

## 3. 측정 자동화

비교 대상 세 mode만 같은 실행 안에서 순서대로 저장하도록 다음 명령을 추가했다.

```text
-smaaSmoothCameraFocusedThreeCapture "<scene> <profile> [firstProfileFrame] [captureFrames] [warmupFrames]"
```

각 mode 전환 시 temporal history를 초기화하고, mode마다 첫 pose에서 60 frame을
warm-up한다. 서로 다른 장면/profile 명령은 `Tools/SMAA/run_clean_cmaa2.ps1`로 독립
프로세스에서 실행했다. 모든 명령의 실행 전후 `CMAA2.exe` 개수는 0이었고 timeout이나
부분 실패 결과는 없었다.

전용 분석기는 다음 파일이다.

- `Tools/SMAA/analyze_smooth_camera_focused_quality.py`

분석기는 다음을 수행한다.

- 6개 capture root와 각 mode의 0~479 연속 index 검증
- 원해상도 same-frame RGB MAE
- 4픽셀 간격 표본의 인접 luma 변화, 2차 luma 차분과 edge strength
- `O-ET2X-R`의 O-1X 대비 차이를 `O-T2X-R`의 차이로 정규화한 temporal 영향 유지율
- post-still 마지막 10 frame plateau에 5 frame 연속 진입할 때까지의 안정화 frame
- full-frame 비교 시트, 4배 증폭 difference sheet와 3-way GIF
- 차이가 큰 640x360 구간을 자동 선택한 peak crop sheet
- 이전 결합 경로 `O-1X`와 현재 `O-1X`의 frame별 SHA-256 회귀 검사

인접 변화와 2차 차분이 낮아지는 현상은 temporal 안정화뿐 아니라 blur에서도 나타날 수
있다. edge strength가 O-1X에 가까운 것도 선명도 유지 대용값이지 aliasing 감소 증명은
아니다. plateau 안정화 frame도 ghost trail의 절대 길이가 아니라 정지 후 최종 필터
상태에 들어오는 시간이다.

## 4. 캡처 무결성

| Scene | Profile | Capture root | 결과 |
|---|---|---|---|
| Bistro | `yaw-smooth-360` | `D:/SMAA-Research-Data/AutoBench/20260820_144823` | 3 mode x 480 PASS |
| Bistro | `flythrough-smooth` | `D:/SMAA-Research-Data/AutoBench/20260820_145153` | 3 mode x 480 PASS |
| Bistro | `flythrough-smooth-yaw-360` | `D:/SMAA-Research-Data/AutoBench/20260820_145624` | 3 mode x 480 PASS |
| Minecraft | `yaw-smooth-360` | `D:/SMAA-Research-Data/AutoBench/20260820_150024` | 3 mode x 480 PASS |
| Minecraft | `flythrough-smooth` | `D:/SMAA-Research-Data/AutoBench/20260820_150325` | 3 mode x 480 PASS |
| Minecraft | `flythrough-smooth-yaw-360` | `D:/SMAA-Research-Data/AutoBench/20260820_150627` | 3 mode x 480 PASS |

총 8,640 PNG의 mode별 수량, 파일명과 profile/capture frame index를 검증했다. 새 결합
경로의 `O-1X`를 이전 경로 시각화 capture와 비교한 결과 Bistro와 Minecraft 모두
480 frame 중 SHA-256 mismatch가 0이었다. 따라서 독립 실행에서도 같은 카메라 pose와
spatial output이 재현됐다.

## 5. Motion 구간 정량 결과

`ET2X temporal 영향 유지율`은 다음 대용값이다.

```text
mean RGB MAE(O-ET2X-R, O-1X)
-------------------------------- x 100
mean RGB MAE(O-T2X-R, O-1X)
```

값이 낮을수록 edge-selective 출력이 Standard보다 O-1X에 가깝다. 이는 temporal history
영향 감소를 뜻하지만, 그 감소가 고스팅 제거인지 temporal supersampling 손실인지는 이
지표 하나로 구분할 수 없다.

| Scene | Profile | T2X-R to 1X RGB MAE | ET2X-R to 1X RGB MAE | ET2X temporal 영향 유지율 | T2X-R 인접 변화/1X | ET2X-R 인접 변화/1X |
|---|---|---:|---:|---:|---:|---:|
| Bistro | `yaw-smooth-360` | 2.1789 | 0.5219 | 23.95% | 98.22% | 98.51% |
| Bistro | `flythrough-smooth` | 2.1654 | 0.6060 | 27.99% | 94.07% | 94.98% |
| Bistro | `flythrough-smooth-yaw-360` | 2.2211 | 0.5642 | 25.40% | 98.29% | 98.45% |
| Minecraft | `yaw-smooth-360` | 1.7670 | 0.5000 | 28.30% | 96.44% | 97.07% |
| Minecraft | `flythrough-smooth` | 2.2209 | 0.6319 | 28.45% | 88.21% | 88.52% |
| Minecraft | `flythrough-smooth-yaw-360` | 1.7210 | 0.4916 | 28.56% | 96.33% | 96.94% |

여섯 조건에서 `O-ET2X-R`의 O-1X 대비 화면 차이는 Standard의 약 23.95~28.56%였다.
즉 current-edge 후보에만 resolve하는 현재 document profile은 history를 완전히 버리지는
않지만, 화면 전체에 나타나는 temporal 영향의 대부분을 제거하는 경향이 새 부드러운
경로에서도 재현됐다.

결합 motion의 유지율은 Bistro 25.40%, Minecraft 28.56%였다. 이는 같은 장면의
rotation-only와 translation-only 범위 안에 있다. 따라서 이동과 360도 회전을 결합했다고
해서 별도의 catastrophic temporal collapse가 추가로 발생했다는 증거는 없다.

## 6. 시간 변화와 선명도 대용값

| Scene/Profile | T2X-R 2차 차분/1X | ET2X-R 2차 차분/1X | T2X-R edge/1X | ET2X-R edge/1X |
|---|---:|---:|---:|---:|
| Bistro yaw | 97.93% | 98.07% | 96.41% | 97.74% |
| Bistro flythrough | 92.65% | 90.87% | 95.53% | 97.93% |
| Bistro combined | 98.08% | 98.03% | 96.49% | 97.69% |
| Minecraft yaw | 95.43% | 95.80% | 94.19% | 95.71% |
| Minecraft flythrough | 84.41% | 81.91% | 92.71% | 96.08% |
| Minecraft combined | 95.31% | 95.61% | 94.09% | 95.62% |

모든 조건에서 `O-ET2X-R` edge strength는 Standard보다 O-1X에 가까웠다. 이는
edge-selective 방식이 Standard의 전체 화면 filtering보다 spatial 선명도를 더 많이
유지한다는 근거다. 다만 O-1X의 aliasing도 함께 유지할 수 있으므로 품질 우위로 바로
해석하지 않는다.

인접 변화와 2차 차분은 두 temporal mode 모두 O-1X보다 낮은 경우가 많았다. 특히
이동-only에서 감소 폭이 컸지만, 이 full-frame 값에는 장면의 실제 camera motion이 크게
포함된다. 따라서 이 값만으로 shimmer 억제량이나 temporal sample 복구를 주장하지 않는다.

## 7. 정지 후 최종 상태 안정화

| Scene | Profile | O-T2X-R | O-ET2X-R |
|---|---|---:|---:|
| Bistro | `yaw-smooth-360` | 0 frame | 7 frame |
| Bistro | `flythrough-smooth` | 0 frame | 0 frame |
| Bistro | `flythrough-smooth-yaw-360` | 0 frame | 6 frame |
| Minecraft | `yaw-smooth-360` | 0 frame | 8 frame |
| Minecraft | `flythrough-smooth` | 0 frame | 1 frame |
| Minecraft | `flythrough-smooth-yaw-360` | 0 frame | 8 frame |

Standard는 여섯 조건 모두 post-still 첫 frame부터 최종 plateau 허용 범위 안에 있었다.
`O-ET2X-R`은 이동-only에서 0~1 frame이었지만 회전이 포함되면 6~8 frame이 필요했다.
이는 회전 후 candidate history가 최종 정지 상태로 수렴하는 짧은 transition이 있음을
보여준다. 이 수치는 최종 reference의 error-map 기반 ghost trail 길이가 아니므로
고스팅 유지 frame으로 명명하지 않는다.

## 8. 시각 자료 해석

full-frame 및 peak crop의 4배 difference map에서 Standard와 O-1X의 차이는 장면의 많은
경계에 넓게 나타났다. `O-ET2X-R`과 O-1X의 차이는 더 작고 edge 주변으로 제한됐다.
대표 프레임에서 화면 전체가 밀리거나 큰 이중상이 남는 catastrophic reprojection 오류는
관찰되지 않았다.

그러나 `O-ET2X-R`이 O-1X와 매우 가까운 것은 고스팅을 잘 제거했기 때문일 수도 있고,
temporal supersampling을 충분히 적용하지 않았기 때문일 수도 있다. 현재 자료만으로
“고스팅이 없고 temporal 효과도 유지된다”고 결론내리지 않는다.

분석 루트는 다음과 같다.

- `D:/SMAA-Research-Data/AutoBench/20260820_SmoothCameraFocused_3Way/Analysis`
- `SMAA-Smooth-Camera-Focused-Analysis-ko.md`
- `smooth_camera_focused_per_frame.csv`
- `smooth_camera_focused_summary.json`
- 장면/profile별 `comparison_sheet.png`
- 장면/profile별 `difference_sheet.png`
- 장면/profile별 `peak_crop_sheet.png`
- 장면/profile별 `motion_3way.gif`

## 9. 현재 결론

1. 새 부드러운 회전-only, 이동-only와 결합 경로에서 세 mode의 결정적 전체 시퀀스를
   확보했다.
2. current-edge document profile의 화면상 temporal 영향은 Standard의 약 24~29%로,
   temporal 범위를 크게 줄이는 기존 경향이 두 실제 장면과 세 motion 조건에서 재현됐다.
3. `O-ET2X-R`은 Standard보다 O-1X의 edge strength에 가까워 전체 화면 blur를 줄이는
   방향이지만, O-1X aliasing까지 더 많이 유지할 가능성이 있다.
4. 이동과 회전을 결합해도 temporal 영향 유지율은 개별 control 범위 안이었고, 대표
   프레임에서 catastrophic camera reprojection ghosting은 보이지 않았다.
5. 회전이 포함된 뒤 `O-ET2X-R`이 최종 정지 plateau에 들어오는 데 6~8 frame이 필요해,
   reference error map에서 이 transition을 다시 확인할 가치가 있다.
6. 따라서 현재 방식이 Standard보다 품질이 우수하거나 temporal supersampling을 충분히
   유지한다고 확정할 수 없다.

## 10. 다음 gate

다음 단계는 두 장면의 `flythrough-smooth-yaw-360` 결합 profile에 대해서만 동일 pose의
supersample spatial-reference를 우선 확보하는 것이다. 먼저 `O-1X`, `O-T2X-R`,
`O-ET2X-R`에 CGVQM-2와 error map을 적용해 다음을 확인한다.

- Standard의 전체 화면 history 차이가 reference 기준 개선인지 blur/ghost인지
- Edge-selective의 O-1X 유사성이 ghost 감소인지 temporal sample 손실인지
- 회전 종료 후 6~8 frame transition이 reference error에서도 나타나는지
- Bistro와 Minecraft에서 결과 방향이 재현되는지

이 reference gate에서 의미 있는 차이가 확인될 때만 같은 결합 경로를 최종 8-case와
Adaptive SMAA로 확대한다. candidate dilation과 filtered-quarter 결과는 이 camera-motion
reference 판정과 섞지 않고 별도 ablation으로 유지한다.

## 11. 후속 경로 선택 정정

이 문서의 정량 결과는 위치 변화 scale 0.25, 총 이동 약 1.86 m인
`flythrough-smooth` 계열의 **low-translation control 결과**다. 이동은 경로 검증상
정상이나 결합 yaw가 시각적으로 지배적이어서 실시간 화면에서는 제자리 회전처럼 보일 수
있다. 결과를 폐기하거나 재해석하지 않고 low-translation 조건으로 보존한다.

후속 reference gate에는 위치 scale 0.50, 총 이동 약 3.72 m인
`flythrough-wide-yaw-360`을 사용한다. 이 경로는 동일한 보간식과 480-frame timeline을
유지하면서 이동량만 2배로 늘렸고, 두 실제 장면에서 관통 없는 전체 O-1X 경로와 정확한
60 FPS 재생을 검증했다. 따라서 10절의 다음 gate에서 profile 이름을
`flythrough-smooth-yaw-360`이 아니라 `flythrough-wide-yaw-360`으로 적용한다.

wide 경로 자체는 카메라 프로토콜 보강일 뿐 새 품질 결과가 아니다. Standard와
Edge-selective의 품질 판단은 wide 동일-pose supersample reference를 확보한 뒤 수행한다.
