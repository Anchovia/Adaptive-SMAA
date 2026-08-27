# 25. 2026-08-20 보고서 이후 작업 개요

2026-08-20 보고서에서는 다음 상태까지 정리했다.

- current-edge 3×3 dilation 구현·정확성·품질·성능 측정 완료
- 부드러운 회전-only, 이동-only, 이동+360° 회전 camera profile 구현 완료
- Bistro와 Minecraft에서 O-1X 경로 재생과 안전성 검증 완료
- 새 부드러운 경로에서 T2X·ET2X 품질 비교는 미진행

그 이후에는 다음 작업을 순서대로 진행했다.

1. 부드러운 카메라 경로에서 `O-1X`, `O-T2X-R`, `O-ET2X-R` 3-way 선행 측정
2. 이동량이 작아 보이던 기존 flythrough를 보완한 wide camera profile 구현
3. Wide 이동+회전 경로에서 supersample spatial-reference 및 CGVQM-2 측정
4. Filtered 1/4 downsample-upsample 후보 확장 구현
5. ARM Dual Filtering kernel을 이용한 candidate expansion adaptation 구현
6. San Miguel의 실제 얇은 의자·테이블 다리·식생 geometry에서 확장 방식 비교
7. SMAA T2X/TSCMAA-inspired 구현 전체에 대한 체계적 코드 감사
8. 감사에서 발견한 FilteredQuarter raw candidate 유실 결함 수정
9. 수정된 FilteredQuarter 재측정 및 3×3과의 최종 engineering trade-off 판정

---

# 26. 부드러운 카메라 경로 3-way 선행 품질 측정

## 26.1 비교 대상

새 카메라 경로에서 먼저 Original SMAA 기반 세 mode만 비교했다.

| Mode | 의미 |
| --- | --- |
| `O-1X` | temporal history를 사용하지 않는 Original SMAA 1X control |
| `O-T2X-R` | 전체 화면 Standard T2X + camera-motion reprojection |
| `O-ET2X-R` | current-edge 후보에만 history를 적용하는 document-profile ET2X + camera-motion reprojection |

장면과 카메라 profile은 다음과 같다.

| 구분 | 조건 |
| --- | --- |
| 저대비 장면 | Bistro |
| 고대비 장면 | Minecraft |
| 회전-only | `yaw-smooth-360` |
| 이동-only | `flythrough-smooth` |
| 이동+회전 | `flythrough-smooth-yaw-360` |

전체 행렬은 다음과 같다.

```text
2개 장면 × 3개 camera profile × 3개 mode = 18 sequence
```

각 sequence는 fixed 60Hz 기준 60-frame pre-still, 360-frame motion, 60-frame
post-still의 총 480프레임이다. 총 8,640개의 PNG를 저장했고 모든 index와 독립 실행의
O-1X hash 재현성을 검증했다.

## 26.2 Temporal 영향 유지율

다음 값을 화면상 temporal 영향의 대용값으로 사용했다.

```text
MAE(O-ET2X-R, O-1X)
-------------------- × 100
MAE(O-T2X-R, O-1X)
```

| Scene | Camera profile | ET2X temporal 영향 유지율 |
| --- | --- | ---: |
| Bistro | 회전-only | 23.95% |
| Bistro | 이동-only | 27.99% |
| Bistro | 이동+회전 | 25.40% |
| Minecraft | 회전-only | 28.30% |
| Minecraft | 이동-only | 28.45% |
| Minecraft | 이동+회전 | 28.56% |

`O-ET2X-R`은 history를 완전히 사용하지 않는 것은 아니지만, 화면 전체에 나타나는
temporal 영향이 Standard T2X의 약 24~29% 수준으로 감소했다.

이 결과는 두 가지 가능성을 동시에 의미한다.

- Standard T2X의 불필요한 history와 blur·ghosting을 줄였을 가능성
- history 적용 범위가 너무 좁아 temporal supersampling 효과까지 잃었을 가능성

O-1X와의 차이만으로 두 가능성을 구분할 수 없으므로 이 단계에서는 품질 우위를 확정하지
않았다.

## 26.3 시간 변화와 정지 후 안정화

- `O-ET2X-R`의 edge strength는 Standard보다 O-1X에 가까웠다.
- 이는 전체 화면 blur를 줄인 결과일 수 있지만 O-1X의 aliasing을 더 많이 유지한 결과일
  수도 있다.
- 이동+회전을 결합해도 temporal 영향 유지율은 개별 회전-only와 이동-only 범위 안에
  있었다.
- 대표 프레임에서 화면 전체가 밀리거나 심한 이중상으로 보이는 catastrophic
  reprojection 오류는 관찰되지 않았다.
- 회전이 포함된 경로에서 `O-ET2X-R`이 최종 정지 plateau에 들어오는 데 6~8프레임이
  필요했다.

이 6~8프레임은 절대적인 ghost trail 길이가 아니라 최종 filter 상태로 수렴하는 보조
지표다.

---

# 27. Wide Smooth Flythrough 보강

기존 `flythrough-smooth` 계열은 원래 Catmull–Rom 이동량을 0.25배로 줄여 총 이동 거리가
약 1.86m였다. 경로 구현은 정상적이었지만 360° yaw가 시각적으로 지배적이어서 실시간
화면에서는 제자리 회전에 가깝게 보일 수 있었다.

기존 결과는 low-translation control로 보존하고, 위치 변화 scale만 0.50으로 늘린 다음
profile을 추가했다.

| Profile | 이동 거리 | 회전 |
| --- | ---: | --- |
| `flythrough-wide` | 약 3.72m | 기존 flythrough 방향 |
| `flythrough-wide-yaw-360` | 약 3.72m | flythrough 방향 + 부드러운 360° yaw |

보간식, 480-frame timeline, fixed 60Hz, 시작·종료 정지 구간은 기존 smooth profile과
동일하게 유지했다. Bistro와 Minecraft에서 geometry 관통 없이 O-1X 480프레임 및 정확한
60 FPS 재생을 검증했다.

이 작업은 알고리즘 변경이 아니라 이동이 시각적으로 명확한 camera-motion reference
조건을 확보하기 위한 프로토콜 보강이다.

---

# 28. Wide Camera Supersample Reference 및 CGVQM-2 측정

## 28.1 목적

`O-ET2X-R`이 Standard보다 O-1X에 가깝다는 사실만으로는 다음을 구분할 수 없었다.

- 잘못된 history와 blur·ghosting이 줄어든 것인지
- temporal sample accumulation 자체를 잃은 것인지

이를 구분하기 위해 `flythrough-wide-yaw-360`에서 동일 pose의 supersample
spatial-reference를 만들고 세 mode를 비교했다.

Reference 조건:

- 2× 선형 해상도
- 한 출력 frame 안에서 3×3 subpixel grid
- 각 sample 8×MSAA
- 한 출력 frame 동안 장면 상태 고정
- temporal history 미사용

이 reference는 현재 frame의 spatial-reference proxy이며 temporal ground truth나
path-traced 절대 정답은 아니다.

## 28.2 전체 480프레임 결과

RGB MAE는 낮을수록 reference에 가깝다.

| Scene | Mode | RGB MAE | PSNR | Luma SSIM | Edge/reference |
| --- | --- | ---: | ---: | ---: | ---: |
| Bistro | `O-1X` | 1.577217 | 35.7525 | 0.981365 | 1.005293 |
| Bistro | `O-T2X-R` | 2.045134 | 33.9554 | 0.970465 | 0.961248 |
| Bistro | `O-ET2X-R` | 1.652512 | 35.3674 | 0.979548 | 0.981994 |
| Minecraft | `O-1X` | 1.330643 | 33.6656 | 0.975452 | 1.007587 |
| Minecraft | `O-T2X-R` | 1.577457 | 33.3814 | 0.968138 | 0.944279 |
| Minecraft | `O-ET2X-R` | 1.331066 | 33.9039 | 0.974925 | 0.970137 |

`O-ET2X-R`의 reference RGB MAE는 Standard보다 다음만큼 낮았다.

- Bistro: 19.20% 감소
- Minecraft: 15.62% 감소

반면 O-1X와 비교하면 다음과 같다.

- Bistro: O-1X보다 4.77% 높음
- Minecraft: O-1X보다 0.03% 높음

따라서 ET2X-R은 Standard의 넓은 history 오차와 blur를 줄였지만, O-1X를 일관되게
넘는 temporal supersampling 품질을 확보했다고 보기는 어려웠다.

## 28.3 CGVQM-2 결과

중앙 motion 180프레임과 motion→still transition 30프레임을 서로 분리해 평가했다.
CGVQM 점수는 높을수록 reference에 가깝다.

| Scene | Window | O-1X | O-T2X-R | O-ET2X-R | ET − Standard | ET − 1X |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Bistro | central motion | 96.9816 | 94.1330 | 96.6804 | +2.5474 | -0.3011 |
| Bistro | transition | 94.4109 | 95.1268 | 94.5747 | -0.5521 | +0.1638 |
| Minecraft | central motion | 97.5651 | 95.9865 | 97.5224 | +1.5360 | -0.0427 |
| Minecraft | transition | 93.4093 | 94.6468 | 93.7529 | -0.8939 | +0.3436 |

중앙 motion에서는 ET2X-R이 Standard보다 높고 O-1X에 매우 가까웠다. 반면 정지 전환
구간에서는 Standard가 가장 높았다. 즉 우위는 장면의 motion phase에 따라 바뀌었다.

## 28.4 Wide Camera 결론

> 현재 ET2X-R은 중앙 camera motion에서 Standard T2X의 넓은 history 오차와 blur를
> 줄이는 방향을 보였지만, O-1X보다 일관되게 우수하지 않아 temporal supersampling 효과를
> 충분히 유지한다고 주장할 수 없다.

이 결과를 근거로 바로 전체 8-case를 확대하지 않고, 얇은 구조에서 history sample 기회를
늘리는 current-edge candidate expansion을 추가로 검토했다.

---

# 29. Filtered 1/4 Downsample-Upsample 후보 확장

3×3 dilation은 후보 수와 GPU 비용을 크게 증가시켰다. 교수님이 제안한 간소화된
downsampling-upsampling 개념을 검토하기 위해 다음 FilteredQuarter 방식을 별도
ablation으로 구현했다.

```text
Full-resolution raw candidate mask
        ↓
유효 4×4 block 평균으로 quarter R8 mask 생성
        ↓
half-pixel bilinear upsample
        ↓
threshold 0.25
        ↓
candidate compact 및 indirect resolve
```

Nearest-neighbor는 사용하지 않았다. Candidate-Jitter와 document profile 각각에서
`None`, `3×3`, `FilteredQuarter`를 비교했다.

초기 engineering smoke에서는 Filtered가 3×3보다 후보 증가율이 작았지만 mask pass가
오히려 더 비쌌다. 다만 이후 체계적 코드 감사에서 초기 구현이 원래 raw candidate를
일부 삭제하는 결함이 발견됐다. 따라서 초기 Filtered 후보·품질·성능 수치와 관련 결론은
최종 연구 근거에서 제외했다.

---

# 30. ARM Dual Filtering 기반 Candidate Expansion Adaptation

## 30.1 연구 분류

ARM SIGGRAPH 2015 *Bandwidth-Efficient Rendering*의 Dual Filtering kernel을 binary
current-edge candidate mask에 적용했다.

이는 bloom용 ARM kernel을 SMAA/TSCMAA 후보 확장에 맞춘 연구 adaptation이다. ARM 또는
Intel의 공식 SMAA 구현이라고 표현하지 않는다.

GPU pass는 다음과 같다.

1. full → half: ARM 5-tap downsample
2. half → quarter: ARM 5-tap downsample
3. quarter → half: ARM 8-tap upsample
4. half → full: ARM 8-tap upsample 및 candidate compact

공개 자료와 대응하는 부분:

- downsample: center weight 4 + diagonal weight 1, 전체 합 8
- upsample: axis weight 1 + diagonal weight 2, 전체 합 12
- linear filtering 및 clamp

연구 구현 가정:

- full→half→quarter→half→full의 두-level pyramid
- half-pixel 좌표 규칙
- R8_UNORM intermediate
- threshold 0.25
- raw current-edge mask와 reconstruction의 합집합

## 30.2 Raw candidate 보존

첫 reconstruction-only 구현은 선택된 raw 후보를 약 43~44%만 남겨 expansion이 아니라
erosion에 가까웠다. 이를 다음과 같이 수정했다.

```text
finalCandidate = rawCandidate OR dualFilterReconstruction >= 0.25
```

수정 후 raw 후보를 보존하면서 주변 candidate만 추가하도록 만들었다.

## 30.3 Bistro·Minecraft 결과

- 후보 coverage: raw 대비 약 1.49~1.69배
- ARM mask 비용: 약 0.133ms
- 3×3 mask보다 약 2.94~2.96배 비쌈
- Candidate-Jitter 품질 개선은 작았음
- Document profile은 장면에 따라 악화됨

따라서 Bistro와 Minecraft 결과만으로 ARM 방식의 품질·성능 우위를 확인할 수 없었다.

---

# 31. San Miguel 실제 얇은 Geometry 측정

기존 절차적 thin-lines 장면이나 미완성 Power Plant 대신, texture와 실제 3D geometry가
있는 San Miguel 2.1 장면에서 얇은 의자·테이블 다리·식생 가지를 평가했다.

비교 구성:

- None
- 정확한 3×3 dilation
- FilteredQuarter
- ARM Dual Filter

두 profile:

- Document
- Candidate-Jitter

San Miguel `yaw-fast-360` frame 60~119, 총 60프레임에서 같은 pose의 supersample
spatial-reference와 비교했다.

## 31.1 ARM 결과

- 전체 화면 reference MAE: None보다 약 10.58~10.79% 감소
- 얇은 의자 ROI reference MAE:
  - Document: 9.44% 감소
  - Candidate-Jitter: 13.10% 감소
- 같은 ROI의 3×3:
  - Document: 9.62% 감소
  - Candidate-Jitter: 14.46% 감소
- ARM mask 비용: 약 0.133ms
- San Miguel에서도 3×3보다 약 2.75배 비쌈

실제 얇은 geometry에서 current-edge 확장 자체의 효과는 확인됐지만, ARM kernel은
3×3보다 품질이 더 좋지 않았고 비용은 훨씬 컸다.

따라서 ARM Dual Filter는 기능적 ablation으로 보존하고 최종 개선안이나 formal 확대
대상으로 채택하지 않았다.

---

# 32. SMAA T2X / TSCMAA-inspired 구현 체계적 코드 감사

## 32.1 감사 목적

기능 추가가 누적되면서 다음 항목을 Git 계보, 공식 문서, shader/API 연결과 실제 GPU
검증으로 다시 확인했다.

- Original SMAA 경로가 분리 보존됐는지
- Adaptive SMAA의 기존 대비별 탐색 규칙이 유지되는지
- Standard SMAA T2X가 공식 jitter·subsample·resolve를 사용하는지
- TSCMAA-inspired core가 Intel 공개 문서의 확인 가능한 항목에 대응하는지
- 구현 가정과 공식 확인 항목이 구분돼 있는지
- history·reprojection·candidate·indirect dispatch resource lifecycle이 올바른지
- 기존 demo와 연구 자동화가 정상 동작하는지

## 32.2 원본성 판정

- Temporal 연구의 SMAA baseline 핵심 7개 파일은 GameTechDev/CMAA2 원본과 Git blob이
  일치했다.
- 현재 파일은 연구 기능을 위해 수정됐으므로 물리적으로 pristine 상태는 아니다.
- `SpatialSearch::Original`과 `AdaptiveContrast`가 별도 축으로 분리돼 Original 실행
  경로는 조건부로 보존돼 있다.
- Adaptive의 대비 구간과 탐색 범위도 기존 구현 그대로 유지됐다.
- CMAA2 demo에는 계측·장면·camera profile이 크게 추가됐지만 기존 scene, AA mode,
  benchmark와 render 기능을 삭제·대체한 훼손은 확인되지 않았다.

## 32.3 공식 SMAA T2X 대응

| 항목 | 판정 |
| --- | --- |
| 2-frame jitter | 공식 SMAA와 대응 |
| T2X subsample index | 공식 `{1,1,1,0}`, `{2,2,2,0}` 사용 |
| current/history resolve | 공식 `SMAAResolvePS` 사용 |
| no-reprojection 0.5 blend | `O-T2X`에서 대응 |
| camera velocity reprojection | `O-T2X-R`에서 지원 |
| object motion velocity | 미지원 |

따라서 정확한 표현은 다음과 같다.

> 공식 SMAA T2X resolve를 DX11 wrapper에 연결하고 depth와 camera matrix 기반의
> camera-motion reprojection을 제공한다.

현재 `-R` mode를 object motion까지 지원하는 완전한 dynamic-scene reprojection으로
표현하면 안 된다.

## 32.4 Intel TSCMAA 공개 문서 대응

확인된 core 항목:

- edge 후보만 temporal 처리
- candidate compact 및 indirect dispatch
- depth와 camera matrix 기반 history coordinate reprojection
- 5-tap Hermite/Catmull–Rom 계열 history sampling
- YCoCg variance clipping
- candidate history weight 0.8
- 비후보 history weight 0
- final resolve를 다음 frame history로 feedback
- edge threshold 1/22
- non-dominant removal 기본값 0.5

다만 Intel PDF에는 exact candidate-selection shader, 5-tap 좌표 세부식, variance
clipping의 세부 box 식이 공개돼 있지 않다. 현재 구현은 공식 원본 포팅이 아니라
Intel 공개 문서에 부합하도록 만든 **document-based SMAA adaptation**이다.

## 32.5 성능 구조의 한계

Intel TSCMAA는 CMAA edge 후보 중심으로 temporal 작업을 수행한다. 현재 SMAA adaptation은
다음 full-screen 작업이 이미 존재한다.

1. SMAA 1X spatial pass
2. 별도 luma edge extraction
3. candidate compact와 indirect resolve
4. spatial copy와 history feedback

따라서 temporal candidate가 줄어도 Standard T2X보다 자동으로 빨라지지 않는다. 실제
기존 측정에서 ET2X가 Standard보다 느렸던 현상은 이 중복 구조와 일치한다. 향후 성능
개선에는 SMAA spatial edge와 temporal candidate 생성의 중복 제거 또는 pass fusion이
필요하다.

---

# 33. 감사에서 발견한 FilteredQuarter 결함

수정 전 FilteredQuarter shader는 다음 조건만 사용했다.

```text
reconstructed >= 0.25
```

따라서 주변 후보를 추가하면서도 원래 raw edge 후보 일부를 지웠다.

San Miguel 기존 GPU mask 재분석 결과:

| Profile | raw 유실 발생 frame | frame당 평균 유실 | 최대 유실 |
| --- | ---: | ---: | ---: |
| Document | 60/60 | 23,395.683 pixel | 58,171 pixel |
| Candidate-Jitter | 60/60 | 23,362.467 pixel | 58,041 pixel |

이는 순수한 candidate expansion이 아니므로 수정 전 FilteredQuarter 열과 관련 pair·품질·
성능 결론은 최종 연구 근거로 재사용하지 않는다. None·3×3·ARM mode 자체 결과는 이
결함의 영향을 받지 않는다.

수정 내용:

```text
finalCandidate = rawCandidate OR reconstructed >= 0.25
```

- GPU upsample pass에 full-resolution raw mask SRV 연결
- shader에서 raw와 reconstruction의 합집합 적용
- Python CPU mirror에도 동일한 union 적용
- Filtered 및 ARM 분석기에 raw 후보 유실 hard-fail 추가

---

# 34. 수정된 FilteredQuarter 재측정

## 34.1 조건

- GPU: RTX 3060 Ti
- DirectX 11, Release x64
- 해상도: 1920×1017
- SMAA Ultra, VSync Off
- 장면: San Miguel
- camera: `yaw-fast-360` frame 60~119
- 품질: mode당 60프레임
- independent final capture: 2회
- mask capture: 1회
- 성능: 300-frame warm-up + 60-frame 측정 × 3회
- timing candidate readback: Off
- 후보 수: 별도 readback-On 60-frame 실행

## 34.2 Correctness와 결정성

- 두 profile 모두 raw 후보 유실 최대: 0 pixel
- 3×3 GPU/CPU exact max-filter mismatch: 0 pixel
- Filtered GPU/CPU 최대 mismatch: 0.010447%
- 독립 반복 final PNG 360장 SHA-256 mismatch: 0장
- 실제 불일치 픽셀: 0개
- 최대 채널 차이: 0

수정된 FilteredQuarter가 원래 edge 후보를 보존하면서 주변 후보를 추가한다는 핵심
불변조건을 통과했다.

## 34.3 Full-frame spatial-reference 결과

| Profile | None | 3×3 | Filtered | 3×3 vs None | Filtered vs None | Filtered vs 3×3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Document | 2.391437 | 2.140196 | 2.144116 | -10.506% | -10.342% | +0.183% |
| Candidate-Jitter | 3.074070 | 2.702365 | 2.744453 | -12.092% | -10.722% | +1.557% |

## 34.4 얇은 실제 geometry ROI 결과

| Profile | None | 3×3 | Filtered | 3×3 vs None | Filtered vs None | Filtered vs 3×3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Document | 5.791908 | 5.235016 | 5.247365 | -9.615% | -9.402% | +0.236% |
| Candidate-Jitter | 6.799291 | 5.816087 | 5.905017 | -14.460% | -13.152% | +1.529% |

3×3과 Filtered 모두 None보다 reference 오차를 줄여 current-edge expansion 가설을
지지했다. 그러나 수정된 Filtered도 3×3보다 품질이 좋지는 않았다.

## 34.5 후보 수와 GPU 비용

| Profile | 3×3 후보 배수 | Filtered 후보 배수 | Filtered 후보 변화 | 3×3 mask | Filtered mask | Filtered mask 변화 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Document | 2.364× | 2.036× | -13.897% | 0.048287ms | 0.068289ms | +41.423% |
| Candidate-Jitter | 2.364× | 2.036× | -13.897% | 0.048151ms | 0.068267ms | +41.777% |

| Profile | 3×3 SMAA | Filtered SMAA | Filtered 변화 |
| --- | ---: | ---: | ---: |
| Document | 0.474419ms | 0.496879ms | +4.734% |
| Candidate-Jitter | 0.461198ms | 0.485046ms | +5.171% |

Filtered는 3×3보다 후보를 약 13.9% 적게 선택했지만, downsample과 full-resolution
bilinear reconstruction의 두 pass 비용 때문에 mask와 SMAA 전체가 더 느렸다.

---

# 35. 후보 확장 방식의 현재 판정

## 35.1 3×3 Dilation

- 가장 단순한 exact max-filter
- San Miguel의 얇은 실제 geometry에서 reference 오차 개선
- Filtered와 ARM보다 reference 품질이 근소하게 우수
- Filtered와 ARM보다 mask 비용이 낮음
- 단점은 raw 대비 candidate가 약 2.36배로 증가해 선택적 처리 범위가 넓어진다는 점

## 35.2 FilteredQuarter

- 3×3보다 후보 수는 약 13.9% 적음
- 품질은 3×3보다 근소하게 낮음
- 두 pass 비용으로 3×3보다 SMAA 전체가 약 4.7~5.2% 느림
- 기능적 ablation으로 보존

## 35.3 ARM Dual Filter

- 실제 얇은 geometry에서 expansion 효과는 확인
- 3×3보다 품질이 좋지 않음
- 4-pass mask 비용이 지나치게 큼
- pass fusion이나 타일 최적화 전에는 formal 확대하지 않음

## 35.4 최종 engineering 선택

> 현재 구현과 RTX 3060 Ti 조건에서는 정확한 3×3 dilation을 다음 연구 단계의 기본
> current-edge expansion으로 선택한다.

이는 3×3을 최종 알고리즘으로 확정했다는 의미는 아니다. 이후 object motion vector,
disocclusion과 history rejection을 추가할 때 별도 toggle로 유지해 독립 효과를 다시
측정해야 한다.

5×5와 7×7 dilation은 후보 수와 비용을 더 증가시킬 가능성이 크므로 계속 보류한다.

---

# 36. 현재 연구에서 확정된 표현과 제한

## 사용할 수 있는 표현

- 공식 SMAA T2X resolve를 DX11 wrapper에 연결했다.
- Reprojected mode는 depth와 camera matrix 기반 camera-motion reprojection을 사용한다.
- Intel TSCMAA 공개 문서에 부합하는 SMAA adaptation을 구현했다.
- current-edge 후보만 temporal resolve하는 edge-selective 구조다.
- 3×3, FilteredQuarter와 ARM Dual Filter는 별도의 candidate-expansion ablation이다.

## 사용하면 안 되는 표현

- Intel 공식 TSCMAA source를 완전히 포팅했다.
- 현재 구현이 Intel TSCMAA와 pixel-exact하게 동일하다.
- `-R` mode가 움직이는 물체의 object motion vector까지 처리한다.
- supersample spatial-reference가 temporal ground truth다.
- 후보 픽셀 수가 줄었으므로 GPU 성능도 반드시 개선됐다.
- 수정 전 FilteredQuarter 결과를 candidate expansion의 근거로 재사용한다.

---

# 37. 현재까지의 핵심 결론

1. `O-ET2X-R`은 Standard T2X보다 전체 화면 blur와 넓은 history 오차를 줄이는 방향을
   보였다.
2. 그러나 출력이 O-1X에 매우 가까워 temporal supersampling 효과를 충분히 유지한다고
   주장하기 어렵다.
3. Camera central motion에서는 ET2X-R이 Standard보다 reference와 가까웠지만
   motion→still transition에서는 Standard가 더 좋은 결과를 보였다.
4. 현재 ET2X의 품질은 장면과 motion phase에 의존한다.
5. Current-edge expansion은 실제 얇은 geometry의 reference 오차를 줄일 수 있다.
6. 비교한 확장 방식 중에서는 3×3이 현재 품질·비용 trade-off가 가장 좋았다.
7. 현재 edge-selective SMAA adaptation은 별도 full-screen SMAA·edge extraction·copy
   비용 때문에 Standard T2X보다 자동으로 빨라지지 않는다.
8. 독립적으로 움직이는 물체에 대한 object motion vector가 없으므로 object-motion
   ghosting은 아직 구조적으로 해결되지 않았다.

---

# 38. 다음 작업

다음 단계는 candidate expansion을 더 늘리는 것이 아니라 **object motion vector 지원
가능성을 먼저 설계·감사하는 것**이다.

확인할 항목:

1. CMAA2의 rigid object가 현재 frame과 previous frame transform을 모두 제공하는지
2. skinned mesh와 rigid mesh의 이전 vertex/object transform을 어디서 관리할 수 있는지
3. camera velocity texture에 object motion을 합성할 수 있는지
4. 새 velocity render target이 필요한지 기존 depth/velocity 경로를 확장할 수 있는지
5. history UV의 부호와 pixel/UV 단위가 현재 camera reprojection과 일치하는지
6. 새로 드러난 disocclusion 영역을 depth로 어떻게 거부할지
7. first frame, scene 변경, camera cut, resize와 object teleport 때 history를 어떻게
   초기화할지
8. object motion 지원 여부와 3×3 candidate expansion을 독립 toggle로 유지할 수 있는지

먼저 코드 구조와 resource lifecycle을 감사해 최소 구현 범위를 확정한다. 설계가 확인되기
전에는 shader나 최종 8-case 정의를 임의로 변경하지 않는다.

---

# 39. 노션에 추가할 대표 자료

## 39.1 부드러운 이동+회전 3-way GIF

```text
D:\SMAA-Research-Data\AutoBench\20260820_SmoothCameraFocused_3Way\Analysis\bistro_flythrough-smooth-yaw-360_motion_3way.gif
```

```text
D:\SMAA-Research-Data\AutoBench\20260820_SmoothCameraFocused_3Way\Analysis\minecraft_flythrough-smooth-yaw-360_motion_3way.gif
```

권장 설명:

> O-1X, Standard T2X-R, Edge-selective ET2X-R을 동일한 부드러운 이동+회전 경로에서
> 비교한다. ET2X-R은 Standard보다 화면 변화가 O-1X에 가깝지만, 이것이 고스팅 감소인지
> temporal supersampling 손실인지는 reference 분석과 함께 판단해야 한다.

## 39.2 Wide camera spatial-reference 비교

```text
D:\SMAA-Research-Data\AutoBench\20260827_WideCameraReference_Formal\Analysis\bistro\reference_comparison_sheet.png
```

```text
D:\SMAA-Research-Data\AutoBench\20260827_WideCameraReference_Formal\Analysis\minecraft\reference_difference_x4_sheet.png
```

권장 설명:

> 이동 약 3.72m와 부드러운 360° yaw가 결합된 경로에서 O-1X, Standard T2X-R,
> ET2X-R을 supersample spatial-reference와 비교한다. 중앙 motion에서는 ET2X-R이
> Standard의 넓은 history 오차를 줄였지만 O-1X보다 일관되게 우수하지는 않았다.

## 39.3 San Miguel 얇은 실제 geometry 비교

```text
D:\SMAA-Research-Data\AutoBench\20260827_080226\Analysis-Postfix-SanMiguel-Thin-ROI\sanmiguel_thin_chairs_roi_frame_00003.png
```

```text
D:\SMAA-Research-Data\AutoBench\20260827_080226\Analysis-Postfix-SanMiguel-Thin-ROI\sanmiguel_thin_chairs_roi_difference_x4_frame_00003.png
```

권장 설명:

> 실제 의자·테이블 다리와 식생 가지가 있는 San Miguel ROI에서 None, 3×3,
> FilteredQuarter와 ARM Dual Filter를 비교한다. 후보 확장 방식 모두 None보다 reference
> 오차를 줄였지만 현재 조건에서는 3×3의 품질·비용 trade-off가 가장 좋았다.

## 39.4 Candidate mask 비교

```text
D:\SMAA-Research-Data\AutoBench\20260827_080226\Analysis-FilteredQuarter-Postfix\candidate_masks_frame_00000.png
```

권장 설명:

> Raw current-edge mask, 정확한 3×3 dilation과 수정된 FilteredQuarter mask의 coverage
> 차이를 보여준다. Filtered는 3×3보다 후보가 적지만 두-pass 비용으로 실제 SMAA 성능은
> 더 낮았다.

---

# 40. 현재 작업 상태

- 부드러운 3-way 카메라 품질 gate: 완료
- Wide 이동+회전 경로: 완료
- Wide supersample reference·CGVQM-2: 완료
- FilteredQuarter 후보 확장: 구현 완료
- ARM Dual Filter adaptation: 구현·engineering 측정 완료
- San Miguel 얇은 실제 geometry 측정: 완료
- 전체 구현 체계적 코드 감사: 완료
- FilteredQuarter raw candidate 유실 결함: 수정 완료
- 수정 후 FilteredQuarter 재측정: 완료
- 다음 기본 candidate expansion: 3×3 선택
- Object motion vector 지원 설계 감사: 다음 작업
- Object motion vector 구현 및 측정: 미진행
- Object motion + 3×3 직교 비교: 미진행
- 최종 8-case 확대 재측정: 위 단계 이후 판단
