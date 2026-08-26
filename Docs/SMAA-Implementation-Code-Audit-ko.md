# SMAA T2X / TSCMAA-inspired 구현 체계적 코드 감사

감사일: 2026-08-27

감사 기준 commit: `1a9366b71069ca2998e301384afe03a3036a9698`

감사 branch: `codex/systematic-implementation-audit`

## 1. 최종 판정 요약

현재 구현은 **Intel TSCMAA 원본 포팅**이 아니라, 공식 SMAA T2X와 Intel TSCMAA 공개
문서의 확인 가능한 구성요소를 CMAA2의 SMAA 경로에 적용한 **문서 기반 SMAA
adaptation**이다.

- Original SMAA 1X 경로: 원본과 분리해 보존됨
- Standard SMAA T2X: 공식 SMAA의 jitter, subsample index와 resolve 식을 사용함
- Reprojected T2X: 공식 resolve를 사용하지만 velocity는 camera/depth 기반만 제공함
- TSCMAA-inspired core: compact candidate, indirect dispatch, reprojection, 5-tap
  Catmull-Rom, YCoCg clipping, 0.8 history weight와 feedback을 구현함
- Adaptive SMAA: 기존 대비 구간과 탐색 범위를 별도 spatial 축으로 보존함
- 원본 demo: pristine 상태는 아니며 연구용 계측·장면·카메라 기능이 크게 추가됨. 다만
  기존 렌더·benchmark 기능을 제거하지 않았고 frame lifecycle은 한 쌍으로 유지됨
- 발견 결함: `FilteredQuarter`가 일부 raw candidate를 지우던 문제를 실제 캡처에서
  재현했고 수정함. 수정 전 Filtered 관련 품질·성능 결론은 무효이며 재측정이 필요함

따라서 현재 상태는 **core engineering 검증 통과, FilteredQuarter formal 결과는 재측정
전 사용 금지**로 판정한다.

## 2. 감사 방법

다음 네 종류의 근거를 분리했다.

1. Git 계보와 blob 비교
2. 공식 논문·공개 문서와 shader/API 항목 대조
3. 현재 코드의 분기·resource lifecycle·pass 연결 정적 검토
4. Release x64 빌드와 RTX 3060 Ti/DX11 GPU 자동 검증

공개 문서가 설명하지 않는 exact candidate shader, 5-tap 좌표 세부, variance box 식은
공식과 동일하다고 추정하지 않았다. 해당 부분은 `확인된 요구`, `동일 계열 adaptation`,
`연구 가정`으로 나눠 판정했다.

## 3. 소스 계보와 원본성

### 3.1 SMAA baseline

`origin/baseline/original-smaa`의 SMAA 통합 파일을 2026-08-27에 다시 받은
GameTechDev/CMAA2 원본과 Git blob 단위로 비교했다. 다음 파일은 exact match였다.

| 파일 | Git blob |
|---|---|
| `SMAA.cpp` | `0c7793d0c6d75c1f3b667fc18537967a99ae8e3f` |
| `SMAA.h` | `36a6bb96e0385eee93fb1221de0e4506b4065dd8` |
| `SMAA.hlsl` | `5ffbdd50e4a5ca4afa8f9f8b0cfa438099e5213c` |
| `SMAAWrapper.hlsl` | `2b11b7b0a52d5df85aa3ef8905042abd025b178f` |
| `vaSMAAWrapper.cpp` | `b1ef3785e959ea1e21681ee33d205cb2d901dc1f` |
| `vaSMAAWrapper.h` | `79ccda15da9388be658f7a00bf2e746ad34005b4` |
| `vaSMAAWrapperDX11.cpp` | `d47e7d5746bd44959e2aa1b12fd1d3b9d2366ce0` |

즉 temporal 연구가 시작한 SMAA baseline의 출처는 추적 가능하다.

### 3.2 CMAA2 demo baseline

`CMAA2Sample.cpp`는 baseline 단계부터 현재 GameTechDev/CMAA2 upstream과 exact match가
아니다. 이는 사용자가 장면과 benchmark 환경을 편집한 동일 비교 환경이기 때문이다.
따라서 이 파일을 `pristine Intel demo`라고 부르면 안 된다. 연구의 의미는 같은 사용자
demo 환경에서 AA 구현만 바꿔 비교한다는 데 있다.

### 3.3 commit 계보

Temporal branch는 `ee0020d Import runnable original SMAA baseline`에서 시작해 다음을
순차 커밋했다.

1. Naive SMAA T2X
2. camera-reprojected SMAA T2X
3. TSCMAA-inspired prototype
4. controlled profile과 GPU diagnostics
5. Adaptive SMAA의 orthogonal integration
6. candidate·jitter·sampling·clipping·expansion ablation

Adaptive `main`도 같은 baseline에서 분기했으며 commit `1432a7b`에서 temporal branch에
별도 spatial mode로 통합됐다. 따라서 Original, Adaptive, temporal 변경이 Git 계보상
구분된다.

## 4. 원본 코드 보존 판정

### 4.1 Original SMAA

현재 SMAA 파일은 baseline 대비 수정됐으므로 `원본 파일을 물리적으로 손대지 않았다`고
말할 수는 없다. 대신 다음 방식으로 Original 동작을 분리 보존한다.

- `SpatialSearch::Original`과 `AdaptiveContrast`를 별도 설정으로 유지
- Adaptive edge metadata MRT는 `SMAA_ADAPTIVE_SEARCH` shader macro일 때만 활성화
- Original mode는 기존 edge target과 기존 maximum search 범위를 사용
- 공식 `SMAAResolvePS` 본문은 baseline과 같은 코드이며 DX11 wrapper가 이를 호출
- edge-search helper의 인자화는 Original에서 기존 상수값을 전달하고 Adaptive에서만
  contrast별 값을 전달

판정: **물리적 무수정은 아니지만 Original 실행 경로는 조건부로 보존됨.**

### 4.2 Adaptive SMAA

`main`의 구현과 현재 코드를 대조해 다음 핵심 규칙이 유지됨을 확인했다.

| Contrast | 수평·수직 | 대각선 |
|---|---:|---:|
| `<0.1` | 4 | 3 |
| `<1/3` | 8 | 최대값/2 |
| 그 외 | 최대값 | 최대값 |

현재 코드는 Adaptive mode에서만 RG8 edge + R8 metadata MRT를 만들고 Original mode는
기존 target을 사용한다. temporal mode는 spatial 설정과 별도 구조체 축으로 조립된다.

판정: **기존 Adaptive 의미를 보존한 채 temporal 축과 직교 통합됨.**

### 4.3 CMAA2 demo

`CMAA2Sample.cpp`는 baseline 대비 약 6,615줄이 추가되고 53줄이 삭제돼 연구 harness로
크게 확장됐다. 그러므로 `원본 demo 코드가 그대로다`라고 표현하면 안 된다.

정적 검토 결과 기존 scene load, CMAA2/MSAA/FXAA/SMAA, SuperSampleReference,
AutoBench와 화면 렌더 경로는 남아 있다. 기존 Catmull-Rom flythrough의 pose 계산은
`EvaluatePose`로 추출하고 기존 `CameraTick`이 이를 호출하도록 refactor됐다. `OnTick`에는
현재 `BeginFrame` 1회와 `EndAndPresentFrame` 1회만 존재한다. baseline에 있던 중복
`BeginFrame`은 공식 CMAA2 lifecycle과 profiler 정상화를 위해 제거됐다.

판정: **pristine demo는 아니지만 기존 기능을 대체·삭제한 훼손은 확인되지 않았고,
연구 자동화가 부가된 구조다.**

## 5. 공식 SMAA T2X 대응

1차 근거는 SMAA 논문과 `iryoku/smaa` 공식 HLSL이다.

| 공식 항목 | 현재 구현 | 판정 |
|---|---|---|
| 2-frame jitter `(0.25,-0.25)`, `(-0.25,0.25)` | camera subpixel Y convention을 반영해 동일 projection offset 생성 | 일치 |
| S0 `{1,1,1,0}`, S1 `{2,2,2,0}` | frame phase에 따라 동일 index 전달 | 일치 |
| current/history resolve | 공식 `SMAAResolvePS` 사용 | 일치 |
| no-reprojection 0.5 blend | `O-T2X`에서 같은 좌표 history와 0.5 결합 | 일치 |
| velocity reprojection | `O-T2X-R`에서 공식 velocity resolve 사용 | 부분 일치 |
| velocity 차이에 따른 history 감쇠 | 공식 resolve shader 그대로 사용 | 일치 |
| object motion velocity | scene object motion vector 미연결 | 미지원 |

`SMAA::reproject`는 baseline에서 `assert(false)`로 막혀 있던 DX11 미완성 함수를 원본의
주석 처리된 state/save-bind-draw-unbind 흐름에 맞춰 포팅했다. GPU velocity 진단은 정적
카메라 0, camera +right 이동의 음의 X velocity와 `historyUV=currentUV-velocity`를
검증했다.

정확한 표현은 **공식 SMAA T2X resolve를 DX11 wrapper에 연결하고 camera/depth
reprojection을 제공한다**이다. object motion vector까지 포함한 완전한 dynamic-scene
reprojection이라고 표현하지 않는다.

## 6. Intel TSCMAA 공개 문서 대응

| Intel 공개 항목 | 현재 구현 | 판정 |
|---|---|---|
| edge 후보만 temporal 처리 | 비후보는 current spatial, 후보만 indirect resolve | 일치 |
| 후보 compact + indirect dispatch | append list, indirect args, indirect CS | 일치 |
| edge threshold 기본 `1/22` | 기본값 `1/22` | 일치 |
| non-dominant removal 기본 `0.5` | 기본값 0.5 | 값 일치, 식은 adaptation |
| TAA 후보 약 50% | 장면별 측정, 강제 목표로 고정하지 않음 | 부분 일치 |
| depth와 view/projection reprojection | depth + current/previous camera matrix velocity | camera motion 범위 일치 |
| 5-tap Hermite/Catmull-Rom | 최적화 5-tap 구현 및 CPU 16-tap 오차 기록 | 계열 일치, exact 식 미확인 |
| YCoCg variance clipping | 3×3 current neighborhood의 YCoCg variance box | 계열 일치, exact 식 미확인 |
| candidate history weight 0.8 | document profile 0.8 | 일치 |
| noncandidate history weight 0 | current spatial을 그대로 유지 | 일치 |
| final output을 다음 history로 feedback | ping-pong final resolve feedback | 일치 |
| CMAA와 TAA 모두 edge candidate 중심 | full-screen SMAA 1X 후 별도 luma candidate 추출 | 구조 차이 |

### 6.1 공개되지 않은 부분

Intel PDF는 exact candidate-selection shader, 5-tap 좌표·가중치 식, variance clipping의
세부 gamma/box 식을 제공하지 않는다. 현재 `IntelFamilyNonDominant`는 공개 CMAA2의
연결 edge/local contrast 구조와 문서의 threshold/removal 기본값을 결합한 adaptation이다.
유실된 Intel 원본 shader와 동일하다고 주장할 수 없다.

Intel sample 설명 화면에는 jitter 조절 항목이 있으므로, 현재 document profile의
`no deliberate jitter`는 공개 문서에서 유일한 정답으로 확인된 설정이 아니다. 그래서
Candidate-Jitter On/Off를 ablation으로 따로 유지한 현재 구조가 타당하다.

### 6.2 성능 구조 차이

Intel 문서는 CMAA와 TAA가 edge candidate 중심으로 실행된다고 설명한다. 현재 SMAA
adaptation은 다음 일을 수행한다.

1. full-screen SMAA 1X spatial pass
2. 별도 full-screen luma edge extraction
3. candidate compact와 indirect resolve
4. current spatial copy와 history feedback

따라서 후보 resolve 픽셀이 줄어도 전체 경로가 Standard T2X보다 빨라진다고 보장할 수
없다. 기존 Bistro formal 측정에서 edge-selective가 느렸던 결과는 이 구조와 일관되며,
버그 하나만의 증거로 해석하지 않는다. 성능을 Intel TSCMAA 수준으로 개선하려면 SMAA
spatial 후보 생성과 temporal 후보 생성의 중복 제거 또는 pass fusion 같은 별도 연구가
필요하다.

## 7. ARM Dual Filtering 대응

ARM SIGGRAPH 2015 공개 notes와 shader를 대조했다.

- downsample: center weight 4 + 네 diagonal weight 1, 합계 8
- upsample: 네 axis weight 1 + 네 diagonal weight 2, 합계 12
- linear filtering + clamp

현재 kernel weight와 offset은 위 공개 방식에 대응한다. 하지만 full→half→quarter→half→
full의 level 수, half-pixel 좌표, R8_UNORM 중간 형식, threshold 0.25와 raw-mask union은
binary candidate mask에 맞춘 연구 가정이다. 따라서 명칭은 **ARM Dual Filtering 기반
candidate expansion adaptation**으로 제한한다.

## 8. 감사에서 발견한 문제

### [높음] FilteredQuarter가 expansion 불변조건을 위반

수정 전 최종 shader는 `reconstructed >= 0.25`만 사용했다. San Miguel의 기존 실제 GPU
mask를 다시 분석한 결과:

- Document: 60/60 frame에서 raw 후보 유실
- Candidate-Jitter: 60/60 frame에서 raw 후보 유실
- frame당 평균 유실: 각각 23,395.683 / 23,362.467 pixel
- 최대 유실: 58,171 / 58,041 pixel

즉 주변 후보를 추가하면서 동시에 원래 edge를 지웠으므로 순수한 candidate expansion이
아니었다.

수정:

```text
finalCandidate = rawCandidate OR reconstructed >= 0.25
```

GPU shader, SRV binding, Python CPU mirror와 두 분석기의 hard-fail을 함께 수정했다. 수정 후
Bistro 3-frame GPU mask에서 raw 유실 최대 0, GPU/CPU 최대 mismatch 0.012240%로 PASS했다.

영향: 수정 전 FilteredQuarter 열, pair 비교와 이를 이용한 품질·성능 결론은 사용하지
않는다. None·3×3·ARM 자체 결과는 이 분기 결함의 영향을 받지 않는다.

### [중간] object motion vector 미지원

현재 velocity는 depth와 camera matrix로 생성한다. 카메라 이동에는 대응하지만 독립적으로
움직이는 물체의 정확한 이전 위치는 계산하지 못한다. object-motion 장면의 고스팅을
완전한 reprojection 결과라고 평가하면 안 된다.

### [중간] Intel exact candidate 식 미확보

현재 policy는 문서-family adaptation이며 공식 source 재현이 아니다. candidate/base 약
50%는 Intel sample의 기본 경험값이지 모든 장면의 correctness 조건이 아니다. 실제
장면별 비율과 비용을 그대로 기록해야 한다.

### [낮음] UI와 자원 정리 코드

- `ArmDualFilter` enum은 구현돼 있었지만 개발 UI combo가 세 항목만 노출했다. 네 번째
  항목과 통계 이름을 추가했다.
- DX11 wrapper destructor와 resize path에 null-safe delete가 중복돼 있었다. 기능 장애는
  재현되지 않았지만 소유권 흐름을 명확히 하도록 중복 호출을 제거했다.

### [정보] baseline에서 상속한 빌드 경고

Release x64는 성공했지만 `CMAA2Sample.cpp`에 C4834 한 건과 C4100 한 건이 남는다. 두
줄은 `ee0020d` baseline에서 상속된 코드다. 기본 demo 동작을 감사 중 임의 변경하지 않고
기술 부채로 기록했다. 자동 품질 캡처는 exposure adaptation을 별도로 infinity로 고정하므로
해당 dead expression이 현재 deterministic capture 설정을 바꾸지는 않는다.

## 9. 실행 검증 결과

환경: RTX 3060 Ti, DirectX 11, 1920×1017, Release x64, VSync Off. 각 명령은
`run_clean_cmaa2.ps1`로 독립 프로세스 실행했고 전후 잔류 `CMAA2.exe`는 0개였다.

| 검증 | 결과 | 산출물 |
|---|---|---|
| Release x64 build | 성공 | `Projects/CMAA2/CMAA2.exe` |
| temporal lifecycle | failure 0, PASS | `AutoBench/20260827_073636` |
| camera velocity/history UV | PASS | `AutoBench/20260827_071527` |
| final-output history feedback | mismatch 0, PASS | `AutoBench/20260827_071555` |
| Catmull-Rom GPU/CPU | PASS | `AutoBench/20260827_071558` |
| YCoCg variance clipping GPU/CPU | PASS | `AutoBench/20260827_071603` |
| static temporal stability | hash mismatch 0, PASS | `AutoBench/20260827_071659` |
| candidate removal sweep/indirect count | 두 장면 모두 PASS | `AutoBench/20260827_071711` |
| post-fix Filtered final/mask | raw 유실 최대 0, PASS | `AutoBench/20260827_071852`, `20260827_071945` |
| post-fix Filtered 16-frame perf smoke | 내부 validation PASS | `AutoBench/20260827_072150` |

Catmull-Rom 검증은 GPU shader와 CPU 5-tap의 최대 오차 0.002946258, CPU 5-tap과
separable 16-tap reference의 최대 오차 0.012019262를 기록했다. 후자는 근사 필터 자체의
오차이며 bit-identical 16-tap이라고 표현하지 않는다.

## 10. 연구 진행 판정

### 진행 가능

- 공식 SMAA T2X와 camera/depth reprojection baseline 유지
- document-based edge-selective core의 engineering 연구
- 3×3과 ARM의 기존 독립 결과 활용
- 수정된 FilteredQuarter의 새 측정

### 재측정 전 금지

- 수정 전 FilteredQuarter를 `확장 방식`의 결과로 인용
- 기존 Filtered 열을 사용해 3×3 또는 ARM 우위를 확정
- 현재 구현을 Intel 공식 TSCMAA 포팅 또는 pixel-exact 재현으로 표현
- camera reprojection 결과를 object motion까지 처리한다고 표현

다음 순서는 수정된 FilteredQuarter의 San Miguel thin-chair 품질·temporal retention과
candidate-readback-Off 반복 성능을 다시 측정하고, 그 뒤 3×3과 trade-off를 확정하는
것이다.

## 11. 1차 출처

- Intel, *Temporally Stable Conservative Morphological Anti-Aliasing (TSCMAA)*:
  <https://www.intel.com/content/dam/develop/external/us/en/documents/tscmaa-codesample-v1.pdf>
- Jimenez et al., *SMAA: Enhanced Subpixel Morphological Antialiasing*:
  <https://www.iryoku.com/smaa/downloads/SMAA-Enhanced-Subpixel-Morphological-Antialiasing.pdf>
- 공식 SMAA source: <https://github.com/iryoku/smaa>
- Intel/GameTechDev CMAA2 source: <https://github.com/GameTechDev/CMAA2>
- ARM SIGGRAPH 2015, *Bandwidth-Efficient Rendering* notes:
  <https://developer.arm.com/cfs-file/__key/communityserver-blogs-components-weblogfiles/00-00-00-20-66/siggraph2015_2D00_mmg_2D00_marius_2D00_notes.pdf>
- Playdead, *Temporal Reprojection Anti-Aliasing in INSIDE*:
  <https://github.com/playdeadgames/temporal>
