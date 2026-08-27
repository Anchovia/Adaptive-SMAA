# Adaptive SMAA / TSCMAA 연구 작업 규칙

이 파일은 저장소 전체에 적용되는 연구·구현 지침이다. 이후 작업자는 코드 수정, 실험 설계,
측정, 보고서 작성 전에 반드시 이 파일을 읽고 아래 실험 행렬과 용어를 유지해야 한다.
기존 문서나 임시 보고서가 이 파일과 충돌하면 이 파일을 우선하고, 충돌 내용을 사용자에게
알린 뒤 정정한다.

## 0.1 CMAA2 실행 프로세스 격리

- CMAA2 데모는 장시간 실행 시 메모리 사용량과 GPU 부하가 누적될 수 있으므로, 각 자동
  캡처·측정 명령은 새로운 독립 프로세스로 실행한다.
- 실행 전 기존 `CMAA2.exe` 프로세스가 0개인지 확인하고, 기존 프로세스가 있으면 새 측정을
  시작하지 않는다.
- 명령이 완료되거나 실패한 뒤 해당 프로세스가 완전히 종료됐고 잔류 CMAA2 프로세스가
  0개인지 확인한 다음에만 다음 명령을 시작한다.
- 한 benchmark 명령 안의 mode/repeat 순회는 같은 실험 실행으로 보되, 서로 다른 benchmark
  명령을 같은 데모 프로세스에 이어 붙이지 않는다.
- 렌더 준비나 캡처가 지정된 wall-clock timeout을 넘으면 무한 대기 가능성이 있는 것으로
  분류하고, 해당 실행에서 시작한 프로세스만 종료한다. 부분 결과는 정식 결과로 사용하지 않는다.
- 자동 실행에는 가능한 한 `Tools/SMAA/run_clean_cmaa2.ps1` 또는 장면별 clean runner를
  사용해 위의 실행 전·후 조건과 timeout을 기계적으로 적용한다.

## 1. 최종 연구 목표

연구의 최종 비교 대상은 다음 세 개의 독립 변수를 조합한 **총 8개 case**다.

1. 공간 SMAA: Original / Adaptive
2. temporal 처리: Standard full-screen T2X / TSCMAA-inspired edge-selective T2X
3. motion reprojection: Off / On

### 원본 SMAA 기반 4개

| ID | 공간 처리 | Temporal 처리 | Motion reprojection |
|---|---|---|---|
| `O-T2X` | Original SMAA | Standard T2X | Off |
| `O-T2X-R` | Original SMAA | Standard T2X | On |
| `O-ET2X` | Original SMAA | TSCMAA-inspired edge-selective T2X | Off |
| `O-ET2X-R` | Original SMAA | TSCMAA-inspired edge-selective T2X | On |

### Adaptive SMAA 기반 4개

| ID | 공간 처리 | Temporal 처리 | Motion reprojection |
|---|---|---|---|
| `A-T2X` | Adaptive SMAA | Standard T2X | Off |
| `A-T2X-R` | Adaptive SMAA | Standard T2X | On |
| `A-ET2X` | Adaptive SMAA | TSCMAA-inspired edge-selective T2X | Off |
| `A-ET2X-R` | Adaptive SMAA | TSCMAA-inspired edge-selective T2X | On |

버전 번호인 V1, V2, V3만 단독으로 사용하지 않는다. UI, 로그, 폴더, 표, 보고서에서는 위의
semantic ID와 전체 이름을 사용한다.

## 1.1 최우선 과제

8개 case의 본 측정이나 Adaptive 결합보다 먼저 **Intel 공개 문서에 부합하는
TSCMAA-inspired SMAA core를 구현하고 검증**한다.

- Intel TSCMAA는 본래 `CMAA + edge-selective TAA`이며, 이 연구는 그 구조를 SMAA에
  적용하는 adaptation이다.
- 공개된 원본 sample source를 확보하지 못한 상태이므로 “완벽한 공식 TSCMAA 재현” 또는
  “공식 TSCMAA 포팅”이라고 표현하지 않는다.
- 목표 표현은 `Intel TSCMAA 공개 문서에 부합하는 SMAA adaptation`이다.
- 공개 자료로 확정되지 않는 candidate selection, Catmull-Rom 좌표/가중치, variance
  clipping 세부식은 구현 가정과 출처를 기록하고 ablation 가능하게 만든다.
- 이 core의 기능 검증이 끝나기 전에는 8-case 최종 품질·성능 측정을 시작하지 않는다.

## 1.2 현재 구현을 다루는 방향

지금까지의 T2X/TSCMAA-inspired 작업은 폐기 대상이 아니라 **document-based controlled
implementation을 만들기 위한 기초 틀**이다. 다음 구현 계획을 기준 문서로 사용한다.

- `Docs/SMAA-TSCMAA-Implementation-Plan-ko.md`

기존 구현은 다음 원칙으로 다룬다.

- 구현된 `O-T2X`와 `O-T2X-R`은 기준선으로 보존하고 회귀가 생기지 않게 한다.
- history texture, ping-pong, reset lifecycle, camera reprojection, candidate buffer,
  indirect dispatch, 자동 캡처·분석 도구는 가능한 한 재사용한다.
- 기존 Catmull-Rom 5-tap과 YCoCg variance clipping 코드는 초기 구현으로 재사용할 수
  있지만, 공식 자료로 확인되지 않은 세부식은 독립 toggle로 분리하고 reference test를
  통과해야 한다.
- 현재 `O-ET2X-R` prototype은 구현 가능성을 확인한 단계이지 최종 controlled
  `O-ET2X-R`이 아니다. 코드를 삭제하기보다 후보 선택, reprojection, jitter, sampling,
  clipping과 history weight를 직교 설정으로 분해·검증한다.
- 기존 3x3 local mean/max 후보식은 공식 TSCMAA 후보식으로 사용하지 않고
  `ExperimentalLocalMeanMax3x3` ablation으로만 보존한다.
- 기존 복합 구현의 캡처와 측정은 디버깅·도구 검증 자료로 보존하되 최종 8-case 결론에는
  사용하지 않는다.
- 리팩터링 전후를 별도 커밋으로 남겨 기존 동작과 새 controlled 구현을 언제든 비교할 수
  있게 한다.

즉, 다음 작업은 처음부터 다시 작성하는 것이 아니라 현재 기초 틀을 보존하면서 공식
자료로 확인된 동작과 SMAA adaptation 가정을 분리·검증하는 작업이다.

## 2. SMAA T2X와 motion reprojection의 관계

- 이전 프레임과 현재 프레임을 결합하는 Standard SMAA T2X가 기본 방식이다.
- motion vector를 이용한 reprojection은 Standard SMAA T2X의 optional 확장이다.
- 따라서 reprojection Off와 On은 반드시 별도 case로 유지한다.
- 현재 프로젝트의 reprojection은 depth와 이전·현재 카메라 행렬에서 만든 camera-motion
  velocity를 사용한다. object motion vector 지원 여부는 별도로 기록해야 한다.
- camera-motion reprojection을 object-motion reprojection으로 표현하면 안 된다.
- Intel 공식 TSCMAA 문서의 history sampling 단계에는 depth와 현재·이전 view/projection을
  이용한 reprojection이 포함된다.
- 따라서 `O-ET2X-R`과 `A-ET2X-R`이 문서 기반 TSCMAA adaptation의 중심 case다.
- reprojection Off인 `O-ET2X`와 `A-ET2X`는 공식 TSCMAA 동작이 아니라, 8-case 연구를
  위해 reprojection의 효과를 분리하는 **no-reprojection ablation**이다.
- 보고서에서 reprojection Off case를 “원본 공식 TSCMAA”라고 부르면 안 된다.

## 3. TSCMAA-inspired 비교 원칙

- TSCMAA-inspired 방식도 reprojection Off와 On을 각각 구현해야 한다.
- `O-ET2X` 또는 `A-ET2X`를 생략하고 reprojection 버전만 측정하면 8-case 연구가 아니다.
- 핵심 비교에서는 대응하는 Standard T2X와 temporal sample pattern, jitter, history weight,
  history 초기화 규칙을 가능한 한 동일하게 유지하고, edge 후보 선택 여부만 우선적으로
  분리한다.
- no-jitter, Catmull-Rom sampling, variance clipping, 다른 history weight 같은 추가 변경은
  각각 별도의 ablation 옵션으로 취급한다. 여러 변경을 한 번에 넣은 복합 버전을
  “TSCMAA 적용 효과”라고 단정하지 않는다.
- Intel 공개 TSCMAA 자료를 참고하되, 공개된 완전한 공식 소스 포팅이 아니므로
  `TSCMAA-inspired` 또는 `document-based adaptation`이라고 표현한다.

### Intel 문서로 확인된 필수 core 항목

- edge detection 후보 중 일부만 temporal 후보로 compact
- 후보 목록을 이용한 indirect shader dispatch
- 현재 depth와 view/projection을 이용한 history coordinate reprojection
- 5-tap Hermite/Catmull-Rom bicubic approximation
- YCoCg variance clipping
- temporal 후보의 history weight `0.8`
- 비후보의 history weight `0.0`, 즉 현재 spatial AA 결과 유지
- 최종 resolve 결과를 다음 프레임 history로 feedback
- edge threshold 기본값 `1/22`
- non-dominant edge removal 기본값 `0.5`
- TAA 후보량은 CMAA edge 후보의 약 50%를 기본 목표로 하되 장면별 실제 수치를 기록

위 항목의 구현과 검증표가 완료되기 전에는 “TSCMAA core 완료”로 표시하지 않는다.

## 4. 2026-08-20 현재 구현 상태

| ID | 상태 | 현재 코드 대응 |
|---|---|---|
| `O-T2X` | 구현됨 | `SMAA_O_T2X`; 같은 좌표의 current/previous를 기본 0.5 weight로 결합 |
| `O-T2X-R` | 구현됨 | `SMAA_O_T2X_R`; camera-motion velocity 사용 |
| `O-ET2X` | document profile 조립·engineering 검증 완료 | `SMAA_O_ET2X`; 같은 좌표의 history를 사용하는 no-reprojection ablation |
| `O-ET2X-R` | document profile 조립·engineering 검증 완료 | `SMAA_O_ET2X_R`; edge-selective + camera reprojection On |
| `A-T2X` | 구현·engineering 검증 완료 | `SMAA_A_T2X`; Adaptive SMAA + Standard T2X |
| `A-T2X-R` | 구현·engineering 검증 완료 | `SMAA_A_T2X_R`; Adaptive SMAA + Standard T2X + camera reprojection |
| `A-ET2X` | 구현·engineering 검증 완료 | `SMAA_A_ET2X`; Adaptive SMAA + edge-selective no-reprojection ablation |
| `A-ET2X-R` | 구현·engineering 검증 완료 | `SMAA_A_ET2X_R`; Adaptive SMAA + edge-selective + camera reprojection |

8개 mode는 공간 처리를 `SpatialSearch::Original/AdaptiveContrast`로, temporal 처리를
`TemporalCoverage`, `ReprojectionMode`, `JitterPolicy`, history sampler, clipping,
candidate policy와 history weight로 각각 명시하는 설정 구조에 연결되어 있다. Adaptive
공간 mode에서만 RG8 edge + R8 contrast metadata MRT와 대비별 탐색 범위를 사용하며,
Original mode는 기존 edge target/shader path를 유지한다.

후보 추출·계측 단계에는 다음이 구현되어 있다.

- 별도 full-resolution luma edge와 threshold `1/22`
- `AllBaseEdges`, `IntelFamilyNonDominant`, `ExperimentalLocalMeanMax3x3` 세 정책
- `IntelFamilyNonDominant`는 Intel CMAA2의 연결된 수직 edge local-contrast 구조를
  TSCMAA 공개 기본값과 결합한 adaptation이며 유실된 원본 식과 동일하다고 표현하지 않음
- candidate compact/indirect process·group count와 비동기 GPU readback
- base edge/candidate debug mask와 개발 UI
- `-smaaCandidatePolicyOverride`, `-smaaHistorySamplerOverride`,
  `-smaaHistoryClippingOverride`, `-smaaTemporalDebugView`,
  `-smaaCandidateForcedCount` 진단 옵션
- `-smaaTemporalLifecycleTest` 자동 검증: 8개 mode 전부의 first-frame seed, history
  ping-pong, jitter/subsample pairing, first-frame matrix 상태와
  mode/scene/camera-cut/resize reset
- `-smaaTemporalVelocityTest` GPU 검증: 정적 카메라 velocity 0, 알려진 +right 이동의
  velocity 부호와 `historyUV = currentUV - velocity` 화면 범위 확인
- `-smaaTemporalFeedbackTest` GPU 검증: 최종 output history와 화면 destination의
  byte 일치, 다음 프레임 previous history와 직전 resolve hash의 일치 확인
- `-smaaStaticStabilityTest` GPU 검증: 고정 카메라·노출에서 `O-ET2X`와
  `O-ET2X-R`를 각각 120프레임 warm-up한 뒤 32개 연속 resolve hash 일치 확인
- `-smaaCatmullRomReferenceTest` GPU/CPU 검증: 실제 5-tap shader의 상수 보존,
  clamp 경계, CPU mirror 일치와 separable 16-tap reference 오차 기록
- `-smaaVarianceClippingTest` GPU/CPU 검증: YCoCg 왕복, 상수 이웃, box 내부 history,
  outlier 제한과 유한값 확인
- `-smaaCandidatePolicyValidationTest` 자동 검증: Bistro/Minecraft에서 Intel-family
  removal 0/0.25/0.5/0.75/1 sweep, base 안정성·단조성·indirect count 확인
- `-smaaOriginalFourPerformanceSmoke` 자동 검증: PNG를 저장하지 않고 Original 네
  mode의 WholeFrame, SMAA total과 spatial, camera velocity, candidate 준비·추출,
  indirect args, candidate resolve, output copy GPU timestamp를 같은 동적 경로에서 기록
- `-smaaOriginalFourPerformanceBenchmark`: 기본 300프레임 warm-up, 4,800프레임 측정,
  3회 반복. 정방향/역방향 mode 순서를 교차하고 UI·PNG·candidate readback을 끈 상태에서
  wall frame interval, WholeFrame과 SMAA pass GPU timestamp, p95/p99, 1% low 및
  run-mean 표준편차를 기록
- `-smaaEightCasePerformanceSmoke` / `-smaaEightCasePerformanceBenchmark`: 같은 계측
  코드와 통계 정의로 전체 8개 mode를 순회. 본 측정 명령의 기본 조건은 300 warm-up,
  4,800 measurement, 3 repeats이며 candidate readback을 끔
- `-smaaOriginalFourCapture` / `-smaaEightCaseCapture`: 각각 Original 4개 또는 전체
  8개 mode의 동일 frame index PNG sequence를 별도 디렉터리에 저장
- `-smaaOneXStressCapture`: `O-1X`와 `A-1X`를 전용 `thin-lines`,
  `object-motion`, `combined` stress timeline에서 캡처하는 spatial-only 품질 control.
  최종 8-case를 늘리는 mode가 아니라 SMAA 1X 대비 temporal 효과를 확인하는 기준군
- `Tools/SMAA/analyze_original_four_quality.py`: Original 네 mode의 정렬된 PNG
  sequence를 검증하고 temporal MAE, 2차 시간 차분, edge strength, 짝·홀 위상 gap,
  대응 mode 차이와 ±2프레임 정렬을 계산하며 contact sheet, 대표 PNG, pair GIF와
  연속 frame/difference sheet 생성. `--include-adaptive`를 지정하면 8개 mode와
  Original↔Adaptive 대응 pair까지 분석하고 `--scenario`로 Bistro 또는 전용 stress
  capture의 provenance를 기록
- `Tools/SMAA/analyze_temporal_stress_quality.py`: 전용 stress capture의 thin-line,
  occluder/disocclusion, rotor ROI를 분리해 인접 frame MAE, 2차 시간 차분, edge
  strength와 대응 mode 차이를 계산. 움직이는 occluder 뒤 36픽셀의 trail darkness/width
  휴리스틱과 ROI 비교 GIF·6-frame difference sheet를 생성하며 절대 ghosting
  ground truth로 표현하지 않음
- `Tools/SMAA/analyze_smaa_1x_controls.py`: `O-1X`/`A-1X` control과 기존 temporal
  8-case stress capture를 같은 frame/ROI에서 검증·비교. 1X 대비 temporal MAE,
  2차 시간 차분, edge strength와 trail 휴리스틱을 계산하고 1X/Standard/Edge-selective
  3-way GIF·sequence sheet 생성
- `Tools/SMAA/analyze_optical_flow_temporal_quality.py`: `O-1X`에서 Farneback
  dense flow를 계산해 Original component ablation mode의 이전 frame을 현재 frame으로
  정렬. forward/backward consistency로 불일치·화면 밖 좌표를 제외하고 motion-compensated
  residual, 유효 비율과 flow 진단 이미지를 생성
- `Tools/SMAA/analyze_eight_case_optical_flow_quality.py`: 별도 1X control과 temporal
  8-case stress capture를 연결해 Original에는 O-1X flow, Adaptive에는 A-1X flow를
  공통 적용. spatial 1X 대비와 세 독립 축의 aligned residual을 분리
- `-smaaSupersampleStressReferenceCapture`: `thin-lines`, `object-motion`,
  `combined` stress timeline을 2× 선형 해상도, frame당 3×3 subpixel grid와
  8×MSAA의 `SuperSampleReference`로 캡처. 한 출력 프레임 동안 장면 상태를 고정하고
  temporal history는 사용하지 않으므로 spatial-reference proxy로 분류
- `Tools/SMAA/analyze_supersample_reference_quality.py`: supersample spatial
  reference와 `O-1X`, `O-T2X-R`, candidate jitter On/Off ablation을 같은 frame/ROI로
  검증. RGB MAE, PSNR, luma SSIM, edge/reference 비율과 대표 5-way GIF·difference
  sheet를 생성하며 temporal ground truth로 표현하지 않음
- `Tools/SMAA/run_cgvqm_png_sequences.py`: frame-aligned PNG test/reference
  sequence의 index·해상도·pixel hash를 검증하고 RGB 계열 FFV1로 무손실 변환한 뒤
  Intel 공식 CGVQM을 호출. decoded RGB 전체가 원본과 pixel-exact인지 확인하고
  score, error-map 통계, per-frame CSV와 error-map 영상을 생성. 부분 capture의 index가
  다시 0부터 시작하는 경우 `--reference-index-offset`으로 원래 profile reference frame과
  명시적으로 대응하며 test/reference의 실제 index 범위를 각각 결과에 기록
- `Tools/SMAA/analyze_candidate_jitter_real_scene_quality.py`: Bistro/Minecraft의 실제
  세부 구조 ROI에서 새 5-way temporal-retention capture를 기존 supersample spatial
  reference와 비교. O-1X formal hash bridge, RGB/PSNR/structure/edge/time-change 지표,
  candidate 비율과 offline 3×3/5×5/7×7 및 filtered 1/4 mask coverage proxy, 비교
  PNG/GIF를 생성. Offline mask 확장을 실제 resolve 품질·성능 결과로 표현하지 않음
- `Tools/SMAA/create_camera_motion_playback.py`: PNG 품질 capture와 화면 재생을 분리해
  단일 mode와 지정 mode 비교 영상을 H.264/MP4 constant 60 FPS로 생성. 단일 mode만
  존재하는 경로 확인 capture에는 `--single-only`를 사용한다. 전체 영상을
  다시 decode해 frame 수, average rate와 PTS 증가를 검증하며 발표·육안 확인용으로만
  사용
- `yaw-smooth-360`, `flythrough-smooth`, `flythrough-smooth-yaw-360`: fixed 60 Hz에서
  각각 회전-only, CMAA2 Catmull-Rom 이동-only, 동일 이동+부드러운 360° yaw를 제공하는
  480-frame control profile. `-smaaSmoothCameraMotionPathValidationTest`로 위치·방향
  연속성과 control pairing을 확인하고 `-smaaCameraMotionSingleModeCapture`로 경로
  시각화용 한 mode만 저장한다. 알고리즘 또는 품질 reference로 분류하지 않는다.
- `flythrough-wide`, `flythrough-wide-yaw-360`: 기존 smooth flythrough의 위치 변화만
  0.25 scale에서 0.50 scale로 늘려 약 3.72 m translation을 제공하는 이동-only/결합
  control. 완료된 low-translation 결과를 변경하지 않으며, 후속 camera-motion
  supersample reference에는 wide 결합 profile을 사용한다.
- `-smaaSmoothCameraFocusedThreeCapture`: 위 세 profile에서 `O-1X`, `O-T2X-R`,
  `O-ET2X-R`만 같은 실행에 저장하는 선행 quality gate. 최종 8-case를 변경하지 않으며
  mode마다 history를 초기화하고 같은 첫 pose warm-up을 적용한다.
- `Tools/SMAA/analyze_smooth_camera_focused_quality.py`: Bistro/Minecraft의
  rotation-only, translation-only, combined 18 sequence를 검증하고 O-1X 대비 temporal
  영향 대용값, 시간 변화, edge strength, post-still plateau 안정화와 full/difference/
  peak-crop/GIF 자료를 생성한다. O-1X 차이를 절대 ghosting ground truth로 표현하지 않는다.
- `Tools/SMAA/analyze_wide_camera_reference_quality.py`: Bistro/Minecraft wide 결합
  profile의 `O-1X`, `O-T2X-R`, `O-ET2X-R` 480-frame sequence를 동일 pose의
  supersample spatial reference와 비교한다. RGB MAE/PSNR, luma SSIM, edge strength,
  O-1X 독립 capture hash bridge와 representative/difference sheet를 생성한다.
- `Tools/SMAA/analyze_wide_camera_cgvqm.py`: wide 결합 profile의 central-motion과
  motion→still 구간 12개 formal CGVQM-2 결과, Intel commit/CUDA/FFV1 round-trip과
  reference hash를 검증한다. official score는 변경하지 않고, R3D-18 CGVQM-2 경로의
  5-frame temporal receptive-field radius를 반영한 per-frame 보조 진단만 별도 생성한다.
- `Tools/SMAA/analyze_eight_case_performance.py`: 8-case 반복 성능 CSV의 내부 PASS,
  mode별 표본 수와 반복 수, candidate readback Off를 검증하고 Original↔Adaptive,
  Standard↔Edge-selective, reprojection Off↔On 효과를 각각 분리한 CSV/JSON/한글
  Markdown 생성. `--window-state`와 `--classification`을 반드시 실제 실행 조건에
  맞게 기록
- `-smaaCandidateStatisticsReadback 0|1`: 후보 카운터용 비동기 GPU→CPU readback을
  성능 측정과 분리. forced-count 진단에서는 정확성 검증을 위해 설정과 무관하게 readback
  수행
- `-smaaCandidateReadbackOverheadTest`: `O-ET2X`/`O-ET2X-R`에서 readback Off/On만
  바꾼 짝 비교로 SMAA GPU/CPU scope 오버헤드를 기록
- temporal debug view 4/5/6: 후보 픽셀의 clipping 전 history, clipping 후 history,
  8배 clipping delta. 이 R16G16B16A16 debug resource는 해당 view에서만 할당한다.
- `CandidateExpansion::Dilate3x3`: raw current-edge candidate mask에 정확한 3×3
  max-filter를 적용하고, 확장된 mask만 compact/indirect resolve로 넘기는 직교 ablation.
  Candidate-Jitter와 document profile 각각 None/3×3 비교 mode를 유지한다.
- `-smaaCurrentEdgeDilationAblationCapture`: 두 profile의 None/3×3 네 mode를 같은
  camera path에서 캡처하고 별도 current-spatial/candidate-mask capture와 대응시킨다.
- `-smaaCurrentEdgeDilationPerformanceSmoke` /
  `-smaaCurrentEdgeDilationPerformanceBenchmark`: raw extraction, 3×3 dilation,
  indirect resolve와 전체 SMAA GPU 시간을 분리하는 전용 성능 matrix.
- `Tools/SMAA/analyze_current_edge_dilation_quality.py`와
  `analyze_current_edge_dilation_performance.py`: GPU mask의 정확한 3×3 검증,
  반복 hash, reference/temporal/coverage 지표와 반복 성능 CSV를 검증·분석한다.
- `CandidateExpansion::FilteredQuarter`: raw current-edge candidate를 유효 4×4 block 평균으로
  quarter-resolution R8_UNORM mask에 저장하고 half-pixel bilinear로 full resolution에
  복원한 뒤, raw candidate와 복원값 0.25 이상 mask를 합집합해 compact하는 직교
  ablation. nearest-neighbor는 사용하지 않으며 원래 raw 후보를 지우면 검증 실패다.
- `-smaaFilteredQuarterAblationCapture`와
  `-smaaFilteredQuarterPerformanceSmoke`/`Benchmark`: Candidate-Jitter와 document profile의
  None/3×3/Filtered 총 6개 mode를 동일 camera path에서 비교하고 quarter downsample,
  upsample/compact 및 전체 SMAA GPU 시간을 분리한다.
- `Tools/SMAA/analyze_filtered_quarter_quality.py`와
  `analyze_filtered_quarter_performance.py`: 6-mode sequence, 3×3 exact CPU mask,
  filtered CPU mirror의 threshold-boundary mismatch, 후보 배수와 timing 표본을 검증한다.
- `CandidateExpansion::ArmDualFilter`: ARM SIGGRAPH 2015 공개 5-tap downsample과 8-tap
  upsample kernel을 full→half→quarter→half→full R8 mask pyramid에 적용한다. 최종 mask는
  raw selected candidate와 `reconstruction>=0.25`를 union해 원본 current edge를 보존한다.
  pyramid 깊이, half-pixel 규칙, R8 형식, threshold와 raw union은 SMAA 연구 adaptation이며
  ARM 또는 Intel의 공식 SMAA/TSCMAA 구현이라고 표현하지 않는다.
- `-smaaArmDualFilterAblationCapture`와
  `-smaaArmDualFilterPerformanceSmoke`/`Benchmark`: Candidate-Jitter와 document profile의
  None/3×3/Filtered/ARM 총 8개 mode를 비교하고 네 ARM filter pass를 따로 계측한다.
- `Tools/SMAA/analyze_arm_dual_filter_quality.py`와
  `analyze_arm_dual_filter_performance.py`: ARM CPU mirror, raw 보존, threshold-boundary
  mismatch, reference/temporal 지표, timing/pass/counter 표본을 검증한다.
- `Tools/SMAA/analyze_san_miguel_arm_dual_thin_roi.py`: San Miguel `yaw-fast-360` frame
  0~9의 화면 좌측·하단 의자/테이블 다리 ROI를 supersample spatial reference와 비교한다.
  화면 고정 ROI이며 object tracking이나 절대 temporal ground truth로 표현하지 않는다.
- `-smaaArmDualFilterPerformanceSmoke`/`Benchmark`의 값 앞에 선택적으로
  `bistro|minecraft|sanmiguel`을 지정하면 해당 장면의 `yaw-fast-360` profile frame
  60부터 측정하고 warm-up 동안 첫 pose를 유지한다. 장면 토큰을 생략한 기존 명령은
  기존 Bistro flythrough 동작을 유지한다.
- Object-motion reprojection 구현 전 설계 감사는
  `Docs/SMAA-Object-Motion-Reprojection-Design-Audit-ko.md`를 기준으로 한다. 현재 `-R`은
  여전히 camera/depth reprojection만 의미한다. Rigid-object velocity 1차 구현은 previous
  rigid world transform을 draw entry에 전달하고 기존 full-screen camera velocity 위에
  움직인 opaque object의 현재-depth 일치 pixel만 덮어쓰는 default-Off engineering
  toggle로 추가됐다. `-smaaObjectMotionReprojectionOverride 1`로만 활성화하며
  `-smaaRigidObjectVelocityTest`에서 camera-only 0 pixel, rigid On 21,284 pixel(1.090011%),
  history UV 100% in-bounds로 PASS했다. 기존 camera velocity와 8-mode lifecycle 회귀도
  PASS했다. Temporal feedback mismatch와 static-stability history hash 변화도 0으로
  PASS했다. Skinned/deforming/transparent motion과 previous-depth disocclusion
  rejection은 별도 후속 범위다. 품질·성능 gate 전에는 기존 8-case `-R` 의미나
  formal 결과를 변경하지 않는다.

`IntelFamilyNonDominant`는 removal sweep와 기존 mask/buffer 검증을 통과해 document
profile의 기본 adaptation 정책으로 조립했다. 다만 유실된 Intel TSCMAA 원본 식과
동일하다고 표현하지 않는다. 이전 `ExperimentalLocalMeanMax3x3` 정책은 ablation
override로 보존한다.

동일 deterministic smoke 프레임에서 base edge 57,354개 중 AllBase 57,354개,
Intel-family 34,938개(60.916%), Experimental 44,266개(77.180%)가 선택됐고 indirect
process count는 candidate count와 일치했다. 이는 구현 검증용 한 프레임 결과이며 최종
품질·성능 결과가 아니다.

forced-count 진단으로 0, 1, 63, 64, 65와 전체 화면 최대 1,952,640 후보를 GPU에서
실제로 compact한 뒤 전체 candidate buffer를 readback했다. 모든 case에서 candidate와
process count, `ceil(count/64)` group count가 기대값과 일치했고 중복·범위 밖·overflow는
0이었다. 전체 candidate-list staging buffer는 진단 옵션이 켜진 경우에만 생성하며 본
성능 측정에는 포함하지 않는다.

현재 `O-ET2X`와 `O-ET2X-R` 기본 document profile은 다음 설정을 사용한다.

- deliberate projection jitter 비활성화
- SMAA 1X spatial input
- `IntelFamilyNonDominant`, edge threshold `1/22`, removal `0.5`
- `O-ET2X`는 같은 좌표 history, `O-ET2X-R`은 camera-motion history reprojection
- Catmull-Rom 5-tap history sampling
- YCoCg variance clipping
- history weight 0.8

Catmull-Rom 5-tap과 YCoCg variance clipping은 실제 shader 분기와 diagnostic override로
분리되어 있다. `ExperimentalLocalMeanMax3x3 + Bilinear + Clipping Off` override로
이전 controlled skeleton 출력도 정확히 재현한다. 비후보는 현재 spatial 결과를 유지하고
후보만 indirect resolve가 덮어쓰는지 픽셀 단위로 검증했다. history lifecycle,
camera-motion GPU velocity/history UV 방향, Catmull-Rom 5-tap GPU/CPU reference,
YCoCg variance clipping GPU/CPU 불변 조건과 Intel-family candidate 정책을 검증했다.
document profile 조립 후 두 번의 engineering capture와 lifecycle 자동 검증도 통과했다.
최종 resolve 결과의 history feedback도 diagnostic-only GPU staging readback으로
검증했다. 이는 기능·회귀 검증 완료를 의미하며 최종 품질·성능 결론은 아니다.

Original 네 mode의 내부 pass GPU timestamp도 mode당 60프레임 warm-up, 120프레임
engineering smoke에서 모두 120/120개 수집했다. 이 smoke는 비동기 candidate counter
readback을 켠 현재 경로를 측정하며 전체 frame GPU time은 포함하지 않는다. 단일 실행
값은 최종 성능 우열이나 통계적 유의성 주장에 사용하지 않는다.

후보 카운터 readback은 출력 알고리즘과 분리해 On/Off 가능하다. RTX 3060 Ti,
1920×1017, mode/profile당 60프레임 warm-up과 180프레임 측정의 단일 engineering
smoke에서 readback On은 Off보다 SMAA GPU 평균이 `O-ET2X` 0.019740 ms(6.643%),
`O-ET2X-R` 0.021550 ms(6.574%) 높았다. CPU 차이는 일관된 방향이 아니었다. 두
edge-selective mode의 readback Off/On PNG는 각각 byte-identical했다. 이 결과는
계측 오버헤드를 본 성능에서 제외해야 한다는 근거이며 최종 성능 결론이 아니다.
후보 수 특성화 실행은 readback On, timing 본 실행은 readback Off로 분리한다.

전체 frame profiler가 0을 반환하던 원인은 `CMAA2Sample::OnTick`에서 한 frame에
`BeginFrame`을 두 번 호출하던 로컬 기준선 수명주기 오류였다. Intel 공식 CMAA2
렌더 루프처럼 한 번만 호출하도록 복구했다. 수정 후 readback Off, 60프레임 warm-up,
120프레임 engineering smoke에서 네 mode 모두 `WholeFrame` GPU timestamp 120/120개를
수집했다. `WholeFrame`은 BeginFrame부터 EndAndPresentFrame 직전까지의 GPU work이며
Present 자체는 제외한다. temporal lifecycle과 네 mode 출력 hash 회귀도 통과했다.

반복 본 측정용 `-smaaOriginalFourPerformanceBenchmark`도 3회×mode당 32프레임의
축소 검증에서 모든 expected metric 96/96개, run mean 3/3개를 수집하고 PASS했다.
`ApplicationFrameWall`은 동일 AutoBench tick 사이의 실제 CPU wall interval로
Present와 OS scheduling을 포함한다. `WholeFrame` 기반 FPS는 GPU-equivalent throughput로
별도 표기하며 실제 표시 FPS와 혼동하지 않는다.

2026-07-30 Original 네 mode의 첫 반복 본 성능 측정을 완료했다. RTX 3060 Ti,
1920×1017, 기본 조건(300 warm-up, 4,800 measurement, 3 repeats)에서 mode별
14,400 표본과 run mean 3개를 모두 수집했고 validation은 PASS했다. candidate readback
Off 성능 결과는 다음과 같다.

| ID | WholeFrame GPU 평균 | SMAA GPU 평균 | Wall 평균 FPS |
|---|---:|---:|---:|
| `O-T2X` | 2.779183 ms | 0.236075 ms | 305.817 |
| `O-T2X-R` | 2.835895 ms | 0.281633 ms | 308.068 |
| `O-ET2X` | 2.966339 ms | 0.406816 ms | 305.250 |
| `O-ET2X-R` | 3.014272 ms | 0.441845 ms | 302.602 |

현재 edge-selective adaptation은 대응 Standard T2X보다 빠르지 않았다.
`O-ET2X`는 `O-T2X` 대비 SMAA +72.33%, WholeFrame +6.73%였고,
`O-ET2X-R`은 `O-T2X-R` 대비 SMAA +56.89%, WholeFrame +6.29%였다.
성능과 분리한 readback On 4,800프레임 특성화에서 평균 base edge 222,123.076개,
candidate/process 150,908.285개, candidate/base 67.939%였다. 이는 전체 픽셀의
각각 11.376%, 7.728%다. Intel 문서의 약 50% 기본 목표보다 높은 장면 결과이며,
후보 감소만으로 성능 향상을 주장하지 않는다는 연구 원칙에 부합하게 그대로 기록한다.
Original 네 mode의 한 Bistro 경로 품질 기준선은 이후 완료됐다. Adaptive 4개를 포함한
정식 8-case visible-window 성능, Bistro 연속 품질과 전용 temporal stress 품질 측정도
이후 완료됐다. SMAA 1X control, Original camera-reprojection 경로의 구성요소별
ablation, optical-flow 정렬 보조 분석과 supersample spatial-reference proxy 보강도
이후 완료됐다.

Original 네 mode 품질 분석기는 16프레임 축소 capture에서 각 mode의 연속 index·해상도·
고유 hash를 검증하고 CSV/JSON/Markdown/contact sheet/대표 PNG/GIF 생성을 완료했다.
축소 수치는 도구 검증용이며 품질 연구 결과로 사용하지 않는다. 다음 실제 품질 capture는
mode당 60프레임 warm-up과 300프레임 저장으로 실행한다.

실제 Original 4-case 품질 capture도 mode당 60프레임 warm-up과 300프레임 저장으로
완료했다. 네 mode 모두 00000~00299 연속·고유 PNG이고, 모든 대응 pair의 ±2프레임
정렬 검사에서 같은 index가 300/300 최적이었다. `O-ET2X` vs `O-T2X`는 temporal
MAE +22.675%, 2차 차분 +47.013%, edge strength +8.987%였고, `O-ET2X-R` vs
`O-T2X-R`은 각각 +3.208%, +4.028%, +5.350%였다. edge-selective의 선명도
대용값이 높지만 화면 공간 temporal 변화도 작아지지 않았으므로 품질 개선으로 단정하지
않는다. sampled sequence sheet에서 심각한 화면 전체 떨림·깨짐은 보이지 않았으나,
한 Bistro camera path에는 독립 object motion/disocclusion ground truth가 없으므로
ghosting 감소 결론은 보류한다.

Adaptive 통합 후 `-smaaTemporalLifecycleTest`를 다시 실행해 8개 mode와
camera-cut/scene/resize 전환을 모두 검증했다. 결과는 reset 25회, completed frame
93개, seed 13개, resolve 80개, reprojection 26개, failure 0으로 PASS했다.
`-smaaEightCasePerformanceSmoke 1 30 32 1`은 각 mode의 expected timing 32개와
edge-selective 네 mode의 candidate 표본 32개를 수집해 PASS했다.
`-smaaEightCaseCapture 1 3 3`은 8개 디렉터리에 연속·고유 PNG 3개씩을 생성했고,
8-case 분석기와 기존 4-case 분석기 양쪽 smoke가 통과했다. 이 축소 실행은 구현·도구
검증일 뿐 최종 8-case 품질·성능 결과가 아니다.

전체 길이의 첫 8-case 성능 실행은 mode당 300 warm-up, 4,800 measurement,
3 repeats로 내부 validation PASS와 mode별 14,400 timing 표본을 확보했다. 다만
애플리케이션 창을 운영체제 수준에서 숨겨 실행했으므로
`analyze_eight_case_performance.py --window-state hidden --classification engineering`
으로 분류한다. 이 결과는 계측과 분석 경로 검증 및 예비 GPU pass 비교에만 사용하고,
논문용 FPS·WholeFrame 결과는 visible-window formal 실행으로 재현한 뒤 확정한다.

이후 운영체제 수준에서 CMAA2 창이 보이는 상태로 같은 8-case benchmark를 재실행했다.
앱 내부 ImGui UI만 측정 중 숨겼고 렌더 창은 visible/windowed 상태를 유지했다.
`Projects/CMAA2/AutoBench/20260730_021435`에서 mode별 14,400 timing 표본과 내부
validation PASS를 확인했으며 `--window-state visible --classification formal` 분석도
PASS했다. 대응 case 평균 SMAA 변화는 Adaptive -10.06%, Edge-selective +68.23%,
camera reprojection On +14.07%였다. 숨김 engineering 실행의 -10.66%, +76.93%,
+14.39%와 방향이 모두 재현됐다. 현재 Edge-selective adaptation은 이 장면에서
Standard T2X보다 느리며, 품질 이득 검증 전에는 종합적인 성공/실패 결론을 내리지 않는다.

같은 Bistro path의 정식 8-case 품질 capture도 완료했다.
`Projects/CMAA2/AutoBench/20260730_023009`에 mode별 60-frame warm-up 뒤
300 PNG, 총 2,400 PNG를 저장했고 8개 mode 모두 연속 index 00000~00299와 고유
hash 300개를 통과했다. 12개 대응 pair의 ±2 frame 정렬에서 모두 300/300 same-index가
최적이었다. 이전 Original 기준선 `20260730_010741`과 새 capture의 Original
1,200 PNG를 SHA-256으로 대조해 mismatch 0을 확인했다.

Adaptive와 Original 대응 case의 same-frame RGB MAE는 0.008164~0.008875,
최대 채널 차이 >8 픽셀 비율은 0.008907~0.009663%로 매우 작았고 temporal MAE 변화도
-0.010~+0.041%였다. 이 Bistro 경로에서는 Adaptive 통합이 대응 Original temporal
출력을 사실상 유지했다. 반면 Edge-selective document profile은 대응 Standard보다
edge strength가 5.309~8.987% 높았지만 temporal MAE와 2차 차분이 감소하지 않았다.
화면 전체 깨짐이나 심한 떨림 회귀는 보이지 않았으나, object-motion ghosting과
disocclusion은 이 경로로 결론내리지 않는다. Edge-selective 비교에는 candidate 선택뿐
아니라 no deliberate jitter, Catmull-Rom, variance clipping, history weight 0.8이
함께 포함되므로 candidate selection 단독 효과라고 표현하지 않는다.

Intel 공개 문서 기반 core의 기능 체크리스트는 모두 통과했다. 따라서
`TSCMAA-inspired SMAA core 기능 검증 완료`라고 표시할 수 있다. 이는 공식 Intel
sample 포팅 인증이나 8-case 연구 완료를 뜻하지 않는다. 전체 8개 mode의 본
품질·성능 반복 측정을 진행할 수 있는 내부 계측·캡처·분석 경로까지 검증됐다.

독립 object motion과 얇은 선/disocclusion을 위한 별도 절차적 장면
`SMAA Temporal Stress Test`를 추가했다. 기존 Bistro/Minecraft asset은 수정하지 않는다.
다음 세 시나리오를 `-smaaEightCaseStressCapture`로 전체 8개 mode에서 동일한 fixed
60 Hz timeline으로 캡처한다.

- `thin-lines`: 물체는 고정하고 카메라만 수평 이동
- `object-motion`: 카메라는 고정하고 어두운 occluder와 회전 날개만 이동
- `combined`: 카메라와 두 물체가 동시에 이동

명령 형식은
`-smaaEightCaseStressCapture "<thin-lines|object-motion|combined> <captureFrames> <warmupFrames>"`
이다. `-R` mode도 camera-motion reprojection만 사용하며 object motion vector는
연결되지 않는다. 2026-07-30에 각 시나리오를 3 warm-up + 3 capture frame으로
축소 검증했고, 매 실행에서 8개 디렉터리와 mode별 연속·고유 PNG 3개, 기존
8-case 분석기의 보고서/비교 이미지 생성을 확인했다. 이 축소 결과는 도구 smoke일 뿐
최종 품질 결과가 아니다.

이후 세 시나리오를 mode별 60 warm-up + 240 capture frame으로 정식 실행했다.
각 실행은 8개 mode × 240장, 총 1,920 PNG이며 모든 mode가 00000~00239 연속 index와
동일 1920×1017 해상도를 통과했다.

- `Projects/CMAA2/AutoBench/20260730_030857`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_031939`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_032435`: `combined`

전용 ROI 분석에서 camera-only `thin-lines`의 Edge-selective no-reprojection은
대응 Standard보다 2차 시간 차분이 Original +29.611%, Adaptive +36.673%였고,
reprojection On에서는 Original -7.586%, Adaptive -6.741%였다. object-motion rotor의
Edge-selective no-reprojection은 인접 frame MAE가 Original +26.762%, Adaptive
+26.931%로 더 컸다. 반면 occluder trailing-halo 휴리스틱은 Standard 대비
Edge-selective에서 darkness가 Original 39.16%, Adaptive 40.71%, 연속 폭이 Original
58.39%, Adaptive 70.99% 감소했다. combined에서도 대응 Edge-selective의 휴리스틱
감소 방향은 재현됐다.

연속 frame sheet에서는 Standard T2X의 회전 날개에 이전 위치가 반투명하게 겹치는
이중 잔상이 보였고 Edge-selective에서 크게 줄었다. 다만 Edge-selective의 temporal
변화 지표가 여러 ROI에서 증가했으므로 이는 현재 `ghosting 감소 가능성 ↔ temporal
variation/flicker 증가 가능성`의 trade-off 근거다. 이 단계에는 SMAA 1X,
supersample reference와 optical-flow 보정이 없었으므로 단독 최종 품질 우위나 절대
ghosting 점수로 표현하지 않는다. 이 보조 reference들은 후속 실험에서 별도로
보강했다. 품질 PNG capture는 hidden-window로 실행했지만 저장된 render target
검증용이며 FPS 결과로 사용하지 않는다.

SMAA 1X 품질 control도 이후 완료했다. `O-1X`는 기존 원본 SMAA 1X를 그대로 사용하고,
`A-1X`는 Adaptive 공간 탐색만 사용하며 두 control 모두 projection jitter, temporal
history와 reprojection을 사용하지 않는다. 최종 8-case를 늘리는 mode가 아니라 temporal
supersampling 효과가 유지되는지 확인하는 기준군이다.

- `Projects/CMAA2/AutoBench/20260730_042245`: `thin-lines` 1X control
- `Projects/CMAA2/AutoBench/20260730_042343`: `object-motion` 1X control
- `Projects/CMAA2/AutoBench/20260730_042414`: `combined` 1X control

각 실행은 `O-1X`/`A-1X` 각각 60 warm-up + 240 capture frame이고, 00000~00239
연속 index와 1920×1017 해상도를 통과했다. 별도 순차 재실행과 최초 실행의 대응 PNG
1,440장을 SHA-256으로 비교해 mismatch 0도 확인했다.

`thin-lines`에서 Standard T2X no-reprojection은 1X 대비 2차 시간 차분을 Original
28.535%, Adaptive 35.228% 줄였다. ET2X no-reprojection의 감소는 각각 7.374%,
11.474%였고 ET2X-R은 24.595%, 26.690%였다. 즉 camera motion에서는 현재 ET2X가
일부 temporal 안정화 효과를 유지하며 camera reprojection이 이를 보강했다.

반면 고정 camera의 회전 rotor에서 Standard T2X는 1X 대비 인접 frame MAE를 Original
21.417%, Adaptive 21.361% 줄였지만 눈에 보이는 이중 잔상을 만들었다. ET2X의 감소는
각각 0.386%, 0.182%뿐이었고 1X와 same-frame MAE도 0.052451, 0.034190에 불과했다.
Occluder에서도 ET2X와 1X의 same-frame MAE는 Original 0.084904, Adaptive
0.074016이었다. 현재 ET2X는 object motion 고스팅을 줄이지만 움직이는 물체에서는
출력과 시간 거동이 1X에 매우 가까워 temporal supersampling 효과를 상당 부분
상실했을 가능성이 있다.

이 결과는 Edge-selective의 종합적 성공이 아니라 다음 ablation의 근거다. Candidate
선택, no-jitter, Catmull-Rom, variance clipping과 history weight 0.8 중 어떤 요소가
object history를 사실상 제거하는지 분리하기 전에는 ET2X 품질 우위를 주장하지 않는다.

Original camera-reprojection 경로에서 다음 누적 구성요소 ablation도 완료했다.

| 순서 | 진단 ID | 직전 단계에서 추가되는 요소 |
|---|---|---|
| 0 | `O-T2X-R` | Standard full-screen 기준선 |
| 1 | `ABL-CandidateOnly-R` | Intel-family edge candidate coverage |
| 2 | `ABL-Candidate+Catmull-R` | Catmull-Rom 5-tap |
| 3 | `ABL-Candidate+Catmull+Clip-R` | YCoCg variance clipping |
| 4 | `ABL-Candidate+Catmull+Clip+W0.8-R` | history weight 0.8 |
| 5 | `O-ET2X-R-Document` | deliberate projection jitter 비활성화 |

Candidate-only 단계는 `O-T2X-R`과 Original spatial, camera reprojection, T2X
jitter/subsample, bilinear sampler, clipping Off, history weight 0.5를 동일하게
유지하고 full-screen resolve를 candidate compact/indirect resolve로 바꾼 통제
비교다. Edge-selective T2X mode에서 jitter가 켜진 경우에도 `MODE_SMAA_T2X`와 올바른
subsample index를 사용하도록 수정했고, resize reset 전에 이전 viewport jitter가
선택되지 않도록 lifecycle 순서도 교정했다. 확장된 lifecycle 자동 검증은 reset 34회,
completed frame 104개, seed 17개, resolve 87개, reprojection 39개, failure 0으로
PASS했다.

정식 품질 capture는 다음 세 경로에서 mode별 60-frame warm-up과 240 PNG로 완료했다.

- `Projects/CMAA2/AutoBench/20260730_125659`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_125853`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_130049`: `combined`

Candidate-only는 Standard `O-T2X-R`보다 `thin-lines` 2차 시간 차분이 52.761%,
object-motion occluder가 209.269%, rotor가 140.795% 증가했다. 반면 occluder trail
대용값은 darkness `0.942569 → 0.682631`, width `1.462 → 0.579 px`로 감소했다.
따라서 candidate coverage 단독은 Standard의 object trail을 줄이지만, T2X jitter가
남은 비후보가 temporal resolve를 받지 못해 강한 temporal variation을 만든다.

인접 단계에서 Catmull-Rom은 세 stress ROI의 temporal 지표를 거의 바꾸지 않았다.
Clipping은 object-motion trail을 추가로 줄였지만 temporal variation을 조금
증가시켰다. History weight 0.8은 variation을 일부 줄였고, no-jitter 단계는
`thin-lines` 2차 차분 33.320%, occluder 48.047%, rotor 49.383%를 직전 단계보다
줄여 현재 selective 구조에서 가장 큰 안정화 요소였다. 이는 current document profile이
object motion에서 1X에 가까워진 원인을 candidate selection 하나로 돌릴 수 없고,
candidate coverage와 deliberate jitter의 부조화가 핵심이라는 통제 근거다.

정식 visible-window 성능 ablation은
`Projects/CMAA2/AutoBench/20260730_130441`에서 300-frame warm-up,
4,800-frame measurement, 3 repeats, candidate readback Off로 완료했다. 내부 validation은
PASS했고 mode별 14,400 timing 표본을 확보했다. Candidate-only는 Standard보다 SMAA
GPU 평균이 `0.283675 → 0.442705 ms`(+56.061%), WholeFrame이
`3.035608 → 3.099416 ms`(+2.102%)였다. Catmull-Rom의 SMAA 추가 비용은
+0.708%, clipping은 +0.885%, weight와 no-jitter는 각각 +0.058%, +0.091%였다.
따라서 현재 성능 병목은 history sample 세부식보다 candidate 준비·compact·indirect
실행 구조의 추가 비용이며, edge-selective는 Standard보다 빠르지 않다.

이 ablation은 최종 8-case mode를 늘리지 않는 원인 분석용 진단 경로다. 이 단계의
품질 지표만으로 최종 품질 우위를 주장하지 않으며, 이후 optical-flow와 supersample
spatial-reference proxy로 보강했다. 상세 결과는
`Docs/SMAA-Temporal-Component-Ablation-Results-ko.md`를 기준으로 한다.

이후 Farneback dense optical flow 기반 motion-compensated 보조 분석도 완료했다.
OpenCV의 `calcOpticalFlowFarneback`으로 spatial-only 1X control의 current→previous
backward flow를 계산하고, 같은 flow로 대응 temporal mode의 previous frame을
`remap`했다. Forward/backward consistency error가 1.0px를 넘거나 화면 밖인 픽셀은
제외했다. 알려진 `(3,-2)px` 합성 이동 self-test는 backward flow vector error
0.000108px, 정렬 MAE 99.877% 감소로 PASS했다.

Original component ablation의 세 정식 capture에 적용한 결과 모든 ROI에서 valid
ratio 78.166~92.763%, O-1X 정렬 MAE 감소 29.474~43.080%로 보조 검증을 통과했다.
Motion 보정 뒤에도 Candidate-only는 Standard보다 aligned residual이 `thin-lines`
+32.304%, object occluder +310.764%, rotor +49.881% 높았다. Object-motion의
forward/backward threshold를 0.5/1.0/2.0px로 바꿔도 Candidate-only 증가는 occluder
+273.06~363.67%, rotor +47.48~52.50%로 유지됐다. 따라서 candidate+jitter 단계의
큰 변화는 장면 motion이 섞인 기존 지표만의 현상이 아니다.

최종 8-case에도 대응 1X flow를 적용했다. 정식 경로는 다음과 같다.

- `Projects/CMAA2/AutoBench/20260730_042245/EightCaseOpticalFlowAnalysis`:
  `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_042343/EightCaseOpticalFlowAnalysis`:
  `object-motion`
- `Projects/CMAA2/AutoBench/20260730_042414/EightCaseOpticalFlowAnalysis`:
  `combined`

Camera-motion `thin-lines`에서 Edge-selective는 대응 Standard보다 aligned residual을
Original Off/On -12.103/-11.984%, Adaptive Off/On -14.055/-9.365% 줄였고,
camera reprojection On도 각 temporal 방식에서 -4.561~-9.500% 방향으로 줄였다.
Combined의 thin-line/occluder도 Edge-selective -8.692~-12.196%, reprojection
-2.808~-7.242%로 같은 방향이었다.

반면 고정-camera rotor에서 Standard는 대응 1X보다 aligned residual이 약
16.25~16.52% 낮았지만 기존 sequence에서 이중 잔상이 보였다. Edge-selective는
1X 대비 -0.090~+0.043%로 사실상 1X와 같고 Standard보다 19.29~19.84% 높았다.
이는 Standard의 낮은 residual이 temporal smoothing/ghost blur를 포함할 수 있고,
Edge-selective의 ghost 감소가 temporal supersampling 상실과 함께 일어났다는 기존
해석을 강화한다.

Optical-flow residual도 ground truth는 아니다. Forward/backward 불일치 영역을
제외하므로 disocclusion ghost를 완전히 재지 않고, 작은 residual은 blur로도 발생할 수
있다. 따라서 trailing-halo, 1X same-frame 비교와 sequence sheet를 함께 사용하며
절대 품질 순위로 표현하지 않는다. 상세 결과는
`Docs/SMAA-Optical-Flow-Temporal-Results-ko.md`를 기준으로 한다.

Candidate-only + 전역 SMAA T2X jitter의 높은 temporal variation 원인도 후속
ablation으로 분리했다. Intel-family와 AllBase 후보를 제외한 temporal 설정을 모두
동일하게 유지한 정식 3-scenario capture에서 AllBase의 flow-aligned residual 변화는
모든 ROI에서 `0.000%~-0.124%`뿐이었다. 따라서 Intel non-dominant 제거가 주원인이라는
가설은 지지되지 않았다.

반면 Intel-family 후보, camera reprojection, bilinear, clipping Off와 weight 0.5를
유지하고 deliberate projection jitter만 끈 ablation은 Jitter On 대비 residual을
thin-lines 40.522%, object-motion occluder 75.676%, rotor 20.106%, combined ROI
11.803~35.609% 줄였다. 이는 화면 전체 jitter와 후보 한정 resolve의 범위 불일치가
주원인이라는 해석을 강하게 지지한다. 다만 no-jitter 결과는 object-motion rotor에서
O-1X 대비 residual이 +0.290%에 불과해 temporal supersampling 효과도 상당 부분
잃었을 가능성이 있다. 따라서 global no-jitter를 최종 개선 성공으로 주장하지 않는다.
새 diagnostic을 포함한 lifecycle 검증은 reset 35회, seed 18회, resolve 89회,
reprojection 41회, failure 0으로 PASS했다.
상세 결과는 `Docs/SMAA-Candidate-Jitter-Stabilization-Results-ko.md`를 기준으로 한다.

같은 세 stress timeline의 supersample spatial-reference proxy도 후속 측정했다.
Reference는 선형 해상도 2배, 한 출력 프레임 안의 3×3 subpixel grid, 각 render
8×MSAA이며 temporal history를 사용하지 않는다. Path-traced 또는 temporal ground
truth가 아니고, 현재 프레임 형상을 비교하기 위한 고품질 spatial proxy다.

- `Projects/CMAA2/AutoBench/20260730_152152`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_152246`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_152342`: `combined`

각 시나리오는 reference 60-frame warm-up 뒤 240 PNG를 저장했다. Object-motion
rotor의 reference RGB MAE는 `O-1X` 0.500726, `O-T2X-R` 2.248942,
candidate jitter 0.691534, candidate no-jitter 0.551653이었다. 즉 Standard는
O-1X보다 349.136% 멀고 difference sheet에서 이전 날개 위치의 이중 잔상이
확인됐다. Candidate jitter는 모든 정식 ROI에서 O-1X보다 MAE가 35.777~49.024%
높았고, candidate no-jitter는 -4.993~+10.171%로 O-1X에 가까웠다.

이는 Standard의 낮은 temporal residual이 올바른 안정화뿐 아니라 ghost smoothing도
포함한다는 해석과, global no-jitter가 범위 불일치를 줄이는 대신 temporal
supersampling을 대부분 잃는다는 해석을 함께 지지한다. 따라서 no-jitter를 최종
성공으로 확정하지 않는다. 상세 결과는
`Docs/SMAA-Supersample-Reference-Results-ko.md`를 기준으로 한다.

후보에는 SMAA T2X jitter와 temporal resolve를 유지하고 비후보에는 screen-space
de-jitter spatial base를 제공하는 `ABL-Candidate-DeJitter-R`도 별도 diagnostic으로
구현했다. Bilinear history, clipping Off, weight 0.5와 Intel-family 후보를 유지해
`ABL-Candidate-Jitter-R`과 비후보 base만 다르게 비교했다. Release x64 build와
temporal lifecycle(reset 36, seed 19, resolve 92, reprojection 44, failure 0)을
통과했다.

3개 stress 시나리오의 mode별 60 warm-up + 240-frame 정식 품질 capture에서 DeJitter는
Candidate Jitter 대비 flow-aligned residual을 4.809~15.254%, supersample
spatial-reference MAE를 7.956~15.908% 줄였다. 그러나 모든 ROI에서 Candidate
NoJitter보다 reference MAE가 8.831~29.242% 높고 O-1X보다도 16.063~35.011%
높았으며, bilinear inverse-jitter의 경계 연화가 관측됐다. 따라서 부분 개선은
확인됐지만 최종 해법으로 채택하지 않는다. 이 diagnostic은 최종 8-case를 변경하지
않으며 Intel 공식 TSCMAA로 표현하지 않는다. 품질상 채택 근거가 없어 full-screen
de-jitter pass의 정식 성능 본 측정은 생략했다. 상세 결과는
`Docs/SMAA-Hybrid-Resolve-Ablation-Results-ko.md`를 기준으로 한다.

`-smaaOriginalFourCapture 1 1 6`의 첫 mode인 `O-T2X`는 같은 실행 조건에서도
`9F5B...`와 `74E9...` 두 PNG hash가 관측됐다. `O-T2X-R`, `O-ET2X`, `O-ET2X-R`은
반복 일치했으며 이 현상은 sampler override와 무관하다. 시작 프레임/history warm-up
비결정성을 해결하기 전에는 `O-T2X` 단일 프레임 hash를 최종 deterministic 증거로
사용하지 않는다.

교수 피드백에 따라 다음 우선순위는 새 장면을 추가하는 대신 기존 Bistro와 Minecraft에서
급격한 camera motion을 통제하고, 공개 논문 기반 고스팅 평가를 적용하는 것이다.
Bistro는 연구상 저대비 동적 장면, Minecraft Lost Empire는 고대비 동적 장면으로
분류하되 luma/local contrast와 edge/candidate 통계로 이 분류를 수치 보강한다.
평가 프로토콜은 `Docs/SMAA-Camera-Motion-Ghosting-Evaluation-Protocol-ko.md`를
기준으로 한다.

IntelLabs/CGVQM 공식 commit `8302ff45`의 CUDA smoke를 RTX 3060 Ti에서 통과했다.
공식 Dock pair는 CGVQM-2 `73.62/100`과 error map을 생성했다. 기존 thin-lines
`O-T2X-R`/supersample reference의 30-frame integration smoke도 두 FFV1 입력의
RGB round-trip mismatch 0, CGVQM-2 `99.4658126831`로 완료했다. 독립 재실행의
score·error-map 통계·per-frame CSV SHA-256이 일치했다. 이는 도구 engineering
validation일 뿐 새 camera-motion 품질 결과가 아니다. Windows Python 3.12에서는
공식 `av==14.4.0` wheel이 없어 같은 API의 `av==15.1.0` binary를 사용하며, 모델,
weight, 전처리와 pooling 코드는 수정하지 않는다.

Bistro/Minecraft에 `yaw-slow-360`, `yaw-fast-360`, `yaw-extreme-360`,
`strafe-fast`, `yaw-strafe-fast` 결정적 camera profile을 연결했다. 각 profile은 fixed
60 Hz에서 60-frame pre-still, profile별 motion, 60-frame post-still로 구성하고 완전한
360도 뒤 pose는 시작 pose와 정확히 같게 복원한다. 다음 두 명령을 사용한다.

- `-smaaCameraMotionOriginalFiveCapture`: `O-1X`, `O-T2X`, `O-T2X-R`,
  `O-ET2X`, `O-ET2X-R` 5-way PNG capture
- `-smaaCameraMotionReferenceCapture`: 같은 pose의 `SS-Reference` 별도 capture
- `-smaaCameraMotionEightCaseCapture`: 최종 8-case + `O-1X`/`A-1X` control의
  10-way PNG capture

두 명령은 `<scene> <profile> [firstProfileFrame] [captureFrames] [warmupFrames]`를
받는다. 부분 frame 범위는 engineering smoke, profile 전체는 complete quality capture로
provenance에 기록한다. PNG 이름은 기존 CGVQM adapter와 호환되는 `_frame_<index>`로
끝난다. Bistro와 Minecraft yaw-fast 정지→회전 smoke, 나머지 4개 profile의 Bistro
분기 smoke, Release x64 build와 temporal lifecycle(reset 36, seed 19, resolve 94,
reprojection 44, failure 0)을 통과했다. Bistro yaw-fast 5-way 25 PNG의 독립 재실행
SHA-256 mismatch는 0이었다. 같은 profile의 시작 frame 0과 360도 회전 후 마지막
frame 179도 5개 mode 모두 대응 PNG가 byte-identical해 pose 복원을 확인했다.

동일 Bistro pose의 supersample reference 재실행은 1920×1017 중 101 pixel에서 최대
2/255 차이, 전체 channel MAE `0.0000198023`의 극소수 GPU 누적 변동이 있었다.
따라서 reference는 byte-identical만을 acceptance로 삼지 않고 이 허용오차와 지표 반복
안정성을 함께 기록한다. 수정된 camera-motion PNG 2-frame pair는 기존 adapter의 연속
index·해상도 검증과 FFV1 RGB round-trip mismatch 0 및 CUDA CGVQM-2 실행을 통과했다.
모든 수치는 engineering validation이며 정식 camera-motion 품질 결론이 아니다.

이후 Bistro와 Minecraft `yaw-fast-360`의 전체 길이 Original 5-way + SS-Reference를
완료했다. 장면별 5 mode × 180 PNG와 reference 180 PNG의 연속 index, 같은 pose,
FFV1 RGB round-trip mismatch 0을 확인했다. CGVQM-2는 다음과 같다.

| Mode | Bistro | Minecraft |
|---|---:|---:|
| `O-1X` | 94.3980 | 97.8179 |
| `O-T2X` | 71.4263 | 82.9486 |
| `O-T2X-R` | 94.2841 | 97.4389 |
| `O-ET2X` | 93.6266 | 97.3908 |
| `O-ET2X-R` | 94.4143 | 97.7409 |

두 장면 모두 `O-T2X`의 회전 중 큰 이중 잔상과 reprojection을 통한 회복이 수치·대표
시트에서 같은 방향으로 확인됐다. `O-ET2X-R`은 눈에 띄는 pure-yaw 고스팅이 없었지만
O-1X와 시간 변화가 거의 같아 temporal 이득 유지는 보류한다. post-stop recovery는
0~2 frame으로 장시간 trail보다 회전 중 오정렬이 핵심이었다. 이는 final 8-case가 아닌
전체 길이 평가 경로 engineering 결과다. 상세 결과는
`Docs/SMAA-Camera-Motion-Ghosting-Results-ko.md`를 기준으로 한다.

전체 평가 뒤 `-smaaCameraMotionEightCaseCapture`를 추가했다. 기존 Original 5-way
출력을 보존하면서 `A-1X`와 Adaptive temporal 4개를 더해 총 10개 sequence를 저장한다.
Bistro 2-frame 축소 실행에서 10개 폴더가 각각 2개 연속 PNG를 생성했고 Release x64
build와 lifecycle(reset 36, seed 19, resolve 93, reprojection 44, failure 0)을
통과했다.

이후 Bistro `Projects/CMAA2/AutoBench/20260812_201017`과 Minecraft
`Projects/CMAA2/AutoBench/20260812_205656`에서 `yaw-fast-360` 최종 8-case +
`O/A-1X` formal capture를 완료했다. 장면별 10 mode × 180 PNG와 10개 CGVQM 결과가
모두 연속 frame, `classification=formal`, test/reference 180 frame, FFV1 RGB
round-trip mismatch 0을 통과했다. `O/A-T2X` no-reprojection은 회전 중 큰 history
오정렬을 보였고 camera reprojection으로 크게 회복됐다. `O/A-ET2X-R`은 눈에 띄는
pure-yaw 고스팅이 없었지만 대응 1X와 시간 거동이 매우 가까워 temporal 이득 유지 여부는
보류한다. Adaptive와 Original 대응 결과 차이는 작아 이 profile의 temporal 결론을
바꾸지 않았다. 상세 결과는
`Docs/SMAA-Camera-Motion-Ghosting-Results-ko.md`를 기준으로 한다.

PNG 동기 저장 때문에 품질 capture 중 보이는 창이 9~10 FPS로 느려지는 현상을 camera
경로 문제와 분리하기 위해 `-smaaCameraMotionPreview`를 추가했다. PNG를 저장하지 않고
분석 camera step을 벽시계 60 Hz로 재생하며 semantic mode와 반복 횟수를 선택한다.
Bistro `O-ET2X-R`에서 `yaw-slow-360`은 frame-start 평균 16.669 ms,
`yaw-fast-360` 2회 반복은 16.669 ms였다. 기존 formal O-1X 회전 frame 60~119도 양 장면 모두
60개 고유 hash와 인접 중복 0이었다. 따라서 기존 fast profile은 frame 누락이 아니라
60 frame 동안 360°, 즉 6°/frame의 의도적인 고속 stress다. 시각적으로 기본 demo에
가까운 회전 확인에는 240-frame motion의 `yaw-slow-360`을 사용한다.

기존 PNG에서는 `Tools/SMAA/create_camera_motion_playback.py`로 단일 mode와 3-way
constant 60 FPS H.264/MP4를 생성했다. Bistro/Minecraft 모두 180 decoded frame,
average rate 60, constant 1/60초 PTS와 3.000초 duration을 통과했다. MP4는 발표용이며
정식 지표에는 원본 PNG/RGB-preserving FFV1만 사용한다. Preview 추가 후 lifecycle은
reset 36, frame 114, seed 19, resolve 95, reprojection 45, failure 0으로 PASS했다.

2026-08-13에 Bistro/Minecraft의 `strafe-fast`와 `yaw-strafe-fast` 최종 8-case +
O/A-1X formal 측정을 완료했다. 각 장면·profile은 10 mode × 240 PNG와 같은 pose의
SS-Reference 240 PNG를 사용했으며 40개 CGVQM 결과의 최종 FFV1 RGB round-trip
mismatch는 0이었다. 유효 capture root는 각각 `20260813_013331`,
`20260813_023150`, `20260813_032105`, `20260813_041648`이고 reference root는
`20260813_013845`, `20260813_023846`, `20260813_032603`, `20260813_042324`다.
두 strafe-only 조건에서는 대응 `T2X-R`이 `ET2X-R`보다 CGVQM-2가 높았지만, 두
yaw+strafe 조건에서는 `ET2X-R`이 높고 motion 구간 reference error도 낮았다.
Edge-selective 이득은 camera-motion 유형에 의존하며, ET2X-R이 1X에 매우 가깝다는
temporal 이득 손실 가능성을 함께 기록한다. Adaptive/Original 대응 CGVQM-2 차이의
최대 절대값은 0.0787로 temporal 결론을 바꾸지 않았다. 상세 결과는
`Docs/SMAA-Camera-Motion-Ghosting-Results-ko.md`를 기준으로 한다.

첫 180-frame CGVQM 실행은 per-frame CSV 생성 뒤 error-map visualization이 전체
context/error/heatmap을 동시에 메모리에 적재하면서 native Python access violation으로
종료됐다. error-map을 frame별 colorize/FFV1 encode하도록 변경했고, 이후 Bistro와
Minecraft 전체 10개 mode 실행에서 재발하지 않았다. 공식 CGVQM 본체는 전체 test/ref
영상을 float tensor로 읽으므로 mode는 순차 실행하며 병렬 실행하지 않는다.

## 5. 기존 측정의 정확한 범위

`Projects/CMAA2/AutoBench/20260729_002704` 데이터는 다음 두 복합 구현의 1차 품질 비교다.

- `O-T2X-R`에 해당하는 Reprojected SMAA T2X
- 현재 `O-ET2X-R` 복합 prototype

이 데이터는 실제 캡처 데이터지만 다음 용도로만 사용한다.

- 두 구현의 현재 화면 차이와 시간적 거동 확인
- 캡처 도구와 프레임 정렬 검증

다음 주장에는 사용하지 않는다.

- 8개 case 전체 비교 결과
- edge 후보 선택만의 독립 효과
- TSCMAA 적용의 최종 품질 또는 성능 결론
- reprojection Off 방식과의 비교

## 6. 구현 순서

추가 본 측정을 진행하기 전에 다음 순서를 지킨다.

1. **완료:** AA mode를 Standard/Edge-selective와 Reprojection Off/On의 직교 조합으로 정리한다.
2. **완료:** 후보 정책 계측과 0/1/group/최대 경계 검증, bilinear/no-clipping
   selective resolve 골격 및 비후보/후보 픽셀 불변식 검증을 완료했다.
3. **완료:** 8개 mode의 history 초기화, ping-pong, jitter, subsample index와
   mode/scene/명시적 camera-cut/resize reset을 자동 검증했다. RTX 3060 Ti의 실제 GPU
   readback에서 정적 카메라 velocity 0과 +right 0.01 m 이동의 음수 X velocity 및
   history UV 방향도 검증했다. 이는 camera motion만 검증하며 object motion은 미지원이다.
4. **완료:** 후보 선택 외의 Catmull-Rom, variance clipping, history weight 변경을
   ablation toggle로 분리했다. Catmull-Rom 5-tap과 YCoCg variance clipping의 실제
   GPU shader/CPU reference 및 불변 조건 검증을 완료했다.
5. **완료:** Intel-family candidate의 두 장면 removal sweep, base 안정성, 단조성,
   candidate/process 일치를 검증하고 document adaptation 정책으로 승인했다.
6. **완료:** Intel document profile을 조립하고 lifecycle·capture 회귀 smoke를
   통과시켰다. 기존 controlled skeleton은 diagnostic override로 재현 가능하다.
7. **완료:** Original 네 mode의 SMAA total과 내부 pass별 GPU timing을 계측하고 PNG 없는
   120-frame 성능 smoke를 통과시켰다. 전체 frame GPU time과 counter readback overhead는
   본 측정 전에 별도로 계측한다.
8. **완료:** Original 4개에 대한 동일 Bistro 경로 품질·성능 기준선을 확보했다.
9. **완료:** Adaptive SMAA를 독립 공간 축으로 결합해 `A-*` 네 mode를 만들고,
   8-mode lifecycle, 축소 성능/capture/analysis smoke를 통과시켰다.
10. **완료:** 전체 8개를 visible-window 정식 조건으로 3회 반복 성능 측정하고
    세 독립 축의 성능 차이를 분석했다.
11. **완료:** 전체 8개 품질 sequence를 같은 Bistro 경로에서 캡처하고 정량·시각
    분석 및 Original deterministic regression 검증을 완료했다.
12. **완료:** 독립 object motion, 얇은 선과 disocclusion 전용 장면의 전체 8-case
    정식 capture와 전용 ROI 분석, SMAA 1X control을 완료했다.
13. **완료:** Original camera-reprojection 경로에서 candidate coverage,
    Catmull-Rom, variance clipping, history weight 0.8과 no-jitter를 인접 한 요소씩
    추가하는 품질·성능 ablation을 완료했다.
14. **완료:** Farneback optical-flow 정렬 보조 지표를 component ablation과 최종
    8-case에 적용하고 합성 이동 self-test, 유효 비율, threshold 민감도를 검증했다.
15. **완료:** Intel-family와 AllBase 후보 정책, projection jitter On/Off를 각각
    단일요소로 분리해 candidate-only variation의 주원인이 후보 제거가 아니라 전역
    jitter와 후보 한정 resolve의 범위 불일치임을 확인했다. Global no-jitter의
    O-1X 유사성도 기록해 안정화와 temporal 효과 손실을 구분했다.
16. **완료:** 2× linear resolution, 3×3 within-frame subpixel grid와 8×MSAA의
    supersample spatial-reference proxy를 같은 stress timeline에 연결하고,
    `O-1X`, `O-T2X-R`, candidate jitter On/Off를 3개 시나리오에서 240프레임씩
    비교했다. Standard의 object ghost와 global no-jitter의 O-1X 유사성을
    reference MAE/PSNR/SSIM 및 difference sheet로 보강했다.
17. **완료:** 후보에는 temporal sample diversity를 유지하면서 비후보에는
    screen-space de-jitter spatial base를 제공하는 hybrid를 ablation했다. Jitter
    candidate보다 부분 개선됐지만 NoJitter와 O-1X보다 일관되게 나쁘고 blur가 남아
    최종 방식으로 채택하지 않았다.
18. **완료:** CGVQM 기반 고스팅 평가 protocol과 PNG lossless adapter의 engineering
    validation을 완료했다. Bistro 저대비/Minecraft 고대비 장면의 독립적인
    `yaw-slow-360`, `yaw-fast-360`, `yaw-extreme-360`, `strafe-fast`,
    `yaw-strafe-fast` deterministic camera profile, Original 5-way capture와 동일 pose의
    supersample reference capture를 연결했다. 양 장면 `yaw-fast-360`의 최종 8-case +
    O/A-1X, reference, CGVQM/error-map/recovery formal 분석을 완료했다. PNG 저장 없는
    벽시계 60 Hz preview와 기존 PNG의 constant 60 FPS MP4도 검증해 캡처 중 낮은 표시
    FPS와 기록 timeline을 분리했다.
19. **완료:** `strafe-fast`, `yaw-strafe-fast`의 양 장면 최종 8-case + O/A-1X,
    supersample reference, CGVQM/recovery 분석을 완료했다. `yaw-extreme-360`은 더 큰
    pure-yaw UV stress가 필요할 때의 선택적 검증으로 남긴다.
20. **완료:** dilation에 앞서 실제 장면에서 현재 edge-selective 구현이 Standard
    T2X의 temporal 효과를 얼마나 유지하는지 직접 측정한다. 비교 matrix는 `O-1X`,
    `O-T2X-R`, `ABL-Candidate-Jitter-R`, `ABL-Candidate-NoJitter-R`,
    `O-ET2X-R-Document`다. final 출력과 동일 프레임의 `CurrentSpatial` debug 출력을
    별도 clean-process capture로 저장해 실제 화면에 나타난 history 기여 범위와 세기를
    측정하고, O-1X 공통 optical flow의 motion-aligned residual 및 기존 CGVQM/reference
    결과를 함께 해석한다. 이 기준선 뒤에만 current-frame edge 3×3/5×5/7×7 dilation과
    filtered downsample-upsample ablation의 필요 여부를 결정한다.

    정식 장면은 저대비 Bistro와 고대비 Minecraft를 기본으로 한다. 자체 절차적
    `thin-lines`/rotor/occluder 장면은 변수 통제·회귀용 engineering stress로만 유지하며
    논문용 실제 장면 근거로 사용하지 않는다.

    공개 외부 장면의 연구 분류도 다음과 같이 고정한다.
    2026-08-13에 UNC Power Plant 원본의 해시·21개 section 구조를 검증하고 외부
    `.smaapp` 캐시 변환/검증 로더를 추가했다. 17개 section 동일 preview에서 실제 배관·
    프레임 구조가 풍부하고 화면 포화가 덜한 `sec4`를 주 후보, 수직 반복선이 극단적인
    `sec10`을 보조 stress 후보로 선정했다. `powerplant`를 기존 60 Hz camera-motion
    preview와 Original 5-way capture에 연결했고 `sec4` 5 mode×3 frame smoke를
    통과했다. 상세 기준은 `Docs/SMAA-PowerPlant-ThinGeometry-Scene-ko.md`다. 현재
    Power Plant 경로는 texture·lighting·재질 표현이 불완전하므로 loader/scene-selection
    engineering 자료로만 보존하고 정식 품질·논문 장면에서는 제외한다.
    같은 날 실제 texture·식생 alpha edge·가구와 난간을 포함하는 San Miguel 2.1
    저폴리 장면도 검증된 외부 `.smaasm` cache로 연결했다. 5,617,451개 triangle,
    281개 material, 265개 diffuse texture와 97개 alpha-test material을 로드하고
    courtyard 고정 camera preview의 Release x64 렌더링·정상 종료·잔류 프로세스 0개를
    확인했다. `yaw-slow-360` Original 5-way의 mode별 1-frame engineering smoke도
    clean process에서 통과했다. 상세 기준은 `Docs/SMAA-SanMiguel-Textured-Scene-ko.md`다.
    San Miguel은 texture와 alpha-tested geometry가 있는 실제 장면 후보지만 현재 renderer가
    diffuse+alpha 중심으로 제한되어 있다. 따라서 동일 camera path의 정상 렌더링, 적절한
    thin/detail ROI와 reference 반복 안정성을 검증한 뒤에만 정식 보조 장면으로 승격한다.
    그 전 capture는 textured real-scene integration/engineering 결과이며 dilation 결과가 아니다.
    이후 dilation 없는 실제 장면 temporal-retention 5-way 선행 측정을 완료했다. `yaw-fast-360`
    회전 frame 60~119, mode별 warm-up/저장 60 frame에서 O-1X와의 same-frame 출력 거리를
    `O-T2X-R=100%`로 정규화하면 Candidate-Jitter는 Bistro 94.07%, Minecraft 91.48%,
    San Miguel 93.06%였으나 Candidate-NoJitter는 14.10%, 14.57%, 18.01%, document
    profile은 19.30%, 19.73%, 25.02%였다. SelectedCandidates mask 내부의
    `final-CurrentSpatial` 차이는 NoJitter/document에서도 남아 history 자체가 0은 아님을
    확인했다. 따라서 현재 전체 temporal 효과 감소의 큰 분기점은 candidate selection 단독보다
    deliberate projection jitter 제거이며, dilation이 이를 자동으로 복구한다고 가정하지
    않는다. 상세 프로토콜/결과는 `Docs/SMAA-Real-Scene-Temporal-Retention-Protocol-ko.md`와
    `Docs/SMAA-Real-Scene-Temporal-Retention-Results-ko.md`를 기준으로 한다.
    이어서 Bistro/Minecraft 새 60-frame `O-1X`와 기존 formal frame 60~119의 PNG
    SHA-256 mismatch 0/60으로 supersample reference pose 정렬을 검증했다. 동일 subset의
    CGVQM-2에서 Candidate-Jitter는 Standard보다 Bistro +0.9011점, Minecraft +0.3384점
    높았지만 O-1X보다 각각 2.6199점, 1.4435점 낮았다. 실제 asset ROI에서도
    Candidate-Jitter의 reference MAE가 O-1X와 no-jitter/document보다 컸다. 저장 mask의
    offline 3×3 dilation은 reference 구조 recall을 크게 높였으나 후보 화면 비율도 약
    2.7~3.2배 늘렸다. 이는 dilation 효과 자체가 아니라 다음 최소 3×3 구현의 근거다.
    상세 결과는 `Docs/SMAA-Candidate-Jitter-Real-Scene-Quality-Results-ko.md`를 기준으로 한다.
    Candidate-Jitter와 document profile에 직교하는 current-edge 3×3 toggle의 구현과
    실제 품질·성능 측정도 완료했다. GPU mask는 정확한 CPU 3×3 max-filter와 mismatch
    0 pixel이었고, 양 장면 독립 반복 capture의 4 mode×60 PNG도 mismatch 0이었다.
    후보는 전체 화면 기준 약 2.9~3.2배, 구조 recall과 화면에 나타난 history 영향은
    증가했다. Candidate-Jitter CGVQM-2는 Bistro +0.7735, Minecraft +0.2121이었으나
    document profile은 Bistro +0.0362, Minecraft -0.3994로 장면 의존적이었다.
    600 frame×3회 hidden engineering에서 3×3은 SMAA GPU 시간을 Candidate-Jitter
    +17.306%, document +18.639% 늘렸다. 따라서 기능적 coverage 확장은 확인했지만
    일관된 품질·성능 개선으로 채택하지 않으며 5×5/7×7은 보류한다. 상세 결과는
    `Docs/SMAA-Current-Edge-Dilation-3x3-Results-ko.md`를 기준으로 한다.
21. **완료:** 교수님이 제안한 nearest-neighbor가 아닌 filtered 1/4
    downsample-upsample 후보 확장을 별도 직교 ablation으로 구현하고 engineering gate를
    측정했다. Bistro/Minecraft yaw-fast pose에서 후보 증가는 약 1.57×로 3×3의
    2.83~3.12×보다 작았다. 그러나 단일 120-frame performance smoke에서 두 filtered
    pass 합은 0.0628~0.0631 ms로 3×3 0.0452~0.0455 ms보다 약 38.5~38.8% 높았고,
    SMAA total도 3×3보다 3.5~3.7% 높았다. 따라서 낮은 후보 증가율은 확인했지만 낮은
    mask 비용 gate는 통과하지 못해 정식 60-frame 품질·CGVQM 및 600×3 성능 측정으로
    확대하지 않는다. 상세 결과는
    `Docs/SMAA-Filtered-Quarter-Candidate-Expansion-Smoke-ko.md`를 기준으로 한다.
22. **완료:** CMAA2 기본 flythrough Catmull-Rom 경로 위에 quintic smootherstep 360°
    yaw를 더하는 결정적 결합 camera profile을 구현했다. 이동-only·회전-only control을
    함께 유지하고 기존 급회전 profile과 최종 8-case는 변경하지 않았다. Release x64,
    경로 불변 조건, Bistro/Minecraft visible 60 Hz preview, 장면 관통 없는 대표 프레임,
    장면별 480 PNG와 정확한 480-frame/60 FPS MP4를 검증했다. 이는 camera protocol
    engineering 완료이며 T2X/ET2X 품질 결론이 아니다. 상세 내용은
    `Docs/SMAA-Smooth-Flythrough-360-Protocol-ko.md`를 기준으로 한다.
23. **완료:** 새 부드러운 경로에서 `O-1X`, `O-T2X-R`, `O-ET2X-R`을
    Bistro/Minecraft별 rotation-only·translation-only·combined control로 비교했다.
    6 capture root의 mode별 480 frame과 O-1X 독립 실행 SHA-256 mismatch 0을 검증했다.
    `O-ET2X-R`의 O-1X 대비 화면 차이는 Standard의 23.95~28.56%였고 combined는 개별
    control 범위 안이었다. ET2X-R edge strength는 Standard보다 O-1X에 가까웠으며,
    회전 포함 후 최종 post-still plateau 안정화에는 6~8 frame이 필요했다. 대표 프레임의
    catastrophic reprojection ghosting은 보이지 않았지만 O-1X 유사성이 ghost 감소인지
    temporal sample 손실인지는 reference 없이 확정하지 않는다. 상세 결과는
    `Docs/SMAA-Smooth-Camera-Focused-Results-ko.md`를 기준으로 한다.
24. **완료:** 기존 `flythrough-smooth*`의 0.25 scale, 약 1.86 m 이동은 수학적으로
    정상이나 결합 yaw에서 제자리 회전처럼 보일 수 있어 완료 결과는 low-translation
    control로 보존했다. 별도 `flythrough-wide`와 `flythrough-wide-yaw-360`을 추가해
    위치 scale만 0.50으로 늘렸다. 두 장면 모두 480 frame 동안 약 3.72 m를 이동하며,
    이동-only/결합 위치 일치, 방향 회전 관계, 시작·종료 연속성, Release x64와 visible
    preview를 통과했다. 장면별 O-1X 480 PNG와 constant 60 FPS 8초 MP4도 검증했고
    대표 프레임에서 장면 관통 없이 translation이 시각적으로 구분됐다. 경로 세부 내용은
    `Docs/SMAA-Smooth-Flythrough-360-Protocol-ko.md`를 기준으로 한다.
25. **완료:** Bistro/Minecraft `flythrough-wide-yaw-360` 결합 profile의 동일 pose
    supersample spatial-reference를 확보하고 `O-1X`, `O-T2X-R`, `O-ET2X-R`에
    CGVQM-2/error-map을 적용했다. mode별 480-frame capture와 supersample reference,
    O-1X 독립 capture SHA-256 mismatch 0, CGVQM 입력 FFV1 round-trip mismatch 0을
    확인했다. Central motion에서 ET2X-R은 Standard보다 CGVQM-2가 Bistro +2.5474,
    Minecraft +1.5360 높고 reference RGB MAE가 각각 19.20%, 15.62% 낮았다. 그러나
    O-1X보다 CGVQM-2는 -0.3011/-0.0427, RGB MAE는 +4.77%/+0.03%여서 temporal
    supersampling 유지 우위는 확인하지 못했다. Transition clip에서는 Standard가 더
    높아 phase 의존성도 기록했다. 상세 결과는
    `Docs/SMAA-Wide-Camera-Reference-Results-ko.md`를 기준으로 한다.
26. **완료:** ARM SIGGRAPH 2015 Dual Filtering의 공개 5-tap downsample/8-tap upsample
    kernel을 current-edge candidate mask에 적용하는 별도 research adaptation을 구현했다.
    첫 reconstruction-only smoke가 raw 후보를 약 43~44%만 남기는 문제를 발견해
    `raw OR reconstruction>=0.25` union으로 수정했고, 이후 raw 후보 유실 없이
    Bistro/Minecraft에서 후보를 약 1.49~1.69배 확장했다. 60-frame CPU/GPU mask와
    supersample spatial-reference gate, lifecycle과 120-frame readback-Off 성능 smoke를
    통과했다. 그러나 ARM 4-pass mask는 약 0.133 ms로 3×3의 약 2.94~2.96배였고,
    Candidate-Jitter의 reference 이득은 작으며 document profile은 장면에 따라 악화됐다.
    후속 San Miguel 60-frame 측정에서는 전체 화면 reference MAE가 10.58~10.79%, 얇은
    의자 ROI가 9.44~13.10% 개선돼 current-edge expansion 가설 자체는 지지됐다. 그러나
    같은 ROI의 3×3이 9.62~14.46%로 약간 더 좋았고, San Miguel ARM mask는 0.133 ms로
    3×3보다 약 2.75배 비쌌다. 따라서 ARM 구현은 기능적 ablation으로 보존하되 최종
    개선안이나 600×3/CGVQM formal 대상으로 확대하지 않는다. 상세 결과는
    `Docs/SMAA-ARM-Dual-Filter-Candidate-Expansion-Smoke-ko.md`를 기준으로 한다.
27. **정정:** 2026-08-27 체계적 구현 감사에서 기존 `FilteredQuarter`가 복원 mask만
    threshold해 raw 후보를 지우는 결함을 발견했다. San Miguel 기존 mask에서 두 profile
    모두 60/60 frame에 유실이 있었고 최대 58,171개 raw 후보가 사라졌다. GPU path를
    `raw OR reconstruction>=0.25`로 수정하고 두 분석기에 raw 유실 hard-fail을 추가했다.
    수정 후 Bistro 3-frame GPU mask에서 유실 최대 0, GPU/CPU 최대 mismatch 0.012240%로
    PASS했다. 따라서 기존 문서·표의 FilteredQuarter 열과 이를 사용한 pair 결론은
    pre-fix 자료로 분류하며 재사용하지 않는다. None·3×3·ARM 자체 결과는 보존한다.
28. **완료:** 수정된 FilteredQuarter를 San Miguel `yaw-fast-360` 60-frame에서 다시
    측정했다. 두 profile 모두 raw 후보 유실 최대 0, GPU/CPU 최대 mismatch 0.010447%,
    독립 반복 360 PNG hash/pixel mismatch 0으로 PASS했다. 얇은 의자 ROI에서 reference
    MAE는 None보다 Document 9.402%, Candidate-Jitter 13.152% 낮았지만 3×3보다 각각
    0.236%, 1.529% 높았다. readback-Off 60-frame×3회에서 Filtered mask는 3×3보다
    41.423~41.777%, SMAA total은 4.734~5.171% 더 컸다. 후보는 13.897% 적었지만
    품질·시간 변화량·비용을 합치면 3×3이 우세하므로 다음 단계의 기본 current-edge
    expansion으로 선택한다. Filtered/ARM은 ablation으로 보존하고 formal 확대와 5×5/7×7은
    보류한다. 상세 결과는 `Docs/SMAA-Filtered-Quarter-Postfix-SanMiguel-Results-ko.md`를
    기준으로 한다.
29. **다음:** 새 브랜치에서 object motion vector 지원 가능성을 먼저 설계·감사한다.
    현재 `-R`은 depth와 camera matrix 기반 camera-motion reprojection만 지원한다.
    object transform의 이전 상태, velocity render target, skinned/rigid mesh coverage,
    invalid/disocclusion 판정과 history reset 경계를 확인한 뒤 최소 구현 범위를 확정한다.
    구현 시 3×3 expansion은 직교 toggle로 유지하고 object motion 효과와 섞지 않는다.
    기존 최종 8-case와 expansion ablation은 회귀 기준으로 보존한다.
30. **구조 정정 필요:** 현재 edge-selective document profile은 `SMAA::go`로 SMAA의
    edge detection→weight calculation→neighborhood blending 전체 spatial path를 실행한
    뒤, `TSCMAAExtractCandidatesCS`를 full resolution으로 dispatch한다. SMAA 1st-pass
    `edgesRT`도 SRV로 bind하지만 기본 `AllBaseEdges`와 `IntelFamilyNonDominant` 정책은
    이를 후보 근거로 사용하지 않고 luma에서 방향 edge strength를 다시 계산한다.
    `ExperimentalLocalMeanMax3x3`만 SMAA edges를 gate로 참고한다. 따라서 현재 기본
    경로에는 중복 edge 판정과 SMAA edge/candidate 불일치 가능성이 있으며, 기존에
    측정된 ET2X overhead의 원인 후보이기도 하다. 다음 핵심 작업은 SMAA 1st-pass edge
    output을 candidate source로 직접 재사용하는 controlled path를 구현·검증하는 것이다.
    기존 luma 재검출은 삭제하지 말고 `LegacyLumaRedetect` ablation으로 보존한다.
    Full SMAA spatial AA 뒤 선택 edge에만 temporal resolve를 적용하는 큰 순서 자체는
    TSCMAA-style adaptation과 양립하지만, temporal 후보 edge를 별도 재검출하는 현재
    기본 방식은 최종 구조로 확정하지 않는다.

## 7. 측정 규칙

### 공통

- Release x64
- DirectX 11
- SMAA Ultra
- 동일 해상도, 장면, 카메라 경로, animation, fixed timestep
- VSync Off
- 동일 warm-up 및 측정 프레임 구간
- 첫 프레임, scene 변경, camera teleport, resize 시 history reset
- 결과에 정확한 semantic ID와 설정값 기록

### 품질 측정

- PNG 또는 영상 연속 프레임을 사용한다.
- 고스팅, shimmer, crawling, flicker, blur, disocclusion을 연속 프레임으로 확인한다.
- 정지 스크린샷만으로 temporal 품질 결론을 내리지 않는다.
- optical-flow 보정 없는 temporal difference는 장면 motion을 포함하므로 상대 지표로만 쓴다.
- CGVQM은 full-reference 주 지표로 사용하되 절대 고스팅 ground truth라고 표현하지
  않는다. supersample spatial reference, error map, 잔상 유지 frame, temporal
  variation과 연속 영상 자료를 함께 사용한다.
- camera-motion 품질 결과는 Bistro 저대비와 Minecraft 고대비 장면을 분리해
  보고하고, 장면 평균 하나만으로 결론내리지 않는다.

### 성능 측정

- PNG 저장과 화면 캡처를 끈 상태에서 측정한다.
- 평균 FPS, GPU frame time, median, 표준편차, 1% low, p95 frame time을 기록한다.
- temporal pass, candidate extraction, indirect resolve, reprojection pass 시간을 분리한다.
- 각 case 최소 3회, 가능하면 5회 반복한다.
- 후보 픽셀 감소만으로 성능 향상이라고 결론내리지 않고 실제 GPU 시간을 확인한다.

## 8. Git 및 산출물 규칙

- `baseline/original-smaa`, `main`, 기존 Adaptive SMAA 코드를 훼손하지 않는다.
- T2X baseline, edge-selective 구현, Adaptive 통합을 한 커밋에 섞지 않는다.
- 빌드 산출물, PNG/GIF 캡처, AutoBench 원시 결과는 Git에 올리지 않는다.
- 의미 있는 코드 변경 전후를 분리해 커밋한다.
- 본 측정 전에 최소 smoke test와 Release x64 빌드를 통과해야 한다.
- 현재 브랜치와 작업 트리 상태를 확인하지 않고 이전 세션 상태를 가정하지 않는다.

## 9. 작업 중 확인 체크

매 작업 시작 시 아래를 확인한다.

- 지금 구현하거나 측정하는 case의 semantic ID는 무엇인가?
- Original/Adaptive 중 어느 공간 SMAA인가?
- Standard/Edge-selective 중 어느 temporal 방식인가?
- Reprojection Off/On 중 어느 방식인가?
- camera motion만 처리하는가, object motion도 처리하는가?
- 비교 대상 사이에서 의도하지 않은 jitter, history weight, clipping 차이가 있는가?
- 이번 결과가 8-case 최종 결과인지, 중간 smoke/ablation 결과인지?

이 질문에 답할 수 없으면 구현이나 본 측정을 진행하지 않는다.
