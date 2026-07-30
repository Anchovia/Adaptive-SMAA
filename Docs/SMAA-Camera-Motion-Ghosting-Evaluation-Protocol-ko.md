# SMAA 카메라 운동 고스팅 평가 프로토콜

## 1. 목적

이 문서는 교수 피드백에 따라 다음 두 항목을 연구의 우선 검증 과제로 정의한다.

1. 고스팅을 눈으로만 판단하지 않고, 공개 논문에 근거한 영상 품질 지표와
   현재 프레임 reference를 함께 사용한다.
2. 새 장면을 계속 추가하기보다 기존 동적 장면에서 카메라 운동을 통제해
   Standard T2X, TSCMAA-inspired edge-selective T2X와 camera reprojection의 효과를
   분리한다.

이번 실험은 기존 최종 8-case를 변경하지 않는다. `-R`의 의미도 기존과 동일한
camera-motion reprojection On이다. 별도 object-motion vector 진단은 이번 측정에서
사용하지 않는다.

## 2. 장면 구성

기존 두 동적 장면을 대비 특성이 다른 비교군으로 사용한다.

| 장면 | 연구상 분류 | 주 관찰 대상 |
|---|---|---|
| Lumberyard Bistro | 저대비 동적 장면 | 완만한 명암 경계, 재질·조명 변화에서의 history lag |
| Minecraft Lost Empire | 고대비 동적 장면 | 강한 윤곽선, 얇은 구조와 고대비 edge의 trail·flicker |

두 장면의 `저대비/고대비` 분류는 실험 가설로 명시하고, 캡처 시 전체 luma 분포,
local contrast 분포, base edge 수와 candidate 수를 함께 기록해 수치로 보강한다.
한 장면 결과를 다른 장면에 일반화하지 않는다.

카메라 운동만 분리하는 첫 실험에서는 가능한 한 장면 애니메이션을 고정한다. 장면
애니메이션을 고정할 수 없다면 동일 fixed timestep과 동일 frame index를 사용하고,
그 사실을 provenance에 기록한다.

## 3. 고스팅의 조작적 정의

이 연구에서 고스팅은 현재 프레임에 존재하지 않아야 할 이전 프레임의 형상 또는 색이
history feedback 때문에 남는 현상으로 정의한다.

다음 현상은 구분해 기록한다.

- `ghost trail`: 운동 방향 뒤쪽에 남는 이전 형상
- `image lag`: 현재 카메라 자세보다 이전 화면이 지연되어 보이는 현상
- `disocclusion ghost`: 새로 드러난 영역에 유효하지 않은 history가 남는 현상
- `blur`: 현재 형상과 이전 형상이 섞여 경계가 넓어진 현상
- `flicker/shimmer`: history 거부 또는 불안정한 sample 때문에 시간 변화가 증가한 현상

낮은 frame-to-frame 변화량만으로 고스팅 감소를 주장하지 않는다. 고스팅과 blur는
오히려 시간 변화량을 낮출 수 있기 때문이다. 반대로 현재 프레임 reference와 가까워도
temporal supersampling을 전부 잃고 1X로 돌아간 결과일 수 있다.

## 4. 근거 문헌과 지표의 역할

### 4.1 주 지표: Intel CGVQM

Akshay Jindal et al., *CGVQM+D: Computer Graphics Video Quality Metric and
Dataset*, Computer Graphics Forum, 2025.

- 논문: <https://arxiv.org/abs/2506.11546>
- 공식 코드: <https://github.com/IntelLabs/CGVQM>
- 실시간 컴퓨터 그래픽의 aliasing, flicker, ghosting 등 시공간 왜곡을 포함한
  full-reference 영상 품질 평가를 목표로 한다.
- 전역 품질 점수와 위치별 error map을 함께 제공한다.
- 본 연구에서는 같은 카메라 경로의 supersample spatial-reference proxy와 각 SMAA
  결과를 비교한다.

CGVQM도 학습 데이터와 pooling의 한계가 있으므로 단독 절대 고스팅 점수로 표현하지
않는다. 같은 frame range, 해상도, 색공간과 encoding을 사용한 대응 case의 상대 비교에
사용한다.

### 4.2 지각적 교차검증: FovVideoVDP 또는 ColorVideoVDP

Rafal Mantiuk et al., *FovVideoVDP: A visible difference predictor for
wide field-of-view video*, ACM TOG/SIGGRAPH, 2021.

- 논문·코드: <https://www.cl.cam.ac.uk/research/rainbow/projects/fovvideovdp/>
- 공간·시간 대비 민감도와 지각 조건을 반영한 full-reference 영상 차이 지표다.
- CGVQM과 다른 모델 계열의 독립적인 교차검증으로 사용한다.
- 특정 TAA 고스팅 검출기라고 표현하지 않는다.

### 4.3 보조 지표: motion-compensated warping error

Wei-Sheng Lai et al., *Learning Blind Video Temporal Consistency*, ECCV 2018.

- 논문: <https://openaccess.thecvf.com/content_ECCV_2018/html/Wei-Sheng_Lai_Real-Time_Blind_Video_ECCV_2018_paper.html>
- optical flow로 이웃 프레임을 정렬하고 non-occlusion mask 안의 warping error를
  temporal stability 지표로 사용한다.
- 기존 Farneback 분석은 이 계열의 보조 지표로 유지한다.
- flow 불일치 mask가 disocclusion을 제외할 수 있고 blur도 작은 residual을 만들 수
  있으므로 주 고스팅 판정에는 사용하지 않는다.

### 4.4 TAA 고스팅 해석 근거

Lei Yang et al., *A Survey of Temporal Antialiasing Techniques*,
Computer Graphics Forum, 2020.

- 논문: <https://diglib.eg.org/bitstreams/53732e70-b64d-46f4-bbae-865eb7673a35/download>
- stale history를 그대로 재사용하면 ghosting과 image lag가 발생한다.
- 잘못된 history 보존은 ghosting을, 과도한 history 거부는 flicker와 temporal
  instability를 만들 수 있다.
- 따라서 `고스팅 감소`와 `temporal supersampling 유지`를 별도 축으로 평가한다.

Julius Ikkala et al., *k-DOP Clipping: Robust Ghosting Mitigation in Temporal
Antialiasing*, SIGGRAPH Asia Technical Communications, 2024.

- DOI: <https://doi.org/10.1145/3681758.3697996>
- current neighborhood로 history를 검증·제한하는 TAA 고스팅 완화 연구다.
- 이번 단계의 검출 지표는 아니지만 향후 clipping ablation과 ghosting 사례 설계의
  참고 문헌으로 사용한다.

## 5. Reference 정의

각 카메라 자세와 장면 시점마다 temporal history 없이 현재 프레임을 고품질로 렌더한
`SuperSampleReference`를 사용한다.

초기 reference profile은 기존 검증 경로를 재사용한다.

- 선형 해상도 2배
- 출력 frame당 3×3 subpixel grid
- 각 subpixel render에 8×MSAA
- 9회 render 동안 카메라와 장면 상태 고정
- temporal history와 이전 프레임 feedback 없음
- test mode와 동일한 tone mapping, exposure, 출력 해상도

이는 path-traced 또는 temporal ground truth가 아니라 **현재 프레임
supersample spatial-reference proxy**다. CGVQM 입력에는 reference와 test를 동일한
lossless encoding 또는 직접 디코딩한 PNG sequence로 제공한다. 서로 다른 손실 압축
설정을 사용하지 않는다.

## 6. 카메라 운동 프로파일

각 프로파일은 fixed 60 Hz에서 독립 실행하고 시작할 때 history를 reset한 뒤 같은
warm-up을 적용한다.

| 프로파일 | 프레임 구성 | 각속도 | 목적 |
|---|---|---:|---|
| `yaw-slow-360` | 정지 60 + 회전 240 + 정지 60 | 90°/s, 1.5°/frame | 일반적인 회전 안정성 |
| `yaw-fast-360` | 정지 60 + 회전 60 + 정지 60 | 360°/s, 6°/frame | 빠른 회전의 history 정렬 |
| `yaw-extreme-360` | 정지 60 + 회전 30 + 정지 60 | 720°/s, 12°/frame | 큰 history UV 이동 stress |
| `strafe-fast` | 정지 60 + 평행이동 120 + 정지 60 | 장면별 고정 거리 | parallax와 disocclusion |
| `yaw-strafe-fast` | 정지 60 + 회전·이동 120 + 정지 60 | 고정 path | 실제적인 복합 camera motion |

한 frame 안에서 정확히 360° 회전하면 시작과 종료 자세가 같아 유효한 운동 sequence가
되지 않는다. 360° 회전은 반드시 여러 frame에 걸쳐 수행한다.

순수 회전은 카메라 중심을 고정해 camera reprojection과 큰 history UV 이동을 우선
분리한다. 평행이동은 depth/parallax와 disocclusion을 추가로 검증한다. 따라서 순수
회전 결과를 일반적인 disocclusion 성능으로 확대 해석하지 않는다.

90° 또는 180° camera cut은 별도 lifecycle 진단으로 분류한다. 명시적 cut에서는
history reset이 정상 동작하는지를 검증하고, reset하지 않은 결과는 알고리즘 본
품질이 아니라 실패 대조군으로만 사용할 수 있다.

## 7. 비교 순서

### 7.1 평가 경로 축소 검증

먼저 Original 공간 처리에서 다음 control과 네 temporal case를 비교한다.

| ID | 역할 |
|---|---|
| `O-1X` | temporal history가 없는 spatial control |
| `O-T2X` | Standard full-screen T2X, reprojection Off |
| `O-T2X-R` | Standard full-screen T2X, camera reprojection On |
| `O-ET2X` | TSCMAA-inspired edge-selective T2X, reprojection Off ablation |
| `O-ET2X-R` | TSCMAA-inspired edge-selective T2X, camera reprojection On |
| `SS-Reference` | 현재 프레임 supersample spatial-reference proxy |

이 실행은 평가 파이프라인 검증이다. `O-T2X` 시작 frame hash 비결정성의 기존 관측을
기록하고, sequence-level 지표와 반복 실행으로 재현성을 확인한다.

### 7.2 정식 비교

축소 검증을 통과한 뒤 `O-1X`/`A-1X` control, 최종 8-case와 같은 frame index의
reference를 Bistro와 Minecraft 양쪽에서 측정한다. 두 장면 결과를 합친 평균만
제시하지 않고 장면별 결과를 우선 보고한다.

## 8. 정량 지표

### 8.1 Reference 기반

- CGVQM-5 및 가능하면 CGVQM-2 전역 점수
- CGVQM 위치별 error map의 평균, p95와 threshold 초과 면적
- reference 대비 RGB MAE, PSNR, luma SSIM
- reference 대비 edge strength 비율
- 대응 frame의 최대 오차와 평균 오차

### 8.2 시간 및 운동 보정

- adjacent-frame RGB MAE
- 2차 temporal luma difference
- camera matrix/depth 기반 또는 optical-flow 기반 aligned residual
- 정렬 유효 픽셀 비율
- 짝·홀 jitter phase gap

### 8.3 잔상 지속 시간

회전 또는 이동이 끝난 뒤 정지 구간에서 다음을 기록한다.

- `peak post-stop error`: 정지 시작 후 최대 reference error
- `ghost area`: baseline threshold를 초과한 픽셀 비율
- `recovery frames`: error가 정상상태 threshold 이하로 5 frame 연속 유지될 때까지의
  frame 수

정상상태 threshold는 임의의 고정 색 차이 하나로 정하지 않는다. 같은 mode의 회전 전
정지 구간 평균과 표준편차, `O-1X`와 reference의 공간 오차를 함께 사용해 사전에
고정한다. threshold 정의는 결과를 본 뒤 변경하지 않는다.

## 9. 공통 측정 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- API: DirectX 11
- Release x64
- SMAA Ultra
- VSync Off
- fixed timestep 60 Hz
- 동일 해상도와 tone mapping/exposure
- 동일 camera pose sequence와 frame index
- mode별 동일 warm-up
- camera motion만 비교하는 첫 실행에서는 object-motion vector 미사용
- PNG/reference capture는 품질 자료이며 FPS 결과로 사용하지 않음
- 성능 측정에서는 PNG 저장, CGVQM과 candidate readback을 끔

## 10. 성공 조건과 해석 제한

고스팅 개선은 다음을 함께 만족할 때만 주장한다.

1. Standard 대응 case보다 reference 기반 CGVQM 또는 교차 지표가 개선된다.
2. error map에서 이전 형상 방향의 잔상 면적·강도·유지 frame이 감소한다.
3. `O-1X`와 거의 동일해진 것만으로 설명되지 않고 temporal 안정성 이득이 남는다.
4. shimmer/flicker 지표가 심각하게 증가하지 않는다.
5. Bistro 저대비와 Minecraft 고대비 결과를 분리해 재현성을 확인한다.

CGVQM, FovVideoVDP, optical-flow residual, supersample reference 중 어느 하나도
단독 절대 ground truth로 표현하지 않는다. 최종 결론에는 정량 표, error map,
연속 frame/GIF와 동일 조건의 육안 비교를 함께 제시한다.

## 11. 구현 및 검증 순서

1. Intel CGVQM 공식 코드와 공개 weight의 실행 환경을 별도 local research tool로 구성
2. 공식 sample reference/distorted pair로 CPU/CUDA smoke
3. PNG sequence의 연속 index·해상도·frame 수를 검증하는 입력 adapter 작성
4. lossless sequence 변환과 frame round-trip hash 또는 pixel 일치 검증
5. 기존 supersample capture 한 쌍으로 CGVQM integration smoke
6. Bistro/Minecraft deterministic camera profile 구현
7. Original 5-way + reference 축소 capture
8. CGVQM/error-map/recovery 분석 검증
9. 최종 8-case 양 장면 품질 측정

### 11.1 Windows Python 3.12 호환 환경

2026-07-30에 IntelLabs/CGVQM 공식 commit
`8302ff45b4ff5a691682baf23f7c007d6b591e98`을 기준으로 환경 구성을 시작했다.
공식 requirements의 PyTorch/CUDA, NumPy와 Pandas 버전은 그대로 유지한다.

공식 `av==14.4.0`은 Windows CPython 3.12 binary wheel이 없어 로컬 FFmpeg 개발
header를 요구하는 source build가 실패한다. 시스템 Python이나 FFmpeg SDK를 전역
설치하지 않고, 같은 `torchvision.io`/PyAV API를 제공하는 가장 가까운 Python 3.12
binary release인 `av==15.1.0`을 사용한다.

재현 requirements:

- `Tools/SMAA/requirements-cgvqm-python312.txt`

이 호환 변경은 공식 CGVQM 모델, weight, 전처리, feature difference와 pooling 식을
수정하지 않는다. 공식 Dock sample CUDA smoke와 PNG→FFV1→RGB pixel-exact round-trip
검증을 모두 통과해야만 integration을 승인한다.

### 11.2 CGVQM 및 PNG adapter engineering smoke 결과

2026-07-30에 RTX 3060 Ti에서 다음 환경을 확인했다.

| 항목 | 값 |
|---|---|
| Python | 3.12.13 |
| PyTorch | 2.8.0+cu128 |
| Torchvision | 0.23.0+cu128 |
| PyAV | 15.1.0 |
| CUDA runtime | 12.8 |
| `torch.cuda.is_available()` | `true` |
| GPU | NVIDIA GeForce RTX 3060 Ti |

Intel 공식 `media/Dock_dist.mp4`와 `media/Dock_ref.mp4`를 수정하지 않은
`cgvqm.py`로 실행했다. CGVQM-2 CUDA 실행은 완료됐고 `73.62/100`과 공식
error-map MP4를 생성했다. 이 값은 환경 smoke이며 본 SMAA 결과가 아니다.

이후 `Tools/SMAA/run_cgvqm_png_sequences.py`를 기존 thin-lines 캡처의 첫
30 frame에 적용했다.

- test:
  `Projects/CMAA2/AutoBench/20260730_141450/O_T2X_R`
- reference:
  `Projects/CMAA2/AutoBench/20260730_152152/SS_Reference`
- 출력:
  `Projects/CMAA2/AutoBench/20260730_152152/CGVQMIntegrationSmoke`
- 해상도: 1920×1017
- frame: 00000~00029
- FPS: 60
- model: CGVQM-2
- patch scale: 3
- pooling: mean

공식 demo의 patch scale 기본값은 4지만 캡처 높이 1017이 4로 나누어떨어지지 않는다.
이 smoke에서는 공간 padding 경고와 error-map 크기 불일치를 피하기 위해 너비 1920과
높이 1017을 모두 정확히 나누는 3을 사용했다. 정식 대응 비교에서도 같은 해상도와
patch scale을 모든 mode에 고정한다.

PNG sequence는 frame index, 연속성, 해상도와 pixel SHA-256을 먼저 검증했다.
FFV1/BGR0 Matroska로 변환한 뒤 RGB24로 다시 decode해 전체 30 frame을 비교했다.
test와 reference 모두 mismatched channel value `0`, maximum absolute difference
`0`으로 pixel-exact round-trip을 통과했다.

Engineering smoke의 CGVQM-2 결과는 다음과 같다.

| 항목 | 값 |
|---|---:|
| CGVQM-2 score | 99.4658126831 |
| error-map mean | 0.534189284 |
| error-map p95 | 1.723288774 |
| error-map p99 | 10.627346992 |
| error-map maximum | 206.277404785 |

같은 입력을 별도 출력 디렉터리에서 다시 실행했고 CGVQM score와 error-map 통계가
동일했다. 두 per-frame CSV의 SHA-256도
`B34DE4BBDFC326D3E4FBE018E9CBD4AAF63BAB8421A421EC7B766358196318A2`로 일치했다.
홀수 높이를 거부하는 공식 libx264/yuv420p 시각화 대신 RGB 계열 FFV1로 error map을
저장했고, 1920×1017, 60 FPS, 30 frame을 확인했다.

이 결과는 CGVQM 통합과 무손실 입력 경로의 **engineering validation**이다. 기존
thin-lines capture의 품질 결론을 다시 내리는 자료가 아니며, 교수 피드백에 따른
Bistro/Minecraft 급격한 camera-motion 본 결과로 사용하지 않는다.

공식 CGVQM loader는 입력 영상 전체와 error map을 메모리에 유지한다. 정식 장시간
sequence는 먼저 메모리 사용량을 확인한다. 임의로 30-frame 파일 여러 개로 나누면
temporal clip 경계와 전역 mean/max pooling 정의가 달라질 수 있으므로, 분할 방식의
수학적 동등성을 별도로 검증하기 전에는 한 sequence의 점수처럼 합치지 않는다.
