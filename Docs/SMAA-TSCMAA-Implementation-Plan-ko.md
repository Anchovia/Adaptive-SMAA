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

### 단계 5: variance clipping

- YCoCg 변환과 variance clipping 독립 구현
- 상수·유효 history·outlier test와 debug view 검증
- clipping 변경만 비교하는 ablation 캡처

### 단계 6: Intel document profile 조립

- threshold `1/22`, non-dominant `0.5`
- candidate compaction + indirect dispatch
- depth/matrix reprojection
- 5-tap history sampling
- YCoCg variance clipping
- 후보 history weight `0.8`, 비후보 `0.0`
- 최종 output history feedback

이 단계까지 모든 검증표가 통과해야 `O-ET2X-R core 구현 완료`로 표시한다.

### 단계 7: lifecycle·성능 smoke

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
- [ ] YCoCg variance clipping 불변 조건 검증
- [x] 후보 history weight `0.8` 설정 및 resolve 경로 연결
- [x] 비후보 history weight `0.0`, 즉 current spatial 유지 픽셀 검증
- [ ] 최종 output의 history feedback
- [x] 첫 프레임·mode·scene·명시적 camera-cut·resize reset
- [ ] static camera 떨림 없음
- [x] object motion 미지원 사실 명시
- [ ] 각 pass GPU time과 후보 비율 기록 가능
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

**단계 1, 단계 2와 단계 3의 controlled selective resolve·lifecycle·camera-motion
reprojection 검증을 완료했다.**

- Original 네 semantic mode를 UI, 로그와 deterministic capture에 연결
- `TemporalCoverage`, `ReprojectionMode`, `JitterPolicy`, sampler, clipping,
  candidate policy와 history weight를 명시적 설정으로 분리
- `O-ET2X` no-reprojection prototype 실행 경로 추가
- threshold `1/22`인 별도 full-resolution base luma edge 검출 구현
- `AllBaseEdges`, `IntelFamilyNonDominant`, `ExperimentalLocalMeanMax3x3` 정책 분리
- candidate compact buffer와 indirect process/group count를 비동기 staging buffer로 readback
- base edge와 selected candidate R8 debug mask 및 개발 UI 구현
- 기존 prototype의 기본 정책은 `ExperimentalLocalMeanMax3x3`으로 유지하고, UI 또는
  `-smaaCandidatePolicyOverride`에서만 다른 정책을 선택
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

다음 작업은 단계 5의 YCoCg variance clipping 불변 조건과 debug view 검증이다.
