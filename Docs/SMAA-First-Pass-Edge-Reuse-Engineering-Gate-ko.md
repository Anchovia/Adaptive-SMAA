# SMAA 1차 패스 edge 재사용 경로 Engineering Gate

## 1. 목적

기존 TSCMAA-inspired SMAA 경로는 SMAA의 공간 패스가 끝난 뒤 temporal 후보를 만들 때
화면 luminance에서 edge를 다시 검출했다. 이 구조는 기능적으로 동작하지만 다음 문제가
있다.

- SMAA 1차 패스가 이미 만든 edge 결과와 temporal 후보의 base edge가 다를 수 있다.
- temporal 후보 준비를 위해 주변 luminance를 다시 읽고 방향 edge strength를 계산한다.
- 기존 ET2X 성능에서 확인된 overhead에 중복 edge 판정이 포함될 가능성이 있다.

이번 작업은 기존 경로를 삭제하지 않고 `CandidateEdgeSource`라는 직교 축으로 분리해,
`LegacyLumaRedetect`와 `SMAAFirstPassEdges`를 동일한 downstream temporal 설정에서 직접
비교할 수 있게 만든 engineering gate다.

이 변경은 공간 SMAA 전체를 생략하는 작업이 아니다. SMAA 1X 결과를 현재 프레임의 공간
AA 입력으로 만들기 위해 edge detection, blending-weight calculation, neighborhood
blending은 그대로 실행한다. 변경된 부분은 그 뒤 temporal 후보 base edge를 별도로 다시
검출하던 단계다.

## 2. 구현 구조

### `LegacyLumaRedetect`

- 기존 동작을 그대로 보존한다.
- post-SMAA color luminance의 상·좌 샘플에서 base edge와 방향 strength를 계산한다.
- 기존 결과와 비교하기 위한 기본값 및 회귀 기준이다.

### `SMAAFirstPassEdges`

- 기존 SMAA 1차 edge detection pass의 `edgesRT` RG 방향 mask를 base edge로 직접 읽는다.
- `AllBaseEdges`에서는 temporal base edge 판정에 추가 luminance edge 검출이 필요하지 않다.
- `IntelFamilyNonDominant`에서는 SMAA mask를 base gate로 사용하고, 살아남은 위치의
  non-dominant ranking 의미를 유지하기 위해 기존 luminance contrast strength를 사용한다.
- SMAA 원본 공간 shader와 공간 pass 순서는 수정하지 않았다.

다음 설정은 두 source 사이에서 동일하게 유지한다.

- 공간 처리: Original SMAA Ultra
- candidate policy: `IntelFamilyNonDominant`
- candidate expansion: None
- history sampler: Catmull-Rom 5-tap
- clipping: YCoCg variance clipping
- history weight: 0.8
- deliberate projection jitter: Off
- reprojection Off/On은 각각 `O-ET2X`/`O-ET2X-R` 안에서 별도 pair로 비교

실행 옵션은 다음과 같다.

```text
-smaaCandidateEdgeSourceOverride -1|0|1
  -1: mode 기본값
   0: LegacyLumaRedetect
   1: SMAAFirstPassEdges

-smaaCandidateEdgeSourcePerformanceSmoke
-smaaCandidateEdgeSourcePerformanceBenchmark
-smaaCandidateEdgeSourceCapture
```

기존 8-case와 기존 측정의 의미를 바꾸지 않도록 현재 mode 기본값은
`LegacyLumaRedetect`로 유지한다.

## 3. 두 source가 완전히 같은 mask가 아닌 이유

SMAA Ultra 1차 edge mask는 SMAA 내부 threshold 0.05와 local contrast adaptation을 거쳐
생성된다. 기존 temporal luma 재검출은 threshold `1/22`를 사용하고 SMAA와 동일한 local
contrast adaptation mask가 아니다. 따라서 first-pass 재사용은 단순 캐시 최적화가 아니라
temporal base edge의 출처를 SMAA 공간 edge와 일치시키는 controlled algorithmic
ablation이다. 두 결과가 pixel-identical할 것이라고 가정하면 안 된다.

## 4. 기능 및 회귀 검증

Release x64 빌드와 두 candidate extraction compute shader의 직접 FXC 컴파일을
통과했다. first-pass source에서 다음 자동 검증도 통과했다.

| 검증 | 결과 |
|---|---|
| Temporal lifecycle | reset 48, completed 130, seed 25, resolve 105, reprojection 62, failure 0 |
| Temporal feedback | output/history mismatch 0, 다음 프레임 history hash mismatch 0 |
| Static stability | `O-ET2X`, `O-ET2X-R` 각각 32개 resolve hash 변화 0 |
| Candidate policy sweep | Bistro/Minecraft의 removal 0~1 단조성·indirect count PASS |

검증 결과 경로:

- `D:\SMAA-Research-Data\AutoBench\20260827_172910`
- `D:\SMAA-Research-Data\AutoBench\20260827_172930`
- `D:\SMAA-Research-Data\AutoBench\20260827_173015`
- first-pass policy sweep: `D:\SMAA-Research-Data\AutoBench\20260827_171252`
- legacy policy sweep: `D:\SMAA-Research-Data\AutoBench\20260827_171458`

## 5. 후보 수 비교

고정 pose, removal 0.5 policy sweep 결과는 다음과 같다.

| 장면 | Source | Base edge | Candidate | Candidate/Base |
|---|---|---:|---:|---:|
| Bistro | Legacy luma | 56,958 | 29,848 | 52.404% |
| Bistro | SMAA first-pass | 48,346 | 27,759 | 57.417% |
| Minecraft | Legacy luma | 653,210 | 354,265 | 54.234% |
| Minecraft | SMAA first-pass | 544,952 | 342,046 | 62.766% |

first-pass source는 legacy 대비 base edge를 Bistro 약 15.12%, Minecraft 약 16.57%
줄였고, 최종 candidate는 각각 약 7.00%, 3.45% 줄였다. Candidate/Base 비율이 올라간
것은 더 작은 SMAA base mask 안에서 기존 non-dominant ranking을 적용했기 때문이다.

동일 프로세스의 동적 Bistro readback-On characterization에서도 legacy 대비 first-pass의
평균 base edge는 57,000.875개에서 49,535.392개로 13.10%, candidate는 34,670.867개에서
33,289.758개로 3.98% 감소했다. reprojection Off/On에서 후보 수가 동일해 source 축이
reprojection과 독립적으로 적용됨을 확인했다.

결과 경로:

- `D:\SMAA-Research-Data\AutoBench\20260827_173518`

## 6. 성능 engineering smoke

readback Off, 동일 프로세스, 60-frame warm-up, 240-frame 측정, 2회 반복의 짧은 matrix에서
candidate extraction GPU 평균은 다음과 같았다.

| Pair | Legacy | SMAA first-pass | 변화 |
|---|---:|---:|---:|
| `O-ET2X` | 0.079038 ms | 0.076826 ms | -2.80% |
| `O-ET2X-R` | 0.079119 ms | 0.076926 ms | -2.77% |

반면 SMAA total은 spatial pass 변동 때문에 first-pass 쪽이 이 짧은 실행에서 약간 높았고,
WholeFrame도 방향이 일관되지 않았다. 따라서 현재 확인된 결론은 **중복 후보 추출 pass의
비용이 소폭 감소했다**는 engineering signal뿐이다. 전체 SMAA 또는 frame 성능 개선은
정식 4,800-frame 반복 benchmark 전에는 주장하지 않는다.

결과 경로:

- `D:\SMAA-Research-Data\AutoBench\20260827_173442`

## 7. 동일 프로세스 품질 격리 캡처

전용 `-smaaCandidateEdgeSourceCapture`로 한 프로세스 안에서 네 설정을 각각 60-frame
warm-up한 뒤 16-frame씩 저장했다. 모든 디렉터리가 00000~00015 연속 index,
1920×1017, 16/16 고유 PNG hash를 통과했다.

| Pair | 평균 변경 픽셀 | normalized RGB MAE | PSNR |
|---|---:|---:|---:|
| `O-ET2X` legacy vs first-pass | 0.083864% | 0.000020741 | 57.668149 dB |
| `O-ET2X-R` legacy vs first-pass | 0.160965% | 0.000022527 | 58.360625 dB |

이는 source 교체가 전체 화면을 크게 바꾸거나 깨뜨리지 않았다는 회귀 gate다. 변경 픽셀의
품질 우열, 고스팅, temporal sample retention을 판정한 결과는 아니다.

결과 경로:

- `D:\SMAA-Research-Data\AutoBench\20260827_174723`

## 8. 현재 결론과 다음 단계

SMAA 1차 패스 edge를 temporal base candidate에 재사용하는 경로가 구현됐고, 기존 원본
SMAA 공간 path를 훼손하지 않은 상태에서 lifecycle, feedback, static stability,
candidate/indirect 구조와 동일 프로세스 캡처 gate를 통과했다. 또한 base/candidate 수와
candidate extraction pass 시간이 감소하는 방향을 확인했다.

다만 아직 기본 source를 first-pass로 승격하거나 기존 ET2X 성능 결론을 교체하지 않는다.
다음 단계는 다음과 같다.

1. visible-window, readback Off, 300 warm-up, 4,800 measurement, 최소 3회 반복 성능 측정
2. Bistro 저대비와 Minecraft 고대비 동일 카메라 경로 품질 캡처
3. supersample spatial reference, CGVQM-2, temporal retention 및 ghosting 보조 지표 비교
4. 품질 회귀가 없고 전체 비용 감소가 반복 오차보다 클 때만 first-pass source의 기본값
   승격 검토

## 9. 정식 gate 완료 후 정정

위 1~3단계 정식 측정은 2026-08-27 완료했다. 4,800-frame×3회 반복 성능에서
first-pass source의 candidate resolve는 소폭 감소했지만 extraction, SMAA total과
WholeFrame은 개선되지 않았다. Bistro/Minecraft reference 및 CGVQM-2 결과도 변화가
매우 작고 장면·구간에 따라 방향이 달랐으며, 출력은 legacy보다 O-1X에 가까워졌다.

따라서 first-pass source는 ablation으로 보존하고 기본값은 legacy로 유지한다. 이 문서의
engineering 수치보다 다음 정식 결과 문서를 최종 판정 근거로 우선한다.

- `Docs/SMAA-First-Pass-Edge-Reuse-Formal-Results-ko.md`
