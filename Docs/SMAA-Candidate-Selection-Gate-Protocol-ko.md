# 후보식 단독 비교 및 핵심 구현 선정

2026-09-15, 기준 `31b881d`, `research/tscmaa-candidate-selection-gate`.

## 질문과 고정 조건

Original SMAA에서 기존 document temporal 계산을 유지한 채 확보 소스의 후보식만
적용할 때 품질과 전체 AA 비용이 개선되는지 확인한다. 원본 CMAA-based TSCMAA 전체
재현이나 최종 8-case 측정이 아니다. 기존 기본값을 변경하지 않는다.

비교는 `O-T2X-R`, `O-ET2X-R-DocCandidate-DocKernel`,
`O-ET2X-R-SourceCandidate-DocKernel-Integrated`다. 두 선택적 모드는 모두
first-edge-pass 통합, CompactIndirect, expansion None, removal 0.5, jitter Off,
camera/depth R, document 5-tap/variance clipping, weight 0.8, resolved feedback 및
동일 두 복사 경로를 사용한다. Source 후보는 weighted RGB residual 기반이며 기존 luma
후보의 부분집합이나 고정 50% 할당량이 아니다. Threshold는 1/22다.

Standard는 공식 paired jitter/subsample pattern과 spatial-frame history를 유지한다.
따라서 Standard 대비 차이는 선택적 처리 전체 조합의 효과이고 후보식 단독 효과는
두 선택적 모드 사이에서만 평가한다. Adaptive, object velocity, 확장 및 threshold sweep은 제외한다.

## 실행 및 판정

- Release x64 DX11, Ultra, 1920×1017, VSync Off. 각 명령은 별도 clean process,
  timeout 600초, 실행 전후 잔류 0. 사용자 설정 XML은 전체 바이트로 복원한다.
- 12-frame 독립 short 캡처와 smoke를 먼저 검증한다. 기존 8-case 96프레임과
  SourceCandidate/DocKernel의 feedback도 확인한다. 셰이더 수식은 수정하지 않는다.
- Bistro/Minecraft wide 이동+회전→정지 480프레임, 첫 pose warm-up 60.
  O-1X/Standard/두 후보식의 새 캡처를 이전 전체 출력과 RGB hash로 대조한다.
  전체 일치와 reference hash/config/FFV1 검증이 있을 때만 기존 CGVQM-2 점수를 재사용한다.
  불일치 시 실패 배열을 보존하고 원인 확인 전 재사용하지 않는다.
- 기존 120-frame 후보 mask와 새 통합 mask를 대조하고 비후보=current spatial을 확인한다.
  후보 coverage/Jaccard는 해당 구간에만 적용하며 성능 경로의 후보 통계로 대체하지 않는다.
- 성능은 별도 visible 실행에서 300 warm-up, 4,800 frame×3회, 정/역/정 순서로
  세 모드를 순회한다. PNG/UI/candidate readback Off. 기존 flythrough start 0초 경로이므로
  wide 품질 캡처와 동일 프레임 trade-off 곡선으로 표현하지 않는다.
- 전체 SMAA/WholeFrame, spatial+통합 후보 비용, clear, velocity, indirect args, resolve,
  두 복사를 함께 보고한다. 통합 후보 계산만 독립 timer로 떼어낼 수 없음을 명시한다.
  평균/median/p95/p99/반복 평균 SD 및 wall interval의 1% low를 기록한다.
- 일관된 승자가 없으면 장면/움직임별 trade-off로 분류하고 기본 구현을 유지한다.
  다음 확장 실험의 기준은 이번 품질·전체 비용 판단에 근거해 선정한다.
