# O-ET2X-R History Feedback Topology Gate

## 1. 목적

이 gate는 `O-ET2X-R`의 motion-to-still 열세에 `history feedback topology`가 실제로
기여하는지 확인하기 위한 단일 축 ablation이다.

앞선 Standard temporal semantics `2×2×2` factorial gate에서는 동일한 compute resolve
경로 안에서 sampler, history weight, feedback을 직교 비교했다. 그 결과
`ResolvedOutput` recursive feedback가 중앙 이동과 Pattern On 이동→정지 구간의
spatial-reference 오차를 일관되게 높이는 강한 원인 후보로 나타났다. 그러나 그 실험은
full-screen document compute cell을 사용했기 때문에, 실제 통합 1차 edge candidate를 쓰는
`O-ET2X-R`에서도 같은 결론이 성립하는지는 별도로 확인해야 했다.

따라서 이번 gate에서는 실제 edge-selective 경로의 설정을 모두 고정하고 다음 프레임
history에 무엇을 저장하는지만 비교했다.

- `ResolvedOutput`: 현재 `O-ET2X-R`처럼 temporal resolve 결과를 다음 history로 feedback
- `SpatialFrame`: 현재 프레임의 spatial SMAA 결과를 다음 history로 저장

`SpatialFrame`은 원인 분리를 위한 진단 mode이며 최종 연구 case를 추가하거나 기존
`O-ET2X-R`의 의미를 변경하지 않는다.

## 2. 비교군과 통제 조건

### 2.1 변경한 유일한 축

| 항목 | `O-ET2X-R / ResolvedOutput` | `ABL-ET2X-SpatialFeedback-R` |
|---|---|---|
| 현재 프레임의 visible output | edge-selective temporal resolve 결과 | edge-selective temporal resolve 결과 |
| 다음 프레임 ping-pong history | resolve 결과 | 현재 spatial SMAA frame |
| feedback 형태 | recursive resolved feedback | non-recursive spatial-frame feedback |

`SpatialFrame` mode도 이번 프레임의 resolve 결과는 화면에 출력한다. 단, 화면 복사 이후
현재 spatial SMAA frame을 output history에 다시 복원한 뒤 ping-pong을 진행한다. 따라서
현재 프레임의 표시 경로를 제거한 비교가 아니라 **다음 프레임에 전달되는 history source만
교체한 비교**다.

### 2.2 두 mode에서 고정한 설정

| 축 | 고정값 |
|---|---|
| Spatial SMAA | Original SMAA |
| Candidate source | 통합 SMAA 1차 edge candidate |
| Candidate policy | `IntelFamilyNonDominant` |
| Non-dominant removal | `0.50` |
| Candidate expansion | `None` |
| Candidate execution | compact + indirect dispatch |
| Projection jitter / subsample pattern | Off (`Pattern Off`) |
| History sampling | Catmull-Rom 5-tap |
| History clipping | YCoCg variance clipping |
| Candidate history weight | fixed `0.8` |
| Non-candidate history weight | `0.0` |
| Reprojection | camera/depth reprojection |
| Bounds / reset / ping-pong lifecycle | 동일 |
| Visible resolve path | 동일한 two-copy resolve path |

따라서 아래 차이를 candidate coverage, jitter, sampler, clipping 또는 history weight의
효과로 해석하면 안 된다.

## 3. 구현과 사전 검증

진단 mode `SMAA_O_ABLATION_ET2X_SPATIAL_FEEDBACK_R`과 다음 전용 실행 경로를 추가했다.

- 품질 캡처: `-smaaET2XFeedbackTopologyCapture`
- 성능 smoke: `-smaaET2XFeedbackTopologyPerformanceSmoke`
- 반복 성능: `-smaaET2XFeedbackTopologyPerformanceBenchmark`

`SpatialFrame` 경로는 resolve 결과를 visible destination으로 복사한 다음 현재 spatial
frame을 history에 복원한다. 이 추가 복사는 `TSCMAARestoreSpatialHistory`로 별도 계측했다.

구현 감사 후에는 두 feedback 경로를 별도의 GPU 자동 검증으로 고정했다.

- `-smaaTemporalFeedbackTest`: `ResolvedOutput` history와 visible destination의 byte 일치,
  다음 프레임 previous-history hash chain 검증
- `-smaaTemporalSpatialFeedbackTest`: 복원된 history와 current spatial frame의 byte 일치,
  복원 전 resolved snapshot과 visible destination의 byte 일치, 다음 프레임
  previous-history hash chain 검증
- 두 명령은 integrated first-pass candidate, removal `0.50`, expansion None,
  Catmull-Rom, YCoCg clipping, compact indirect execution, debug Off, rigid-object motion Off를
  강제로 고정하고 기존 runtime override 상태를 종료 시 복원한다.
- mode/scene/camera-cut/resize로 history generation이 reset되면 이전 generation의 진단
  counter와 hash를 이어 붙이지 않고 새로 시작한다.
- clean runner는 새 CSV의 존재뿐 아니라 validation CSV 안의 `Aggregate`/row FAIL도 검사한다.

최종 자동 검증 결과:

| 검증 | 결과 root | 핵심 결과 |
|---|---|---|
| Resolved feedback bytes/hash | `20260903_023929` | output/history mismatch 0, previous hash mismatch 0, Aggregate PASS |
| Spatial history/visible bytes/hash | `20260903_023947` | history mismatch 0, visible mismatch 0, previous hash mismatch 0, Aggregate PASS |
| 기존 temporal lifecycle 회귀 | `20260903_024013` | failures 0, Aggregate PASS |
| feedback 성능 smoke | `20260903_024439` | 각 mode 120 samples, restore timer 120 samples, validation PASS |
| feedback 품질 경로 smoke | `20260903_024546` | 4 mode × 2 PNG 생성, clean process PASS |

위 root는 `D:\SMAA-Research-Data\AutoBench` 아래에 있다.

유효한 engineering smoke 결과는 다음과 같다.

- 품질 smoke: `D:\SMAA-Research-Data\AutoBench\20260903_010048`
  - ResolvedOutput와 SpatialFrame의 4/4 비교 프레임 hash가 서로 달라 실제 feedback 분기가
    다음 프레임 결과에 반영됨을 확인
- 성능 smoke: `D:\SMAA-Research-Data\AutoBench\20260903_010123`
  - 두 mode의 candidate count 일치
  - SpatialFrame의 restore timer 120/120 frame 존재
  - 내부 검증 PASS

### 3.1 formal 결과에서 제외한 실행

다음 두 root는 초기 설정 배치 오류로 `SpatialFrame` mode가 실제로는
`ResolvedOutput`처럼 동작했으므로 formal 결과에서 제외한다.

- `D:\SMAA-Research-Data\AutoBench\20260903_005626`
- `D:\SMAA-Research-Data\AutoBench\20260903_005656`

두 실행의 수치와 이미지는 재사용하지 않는다. 설정을 올바른 mode switch에 연결한 뒤
위 smoke와 아래 formal 캡처를 새 clean process에서 다시 수행했다.

## 4. formal 측정 조건과 입력 무결성

### 4.1 공통 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- API / preset: DirectX 11, SMAA Ultra
- 해상도: `1920×1017`
- VSync: Off
- 장면: Bistro, Minecraft
- camera profile: `flythrough-wide-yaw-360`
- fixed timestep: 60 Hz
- motion scope: camera motion only
- 품질 window
  - 중앙 이동: profile frame `150..329`, 180 frame
  - 이동→정지: profile frame `410..439`, 30 frame
- mode별 warm-up: profile frame 0에서 60 frame
- temporal pre-roll: 요청 window 직전까지 PNG 저장 없이 전체 timeline 순서대로 렌더링

Supersample 입력은 같은 pose를 고해상도로 렌더한 **spatial-reference proxy**이며 절대
temporal ground truth가 아니다. 최종 해석에는 spatial 지표와 CGVQM-2를 함께 사용했다.

### 4.2 유효한 formal quality root

| Window | Scene | Capture root |
|---|---|---|
| 중앙 이동 | Bistro | `D:\SMAA-Research-Data\AutoBench\20260903_010246` |
| 중앙 이동 | Minecraft | `D:\SMAA-Research-Data\AutoBench\20260903_010510` |
| 이동→정지 | Bistro | `D:\SMAA-Research-Data\AutoBench\20260903_010625` |
| 이동→정지 | Minecraft | `D:\SMAA-Research-Data\AutoBench\20260903_010707` |

Supersample spatial reference:

- Bistro: `D:\SMAA-Research-Data\AutoBench\20260827_014143`
- Minecraft: `D:\SMAA-Research-Data\AutoBench\20260827_014612`

기존 formal `O-T2X-R` control과의 byte-hash bridge는 두 window, 두 장면에서 mismatch 0으로
통과했다. 즉 이번 캡처를 위해 기존 Standard control의 출력이 바뀌지 않았다.

## 5. spatial-reference 보조 결과

`Spatial−Resolved`가 음수이면 SpatialFrame의 오차가 더 낮고, 양수이면 더 높다는 뜻이다.

### 5.1 중앙 이동

| Scene | Resolved RGB MAE | Spatial RGB MAE | MAE Δ | Luma SSIM Δ | Temporal residual Δ |
|---|---:|---:|---:|---:|---:|
| Bistro | 1.515207 | 1.454433 | -0.060774 | +0.001470 | -0.099949 |
| Minecraft | 0.859217 | 0.827006 | -0.032211 | +0.001212 | -0.053685 |

중앙 카메라 이동에서는 두 장면 모두 SpatialFrame이 spatial-reference 오차와 temporal
residual을 줄였다. 이는 recursive feedback가 이동 중 누적 오차의 한 원인이라는 앞선
factorial gate의 관찰과 같은 방향이다.

### 5.2 이동→정지와 후기 정지

| Scene | 구간 | Resolved RGB MAE | Spatial RGB MAE | MAE Δ | Luma SSIM Δ | Temporal residual Δ |
|---|---|---:|---:|---:|---:|---:|
| Bistro | 이동→정지 | 1.517447 | 1.524665 | +0.007219 | -0.000226 | +0.014191 |
| Bistro | 후기 정지 | 1.509959 | 1.530304 | +0.020344 | -0.000546 | -0.004220 |
| Minecraft | 이동→정지 | 1.553114 | 1.582219 | +0.029105 | -0.000806 | +0.025538 |
| Minecraft | 후기 정지 | 1.560092 | 1.594904 | +0.034812 | -0.001196 | -0.007735 |

이동→정지와 후기 정지에서는 반대로 SpatialFrame의 RGB MAE가 두 장면 모두 증가했다.
따라서 중앙 이동의 개선만 보고 feedback topology를 전역 교체하면 정지 전환의 history
accumulation 이점을 잃을 수 있다.

## 6. 공식 CGVQM-2 결과

검증 조건:

- Intel 공식 CGVQM commit: `8302ff45b4ff5a691682baf23f7c007d6b591e98`
- CUDA device: NVIDIA GeForce RTX 3060 Ti
- FFV1 test/reference round-trip pixel mismatch: 0
- 각 scene/window의 두 mode가 동일 reference pixel hash 사용
- 점수는 높을수록 좋으며 절대 ghosting ground truth는 아님

| Scene | Window | ResolvedOutput | SpatialFrame | Spatial−Resolved |
|---|---|---:|---:|---:|
| Bistro | 중앙 이동 | 96.688606 | 96.880989 | +0.192383 |
| Bistro | 이동→정지 | 94.560982 | 94.446014 | -0.114967 |
| Minecraft | 중앙 이동 | 97.515762 | 97.647354 | +0.131592 |
| Minecraft | 이동→정지 | 93.739021 | 93.496910 | -0.242111 |

CGVQM-2도 spatial-reference 보조 결과와 같은 방향을 재현했다. SpatialFrame은 중앙
이동에서는 두 장면 모두 점수를 높였지만 이동→정지에서는 두 장면 모두 낮췄다. 즉
feedback topology의 효과는 전 구간 단일 우열이 아니라 **motion phase trade-off**다.

## 7. 반복 성능 결과

### 7.1 조건과 root

- Release x64, DirectX 11, SMAA Ultra, VSync Off
- PNG/UI/candidate readback Off
- 300 frame warm-up
- mode당 4,800 measurement frame × 3 repeats
- repeat마다 mode 순서를 정방향/역방향으로 교차
- GPU timestamp sample: mode당 14,400
- Bistro: `D:\SMAA-Research-Data\AutoBench\20260903_020856`
- Minecraft: `D:\SMAA-Research-Data\AutoBench\20260903_021101`
- 두 benchmark의 내부 검증: PASS

### 7.2 결과

| Scene | Resolved SMAA | Spatial SMAA | SMAA Δ | SMAA Δ % | Resolved WholeFrame | Spatial WholeFrame | Frame Δ % | Restore copy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bistro | 0.342839 ms | 0.367524 ms | +0.024685 ms | +7.200% | 3.016821 ms | 3.017451 ms | +0.021% | 0.022493 ms |
| Minecraft | 0.385129 ms | 0.407214 ms | +0.022085 ms | +5.734% | 1.394054 ms | 1.421584 ms | +1.975% | 0.021993 ms |

SpatialFrame은 visible resolve 결과를 보존하면서 다음 history만 spatial frame으로 바꾸기
위해 복사 1회를 추가한다. 두 장면에서 약 `0.022 ms`의 restore copy가 측정됐고, 전체 SMAA
시간은 ResolvedOutput보다 `5.734~7.200%` 증가했다. 따라서 현재 구현에서 SpatialFrame은
성능 최적화가 아니다.

## 8. 종합 판정

1. 실제 통합 1차 edge candidate를 사용하는 `O-ET2X-R`에서도 feedback topology는 품질에
   유의미한 영향을 준다.
2. SpatialFrame은 중앙 이동에서 RGB MAE와 temporal residual을 줄이고 CGVQM-2를
   Bistro `+0.192383`, Minecraft `+0.131592` 높였다.
3. 그러나 이동→정지에서는 CGVQM-2가 Bistro `-0.114967`, Minecraft `-0.242111`
   낮아졌고, 후기 정지 spatial-reference 오차도 증가했다.
4. SpatialFrame은 현재 파이프라인에서 추가 history restore copy를 요구해 SMAA 시간을
   `5.734~7.200%` 증가시켰다.
5. 따라서 `ResolvedOutput → SpatialFrame` 전역 교체는 현재 증거로 채택할 수 없다.

## 9. 기본 `ResolvedOutput`을 유지하는 이유

현재 document profile과 최종 8-case의 ET2X feedback은 계속 `ResolvedOutput`으로 유지한다.

그 이유는 다음과 같다.

1. Intel 공개 TSCMAA 자료에는 최종 resolve 결과를 다음 프레임 history로 feedback하는
   구조가 포함되어 있다. 문서 기반 adaptation의 기본값을 바꾸려면 전 구간 우위에 대한
   더 강한 증거가 필요하다.
2. SpatialFrame은 중앙 이동에서만 개선됐고, 이동→정지와 후기 정지에서는 열세였다.
3. 현재 구현에서는 추가 복사 때문에 SMAA 비용도 증가한다.
4. 이번 mode는 원인 분리용 ablation이며 공식 Intel 구현이나 새로운 최종 case가 아니다.

따라서 이번 gate는 기존 `O-ET2X-R`이 완전한 최적값임을 증명한 것이 아니라, **단일 전역
feedback 교체로는 motion 중 품질과 정지 전환 품질을 동시에 개선할 수 없다는 것**을
확인한 결과다.

## 10. final 8-case semantics

이번 gate 이후에도 최종 8-case 행렬과 각 semantic ID는 변하지 않는다.

- `O-ET2X`, `O-ET2X-R`, `A-ET2X`, `A-ET2X-R`은 계속 document profile의
  `ResolvedOutput` feedback을 사용한다.
- `ABL-ET2X-SpatialFeedback-R`은 최종 8-case에 포함하지 않는다.
- 기존 Standard T2X와 Adaptive SMAA 동작도 변경하지 않는다.
- 이번 결과는 feedback topology 한 축의 원인 분석 자료로만 사용한다.

## 11. 해석 제한

- 장면은 Bistro와 Minecraft, camera-motion 경로에 한정된다.
- 현재 `-R`은 camera/depth reprojection이며 object motion vector를 뜻하지 않는다.
- supersample reference는 같은 pose의 공간 기준이며 절대 temporal/ghosting ground truth가
  아니다.
- 결과는 integrated candidate, removal `0.50`, expansion None, Pattern Off,
  Catmull-Rom, YCoCg clipping, fixed weight `0.8` 조합에 대한 것이다.
- SpatialFrame의 비용에는 현재 visible output을 유지하기 위한 restore copy가 포함된다.
  다른 history storage topology의 비용을 직접 대표하지 않는다.
- 두 feedback mode의 CGVQM 결과는 같은 reference로 검증했지만, 더 다양한 textured
  object-motion 및 disocclusion 장면은 후속 검증이 필요하다.

## 12. 다음 연구 방향

전역 feedback source를 하나로 고정해서 교체하기보다 motion phase와 history 신뢰도를
분리하는 controlled gate를 우선한다.

1. **Phase-aware feedback**
   - 중앙 이동, 감속, 이동→정지, 후기 정지를 명시적으로 구분한다.
   - 이동 중 SpatialFrame의 낮은 누적 오차와 정지 전환에서 ResolvedOutput의 sample
     accumulation 이점을 함께 유지할 수 있는지 확인한다.
2. **Confidence-aware history**
   - reprojection bounds, depth/disocclusion, velocity, clipping delta 등 이미 계산 가능한
     신뢰도 신호를 각각 독립 ablation으로 검증한다.
   - 낮은 신뢰도에서만 history weight 또는 feedback source를 제한하고, 단순 전역 교체와
     비교한다.
3. **Candidate/history persistence**
   - 한 프레임의 edge candidate 누락 때문에 temporal accumulation이 즉시 끊기지 않도록
     짧은 persistence 또는 hysteresis를 검토한다.
   - ghosting, flicker, candidate 수와 GPU 비용을 함께 측정하며 history를 무조건 늘리는
     방식은 사용하지 않는다.
4. 위 세 방향은 한 번에 결합하지 않고 각각의 품질·성능 gate를 통과한 뒤 조합한다.
5. 후속 개선안이 두 장면의 중앙 이동과 이동→정지에서 모두 재현되기 전에는 final 8-case
   기본 semantics를 변경하지 않는다.

## 13. 결과 경로

- 통합 분석 root:
  `D:\SMAA-Research-Data\AutoBench\20260903_ET2X-Feedback-Topology-Formal`
- 중앙 이동 spatial 분석:
  `D:\SMAA-Research-Data\AutoBench\20260903_ET2X-Feedback-Topology-Formal\CentralMotion`
- 이동→정지 spatial 분석:
  `D:\SMAA-Research-Data\AutoBench\20260903_ET2X-Feedback-Topology-Formal\Transition`
- CGVQM-2 원시 결과:
  `D:\SMAA-Research-Data\AutoBench\20260903_ET2X-Feedback-Topology-Formal\CGVQM2`
- CGVQM-2 통합 분석:
  `D:\SMAA-Research-Data\AutoBench\20260903_ET2X-Feedback-Topology-Formal\CGVQM2-Analysis`
- 반복 성능 분석:
  `D:\SMAA-Research-Data\AutoBench\20260903_ET2X-Feedback-Topology-Formal\Performance`

분석 도구는 formal 입력을 생성하기 전에 다음을 검증하도록 고정했다.

- Bistro/Minecraft가 정확히 한 번씩 존재하는지
- DirectX 11, Ultra, `1920×1017`, full-profile temporal pre-roll provenance
- reference/profile frame index의 중복·누락과 기존 `O-T2X-R` byte-hash bridge
- 성능 측정의 RTX 3060 Ti, VSync Off, 300 warm-up, 4,800 frame×3회,
  candidate readback Off 및 필수 timer
- CGVQM-2의 Intel commit, CUDA device, FFV1 round-trip, test/reference pixel hash와
  reference offset

강화 후 기존 formal 입력을 다시 읽어 중앙 이동 1,440 metric row, 이동→정지 240 row,
성능 2개 scene, CGVQM-2 8개 결과를 모두 PASS로 재검증했다. CGVQM runner는 단순히 기존
JSON이 있다는 이유만으로 건너뛰지 않고 현재 PNG hash와 provenance가 모두 일치할 때만
safe-resume하며 기본 재시도 횟수는 1회다.
