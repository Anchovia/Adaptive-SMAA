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

## 4. 2026-07-29 현재 구현 상태

| ID | 상태 | 현재 코드 대응 |
|---|---|---|
| `O-T2X` | 구현됨 | `SMAA_O_T2X`; 같은 좌표의 current/previous를 기본 0.5 weight로 결합 |
| `O-T2X-R` | 구현됨 | `SMAA_O_T2X_R`; camera-motion velocity 사용 |
| `O-ET2X` | prototype 구현 | `SMAA_O_ET2X`; 같은 좌표의 history를 사용하는 no-reprojection ablation |
| `O-ET2X-R` | prototype 구현 | `SMAA_O_ET2X_R`; edge-selective + camera reprojection On 복합 실험 버전 |
| Adaptive 4개 | **미구현** | Original 4개를 검증한 뒤 `main`의 Adaptive SMAA와 통합해야 함 |

Original 네 mode는 `TemporalCoverage`, `ReprojectionMode`, `JitterPolicy`, history sampler,
clipping, candidate policy와 history weight를 명시적으로 기록하는 설정 구조로 연결되어
있다. `-smaaOriginalFourCapture`로 네 mode를 같은 조건에서 순회하는 engineering smoke
capture를 실행할 수 있다.

후보 추출·계측 단계에는 다음이 구현되어 있다.

- 별도 full-resolution luma edge와 threshold `1/22`
- `AllBaseEdges`, `IntelFamilyNonDominant`, `ExperimentalLocalMeanMax3x3` 세 정책
- `IntelFamilyNonDominant`는 Intel CMAA2의 연결된 수직 edge local-contrast 구조를
  TSCMAA 공개 기본값과 결합한 adaptation이며 유실된 원본 식과 동일하다고 표현하지 않음
- candidate compact/indirect process·group count와 비동기 GPU readback
- base edge/candidate debug mask와 개발 UI
- `-smaaCandidatePolicyOverride`, `-smaaTemporalDebugView`,
  `-smaaCandidateForcedCount` 진단 옵션

기존 prototype 출력 보존을 위해 기본 정책은 아직 `ExperimentalLocalMeanMax3x3`이다.
`IntelFamilyNonDominant`는 diagnostic override에서 검증 중이며 controlled
`O-ET2X`/`O-ET2X-R` 기본값으로 아직 승인하지 않았다.

동일 deterministic smoke 프레임에서 base edge 57,354개 중 AllBase 57,354개,
Intel-family 34,938개(60.916%), Experimental 44,266개(77.180%)가 선택됐고 indirect
process count는 candidate count와 일치했다. 이는 구현 검증용 한 프레임 결과이며 최종
품질·성능 결과가 아니다.

forced-count 진단으로 0, 1, 63, 64, 65와 전체 화면 최대 1,952,640 후보를 GPU에서
실제로 compact한 뒤 전체 candidate buffer를 readback했다. 모든 case에서 candidate와
process count, `ceil(count/64)` group count가 기대값과 일치했고 중복·범위 밖·overflow는
0이었다. 전체 candidate-list staging buffer는 진단 옵션이 켜진 경우에만 생성하며 본
성능 측정에는 포함하지 않는다.

현재 `O-ET2X`와 `O-ET2X-R` prototype은 다음 변경을 동시에 포함한다.

- deliberate projection jitter 비활성화
- SMAA 1X spatial input
- locally dominant edge candidate 선택
- camera-motion history reprojection
- Catmull-Rom 5-tap history sampling
- YCoCg variance clipping
- history weight 0.8

따라서 두 prototype은 현재 상태에서 최종 controlled 구현으로 간주하지 않는다. 설정
구조와 candidate policy는 분리됐지만 sampler/clipping toggle의 실제 shader 분기 및
공식 자료 기반 검증은 아직 완료되지 않았다.

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
2. **진행 중:** 후보 정책 계측과 0/1/group/최대 경계 검증은 완료했다. 다음은
   bilinear/no-clipping selective resolve 골격부터 Original SMAA 기반 `O-T2X`,
   `O-T2X-R`, `O-ET2X`, `O-ET2X-R` 네 controlled mode를 구현한다.
3. 네 mode에서 history 초기화, ping-pong, jitter, subsample index, scene/resize reset을 검증한다.
4. 후보 선택 외의 Catmull-Rom, variance clipping, history weight 변경은 ablation toggle로 분리한다.
5. Original 4개에 대한 동일 조건 품질·성능 결과를 확보한다.
6. 그 이후에만 Adaptive SMAA를 결합하여 `A-*` 네 mode를 만든다.
7. Adaptive 4개를 같은 조건으로 측정해 최종 8-case 표를 작성한다.

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
