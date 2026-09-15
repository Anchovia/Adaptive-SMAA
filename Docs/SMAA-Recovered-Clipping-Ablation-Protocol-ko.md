# 확보 소스 clipping 2×2 효과 분리 계획

기준 커밋: `c5b5a149ee7c1d992cd4d7169bea480690dc8e31`.
브랜치: `research/tscmaa-source-clipping-ablation`.

목적은 소스 기반 temporal kernel의 품질 열세에서 clipping의 두 계산이 차지하는 영향을
분리하는 것이다. 원본 전체의 오류율을 추정하거나 최종 8-case 기본값을 변경하지 않는다.

| 진단 이름 | 중심 YCoCg 음수 색차 | variance clamp 공간 |
|---|---|---|
| SourceClip | 원본처럼 0으로 제한 | 원본처럼 두 끝점만 RGB 변환 |
| SignedChroma | 부호 유지 | 원본 RGB 끝점 처리 |
| YCoCgClamp | 원본처럼 0으로 제한 | history를 YCoCg로 변환하여 제한 후 RGB 복원 |
| SignedChroma-YCoCgClamp | 부호 유지 | YCoCg에서 제한 |

공통 조건: Original SMAA, recovered source 후보식, 첫 edge 패스 통합, CompactIndirect,
확장 None, removal 0.5, camera/depth reprojection On, source 5-fetch sampler,
sharpen 0.263157904, weight 0.789473712, source 제곱/제곱근 blend 및 R8 packing,
ResolvedOutput feedback, jitter Off. 중심 Y 하한 0은 네 조합 모두 유지한다.
RGB 범위를 재정렬하거나 sampling/blending/weight를 동시에 수정하지 않는다.

두 컴파일 스위치는 기본 0이다. 전용 runner가 독립 프로세스 사이에서만 설정을 바꾸고
실행 manifest에 의미 이름, 두 값, 실행 파일 및 shader hash를 저장한다. `finally`에서
shader와 사용자 ApplicationSettings의 원본 bytes를 복원한다. 앱 CSV의 기존 mode 이름만
보고 조합을 판단하지 않고 manifest를 함께 사용한다. 각 실행은 clean runner로 격리한다.

검증 순서:

1. 이전 source resolve/extract와 기본 조합의 DXBC 동일성 및 네 조합 컴파일.
2. 창 없는 D3D11 fixture에서 CPU 식 대응, 유한값, 색상 보존과 YCoCg box 내부 판정.
3. 두 장면의 짧은 캡처로 baseline/후보 mask 동일성 확인.
4. Bistro/Minecraft의 동일 480-frame wide 이동·회전 경로, 첫 pose warm-up 60.
   baseline은 기존 source 480-frame hash bridge로 검증한다.
5. supersample spatial-reference proxy에 대해 MAE/PSNR, 시간 차분 residual 및 비교 이미지.
   중앙 이동 150–329와 이동→정지 410–439의 공식 CGVQM-2를 함께 평가한다.
6. 성능은 PNG 캡처와 분리한다. 품질 후보가 나오면 동일 조건의 반복 실행으로 비용을
   확인한다. 작은 차이나 서로 다른 실행의 환경 변화를 최적화 성과로 단정하지 않는다.
   Benchmark 실행 중 `observe_recovered_clipping_windows.ps1`을 별도 셸에서 실행해
   프로세스별 표시·최소화 상태를 기록한다. 분석기는 품질/성능 코드 hash의 일치도 확인한다.

SignedChroma 단독은 RGB 끝점 역전 문제를 남긴다. YCoCgClamp 단독은 잘못된 색차 통계를
남길 수 있다. 따라서 두 주효과와 상호작용을 함께 기록하고, 단색 fixture의 개선을
실제 장면의 ghosting 개선으로 대신하지 않는다. 공간 reference와 CGVQM도 절대적인
temporal ground truth는 아니다. 이 gate의 결과로만 source kernel 전체의 우위를 주장하지 않는다.
