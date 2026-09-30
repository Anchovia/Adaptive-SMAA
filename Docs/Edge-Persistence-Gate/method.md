# 직전 edge 한 프레임 유지 검증

- Branch: `validation/spatial-edge-persistence-gate`.
- Direct base: corrected case 6 `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459`.
- 대상: Original spatial SMAA + exact first-edge selective T2X-R, paired pattern Off,
  camera/depth reprojection On, native point sampler/weight, previous spatial history.
- 최종 Adaptive 8-case 결과가 아닌 독립 선택 정책 gate다.

이번 단계는 GPU 구현 전 저장된 실제 입력에 대한 offline gate다. 새 renderer나
GPU 성능 결과를 만들지 않는다. 이전 `756ff54`의 검증된 trace 입력 기록과 CPU
읽기/재구성 함수만 재사용한다. 의존성은 `dependencies.json`에 기록한다.
기준선 이후 renderer/HLSL 변경은 없어야 한다.

## 한 요소만 변경하는 가설

`E(t,x)`는 원본 1st-pass의 최종 RG가 0이 아닌 픽셀이다.
`q = (uv - velocity) * (width,height)`, `p = floor(q)`로 native point history와
같은 이전 texel을 구한다. 화면 밖 q는 거부한다.

`P(t,x) = E(t,x) OR E(t-1,p)`.

이전 **raw edge**만 한 프레임 사용한다. 이전 P를 누적하지 않고, dilation,
다른 sample pattern, weight, clipping, recursive feedback을 추가하지 않는다.
기존 선택 위치는 실제 기준선 최종 RGB를 유지하고, 새로 추가된 위치에만 같은
native 식의 CPU temporal 출력을 사용한다. 이전 spatial history는 최종 출력에
의존하지 않으므로 이 가설의 offline 계산에 recursive color simulation은 필요 없다.

## 입력과 검증

- 두 장면의 이전/현재 trace가 모두 있는 f128..138, f174..185, f190..195: 각 29프레임.
- 저장된 raw/current/previous/velocity DDS의 hash를 이전 검증 기록과 비교한다.
- previous가 직전 current spatial과 같은지 확인하고, 최종 PNG를 수정 기준선 hash와 비교한다.
- 현재 선택 픽셀 보존, 합집합/추가 mask 관계, 비선택 current 유지, 화면 밖 거부를 확인한다.
- CPU 재구성은 실제 baseline과 point 경계 밖 RGB 최대 1/255 오차를 허용한다.
- Point texel 경계 근처는 uncertainty로 기록하며 확정 pixel witness와 정량 gate에서 제외한다.
- 정지 시 previous/current edge와 velocity가 같으면 새 후보가 0이어야 한다.

## 평가와 한계

후보 비율과 추가 비율, 알려진 선 소실 위치의 복구 여부를 기록한다. 원본 색상의
연속 프레임과 전체 화면을 직접 열어 비교한다. 기존 supersample same-pose reference는
spatial proxy이며 RGB 오차의 증가/감소를 절대 ghosting 판정으로 사용하지 않는다.
CGVQM으로 프레임의 선 소실/단절을 덮지 않는다.

현재 trace에는 previous depth/surface ID가 없다. 따라서 disocclusion에서 올바른
history인지 확정할 수 없고, 새 후보의 모든 오차를 ghosting이라고 명명할 수도 없다.
추가된 candidate 수를 GPU 비용이나 속도 향상으로 환산하지 않는다.

GPU 이식 설계에서는 이전 edge 저장, 재투영/읽기, 기존 stencil 거부 경로에 mask를
전달하는 비용을 모두 명시한다. 공식 D3D 문서를 확인하며, full-screen history 읽기나
새 mask pass를 비용 없이 사용할 수 있다고 가정하지 않는다. 이 gate가 실패하면
동일 가설의 GPU 구현을 진행하지 않고 실패 근거를 보존한다.
