# 1차 edge texture의 temporal 읽기 비용 분리

## 질문과 범위

Original SMAA `O-T2X-R`의 기존 temporal pixel pass에서, 이미 생성된 첫 pass의
`edgesRT` RG 정보를 그대로 읽는 추가 비용을 측정한다. 재계산한 luma 대비나
2차 blending weight를 사용하지 않는다. camera-motion reprojection On, paired
T2X jitter/subsample pattern On, 원본 spatial-frame history/혼합식을 유지한다.
이는 진단 ablation이며 최종 8-case 또는 품질 개선 구현이 아니다.

## 비교 조건

1. `O-T2X-R`: 원본 resolve.
2. `ABL-EdgeBindOnly-R` (kind 54): 원본 shader + 기존 edgesRT를 t8에 연결/해제.
3. `ABL-EdgeReadControl-R` (55): 위 연결 + native.rg에 runtime-zero × 상수 RG를 더함.
4. `ABL-EdgeReadOne-R` (56): 위 연결 + 현재 정수 픽셀의 edgesTex.Load RG를
   native.rg에 runtime-zero × RG로 더함. native.ba는 그대로 보존.

컴파일러가 사용하지 않는 읽기를 삭제하지 않도록 runtime-zero인 padding0를 사용한다.
Control과 One은 같은 두 채널 MAD를 사용한다. scale 1의 별도 capture 진단으로
실제 edge 입력이 출력에 영향을 주는지 확인하며 이 조건은 timing에서 제외한다.
DXBC의 살아 있는 t8 Load, RG 사용, 원본 sample 수와 무분기 구조를 검사한다.

`ReadOne−Control`은 읽기·좌표·의존성·레지스터·캐시와 입력 출처 차이를 포함한
증분 추정치다. `ReadOne−Native`에는 진단용 MAD도 포함된다. 순수 DRAM 전송 시간,
CPU→GPU 복사 시간 또는 edge 선택 방식의 완성된 성능이라고 표현하지 않는다.
새 texture/복사/후보 목록/pass는 없다. 읽은 RG는 shader 값으로 사용하며 별도
edge 저장 버퍼에 쓰지 않는다. shader의 Native BA 보존과 PNG의 RGB 검증을 구분한다.

## 리소스와 측정

SMAA.cpp는 NVIDIA에서 기본 edgeRT를 R8G8B8A8_UNORM으로 할당하고 RG에 edge를 저장한다.
실제 wrapper의 외부 storage 지정 여부도 확인한다. 물리 리소스 형식과 사용 채널을 혼동하지 않는다.
1920×1061 hidden, Bistro/Minecraft, 동일 결정론적 이동→정지 경로를 사용한다.
capture는 240프레임을 진행하되 0/1/60/61/140/179/180/200/201/239만 저장한다.
기존 Native capture와 hash bridge 및 zero-scale의 원본 출력 동일성을 확인한다.
성능은 clean process마다 30초 preconditioning, 조건별 300 warm-up,
4,800프레임 × 4회 정순/역순 교차 측정한다. smoke는 기능 확인만 사용한다.
캡처·후보 readback·CPU 영상 분석과 본 timing을 분리한다.

## API 근거

- [HLSL Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load): 정수 texel/mip 접근, filtering 없음.
- [PSSetShaderResources](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-pssetshaderresources): 기존 SRV 연결. Temporal 시점에 edgeRT는 출력 target이 아님을 확인한다.

이전 first-edge 선택 실험의 +8.45%/+31.32%에는 판정·분기·계산 생략이 섞여 있다.
해상도와 실행 조건도 다르므로 이번 값과 직접 빼서 분기 비용을 계산하지 않는다.
