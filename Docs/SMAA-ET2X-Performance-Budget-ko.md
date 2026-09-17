# Standard T2X-R 손익분기 성능 감사

2026-09-17 · 기준 구현 `322ad90` · `research/et2x-performance-budget`

## 판정

현재 document core를 Standard T2X-R보다 빠르게 만들려면 전체 AA 비용을 Bistro
18.77%, Minecraft 23.33% 줄여야 한다. 복사 두 번을 없애거나 candidate resolve만
빠르게 하는 단일 변경으로 해결될 것으로 예상할 근거는 부족하다. 후보 생성과
spatial/temporal 출력의 데이터 전달 구조를 함께 다루는 prototype이 필요하다.

이번 작업은 기존 원시 측정의 비용 감사다. 렌더러 변경, 새 GPU 실행, 새 품질 측정은
하지 않았다. 아래 가정값은 실측 개선이나 달성 가능한 하한이 아니다. 나머지 비용이
고정되고 제거한 작업의 대체 비용이 0이라는 산술 가정이며 GPU cache/scheduling과
pass 재구성에 따른 상호작용을 예측하지 않는다. 따라서 알고리즘의 불가능 증명도 아니다.

## 자료와 검증

- 9월 15일 Standard / DocCandidate+DocKernel / SourceCandidate+DocKernel의 동일 실행
  자료 중 앞의 두 모드만 사용했다. Original SMAA, camera/depth R, expansion None,
  rigid velocity Off, previous-depth rejection Off다.
- RTX 3060 Ti, DX11 Release x64, 1920×1017, visible window, 300 warm-up,
  4,800 frame×3 repeats, candidate readback Off다.
- Standard는 원본 paired jitter/subsample, point sampling, adaptive weight와 spatial
  history를 유지한다. ET2X와의 차이는 coverage만의 효과가 아니라 실제 구현 전체 비교다.
- 두 scene CSV의 내부 PASS, scene, 표본 수, 반복 수, readback 및 기록된 JSON의 모든
  사용 timer 평균을 대조했다. parent와 child timer의 차이도 잔여값으로 보존했다.
- 8월 matched-kernel 결과는 원시 CSV 4개와 기존 분석 JSON을 다시 대조했다. 9월 자료와
  실행 시점·경로가 달라 절대 시간을 서로 빼거나 합치지 않는다.
- 재계산 산출물: [budget.md](ET2X-Performance-Budget-20260917/budget.md),
  [검증 및 SHA-256 기록](ET2X-Performance-Budget-20260917/budget.json).

## 1. 필요한 절감량

| 장면 | Standard | 현재 ET2X | 초과 시간 | ET2X에서 줄여야 할 비율 |
|---|---:|---:|---:|---:|
| Bistro | 0.277314 ms | 0.341403 ms | 0.064089 ms | 18.77% |
| Minecraft | 0.293613 ms | 0.382936 ms | 0.089323 ms | 23.33% |

Standard 대비 느린 비율(+23.11%/+30.42%)과 현재 ET2X에서 줄여야 할 비율은 분모가
다르다. 논문의 합격 판정은 동일 공간 설정의 Standard 대비 전체 AA 시간과 WholeFrame,
품질을 함께 사용해야 한다. Adaptive 이득을 선택적 temporal의 이득으로 합산하지 않는다.

## 2. 초과 비용의 위치

| 구간의 ET2X−Standard 차이 | Bistro | Minecraft |
|---|---:|---:|
| 공간 처리 구간 | +0.014301 ms | +0.024627 ms |
| camera velocity | +0.000109 ms | −0.000093 ms |
| 추가 spatial→history / history→output 복사 | +0.047051 ms | +0.046670 ms |
| 후보 counter 초기화 / indirect args | +0.008336 ms | +0.007926 ms |
| temporal resolve | −0.009219 ms | +0.007089 ms |
| parent/child timer 잔여 차이 | +0.003511 ms | +0.003104 ms |
| 합계 | +0.064089 ms | +0.089323 ms |

공간 구간에는 integrated 후보식·compact뿐 아니라 jitter/subsample 등 경로 차이가
포함된다. 이 값을 후보 atomic의 단독 비용이라고 부르면 안 된다. 잔여 차이도 새
독립 GPU pass나 특정 병목으로 해석하지 않는다.

## 3. 단일 최적화의 조건부 예산

| 비용을 0으로 만드는 가정 | Bistro 예상 합계 / Standard 대비 | Minecraft 예상 합계 / Standard 대비 |
|---|---:|---:|
| 최종 output copy만 | 0.317497 ms / +14.49% | 0.359078 ms / +22.30% |
| 두 copy 모두 | 0.294352 ms / +6.14% | 0.336266 ms / +14.53% |
| 두 copy와 counter clear/args 모두 | 0.286016 ms / +3.14% | 0.328340 ms / +11.83% |
| candidate resolve 전체 | 0.313520 ms / +13.06% | 0.337963 ms / +15.10% |

현재 공간 구간과 velocity를 고정하면 Standard와 같아지기 위해 남는 예산은 Bistro
0.022809 ms, Minecraft 0.013438 ms다. 여기에 후보 준비, resolve, 전달 비용이 모두
들어가야 한다. 단순 threshold 조정이나 sampler 교체만으로 목표 달성을 약속할 수 없다.

## 4. 이미 수행한 실험을 다시 시작하지 않기

- 같은 document temporal 계산의 full-screen 대비 선택적 처리는 reprojection On에서
  Bistro 21.50%, Minecraft 13.75% 빨랐다. 선택적 처리의 절감 효과 자체는 이미 있다.
  비교 대상이 원본 Standard가 아니므로 이 비율을 Standard 대비 가속률로 쓰지 않는다.
- dual-output compute initialization은 출력 동일성을 유지했지만 기존 two-copy보다
  On 조건에서 1.75%/3.98% 느렸다. 같은 구조의 재실험은 우선하지 않는다.
- full-screen early-exit mask compute도 기존 compact/indirect보다 느렸다.
  [실행 구조 결과](SMAA-Candidate-Execution-Structure-Results-ko.md)를 따른다.
- axial luma 재사용은 이미 적용됐다. 효과는 약 0.24~2.11%였고 장면에 의존했다.
  [전후 교차 측정](SMAA-Luma-Reuse-Paired-Performance-Results-ko.md)을 따른다.

## 5. 코드에서 확인한 구조 제약

`vaSMAAWrapperDX11.cpp::ExecuteTSCMAAInspiredResolve`는 current spatial을 별도
texture로 보존하고 output history를 복사로 초기화한 뒤 후보를 덮어쓴다. 비후보는
현재 spatial을 유지하고 최종 history를 화면 destination으로 복사한다.

`SMAAWrapper.hlsl::TSCMAAVarianceClip`은 후보 주변의 **SMAA 처리 후** 3×3 색을 읽는다.
따라서 current spatial과 output history를 단순히 같은 texture로 합치면 다른 thread가
이미 temporal 처리한 이웃을 읽는 경쟁이 생길 수 있다. DX11에서 같은 subresource를
SRV/UAV로 동시에 바인딩하는 것도 기존 방식의 안전한 대체가 아니다.

`SMAA.cpp::neighborhoodBlendingPass`는 현재 단일 RTV 출력이다. 이 공간 출력과
history 초기화를 MRT로 함께 기록하는 설계는 가능성 검토 대상이지만, 추가 쓰기
대역폭이 생기므로 copy 한 번의 시간이 그대로 사라진다고 계산하지 않는다.

`CMAA2Sample.cpp::DrawScene`은 scratch texture에 최종 AA 출력이 있다는 계약을 사용한다.
history를 후속 처리의 입력으로 직접 전달하면 output copy를 줄일 수 있으나, 후속
렌더링·캡처가 history를 수정하지 않는 소유권 분리가 먼저 필요하다. 단순 pointer
교환만으로 안전성이 보장되지는 않는다.

## 6. 다음 구현의 좁은 범위와 중단 기준

첫 prototype은 기존 수식·history semantics를 유지한 채 **공간 출력에서 history 초기화를
함께 수행하는 MRT 경로**와 **최종 history를 읽기 전용 출력으로 전달하는 경로**를 각각
분리해서 검증하는 것이다. 기존 실패한 compute dual-output initialization과 다른 경로다.
이 둘은 아직 구현/성능 검증되지 않았으며, 성공해도 위 예산상 단독으로 최종 목표를
달성한다고 기대해서는 안 된다.

검증 순서는 다음과 같다.

1. 각 변경을 default-Off 옵션으로 분리하고 first-frame/resize/camera-cut/history
   feedback과 최종 출력 hash를 확인한다. 같은 색 공간·양자화 순서를 보존한다.
2. Standard / 기존 ET2X / 변경 ET2X를 동일 프로세스의 교차 순서로 짧게 측정한다.
   두 장면에서 절감이 반복되지 않으면 해당 경로를 중단한다.
3. 후보 준비까지 포함한 남은 비용을 다시 계산한다. 복사 절감만으로 통과했다고
   발표하지 않고 Standard보다 느린 잔여 구간을 명시한다.
4. 성능 유망 경로에만 300/4,800×3 정식 반복과 품질 검증을 수행한다.

MRT/출력 전달이 유효하지 않거나 남은 비용을 줄일 수 없다면 neighborhood spatial과
temporal의 더 큰 통합을 검토한다. 다만 현 3×3 spatial clipping을 그대로 재계산하면
중복 spatial 작업이 생기며, AA 전 색으로 clipping 입력을 바꾸면 알고리즘과 품질이
달라진다. 이 변경은 별도 방법으로 표시해야 하며 몰래 TSCMAA-equivalent 최적화로
대체하지 않는다. Standard sampler/weight로 단순화하는 것도 독립 품질 ablation이다.

깊이 rejection 튜닝, 후보 확장 확대와 최종 8-case 재측정은 성능 경로의 가능성을
확인한 뒤 진행한다. 기존 결과는 보존하되 현재 연구의 우선순위를 성능 손익분기로 옮긴다.

## 재현

```powershell
python Tools/SMAA/analyze_et2x_performance_budget.py `
  --matched D:/SMAA-Research-Data/AutoBench/20260828_ET2XPipelineOptimizationAnalysis/matched_kernel_optimization.json `
  --output Docs/ET2X-Performance-Budget-20260917
python Tools/SMAA/test_et2x_performance_budget.py
```

분석기는 기존 CSV와 기록 JSON 불일치, 불완전 표본, 실패한 실행, 중복 timer,
유한하지 않은 수치를 거부한다. 역사적 입력 hash를 결과 JSON에 남긴다. 원시 AutoBench
자료를 Git에 새로 추가하지 않고 기존 자료를 참조한다.

이번 실행에서 두 장면의 baseline 대조와 matched 원시 CSV 4개 대조가 PASS했다.
정상 입력 및 sample 부족/수치 불일치/NaN/장면 불일치/내부 FAIL/중복 timer의
7개 분석기 검증도 PASS했다. 렌더러를 수정하지 않아 Release 재빌드나 GPU 회귀 검사를
반복하지 않았다. 측정 앱 실행 없이 완료했고 종료 시 CMAA2 프로세스는 0개였다.
