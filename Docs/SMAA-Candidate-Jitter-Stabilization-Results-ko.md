# SMAA Edge-selective candidate·projection jitter 원인 분리 결과

## 1. 목적

기존 controlled component ablation과 optical-flow 분석에서는
`ABL-CandidateOnly-R`이 대응하는 `O-T2X-R`보다 motion-compensated temporal
residual이 컸다. 이번 실험은 그 원인을 다음 두 가설로 분리했다.

1. Intel-family non-dominant 정책이 필요한 edge 후보를 너무 많이 제거한다.
2. projection jitter는 화면 전체에 적용되지만 temporal resolve는 후보에만 적용되어,
   비후보 픽셀에 jitter가 그대로 남는다.

이번 결과는 최종 8-case를 늘리는 새 mode가 아니라 후속 원인 분석용 ablation이다.

## 2. 공통 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- API: DirectX 11
- 해상도: 1920×1017
- SMAA preset: Ultra
- fixed timestep: 60 Hz
- mode별 warm-up: 60프레임
- mode별 저장: 240프레임
- 시나리오: `thin-lines`, `object-motion`, `combined`
- `-R`: depth와 camera matrix를 이용한 camera-motion reprojection
- object motion vector: 미지원
- hidden-window PNG capture이며 성능 측정으로 사용하지 않음
- O-1X에서 Farneback flow를 추정해 같은 ROI의 모든 mode에 동일 적용
- forward/backward consistency threshold: 1 px
- optical-flow 합성 이동 self-test vector error: 0.000108 px, PASS
- 새 no-jitter diagnostic을 포함한 temporal lifecycle: reset 35, seed 18,
  resolve 89, reprojection 41, failure 0, PASS

Flow-aligned residual은 장면 motion을 줄인 보조 지표다. 작은 값이 blur 때문에
발생할 수도 있고, forward/backward 불일치로 제외된 disocclusion을 완전히 재지
않으므로 절대 품질 점수로 사용하지 않는다.

## 3. 가설 1: 후보 누락 검증

비교 mode:

| Mode | Temporal 범위 | Candidate | Jitter | Reprojection | Sampler | Clipping | Weight |
|---|---|---|---|---|---|---|---:|
| `O-1X` | 없음 | N/A | Off | Off | N/A | Off | 0.0 |
| `O-T2X-R` | Full-screen | 전체 화면 | SMAA T2X | Camera | Point | Off | velocity-alpha adaptive 0~0.5 |
| `ABL-Candidate-Intel-R` | Edge-selective | Intel-family | SMAA T2X | Camera | Bilinear | Off | 0.5 |
| `ABL-Candidate-AllBase-R` | Edge-selective | 모든 base edge | SMAA T2X | Camera | Bilinear | Off | 0.5 |

두 candidate mode의 유일한 차이는
`IntelFamilyNonDominant`와 `AllBaseEdges` 후보 정책이다.
`O-T2X-R`은 공식 point/velocity-adaptive resolve를 사용하므로 candidate mode와의 차이를
candidate coverage 하나의 효과로 해석하지 않는다.

캡처:

- `Projects/CMAA2/AutoBench/20260730_140313`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_140430`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_140549`: `combined`

### Flow-aligned residual 결과

| 시나리오·ROI | `O-T2X-R` | Intel 후보 | AllBase 후보 | AllBase vs Intel |
|---|---:|---:|---:|---:|
| thin-lines · thin line | 1.487113 | 1.967515 | 1.967515 | 0.000% |
| object-motion · occluder | 0.256554 | 1.053831 | 1.052523 | -0.124% |
| object-motion · rotor | 1.698475 | 2.545684 | 2.545611 | -0.003% |
| combined · thin line | 1.925195 | 2.383669 | 2.383470 | -0.008% |
| combined · occluder | 1.157460 | 1.462500 | 1.461365 | -0.078% |
| combined · rotor | 2.459543 | 2.966502 | 2.966348 | -0.005% |

AllBase 전환의 변화는 모든 ROI에서 `0.000%~-0.124%`에 그쳤다. Standard와의
거리 감소도 최대 0.372%였다. 따라서 Intel-family non-dominant 제거가 현재
candidate-only jitter 문제의 주원인이라는 가설은 지지되지 않는다.

AllBase는 검출된 base edge 전체이지 full-screen이 아니다. 따라서 이 결과는
“edge 후보 내부의 제거량”을 기각하며, 비edge·비후보 픽셀 문제를 기각하지 않는다.

## 4. 가설 2: 전역 projection jitter와 비후보 불일치 검증

비교 mode:

| Mode | Temporal 범위 | Candidate | Jitter | Reprojection | Sampler | Clipping | Weight |
|---|---|---|---|---|---|---|---:|
| `O-1X` | 없음 | N/A | Off | Off | N/A | Off | 0.0 |
| `O-T2X-R` | Full-screen | 전체 화면 | SMAA T2X | Camera | Point | Off | velocity-alpha adaptive 0~0.5 |
| `ABL-Candidate-Jitter-R` | Edge-selective | Intel-family | SMAA T2X | Camera | Bilinear | Off | 0.5 |
| `ABL-Candidate-NoJitter-R` | Edge-selective | Intel-family | Off | Camera | Bilinear | Off | 0.5 |

두 candidate mode의 유일한 차이는 deliberate projection jitter On/Off다.
`O-T2X-R`은 공식 point/velocity-adaptive resolve를 사용하므로 candidate mode와의 차이를
candidate coverage 하나의 효과로 해석하지 않는다.

캡처:

- `Projects/CMAA2/AutoBench/20260730_141450`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_141600`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_141705`: `combined`

### Flow-aligned residual 결과

| 시나리오·ROI | `O-1X` | `O-T2X-R` | Jitter On | Jitter Off | Off vs On |
|---|---:|---:|---:|---:|---:|
| thin-lines · thin line | 1.079927 | 1.487113 | 1.967515 | 1.170240 | -40.522% |
| object-motion · occluder | 0.249265 | 0.256554 | 1.053831 | 0.256339 | -75.676% |
| object-motion · rotor | 2.027974 | 1.698475 | 2.545684 | 2.033851 | -20.106% |
| combined · thin line | 1.513948 | 1.925195 | 2.383669 | 1.612773 | -32.341% |
| combined · occluder | 0.879953 | 1.157460 | 1.462500 | 0.941716 | -35.609% |
| combined · rotor | 2.553482 | 2.459543 | 2.966502 | 2.616351 | -11.803% |

Jitter Off는 Jitter On보다 모든 ROI의 aligned residual을 `11.803%~75.676%`
낮췄다. Standard와의 거리도 `29.274%~99.973%` 감소했다. 반면 AllBase 후보
확대는 거의 효과가 없었다.

이 두 실험을 함께 보면 현재 candidate-only 구성의 높은 temporal variation은
Intel-family 후보 제거보다 **화면 전체 projection jitter와 후보 한정 resolve의
범위 불일치**가 주원인이라는 해석을 강하게 지지한다.

## 5. 시각 확인과 temporal 효과 손실

`object-motion` rotor sequence sheet에서 다음이 확인됐다.

- `O-T2X-R`은 회전 날개의 이전 위치가 반투명하게 겹치는 이중 잔상이 보인다.
- `ABL-Candidate-Jitter-R`은 날개 잔상은 줄지만 비후보 영역의 jitter variation이
  aligned residual에 크게 남는다.
- `ABL-Candidate-NoJitter-R`은 안정화되지만 현재 날개 형상이 `O-1X`와 매우 가깝다.

Jitter Off의 O-1X 대비 aligned residual 차이는 object-motion rotor `+0.290%`,
occluder `+2.838%`였다. combined rotor도 `+2.462%`였다. 이는 global no-jitter가
문제 증상을 줄이는 동시에 움직이는 물체에서 temporal supersampling 효과를 상당
부분 잃고 O-1X에 가까워질 수 있음을 보여준다.

따라서 global no-jitter를 독립적인 최종 개선 성공으로 주장하면 안 된다. 현재
document profile의 no-jitter 선택이 심한 후보·jitter 불일치를 피하는 이유는
확인됐지만, temporal sample diversity 손실이라는 trade-off가 남는다.

대표 자료:

- `20260730_141450/CandidateJitterIsolationAnalysis/candidate_jitter_isolation_sheet_thin_line_field_00108_00128.png`
- `20260730_141600/CandidateJitterIsolationAnalysis/candidate_jitter_isolation_sheet_rotor_00078_00098.png`
- `20260730_141600/CandidateJitterIsolationAnalysis/candidate_jitter_isolation_rotor_00078_00101.gif`
- `20260730_141600/CandidateJitterIsolationAnalysis/candidate_jitter_isolation_sheet_occluder_path_00078_00098.png`

위 상대 경로의 기준은 `Projects/CMAA2/AutoBench/`다.

## 6. 결론

1. Intel-family에서 AllBase로 후보를 늘리는 것만으로 문제는 해결되지 않았다.
2. 전역 projection jitter를 유지하면서 후보에만 temporal resolve를 적용하는 범위
   불일치가 높은 temporal variation의 주원인으로 확인됐다.
3. global no-jitter는 variation을 크게 줄이지만 object motion 출력이 O-1X에
   가까워져 temporal supersampling 효과 손실 가능성이 크다.
4. 따라서 현 단계의 올바른 결론은 “후보 확대 성공”이나 “no-jitter 최종 개선
   성공”이 아니라, **문제 원인과 trade-off를 분리해 확인했다**는 것이다.
5. candidate-aware jitter는 현재 deferred renderer에서 후보 mask가 geometry render
   이후에 생성되므로 단순 toggle로 구현할 수 없다.

## 7. 다음 연구 범위

현재 8-case와 분리한 후속 연구로 다음을 검토한다.

1. 비후보 픽셀을 위한 별도 unjittered spatial base 또는 de-jitter resolve
2. 후보와 비후보의 서로 다른 temporal weight를 사용하는 안정화 band
3. object motion vector 연결
4. supersample ground truth로 blur와 temporal 안정화를 분리
5. 위 방식이 실제 temporal 효과를 유지하는지 O-1X control과 함께 재검증

추가 방식은 candidate selection 효과와 섞지 말고 별도 ablation으로 구현해야 한다.
