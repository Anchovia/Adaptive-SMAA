# 수정 후 FilteredQuarter와 3×3 후보 확장 비교 결과

## 1. 목적

2026-08-27 구현 감사에서 `FilteredQuarter`가 복원된 quarter mask만 threshold해 원래
raw current-edge candidate 일부를 지우던 결함을 발견했다. GPU와 CPU mirror를 다음
불변조건으로 수정한 뒤, 기존 Filtered 열을 재사용하지 않고 San Miguel에서 다시
측정했다.

```text
finalCandidate = rawCandidate OR reconstructedQuarter >= 0.25
```

이번 gate의 질문은 다음 두 가지다.

1. 수정된 FilteredQuarter가 raw candidate를 실제로 모두 보존하는가
2. 정확한 3×3 max-filter보다 후보 수·품질·GPU 비용의 trade-off가 좋은가

최종 8-case는 변경하지 않았다. 비교 대상은 document profile과 Candidate-Jitter
profile 각각의 `None`, `Dilate3x3`, `FilteredQuarter`이며, 동일 pose가 확인된 기존
`ArmDualFilter` 결과는 참고 ablation으로만 결합했다.

## 2. 조건과 분류

- GPU: NVIDIA GeForce RTX 3060 Ti
- API: DirectX 11
- 해상도: 1920×1017
- 빌드: Release x64
- SMAA preset: Ultra
- VSync: Off
- 장면: San Miguel 2.1 low-poly textured cache
- 카메라: `yaw-fast-360`, profile frame 60~119
- 품질: mode당 60 frame, independent final capture 2회, mask capture 1회
- 성능: mode당 300-frame warm-up + 60-frame 측정 × 3회
- timing의 candidate readback: Off
- 후보 수 특성화: 별도 60-frame readback-On 실행
- 분류: engineering gate; 정식 4,800-frame 성능 또는 temporal ground truth가 아님

모든 CMAA2 명령은 clean runner의 독립 프로세스로 실행했고, 실행 전후 잔류
`CMAA2.exe`는 0개였다.

## 3. Correctness와 반복 결정성

- 두 profile × 60 frame에서 Filtered raw 후보 유실 최대값: **0 pixel**
- GPU 3×3 mask와 CPU exact max-filter mismatch: **0 pixel**
- Filtered GPU/CPU mirror 최대 mismatch: **0.010447%**
- 독립 반복 final PNG 360장:
  - SHA-256 mismatch: **0장**
  - 실제 불일치 픽셀: **0개**
  - 최대 채널 차이: **0**

Filtered의 소수 GPU/CPU mismatch는 R8_UNORM 양자화와 `0.25` threshold 바로 근처의
부동소수점 분류 차이로 기록한다. 따라서 CPU mirror와 bit-identical이라고 표현하지
않지만, expansion의 핵심 불변조건인 raw 후보 보존은 모든 측정 frame에서 통과했다.

## 4. 후보 coverage

아래 full-frame 배수는 readback-On 실행의 평균 후보 수를 평균 None 후보 수로 나눈
값이다.

| Profile | None 평균 후보 | 3×3 배수 | Filtered 배수 | Filtered vs 3×3 |
|---|---:|---:|---:|---:|
| Document | 203,328.033 | 2.364× | 2.036× | -13.897% |
| Candidate-Jitter | 203,340.683 | 2.364× | 2.036× | -13.897% |

얇은 의자·테이블 다리와 식생 가지가 보이는 화면 ROI `(0, 500, 1050, 1017)`, frame
0~9의 coverage는 다음과 같다.

| Profile | Raw | 3×3 | Filtered |
|---|---:|---:|---:|
| Document | 27.532% | 60.429% | 55.263% |
| Candidate-Jitter | 27.541% | 60.420% | 55.280% |

Filtered는 3×3보다 선택 후보가 약 14% 적지만 raw mask보다 충분히 넓은 영역을
추가한다.

## 5. Supersample spatial-reference 품질

Reference는 동일 pose를 2× 선형 해상도, frame당 3×3 subpixel grid와 8×MSAA로
렌더한 spatial-reference proxy다. Temporal ground truth나 path-traced 정답은 아니다.
RGB MAE는 낮을수록 reference에 가깝다.

### 5.1 Full frame 60개 평균

| Profile | None | 3×3 | Filtered | 3×3 vs None | Filtered vs None | Filtered vs 3×3 |
|---|---:|---:|---:|---:|---:|---:|
| Document | 2.391437 | 2.140196 | 2.144116 | -10.506% | -10.342% | +0.183% |
| Candidate-Jitter | 3.074070 | 2.702365 | 2.744453 | -12.092% | -10.722% | +1.557% |

### 5.2 얇은 실제 geometry ROI, frame 0~9

| Profile | None | 3×3 | Filtered | 3×3 vs None | Filtered vs None | Filtered vs 3×3 |
|---|---:|---:|---:|---:|---:|---:|
| Document | 5.791908 | 5.235016 | 5.247365 | -9.615% | -9.402% | +0.236% |
| Candidate-Jitter | 6.799291 | 5.816087 | 5.905017 | -14.460% | -13.152% | +1.529% |

두 expansion 모두 None보다 reference 오차를 줄여 current-edge 확장 가설을 지지했다.
그러나 수정된 Filtered도 3×3을 넘지는 못했고, Candidate-Jitter에서 차이가 더 컸다.

## 6. 시간 변화량 보조 지표

Adjacent-frame RGB MAE는 카메라 motion 자체를 포함하므로 절대 고스팅 점수가 아니다.
같은 경로에서 상대적인 화면 변화량만 기록한다.

| Profile | 3×3 full frame | Filtered full frame | Filtered 변화 | 3×3 thin ROI | Filtered thin ROI | Filtered 변화 |
|---|---:|---:|---:|---:|---:|---:|
| Document | 26.935528 | 26.965949 | +0.113% | 40.586494 | 40.691398 | +0.258% |
| Candidate-Jitter | 26.770701 | 26.811641 | +0.153% | 40.489421 | 40.579663 | +0.223% |

Filtered가 3×3보다 temporal variation을 낮췄다는 증거는 이번 구간에서 확인되지 않았다.

## 7. 반복 GPU 성능

| Profile | 3×3 mask | Filtered mask | Filtered mask 변화 | 3×3 SMAA | Filtered SMAA | Filtered SMAA 변화 |
|---|---:|---:|---:|---:|---:|---:|
| Document | 0.048287 ms | 0.068289 ms | +41.423% | 0.474419 ms | 0.496879 ms | +4.734% |
| Candidate-Jitter | 0.048151 ms | 0.068267 ms | +41.777% | 0.461198 ms | 0.485046 ms | +5.171% |

SMAA run-mean 표준편차는 3×3/Filtered에서 Document 0.001835/0.001014 ms,
Candidate-Jitter 0.000472/0.000363 ms였다. 두 profile 모두 Filtered와 3×3의 평균 차이가
이 반복 변동보다 훨씬 컸다. WholeFrame은 장면·OS 변동이 커 이번 gate의 선택 근거로
사용하지 않는다.

Filtered는 후보를 줄였지만 full→quarter downsample과 quarter→full bilinear
reconstruction의 두 pass 비용 때문에 3×3보다 빨라지지 않았다.

## 8. 판정

1. 수정된 FilteredQuarter는 raw candidate 보존과 독립 반복 결정성을 통과했다.
2. Filtered와 3×3 모두 San Miguel의 얇은 실제 geometry에서 None보다 reference 오차를
   줄였다.
3. 3×3은 full frame과 thin ROI 모두에서 Filtered보다 reference 오차와 adjacent-frame
   변화량이 작았다.
4. Filtered는 3×3보다 후보가 약 13.9% 적지만 mask 비용은 약 41.4~41.8%, SMAA total은
   약 4.7~5.2% 더 컸다.
5. 따라서 **현재 구현과 RTX 3060 Ti 조건에서는 3×3 dilation을 다음 연구 단계의 기본
   current-edge expansion으로 선택**한다.
6. 이는 3×3이 최종 알고리즘으로 확정됐다는 뜻은 아니다. Original/Adaptive 최종 8-case,
   object motion vector, depth disocclusion과 candidate-aware stabilization 실험에서 별도
   검증해야 한다.
7. FilteredQuarter와 ARM Dual Filter는 구현·실패 원인·장면 의존성을 보여주는 ablation으로
   보존하고, pass fusion 또는 타일 기반 최적화 전에는 formal 확대하지 않는다.
8. 5×5/7×7은 후보·비용 증가가 예상되고 3×3이 이미 우세하므로 계속 보류한다.

## 9. 산출물

- post-fix final capture: `D:/SMAA-Research-Data/AutoBench/20260827_080226`
- post-fix mask capture: `D:/SMAA-Research-Data/AutoBench/20260827_080557`
- independent repeat: `D:/SMAA-Research-Data/AutoBench/20260827_081045`
- correctness analysis: `D:/SMAA-Research-Data/AutoBench/20260827_080226/Analysis-FilteredQuarter-Postfix`
- 8-mode reference analysis: `D:/SMAA-Research-Data/AutoBench/20260827_080226/Analysis-Postfix-8Mode-Reference`
- thin ROI analysis: `D:/SMAA-Research-Data/AutoBench/20260827_080226/Analysis-Postfix-SanMiguel-Thin-ROI`
- supersample reference: `D:/SMAA-Research-Data/AutoBench/20260827_051339/SS_Reference`
- readback-Off repeated timing: `D:/SMAA-Research-Data/AutoBench/20260827_082205`
- readback-On characterization: `D:/SMAA-Research-Data/AutoBench/20260827_082334`
- performance analysis: `D:/SMAA-Research-Data/AutoBench/20260827_082205/Analysis-Postfix-Performance`

대용량 PNG와 AutoBench 원시 결과는 Git에 포함하지 않는다.

## 10. 다음 단계

후보 확장 비교는 이 gate에서 닫는다. 다음 우선순위는 새 브랜치에서 object motion vector
지원 가능성을 먼저 설계·감사하는 것이다. 현재 `-R` mode는 depth와 camera matrix로 만든
camera-motion reprojection만 지원하므로, 독립적으로 움직이는 물체의 정확한 history
좌표와 disocclusion을 해결하지 못한다. 설계가 확정된 뒤 3×3 expansion을 직교 toggle로
결합해 효과를 분리한다.
