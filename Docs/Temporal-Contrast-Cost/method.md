# 픽셀별 luma 선택을 보존한 실행 비용 최적화

범위는 현재 temporal PS 안의 luma 선택 비용 개선이다. 후보 확장, 새 판단 단위, 다른 패스의
metadata, 추가 pass 및 새 품질 기능을 도입하지 않는다. Original SMAA Ultra, camera/depth R,
paired jitter, spatial-frame history 및 기존 0.01 선택 threshold를 유지한다.
최종 8-case가 아닌 동일 선택 구현 최적화 검증이다.

## 검토 대상

| ID 축약 | 변경 | 검증할 제한 |
|---|---|---|
| 원본/기존 선택 | O-T2X-R / ABL-Contrast-001-R | 기준선 유지 |
| Flatten | 기존 실행 대조군 재사용 | 전 픽셀 texture fetch 후 RGBA 선택 |
| ScalarWeight | 기존 weight를 비후보에서 0으로 만들고 한 번 lerp | 동일 선택/출력, 전 픽셀 fetch는 유지 |
| ScalarReassociated | 위 방식의 weight 산술 정리 | FP 반올림 차이 별도 기록 |
| BranchReassociated | 기존 early return에서 weight 산술만 정리 | 선택과 fetch 생략 보존, FP 차이 검사 |
| HistoryLoad | 기존 point/clamp history sampling을 정수 좌표 Load로 구현 | fractional UV와 sampler 정밀도 차이 검사 |
| SelectorAny | max(abs(dx),abs(dy)) 비교를 any(abs(float2(dx,dy)) 비교로 표현 | 유한 RGB 입력에서 같은 논리식 |
| FixedThreshold | 같은 0.01을 상수로 specialize | 값은 같고 cbuffer 참조만 제거 |
| ScalarFixedThreshold | ScalarWeight에 같은 상수 specialization | 동일 출력과 비용 확인 |

모든 선택식은 같은 RGB 계수와 fine derivative를 사용한다. Scalar 계열은 history 접근을
생략하는 방식이 아니다. 픽셀별 temporal 적용 결과를 유지하면서 실행 비용을 줄이는 대조다.
임계값 specialization은 0.01 이외의 설정에서 각각 원래 branch/scalar 경로로 fallback한다.

기존 weight `0.5*max(1-sqrt(abs(a²-b²)/5)*30,0)`는 실수 산술에서
`max(0.5-sqrt(45*abs(a²-b²)),0)`와 같다. GPU FP 연산 재배치로 발생하는 차이는 숨기지 않는다.
더 싼 코드라는 이유만으로 동일 출력이라고 간주하지 않는다. History Load의 OOB는 좌표 clamp로
방지하지만 fractional sampling 정밀도는 실제 연속 프레임으로 따로 확인한다.

## 공식 근거

- [Microsoft HLSL lerp](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-lerp):
  혼합식과 scalar weight 의미.
- [Microsoft HLSL if](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if):
  branch/flatten 의미. 이전에 실패한 단순 문법 교체는 새 개선으로 세지 않는다.
- [Microsoft Texture.Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load):
  정수 texel 좌표이며 sampler clamp와 같지 않다.
- [Microsoft compiler flags](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/d3dcompile-constants):
  Release 최적화 설정을 확인하며 bytecode가 같은 변경은 GPU 최적화로 주장하지 않는다.

## 절차와 판정

1. FXC /O3: 원본 spatial/resolve 8 variant가 baseline과 동일함을 확인한다. 새 shader는 R Off/On
   14 variant에서 derivative, texture 명령 및 실제 branch 구조를 검사한다. DXBC는 GPU cycle 수가 아니다.
2. Release x64, DX11, RTX 3060 Ti, 1920×1061, hidden, VSync Off. clean runner의 독립 process를 쓴다.
3. 같은 60 Hz 경로(60 정지+120 이동+60 정지)의 240-frame capture. 새 7개 후보와 3개 대조,
   기존 mask를 저장한다. 기존 원본/선택/mask는 Locality gate와 hash bridge한다.
4. 각 후보의 RGB 변경 픽셀 수, 최대 오차, MAE 및 비후보 변경을 기록한다. 비동일 출력 경로는
   동일 품질 최적화로 승인하지 않는다. 그 timing은 원인 분석용으로만 구분한다.
5. 성능은 PNG/영상 분석과 분리해 300 warmup, 4,800 frame×3회 정/역/정. resolve뿐 아니라
   전체 SMAA와 불변 spatial control, 반복 변동을 함께 비교한다.
6. 작은 우위는 반복 검증 전 채택하지 않는다. 양쪽 장면의 효과와 원본 대비 목표를 구분한다.
   개선 후보가 실패해도 곧바로 보편적 불가능이라고 결론내리지 않고 검토 범위/남은 가설을 기록한다.

재현: `validate_temporal_cost_shaders.py`, `run_temporal_cost.ps1 -Phase Smoke|Capture|Benchmark
-Scene bistro|minecraft -Receipt tmp/temporal-cost-final-runs.json`, `analyze_temporal_cost.py`.
초기 smoke `20260921_003723`은 specialization 추가 전 예비 빌드이며 최종 paired 결과와 분리한다.
기본값은 gate 통과 전 변경하지 않는다.
