# 현재 픽셀별 luma 선택의 성능 최적화 판정

현재 선택 기준과 출력을 보존한 최적화로 Minecraft의 속도 손해를 크게 줄였다.
그러나 **두 장면 모두에서 원본 SMAA T2X-R보다 빠른 공통 구현을 확보하지 못했다.**
이번 결과는 선택적 temporal 가속 목표의 달성으로 보고하지 않는다. 후보 확장이나
다른 선택 기준으로 질문을 바꾸지 않으며, 검증한 DX11 구현 범위의 성능 한계로 기록한다.

## 최종 확인 수치

RTX 3060 Ti, Release x64, DX11, SMAA Ultra, 1920×1061, hidden, VSync Off.
Original 공간 SMAA, camera/depth reprojection, paired jitter와 spatial-frame history를 유지했다.
장면별 독립 프로세스에서 30초 미측정 렌더링 후 각 mode 300-frame warmup,
4,800-frame 측정을 5회 수행했다. 원본은 정/역 순서 모두 가운데 배치했다.
픽셀 선택률은 별도 240-frame 품질 경로에서 측정한 값이며 성능 측정 중 readback한 값이 아니다.

| 전체 SMAA GPU 시간 | Bistro | Minecraft |
|---|---:|---:|
| 원본 O-T2X-R | 0.210864 ms | 0.286205 ms |
| 기존 픽셀별 대비 선택 | 0.201864 ms (−4.268%) | 0.289489 ms (+1.147%) |
| 동일 선택, scalar weight | 0.211166 ms (+0.143%) | 0.286331 ms (+0.044%) |

괄호는 같은 실행의 원본 대비 변화다. ScalarWeight의 Minecraft temporal resolve는
기존 선택의 0.038740 ms에서 0.034973 ms로 **9.725% 감소**했다. 전체 SMAA는 기존 선택
대비 1.091% 감소했다. 그러나 원본 resolve 0.034786 ms보다는 평균 0.000187 ms 느렸고,
다섯 반복 모두 같은 방향이었다. 전체 SMAA의 원본 대비 차이는 반복별로 부호가 바뀌므로
평균 +0.044%를 확정적인 열세나 동등성 증명으로 해석하지 않는다. 가속 근거도 아니다.

Bistro에서 기존 선택은 읽기 생략의 이점이 있었으나 ScalarWeight는 이를 잃었다.
기존 선택 대비 전체 SMAA +4.608%, resolve +35.298%였다. 두 장면 평균 하나로 이 손해를
숨기거나 장면 이름에 따라 구현을 자동 전환하지 않는다. 기본값은 유지하고 새 코드는
명시적인 성능 대조 옵션으로 보존한다.

## 실제로 바꾼 부분

선택식은 `max(abs(ddx_fine(luma)), abs(ddy_fine(luma))) >= 0.01`로 동일하다.
추가 texture, pass, 다른 패스의 edge/metadata 접근은 없다.

기존 방식은 현재 색상에서 선택 여부를 판단한 뒤 비후보에서 반환한다. ScalarWeight는
velocity와 history를 전 픽셀에서 읽고, 원본 history weight를 비후보에서 0으로 만들어
한 번의 lerp로 출력한다. 컴파일 결과도 conditional texture path 대신 scalar weight
masking으로 바뀌었다. 이는 **같은 화면을 만드는 실행 비용 개선**이지 history fetch를
더 많이 생략한 결과가 아니다. DXBC는 실제 GPU stall/cache 계측을 대신하지 않는다.

두 장면에서 각각 11 mode×240 frame, 총 5,280 PNG를 검사했다. 원본·기존 선택·선택 mask는
이전 Locality 검증과 hash 불일치 0이었다. ScalarWeight와 기존 선택의 저장된 최종 PNG도
480 frame 전부 동일했다. 선택률은 Bistro 1.512189%, Minecraft 50.449044%로 유지됐다.
품질을 새로 개선한 것이 아니며, 기존 선택 방식의 고스팅·깜빡임 특성도 그대로다.
동일 출력 주장은 이 캡처 경로의 PNG 검증 범위이며 임의 장면의 모든 부동소수점 중간값에
대한 증명은 아니다.

## 비용을 줄이려 시도한 항목과 판정

| 항목 | 확인한 결과 | 판정 |
|---|---|---|
| RGBA 선택을 scalar weight masking으로 변경 | 동일 출력, Minecraft resolve 약 9.7% 감소, Bistro 이점 상실 | 개선 후보로 보존하되 공통 기본값으로 채택하지 않음 |
| max 비교를 any 비교로 표현 | 같은 선택/출력, 새 가속 확인 안 됨 | 미채택 |
| 같은 0.01 threshold를 셰이더 상수로 고정 | cbuffer 참조 제거, branch/scalar 모두 확정 이점 없음 | 미채택 |
| history weight 산술 재배열 | Minecraft 8 frame에서 총 9 pixel이 채널 1/255 변화, 속도 이점 없음 | 동일 출력 최적화에서 제외 |
| point history를 정수 좌표 Load로 변경 | Minecraft 최대 채널 차이 156/255, Bistro 100/255 | sampler 정밀도와 동등하지 않아 제외 |
| /O1, /O2, /O3 | 기존 선택/scalar/scalar 고정 threshold의 명령열 각각 동일 | 중복 GPU 측정 생략 |
| scalar weight에 선택값 0/1 곱하기 | masking보다 multiply 명령 하나 추가 | 짧은 masking 후보를 우선 검증; 이 후보의 GPU 시간은 미측정 |

이전 [Execution](../Temporal-Contrast-Execution/report.md)과
[Dependency](../Temporal-Contrast-Dependency/report.md) 검증에서 소스 순서 변경,
prefetch 시도, early-return/structured/flatten, current/velocity Load를 이미 조사했다.
동일 DXBC인 소스 재배치를 새 최적화로 반복하지 않았다. 기존 flatten은 이번 비교에서
대조군으로만 사용했다.

## 왜 선택 픽셀 수만큼 빨라지지 않았는가

현재 경로에는 별도 후보 pass나 cross-pass mask 전송이 없다. 추가 비용은 temporal PS의
대비 계산, 선택 판단, 조건부 접근과 그에 따른 실행 의존 관계에 있다. 이들을 각각의
하드웨어 원인별 시간으로 완전히 분해한 것은 아니다.

이전 [동일 선택률 배치 대조](../Temporal-Contrast-Locality/report.md)에서는 같은 50% 선택과
같은 branch 셰이더라도 선택 위치의 배치에 따라 resolve 시간이 달라졌다. 따라서 픽셀
50% 생략이 GPU 시간 50% 절감이라는 전제는 실제 결과와 맞지 않는다. 이번에는 전 픽셀을
읽는 ScalarWeight가 Minecraft에서 오히려 빨랐다. 원본의 작은 temporal 작업량에 선택
비용을 더한 뒤 일부를 생략하는 방식에서는, 생략량보다 실행 방식이 더 중요할 수 있다는
근거다. 이를 특정 warp divergence 비율이나 메모리 병목의 확정 측정으로 표현하지 않는다.

## 결론의 범위와 재검토 조건

현재 GPU·두 장면·동일 선택식·동일 출력·단일 temporal PS 조건에서 조사한 구현들은
**원본보다 일관되게 빠르다는 목표를 만족하지 못했다.** 기존 선택의 Minecraft 손해를
대부분 줄이는 것은 가능했으므로, 최적화 자체가 불가능했다고 결론내리지 않는다.
모든 GPU와 모든 가능한 셰이더에 대한 수학적 불가능 증명도 아니다.

남은 hardware stall/cache/활성 lane 자료는 프로파일러 권한 제한으로 확보하지 못했다.
GPU counter 자료나 실제 명령열을 더 줄이는 별개의 가설이 생기면 같은 선택/출력 조건에서
재검토할 수 있다. 이 자료 없이 추가 추측을 확정 원인으로 삼거나, 이미 실패한 문법 변경을
계속 반복하지 않는다. 후보 확장·새 품질 기능·다른 선택식은 이 성능 문제의 해결로 세지 않는다.

새 방식은 자동 채택하지 않았다. `ABL-ScalarWeight-001-R`은 기존 선택과 원본을 비교할 수
있는 명시적인 대조 경로로 남는다. 현재 연구 질문에 대한 부정 결과와 부분 개선을 함께
보존하며 최종 8-case 논문 결과로 혼용하지 않는다.

## 근거와 재현 자료

- [방법과 Microsoft 공식 근거](method.md)
- [10-mode 비교·품질 동일성](report.md), [원시 분석 통계 및 실행 hash](results.json)
- [예열 후 5회 확인](focused-report.md), [반복별 통계 및 실행 hash](focused-results.json)
- 셰이더/광범위 비교 구현: `419eef42266d105220fe3319c23ca7de6b25f8d2`
- 예열 후 확인 도구: `ce8053f` (셰이더와 binding은 위 구현과 불변)
- Release x64 빌드, 원본 8 shader variant 불변, 새 14 variant 컴파일 검사 통과.
- 이번 최종 실행 10개(광범위 smoke/capture/benchmark 6개, 후속 smoke/benchmark 4개)는
  모두 완성된 PASS 보고서와 정상 종료를 확인했다. 자동 실행은 각 명령 전후 잔류 CMAA2
  프로세스가 없음을 검사했다. raw capture/EXE/AutoBench 산출물은 Git에 넣지 않는다.
