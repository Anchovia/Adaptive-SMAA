# Intel 공개 자료 기반 TSCMAA-inspired SMAA 구현 계획

## 1. 문서 목적

이 문서는 Intel TSCMAA 공개 문서와 특허, 공식 SMAA 자료로 확인할 수 있는 범위 안에서
TSCMAA의 temporal 구조를 SMAA에 적용하기 위한 확정 계획이다.

Intel TSCMAA는 본래 `CMAA + edge-selective TAA`이고 공개 sample source는 확보하지
못했다. 따라서 이 연구의 구현은 다음과 같이 부른다.

> Intel TSCMAA 공개 문서에 부합하는 SMAA adaptation

`공식 TSCMAA 포팅`, `완전한 TSCMAA 재현`, `Intel 원본 코드와 동일한 구현`이라고
표현하지 않는다.

이 문서는 기존의 복합 edge-selective temporal prototype을 최종안으로 승인하는 문서가
아니다. 현재 구현을 직교 설정으로 분해하고, 출처가 있는 동작과 연구 가정을 구분해
다시 검증하기 위한 작업 기준이다.

## 2. 출처와 증거 등급

### 2.1 우선 출처

1. Intel, *Temporal & Spatial Concurrent Morphological Anti-Aliasing*
   - <https://www.intel.com/content/dam/develop/external/us/en/documents/tscmaa-codesample-v1.pdf>
2. Intel TSCMAA 특허
   - <https://patents.google.com/patent/US20190236758A1/en>
3. Intel, *Conservative Morphological Anti-Aliasing 2.0*
   - <https://www.intel.com/content/www/us/en/developer/articles/technical/conservative-morphological-anti-aliasing-20.html>
   - 저장소의 `Projects/CMAA2/CMAA2/CMAA2.hlsl`
4. 공식 SMAA 논문과 저장소
   - <https://www.iryoku.com/smaa/downloads/SMAA-Enhanced-Subpixel-Morphological-Antialiasing.pdf>
   - <https://github.com/iryoku/smaa>

블로그나 제3자 구현은 아이디어 탐색에만 사용할 수 있으며, 문서 기반 core의 동작을
확정하는 근거로 사용하지 않는다.

### 2.2 증거 등급

| 등급 | 의미 | 결과 보고 시 표현 |
|---|---|---|
| `D` | Intel TSCMAA 문서 또는 특허에 직접 명시 | 문서로 확인된 TSCMAA 구조 |
| `S` | Intel CMAA 계열 또는 공식 SMAA에 구현·명시 | 공식 계열 자료에서 차용 |
| `A` | 공개 자료의 빈 부분을 채우는 SMAA adaptation 결정 | 본 연구의 명시적 구현 결정 |
| `X` | 품질·원인 분석용 실험 설정 | ablation 또는 진단 설정 |

코드 상수, shader 함수, UI 설정과 결과 로그에는 가능한 한 이 구분을 주석 또는 이름으로
남긴다.

## 3. 공개 자료로 확정된 TSCMAA core

| 항목 | 확정 동작 | 등급 |
|---|---|---|
| 처리 범위 | edge detection 결과 중 일부만 temporal 후보로 처리 | `D` |
| 후보 실행 | 후보 좌표를 GPU buffer로 compact | `D` |
| dispatch | 후보 수를 이용한 indirect shader dispatch | `D` |
| 재투영 | 현재 depth와 현재·이전 view/projection으로 history 좌표 계산 | `D` |
| history sampling | 5-tap Hermite/Catmull–Rom bicubic approximation | `D` |
| history 제한 | 현재 이웃을 이용한 YCoCg variance clipping | `D` |
| 후보 blend | history weight `0.8` | `D` |
| 비후보 blend | history weight `0.0`, 즉 현재 spatial AA 결과 유지 | `D` |
| feedback | 최종 resolve 결과를 다음 프레임 history로 사용 | `D` |
| edge threshold | 기본값 `1/22` | `D` |
| non-dominant removal | 기본값 `0.5` | `D` |
| 후보 비율 | CMAA edge 후보의 약 50%를 기본 목표로 하며 조절 가능 | `D` |

50%는 모든 장면에서 강제로 맞춰야 하는 quota가 아니다. 장면별 실제 후보 비율을
측정하고 그대로 기록한다.

## 4. 공개 자료만으로 확정할 수 없는 세부

다음 항목의 완전한 shader 식이나 sample code는 공개 문서와 특허에 없다.

- temporal 후보를 고르는 non-dominant edge kernel의 정확한 식과 이웃 범위
- 5-tap Catmull–Rom의 정확한 sample 좌표와 결합식
- YCoCg 변환식, 이웃 window, variance gamma와 clip 함수
- projection jitter의 사용 여부와 sample sequence
- 움직이는 물체의 object motion vector 입력 및 처리
- disocclusion을 위한 이전 depth 비교 규칙

이 항목은 추정한 구현 하나를 곧바로 “공식 방식”으로 고정하지 않는다. 독립 설정으로
격리하고, 출처·수식·기본값·검증 결과를 함께 기록한다.

## 5. 기존 계획에서 바로잡는 사항

1. 기존의 번호형 버전 이름만으로 구현을 부르지 않는다. 8개 semantic ID를 사용한다.
2. 기존 3x3 평균/최댓값 기반 후보식은 Intel 문서로 확인되지 않았다. 최종 기본 후보식이
   아니라 `ExperimentalLocalMeanMax3x3` ablation으로만 보존한다.
3. `projection jitter를 사용하지 않는다`는 내용도 Intel 문서가 직접 확정한 사실이
   아니다. selective temporal 처리와 SMAA T2X의 차이를 해결하기 위한 adaptation
   결정으로 명시한다.
4. 현재 `O-ET2X-R` prototype은 후보 선택, jitter, reprojection, history sampler,
   clipping과 weight를 동시에 포함한 복합 버전이다. 최종 controlled `O-ET2X-R`로
   간주하지 않는다.
5. 기존 복합 구현의 캡처는 디버깅 자료로만 보존하고 최종 8-case 결론에 사용하지 않는다.

## 6. 최종 8-case 의미

### 6.1 Original SMAA

| ID | 전체 이름 | Temporal 범위 | Reprojection |
|---|---|---|---|
| `O-T2X` | Original SMAA Standard T2X | full-screen | Off |
| `O-T2X-R` | Original SMAA Standard T2X with camera reprojection | full-screen | On |
| `O-ET2X` | Original SMAA edge-selective temporal, no-reprojection ablation | edge candidates | Off |
| `O-ET2X-R` | Original SMAA TSCMAA document-based adaptation | edge candidates | On |

`O-ET2X-R`이 Intel 문서 기반 adaptation의 중심 case다. `O-ET2X`는 reprojection 효과를
분리하기 위한 연구용 ablation이며 공식 TSCMAA 동작이라고 부르지 않는다.

### 6.2 Adaptive SMAA

| ID | 전체 이름 | Temporal 범위 | Reprojection |
|---|---|---|---|
| `A-T2X` | Adaptive SMAA Standard T2X | full-screen | Off |
| `A-T2X-R` | Adaptive SMAA Standard T2X with camera reprojection | full-screen | On |
| `A-ET2X` | Adaptive SMAA edge-selective temporal, no-reprojection ablation | edge candidates | Off |
| `A-ET2X-R` | Adaptive SMAA TSCMAA document-based adaptation | edge candidates | On |

Adaptive 4개는 Original 4개와 TSCMAA-inspired core 검증이 끝난 뒤에만 구현한다.

## 7. 설정 구조

AA mode 하나에 여러 동작을 숨기지 않고 다음 축을 독립 설정으로 만든다.

| 설정 | 값 |
|---|---|
| `SpatialMethod` | `Original`, `Adaptive` |
| `TemporalCoverage` | `FullScreen`, `EdgeSelective` |
| `ReprojectionMode` | `Off`, `CameraDepthMatrices` |
| `JitterPolicy` | `SMAAT2X`, `None` |
| `HistorySampler` | `Bilinear`, `CatmullRom5Tap` |
| `HistoryClipping` | `Off`, `YCoCgVariance` |
| `HistoryWeight` | 실수 값; document profile은 `0.8` |
| `CandidatePolicy` | `AllBaseEdges`, `IntelFamilyNonDominant`, `ExperimentalLocalMeanMax3x3` |

일반 UI에서는 8개 semantic case만 노출하고, 개발용 ablation UI에서 세부 설정을
변경한다. 실행 로그와 결과 폴더에는 semantic ID뿐 아니라 위 설정값 전체를 기록한다.

## 8. projection jitter에 대한 확정 방침

공식 SMAA T2X는 두 subpixel jitter 위치와 대응하는 subsample index를 사용한다. 반면
Intel TSCMAA 문서는 비후보의 history weight를 `0.0`으로 두어 현재 spatial 결과를
그대로 출력한다고 설명하며, 별도 projection jitter 정책은 공개하지 않는다.

전체 화면을 SMAA T2X 방식으로 jitter한 상태에서 비후보가 현재 프레임만 출력되면,
비후보 픽셀이 두 jitter 위치를 번갈아 보여 정지 화면도 떨릴 수 있다. 실제 기존 복합
구현에서 이 2-frame 진동을 확인했다.

따라서 기본 profile은 다음과 같이 고정한다.

- Standard `O-T2X`, `O-T2X-R`: 공식 SMAA T2X jitter와 subsample index 사용 (`S`)
- Edge-selective `O-ET2X`, `O-ET2X-R`: deliberate T2X projection jitter를 사용하지 않고
  현재 SMAA spatial 결과에 selective temporal filtering 적용 (`A`)

두 계열의 최종 비교는 서로 다른 원 알고리즘 profile의 비교다. 그러므로 그 결과를
`edge 후보 선택 하나만의 효과`라고 표현하지 않는다.

edge 선택의 독립 효과는 최종 8-case 밖의 matched ablation으로 별도 확인한다. 이때
full-screen과 edge-selective 양쪽 모두 `JitterPolicy=None` 및 동일 sampler, clipping,
weight를 사용한다. jitter를 유지한 edge-selective 방식은 떨림 진단용 `X` 설정으로만
남기며, 문서에 없는 unjitter/reconstruction pass를 임의로 추가하지 않는다.

## 9. temporal 후보 선정 방침

### 9.1 base edge

document profile의 후보 검출은 SMAA spatial pass와 별도인 full-resolution compute
단계에서 수행한다.

- 현재 SMAA luma edge shader와 동일한 luma 계수 `(0.2126, 0.7152, 0.0722)` 사용 (`S`)
- gamma-corrected color에서 인접 픽셀 luma 차이 계산 (`S`)
- base edge threshold 기본값 `1/22` 적용 (`D`)
- base edge 수를 별도 counter에 기록

별도 검출 비용이 생기므로 candidate extraction GPU 시간을 독립 측정한다. SMAA edge
texture만 재사용하면 SMAA Ultra threshold `0.05`를 이미 통과한 edge만 남아 Intel
기본값 `1/22`를 정확히 적용할 수 없으므로 document profile의 기본 경로로 사용하지
않는다.

### 9.2 non-dominant edge 제거

Intel TSCMAA는 기본 조절값 `0.5`를 공개하지만 정확한 kernel은 공개하지 않았다. 기본
`IntelFamilyNonDominant` 정책은 다음 근거로 제한해 구현한다.

- Intel CMAA2 공식 source의 방향별 local-contrast 구조를 출발점으로 사용 (`S`)
- 중심 edge strength에서 양 끝점에 연결된 **수직 방향 edge** 최댓값에 removal amount를
  곱한 값을 빼고 base threshold와 비교하는 형태로 격리 (`A`)
- 기본 removal amount는 `0.5` (`D`)
- kernel 좌표, 경계 처리와 식을 shader 주석 및 실험 로그에 그대로 기록

이 식은 유실된 TSCMAA sample과 동일하다고 주장하지 않는다. 공개된 Intel 계열 구조와
TSCMAA API 의미를 결합한 adaptation이다.

검증용 정책은 다음과 같이 유지한다.

- `AllBaseEdges`: non-dominant 제거 전 모든 base edge를 temporal 후보로 사용
- `IntelFamilyNonDominant`: document profile 기본 후보 정책
- `ExperimentalLocalMeanMax3x3`: 기존 구현 보존용 ablation

후보 정책 승인 조건은 다음과 같다.

1. `removal=0`에서 후보 수가 base edge 수와 일치
2. removal amount 증가 시 후보 수가 증가하지 않음
3. 후보 buffer에 중복 좌표·범위 밖 좌표·overflow가 없음
4. 정지 및 동적 대표 장면에서 base edge/후보 mask를 육안 확인
5. 후보/base-edge 비율을 기록하고 Intel 문서의 약 50%와 비교

50%에 맞추려고 프레임별 상위 N개를 강제로 고르거나 threshold를 자동 보정하지 않는다.

## 10. history sampling과 clipping 방침

### 10.1 Catmull–Rom 5-tap

5-tap 사용 자체는 문서 확정 사항이지만 정확한 좌표·가중치는 미공개다. 구현은 독립
함수와 toggle로 격리하고 다음 검증을 통과해야 한다.

- 상수 texture에서 정확히 같은 값을 반환
- 모든 유효 fractional UV에서 weight 합이 1
- 좌우·상하 대칭성 확인
- clamp sampler를 사용해 화면 경계에서 범위 밖 접근 방지
- CPU 16-tap Catmull–Rom reference와 UV grid 비교 후 max error와 RMSE 기록

검증 전에는 `CatmullRom5Tap`을 document core 완료 항목으로 표시하지 않는다.

### 10.2 YCoCg variance clipping

YCoCg variance clipping 사용은 문서 확정 사항이지만 세부식은 adaptation이다.

- 현재 spatial 결과의 3x3 이웃 사용 (`A`)
- YCoCg 변환식, 평균·분산 계산식과 `gamma`를 코드 및 로그에 명시
- 기본 `gamma=1.0`은 adaptation 기본값이며 ablation 가능
- history가 variance box 내부이면 유지
- outlier는 유한한 값으로 box 안에 제한
- 상수 이웃에서는 NaN/Inf 없이 상수 결과 유지

clipping 전후 history와 clip delta를 debug view로 확인할 수 있게 한다.

## 11. reprojection 범위

`CameraDepthMatrices`는 현재 depth와 현재·이전 unjittered view-projection matrix로
camera-motion history UV를 계산한다.

- 화면 밖 history 좌표는 거부
- 첫 프레임, mode 변경, scene 변경, camera teleport와 resize 시 history reset
- camera matrix와 history는 같은 프레임 순서로 갱신
- jittered matrix와 unjittered matrix를 혼용하지 않음
- static camera에서 velocity가 0에 가까운지 확인
- 알려진 카메라 이동에서 history UV 방향을 debug view로 확인

현재 renderer의 object motion vector는 연결되어 있지 않다. 따라서 움직이는 물체의
재투영을 처리한다고 표현하지 않는다. 이전 depth 비교나 object motion vector를 나중에
추가하면 별도 ablation으로 기록한다.

## 12. 확정 pipeline

`O-ET2X-R` document profile의 frame pipeline은 다음과 같다.

1. Original SMAA Ultra spatial pass 실행
2. 현재 spatial 결과를 새 history/output texture의 초기값으로 복사
3. full-resolution base luma edge detection 실행
4. `IntelFamilyNonDominant` 정책으로 temporal 후보 선정
5. 후보 좌표를 structured buffer에 compact하고 counter 기록
6. 후보 수로 `ceil(candidateCount / resolveGroupSize)` indirect argument 생성
7. `DispatchIndirect`로 후보만 resolve
   - 현재 depth와 camera matrix로 history UV reprojection
   - 유효하지 않거나 화면 밖인 history 거부
   - 5-tap Catmull–Rom history sampling
   - 현재 3x3 이웃의 YCoCg variance clipping
   - current `0.2` / clipped history `0.8` blend
8. 비후보는 2단계의 현재 spatial 결과 유지
9. 완성된 output을 화면에 복사하고 다음 프레임 history로 feedback
10. history ping-pong index 교체

`O-ET2X`는 위 pipeline에서 history UV를 동일 좌표로 사용한다. 이는 no-reprojection
ablation이다.

## 13. 계측과 debug view

성능을 왜곡하지 않는 비동기 readback 경로로 다음 값을 기록한다.

- 전체 픽셀 수
- base edge 수
- temporal 후보 수
- 후보/base-edge 비율
- reprojection 성공 수
- 화면 밖 또는 무효 history 거부 수
- temporal resolve 실행 수
- candidate extraction GPU time
- indirect argument 생성 GPU time
- selective resolve GPU time
- spatial-to-history copy GPU time
- 전체 SMAA 및 전체 frame GPU time

필수 debug view는 base edge mask, temporal candidate mask, reprojection validity,
history UV/velocity, variance clip delta다.

## 14. 구현 단계와 커밋 경계

각 단계는 Release x64 build와 최소 smoke test를 통과한 뒤 별도 커밋한다.

### 단계 0: 계획 고정

- 이 문서와 `AGENTS.md`의 용어·8-case·완료 기준 일치 확인
- 코드 변경 없음

### 단계 1: mode와 설정 직교화

- 기존 세 boolean과 복합 mode를 명시적 설정 구조로 교체
- Original 네 semantic mode를 UI와 로그에 연결
- 기존 `O-T2X`, `O-T2X-R` 출력이 바뀌지 않는 회귀 확인
- 아직 TSCMAA 품질 결론을 내리지 않음

### 단계 2: 후보 추출과 계측

- base luma edge, 세 candidate policy, compact buffer, counter 구현
- indirect argument의 0개·1개·group 경계값 검증
- debug mask와 비동기 통계 readback 구현
- 기존 prototype 기본 출력은 유지하고, 명시적 diagnostic override에서만 정책을 바꿔 확인

### 단계 3: selective resolve 골격

- `O-ET2X`, `O-ET2X-R` history ping-pong과 lifecycle 구현
- 우선 bilinear/no-clipping 설정으로 coverage와 reprojection만 검증
- 비후보가 현재 spatial 결과와 정확히 일치하는지 이미지 diff 확인
- matched full-screen/selective ablation으로 후보 선택 효과 분리

현재 구현에서는 all-pixel 진단을 `-smaaCandidateForcedCount 9999999`로 실행한다.
이는 `O-T2X`가 아니라 edge-selective pipeline의 jitter, sampler, clipping, weight와
reprojection 설정을 그대로 유지한 채 모든 픽셀을 후보로 만드는 matched diagnostic이다.

### 단계 4: 5-tap sampler — 완료

- `CatmullRom5Tap` 독립 구현
- CPU 16-tap reference test와 GPU 불변 조건 검증
- sampler 변경만 비교하는 ablation 캡처

### 단계 5: variance clipping — 완료

- YCoCg 변환과 variance clipping 독립 구현
- 상수·유효 history·outlier test와 debug view 검증
- clipping 변경만 비교하는 ablation 캡처

### 단계 6: Intel document profile 조립 — 완료

- threshold `1/22`, non-dominant `0.5`
- candidate compaction + indirect dispatch
- depth/matrix reprojection
- 5-tap history sampling
- YCoCg variance clipping
- 후보 history weight `0.8`, 비후보 `0.0`
- 최종 output history feedback

이 단계까지 모든 검증표가 통과해야 `O-ET2X-R core 구현 완료`로 표시한다.

### 단계 7: lifecycle·성능 smoke — 내부 pass 계측 완료

- 첫 프레임, mode/scene/resize/teleport reset
- 0 candidate와 최대 candidate stress
- 동일 장면 반복 실행 및 GPU 오류 확인
- 각 pass timer와 candidate counter가 성능 캡처를 과도하게 방해하지 않는지 확인

### 단계 8: Original 네 case 본 측정

- `O-T2X`
- `O-T2X-R`
- `O-ET2X`
- `O-ET2X-R`

동일 장면·경로·해상도·fixed timestep에서 품질과 성능을 측정한다. PNG 저장은 품질
캡처에서만 사용하고 성능 측정에서는 끈다.

### 단계 9: Adaptive 통합

Original 네 case 검증 이후 `main`의 Adaptive SMAA를 결합해 `A-*` 네 case를 만든다.
Original과 같은 조건으로 측정해 최종 8-case 표를 작성한다.

## 15. 완료 판정표

다음 항목이 모두 통과하기 전에는 `TSCMAA-inspired core 완료`라고 표현하지 않는다.

- [x] edge threshold `1/22` 적용 및 로그 기록
- [x] non-dominant removal `0.5` 적용 및 후보 정책 출처/식 기록
- [x] base edge 수와 temporal 후보 수 측정
- [x] 후보 compact buffer 중복·overflow 검증
- [x] indirect dispatch count 검증
- [x] depth 및 현재·이전 matrix reprojection 검증
- [x] 5-tap Catmull–Rom reference 검증
- [x] YCoCg variance clipping 불변 조건 검증
- [x] 후보 history weight `0.8` 설정 및 resolve 경로 연결
- [x] 비후보 history weight `0.0`, 즉 current spatial 유지 픽셀 검증
- [x] 최종 output의 history feedback
- [x] 첫 프레임·mode·scene·명시적 camera-cut·resize reset
- [x] static camera 떨림 없음
- [x] object motion 미지원 사실 명시
- [x] 각 SMAA 내부 pass GPU time과 후보 비율 기록 가능
- [x] Release x64 build 및 동적 장면 engineering smoke test

## 16. 결과 해석 원칙

- 최종 8-case 비교와 원인 분리용 ablation을 구분한다.
- Standard T2X와 edge-selective document profile의 차이를 모두 `edge 선택 효과`로
  단정하지 않는다.
- 후보 수 감소만으로 성능 향상이라고 결론내리지 않고 실제 pass 및 frame GPU time을 본다.
- 정지 스크린샷만으로 temporal 품질을 판단하지 않고 연속 프레임·영상으로 ghosting,
  shimmer, crawling, flicker, blur와 disocclusion을 확인한다.
- camera-motion reprojection을 object-motion reprojection이라고 부르지 않는다.
- 공개되지 않은 식은 adaptation 또는 ablation이라고 표시한다.
- 예상과 다른 결과도 제외하지 않는다.

## 17. 현재 시점의 다음 작업

**단계 1~6의 직교 설정 분리, 개별 shader 검증과 Intel document profile 조립을
완료했다.**

- Original 네 semantic mode를 UI, 로그와 deterministic capture에 연결
- `TemporalCoverage`, `ReprojectionMode`, `JitterPolicy`, sampler, clipping,
  candidate policy와 history weight를 명시적 설정으로 분리
- `O-ET2X` no-reprojection ablation 실행 경로 추가
- threshold `1/22`인 별도 full-resolution base luma edge 검출 구현
- `AllBaseEdges`, `IntelFamilyNonDominant`, `ExperimentalLocalMeanMax3x3` 정책 분리
- candidate compact buffer와 indirect process/group count를 비동기 staging buffer로 readback
- base edge와 selected candidate R8 debug mask 및 개발 UI 구현
- `IntelFamilyNonDominant`, Catmull-Rom 5-tap, YCoCg variance clipping, history weight
  0.8을 edge-selective document profile의 기본값으로 조립
- 이전 `ExperimentalLocalMeanMax3x3 + Bilinear + Clipping Off` skeleton은 명시적
  diagnostic override로 보존
- Release x64 build 및 세 정책 engineering smoke capture 통과

### 17.1 단계 2 engineering smoke 결과

2026-07-29, 1920×1017, 같은 deterministic 프레임에서 확인한 구현 검증 값은 다음과 같다.
이 값은 한 프레임의 smoke 결과이며 최종 품질·성능 결과가 아니다.

| 정책 | Base edge | Candidate | Candidate/Base | Indirect process |
|---|---:|---:|---:|---:|
| `AllBaseEdges` | 57,354 | 57,354 | 100.000% | 57,354 |
| `IntelFamilyNonDominant` | 57,354 | 34,938 | 60.916% | 34,938 |
| `ExperimentalLocalMeanMax3x3` | 57,354 | 44,266 | 77.180% | 44,266 |

- 세 정책 모두 프로그램 종료·검은 화면·shader compile 오류 없이 자동 캡처 완료
- `CandidateCount == ProcessCount` 확인
- `AllBaseEdges`에서 `CandidateCount == BaseEdgeCount` 확인
- base/candidate debug mask를 시각 확인
- 기본 profile과 명시적 `ExperimentalLocalMeanMax3x3` override의 `O-ET2X`,
  `O-ET2X-R` PNG SHA-256이 각각 일치해 기본 정책 회귀가 없음을 확인
- Intel 문서의 약 50%는 강제 quota가 아니므로 60.916%를 실패나 성공으로 단정하지 않음

### 17.2 단계 2 candidate boundary·safety 결과

`-smaaCandidateForcedCount` 진단 옵션으로 정확한 후보 수를 강제하고 GPU compact buffer
전체를 비동기 staging buffer로 되읽었다. 이 큰 candidate-list readback buffer는 진단
옵션이 켜진 경우에만 생성되며 일반 실행과 본 성능 측정에는 포함되지 않는다.

| 요청 후보 | 실제/기대 후보 | 실제/기대 group | 중복 | 범위 밖 | Overflow | 결과 |
|---:|---:|---:|---:|---:|---:|---|
| 0 | 0 / 0 | 0 / 0 | 0 | 0 | 0 | PASS |
| 1 | 1 / 1 | 1 / 1 | 0 | 0 | 0 | PASS |
| 63 | 63 / 63 | 1 / 1 | 0 | 0 | 0 | PASS |
| 64 | 64 / 64 | 1 / 1 | 0 | 0 | 0 | PASS |
| 65 | 65 / 65 | 2 / 2 | 0 | 0 | 0 | PASS |
| 9,999,999 | 1,952,640 / 1,952,640 | 30,510 / 30,510 | 0 | 0 | 0 | PASS |

마지막 case는 1920×1017 전체 픽셀 capacity로 clamp되며 1,952,640개 좌표를 모두
검사했다. 모든 case가 `O-ET2X`와 `O-ET2X-R` 양쪽에서 동일하게 통과했다.

진단을 끈 기본 실행은 기존과 같은 44,266 candidate와 692 indirect group을 기록했고,
변경 전 기본 `O-ET2X`/`O-ET2X-R` 캡처와 PNG SHA-256이 각각 일치했다.

### 17.3 단계 3 controlled selective resolve 결과

edge-selective 기본 profile을 `Bilinear + Clipping Off`로 바꾸고 두 설정을 실제 compute
shader 분기로 연결했다. `CatmullRom5Tap`과 `YCoCgVariance`는 독립 UI/명령줄 diagnostic
override로 보존했다. `CurrentSpatial` debug view도 추가해 resolve 입력을 별도 캡처할 수
있다.

2026-07-29, Release x64, 1920×1017, 같은 deterministic capture 조건에서 다음 네 출력을
분리했다.

1. 기본 selective resolve
2. current spatial SMAA debug view
3. selected candidate mask
4. 같은 resolve 설정으로 전체 1,952,640픽셀을 후보로 강제한 all-pixel diagnostic

마스크의 흰 픽셀을 후보로 사용해 RGB PNG를 비교한 결과는 다음과 같다. 이 결과는
coverage 구현의 engineering 검증이며 최종 품질·성능 결과가 아니다.

| Mode | 후보 픽셀 | 비후보 `selective == spatial` | 후보 `selective == all-pixel` |
|---|---:|---:|---:|
| `O-ET2X` | 44,542 | 0 mismatch / 1,908,098 | 0 mismatch / 44,542 |
| `O-ET2X-R` | 44,542 | 0 mismatch / 1,908,098 | 0 mismatch / 44,542 |

두 mode 모두 selective와 current spatial 전체 비교에서는 실제 차이 픽셀이 존재했다
(`O-ET2X` 33,556개, `O-ET2X-R` 35,798개). 따라서 0 mismatch 결과는 temporal resolve가
꺼졌기 때문이 아니라, 후보 영역만 all-pixel temporal 결과로 덮어쓰고 비후보를 current
spatial로 보존했기 때문이다.

기존 복합 prototype의 회귀도 확인했다. sampler를 `CatmullRom5Tap`, clipping을
`YCoCgVariance`로 override한 출력 SHA-256은 변경 전과 정확히 일치했다.

- `O-ET2X`: `D39F9FBD3DA57D3EAE0E648657651F9FE5B3498450045F7E6AD0A88D00B963F5`
- `O-ET2X-R`: `FCAEEE29310774501E2E3B37DEADA880A64062365974FBEBC8B8C35C2DCAF7C3`

### 17.4 temporal lifecycle 자동 검증 결과

`-smaaTemporalLifecycleTest` 진단을 추가해 다음 상태를 각 temporal draw에서 검증한다.

- wrapper frame index와 공식 SMAA core frame index 일치
- current/previous history texture가 서로 다른 ping-pong resource인지 확인
- reset 뒤 첫 프레임은 history를 읽지 않고 seed하며 `0 → 1`로 전환
- 이후 history resolve가 `1 → 0 → 1` 순서로 교대
- Standard T2X frame 0/1의 jitter가 각각 `(0.25, 0.25)`, `(-0.25, -0.25)`
- Standard T2X subsample index가 각각 `(1,1,1,0)`, `(2,2,2,0)`
- edge-selective profile의 jitter와 subsample index는 모두 0
- reprojection matrix가 유한하고 `CurrentViewProj * CurrentViewProjInv`가 identity에
  근접하는지 확인
- reset 직후 첫 reprojection frame에서 `PreviousViewProj == CurrentUnjitteredViewProj`

2026-07-29 Release x64 자동 실행에서는 다음 reset 경계를 순서대로 시험했다.

1. `O-T2X`, `O-T2X-R`, `O-ET2X`, `O-ET2X-R` mode 시작·전환
2. 알려진 camera cut에서 사용하는 명시적 history reset entry point
3. Bistro에서 Minecraft로 scene 변경 후 Bistro 복원
4. `1920×1017 → 1856×953` resize 후 원래 해상도 복원

| 항목 | 결과 |
|---|---:|
| 관측 reset | 16 |
| 완료 temporal frame | 79 |
| seed frame | 9 |
| history resolve frame | 70 |
| camera reprojection frame | 20 |
| frame/history/resource/jitter/subsample/matrix failure | 0 |
| 전체 판정 | PASS |

shader compilation과 scene 준비 중에도 rendering tick은 진행될 수 있어 완료 frame 수는
테스트의 최소 frame 수보다 많다. 자동 판정은 마지막 프레임이 seed라고 가정하지 않고,
각 reset 경계 뒤 seed counter가 실제로 증가했는지 확인한다.

진단을 끈 일반 네 mode capture를 같은 조건으로 두 번 반복했으며 네 PNG SHA-256이
실행 간 모두 일치했다. 따라서 진단 분기가 기본 출력에 영향을 주지 않음을 확인했다.

이 결과는 lifecycle과 CPU→shader matrix frame ordering의 engineering 검증이다.

### 17.5 camera-motion GPU velocity/history UV 검증 결과

`-smaaTemporalVelocityTest` 진단을 추가했다. 이 옵션에서만 `R16G16_FLOAT` velocity
texture를 staging texture로 동기 readback하며 일반 실행과 본 성능 측정에는 해당
readback resource와 stall이 포함되지 않는다.

2026-07-29, RTX 3060 Ti, DirectX 11, Release x64, 1920×1017 Bistro에서
`O-ET2X-R`의 camera-motion velocity를 다음 두 단계로 검증했다.

| 단계 | Mean velocity | Max abs | 예상 X 부호 | History UV in bounds | 결과 |
|---|---:|---:|---:|---:|---|
| 정적 카메라 | `(0.00000000, 0.00000000)` | 0.00000000 | - | 100.000% | PASS |
| 카메라 +right 0.01 m | `(-0.00512720, 0.00000000)` | 0.02040100 | 음수 100.000% | 99.405% | PASS |

두 단계 모두 1,952,640개 픽셀의 velocity가 유한했다. +right 이동에서는 유의한 X
velocity 1,952,640개가 모두 음수였고, shader resolve와 같은
`historyUV = currentUV - velocity` 식으로 계산한 좌표의 99.405%가 화면 안에 있었다.
따라서 현재 depth와 이전·현재 unjittered view-projection matrix로 생성하는
camera-motion velocity의 정적 상태, 이동 방향과 history UV 부호를 실제 GPU 출력에서
확인했다.

이 검증은 object motion vector를 검증하지 않는다. 현재 renderer에는 object motion
vector가 연결되어 있지 않으므로 움직이는 물체의 재투영 지원으로 해석하면 안 된다.

진단을 끈 일반 네 mode 캡처도 다시 실행했으며 각 PNG SHA-256이 이전 회귀 기준과
일치했다.

- `O-T2X`: `9F5BFE4BE601ED547408FE4FE1F9DC1D3F0B71C294E33880E779150359928D6C`
- `O-T2X-R`: `53C0E2A65BAA02C936A3090F26BC48DD8F568CAED2EB2EF24FB408E792BEC667`
- `O-ET2X`: `CA3AB01FD2DEF99EB21ACF7820502DCBAC57646E67A9772EA9B6F283959D9ECE`
- `O-ET2X-R`: `A0DE7204B3AA14AC409B512156DCB45D5901C3A14F5EDD0CA163B31243F7668D`

### 17.6 Catmull-Rom 5-tap GPU/CPU reference 검증 결과

`-smaaCatmullRomReferenceTest` 자동 진단을 추가했다. 이 진단은 production resolve가
호출하는 `TSCMAASampleHistoryCatmullRom5Tap` 함수를 전용 compute shader에서도 그대로
호출한다.

- 8×8 `RGBA32F` 입력: 고주파 결정론 패턴, 평면 gradient, 상수 `0.375`, 상수 `1.0`
- 16×16 GPU UV grid: `[-0.1, 1.1]`을 포함해 clamp sampler 경계와 범위 밖 좌표 확인
- CPU 5-tap mirror: HLSL과 같은 좌표·가중치·5개 bilinear sample·정규화
- CPU 16-tap reference: separable Catmull-Rom 4×4 texel 합
- CPU reference UV: 64×64, 총 4,096개

2026-07-29, RTX 3060 Ti, DirectX 11, Release x64에서 얻은 결과는 다음과 같다.

| 항목 | 결과 | 판정 |
|---|---:|---|
| cubic/effective 5-tap weight 합 최대 오차 | 0.000000119 | PASS |
| mirror symmetry 최대 오차 | 0.000000060 | PASS |
| GPU 상수 channel 최대 오차 | 0.000000238 | PASS |
| GPU shader 대 CPU 5-tap 최대 오차 | 0.002946258 | PASS |
| GPU shader 대 CPU 5-tap RMSE | 0.000403950 | 기록값 |
| CPU 5-tap 대 CPU 16-tap 최대 오차 | 0.012019262 | 기록값 |
| CPU 5-tap 대 CPU 16-tap RMSE | 0.001406755 | 기록값 |

GPU 대 CPU 5-tap 최대 허용치는 texture unit의 선형 보간 정밀도 차이를 고려한 engineering
tolerance `0.005`다. 상수 channel 보존 허용치는 `0.000020`, weight 합과 symmetry는
`0.000002`다. CPU 5-tap 대 16-tap 수치는 5-tap 근사의 특성을 기록하는 값이므로 임의의
품질 합격 threshold를 적용하지 않았다.

sampler만 바꾸는 engineering capture도 수행했다. edge-selective bilinear 출력은 기존
회귀 기준과 반복 일치했고 Catmull-Rom override에서 실제 sampler 분기를 사용하는 두
mode의 해시가 다음과 같이 변경됐다.

- `O-ET2X` bilinear: `CA3AB01FD2DEF99EB21ACF7820502DCBAC57646E67A9772EA9B6F283959D9ECE`
- `O-ET2X-R` bilinear: `A0DE7204B3AA14AC409B512156DCB45D5901C3A14F5EDD0CA163B31243F7668D`
- `O-ET2X` Catmull-Rom: `53C855E7B8232401A1F3DAAFAC8F0CFEE01EA6B7244B64625AE5A92C4C115E81`
- `O-ET2X-R` Catmull-Rom: `D7C0FA2306B42E416DBE0AA0F932B6362B6C931D3F8308BF58FB775AC71154F1`

Standard `O-T2X-R`은 override와 무관하게 기준 해시를 유지했다. 반면 four-mode capture의
첫 mode인 `O-T2X`는 override Off/Bilinear/Catmull-Rom과 무관하게 동일 명령에서도
`9F5B...`와 `74E9...` 두 해시가 관측됐다. 이는 sampler 효과가 아니라 시작
프레임/history warm-up의 기존 비결정성으로 분리하며, 캡처 도구를 보완하기 전에는
`O-T2X` 단일 프레임 hash를 deterministic 증거로 사용하지 않는다.

이로써 shader 분기, 상수 보존, weight 합, 대칭성, clamp 경계와 CPU 16-tap reference
비교를 확인했다. 다만 정확한 5-tap 좌표·가중치는 Intel 공개 문서에 없는 adaptation이므로
공식 TSCMAA 식이라고 표현하지 않는다.

### 17.7 YCoCg variance clipping GPU/CPU 검증 결과

`-smaaVarianceClippingTest` 자동 진단을 추가했다. production resolve가 호출하는
`TSCMAAVarianceClip`을 전용 8×8 compute test에서도 그대로 호출하고, 같은 3×3 통계와
segment clipping을 구현한 CPU mirror와 비교한다.

세 case는 다음과 같다.

1. 상수 current 이웃 + 큰 history outlier: 분산 0에서 current 상수를 유지하는지 확인
2. 평면 current 이웃 + variance box mean history: box 내부 history가 유지되는지 확인
3. 평면 current 이웃 + 큰 YCoCg outlier: history 거부, box 제한과 CPU 결과 확인

2026-07-29, RTX 3060 Ti, DirectX 11, Release x64 결과는 다음과 같다.

| 항목 | 결과 | 판정 |
|---|---:|---|
| 유한 GPU pixel | 192 / 192 | PASS |
| RGB→YCoCg→RGB 왕복 최대 오차 | 0.000000060 | PASS |
| 상수 이웃 최대 오차 | 0.000000000 | PASS |
| box 내부 history 최대 오차 | 0.000000030 | PASS |
| GPU shader 대 CPU reference 최대 오차 | 0.000002086 | PASS |
| GPU shader 대 CPU reference RMSE | 0.000000175 | 기록값 |
| outlier history 거부 | 64 / 64 | PASS |
| clipping box 위반 | 0 | PASS |

`gamma=1.0`, current spatial 3×3 이웃, YCoCg 변환식, mean/variance 식과 current→history
segment clipping은 공개 문서에 세부식이 없는 adaptation이다. Intel 공개 문서에서 확인한
YCoCg variance clipping 사용과 이 세부 구현을 구분한다.

temporal debug view도 다음과 같이 확장했다.

- 4: 후보 픽셀의 history before clipping
- 5: 후보 픽셀의 history after clipping
- 6: `abs(after-before) * 8` clipping delta

세 view는 `R16G16B16A16_FLOAT` debug texture 하나를 공유하며 view가 4~6일 때만
resource를 할당한다. 비후보는 검은색이고, 후보 compute thread만 값을 기록한다.
`O-ET2X-R`, YCoCg clipping On의 동일 프레임 캡처를 육안 확인했으며 해시는 다음과 같다.

- before: `D72414938562B77415FC3B779AB6026F8AF5BC5634063ED4BDB258D3784EB626`
- after: `1599A754806DD269039CDB4B109994C1117B626DE55F260F03EC42C3B1CC0430`
- delta 8×: `0142F2364732550E3F784949C7C833E6A23A99F018F8404D1D02C1E04ED4439E`

debug를 끈 기본 실행에서 `O-ET2X`와 `O-ET2X-R` 해시는 각각 기존
`CA3AB0...`, `A0DE72...` 기준과 일치했다. 따라서 선택형 debug UAV와 shader write는
기본 실행 및 본 성능 경로에 포함되지 않는다.

이 검증 다음 단계로 candidate 정책 승인과 Intel document profile 조립을 진행했으며,
결과는 17.8과 17.9에 기록한다.

### 17.8 Intel-family candidate removal sweep 결과

`-smaaCandidatePolicyValidationTest`를 추가해 `IntelFamilyNonDominant` 정책을 두 장면의
고정 카메라에서 검증했다. shadow-map update가 끝난 뒤 각 removal 값마다 GPU counter
readback을 새로 받아 다음 조건을 자동 판정한다.

- removal `0`에서 candidate 수와 base edge 수 일치
- removal 증가 시 base edge 수 고정
- candidate 수 단조 비증가
- indirect process 수와 candidate 수 일치

2026-07-29, RTX 3060 Ti, DirectX 11, Release x64, 1920×1017 결과는 다음과 같다.

| 장면 | Removal | Base edge | Candidate | Candidate/Base | Process |
|---|---:|---:|---:|---:|---:|
| Bistro | 0.00 | 211,713 | 211,713 | 100.000% | 211,713 |
| Bistro | 0.25 | 211,713 | 176,828 | 83.523% | 176,828 |
| Bistro | 0.50 | 211,713 | 148,824 | 70.295% | 148,824 |
| Bistro | 0.75 | 211,713 | 126,254 | 59.635% | 126,254 |
| Bistro | 1.00 | 211,713 | 106,423 | 50.268% | 106,423 |
| Minecraft | 0.00 | 439,615 | 439,615 | 100.000% | 439,615 |
| Minecraft | 0.25 | 439,615 | 317,055 | 72.121% | 317,055 |
| Minecraft | 0.50 | 439,615 | 229,988 | 52.316% | 229,988 |
| Minecraft | 0.75 | 439,615 | 172,143 | 39.158% | 172,143 |
| Minecraft | 1.00 | 439,615 | 129,426 | 29.441% | 129,426 |

10개 단계가 모두 PASS했다. 공개 기본값 removal `0.5`에서 후보 비율은 Bistro
70.295%, Minecraft 52.316%로 장면에 따라 달랐다. Intel 문서의 약 50%는 quota가
아니므로 Bistro를 50%에 맞추기 위해 removal을 1.0으로 바꾸거나 threshold를 자동
조정하지 않는다.

기존 전체 candidate buffer 검증에서는 중복·범위 밖·overflow가 모두 0이었고,
Intel-family mask도 engineering capture에서 육안 확인했다. 따라서
`IntelFamilyNonDominant + threshold 1/22 + removal 0.5`를 SMAA document adaptation의
candidate 정책으로 내부 승인한다. 이는 공개 문서와 Intel CMAA2의 연결 edge 구조에
근거한 adaptation 승인이지, 유실된 공식 TSCMAA shader 식의 재현 인증이 아니다.

removal override를 끈 기본 prototype 회귀에서 `O-ET2X`와 `O-ET2X-R` 해시는 기존
`CA3AB0...`, `A0DE72...`와 일치했다.

### 17.9 Intel document profile 조립·회귀 결과

2026-07-30에 검증된 구성요소를 `O-ET2X`와 `O-ET2X-R`의 기본 profile로 조립했다.

| 설정 | `O-ET2X` | `O-ET2X-R` |
|---|---|---|
| Spatial input | Original SMAA 1X | Original SMAA 1X |
| Temporal coverage | Edge-selective | Edge-selective |
| Reprojection | Off, no-reprojection ablation | Camera depth + current/previous matrices |
| Deliberate projection jitter | None | None |
| Candidate | `IntelFamilyNonDominant` | `IntelFamilyNonDominant` |
| Edge threshold / removal | `1/22` / `0.5` | `1/22` / `0.5` |
| History sampler | Catmull-Rom 5-tap | Catmull-Rom 5-tap |
| History clipping | YCoCg variance | YCoCg variance |
| History weight | `0.8` | `0.8` |

여기서 `O-ET2X-R`이 Intel 공개 문서 기반 adaptation의 중심 case이고, `O-ET2X`는
reprojection 효과를 분리하는 연구용 ablation이다. 현재 reprojection은 camera motion만
처리하며 object motion vector는 지원하지 않는다.

Release x64, DirectX 11, RTX 3060 Ti, 1920×1017에서
`-smaaOriginalFourCapture 1 1 6`을 두 번 독립 실행했다. 두 edge-selective document
profile의 PNG SHA-256은 실행 간 일치했다.

- `O-ET2X`: `86FA6CEC9A639DDDC89605663F633163E87F31F173EDBA3A057DB7961A7F4DBC`
- `O-ET2X-R`: `95F619F2BA4CE3F0828767C88341A32F0DEADD9A1A46EF8E113CA84250075F99`

동일 프레임에서 base edge 57,354개 중 34,938개(60.916%)가 후보였으며 indirect
process count도 34,938개였다. 이 값은 구현 회귀용 한 프레임 결과로 최종 품질·성능
수치가 아니다.

`ExperimentalLocalMeanMax3x3 + Bilinear + Clipping Off` diagnostic override를 적용한
캡처는 변경 전 controlled skeleton hash를 정확히 재현했다.

- `O-ET2X`: `CA3AB01FD2DEF99EB21ACF7820502DCBAC57646E67A9772EA9B6F283959D9ECE`
- `O-ET2X-R`: `A0DE7204B3AA14AC409B512156DCB45D5901C3A14F5EDD0CA163B31243F7668D`

프로필 조립 뒤 lifecycle 자동 검증도 다시 실행했다. 총 80 temporal frame에서
16 reset, 9 seed, 71 history resolve, 20 camera reprojection을 관측했고 failure는 0으로
PASS했다.

이 결과로 document profile의 기능 조립과 engineering 회귀 검증은 완료했다. 아직
`TSCMAA core 최종 완료`나 품질·성능 개선을 주장하지 않는다. 이어서 후보 추출,
indirect temporal resolve와 전체 SMAA의 GPU time을 분리하는 performance smoke를
17.10에서 진행했다.

### 17.10 Original 네 mode 내부 pass GPU performance smoke

`-smaaOriginalFourPerformanceSmoke <startSeconds> <warmupFrames> <measureFrames>`를
추가했다. 이 경로는 PNG를 저장하지 않고 VSync를 끄며 동일한 Bistro camera path와
SMAA Ultra에서 네 semantic mode를 순회한다. 엔진의 DX11 GPU timestamp-query profiler로
다음 scope를 기록한다.

- 전체 SMAA wrapper
- camera-motion velocity 생성
- Standard T2X spatial 및 temporal resolve
- edge-selective SMAA 1X spatial
- current spatial→history copy
- candidate buffer 준비, 후보 추출, indirect args 생성
- candidate temporal resolve와 최종 output copy

2026-07-30, RTX 3060 Ti, DirectX 11, Release x64, 1920×1017,
`start=1 s`, mode당 warm-up 60프레임, 측정 120프레임으로 engineering smoke를
실행했다. 모든 예상 scope가 120/120개 GPU timestamp를 반환했고 PNG는 0개였다.

| Mode | SMAA total 평균 | 주요 temporal 구성 평균 |
|---|---:|---|
| `O-T2X` | 0.151066 ms | Standard temporal resolve 0.022443 ms |
| `O-T2X-R` | 0.193399 ms | camera velocity 0.022963 ms, temporal resolve 0.035166 ms |
| `O-ET2X` | 0.312713 ms | prepare 0.031847 ms, extract 0.067900 ms, indirect resolve 0.013303 ms |
| `O-ET2X-R` | 0.343893 ms | velocity 0.022741 ms, extract 0.067729 ms, indirect resolve 0.014609 ms |

동일 동적 구간에서 두 edge-selective mode의 평균 base edge는 57,000.875개,
candidate와 process는 모두 34,670.867개로 candidate/base는 60.8251%였다.

이 값은 계측 경로의 유효성을 확인하는 단일 smoke 결과다. candidate counter의 작은
비동기 readback이 켜진 현재 경로를 포함하고, 전체 frame GPU time·FPS·반복 간 분산은
측정하지 않았다. 따라서 네 mode의 최종 성능 우열이나 개선률로 인용하지 않는다.
본 측정 전에는 counter readback On/Off overhead와 전체 frame GPU timer를 분리하고,
최소 3회 반복해야 한다.

계측 scope 추가 뒤 기본 네 mode 캡처를 다시 실행했으며 출력 SHA-256은 프로필 조립
회귀 기준과 모두 일치했다. 따라서 timer scope가 shader 출력에는 영향을 주지 않았다.

### 17.11 최종 output history feedback GPU 검증

`-smaaTemporalFeedbackTest`를 추가해 `O-ET2X-R`의 실제 DX11 texture를 동기 staging
readback했다. 이 resource와 stall은 진단이 명시적으로 활성화된 실행에서만 생성·사용되며
일반 실행과 성능 측정 경로에는 포함되지 않는다.

매 진단 frame에서 다음 두 불변 조건을 확인한다.

1. candidate resolve가 끝난 `outputHistory`와 화면 destination으로 복사된 texture의
   유효 pixel byte가 정확히 일치
2. 다음 frame의 `previousHistory` FNV-1a hash가 직전 frame에서 저장한 resolved-history
   hash와 일치

2026-07-30, RTX 3060 Ti, DirectX 11, Release x64, 1920×1017, Bistro 동적 경로에서
얻은 결과는 다음과 같다. shader 준비 중 AutoBench tick이 대기하는 동안에도 진단 draw는
계속되어 최소 요구 3프레임보다 많은 33프레임이 검사됐다.

| 항목 | 결과 | 판정 |
|---|---:|---|
| 완료 frame | 33 | PASS |
| output history/destination 검사 | 33 | PASS |
| previous history/직전 resolve hash 검사 | 32 | PASS |
| staging readback 실패 | 0 | PASS |
| output history/destination mismatch byte | 0 | PASS |
| previous history hash mismatch | 0 | PASS |

따라서 최종 selective resolve 결과가 화면 출력으로 복사되는 동시에 ping-pong history에
남고, 다음 frame에서 실제 previous history로 읽히는 것을 GPU resource 내용으로
검증했다.

진단을 끈 일반 네 mode capture를 다시 실행했다. `O-T2X-R`, `O-ET2X`,
`O-ET2X-R`은 기존 회귀 hash와 일치했고 `O-T2X`는 이미 기록된 두 시작 hash 중 하나를
보였다. 따라서 feedback readback 분기는 일반 shader 출력에 영향을 주지 않았다.

### 17.12 고정 카메라 temporal 안정성 GPU 검증

`-smaaStaticStabilityTest`를 추가했다. Bistro에서 camera play time과 exposure를
고정하고 `O-ET2X`, `O-ET2X-R`를 각각 독립적으로 reset한다. diagnostic-only staging
readback으로 resolved-history FNV-1a hash를 읽고 warm-up 이후 연속 32개 hash가
byte-identical인지 확인한다.

첫 실행의 16프레임 warm-up에서는 앱 시작 직후 첫 mode인 `O-ET2X`가 32개 측정 중
7회 변했고 `O-ET2X-R`은 0회였다. mode 차이로 단정하지 않고 시작 shader·장면 안정화가
부족한 조건으로 분리했다. 연구 측정 규칙에 맞춰 warm-up을 120프레임으로 늘려 다시
실행했다.

2026-07-30, RTX 3060 Ti, DirectX 11, Release x64, 1920×1017, VSync Off,
SMAA Ultra 결과는 다음과 같다.

| Mode | Warm-up | 측정 hash | Hash 변화 | First/last | 판정 |
|---|---:|---:|---:|---|---|
| `O-ET2X` | 120 | 32 | 0 | `0xE6B9D9720906E286` / 동일 | PASS |
| `O-ET2X-R` | 120 | 32 | 0 | `0x6615D4369B223F95` / 동일 | PASS |

따라서 충분한 안정화 이후 고정 camera·scene 입력에서 두 document profile 모두
frame-to-frame byte 변화가 없었다. 이 검증은 static camera 떨림 부재를 강하게
뒷받침하지만, 움직이는 camera·object의 shimmer, ghosting, disocclusion 품질을
대신 평가하지 않는다.

이 결과로 15절의 Intel 공개 문서 기반 core 기능 체크리스트가 모두 통과했다.
`TSCMAA-inspired SMAA core 기능 검증 완료`라고 표시할 수 있으나, 공식 Intel sample
포팅이나 최종 8-case 품질·성능 연구 완료를 의미하지 않는다. 다음 단계는 전체 frame
GPU timing과 candidate counter readback overhead를 정리한 뒤 Original 네 case의
반복 본 측정을 시작하는 것이다.

### 17.13 후보 통계 readback 오버헤드 분리

edge-selective resolve가 만든 네 개의 control counter를 CPU에서 확인하는 비동기
GPU→CPU readback은 알고리즘 출력이 아니라 진단 계측이다. 이를 본 성능에서 제외할 수
있도록 `-smaaCandidateStatisticsReadback 0|1` 설정과
`-smaaCandidateReadbackOverheadTest <startSeconds> <warmupFrames> <measureFrames>`를
추가했다. forced-count 후보 경계 진단은 정확성 검증에 counter가 필수이므로 설정이
Off여도 readback을 수행한다.

2026-07-30, RTX 3060 Ti, DirectX 11, Release x64, 1920×1017, VSync Off,
SMAA Ultra, 동일 Bistro 동적 경로에서 profile당 60프레임 warm-up과 180프레임 측정으로
다음 단일 engineering smoke 결과를 얻었다.

| Profile | SMAA GPU 평균 | SMAA CPU 평균 | Counter sample |
|---|---:|---:|---:|
| `O-ET2X`, readback Off | 0.297170 ms | 0.024362 ms | 0 |
| `O-ET2X`, readback On | 0.316911 ms | 0.024772 ms | 180 |
| `O-ET2X-R`, readback Off | 0.327788 ms | 0.030301 ms | 0 |
| `O-ET2X-R`, readback On | 0.349338 ms | 0.028871 ms | 180 |

On−Off GPU 평균 차이는 `O-ET2X` 0.019740 ms(6.643%), `O-ET2X-R`
0.021550 ms(6.574%)였다. CPU 평균 차이는 각각 +0.000409 ms, -0.001430 ms로 방향이
일관되지 않았다. 이는 한 번의 짝 smoke이므로 효과 크기의 최종 통계가 아니라, 작은
counter readback도 GPU timing에 포함하면 안 된다는 구현 근거로만 사용한다.

동일한 `start=1 s`, warm-up 60프레임, 1프레임 capture를 readback Off/On으로 각각
실행했다. 알고리즘 영향을 직접 받는 두 edge-selective 결과는 각각 SHA-256이 완전히
일치했다.

- `O-ET2X`: `235A32AF21E4E2EFDBCA21878F13B4CB70447127FD43C7663F602DF27056EE7C`
- `O-ET2X-R`: `5C78117959D8AE6522EF31D0D62EFB88355ED20917D97DB0831323AE7D0D4E2C`

`O-T2X-R`도 일치했다. `O-T2X`는 이미 17.10 이전부터 기록한 실행 시작 hash
비결정성을 다시 보였으므로 readback 설정 영향의 증거로 해석하지 않는다.

이후 측정은 다음처럼 분리한다.

1. 후보 수·candidate/base 특성화: readback On
2. SMAA pass와 전체 frame timing: readback Off
3. 성능 측정과 PNG 품질 capture: 별도 실행

이제 counter readback 오버헤드 분리는 완료했다. Original 네 case의 반복 본 측정 전에
남은 계측 과제는 신뢰할 수 있는 전체 frame GPU timing 경로를 확정하는 것이다.

### 17.14 DX11 전체 frame GPU timing 수명주기 복구

기존 `WholeFrame` profiler node가 0을 반환하던 원인을 조사했다. 로컬 기준선의
`CMAA2Sample::OnTick`에는 한 번의 render/present 구간에서 `BeginFrame`이 두 번
호출되고 있었다. 두 번째 호출은 사용자 스크린샷 기능 뒤, ImGui 렌더 앞에 남아 있었다.
Release 빌드에서는 assert가 제거되므로 프로그램은 계속 실행됐지만 다음 상태가
발생했다.

- DX11 GPU timer의 frame-active 상태가 한 frame 안에서 두 번 시작
- 첫 `WholeFrame` profiler scope를 닫기 전에 두 번째 scope 생성
- profiler frame 계층과 query 수명주기가 불일치

[Intel 공식 CMAA2의 `CMAA2Sample.cpp`](https://github.com/GameTechDev/CMAA2/blob/master/Projects/CMAA2/CMAA2Sample.cpp)는
`RenderTick` 앞에서 `BeginFrame`을 한 번 호출하고, ImGui 뒤
`EndAndPresentFrame`으로 닫는다. 이에 맞춰 로컬의 두 번째 `BeginFrame`만 제거했다.
스크린샷 저장 기능과 렌더링 내용은 유지했다.

수정 뒤 `WholeFrame`을 `-smaaOriginalFourPerformanceSmoke`의 정식 metric으로
추가했다. 이 scope는 `BeginFrame` 이후부터 `EndAndPresentFrame` 진입 시점까지의
GPU work를 포함하며 DXGI `Present` 자체는 제외한다.

2026-07-30, RTX 3060 Ti, DirectX 11, Release x64, 1920×1017, VSync Off,
SMAA Ultra, candidate counter readback Off, mode당 warm-up 60프레임과 측정
120프레임의 engineering smoke 결과는 다음과 같다.

| Mode | WholeFrame GPU 평균 | SMAA GPU 평균 | GPU sample |
|---|---:|---:|---:|
| `O-T2X` | 2.669116 ms | 0.150827 ms | 120/120 |
| `O-T2X-R` | 2.724453 ms | 0.191497 ms | 120/120 |
| `O-ET2X` | 2.815045 ms | 0.308625 ms | 120/120 |
| `O-ET2X-R` | 2.893030 ms | 0.340531 ms | 120/120 |

모든 내부 expected scope도 120/120개를 반환해 performance smoke가 PASS했다. 이 값은
전체 frame 계측 경로를 검증한 단일 실행이지 최종 반복 성능 결과가 아니다.

수명주기 회귀에서는 16 reset, 81 temporal frame, 9 seed, 72 resolve,
20 camera reprojection, failure 0으로 PASS했다. 같은 `start=1 s`, warm-up
60프레임, 1프레임 capture hash도 수정 직전과 일치했다.

- `O-T2X`: `9F5BFE4BE601ED547408FE4FE1F9DC1D3F0B71C294E33880E779150359928D6C`
- `O-T2X-R`: `53C0E2A65BAA02C936A3090F26BC48DD8F568CAED2EB2EF24FB408E792BEC667`
- `O-ET2X`: `235A32AF21E4E2EFDBCA21878F13B4CB70447127FD43C7663F602DF27056EE7C`
- `O-ET2X-R`: `5C78117959D8AE6522EF31D0D62EFB88355ED20917D97DB0831323AE7D0D4E2C`

따라서 두 번째 `BeginFrame` 제거는 공식 렌더 수명주기를 복구하고 전체 frame
timestamp를 활성화했으며, 검증한 렌더 출력에는 영향을 주지 않았다. counter readback
분리와 WholeFrame 경로가 모두 준비됐으므로 다음 단계는 Original 네 case의 반복
성능 측정 설계를 고정하고 최소 3회 실행하는 것이다.

### 17.15 Original 네 case 반복 성능 벤치마크 도구

`-smaaOriginalFourPerformanceBenchmark [startSeconds warmupFrames measureFrames repeats]`를
추가했다. 인수를 생략할 때 연구 측정 규칙에 맞춰 start 1초, mode당 300프레임 warm-up,
4,800프레임 측정, 3회 반복을 사용한다.

측정 조건과 기록 항목은 다음과 같다.

- Release x64, DirectX 11, SMAA Ultra, VSync Off
- 동일 Bistro camera path, fixed 60 Hz simulation
- UI 숨김, PNG capture 없음
- candidate statistics readback 강제 Off
- 반복 1은 `O-T2X → O-T2X-R → O-ET2X → O-ET2X-R`
- 반복 2는 역순, 이후 정방향/역방향 교차
- `ApplicationFrameWall`: 같은 AutoBench tick 사이의 실제 CPU wall interval
- `WholeFrame`: BeginFrame부터 Present 직전까지 GPU timestamp
- SMAA total 및 mode별 내부 pass GPU timestamp
- 전체 frame 표본의 평균, 중앙값, 표준편차, p95, p99, 최댓값
- 각 반복 평균의 표준편차
- wall 평균 FPS와 `1000 / p99` 방식 1% low FPS
- WholeFrame 기반 GPU-equivalent 평균/1% low FPS

`ApplicationFrameWall`은 Present와 OS scheduling을 포함하므로 실제 앱 처리율에 가깝지만
외부 PresentMon의 displayed FPS와 동일한 개념은 아니다. 반대로 WholeFrame 기반 FPS는
Present를 제외한 GPU render throughput 환산값이다. 두 수치를 분리해 보고한다.

도구 자체 검증은 2026-07-30에 warm-up 16프레임, 측정 32프레임, 3회 반복으로
실행했다. 네 mode의 모든 expected timing metric은 96/96개, run mean은 3/3개가
수집됐고 candidate counter 표본은 0으로 유지되어 PASS했다. 이 축소 실행 수치는
벤치마크 기능 검증용이며 연구 성능 결과로 사용하지 않는다.

다음 단계는 기본 조건인 300 warm-up, 4,800 measurement, 3 repeats를 실행하고, 원시
AutoBench CSV는 Git에 넣지 않은 채 결과 요약과 반복 분산을 검토하는 것이다.

### 17.16 Original 네 case 반복 성능 측정 결과

2026-07-30에 기본 반복 벤치마크를 실제 실행했다.

- GPU: NVIDIA GeForce RTX 3060 Ti
- CPU: AMD Ryzen 5 5600
- 해상도: 1920×1017 windowed
- API/빌드: DirectX 11, Release x64
- SMAA: Ultra
- VSync/UI/PNG/candidate counter readback: Off
- camera: Bistro 동일 동적 path, fixed 60 Hz simulation, start 1초
- mode당 매 반복: warm-up 300프레임, 측정 4,800프레임
- 반복: 3회, 정방향/역방향/정방향
- mode당 총 timing 표본: 14,400

모든 expected metric은 14,400/14,400개, run mean은 3/3개 수집됐고 benchmark
validation은 PASS했다. 결과 원본은 Git에 포함하지 않는
`Projects/CMAA2/AutoBench/20260730_005402/20260730_005402_results.csv`에 있다.

| Mode | Wall 평균 | Wall p99 | Wall 평균 FPS | Wall 1% low | WholeFrame 평균 | WholeFrame p99 | SMAA 평균 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `O-T2X` | 3.269926 ms | 4.157800 ms | 305.817 | 240.512 | 2.779183 ms | 3.435520 ms | 0.236075 ms |
| `O-T2X-R` | 3.246035 ms | 4.017700 ms | 308.068 | 248.899 | 2.835895 ms | 3.502080 ms | 0.281633 ms |
| `O-ET2X` | 3.275998 ms | 4.159800 ms | 305.250 | 240.396 | 2.966339 ms | 3.642368 ms | 0.406816 ms |
| `O-ET2X-R` | 3.304674 ms | 4.163100 ms | 302.602 | 240.206 | 3.014272 ms | 3.696640 ms | 0.441845 ms |

WholeFrame 반복 평균 표준편차는 `O-T2X` 0.028973 ms, `O-T2X-R`
0.025554 ms, `O-ET2X` 0.015333 ms, `O-ET2X-R` 0.010409 ms였다. SMAA 반복 평균
표준편차는 각각 0.003863, 0.004581, 0.002899, 0.002216 ms였다.

대응 mode의 평균 차이는 다음과 같다.

| 비교 | Wall 평균 변화 | WholeFrame 평균 변화 | SMAA 평균 변화 |
|---|---:|---:|---:|
| `O-T2X-R` vs `O-T2X` | -0.73% | +2.04% | +19.30% |
| `O-ET2X` vs `O-T2X` | +0.19% | +6.73% | +72.33% |
| `O-ET2X-R` vs `O-T2X-R` | +1.81% | +6.29% | +56.89% |
| `O-ET2X-R` vs `O-ET2X` | +0.88% | +1.62% | +8.61% |

Wall 평균 FPS는 CPU scheduling과 Present 영향을 함께 받으므로 작은 차이의 알고리즘
원인으로 사용하지 않는다. GPU timestamp에서는 현재 document-based edge-selective
adaptation이 대응 Standard T2X보다 명확히 느렸다. 후보 resolve 자체보다 full-screen
SMAA 1X, 후보 준비·추출과 copy/indirect 작업의 추가 비용이 더 큰 현재 구조로
해석할 수 있다. 이는 측정에 근거한 구현 분석이며, quality 결과 없이 기법 전체의
유효성을 결론내리는 것은 아니다.

#### 분리된 후보 픽셀 특성화

성능 실행과 분리해 candidate readback On, warm-up 300프레임, 측정 4,800프레임을
동일 동적 경로에서 실행했다. 결과 원본은
`Projects/CMAA2/AutoBench/20260730_005902/20260730_005902_results.csv`에 있다.

| 항목 | 평균 | 전체 픽셀/기준 대비 |
|---|---:|---:|
| 전체 픽셀 | 1,952,640 | 100% |
| base edge | 222,123.076 | 전체의 11.376% |
| temporal candidate | 150,908.285 | 전체의 7.728% |
| indirect process | 150,908.285 | candidate와 일치 |
| candidate/base | — | 67.939% |

문서의 약 50%는 기본 목표이지 모든 장면의 보장값이 아니다. 이 Bistro 동적 경로에서는
평균 67.939%가 선택됐다. 후보 수는 감소했지만 실제 SMAA/WholeFrame GPU 시간은
증가했으므로 현재 구현을 성능 최적화 성공으로 주장할 수 없다.

이 결과는 Original 네 case의 첫 반복 성능 결과다. 아직 필요한 다음 단계는 같은 네
mode의 연속 프레임 품질 비교(ghosting, shimmer, crawling, flicker, blur,
disocclusion)이며, 그 뒤에만 Adaptive 네 mode 통합·측정을 진행한다.

### 17.17 Original 네 case 품질 분석기

`Tools/SMAA/analyze_original_four_quality.py`를 추가했다. 입력은
`-smaaOriginalFourCapture`가 만든 다음 네 디렉터리다.

- `O_T2X`
- `O_T2X_R`
- `O_ET2X`
- `O_ET2X_R`

분석기는 네 sequence의 frame 수, 연속 index, 해상도와 고유 파일 hash를 먼저
검증한 뒤 다음을 계산한다.

- mode별 인접 frame RGB MAE/RMSE와 차이 임계 픽셀 비율
- mode별 Luma 2차 시간 차분과 두 frame 간 차이
- 공간 edge strength 대용값
- 짝수·홀수 frame temporal MAE gap
- Standard/Edge-selective 및 reprojection Off/On 대응 pair 차이
- ±2 frame 범위의 축소 luma 정렬 검사

자동 산출물은 frame별 CSV, JSON 요약, 한글 Markdown 보고서, 네 mode contact sheet,
대표 4-column PNG와 Standard/Edge-selective pair GIF다. 보고서에는 optical-flow
보정 없는 시간 차이가 장면 motion을 포함하고, 작은 temporal difference가 blur 때문일
수 있으며, edge strength가 단독 품질 순위가 아니라는 제한을 자동 기록한다.

2026-07-30, mode당 warm-up 8프레임과 capture 16프레임의 축소 검증에서 네 sequence
각각 16개 연속·고유 PNG를 확인했고 모든 산출물을 정상 생성했다. 이 축소 결과는
분석기 smoke validation일 뿐 품질 연구 결과가 아니다.

다음 단계는 mode당 warm-up 60프레임, capture 300프레임의 실제 Original 4-case
sequence를 생성해 이 분석기로 처리하고 대표 GIF를 수동 검토하는 것이다.

### 17.18 Original 네 case 연속 프레임 품질 결과

2026-07-30에 `-smaaOriginalFourCapture 1 300 60`을 실행했다.

- RTX 3060 Ti, DirectX 11, Release x64
- 1920×1017 windowed, SMAA Ultra, VSync Off
- Lumberyard Bistro 동일 flythrough, fixed 60 Hz
- mode별 warm-up 60프레임
- mode별 PNG 300프레임, 총 1,200프레임
- PNG 저장 중 FPS는 성능값으로 사용하지 않음

원본 capture와 분석 산출물은 Git에 포함하지 않는
`Projects/CMAA2/AutoBench/20260730_010741`에 있다. 네 mode 모두
00000~00299 연속 index와 고유 SHA-256 파일 300개를 통과했다. Standard/Edge-selective,
reprojection Off/On 네 대응 pair의 ±2프레임 축소 luma 정렬 검사에서 같은 index가
모두 300/300 최적이었다.

#### 시간·공간 대용 지표

| Mode | 인접 frame RGB MAE | 2차 시간 차분 Luma MAE | Edge strength | 짝·홀 temporal gap |
|---|---:|---:|---:|---:|
| `O-T2X` | 1.216633 | 1.445442 | 2.095559 | 0.001201 |
| `O-T2X-R` | 1.461848 | 2.029758 | 2.171057 | 0.077666 |
| `O-ET2X` | 1.492503 | 2.124981 | 2.283882 | 0.000738 |
| `O-ET2X-R` | 1.508738 | 2.111518 | 2.287209 | 0.000625 |

| 비교 | 동일 frame RGB MAE | 차이 >8 픽셀 | Temporal MAE 변화 | 2차 차분 변화 | Edge strength 변화 |
|---|---:|---:|---:|---:|---:|
| `O-ET2X` vs `O-T2X` | 1.077730 | 2.631774% | +22.675% | +47.013% | +8.987% |
| `O-ET2X-R` vs `O-T2X-R` | 0.776444 | 1.912337% | +3.208% | +4.028% | +5.350% |
| `O-T2X-R` vs `O-T2X` | 0.697505 | 1.258117% | +20.155% | +40.425% | +3.603% |
| `O-ET2X-R` vs `O-ET2X` | 0.109174 | 0.524544% | +1.088% | -0.634% | +0.146% |

화면 공간 temporal MAE와 2차 차분에는 실제 camera/object motion이 포함된다. 따라서
값이 높다는 사실만으로 flicker가 증가했다고 단정하지 않고, 반대로 값이 낮아도
history blur일 수 있으므로 안정성 향상으로 단정하지 않는다.

현재 결과에서 edge-selective 두 mode의 edge strength는 대응 Standard보다
5.350~8.987% 높아 더 선명한 공간 출력 경향을 보였다. 그러나 temporal MAE와 2차
차분은 감소하지 않았다. 특히 no-reprojection ablation은 Standard보다 변화량이 크게
높았고, camera reprojection을 사용하면 그 차이가 +3.208%, +4.028%로 줄었다.
`O-T2X-R`에서만 짝·홀 temporal gap 0.077666이 나타났고 deliberate jitter를 쓰지
않는 edge-selective mode는 약 0.001 이하였지만, edge-selective의 전체 temporal
MAE가 더 높으므로 이를 전체 안정성 개선이라고 부르지 않는다.

대표 6-frame sequence/difference sheet를 확인했을 때 차이는 주로 창틀, 실내의
고대비 세부선, 스쿠터 윤곽과 밝은 광원 edge에 집중됐다. 화면 전체 깨짐이나 이전에
발생했던 심각한 떨림 회귀는 보이지 않았다. 다만 5-frame 간격 정적 sheet와 한 개의
Bistro camera path만으로 잔상 길이, 독립 object motion ghosting, disocclusion을
확정할 수 없다. 생성된 GIF를 실시간으로 보고, 별도 object-motion/disocclusion
장면도 추가해야 한다.

주요 분석 산출물:

- `Analysis/SMAA-Original-Four-Quality-Analysis-ko.md`
- `Analysis/temporal_metrics_original_four.csv`
- `Analysis/analysis_summary_original_four.json`
- `Analysis/contact_sheet_original_four.png`
- `Analysis/comparison_edge_vs_standard_no_reprojection_00270_00299.gif`
- `Analysis/comparison_edge_vs_standard_reprojected_00162_00191.gif`
- `Analysis/sequence_sheet_edge_vs_standard_no_reprojection_00270_00295.png`
- `Analysis/sequence_sheet_edge_vs_standard_reprojected_00162_00187.png`

이로써 한 개의 동일 Bistro 경로에 대한 Original 네 case 성능·품질 기준선은 확보했다.
현재 결과는 edge-selective adaptation의 성능 우위나 temporal 품질 우위를 보이지
않는다. 추가 scene-specific ghosting 검증을 유지한 채 다음 구현 단계인 Adaptive
SMAA 네 mode 통합을 준비할 수 있다.

### 17.19 Adaptive SMAA 통합과 8-case 자동 검증

2026-07-30에 검증 완료된 Original/TSCMAA-inspired core에서
`codex/adaptive-temporal-smaa` 브랜치를 만들고 Adaptive SMAA를 독립 공간 처리 축으로
통합했다.

통합 원칙:

- `SpatialSearch::Original`은 기존 edge target과 shader path를 유지
- `SpatialSearch::AdaptiveContrast`에서만 RG8 edge + R8 metadata MRT 사용
- edge pass의 local contrast를 `0.0/0.5/1.0` 세 tier로 기록
- 낮은 대비: 수평·수직 4 step, 대각선 3 step
- 중간 대비: 수평·수직 8 step, 대각선 Ultra 최대값의 절반
- 높은 대비: 기존 Ultra 최대 탐색 범위
- spatial 축만 바꾸고 대응하는 temporal 설정은 O/A mode 사이에서 동일하게 유지

연결된 8개 semantic mode:

| ID | Spatial | Temporal | Reprojection |
|---|---|---|---|
| `O-T2X` | Original | Standard T2X | Off |
| `O-T2X-R` | Original | Standard T2X | Camera |
| `O-ET2X` | Original | Edge-selective | Off ablation |
| `O-ET2X-R` | Original | Edge-selective | Camera |
| `A-T2X` | Adaptive | Standard T2X | Off |
| `A-T2X-R` | Adaptive | Standard T2X | Camera |
| `A-ET2X` | Adaptive | Edge-selective | Off ablation |
| `A-ET2X-R` | Adaptive | Edge-selective | Camera |

Release x64 빌드는 기존 C4834/C4100 경고 두 개만 남기고 성공했다. 이후
`-smaaTemporalLifecycleTest`를 실제 RTX 3060 Ti/DX11에서 실행했다. Adaptive shader는
런타임에 새로 컴파일됐고 8개 mode 모두 reset과 first-frame seed를 통과했다.

| 항목 | 결과 |
|---|---:|
| reset | 25 |
| completed frame | 93 |
| seed | 13 |
| resolve | 80 |
| reprojection | 26 |
| lifecycle failure | 0 |
| 종합 | PASS |

자동 측정·캡처 경로도 8-case로 확장했다.

- `-smaaEightCasePerformanceSmoke`
- `-smaaEightCasePerformanceBenchmark`
- `-smaaEightCaseCapture`
- `Tools/SMAA/analyze_original_four_quality.py --include-adaptive`

성능 도구는 기존 Original 4-case와 같은 통계 코드와 profiler node를 사용한다. 8-case
본 측정 명령은 기본적으로 mode당 300 warm-up, 4,800 measurement, 3 repeats이고
정방향/역방향 순서를 교차하며 candidate readback을 끈다.

축소 검증은 `-smaaEightCasePerformanceSmoke "1 30 32 1"`로 실행했다. 8개 mode의
expected timing sample이 각각 32개 수집됐고 edge-selective 네 mode의 candidate
sample도 각각 32개 수집되어 PASS했다. 결과는 Git에 포함하지 않는
`Projects/CMAA2/AutoBench/20260730_013440`에 있다. 이 짧은 수치는 성능 연구 결과로
사용하지 않는다.

품질 캡처 축소 검증은 `-smaaEightCaseCapture "1 3 3"`으로 실행했다. 8개 출력
디렉터리 모두 `00000~00002` PNG 3개와 고유 hash 3개를 확인했다. 8-case 분석은 mode별
시간·공간 지표 외에 다음 대응 비교를 계산한다.

- Original/Adaptive 각각의 Standard ↔ Edge-selective
- Original/Adaptive 각각의 reprojection Off ↔ On
- 동일 temporal 설정의 Original ↔ Adaptive

8-case와 기존 4-case 분석 경로가 모두 통과했고 contact sheet, CSV, JSON, Markdown,
대표 PNG/GIF와 sequence sheet를 생성했다. 축소 캡처와 분석 결과는
`Projects/CMAA2/AutoBench/20260730_013737`에 있으며 연구 품질 결론으로 사용하지
않는다.

관련 커밋:

- `1432a7b` Integrate adaptive SMAA as an orthogonal spatial mode
- `97f54c6` Expose the eight temporal SMAA research cases
- `f38aa25` Add eight-case temporal performance benchmark
- `a65363d` Add eight-case temporal quality capture
- `c05e484` Extend temporal quality analysis to eight cases

이 시점에서 8개 mode의 구현·빌드·lifecycle·축소 측정/capture/analysis 경로는
검증됐다. 아직 완료되지 않은 것은 정식 8-case 반복 측정과 별도 object-motion,
얇은 선, disocclusion 장면의 품질 검증이다. 축소 smoke 수치로 성능 또는 품질 우위를
주장하지 않는다.

### 17.20 8-case 성능 분석기와 숨김 창 engineering 실행

8개 mode의 성능 결과를 세 연구 축으로 일관되게 분리하기 위해
`Tools/SMAA/analyze_eight_case_performance.py`를 추가했다.

입력 검증:

- 정확한 8개 semantic ID 존재
- 각 mode의 `ApplicationFrameWall`, `WholeFrame`, `SMAA` 존재
- 설정된 measurement frame × repeats와 실제 표본 수 일치
- 각 timing metric의 run 수 일치
- frame-rate characterization 존재
- candidate counter readback Off
- 벤치마크 내부 validation PASS

출력 비교:

- Original ↔ Adaptive: 대응 temporal/reprojection 설정 네 쌍
- Standard ↔ Edge-selective: 대응 spatial/reprojection 설정 네 쌍
- Reprojection Off ↔ On: 대응 spatial/temporal 설정 네 쌍
- 각 쌍에서 Wall, WholeFrame, SMAA 평균 시간의 절대·백분율 변화

분석기는 다음과 같이 실행한다.

```powershell
python Tools/SMAA/analyze_eight_case_performance.py `
  <results.csv> `
  --window-state visible|hidden|unknown `
  --classification formal|engineering
```

`formal` 결과는 `--window-state visible --classification formal` 조합에서만 표시한다.
창 상태를 알 수 없거나 운영체제 수준에서 숨겨 실행한 결과가 논문용 FPS 결과로
잘못 사용되는 것을 막기 위한 provenance 규칙이다.

첫 전체 길이 실행은 mode당 warm-up 300프레임, measurement 4,800프레임, 3회 반복으로
완료되어 내부 PASS와 mode별 14,400개 표본을 확보했다. 원본은 Git에 포함하지 않는
`Projects/CMAA2/AutoBench/20260730_014653/20260730_014653_results.csv`다. 이 실행은
프로그램 창을 숨긴 상태였으므로 다음과 같이 engineering 결과로 분석했다.

```powershell
python Tools/SMAA/analyze_eight_case_performance.py `
  Projects/CMAA2/AutoBench/20260730_014653/20260730_014653_results.csv `
  --window-state hidden `
  --classification engineering
```

검증 결과는 8개 mode, mode별 14,400개 표본, 12개 대응 비교와 36개 지표 행으로
PASS했다. 이 예비 실행에서는 대응 case 평균 SMAA 시간이 Adaptive에서 10.66%
감소했고, Edge-selective에서 Standard 대비 76.93% 증가했으며, camera reprojection
On에서 Off 대비 14.39% 증가했다. 이는 숨김 실행에서 관측한 예비 GPU pass 결과이고,
visible-window 실행으로 재현하기 전에는 최종 성능 결론으로 사용하지 않는다.

생성 산출물:

- `PerformanceAnalysis/SMAA-Eight-Case-Performance-Analysis-ko.md`
- `PerformanceAnalysis/smaa_eight_case_performance_modes.csv`
- `PerformanceAnalysis/smaa_eight_case_performance_comparisons.csv`
- `PerformanceAnalysis/smaa_eight_case_performance_analysis.json`

다음 작업은 동일 실행 파일과 설정으로 창을 보이는 상태에서 8-case 반복 벤치마크를
재실행하고, `visible/formal` 분석 결과가 숨김 engineering 결과와 같은 GPU timing
방향을 재현하는지 확인하는 것이다.

### 17.21 visible-window 8-case 성능 본 측정

2026-07-30에 운영체제 수준에서 CMAA2 렌더 창이 보이는 상태로 8-case 반복 성능
벤치마크를 실행했다. 앱 내부 ImGui UI는 기존 벤치마크 구현대로 측정 중 숨겼지만,
Windows 렌더 창 자체는 visible/windowed 상태를 유지했다.

실행 조건:

- AMD Ryzen 5 5600 / NVIDIA GeForce RTX 3060 Ti
- Release x64 / DirectX 11
- 1920×1017 windowed / VSync Off / SMAA Ultra
- Bistro fixed 60 Hz camera path, start 1초
- mode당 300 warm-up + 4,800 measurement
- 3 repeats, 정방향/역방향/정방향
- PNG capture Off / candidate readback Off
- mode당 timing 표본 14,400개

자동화 환경에서는 GUI 앱에 명령행 인수를 직접 전달할 수 없어, 기존
`BenchItemSMAATemporalPerformanceBenchmark`를 앱 초기화 시 한 번 등록하는 임시
startup flag를 사용했다. 이 flag는 측정 직후 기본값 `false`로 복원했고 최종 코드에는
자동 실행 상태가 남아 있지 않다. temporal 알고리즘, benchmark class, mode 순서,
warm-up/measurement/repeat 조건은 명령행 실행과 동일했다. 향후 수동 재현을 위해
Benchmarking UI의 `Run SMAA eight-case performance benchmark` 버튼과 `F8` 단축키를
추가했다.

원본과 분석 산출물:

- `Projects/CMAA2/AutoBench/20260730_021435/20260730_021435_results.csv`
- `Projects/CMAA2/AutoBench/20260730_021435/PerformanceAnalysis/SMAA-Eight-Case-Performance-Analysis-ko.md`
- `Projects/CMAA2/AutoBench/20260730_021435/PerformanceAnalysis/smaa_eight_case_performance_modes.csv`
- `Projects/CMAA2/AutoBench/20260730_021435/PerformanceAnalysis/smaa_eight_case_performance_comparisons.csv`
- `Projects/CMAA2/AutoBench/20260730_021435/PerformanceAnalysis/smaa_eight_case_performance_analysis.json`

내부 benchmark validation과 `visible/formal` 분석 validation은 모두 PASS했다.

| Mode | Wall 평균 | Wall 1% low | WholeFrame 평균 | SMAA 평균 | SMAA run σ |
|---|---:|---:|---:|---:|---:|
| `O-T2X` | 3.294510 ms | 236.967 FPS | 3.187142 ms | 0.239521 ms | 0.002811 ms |
| `O-T2X-R` | 3.342563 ms | 233.618 FPS | 3.239933 ms | 0.283395 ms | 0.001114 ms |
| `O-ET2X` | 3.508584 ms | 152.458 FPS | 3.440512 ms | 0.408391 ms | 0.001245 ms |
| `O-ET2X-R` | 3.773257 ms | 132.114 FPS | 3.674302 ms | 0.440497 ms | 0.000505 ms |
| `A-T2X` | 3.296973 ms | 235.444 FPS | 3.165971 ms | 0.206022 ms | 0.000065 ms |
| `A-T2X-R` | 3.306381 ms | 235.089 FPS | 3.198469 ms | 0.250192 ms | 0.000318 ms |
| `A-ET2X` | 3.359188 ms | 206.364 FPS | 3.309388 ms | 0.377269 ms | 0.000197 ms |
| `A-ET2X-R` | 3.571518 ms | 144.970 FPS | 3.494936 ms | 0.409989 ms | 0.001135 ms |

세 독립 축의 대응 case 결과:

| 축 | 대응 case 평균 SMAA 변화 | 관측 범위 |
|---|---:|---:|
| Original → Adaptive | -10.06% | -6.93% ~ -13.99% |
| Standard → Edge-selective | +68.23% | +55.44% ~ +83.12% |
| Reprojection Off → On | +14.07% | +7.86% ~ +21.44% |

숨김 engineering 실행과 visible formal 실행의 축별 평균은 각각 다음과 같았다.

| 축 | Hidden engineering | Visible formal | 방향 재현 |
|---|---:|---:|---|
| Adaptive | -10.66% | -10.06% | 예 |
| Edge-selective | +76.93% | +68.23% | 예 |
| Reprojection | +14.39% | +14.07% | 예 |

따라서 Adaptive 공간 탐색의 SMAA pass 시간 감소와 reprojection 비용 증가는 visible
실행에서도 재현됐다. 현재 document-based Edge-selective 구현은 후보 수를 줄이지만,
후보 준비·추출·copy·indirect resolve의 고정 비용 때문에 대응 Standard T2X보다
SMAA 시간이 55.44~83.12% 증가했다. WholeFrame도 대응 case에서 4.53~13.41%
증가했다. 이 장면의 현재 구현을 성능 최적화 성공으로 주장할 수 없다.

이 결론은 성능에 한정된다. Edge-selective 방식이 ghosting, shimmer, crawling 등에서
품질 이득을 제공하는지는 8-case 연속 PNG sequence와 object-motion/disocclusion
전용 장면으로 별도 검증해야 한다. 다음 작업은 정식 8-case 품질 캡처와 분석이다.

### 17.22 Bistro 8-case 연속 프레임 품질 본 측정

2026-07-30에 기존 Original 품질 기준선과 동일한 camera 구간에서 전체 8개 mode를
캡처했다.

- RTX 3060 Ti / DirectX 11 / Release x64
- 1920×1017 windowed / SMAA Ultra / VSync Off
- Lumberyard Bistro fixed 60 Hz flythrough
- start 1초 / mode별 warm-up 60프레임
- mode별 PNG 300장, 총 2,400장
- PNG 저장 중 FPS는 성능 결과로 사용하지 않음
- 원본 용량 약 4.0GB

원본과 분석 산출물은 Git에 포함하지 않는
`Projects/CMAA2/AutoBench/20260730_023009`에 있다. 8개 mode 모두 00000~00299
연속 index, 1920×1017 해상도와 고유 파일 hash 300개를 통과했다. 12개 대응 pair의
±2프레임 축소 luma 정렬 검사에서도 모두 300/300 same-index가 최적이었다.

#### Original deterministic regression

이전 Original 기준선 `Projects/CMAA2/AutoBench/20260730_010741`과 새 8-case
capture의 Original 4개 디렉터리를 파일별 SHA-256으로 대조했다.

| 항목 | 결과 |
|---|---:|
| 비교한 PNG pair | 1,200 |
| hash mismatch | 0 |
| 결과 | PASS |

따라서 Adaptive 네 mode를 추가한 뒤에도 대응 Original 4개 출력은 이전 기준선과
byte 단위로 동일했다.

#### Mode별 시간·공간 대용 지표

| Mode | 인접 frame RGB MAE | 2차 시간 차분 Luma MAE | Edge strength | 짝·홀 temporal gap |
|---|---:|---:|---:|---:|
| `O-T2X` | 1.216633 | 1.445442 | 2.095559 | 0.001201 |
| `O-T2X-R` | 1.461848 | 2.029758 | 2.171057 | 0.077666 |
| `O-ET2X` | 1.492503 | 2.124981 | 2.283882 | 0.000738 |
| `O-ET2X-R` | 1.508738 | 2.111518 | 2.287209 | 0.000625 |
| `A-T2X` | 1.217134 | 1.446437 | 2.097672 | 0.001225 |
| `A-T2X-R` | 1.462363 | 2.032444 | 2.173170 | 0.077701 |
| `A-ET2X` | 1.492353 | 2.125176 | 2.285311 | 0.000681 |
| `A-ET2X-R` | 1.508687 | 2.112713 | 2.288546 | 0.000556 |

#### Adaptive 공간 처리의 품질 영향

| 비교 | 같은 frame RGB MAE | 차이 >8 픽셀 | Temporal MAE 변화 | 2차 차분 변화 | Edge strength 변화 |
|---|---:|---:|---:|---:|---:|
| `A-T2X` vs `O-T2X` | 0.008875 | 0.008907% | +0.041% | +0.069% | +0.101% |
| `A-T2X-R` vs `O-T2X-R` | 0.008862 | 0.009663% | +0.035% | +0.132% | +0.097% |
| `A-ET2X` vs `O-ET2X` | 0.008164 | 0.009305% | -0.010% | +0.009% | +0.063% |
| `A-ET2X-R` vs `O-ET2X-R` | 0.008216 | 0.009419% | -0.003% | +0.057% | +0.058% |

Adaptive/Original 차이는 최대 채널 차이 8을 넘는 픽셀이 약 0.009%뿐이고 시간 지표
변화도 약 ±0.1% 이내였다. 이 한 Bistro path에서는 Adaptive 공간 탐색이 대응
Original temporal 결과를 사실상 유지하면서, 17.21에서 측정한 SMAA GPU 시간을
대응 case 평균 10.06% 줄였다.

#### Edge-selective document profile의 품질 영향

| 비교 | 같은 frame RGB MAE | 차이 >8 픽셀 | Temporal MAE 변화 | 2차 차분 변화 | Edge strength 변화 |
|---|---:|---:|---:|---:|---:|
| `O-ET2X` vs `O-T2X` | 1.077730 | 2.631774% | +22.675% | +47.013% | +8.987% |
| `O-ET2X-R` vs `O-T2X-R` | 0.776444 | 1.912337% | +3.208% | +4.028% | +5.350% |
| `A-ET2X` vs `A-T2X` | 1.077396 | 2.645783% | +22.612% | +46.925% | +8.945% |
| `A-ET2X-R` vs `A-T2X-R` | 0.776273 | 1.926304% | +3.168% | +3.949% | +5.309% |

Edge-selective profile은 대응 Standard보다 edge strength가 5.309~8.987% 높아 창틀,
실내 고대비 세부선, 스쿠터 윤곽과 밝은 광원에서 더 선명한 경향을 보였다. 그러나
temporal MAE와 2차 차분은 감소하지 않았다. 특히 no-reprojection ablation의 변화가
컸고 camera reprojection을 사용하면 차이가 약 +3~4%로 줄었다.

이 비교는 candidate selection만의 단독 ablation이 아니다. document profile에는
no deliberate projection jitter, SMAA 1X spatial input, Catmull-Rom 5-tap,
YCoCg variance clipping과 history weight 0.8이 함께 포함된다. 따라서 위 차이를
“edge 후보 선택만의 효과”라고 표현하지 않는다.

contact sheet와 6-frame sequence/difference sheet에서 화면 전체 깨짐이나 과거의
심각한 떨림 회귀는 보이지 않았다. 하지만 한 camera flythrough와 optical-flow 보정
없는 지표만으로 ghosting 길이, 독립 object motion, disocclusion 또는 shimmer 개선을
확정할 수 없다.

주요 산출물:

- `Analysis/SMAA-Eight-Case-Quality-Analysis-ko.md`
- `Analysis/temporal_metrics_eight_case.csv`
- `Analysis/analysis_summary_eight_case.json`
- `Analysis/contact_sheet_eight_case.png`
- `Analysis/comparison_edge_vs_standard_no_reprojection_00270_00299.gif`
- `Analysis/comparison_edge_vs_standard_reprojected_00162_00191.gif`
- `Analysis/comparison_adaptive_edge_vs_standard_no_reprojection_00270_00299.gif`
- `Analysis/comparison_adaptive_edge_vs_standard_reprojected_00162_00191.gif`
- `Analysis/sequence_sheet_edge_vs_standard_no_reprojection_00270_00295.png`
- `Analysis/sequence_sheet_edge_vs_standard_reprojected_00162_00187.png`

이 시점에서 동일 Bistro path의 8-case 성능·품질 표는 확보됐다. 다음 단계는 풍차 날개,
얇은 선/울타리, 정지 카메라의 독립 object motion과 명시적 disocclusion 장면을
추가해 ghosting, shimmer, crawling과 flicker를 검증하는 것이다.

### 17.23 전용 temporal stress 장면과 캡처 smoke

2026-07-30에 기존 장면 asset을 수정하지 않는 별도 절차적 장면
`SMAA Temporal Stress Test`를 추가했다.

- 밝은 수직·대각선 반복선: 카메라 수평 이동 시 shimmer/crawling 관찰
- 회전하는 네 개의 얇은 날개: 빠른 대각선·subpixel object edge 관찰
- 밝은 반복선 앞의 어두운 이동 occluder: object-motion ghosting과 disocclusion 관찰
- 고정 노출, SMAA Ultra, fixed 60 Hz analytical timeline

8개 semantic mode를 같은 순서와 timeline으로 저장하는 명령은 다음과 같다.

```powershell
.\CMAA2.exe -smaaEightCaseStressCapture "thin-lines 180 60"
.\CMAA2.exe -smaaEightCaseStressCapture "object-motion 180 60"
.\CMAA2.exe -smaaEightCaseStressCapture "combined 180 60"
```

각 시나리오의 의미는 다음과 같다.

| 시나리오 | 카메라 | 독립 물체 |
|---|---|---|
| `thin-lines` | 수평 이동 | 고정 |
| `object-motion` | 고정 | occluder 이동 + 날개 회전 |
| `combined` | 수평 이동 | occluder 이동 + 날개 회전 |

`-R` mode의 reprojection은 현재 depth와 이전·현재 카메라 행렬에서 만든 camera motion만
처리한다. 따라서 `object-motion`은 object motion vector 미지원 상태가 temporal
history에 어떤 잔상을 만드는지 분리하는 장면이다.

Release x64 빌드 후 각 시나리오에 3 warm-up + 3 capture frame smoke를 실행했다.
각 실행에서 8개 mode 디렉터리, mode별 연속·고유 PNG 3개와 기존
`analyze_original_four_quality.py --include-adaptive` 분석 산출물 생성을 확인했다.
첫 thin-lines smoke에서 free-flight controller가 analytical camera를 덮어써 하늘만
캡처되는 문제를 발견했고, controller 처리 뒤 테스트 카메라를 재적용하도록 수정했다.
재실행에서는 backdrop, 반복선, occluder와 rotor가 정상 출력됐다.

smoke 원시 경로:

- `Projects/CMAA2/AutoBench/20260730_030258`: `thin-lines`
- `Projects/CMAA2/AutoBench/20260730_030342`: `object-motion`
- `Projects/CMAA2/AutoBench/20260730_030417`: `combined`

이 결과는 장면·캡처·분석 도구 검증용이며 최종 품질 결론에 사용하지 않는다. 다음 작업은
각 시나리오를 충분한 길이로 캡처하고, 전체 화면 지표뿐 아니라 rotor와 occluder
disocclusion 영역을 분리해 ghosting 길이, temporal 변화와 edge 안정성을 분석하는
것이다.

### 17.24 전용 temporal stress 8-case 품질 측정

2026-07-30에 세 전용 시나리오를 전체 8개 semantic mode로 정식 캡처했다. 공통 조건은
DirectX 11, Release x64, SMAA Ultra, fixed 60 Hz, mode별 60-frame warm-up과
240-frame PNG 저장이다. 각 실행은 8개 mode × 240장, 총 1,920 PNG이며 모든 mode가
00000~00239 연속 index와 동일 1920×1017 해상도를 통과했다.

| 시나리오 | 원시 경로 | 분리 목적 |
|---|---|---|
| `thin-lines` | `Projects/CMAA2/AutoBench/20260730_030857` | camera motion의 얇은 선 shimmer/crawling |
| `object-motion` | `Projects/CMAA2/AutoBench/20260730_031939` | 고정 camera에서 rotor ghosting과 occluder disocclusion |
| `combined` | `Projects/CMAA2/AutoBench/20260730_032435` | camera motion과 독립 object motion의 복합 영향 |

품질 PNG는 숨긴 렌더 창에서 render target으로 직접 저장했다. 이는 화면 표시 FPS를
측정한 실행이 아니므로 창 visibility는 PNG 내용에 영향을 주지 않으며, 이 실행의 FPS는
성능 결과로 사용하지 않는다.

전용 분석기 `Tools/SMAA/analyze_temporal_stress_quality.py`를 추가했다. 이 도구는
thin-line field, occluder path, rotor ROI를 분리해 다음을 생성한다.

- 인접 frame RGB MAE, 2차 시간 차분 Luma MAE, edge strength
- Standard↔Edge-selective, reprojection Off↔On의 same-frame 차이
- occluder의 알려진 이동 방향 뒤 36픽셀에서 trail darkness와 연속 폭을 재는 휴리스틱
- 각 ROI의 Standard/Edge-selective 비교 GIF
- 6개 연속 frame과 4배 absolute difference sheet

#### Camera motion 얇은 선

`thin-lines` ROI의 주요 대응 비교는 다음과 같다.

| 비교 | 인접 frame MAE 변화 | 2차 시간 차분 변화 | Edge strength 변화 |
|---|---:|---:|---:|
| `O-ET2X` vs `O-T2X` | +1.539% | +29.611% | +0.647% |
| `O-ET2X-R` vs `O-T2X-R` | -1.607% | -7.586% | +0.478% |
| `A-ET2X` vs `A-T2X` | +1.224% | +36.673% | +0.303% |
| `A-ET2X-R` vs `A-T2X-R` | -1.664% | -6.741% | +0.288% |

reprojection Off에서는 Edge-selective의 2차 시간 차분이 커졌고, camera reprojection
On에서는 대응 Standard보다 작아졌다. 이 수치는 실제 camera motion과 blur를 함께
포함하므로 값 하나만으로 shimmer 순위를 확정하지 않는다.

#### 독립 object motion

고정 camera에서 회전하는 rotor의 Edge-selective no-reprojection은 대응 Standard보다
인접 frame MAE가 Original +26.762%, Adaptive +26.931%, 2차 시간 차분이 각각
+15.031%, +16.545%였다. 연속 frame sheet에서는 Standard T2X의 날개에 이전 위치가
반투명하게 겹치는 이중 잔상이 보였고, Edge-selective에서는 이 잔상이 크게 줄었다.
동시에 시간 변화량은 더 컸으므로 history를 덜 사용하는 데 따른 flicker 가능성을
별도로 평가해야 한다.

occluder 뒤 trailing-halo 휴리스틱은 다음과 같다.

| 비교 | Trail darkness 감소 | 연속 trail 폭 감소 |
|---|---:|---:|
| `O-ET2X` vs `O-T2X` | 39.16% | 58.39% |
| `A-ET2X` vs `A-T2X` | 40.71% | 70.99% |

`combined`에서도 모든 대응 Edge-selective case가 같은 감소 방향을 보였다. 감소 범위는
darkness 42.84~54.50%, 연속 폭 61.42~76.78%였다. 그러나 이 지표는 현재 어두운
occluder core와 알려진 운동 방향을 이용한 장면 전용 휴리스틱이며 supersample
ground truth나 optical-flow 보정 ghosting metric이 아니다.

#### 현재 해석

이번 결과는 현재 document profile이 Standard T2X보다 object-motion 이중 잔상과
occluder 뒤 trail을 줄일 가능성을 보여준다. 반면 여러 ROI에서 인접 frame/2차 차분이
증가해 temporal variation 또는 flicker가 늘 수 있는 trade-off도 보인다. 따라서
`Edge-selective가 종합적으로 더 우수하다`는 최종 결론은 아직 내리지 않는다.

남은 품질 검증은 다음과 같다.

1. 같은 stress timeline의 SMAA 1X control을 추가해 temporal 방식이 실제로
   shimmer/crawling을 얼마나 줄이는지 비교
2. 가능하면 supersample reference 또는 optical-flow 정렬 지표로 ghosting 휴리스틱 보강
3. candidate selection, jitter, Catmull-Rom, variance clipping, history weight를
   분리한 ablation으로 현재 trade-off의 원인 규명
4. 현재 `-R`이 camera motion만 처리한다는 한계를 유지하고, object motion vector
   미지원 결과를 별도로 명시

### 17.25 SMAA 1X spatial-only 품질 control

2026-07-30에 temporal 방식이 실제로 SMAA 1X보다 시간적 안정성을 제공하는지, 그리고
현재 ET2X의 ghosting 감소가 history를 사실상 제거해 1X로 돌아간 결과인지 확인하기
위해 두 spatial-only control을 추가했다.

| Control | 공간 처리 | Jitter | History | Reprojection |
|---|---|---|---|---|
| `O-1X` | Original SMAA | Off | Off | Off |
| `A-1X` | Adaptive SMAA | Off | Off | Off |

이 두 control은 최종 8-case를 10-case로 확장하는 새 연구 mode가 아니라, 기존 8개
temporal mode의 효과를 판단하기 위한 외부 기준군이다. 캡처 명령은 다음과 같다.

```powershell
.\CMAA2.exe -smaaOneXStressCapture "thin-lines 240 60"
.\CMAA2.exe -smaaOneXStressCapture "object-motion 240 60"
.\CMAA2.exe -smaaOneXStressCapture "combined 240 60"
```

Release x64 빌드와 `3 warm-up + 3 capture` smoke를 통과했고, 리팩터링 전의
`-smaaEightCaseStressCapture`도 8개 mode × 1-frame 회귀 smoke로 확인했다.

정식 control 경로는 다음과 같다.

| 시나리오 | 1X control 경로 | 대응 temporal 8-case 경로 |
|---|---|---|
| `thin-lines` | `Projects/CMAA2/AutoBench/20260730_042245` | `Projects/CMAA2/AutoBench/20260730_030857` |
| `object-motion` | `Projects/CMAA2/AutoBench/20260730_042343` | `Projects/CMAA2/AutoBench/20260730_031939` |
| `combined` | `Projects/CMAA2/AutoBench/20260730_042414` | `Projects/CMAA2/AutoBench/20260730_032435` |

각 정식 control은 `O-1X`와 `A-1X`에 mode별 60-frame warm-up과 240 PNG를 저장했다.
두 mode 모두 00000~00239 연속 index, 1920×1017 해상도를 통과했다. 별도 순차 재실행과
최초 실행의 대응 PNG 총 1,440장을 SHA-256으로 비교했고 mismatch는 0이었다.

전용 분석기 `Tools/SMAA/analyze_smaa_1x_controls.py`는 1X root와 기존 temporal
8-case root를 함께 받아 동일 frame과 ROI에서 총 10개 출력을 비교한다. 프레임별
temporal MAE, 2차 시간 차분, edge strength, trail 휴리스틱과 함께
`1X / Standard T2X / ET2X` 3-way GIF 및 6-frame sequence sheet를 생성한다.

#### Camera motion의 얇은 선

`thin-lines`의 1X 대비 2차 시간 차분 변화는 다음과 같다.

| 비교 | Original | Adaptive |
|---|---:|---:|
| Standard T2X no-reprojection | -28.535% | -35.228% |
| Standard T2X camera reprojection | -18.405% | -21.391% |
| ET2X no-reprojection | -7.374% | -11.474% |
| ET2X camera reprojection | -24.595% | -26.690% |

Standard T2X no-reprojection은 1X보다 불규칙 시간 변화를 크게 줄였다. ET2X
no-reprojection의 감소 폭은 더 작았지만 0은 아니었고, camera reprojection이 있는
ET2X-R에서는 감소 폭이 24.595~26.690%로 커졌다. 따라서 camera motion의 얇은
선에서는 현재 ET2X가 일부 temporal 안정화 효과를 유지하며 reprojection이 이를
보강하는 결과다.

#### 독립 object motion의 회전 날개

고정 camera의 rotor에서 1X 대비 결과는 다음과 같다.

| 비교 | 인접 frame MAE 변화 | 1X와 same-frame MAE |
|---|---:|---:|
| `O-T2X` vs `O-1X` | -21.417% | 2.293902 |
| `O-ET2X` vs `O-1X` | -0.386% | 0.052451 |
| `A-T2X` vs `A-1X` | -21.361% | 2.285220 |
| `A-ET2X` vs `A-1X` | -0.182% | 0.034190 |

3-way sequence sheet에서 Standard T2X에는 이전 rotor 위치가 반투명하게 겹치는 이중
잔상이 나타났다. ET2X는 그 잔상이 크게 줄었지만 출력 형상과 시간 변화량이 1X에
거의 일치했다. Occluder ROI에서도 ET2X와 1X의 same-frame MAE는 Original
0.084904, Adaptive 0.074016에 불과했다.

Object-motion trailing-halo 휴리스틱도 같은 경향을 보였다.

| Mode | Trail darkness | Trail width |
|---|---:|---:|
| `O-1X` | 0.561651 | 0.579 px |
| `O-T2X` | 0.942147 | 1.442 px |
| `O-ET2X` | 0.573162 | 0.600 px |
| `A-1X` | 0.471003 | 0.275 px |
| `A-T2X` | 0.870598 | 1.179 px |
| `A-ET2X` | 0.516216 | 0.342 px |

#### 현재 해석

1X control은 Standard T2X와 현재 ET2X의 trade-off를 명확히 했다.

- Standard T2X는 1X보다 시간 변화량을 줄이지만 object-motion 이중 잔상이 크다.
- 현재 ET2X는 camera-motion thin-line에서는 일부 temporal 안정화를 유지한다.
- 현재 ET2X는 독립 object motion에서 잔상을 줄이지만 1X와 거의 같은 출력·시간
  거동을 보여 temporal supersampling 효과를 상당 부분 상실했을 가능성이 있다.
- 따라서 현재 결과는 `ET2X가 성공했다`는 결론이 아니라, candidate selection,
  no-jitter, Catmull-Rom, variance clipping, history weight 0.8을 분리해야 한다는
  ablation 근거다.

다음 단계에서는 우선 Original SMAA와 camera reprojection 경로에서 Standard T2X의
jitter, bilinear sampler, clipping Off, history weight 0.5를 그대로 유지하고
coverage만 Edge-selective로 변경한 candidate-only profile을 만든다. 이후
Catmull-Rom, clipping, weight와 jitter를 하나씩 추가해 object history 제거와
temporal 안정성 변화의 원인을 분리한다.

### 17.26 Edge-selective temporal 구성요소별 ablation

2026-07-30에 위 계획의 candidate-only 및 누적 구성요소 ablation을 구현하고 정식
품질·성능 측정을 완료했다. 최종 8-case mode는 변경하지 않았으며 아래 mode는 원인
분석용 진단 설정이다.

```text
O-T2X-R
→ ABL-CandidateOnly-R
→ ABL-Candidate+Catmull-R
→ ABL-Candidate+Catmull+Clip-R
→ ABL-Candidate+Catmull+Clip+W0.8-R
→ O-ET2X-R-Document
```

첫 인접 비교는 Standard와 reprojection, T2X jitter/subsample, bilinear sampler,
clipping Off, history weight 0.5를 모두 동일하게 유지하고 temporal coverage만
full-screen에서 Intel-family edge candidate로 바꾼다. 이후에는 Catmull-Rom,
YCoCg clipping, weight 0.8, no-jitter를 하나씩 누적한다.

세 stress scenario의 mode별 60 warm-up + 240 PNG 정식 capture와 visible-window
300 warm-up + 4,800 measurement × 3회 성능 측정을 완료했다. Candidate-only는
Standard보다 occluder trail을 줄였지만 2차 시간 차분을 thin-lines +52.761%,
occluder +209.269%, rotor +140.795% 늘렸다. Catmull-Rom 영향은 작았고 clipping은
trail을 더 줄이는 대신 variation을 조금 늘렸으며, weight 0.8과 no-jitter가
variation을 줄였다. 특히 no-jitter는 직전 단계 대비 2차 차분을 대표 ROI에서
33.320~49.383% 줄였다.

성능에서는 Candidate-only가 Standard보다 SMAA GPU +56.061%, WholeFrame GPU
+2.102%였고, 후속 Catmull-Rom과 clipping의 SMAA 증가는 각각 +0.708%, +0.885%였다.
현재 병목은 history sample 세부식보다 candidate 준비·compact·indirect 실행 구조다.

상세 조건, 표와 해석 제한은
`Docs/SMAA-Temporal-Component-Ablation-Results-ko.md`에 기록한다. 다음 연구 단계는
supersample 또는 optical-flow reference로 ghost trail과 실제 temporal instability를
분리하는 것이다.

### 17.27 Optical-flow 정렬 보조 품질 분석

2026-07-30에 Farneback dense optical flow 기반 motion-compensated residual 분석을
component ablation과 최종 8-case에 적용했다. Spatial-only O-1X/A-1X에서 flow를
추정해 대응 temporal mode에 공통 적용하고, forward/backward consistency 1.0px와
화면 경계 검사를 통과한 픽셀만 사용한다.

알려진 `(3,-2)px` 합성 이동 self-test는 backward vector error 0.000108px,
정렬 MAE 99.877% 감소로 PASS했다. 정식 stress ROI의 flow valid ratio는
78.166~92.763%였고 각 spatial 1X의 정렬 MAE도 29.474~43.080% 감소했다.

Motion 보정 후 Candidate-only는 Standard보다 aligned residual이 `thin-lines`
+32.304%, object occluder +310.764%, rotor +49.881% 높았다. Object-motion
FB threshold 0.5/1.0/2.0px sweep에서도 같은 방향이 유지돼 candidate+jitter
instability가 기존 unaligned 지표만의 현상이 아님을 확인했다.

최종 8-case에서 camera-motion thin-lines의 Edge-selective는 대응 Standard보다
aligned residual이 9.365~14.055% 낮았고 camera reprojection On도 Off보다
4.561~9.500% 낮았다. 반면 고정-camera rotor의 Standard는 대응 1X보다 약
16.25~16.52% 낮았지만 visible double ghost를 동반했고, Edge-selective는 1X 대비
-0.090~+0.043%로 거의 동일했다. 이는 현재 ET2X가 object ghost를 줄이는 대신
temporal supersampling을 상당 부분 잃었다는 기존 해석을 보강한다.

Flow metric도 ground truth는 아니다. 불일치 mask가 disocclusion 경계를 제외하고,
blur도 residual을 낮출 수 있으므로 절대 품질 순위로 사용하지 않는다. 상세 결과는
`Docs/SMAA-Optical-Flow-Temporal-Results-ko.md`에 기록한다. 다음 구현 후보는
candidate-aware jitter 또는 비후보 안정화이며, 필요 시 supersample ground truth를
먼저 추가한다.

### 17.28 Supersample spatial-reference proxy

2026-07-30에 같은 stress timeline을 선형 2배 해상도, frame 내부 3×3 subpixel
grid와 각 render의 8×MSAA로 렌더하는 spatial-reference proxy를 추가했다.
Temporal history가 없는 현재 프레임 reference이며 path-traced 또는 temporal
ground truth로 표현하지 않는다.

3개 시나리오의 60 warm-up + 240-frame reference와 `O-1X`, `O-T2X-R`,
Candidate Jitter/NoJitter를 비교했다. Object-motion rotor에서 `O-T2X-R`의
reference MAE는 `O-1X`보다 349.136% 높고 이중 잔상이 명확했다. Candidate
NoJitter는 모든 ROI에서 O-1X 대비 -4.993~+10.171% 범위로 가까워, 안정화와 함께
temporal supersampling 손실이 발생했다는 해석을 보강했다. 상세 결과는
`Docs/SMAA-Supersample-Reference-Results-ko.md`를 기준으로 한다.

### 17.29 Candidate temporal·비후보 de-jitter hybrid

후보에는 T2X projection jitter와 camera-reprojected temporal resolve를 유지하고
비후보에는 현재 jitter를 bilinear inverse sample한 spatial base를 제공하는
`ABL-Candidate-DeJitter-R`을 별도 diagnostic으로 구현했다. 최종 8-case나 Intel
공식 TSCMAA mode가 아니다.

Release x64 build와 temporal lifecycle을 통과한 뒤 3개 stress 시나리오를 mode별
60 warm-up + 240-frame으로 캡처했다. DeJitter는 Candidate Jitter보다
flow-aligned residual을 4.809~15.254%, supersample reference MAE를
7.956~15.908% 줄였다. 그러나 Candidate NoJitter보다 reference MAE가
8.831~29.242%, O-1X보다 16.063~35.011% 높고 bilinear 역이동의 경계 연화가
남았다.

따라서 screen-space de-jitter 가설은 부분적으로만 지지됐고 최종 방식으로 채택하지
않는다. 품질상 채택 근거가 없어 추가 full-screen compute pass의 정식 성능 본
측정은 진행하지 않았다. 상세 구현·표·산출물은
`Docs/SMAA-Hybrid-Resolve-Ablation-Results-ko.md`를 기준으로 한다.

다음 우선순위는 candidate-aware stabilization band를 바로 추가하기 전에 현재
엔진에서 object motion vector를 생성하고 SMAA temporal resolve에 전달할 수 있는지
조사하는 것이다. 현재 `-R`은 camera motion만 보정하므로 독립 object-motion
ghosting의 구조적 한계를 해결하지 못한다.

### 17.30 Current-edge 3×3 dilation ablation

교수님이 제안한 현재 프레임 edge 영역 확장을 Candidate-Jitter와 document profile에
각각 직교하는 3×3 toggle로 구현했다. raw candidate mask와 dilation pass를 분리하고
확장된 mask를 candidate compact/indirect resolve에 연결했다. 이전 프레임 edge mask와
object motion vector는 사용하지 않으며 최종 8-case도 변경하지 않았다.

Bistro/Minecraft `yaw-fast-360`에서 GPU mask와 CPU의 정확한 3×3 max-filter가
mismatch 0 pixel이었고 독립 반복 capture의 4 mode×60 PNG도 모두 동일했다. 후보 수는
약 2.9~3.2배, reference 구조 recall과 관측 history 영향은 증가했다. Candidate-Jitter의
CGVQM-2는 Bistro +0.7735, Minecraft +0.2121이었지만 document profile은 각각
+0.0362, -0.3994로 일관되지 않았다.

120 warm-up + 600 measurement frame×3회 hidden engineering 측정에서 SMAA GPU 시간은
Candidate-Jitter +17.306%, document +18.639%였다. 따라서 3×3은 temporal coverage를
확실히 늘리지만 현재 경로의 성능 최적화가 아니며, document profile의 temporal 손실을
일관되게 복구하지도 못했다. 5×5/7×7은 즉시 진행하지 않는다.

상세 구현, 조건, 품질·성능 표와 산출물은
`Docs/SMAA-Current-Edge-Dilation-3x3-Results-ko.md`를 기준으로 한다. 다음 ablation은
nearest-neighbor가 아닌 filtered 1/4 downsample-upsample 후보 확장으로 제한하며,
3×3보다 낮은 비용과 후보 증가율의 가능성을 먼저 engineering smoke로 확인한다.

### 17.31 Filtered 1/4 candidate expansion engineering gate

교수님 제안에 따라 nearest-neighbor를 사용하지 않는 filtered 1/4 후보 확장을
Candidate-Jitter와 document profile에 각각 직교하는 toggle로 구현했다. 4×4 valid-pixel
box average를 R8_UNORM quarter mask에 기록하고, half-pixel bilinear reconstruction 값이
0.25 이상인 full-resolution 픽셀만 compact한다. 이전 edge mask와 object motion vector는
사용하지 않으며 최종 8-case도 변경하지 않았다.

Bistro/Minecraft `yaw-fast-360` 3-frame engineering smoke에서 후보 배수는 3×3의
2.83~3.12×에 비해 Filtered가 1.57×였다. 그러나 120-frame 단일 성능 smoke에서
downsample+upsample mask 비용은 0.0628~0.0631 ms로 3×3의 0.0452~0.0455 ms보다
약 38.5~38.8% 높았다. SMAA total도 Filtered가 대응 None보다 23.2~24.3%, 3×3보다
3.5~3.7% 높았다.

따라서 “후보 증가율 감소”는 확인했지만 “3×3보다 낮은 mask 비용” engineering gate는
통과하지 못했다. 현재 구현의 60-frame 정식 품질·CGVQM과 600-frame×3회 성능 측정은
확대하지 않는다. 상세 정의, 검증 한계와 산출물은
`Docs/SMAA-Filtered-Quarter-Candidate-Expansion-Smoke-ko.md`를 기준으로 한다.
