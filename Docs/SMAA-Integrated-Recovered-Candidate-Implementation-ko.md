# 확보 소스 후보 생성의 SMAA 첫 패스 통합

작업 branch: `research/tscmaa-integrated-source-candidates`.
비교 기준: `b696c28`의 별도 compute 후보 추출 및 recovered-source temporal kernel.
본 작업은 CMAA의 공간 필터를 SMAA로 대체하는 adaptation이며 CMAA 원본 전체의 exact port가 아니다.

## 구현

`-smaaRecoveredSourceProfile 3 -smaaRecoveredSourceIntegratedCandidates 1`에서
Original SMAA의 edge pixel shader가 pre-AA UNORM RGB를 읽어 recovered-source 후보를
생성한다. 기본값은 Off로 유지해 기존 8-case 및 이전 실험의 설정을 보존한다.

`RecoveredTSCMAACandidate.hlsl`에 후보 함수를 공유하고 원본의 weighted-RGB max 차이,
threshold subtraction, 네 연결 edge 평균 suppression, 추가 `0.5 × threshold` 판정을 유지한다.
동일한 min16float 경계와 black halo도 보존한다. 후보를 SMAA luma edge로 다시 제한하지 않는다.

후보 mask/list/counter UAV 쓰기는 기존 SMAA discard 전에 수행한다. 이후 공간 edge 계산,
discard와 stencil 출력은 그대로 유지한다. D3D11 명세의 discard 이전 UAV 쓰기 규칙을 따른다.
후보 개수는 같은 방식으로 compact하고 64-thread indirect temporal resolve를 실행한다.
후보 목록의 atomic 삽입 순서는 비교 대상이 아니며 픽셀 집합, 중복 및 범위를 검사한다.

성능 비교에서 수식 외의 변경이 섞이지 않도록 별도 CS의 mask 쓰기와 base counter 증가도
통합 PS에 유지했다. 통합 경로는 control clear를 사용하며 별도 후보 준비와 full-screen 후보
Dispatch를 제거한다. Temporal resolve, camera velocity, spatial/history 및 output copy는 남는다.
SMAA first pass에는 RGB 후보 계산 비용이 추가되므로 실제 전체 GPU 시간으로 효과를 판정한다.

## 검증

- 재시작 후 동일 60-frame warm-up 기준 캡처 `20260914_190049`는 이전 `20260914_140823`의
  8-case 96 PNG와 byte mismatch 0이다. 24-frame warm-up의 `185409`는 조건이 달라 비교에서 제외했다.
- Release x64 빌드 통과. Shared-header 분리 전후 `RecoveredExtractCS`, `RecoveredResolveCS`
  FXC `/O3` bytecode가 각각 동일하다. Original/Adaptive × RGB/raw-luma 통합 PS 4 variant도 컴파일됐다.
- `20260914_190612` same-draw snapshot에서 Bistro/Minecraft 각각 별도/통합을 7회 교대했다.
  Base/selected mask 동일, candidate=process, ceil(count/64)와 실제 indirect args 일치.
  중복/OOB/overflow/mask mismatch/args mismatch 모두 0, history seed 및 설정 복원 PASS.
- 두 장면의 동적 경로 첫 12 frame에서 별도/통합 최종 PNG byte mismatch 0.
- 최종 빌드 기본 8-case `20260914_191019`는 변경 전 96 PNG와 mismatch 0.
  Lifecycle `191037`, integrated source feedback `191046` PASS. History/output byte mismatch 0.
- Forced count 0/1/63/64/65/1,952,640의 짧은 캡처 `191105`~`191152` 모두 정상 종료 및 검사 PASS.

## 비교 실행

`Tools/SMAA/run_integrated_source_comparison.ps1`은 Snapshot/Regression/Boundary/ShortQuality/
Quality/Masks/Smoke/Benchmark를 각각 새 프로세스로 실행하고 명령·실행파일 hash·보고서 위치를 기록한다.
`validate_integrated_source_equivalence.py`는 GPU snapshot과 동적 PNG의 동일성을 검사한다.

`-smaaIntegratedSourcePerformanceSmoke` / `Benchmark`는 `O-T2X-R`,
`O-ET2X-R-SourceCandidate-SourceKernel-Separate`,
`O-ET2X-R-SourceCandidate-SourceKernel-Integrated`를 교대한다.
Standard의 공식 paired jitter/subsample, point sampling, spatial-frame history와 adaptive weight는
유지한다. 두 source mode는 no jitter 및 같은 source temporal kernel/resolved feedback을 사용한다.
따라서 Standard 대비는 완성 기법 비교, 별도 대비 통합은 후보 실행 구조 비교다.

전체 동적 sequence와 반복 측정을 완료했다. 최종 결과는
`Docs/SMAA-Integrated-Recovered-Candidate-Results-ko.md`를 따른다.
통합 전후 960 frame 출력은 동일했고 AA 시간은 약 6% 감소했으나,
Standard T2X-R 대비 성능 및 CGVQM 우위는 확인되지 않았다.
