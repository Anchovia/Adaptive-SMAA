# TSCMAA 문서 기반 SMAA temporal 연구 설계

## 1. 목적과 명칭

이 브랜치의 목표는 V2 `SMAA_T2x (Reprojected)`를 기준으로 Intel TSCMAA가 공개한
temporal 처리 구조를 SMAA에 적용하고 품질과 성능을 검증하는 것이다.

Intel TSCMAA는 본래 `CMAA + selective TAA`이므로, 이 구현을 공식 TSCMAA의 완전한
재현이라고 부르지 않는다. 연구 및 UI에서의 명칭은 다음과 같이 제한한다.

> TSCMAA-inspired edge-selective temporal SMAA

기존 `research/edge-guided-t2x`의 V3/V4 실험은 아이디어 탐색 기록으로만 보존하며,
이 문서 기반 구현의 결과나 논문 본문 결과에는 포함하지 않는다.

## 2. 기준선

- 기준 커밋: `88893da` (`Implement camera-reprojected SMAA T2X baseline`)
- V0: SMAA 1X
- V1: Naive SMAA T2X
- V2: camera-reprojected SMAA T2X
- 새 구현: TSCMAA-inspired edge-selective temporal SMAA

V2가 이미 제공하는 기능은 다음과 같다.

- 공식 SMAA T2X의 2개 jitter 위치와 subsample index
- 현재 depth와 현재/이전 view-projection을 이용한 camera reprojection
- 2개의 temporal texture
- 첫 프레임, 모드 전환, 해상도 변경 시 history reset

V2의 reprojection은 카메라 움직임만 처리한다. 움직이는 물체의 object motion vector는
현재 렌더러에 연결되어 있지 않다.

## 3. 출처 우선순위

1. Intel TSCMAA 공식 문서
   - <https://www.intel.com/content/dam/develop/external/us/en/documents/tscmaa-codesample-v1.pdf>
2. Intel TSCMAA 특허
   - <https://patents.google.com/patent/US20190236758A1/en>
3. Intel CMAA2 공식 설명 및 현재 저장소의 CMAA2 구현
   - <https://www.intel.com/content/www/us/en/developer/articles/technical/conservative-morphological-anti-aliasing-20.html>
4. 공식 SMAA 논문과 공식 HLSL
   - <https://www.iryoku.com/smaa/downloads/SMAA-Enhanced-Subpixel-Morphological-Antialiasing.pdf>
   - <https://github.com/iryoku/smaa/blob/master/SMAA.hlsl>
5. 공개된 temporal filtering 1차 자료
   - Marco Salvi, *An Excursion in Temporal Supersampling*
     <https://developer.download.nvidia.com/gameworks/events/GDC2016/msalvi_temporal_supersampling.pdf>
   - Jorge Jimenez, *Filmic SMAA: Sharp Morphological and Temporal Antialiasing*
     <https://advances.realtimerendering.com/s2016/>

## 4. 공식 문서에서 확인되는 동작

| 항목 | 공개된 내용 |
|---|---|
| 처리 대상 | edge detection이 만든 후보에만 CMAA와 TAA를 수행 |
| TAA 후보량 | CMAA edge 후보의 50%를 기본값으로 사용하며 조절 가능 |
| 실행 구조 | 후보 목록과 indirect shader dispatch 사용 |
| 재투영 | 현재 depth와 view/projection을 사용해 이전 texture coordinate 계산 |
| history sampling | Hermite/Catmull–Rom bicubic의 5-tap 근사 |
| history validation | YCoCg 공간에서 variance clipping |
| blend | TAA 후보는 history weight `0.8`, 비후보는 `0.0` |
| feedback | 최종 temporal resolve 결과가 다음 프레임 history가 됨 |
| 기본 edge threshold | `1/22` |
| 기본 non-dominant removal | `0.5` |

## 5. 공식 자료만으로 확정할 수 없는 내용

Intel 문서와 특허는 다음 세부 구현을 공개하지 않는다.

- CMAA 후보 중 TAA 후보 50%를 고르는 정확한 코드와 순서
- 5-tap Catmull–Rom의 정확한 좌표/가중치 구현
- YCoCg 변환식, variance window 크기, gamma, AABB clip 함수
- 움직이는 물체의 motion vector 처리 방식
- 의도적인 subpixel projection jitter 사용 여부

과거 Intel 페이지에 76.6 MB 코드 샘플이 첨부되어 있었으나 현재 링크는 제거되었고,
공식 PDF에도 소스 attachment가 포함되어 있지 않다. 따라서 위 항목을 공식 코드와
동일하다고 주장해서는 안 된다.

## 6. 이 프로젝트에서 사용하는 명시적 구현 가정

### 6.1 TAA 후보 선정

SMAA edge texture에서 현재 edge를 찾고, 현재 luma 차이로 edge strength를 계산한다.
3x3 이웃의 평균과 최댓값 사이를 `nonDominantEdgeRemovalAmount = 0.5`로 보간한
threshold보다 강한 edge만 temporal 후보로 사용한다.

이 규칙을 선택한 이유는 다음과 같다.

- Intel 문서가 50%를 장면 기반 기본값이라고 표현한다.
- 공개된 Figure 2는 규칙적인 checkerboard가 아니라 약한 세부 edge가 제거된 형태다.
- Intel API가 `nonDominantEdgeRemovalAmount = 0.5`를 edge 수 조절값으로 노출한다.

단, 이 규칙이 유실된 Intel 코드와 동일하다는 근거는 없다. 실제 후보 비율은 장면마다
측정하며, 50%와 다르면 그대로 기록한다.

### 6.2 5-tap Catmull–Rom

4x4 Catmull–Rom을 9개의 bilinear sample로 계산하는 공개식에서 네 모서리 sample을
제외하고 center, left, right, top, bottom의 5개 sample만 사용한다. 이는 Filmic SMAA
발표에서 제안된 5-tap 형태다. 제외된 모서리 때문에 남은 가중치 합으로 결과를
정규화한다.

### 6.3 Variance clipping

- 현재 spatial SMAA 결과의 3x3 이웃을 RGB에서 YCoCg로 변환
- 1차/2차 moment에서 평균과 표준편차 계산
- `gamma = 1.0`
- `mean ± gamma * sigma`를 이웃 min/max AABB로 제한
- 현재 color에서 history color로 향하는 선분을 AABB에 clip
- 결과를 RGB로 역변환

이는 Salvi의 variance clipping 설명을 구현한 것이며 Intel의 유실된 세부 코드와
byte-for-byte 동일하다는 의미는 아니다.

### 6.4 색 공간

temporal blend와 variance clipping은 linear color에서 수행한다. history UAV가 sRGB
view와 같은 typeless resource를 사용할 경우, compute shader의 UNORM UAV store 전에
linear-to-sRGB 변환을 명시적으로 수행한다.

### 6.5 Spatial 입력과 projection jitter

TSCMAA-inspired 모드는 현재 프레임의 spatial 입력으로 SMAA 1X를 사용하며, 의도적인
SMAA T2X projection jitter를 적용하지 않는다. Intel 공개 문서는 head pose 및 프레임
간 motion에 대한 temporal accumulation은 설명하지만 별도의 subpixel render jitter는
명시하지 않는다.

초기 구현에서 화면 전체에 SMAA T2X jitter를 적용하고 비후보 픽셀의 history weight를
공식 설명대로 `0.0`으로 두자, 정지 장면의 비후보 픽셀이 두 jitter 위치를 그대로
번갈아 출력했다. 이는 selective TAA와 맞지 않으므로 제거한다. V2의 jittered
reprojected SMAA T2X는 비교 기준선으로 그대로 유지한다.

## 7. 구현 파이프라인

1. SMAA 1X spatial pass를 실행해 현재 spatial SMAA 결과와 SMAA edge texture 생성
2. 현재 spatial 결과를 새 history texture의 초기값으로 복사
3. full-resolution compute shader에서 locally dominant SMAA edge 후보를 compact buffer에 기록
4. 후보 수로 `DispatchIndirect` argument 생성
5. 후보에 대해서만 다음 작업 수행
   - camera velocity로 history UV 계산
   - 화면 밖 history 거부
   - 5-tap Catmull–Rom history sampling
   - 현재 3x3 YCoCg variance clipping
   - current 0.2 / history 0.8 blend
6. 최종 결과를 현재 history에 저장
7. 현재 history를 화면 출력으로 복사
8. 현재/이전 history를 ping-pong하고 최종 결과를 다음 프레임에 사용

비후보 픽셀은 2단계에서 복사된 현재 spatial SMAA 값이 그대로 유지된다.

## 8. 성능 해석의 제한

후보 추출은 full-resolution pass이므로 그 비용은 해상도에 비례한다. temporal resolve는
후보 목록에 대해서만 indirect dispatch하지만, 현재 spatial 결과를 history/output으로
복사하는 bandwidth 비용은 남는다.

따라서 다음을 분리해 측정한다.

- candidate extraction GPU time
- indirect temporal resolve GPU time
- spatial-to-history copy를 포함한 전체 SMAA time
- SMAA edge 수와 temporal 후보 수

후보 수 감소만으로 성능 향상을 주장하지 않는다.

## 9. 검증 순서

1. Release x64 빌드 및 shader compilation 확인
2. 첫 프레임, 모드 전환, resize에서 검은 화면/깨짐/종료가 없는지 확인
3. 정지 카메라에서 jitter 떨림이 없는지 확인
4. 동일 flythrough에서 V2와 새 구현을 연속 프레임/GIF로 비교
5. 움직이는 물체, disocclusion, 얇은 선에서 ghosting, flicker, blur 비교
6. GPU profiler로 pass별 시간과 후보 수 반복 측정

## 10. 결과 표기 원칙

- `공식 TSCMAA`라고 표기하지 않는다.
- `Intel TSCMAA 공개 구조를 SMAA에 적용한 edge-selective temporal 구현`이라고 표기한다.
- 공개 문서에 없는 후보 선정 규칙과 filter 세부식은 연구 가정으로 명시한다.
- V2보다 품질 또는 성능이 나쁘더라도 결과를 제외하지 않는다.
- 기존 V3/V4 탐색 결과는 이 구현의 근거 또는 최종 결과로 사용하지 않는다.

## 11. 구현 검증 기록

다음 값은 정식 품질·성능 결과가 아니라 projection jitter 오류를 찾기 위한 엔지니어링
검증이다. 1920x1017, 정지된 Lumberyard Bistro 카메라에서 연속 16프레임을 저장했다.

| 상태 | 인접 프레임 평균 MAE | 변경 픽셀 비율 | 2프레임 간격 MAE |
|---|---:|---:|---:|
| full-frame T2X jitter + selective TAA | 3.7014 | 75.7% | 약 0 |
| SMAA 1X spatial + selective TAA | 0.000004 | 약 0.00039% | 약 0 |

첫 구현은 홀수·짝수 프레임이 두 상태로 정확히 반복되어 정지 장면에서도 심한 떨림이
발생했다. 의도적인 T2X projection jitter를 제거한 뒤 4번째 캡처부터 모든 프레임이
완전히 동일했다. 이 검증은 떨림 오류가 제거됐다는 뜻이며, 움직이는 장면의 ghosting,
flicker 및 성능 개선을 입증하는 결과는 아니다.
