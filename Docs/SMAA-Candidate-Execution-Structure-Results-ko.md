# ET2X Candidate 실행 구조 최적화 Gate

## 1. 목적

Integrated `O-ET2X`/`O-ET2X-R`의 가장 큰 잔여 성능 문제인 candidate 실행 구조를
분리해 검증했다. 기존 경로는 SMAA 1차 edge pass에서 선택한 좌표를 compact list에
기록하고 candidate 수로 indirect dispatch를 수행한다. 대안 경로는 같은 1차 pass가 쓴
full-resolution R8 candidate mask를 full-screen compute가 읽고 비후보 thread를 즉시
종료한다.

이 비교는 Intel 공식 TSCMAA의 대체 구현을 주장하기 위한 것이 아니다. 공개 문서에
부합하는 기존 compact/indirect 구조가 현재 SMAA adaptation과 RTX 3060 Ti에서 실제로
손익분기점을 넘는지 확인하기 위한 default-Off 실행 구조 ablation이다.

## 2. 비교 경로

### `CompactIndirect` — 기존 기본 경로

```text
SMAA first-pass candidate selection
→ candidate counter atomic + packed coordinate list
→ dispatch args 생성
→ DispatchIndirect(candidate threads)
```

### `DirectMaskedFullScreen` — 이번 실험 경로

```text
SMAA first-pass candidate selection
→ full-resolution R8 candidate mask
→ full-screen 8×8 compute dispatch
→ mask가 0이면 즉시 return
→ candidate pixel만 동일 temporal kernel 실행
```

두 경로에서 다음 항목은 동일하게 유지했다.

- Original SMAA 1X spatial input
- SMAA 1차 edge pass의 `IntelFamilyNonDominant` candidate 식
- edge threshold `1/22`, removal `0.5`, expansion `None`
- projection jitter Off
- Catmull-Rom 5-tap history sampling
- YCoCg variance clipping
- history weight `0.8`
- spatial→history와 history→destination copy
- reprojection Off/On의 camera/depth 의미

따라서 이번 비교에서 바뀐 독립 변수는 candidate scheduling 방식뿐이다.

## 3. 구현 및 원본 보존 경계

- 옵션: `-smaaTemporalDirectMaskedResolve 0|1`
- 성능 gate:
  - `-smaaCandidateExecutionPerformanceSmoke`
  - `-smaaCandidateExecutionPerformanceBenchmark`
- 기본값은 `0`, 즉 기존 `CompactIndirect`다.
- direct path는 integrated source, expansion None, forced-count Off에서만 활성화된다.
- Standard T2X, SMAA 1X, Adaptive spatial path와 기존 8-case 기본 설정은 변경하지 않았다.
- direct path와 dual-output 최적화는 동시에 활성화하지 않는다.
- readback-Off 성능 실행에서는 candidate counter/list atomic과 dispatch-args pass를 모두
  생략한다.
- readback-On 진단에서는 후보 수 동일성을 검증하기 위해 counter와 작은 dispatch-args
  pass만 유지한다.

## 4. Engineering 검증

### 4.1 빌드와 런타임

- Visual Studio 2022 Release x64 빌드: 오류 0
- DX11 runtime `TSCMAAResolveCandidateMaskCS` 컴파일: PASS
- direct path 8-mode lifecycle: reset 48, failure 0
- direct path feedback: output mismatch byte 0, previous-history hash mismatch 0
- direct path static stability: `O-ET2X` 0/32 변화, `O-ET2X-R` 0/32 변화
- 기본 CompactIndirect lifecycle 재검증: reset 48, failure 0
- 모든 자동 실행 전후 잔류 `CMAA2.exe`: 0개

### 4.2 Candidate 동일성

readback-On smoke에서 각 장면의 네 구성은 같은 frame별 후보 수를 기록했다.

| Scene | 평균 base edge | 평균 candidate/process | Candidate/base |
|---|---:|---:|---:|
| Bistro | 49,535.392 | 33,289.758 | 67.2040% |
| Minecraft | 170,465.758 | 109,005.208 | 63.9455% |

Compact와 Direct의 base/candidate/process 평균은 reprojection Off/On 모두 위 값과
정확히 일치했다.

### 4.3 출력 동등성

두 경로를 독립 clean process에서 동일한 12개 frame으로 캡처했다.

| Mode | 비교 frame | SHA-256 mismatch |
|---|---:|---:|
| `O-ET2X` | 12 | 0 |
| `O-ET2X-R` | 12 | 0 |

따라서 아래 성능 차이는 품질이나 temporal kernel 변경이 아니라 실행 구조 차이다.

## 5. 반복 성능 결과

조건:

- RTX 3060 Ti, DirectX 11, Release x64
- 1920×1017, SMAA Ultra, VSync Off, UI hidden
- fixed 60 Hz 동일 flythrough
- mode당 300-frame warm-up
- 4,800-frame 측정 × 3회
- mode당 14,400 timing sample
- 정·역순 mode traversal 교차
- candidate readback Off
- Bistro와 Minecraft는 별도 clean process
- 두 결과 모두 내부 validation PASS

| Scene | Reprojection | Compact SMAA | Direct SMAA | 변화 | Compact WholeFrame | Direct WholeFrame | 변화 |
|---|---|---:|---:|---:|---:|---:|---:|
| Bistro | Off | 0.311432 ms | 0.363021 ms | +16.57% | 2.905601 ms | 2.974887 ms | +2.38% |
| Bistro | On | 0.348237 ms | 0.399925 ms | +14.84% | 2.961773 ms | 3.021908 ms | +2.03% |
| Minecraft | Off | 0.353000 ms | 0.427250 ms | +21.03% | 1.410903 ms | 1.497208 ms | +6.12% |
| Minecraft | On | 0.393623 ms | 0.467577 ms | +18.79% | 1.465559 ms | 1.546655 ms | +5.53% |

Candidate 실행 관련 timer 합은 다음과 같다.

- Compact: candidate-buffer clear + dispatch args + indirect candidate resolve
- Direct: full-resolution candidate-mask clear + direct masked resolve

| Scene | Reprojection | Compact 실행 합 | Direct 실행 합 | 변화 |
|---|---|---:|---:|---:|
| Bistro | Off | 0.031701 ms | 0.087472 ms | +175.93% |
| Bistro | On | 0.035078 ms | 0.091901 ms | +161.99% |
| Minecraft | Off | 0.044894 ms | 0.125343 ms | +179.20% |
| Minecraft | On | 0.051554 ms | 0.133029 ms | +158.04% |

Direct path는 compact atomic/list를 생략해 integrated spatial timer를 약간 줄였지만,
full-resolution mask clear와 모든 pixel의 mask load/분기 비용이 그 이득보다 훨씬 컸다.

## 6. 판정

1. `DirectMaskedFullScreen`의 candidate와 최종 출력은 기존 경로와 동일하다.
2. 그러나 두 장면과 reprojection Off/On 모두에서 SMAA와 WholeFrame 비용이 증가했다.
3. 현재 RTX 3060 Ti, 1920×1017, 후보 비율 약 64~67% 조건에서는 full-screen early-exit
   방식이 compact/indirect보다 효율적이지 않다.
4. 기존 `CompactIndirect`를 ET2X 기본 실행 구조로 유지한다.
5. direct path는 구조 가설을 재현할 수 있는 default-Off negative-result ablation으로만
   보존한다.
6. 이번 결과는 candidate compact/indirect 자체가 현재 주요 실패 원인이라는 가설을
   지지하지 않는다. 다음 성능 작업은 동일 구조 안의 메모리 전송/history feedback 비용,
   candidate selection의 first-pass 부가 비용 또는 tile 단위 대안을 별도로 다뤄야 한다.

## 7. 산출물

- Bistro formal: `D:\SMAA-Research-Data\AutoBench\20260830_192939`
- Minecraft formal: `D:\SMAA-Research-Data\AutoBench\20260830_193321`
- Compact capture: `D:\SMAA-Research-Data\AutoBench\20260830_192805`
- Direct capture: `D:\SMAA-Research-Data\AutoBench\20260830_192839`
- 분석: `D:\SMAA-Research-Data\AutoBench\Candidate-Execution-Analysis-20260830`
- 분석기: `Tools/SMAA/analyze_candidate_execution_performance.py`
