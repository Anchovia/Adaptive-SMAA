# SMAA Integrated Candidate Removal 반복 성능 결과

## 1. 목적

SMAA 1차 edge pass에 temporal candidate 생성을 통합한 뒤 non-dominant removal을
높이면 실제 GPU 시간이 줄어드는지 확인했다. 앞선 품질 gate를 통과한 `0.50`, `0.65`,
`0.70`, `0.75`를 `O-ET2X`와 `O-ET2X-R`에 각각 적용해 총 8개 configuration을
측정했다.

이 실험은 Original 공간 SMAA의 document-based candidate 파라미터 성능 gate다. 최종
Original/Adaptive 8-case 결과가 아니며, Intel의 공개되지 않은 원본 candidate 식에 대한
최적화 결과도 아니다.

## 2. 구현한 측정 경로

새 명령:

```powershell
CMAA2.exe -smaaIntegratedCandidateRemovalPerformanceSmoke <bistro|minecraft> 1 30 60 1
CMAA2.exe -smaaIntegratedCandidateRemovalPerformanceBenchmark <bistro|minecraft> 1 300 4800 3
```

비교 configuration:

```text
O-ET2X   removal 0.50 / 0.65 / 0.70 / 0.75
O-ET2X-R removal 0.50 / 0.65 / 0.70 / 0.75
```

모든 configuration은 다음을 공유한다.

- Original SMAA, Ultra preset
- `SMAAFirstPassIntegratedCandidates`
- `IntelFamilyNonDominant`, edge threshold `1/22`
- candidate expansion None
- deliberate projection jitter Off
- Catmull-Rom 5-tap history sampling
- YCoCg variance clipping
- history weight `0.8`
- DirectX 11, 1920×1017, VSync Off, fixed 60 Hz
- UI hidden, PNG capture Off

`O-ET2X-R`만 camera/depth reprojection을 사용한다. object motion vector는 연결하지
않았다. 반복마다 mode 순서를 정방향/역방향으로 교차했고, 본 timing에서는 candidate
readback을 껐다.

## 3. Engineering smoke와 후보 특성화

Release x64 빌드 후 장면별 readback-On 30-frame warm-up + 60-frame smoke를 독립
clean process로 실행했다.

| Scene | Removal | Candidate/base |
|---|---:|---:|
| Bistro | 0.50 | 67.0171% |
| Bistro | 0.65 | 62.0433% |
| Bistro | 0.70 | 60.7840% |
| Bistro | 0.75 | 58.8249% |
| Minecraft | 0.50 | 88.9916% |
| Minecraft | 0.65 | 85.8067% |
| Minecraft | 0.70 | 84.8146% |
| Minecraft | 0.75 | 82.8004% |

- 여덟 configuration 모두 timestamp 60/60과 내부 validation PASS
- removal 증가에 따라 candidate/base 단조 감소
- 모든 configuration에서 candidate count와 process count 일치
- 같은 removal의 reprojection Off/On 후보 수 정확히 일치
- 실행 전후 잔류 `CMAA2.exe` 0

이 동적 flythrough 구간의 후보 비율은 이전 고정 pose sweep과 다르다. 후보 비율이
장면뿐 아니라 camera path와 프레임 구간에도 의존한다는 추가 근거이며, 약 50%라는
목표만으로 값을 선택하지 않는다.

## 4. 본 측정 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- CPU: AMD Ryzen 5 5600
- visible window, Release x64, DirectX 11, SMAA Ultra
- 장면별 별도 clean process
- mode별 300-frame warm-up
- mode별 4,800-frame 측정 × 3회
- mode당 timing 표본 14,400개, run mean 3개
- candidate readback Off, PNG Off
- 내부 benchmark validation PASS
- 두 장면 종료 후 잔류 `CMAA2.exe` 0

## 5. Bistro 저대비 장면

| Mode | Wall FPS | WholeFrame | SMAA | Spatial | Resolve | Velocity | SMAA run σ |
|---|---:|---:|---:|---:|---:|---:|---:|
| `O-ET2X 0.50` | 313.453 | 3.148629 ms | 0.361753 ms | 0.251344 ms | 0.023918 ms | - | 0.006000 ms |
| `O-ET2X 0.65` | 313.024 | 3.151829 ms | 0.361626 ms | 0.251846 ms | 0.023206 ms | - | 0.003746 ms |
| `O-ET2X 0.70` | 313.012 | 3.141799 ms | 0.361682 ms | 0.251958 ms | 0.022937 ms | - | 0.002905 ms |
| `O-ET2X 0.75` | 312.321 | 3.160531 ms | 0.360513 ms | 0.251020 ms | 0.022598 ms | - | 0.001692 ms |
| `O-ET2X-R 0.50` | 308.772 | 3.198508 ms | 0.398299 ms | 0.259372 ms | 0.027200 ms | 0.023799 ms | 0.002290 ms |
| `O-ET2X-R 0.65` | 309.562 | 3.192372 ms | 0.398887 ms | 0.260613 ms | 0.026544 ms | 0.023844 ms | 0.000629 ms |
| `O-ET2X-R 0.70` | 308.956 | 3.200353 ms | 0.398408 ms | 0.260447 ms | 0.026056 ms | 0.023852 ms | 0.000534 ms |
| `O-ET2X-R 0.75` | 309.311 | 3.196808 ms | 0.397560 ms | 0.260045 ms | 0.025731 ms | 0.023849 ms | 0.000137 ms |

`0.50` 대비:

| Reprojection | Removal | Resolve | SMAA total | WholeFrame |
|---|---:|---:|---:|---:|
| Off | 0.70 | -4.102% | -0.020% | -0.217% |
| Off | 0.75 | -5.519% | -0.343% | +0.378% |
| On | 0.70 | -4.206% | +0.027% | +0.058% |
| On | 0.75 | -5.401% | -0.186% | -0.053% |

Resolve 감소는 run 변동보다 컸지만 SMAA total과 WholeFrame 변화는 결합 run 표준편차보다
작았다. Bistro에서는 removal 증가가 전체 성능 개선으로 이어졌다고 볼 수 없다.

## 6. Minecraft 고대비 장면

| Mode | Wall FPS | WholeFrame | SMAA | Spatial | Resolve | Velocity | SMAA run σ |
|---|---:|---:|---:|---:|---:|---:|---:|
| `O-ET2X 0.50` | 653.671 | 1.486626 ms | 0.438705 ms | 0.315575 ms | 0.038045 ms | - | 0.003684 ms |
| `O-ET2X 0.65` | 656.013 | 1.487043 ms | 0.436275 ms | 0.314448 ms | 0.036649 ms | - | 0.002988 ms |
| `O-ET2X 0.70` | 654.615 | 1.486491 ms | 0.435966 ms | 0.314317 ms | 0.036335 ms | - | 0.002056 ms |
| `O-ET2X 0.75` | 655.425 | 1.481933 ms | 0.434622 ms | 0.313457 ms | 0.035777 ms | - | 0.001778 ms |
| `O-ET2X-R 0.50` | 633.493 | 1.536543 ms | 0.478963 ms | 0.325275 ms | 0.044509 ms | 0.023198 ms | 0.001561 ms |
| `O-ET2X-R 0.65` | 634.684 | 1.529334 ms | 0.476041 ms | 0.323996 ms | 0.042870 ms | 0.023217 ms | 0.001169 ms |
| `O-ET2X-R 0.70` | 634.866 | 1.535012 ms | 0.475052 ms | 0.323577 ms | 0.042306 ms | 0.023198 ms | 0.000983 ms |
| `O-ET2X-R 0.75` | 635.645 | 1.537108 ms | 0.473195 ms | 0.322494 ms | 0.041591 ms | 0.023194 ms | 0.000744 ms |

`0.50` 대비:

| Reprojection | Removal | Resolve | SMAA total | WholeFrame |
|---|---:|---:|---:|---:|
| Off | 0.70 | -4.495% | -0.624% | -0.009% |
| Off | 0.75 | -5.961% | -0.931% | -0.316% |
| On | 0.70 | -4.950% | -0.817% | -0.100% |
| On | 0.75 | -6.556% | -1.204% | +0.037% |

Minecraft의 `O-ET2X-R`에서는 `0.70/0.75` SMAA 감소가 결합 run 표준편차의 약
2.12배/3.34배였다. 이는 repeat 변동보다 큰 engineering signal이지만 3회 반복만으로
통계적 유의성을 단정하지 않는다. WholeFrame 변화는 여전히 작고 방향도 일관되지 않았다.

## 7. 종합 판정

### 확인된 효과

- removal을 높이면 두 장면과 reprojection Off/On 모두 candidate resolve 시간이
  일관되게 감소했다.
- `0.70`의 resolve 감소는 약 4.10~4.95%, `0.75`는 약 5.40~6.56%였다.
- Minecraft에서는 SMAA total도 최대 1.204% 감소했다.

### 확인되지 않은 효과

- WholeFrame 개선은 두 장면과 Off/On에서 방향이 일관되지 않았다.
- Wall FPS 차이도 작은 변동 범위였고 removal 증가에 따라 단조 개선되지 않았다.
- 따라서 현재 결과로 전체 frame 성능 향상을 주장할 수 없다.

### 파라미터 결정

- `0.75`는 가장 큰 resolve 절감을 보였지만 앞선 품질 gate에서 출력이 더 O-1X에
  가까워지고 temporal change가 더 증가했다.
- `0.70`은 두 고정-pose 장면에서 candidate/base가 약 50%였고 품질 artifact 없이
  resolve 절감도 재현돼 현재 robust 중심 후보를 유지한다.
- 그러나 기본 document profile의 `0.50`을 아직 코드에서 `0.70`으로 변경하지 않는다.
  전체 timeline 품질과 Standard control까지 포함한 matched 검증 뒤 최종 선택한다.

즉, removal tuning은 국소 candidate resolve 최적화에는 효과가 있지만 integrated
TSCMAA-inspired core 전체의 성능 문제를 단독으로 해결하지는 못한다.

## 8. 다음 작업

1. 전체 wide timeline에서 `0.50`, `0.70`과 품질 경계 `0.75`를 O-1X 및 Standard
   T2X control과 함께 캡처한다.
2. supersample spatial reference와 CGVQM-2, 연속 frame/temporal 지표로 `0.70`의
   temporal 손실이 허용 가능한지 확인한다.
3. 최종 removal을 고정한 뒤 fresh matched benchmark에서 Standard T2X와 integrated
   edge-selective T2X의 실제 overhead를 비교한다.
4. 위 gate 전에는 최종 8-case 기본값과 기존 formal 결과를 변경하지 않는다.

## 9. 산출물

- Bistro 본 측정: `D:/SMAA-Research-Data/AutoBench/20260828_012831`
- Minecraft 본 측정: `D:/SMAA-Research-Data/AutoBench/20260828_013600`
- Bistro readback smoke: `D:/SMAA-Research-Data/AutoBench/20260828_012713`
- Minecraft readback smoke: `D:/SMAA-Research-Data/AutoBench/20260828_014008`
- 분석기: `Tools/SMAA/analyze_integrated_candidate_removal_performance.py`
