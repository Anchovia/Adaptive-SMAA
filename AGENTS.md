# Adaptive SMAA / TSCMAA 연구 작업 규칙

이 파일은 저장소 전체에 적용되는 연구·구현 지침이다. 이후 작업자는 코드 수정, 실험 설계,
측정, 보고서 작성 전에 반드시 이 파일을 읽고 아래 실험 행렬과 용어를 유지해야 한다.
기존 문서나 임시 보고서가 이 파일과 충돌하면 이 파일을 우선하고, 충돌 내용을 사용자에게
알린 뒤 정정한다.

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

## 4. 2026-07-30 현재 구현 상태

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
이후 완료됐다. SMAA 1X control과 Original camera-reprojection 경로의 구성요소별
ablation도 이후 완료됐으며 최종 연구 결론에는 supersample/optical-flow reference
보강이 남아 있다.

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
variation/flicker 증가 가능성`의 trade-off 근거다. SMAA 1X 또는 supersample
ground truth와 optical-flow 보정이 없으므로 최종 품질 우위나 절대 ghosting 점수로
표현하지 않는다. 품질 PNG capture는 hidden-window로 실행했지만 저장된 render target
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

이 ablation은 최종 8-case mode를 늘리지 않는 원인 분석용 진단 경로다. 품질 지표는
ground-truth가 아니므로 최종 품질 우위는 supersample 또는 optical-flow reference로
보강하기 전까지 보류한다. 상세 결과는
`Docs/SMAA-Temporal-Component-Ablation-Results-ko.md`를 기준으로 한다.

`-smaaOriginalFourCapture 1 1 6`의 첫 mode인 `O-T2X`는 같은 실행 조건에서도
`9F5B...`와 `74E9...` 두 PNG hash가 관측됐다. `O-T2X-R`, `O-ET2X`, `O-ET2X-R`은
반복 일치했으며 이 현상은 sampler override와 무관하다. 시작 프레임/history warm-up
비결정성을 해결하기 전에는 `O-T2X` 단일 프레임 hash를 최종 deterministic 증거로
사용하지 않는다.

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
14. **남음:** supersample reference 또는 optical-flow 정렬 지표로 현재 trail과
    temporal variation 해석을 보강한다. 필요하면 object motion vector 지원을 별도
    확장 연구로 분리한다.

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
