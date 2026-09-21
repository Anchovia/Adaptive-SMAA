# 동일 edge RG 읽기 최적화 사전 계획

기준은 `6899477`의 첫-pass edge read gate다. 현재 `experiment/temporal-edge-read-cost`
브랜치에서 진단 모드만 추가한다. 원본 mode와 기존 측정 결과는 보존한다.

## 고정 조건

동일 프레임 edgesRT(RG8_UNORM), 현재 픽셀 RG 모두, mip 0, full resolution,
기존 pixel pass, Original SMAA T2X-R 계산과 spatial-frame history를 고정한다.
새 production pass/texture/복사/후보 선택/분기는 없다. 표본 생략이나 근사도 없다.

## 제한된 후보

- 기존 Load (56), Point SampleLevel(57), 앞에 배치한 Load(58), 앞에 배치한 Point(59).
- 기존 Native(0)와 matched sink Control(55)을 함께 비교한다.
- Source 순서만 바뀌고 R-On DXBC executable instructions가 동일하면 중복 timing은 생략한다.
- DXBC 순서는 native GPU instruction scheduling 또는 실제 stall 원인의 증명이 아니다.
- Read scheduling은 독립 접근의 latency hiding과 register 수 증가의 trade-off다.

## 정확성 선행 조건

runtime-zero 출력 동일성만으로 읽은 값의 동일성을 판단하지 않는다.
Load/Point는 공통 production access helper를 사용한다. 별도 offscreen pixel-shader probe는
production과 같은 fullscreen triangle/UV, origin-zero viewport, Point+Clamp sampler와
RG8 형식으로 화면 가장자리·1×1·3×5·1919×1061·1920×1061·1920×1080을 검사한다.
두 phase의 임의 RG8 값 및 0/1 edge 패턴을 생성하고 각 pixel의 Load/Point float RG를
직접 비교한다. Readback은 검증에서만 사용한다.
실제 두 장면에서도 diagnostic shader가 Load와 Point RG를 비교해 mismatch를 R에 출력하고
원래 RG는 GB에 출력한다. 이동/정지와 두 jitter 위상을 포함한 frame별 full-image 검증을 한다.
최종 색상 zero-scale 출력과 기존 Native hash bridge도 검사한다.

## 성능과 종료 조건

정확성 통과 variant만 같은 clean process의 alternating order 4800 frames×4 repeats로 비교한다.
기존 read와 대조군 및 Native는 같은 실행에 포함한다. Capture/CPU 영상 분석을 timing과 분리한다.
우열은 temporal 및 whole-SMAA GPU 시간, 반복 차이/분산을 함께 보고한다.
결과가 미미하거나 장면마다 역전되면 우승자를 강제로 고르지 않고 기존 Load를 보존한다.
이번 두 가지 접근 검토를 완료하면 종료하며 후보 선택이나 품질 알고리즘으로 범위를 확장하지 않는다.

## 근거

- https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load
- https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel
- https://developer.nvidia.com/blog/advanced-api-performance-shaders/

Load의 out-of-bounds zero와 Point Clamp는 일반적으로 다르다. 이번 동치는 현재 pass의
in-bounds current-pixel 접근 범위에 한정하며 임의 UV나 외부 viewport에 일반화하지 않는다.
