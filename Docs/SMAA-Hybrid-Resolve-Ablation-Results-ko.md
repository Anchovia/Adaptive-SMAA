# SMAA candidate temporal·비후보 de-jitter hybrid ablation 결과

## 1. 목적

앞선 원인 분리 실험에서는 다음 두 결과가 확인됐다.

- 화면 전체에 SMAA T2X projection jitter를 적용하고 후보 픽셀만 temporal resolve하면
  비후보 영역에 jitter가 그대로 남아 temporal variation이 커진다.
- projection jitter를 전체적으로 끄면 variation은 줄지만 출력이 `O-1X`에 가까워져
  temporal supersampling 효과를 상당 부분 잃는다.

이번 실험은 후보 픽셀에는 T2X sample diversity를 유지하면서, 비후보 픽셀에만
현재 프레임의 jitter를 역보정한 spatial base를 제공하면 두 문제를 함께 완화할 수
있는지 확인하는 diagnostic ablation이다.

새 mode `ABL-Candidate-DeJitter-R`은 최종 8-case를 늘리지 않으며 Intel 공식
TSCMAA mode도 아니다.

## 2. 구현

비교 대상:

| Mode | Temporal 범위 | Projection jitter | 비후보 base | Reprojection |
|---|---|---|---|---|
| `O-1X` | 없음 | Off | 현재 SMAA 1X | Off |
| `O-T2X-R` | Full-screen | SMAA T2X | N/A | Camera |
| `ABL-Candidate-Jitter-R` | Intel-family 후보 | SMAA T2X | jittered spatial | Camera |
| `ABL-Candidate-NoJitter-R` | Intel-family 후보 | Off | unjittered spatial | Camera |
| `ABL-Candidate-DeJitter-R` | Intel-family 후보 | SMAA T2X | de-jittered spatial | Camera |

세 candidate mode는 모두 bilinear history sampling, clipping Off, history weight 0.5를
사용한다. `ABL-Candidate-DeJitter-R`의 유일한 새 요소는 비후보 base다.

구현 순서:

1. 현재 spatial SMAA 결과를 full-screen compute shader로 읽는다.
2. `outputUV + currentProjectionJitter / resolution`에서 bilinear sample해
   inverse-jitter spatial base를 만든다.
3. 이 결과로 현재 output/history target을 먼저 채운다.
4. Intel-family candidate만 기존 indirect temporal resolve로 덮어쓴다.
5. 최종 결과를 다음 프레임 history로 feedback한다.

카메라 projection에서 geometry가 설정된 pixel offset만큼 이동하므로, unjittered
위치의 색은 jittered image의 `current UV + jitter`에서 근사했다.

이 방식은 별도의 unjittered scene render가 아니라 이미 렌더된 화면을 bilinear로
역이동하는 screen-space 근사다. 따라서 subpixel 정보 복원이 제한되고 blur가 생길 수
있다.

## 3. 기능 검증

- Release x64 build: PASS, error 0
- temporal lifecycle: PASS
  - 결과: `Projects/CMAA2/AutoBench/20260730_175446`
  - reset 36, completed frame 111
  - seed 19, resolve 92, camera reprojection 44
  - failure 0
- 12-frame object-motion smoke: PASS
  - 결과: `Projects/CMAA2/AutoBench/20260730_175521`
  - 5개 mode가 각각 연속 PNG 12개 생성
  - 검은 화면, 깨짐, 전체 화면 떨림 없음

## 4. 정식 측정 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- API: DirectX 11
- 해상도: 1920×1017
- SMAA preset: Ultra
- fixed timestep: 60 Hz
- mode별 warm-up: 60프레임
- mode별 저장: 240프레임
- `-R`: depth와 camera matrix 기반 camera-motion reprojection
- object motion vector: 미지원
- hidden-window PNG 품질 capture이며 성능 결과로 사용하지 않음

정식 hybrid capture:

- `Projects/CMAA2/AutoBench/20260730_175729`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_175858`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_180021`: `combined`

세 실행 모두 5개 mode × 240 PNG의 연속 index와 동일 해상도를 확인했다.

Supersample spatial-reference proxy:

- `Projects/CMAA2/AutoBench/20260730_152152`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_152246`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_152342`: `combined`

Reference는 선형 해상도 2배, 한 출력 프레임 안의 3×3 subpixel grid와 각 render의
8×MSAA를 사용한다. Temporal ground truth가 아니라 현재 프레임 형상을 비교하는
spatial-reference proxy다.

## 5. Optical-flow 정렬 결과

O-1X에서 계산한 Farneback flow를 같은 ROI의 모든 mode에 공통 적용했다. 아래 값은
motion-compensated RGB MAE이며 낮을수록 정렬 뒤 프레임 변화가 작다.

| 시나리오·ROI | `O-1X` | `O-T2X-R` | Candidate Jitter | Candidate NoJitter | Candidate DeJitter | DeJitter vs Jitter |
|---|---:|---:|---:|---:|---:|---:|
| thin-lines · thin line | 1.079927 | 1.487113 | 1.967515 | 1.170240 | 1.673875 | -14.924% |
| object-motion · occluder | 0.249265 | 0.256554 | 1.053831 | 0.256339 | 0.893078 | -15.254% |
| object-motion · rotor | 2.027974 | 1.698475 | 2.545684 | 2.033851 | 2.423269 | -4.809% |
| combined · thin line | 1.513948 | 1.925195 | 2.383669 | 1.612773 | 2.126066 | -10.807% |
| combined · occluder | 0.879953 | 1.157460 | 1.462500 | 0.941716 | 1.301739 | -10.992% |
| combined · rotor | 2.553482 | 2.459543 | 2.966502 | 2.616351 | 2.805641 | -5.423% |

DeJitter는 Candidate Jitter보다 모든 ROI의 aligned residual을
`4.809%~15.254%` 줄였다. Candidate Jitter와 Standard 사이 거리도
`14.449%~61.124%` 줄어 부분적인 안정화 효과는 확인됐다.

그러나 DeJitter는 모든 ROI에서 Candidate NoJitter보다 residual이 크고, 고정-camera
object-motion에서는 `O-1X` 및 Standard와도 큰 차이가 남았다. 즉 screen-space
de-jitter만으로 candidate-only jitter mismatch를 충분히 제거하지 못했다.

Optical-flow residual은 blur로도 작아질 수 있고 disocclusion을 완전히 평가하지
못하므로 절대 품질 점수가 아니다.

## 6. Supersample spatial-reference 결과

아래 RGB MAE는 같은 시점의 spatial-reference proxy와의 차이다.

| 시나리오·ROI | `O-1X` | `O-T2X-R` | Candidate Jitter | Candidate NoJitter | Candidate DeJitter |
|---|---:|---:|---:|---:|---:|
| thin-lines · thin line | 0.719308 | 0.845783 | 0.980899 | **0.683393** | 0.854022 |
| object-motion · occluder | **0.497008** | 0.936618 | 0.687563 | 0.542440 | 0.632862 |
| object-motion · rotor | **0.500726** | 2.248942 | 0.691534 | 0.551653 | 0.600367 |
| combined · thin line | **0.764908** | 1.443198 | 1.038566 | 0.778050 | 0.914656 |
| combined · occluder | **0.522279** | 0.933988 | 0.778320 | 0.545593 | 0.705134 |
| combined · rotor | **0.581120** | 1.974153 | 0.802050 | 0.611566 | 0.674462 |

DeJitter는 Candidate Jitter보다 reference MAE를 모든 ROI에서
`7.956%~15.908%` 줄였다. 그러나 Candidate NoJitter보다
`8.831%~29.242%` 높았고, `O-1X`보다도 `16.063%~35.011%` 높았다.

Object-motion rotor에서 DeJitter는 Candidate Jitter보다 reference에 가까워졌고
Standard T2X의 명확한 이중 날개 잔상도 만들지 않았다. 반면 edge strength는
reference의 약 0.970배로 낮아졌고, sequence sheet에서도 bilinear 역이동에 따른
경계 연화가 보였다. 이는 오차 감소 일부가 올바른 temporal reconstruction뿐 아니라
screen-space filtering에서 온 것일 수 있음을 뜻한다.

## 7. 시각 확인

- `O-T2X-R`: 회전 날개와 이동 occluder 뒤에 이전 위치가 반투명하게 남는다.
- Candidate Jitter: Standard의 큰 object ghost는 줄지만 얇은 선과 배경에
  jitter variation이 남는다.
- Candidate NoJitter: 현재 형상이 `O-1X`와 가장 비슷하고 안정적이지만 temporal
  sample diversity가 없다.
- Candidate DeJitter: Candidate Jitter보다 흔들림은 줄지만 Candidate NoJitter보다
  변화가 크며 선 경계가 다소 부드러워진다.

대표 자료:

- `20260730_175729/HybridResolveAnalysis/hybrid_resolve_sheet_thin_line_field_00108_00128.png`
- `20260730_175858/HybridResolveAnalysis/hybrid_resolve_sheet_rotor_00078_00098.png`
- `20260730_175858/HybridResolveAnalysis/hybrid_resolve_sheet_occluder_path_00078_00098.png`
- `20260730_175858/SupersampleHybridAnalysis/supersample_reference_difference_rotor_00090.png`
- `20260730_175858/SupersampleHybridAnalysis/supersample_reference_rotor_00078_00101.gif`
- `20260730_180021/SupersampleHybridAnalysis/supersample_reference_difference_thin_line_field_00090.png`

위 상대 경로의 기준은 `Projects/CMAA2/AutoBench/`다.

## 8. 결론

1. Candidate temporal + 비후보 screen-space de-jitter hybrid를 독립 diagnostic으로
   구현하고 lifecycle, smoke, 3개 stress 시나리오 정식 품질 측정을 완료했다.
2. DeJitter는 Candidate Jitter보다 optical-flow residual과 spatial-reference MAE를
   일관되게 줄였으므로 가설은 부분적으로 지지됐다.
3. 그러나 Candidate NoJitter와 `O-1X`보다 품질 지표가 일관되게 나빴고, bilinear
   역이동의 blur도 관측됐다.
4. 따라서 현재 screen-space de-jitter 구현은 `O-1X`보다 temporal 효과를 유지하면서
   Standard보다 ghosting을 줄이는 최종 해법으로 채택하지 않는다.
5. 이 결과는 최종 8-case의 정의나 기존 document-based ET2X profile을 변경하지 않는다.
6. 품질상 채택 근거가 없고 full-screen compute pass가 추가되므로 정식 성능 본 측정은
   진행하지 않았다. 향후 방식을 재설계해 품질 이득이 확인될 때 비용을 별도 측정한다.

## 9. 다음 연구 범위

다음 후보도 최종 8-case와 분리한 후속 ablation으로 다룬다.

1. hard candidate mask 주변에 안정화 band를 두고 history weight를 연속적으로 변화
2. 별도 unjittered scene render를 생성해 screen-space 역이동의 blur와 분리
3. object motion vector를 연결해 rotor와 occluder history 좌표를 직접 보정
4. candidate-aware jitter 또는 geometry 이전에 얻을 수 있는 안정적인 coverage mask 검토

가장 직접적인 다음 우선순위는 현재 camera-only reprojection의 구조적 한계를 해결하는
object motion vector 지원 여부 조사다.
