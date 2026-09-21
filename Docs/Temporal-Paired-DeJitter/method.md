# Current/history paired de-jitter 검증 계획

출발점 `9c49d5e`, 브랜치 `experiment/temporal-pass-paired-dejitter`.
Original spatial SMAA + camera/depth reprojection On의 별도 engineering ablation이다.
기본 O-T2X-R 및 최종 8-case 의미는 보존한다. Object motion은 지원하지 않는다.

## 가설과 범위

현재만 보정하면 정지 장면의 두 출력은 (D0(C0)+C1)/2와 (D1(C1)+C0)/2로 서로 다르다.
현재와 이전을 모두 보정하면 (D0(C0)+D1(C1))/2의 대칭성을 회복할 수 있는지 확인한다.
유효한 history는 직전 성공한 draw의 반대 phase spatial texture다. wrapper가 spatial 저장,
resolve 후에만 두 frame index를 함께 advance하며 reset은 history를 invalid로 만든다.
Invalid history는 기존 동일 draw에서 DeJitterSpatial(kind31)로 seed한다.

기존 constant의 subsample index 1/2는 화면 jitter +.25/-.25 픽셀이다. index0은 보정0이다.
Current는 Linear(UV+j), previous는 Linear(UV-motion-j), velocity는 기존 Point(UV)다.
History는 계속 raw spatial frame이며 추가 pass, copy, texture, sample 명령을 추가하지 않는다.
Velocity가 원래 위치의 depth에서 생성된 값이므로 움직이는 경계의 재구성은 근사다.
RGBA 필터링은 alpha와 실제 가중치도 바꾼다. Linear는 여러 texel을 사용하므로 무료가 아니다.
이는 공식 T2X와 동일한 reconstruction이나 원본 TSCMAA 이식이라고 주장하지 않는다.

## 순차 gate

1. 전체 화면 정지 gate: 두 장면 각각 40 frame, 60 warmup 후 frame0 reset.
   O-T2X-R, history Linear-only(kind25), current-only(kind28), paired(kind32),
   paired 반복, corrected spatial(kind31)을 캡처한다. Late20..39에서 원본 byte 안정성과
   paired 반복/seed 일치를 검사한다. Paired도 완전 안정이 목표다. 부동소수 반올림으로
   최대1 RGB 단계, 평균 step .001 이하만 남으면 이를 명시해 수치 오차 수준으로 분류한다.
   이 범위를 넘으면 선택 기능을 구현하지 않고 원인을 먼저 분석한다.
2. Gate 통과 후에만 기존 luma derivative threshold .01을 보정 current에 적용한다.
   선택된 픽셀=paired full, 비선택=corrected spatial의 일치를 검증한다.
3. 동일 240-frame still/moving/still, supersample spatial proxy와 비교한다.
   Native, history Linear-only, old Scalar, paired full, paired Scalar를 구분한다.
   선택률은 혼합한 픽셀 비율이며 history fetch 생략률이 아니다.
4. 빌드/정확성/smoke 후 PNG·readback 없는 4800 frame×4 교차 반복으로 전체 AA와 resolve
   비용을 분리한다. 한 process의 반복이며 독립4회/성능 동등성 증명이 아니다.

기존 공식 API 근거: [SampleLevel](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel),
[D3D11_FILTER](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_filter).
