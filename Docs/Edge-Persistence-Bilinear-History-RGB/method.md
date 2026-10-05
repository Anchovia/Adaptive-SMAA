# 직전 raw-edge 선택 유지 + history RGB bilinear 실험

독립 브랜치: `experiment/edge-persistence-bilinear-history-rgb`.
공통 기준선 `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459`에서 직접 분기했다.
⑨의 필요한 의존성만 `9f46c9a`로 먼저 분리했다. 기존 depth-export,
shader stencil-ref, 실패한 속도 실험과 다른 항목의 구현을 누적 상속하지 않았다.
의존성과 제외 목록은 `dependency.json`에 기록한다.

## 가설과 고정 조건

지터 Off에서 이미 선택된 픽셀도 point 재투영으로 색상이 바뀌며 선이 약해지는
문제가 있다. 필터의 개선 가능성만 확인하기 위해 **history RGB만 bilinear**로 바꾼다.
정지 화면의 부족한 공간 표본 자체를 복구하는 가설은 아니다.

Original SMAA Ultra 공간 3단계, camera/depth reprojection, 현재 raw edge와 재투영한
직전 raw edge의 stencil union, Pattern Off, spatial-frame history, 비선택=current spatial,
history 초기화와 원본 point alpha 기반 `0..0.5` 가중치는 유지한다. 새 패스, dilation,
clip, Adaptive, object-motion velocity, resolved-output feedback을 추가하지 않는다.

기존 point history fetch에서 alpha를 보존하고 같은 UV에서 RGB만 linear sampler,
LOD 0으로 한 번 더 읽는다. 출력 alpha도 기존 point alpha 혼합을 유지한다.
FXC 생산 셰이더는 velocity/current/history point 3 sample에서 RGB bilinear를 더한
4 sample로 바뀐다. 이는 sample 명령 수이며 실제 메모리 거래 수와 동일한 표현이 아니다.
추가 접근 비용을 포함해 평가하고 속도 개선을 선험적으로 주장하지 않는다.

| 캡처 ID | 의미 | paired jitter/subsample | RGB / alpha |
|---|---|---|---|
| `O-T2X-R` | 원본 ④, 전체 화면 temporal | On | point / point |
| `O-ET2X-R-CurrentEdge-Point` | 수정된 ⑥, 현재 first-pass edge | Off | point / point |
| `O-ET2X-R-PreviousRawEdge-Point` | ⑨, 현재 + 직전 raw edge | Off | point / point |
| `ABL-ET2X-R-PreviousRawEdge-BilinearRGB` | 이번 가설, ⑨의 RGB 필터만 변경 | Off | bilinear / point |

이 ID는 중간 ablation의 설정을 나타낸다. 최종 Original/Adaptive 8-case 완료나
원본 Intel TSCMAA exact port로 표현하지 않는다. ④와의 품질 차이는 sample pattern
차이도 포함한다. 필터 자체의 대조는 ⑨와 새 구현이다.

## 실행과 정확성

- DX11 Release x64, RTX 3060 Ti, 1920×1061, hidden, VSync Off, deterministic fixed60.
- scene bootstrap 후 별도 clean process. 실행 전후 CMAA2 process 0 확인, timeout1200s.
- 240 frame: 정지60 / 이동120 / 정지60. mode별 같은 첫 pose에서60 frame warm-up.
- 원본 ④/수정⑥는 공통 기준선240 RGB hash, ⑨는 불변 커밋 `6e6950c`의240 hash와 연결한다.
  장면별 720 control PNG의 실제 decoded RGB가 동일해야 한다.
- 선택 경로43 trace frame의 raw/current/previous/velocity/edge/coverage/weight DDS가
  ⑨와 새 구현에서 byte-exact인지 검사한다. 모든 비선택 RGB=current spatial,
  첫 프레임=current edge만, weight 유한값 및 `0..0.5`, 비선택 weight0도 검사한다.
- 캡처 전용 coverage/R32 weight MRT와 query/readback은 성능 실행에서 꺼진다.
- 기존 point 생산/coverage 셰이더의 R Off/On DXBC4개가 기준선과 byte-exact인지 확인한다.

CPU point alpha/weight와 point RGB mirror는 안전한 point 경계에서 검증한다.
이상적인 float bilinear mirror는 좌표에서0.5 texel을 뺀 뒤 네 texel을 clamp하고,
**sRGB→linear 후** 보간한다. 하드웨어의 정확한 수치 재현 모델로 표현하지 않는다.
최초 분석의 RGB2 tolerance는 Bistro179(1049,584)와 Minecraft133(167,784)의
어두운 픽셀에서 RGB3 차이로 실패했다. renderer/캡처는 수정하거나 재실행하지 않았다.
ideal model과의 차이는 그대로 기록하고, 필터의 유한 정밀도를 고려한 보수적인
진단 envelope도 따로 검사한다. 이 envelope는 공식 규격 준수 인증이나 exact GPU
mirror가 아니다. 좌표8 fractional bit, format precision의1/255와 출력 양자화 등을
명시한 CPU 진단이다. 가중치·입력·mask의 GPU byte 비교와 구분한다.

Direct3D의 normalized coordinate 처리, bilinear 주소 계산과 최소 필터 정밀도는
[Microsoft D3D11.3 규격 7.18.8/7.18.16](https://microsoft.github.io/DirectX-Specs/d3d/archive/D3D11_3_FunctionalSpec.htm),
LOD 선택은 [SampleLevel 공식 문서](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel)를 참고했다.
일반적인 bilinear history reprojection과 세부 구조의 흐림 위험은
[Yang·Liu·Salvi 2020 TAA survey](https://leiy.cc/publications/TAA/TemporalAA.pdf)의 3.1/6.1.1을
참고한다. 이 논문이 이번 SMAA 가설의 품질 개선을 보장하는 근거는 아니다.

## 품질과 성능 판단

원본 full frame와 nearest2× ROI의 이동130–135, 전후127–138, 전환178–183,
정지190–195를 직접 검사한다. 얇은 선의 단절/소실, 출현·소멸, 계단, 잔상, 흐림을
구분한다. 이전 supersample spatial proxy를 같은 index에 대응시키되 temporal ground
truth로 부르지 않는다. ROI RGB error와 시간 차분은 보조 지표이며 카메라 motion을 포함한다.
CGVQM을 재실행한 결과로 주장하지 않는다. 미디어 생성/검증과 실제 재생 시청을 구분한다.

성능: 장면별 ⑨/새 구현/④의 순서를 교차하며300 warm-up, 4,800 frame×6회.
30s precondition, PNG/query/readback Off, mode마다 resource cleanup/history reset,
240-frame timeline 반복 시작마다 history reset. 기존 동일-binary smoke 완료 후 실행한다.
전체 AA(SMAA), spatial+선택, camera velocity, temporal resolve, WholeFrame,
WallFrame의 mean/median/p95/p99/stddev/slowest1% equivalent FPS를 보존한다.
변화율은 **동일 실행의 대응 run**을 분모로 계산한다. 6개 run 평균의 표준편차와
paired 변화율의 df5 Student t95% 구간은 기술 통계이며, 한 process의 반복을
서로 다른 실행 세션으로 해석하거나 다중 비교 보정을 했다고 주장하지 않는다.

전체 품질 문제가 남아 있으면 작은 보조 지표 개선을 최종 품질 성공으로 표현하지 않는다.
효과가 제한적이거나 비용이 큰 경우 기본 경로로 채택하지 않고 독립 ablation으로 보존한다.
