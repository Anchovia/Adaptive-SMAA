# 확보 소스 기반 SMAA 비교 프로토콜

## 기준과 범위

기준 브랜치는 `research/tscmaa-source-audit`, 기준 커밋은
`4fa5f8b90f1e35ba261ab46e9ad4f4eaed7c91cb`다. 구현 브랜치는
`research/tscmaa-source-based-smaa`다. 기존 8-case 기본 설정은 유지한다.
이 실험은 확보한 Intel TSCMAA의 후보식과 temporal kernel을 **SMAA 공간 처리에
적용한 adaptation**이다. CMAA 공간 처리를 포함하는 전체 TSCMAA의 exact port가 아니다.

첫 비교는 Original SMAA, camera/depth reprojection On, jitter Off, expansion None,
resolved-output history, threshold 1/22, removal 0.5를 고정한다.

| 진단 ID | 후보 | Temporal kernel |
|---|---|---|
| O-ET2X-R-DocCandidate-DocKernel | 기존 integrated Intel-family | 기존 document |
| O-ET2X-R-SourceCandidate-DocKernel | 확보 소스 식 | 기존 document |
| O-ET2X-R-DocCandidate-SourceKernel | 기존 integrated Intel-family | 확보 소스 식 |
| O-ET2X-R-SourceCandidate-SourceKernel | 확보 소스 식 | 확보 소스 식 |

이름의 Source는 확보 소스의 수식에 근거한다는 뜻이다. 원본 실행파일의 출력과 byte-exact
동일하다는 뜻은 아니다. 후보 교체와 kernel 교체의 주효과 및 상호작용을 분리한다.

## 구현 대응

- 후보: AA 이전 UNORM RGB에서 weighted-channel maximum difference, threshold subtraction,
  연결된 수직 edge 네 개의 평균 suppression, 사방 residual의 threshold/2 초과를 구현한다.
  SMAA base-edge로 다시 제한하지 않는다. 원본의 CMAA shape 후보와 TAA 후보는 다르다.
- 최초 이식은 안전한 pixel 단위 compute로 식을 평가한다. 원본 group-shared/fused CMAA
  실행 구조와 다른 비용이므로 timing을 Intel 원본의 성능으로 표현하지 않는다.
- kernel: UNORM SRV의 black-border linear sampling, 확보 5-fetch 식의 비대칭 항,
  YCoCg center sharpening 0.263157904, RGB endpoint clamp, weight 0.789473712,
  square/sqrt blend를 보존한다. 기존 proper-sRGB document kernel과 혼합하지 않는다.
- 원본의 색 endpoint 역전 및 음수 chroma 제거도 기준 수식에 포함한다. 품질 개선을
  가정해 임의로 교정하지 않는다. variance의 음수 반올림은 0으로 제한하는 수치 안전성
  변경을 명시한다. 원본 min16float와 compiler 실행 정밀도의 차이는 따로 검증한다.
- list load 전 count 검사, full-resolution capacity, pixel 경계 검사와 초기 current-frame
  history seed를 유지한다. 원본의 uninitialized matrix/history 및 resize 오류는 재현하지 않는다.
- 같은 camera velocity와 올바른 previous projection을 재사용한다. 원본 matrix 연산 순서와
  R16G16 velocity 저장에 의한 수치 차이는 exactness 한계다. object velocity는 Off다.

## 검증 순서와 판정

1. 변경 전 기본 8-case 짧은 PNG sequence와 실행파일 hash를 보존한다.
2. Release x64 빌드, 후보 mask/compact/indirect 경계와 CPU/GPU 식 대응을 검사한다.
3. 기본 8-case PNG 회귀, history seed/feedback/lifecycle와 후보 외 spatial 보존을 검사한다.
4. 동일 장면/카메라/초기 pose/warm-up/pre-roll로 네 설정의 sequence를 비교한다.
   비교 중 설정과 원시 실행 경로, frame index, 해상도, reset 상태를 기록한다.
5. PNG/readback을 끈 반복 성능에서 후보 준비·추출·resolve·복사·전체 SMAA를 기록한다.
   후보 감소나 image difference만으로 품질 향상을 판정하지 않는다.

매 실행은 clean runner로 독립 프로세스를 사용한다. 실패/timeout의 부분 결과는 제외한다.
품질은 연속 프레임과 spatial-reference proxy를 함께 해석하고 절대 temporal ground truth라고
부르지 않는다. 원본 대비 안전성 변경과 SMAA 적용 가정을 결과 문서에도 유지한다.
