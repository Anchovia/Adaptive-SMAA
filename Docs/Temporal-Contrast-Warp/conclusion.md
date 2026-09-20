# Warp 단위 실행 최적화 판정

**새 warp 방식은 채택하지 않는다.** 같은 선택과 출력을 유지했지만 두 장면 모두에서
기존 픽셀별 분기보다 temporal resolve가 느렸다. Bistro에서는 원본 T2X-R보다 빠르지만
기존 선택보다 이점이 줄었고, Minecraft에서는 원본 대비 손해가 더 커졌다.

이번 작업의 우선 목표는 품질 변경 없이 속도 하락을 거의 없애거나 가속하는 것이었다.
품질을 새로 개선하는 기능은 추가하지 않았다. 이전 방법의 '실패'도 모든 연구 가치의
부정이 아니라, 두 장면에서 원본보다 빠른 공통 구현을 확보하지 못했다는 범위로 해석한다.

## 같은 실행 안에서 비교한 결과

아래는 전체 SMAA GPU 시간이다. 30초 미측정 렌더링, 각 mode 300 warmup,
4,800 frame×5회 결과이며 괄호는 같은 실행의 원본 대비 변화다.

| 방식 | Bistro | Minecraft |
|---|---:|---:|
| 원본 T2X-R | 0.210667 ms | 0.281753 ms |
| 기존 픽셀별 대비 분기 | 0.201573 ms (−4.317%) | 0.285382 ms (+1.288%) |
| 혼합 비중만 선택하는 ScalarWeight | 0.211006 ms (+0.161%) | 0.282080 ms (+0.116%) |
| 새 NvWarp 실행 | 0.202584 ms (−3.837%) | 0.286309 ms (+1.617%) |

NvWarp−기존 분기의 resolve 차이는 Bistro 약 +0.000539 ms,
Minecraft 약 +0.000686 ms였다. **각 장면 5회 모두 resolve가 느려졌다.**
전체 SMAA 평균도 각각 +0.502%, +0.325%였으나 Minecraft의 한 반복에서는 부호가 달랐다.
불변 spatial 시간 변동을 알고리즘 효과로 해석하지 않는다. 각 반복과 분포는
[측정 보고서](report.md)와 [분석 통계](results.json)에 보존했다.

ScalarWeight는 이번에도 원본과 전체 시간이 가까웠다. 이전 예열 후 확인의
Bistro +0.143% / Minecraft +0.044%와 이번 +0.161% / +0.116%는 서로 다른 실행의
대응 기준선 대비 값이다. 절대 시간을 서로 빼서 최적화 효과로 보고하지 않는다.
작은 차이는 실행 변동을 포함하므로 정확한 동등성이나 항상 빠르다는 주장은 하지 않는다.
현재 공통 실행 후보 중 원본에 가장 가까운 방식은 ScalarWeight이며, Bistro의 기존
분기 방식이 제공한 약 4% 절약까지 보존하는 공통 해법은 확보하지 못했다.

## 구현 정확성

- 공식 NVIDIA SDK의 NvAny와 thread-local shader extension 설정을 사용했다.
  SDK는 commit `70d337db9186e968eab622f7e786de7e437faf3d`에 고정했고 원본 파일 hash와
  MIT 라이선스를 보존했다. `.lib`는 공식 SDK 의존성이며 연구 빌드 산출물이 아니다.
- 독립 GPU probe의 129×17 전체 비선택/전체 선택/checkerboard/단일 선택 검사는 오류 0이었다.
  한 픽셀 선택의 vote coverage는 32픽셀이었고, 모든 비선택 상태에서는 0이었다.
  slot 설정·해제와 이후 일반 pixel shader 생성도 통과했다.
- 원본 SMAA shader 8 variant가 baseline과 byte-exact였다. NVAPI resolve/mask 각각
  reprojection Off/On 4 variant도 컴파일했다. 실제 장면의 runtime 검증은 On에 한정한다.
- 두 장면 각 6 mode×240 frame, 총 2,880 PNG를 검사했다. 이전 원본/기존 선택/scalar/mask와
  hash 불일치 0, 새 NvWarp와 기존 선택의 최종 화면 불일치 0이었다.
- 원래 선택률은 Bistro 1.512189%, Minecraft 50.449044%로 보존됐다. 별도 debug PS의
  NvAny coverage는 4.421425%, 68.907796%였다. 이 값은 해당 debug PS의 실행 범위이며
  별도 resolve의 실제 lane 배치나 성능 측정의 hardware counter라고 표현하지 않는다.
- Release x64 빌드와 장면별 smoke/capture/benchmark 6개 독립 실행 모두 정상 종료 및
  완성된 PASS CSV를 확인했다. 성능 실행 중 이미지 분석과 캡처는 없었다.

## 이번 가설이 해결하지 못한 비용

새 방식은 선택 픽셀을 늘리지 않고, 한 warp 안에 선택 픽셀이 있으면 함께 history를 읽되
비선택 lane의 혼합 비중을 0으로 유지한다. 출력은 같지만 mixed warp에서 기존 분기보다
많은 lane이 history/weight 계산을 실행할 수 있다. NvAny 판정과 null UAV slot 설정도 있다.
측정 차이는 이 실행 구조 전체의 효과이며 순수 vote 명령 하나의 시간은 아니다.

HLSL과 생성 DXBC에서는 여전히 current 읽기→luma/derivative→vote→조건부 velocity/history
순서의 의존 관계가 남는다. 명시적인 warp 분기는 이를 제거하지 않는다. 원래 픽셀별 분기도
GPU에서 이미 묶음으로 실행되므로, warp API를 추가하면 자동으로 병렬 효율이 높아진다고
가정할 수 없다. 이번 결과는 그 추가가 성능 개선으로 이어지지 않은 사례다.

실제 GPU ISA·stall·cache counter는 확보하지 못했으므로 특정 하드웨어 원인의 기여율을
확정하지 않는다. 다른 GPU·장면·모든 구현에 대한 불가능 증명도 아니다. NvWarp는
NVIDIA 전용의 부정 결과 대조 옵션으로 남기고 기본값은 변경하지 않는다.

## 재현과 현재 판정

[방법 및 공식 근거](method.md), [probe 결과](probe-result.txt),
[셰이더 검증](shader-validation.json), [전체 결과](results.json)를 함께 사용한다.
구현 commit은 `e156bd4`, upstream byte 보존 수정은 `7658f75`다.
실행 파일 hash와 여섯 실행의 보고서 hash는 results.json에 기록돼 있다.

현재 속도만의 판정은 다음과 같다. **GPU warp 묶음 최적화는 실패했고,
기존 ScalarWeight 방식은 선택 결과를 유지하면서 원본에 가까운 속도를 내는 후보로 남는다.**
후보 확장, 새 선택식 또는 품질 기능의 효과를 이 실행 비용 문제의 해결로 혼용하지 않는다.
