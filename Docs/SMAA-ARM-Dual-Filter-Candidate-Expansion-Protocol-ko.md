# ARM Dual Filtering 기반 current-edge candidate 확장 프로토콜

## 1. 연구 목적

현재 TSCMAA-inspired SMAA는 선택된 current-frame edge candidate에서만 temporal
history를 사용한다. 이 구조는 넓은 camera-motion history 오차와 blur를 줄이지만,
subpixel thin geometry가 current edge mask에서 끊긴 픽셀에는 history sample 기회가
생기지 않는다.

이번 ablation은 current-edge candidate mask를 저비용으로 부드럽게 확장해 다음을
동시에 확인한다.

1. 얇은 구조 주변의 temporal candidate coverage가 증가하는가.
2. `O-1X`에 가까워진 현재 ET2X-R 출력에서 temporal sample 영향이 회복되는가.
3. 정확한 3×3 dilation보다 후보 증가와 GPU 비용의 균형이 나은가.
4. 확장 범위 증가로 ghosting 또는 blur가 다시 커지는가.

## 2. 출처와 명칭

1차 출처는 Marius Bjørge의 ARM SIGGRAPH 2015 course notes
*Bandwidth-Efficient Rendering*이다.

- ARM 공식 course notes:
  <https://developer.arm.com/cfs-file/__key/communityserver-blogs-components-weblogfiles/00-00-00-20-66/siggraph2015_2D00_mmg_2D00_marius_2D00_notes.pdf>
- ARM의 후속 mobile post-processing 설명:
  <https://developer.arm.com/community/arm-community-blogs/b/mobile-graphics-and-gaming-blog/posts/post-processing-effects-on-mobile-optimization-and-alternatives>

ARM 방식은 본래 bloom blur를 위한 multi-resolution downsample/upsample filter다. 이번
구현은 그 filter kernel을 binary current-edge candidate mask에 적용하는 연구용
adaptation이며, ARM의 SMAA/TSCMAA 공식 구현이 아니다. 이름은
`ArmDualFilter` 또는 `ARM Dual Filtering 기반 candidate expansion`으로 고정한다.

기존 `FilteredQuarter`는 다음 자체 방식이므로 그대로 보존하고 ARM 방식으로
재명명하지 않는다.

- full-resolution binary mask를 유효 4×4 block mean으로 직접 quarter resolution에 저장
- R8_UNORM 양자화
- manual bilinear로 full resolution 복원
- `>= 0.25` threshold로 compact

## 3. ARM 공식 kernel

공식 notes의 downsample kernel은 center weight 4와 네 diagonal weight 1을 합산해
8로 나눈다.

```text
D(uv, h) = (
    4 S(uv)
    + S(uv + (-h.x, -h.y))
    + S(uv + ( h.x,  h.y))
    + S(uv + ( h.x, -h.y))
    + S(uv + (-h.x,  h.y))
) / 8
```

공식 upsample kernel은 네 diagonal sample에 weight 2, 네 axis sample에 weight 1을
주어 12로 나눈다.

```text
U(uv, h) = (
      S(uv + (-2h.x,     0))
    + 2 S(uv + (-h.x,  h.y))
    +   S(uv + (    0, 2h.y))
    + 2 S(uv + ( h.x,  h.y))
    +   S(uv + ( 2h.x,     0))
    + 2 S(uv + ( h.x, -h.y))
    +   S(uv + (    0,-2h.y))
    + 2 S(uv + (-h.x, -h.y))
) / 12
```

두 kernel 모두 linear filtering과 clamp address mode를 사용한다. 가중치와 상대 sample
offset은 ARM notes 그대로 유지한다.

## 4. SMAA adaptation에서 고정하는 구현 가정

ARM notes의 pseudocode는 bloom pyramid의 level 수, application-side `halfpixel` 계산과
binary mask threshold를 고정하지 않는다. 따라서 다음 항목은 공식 사실이 아니라 이번
controlled implementation의 명시적 가정이다.

- Pyramid: full → half → quarter → half → full의 두 down/two up pass
- 각 pass의 output pixel center:
  `(dispatchPixel + 0.5) / outputDimensions`
- `halfpixel`: `0.5 / inputDimensions`
- sampler: D3D11 linear min/mag, mip point, clamp
- intermediate: R8_UNORM
- final candidate threshold: `>= 0.25`
- odd resolution: 각 level을 `ceil(width/2) × ceil(height/2)`로 생성
- 최종 full-resolution pass는 별도 mask를 만들지 않고 candidate mask 기록과 list
  compact를 함께 수행

`0.25`는 기존 FilteredQuarter와 threshold 변수를 통제하기 위한 연구 설정이지 ARM
공식 값이 아니다. 필요할 경우 후속 threshold sweep으로 분리하며 이번 첫 gate에서는
변경하지 않는다.

## 5. GPU pass 구성

| Pass | Input | Output | Kernel |
|---|---|---|---|
| Raw extraction | luma/current edge | full raw R8 | 기존 candidate policy |
| Down 0 | full raw R8 | half R8 | ARM downsample |
| Down 1 | half R8 | quarter R8 | ARM downsample |
| Up 0 | quarter R8 | half R8 | ARM upsample |
| Up 1 + compact | half R8 | full candidate R8 + list | ARM upsample + threshold |

Half texture는 Down 0 결과를 Down 1에서 읽은 뒤 Up 0 output으로 재사용한다. 각 SRV/UAV
전환 전에 D3D11 binding을 명시적으로 해제한다. Candidate counter, indirect args,
resolve와 history feedback은 기존 검증된 경로를 그대로 사용한다.

## 6. 비교 matrix

두 temporal profile에서 expansion만 변경한다.

| Profile | None | 3×3 | FilteredQuarter | ArmDualFilter |
|---|---|---|---|---|
| Candidate-Jitter | `ABL-Candidate-Jitter-R` | `ABL-Candidate-Jitter-Dilate3x3-R` | `ABL-Candidate-Jitter-FilteredQuarter-R` | `ABL-Candidate-Jitter-ArmDualFilter-R` |
| Document | `O-ET2X-R-Document` | `ABL-Document-Dilate3x3-R` | `ABL-Document-FilteredQuarter-R` | `ABL-Document-ArmDualFilter-R` |

최종 8-case semantic mode는 변경하지 않는다. 두 Arm mode는 candidate expansion만을
분리하는 ablation이다.

## 7. 검증 순서

### 7.1 구현 correctness

- Release x64 shader compile 및 실행
- lifecycle test에 두 mode 추가
- raw mask와 ArmDualFilter output을 저장
- CPU float32/linear-clamp/R8 mirror와 GPU mask 비교
- candidate count와 process count 일치
- 후보 index overflow와 화면 밖 접근 0
- 독립 clean-process 반복의 mask/final output 재현성

R8 변환과 GPU fused arithmetic 때문에 threshold 바로 주변에서 소수 차이가 날 수 있다.
정확한 mismatch 수와 threshold-boundary pixel 수를 함께 기록하며 임의로 무시하지 않는다.

### 7.2 Engineering quality gate

- 장면: Bistro와 Minecraft
- camera: 우선 `yaw-fast-360`의 동일 motion subset
- profile당 expansion 4개, 총 8 mode
- current candidate mask와 final output을 별도 clean process로 capture
- 기존 동일 pose SS-Reference가 있을 때 RGB MAE/PSNR/SSIM과 CGVQM-2 보조 평가
- O-1X, None, 3×3, FilteredQuarter 대비 temporal influence와 edge/reference 변화 기록

### 7.3 Engineering performance gate

- PNG/candidate readback Off
- raw extraction, Down 0, Down 1, Up 0, Up 1+compact, indirect resolve와 SMAA total
  GPU timestamp 분리
- 첫 gate: 60 warm-up + 120 measurement, 1회
- 통과 시: 300 warm-up + 600 measurement, 3회

`ArmDualFilter`가 3×3보다 느리더라도 품질/coverage 이득이 충분할 수 있으므로 pass 비용만
보고 즉시 폐기하지 않는다. 반대로 후보 수만 증가하고 CGVQM/temporal retention이
개선되지 않으면 성공으로 판단하지 않는다.

## 8. 첫 gate 판정 기준

다음을 모두 충족해야 formal 확대 후보로 남긴다.

1. CPU/GPU mask mirror가 허용 가능한 threshold-boundary 오차 안에서 일치
2. 두 장면 모두 None보다 candidate coverage 증가
3. 적어도 한 장면에서 1X 대비 temporal influence 또는 thin/detail reference 지표 개선
4. 3×3보다 candidate coverage가 낮더라도 품질 손실이 과도하지 않음
5. GPU 비용과 품질 변화의 tradeoff를 반복 측정으로 설명 가능
6. catastrophic ghosting, 화면 전체 blur, 떨림 또는 history lifecycle 회귀 없음

첫 gate 결과가 부정적이어도 수치와 구현 가정을 그대로 보존한다. ARM bloom의 장점이
binary edge mask expansion에 자동으로 이어진다고 가정하지 않는다.
