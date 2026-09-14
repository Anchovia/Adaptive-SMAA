# 원본식 후보 생성 통합 및 Standard SMAA T2X 비교

기준 commit은 `b696c28`, 작업 branch는 `research/tscmaa-integrated-source-candidates`다.
기존 별도 후보 추출 버전은 수식·출력 기준 및 실행 구조 ablation으로 보존한다.

주 비교는 **Original SMAA Standard T2X + camera reprojection**과 **같은 Original SMAA에
원본식 후보 생성·source temporal kernel을 적용한 통합 버전**이다. Standard의 공식
paired jitter/subsample, point history, spatial-frame history와 adaptive weight를 바꾸지
않는다. Source는 no jitter, 원본식 filtering/clipping/weight와 resolved feedback을 유지한다.
이는 완성 기법 간 비교이며 후보 coverage 단독 효과라고 해석하지 않는다. 기존 8-case 기본은 불변이다.

## 구현 gate

- 별도 full-screen 후보 추출 Dispatch를 제거하고 SMAA edge PS에서 원본 RGB residual
  후보를 생성한다. Source 후보를 SMAA luma edge로 다시 gate하지 않는다.
- Source 후보 UAV 쓰기는 SMAA의 discard보다 먼저 수행한다. Spatial edge/contrast와
  stencil 동작은 유지한다. D3D11.3 기능 명세 16.13은 discard 이전 UAV 쓰기가 유지되며
  discard 이후 쓰기는 무시됨을 명시한다.
  [Microsoft D3D11.3 specification](https://microsoft.github.io/DirectX-Specs/d3d/archive/D3D11_3_FunctionalSpec.htm#16.13%20Pixel%20Shader%20Discarded%20Pixels%20and%20Helper%20Pixels)
- 기존 별도 CS와 같은 후보 함수, pre-AA UNORM input, minprecision, threshold/removal을 사용한다.
- 후보 mask/list/count/indirect args, 중복/범위/overflow, profile 전환과 history reset을 검사한다.
- 두 장면의 같은 동적 경로에서 별도/통합 mask와 최종 PNG가 일치해야 본 측정으로 진행한다.
- Standard T2X와 기본 8-case의 출력 회귀 및 history lifecycle을 검사한다.

## 측정 gate

- primary: O-T2X-R (Standard), O-ET2X-R-SourceCandidate-SourceKernel-Integrated.
- engineering control: O-ET2X-R-SourceCandidate-SourceKernel-Separate.
- 품질 보조: O-1X, 동일 pose supersampled spatial reference.
- 동일 장면·해상도·camera path·warm-up에서 비교한다. 성능은 세 mode를 한 clean process에서
  교차 순서로 300 warm-up, 4,800 frame × 3회, visible/VSync Off/readback Off로 측정한다.
- temporal resolve는 원본에도 있는 별도 pass로 유지한다. 모든 copy와 후보 준비를 포함한
  전체 AA 시간을 보고한다. 통합 후 빨라질 것이라고 미리 판정하지 않는다.
- 품질은 CGVQM과 spatial-reference 오차 및 연속 영상을 함께 본다. Reference는 temporal
  ground truth가 아니며 기존 별도 패스의 품질 자료는 동일성 검증 범위에서만 연결한다.
- 기존 push는 공개 연구 코드·결과 게시의 구체적 승인 부족으로 자동 검토가 거부한 상태다.
  이번 일반 작업 시작 지시를 그 공개 게시 승인으로 간주하여 우회하지 않는다. 로컬 커밋까지 진행한다.
