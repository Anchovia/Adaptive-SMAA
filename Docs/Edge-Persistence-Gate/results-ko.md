# 직전 edge 한 프레임 유지: 검증 결과

2026-10-01. Branch `validation/spatial-edge-persistence-gate`, direct base `304f749`.

**사라진 선 일부를 다시 이어주는 효과는 있지만, 이것만으로 품질 문제가 해결되지는
않는다.** 현재 edge와 재투영한 직전 raw edge를 합친 가설을 실제 저장 입력으로
계산했다. 새로운 GPU AA 구현·성능 결과가 아니라, 적용 전에 수행한 offline gate다.

## 무엇을 변경해 비교했는가

⑥ Original spatial SMAA + exact first-edge selective native T2X-R, paired pattern Off,
camera/depth reprojection On을 기준으로 선택식만 비교했다.

- 기준: 현재 최종 1st-pass RG edge가 있는 위치.
- 가설: 현재 edge **또는** native point 재투영 위치의 직전 raw edge가 있는 위치.
- 한 프레임만 유지하며, 선택 mask 자체를 누적하지 않는다.
- 현재 선택 위치는 실제 GPU baseline RGB를 유지한다. 추가 위치에만 동일 native
  sampler/weight의 CPU 결합 결과를 넣는다. 비선택은 current spatial 그대로다.
- Spatial/jitter/weight/clipping/feedback을 바꾸지 않고 dilation도 하지 않았다.

이전 trace `756ff54`의 입력과 읽기 함수를 제한적으로 재사용했다. 새 브랜치의
renderer/HLSL diff는 0이다. 이 브랜치에서 CMAA2를 실행하거나 재측정하지 않았다.
독립 장치 capability probe만 별도로 실행했다.

## 검증과 범위

Bistro/Minecraft 각각 29프레임(f128..138, f174..185, f190..195), 총 58프레임을
분석했다. 전체 타임라인 평균으로 일반화하지 않는다. 입력 DDS의 hash와 이전
current→history 연결을 확인하고, 각 프레임의 ④/⑥ RGB를 수정 기준선 hash와
비교했다. CPU baseline 재구성의 확정 point 위치 오차는 최대 RGB 1/255 이내다.
현재 후보 보존, 비선택 current 유지, 화면 밖 이전 edge 거부와 정지 mask 일치를
모두 통과했다. Point 경계 근처는 별도 uncertainty로 기록했다.

## 프레임에서 확인한 효과와 남은 결함

Minecraft ROI `(964,524)..(996,588)`의 f130..135를 원본 색상으로 나란히 확인했다.
f131/f134에서 끊기던 수직 경계가 직전 edge 유지 가설에서는 이어진다.
이미 현재 edge였던 f132/f135의 선 약화는 바뀌지 않는다.

| 프레임·좌표 | 추가 선택 | 기존 ⑥ RGB | CPU 가설 RGB | Same-pose spatial reference RGB |
|---|---|---|---|---|
| f131 (971,544) | 예 | 163,162,150 | 142,139,131 | 133,131,123 |
| f134 (972,544) | 예 | 163,163,150 | 141,139,130 | 139,138,129 |
| f132 (972,544) | 아니오, 기존 후보 | 140,138,128 | 140,138,128 | 122,119,111 |
| f135 (973,544) | 아니오, 기존 후보 | 138,137,127 | 138,137,127 | 115,111,105 |

이 네 위치는 point 경계의 불확실 범위 밖이다. Reference는 temporal 정답이 아니라
공간 reference proxy이며, 대표 픽셀의 개선을 전체 장면 개선으로 확대하지 않는다.

연속 프레임에서 원본 ④ T2X-R과 비교하면 가설 출력에도 선 농도의 변화가 남는다.
Bistro 의자·창문 영역에서도 일부 차이는 있지만 전반적인 깜빡임 해결을 입증하지
못했다. f181 이후 추가 후보가 없어지고, f190..195의 가설 출력은 기존 ⑥과 정확히
같다. 따라서 정지 화면에 남아 있던 계단과 단절을 이 가설로 고칠 수 없다.

## 후보량과 보조 reference 진단

아래는 f128..138 및 f174..179, **17개 이동 프레임 평균**이다.

| 장면 | 기존 후보/전체 화면 | 직전 edge 합집합/전체 화면 | 기존 후보 대비 증가 |
|---|---:|---:|---:|
| Bistro | 2.648% | 3.447% | +30.17% |
| Minecraft | 24.302% | 30.487% | +25.45% |

이 증가는 temporal 대상의 수이며 GPU 시간 증가율이 아니다. 이전 edge를 찾고
선택 결과를 전달하는 비용은 이 수치에 들어 있지 않다.

Point 경계 밖의 추가 위치에서 reference RGB 평균 절대오차가 1보다 더 감소/증가한
pixel-frame 수는 다음과 같다. 동일 픽셀이 여러 프레임에 있으면 각각 집계한다.

| 장면 | 오차 감소 | 오차 증가 | 확정 추가 위치만 반영한 전체 화면당 오차 변화 |
|---|---:|---:|---:|
| Bistro | 63,899 | 61,581 | -0.006665 RGB level |
| Minecraft | 215,498 | 890,924 | +0.042386 RGB level |

이 값만으로 육안 품질 우열을 판정하지 않았다. 대표 선은 개선됐지만, Minecraft의
벽/잔디 texture에도 많은 위치가 추가되어 오차 증가가 발생한다. 오차 증가가 큰
영역을 따로 열어 확인했으며, 이것을 모두 ghosting으로 명명할 근거는 없다.
특히 current/previous depth나 surface ID가 없어 가려짐 해제의 history 유효성을
판정할 수 없다. **고스팅 해결은 미검증**이다. CGVQM은 새로 실행하지 않았다.

## 직접 확인한 이미지

- Minecraft 선: f130..135, 이동→정지 f178..183, 정지 f190..195.
- Bistro 의자: f130..135. 창문: f178..183, f190..195.
- 추가 오차가 큰 screen-fixed ROI: Bistro `(1040,344)..(1088,392)`,
  Minecraft `(1864,184)..(1912,232)`의 f130..135.
- 전체 화면: Minecraft f131, Bistro f180의 기존 GPU 출력과 CPU 가설 출력을 직접 확인.

원본 PNG/CPU 가설/원본 ④/고해상도 참조/추가 mask를 나란히 표시했다. 확대는
nearest이며 원본 색상을 바꾸지 않았다. 각 파일과 ROI·배율·frame index는 `media.json`에
있다. Lossless WebP 6fps(0.1배속)는 decode 검증을 통과했으며 정지 프레임 검사와
구분해 재생 자료로 제공한다. 동영상 실시간 재생을 직접 관찰했다고 주장하지 않는다.

## GPU 적용 판단

필요한 자원과 실행 구조는 `integration-cost-ko.md`에 정리했다.

- 이전 RG8 edge를 ping-pong하면 전체 복사 pass를 피하는 설계는 가능하지만,
  추가 edge texture와 이전 위치 계산·읽기가 필요하다.
- 현재 stencil 밖 픽셀은 temporal shader가 실행되기 전에 제외된다. 따라서
  temporal 내부 코드만 바꿔 직전 edge를 추가할 수는 없다.
- 현재 RTX 3060 Ti/D3D11 장치에서 `PSSpecifiedStencilRefSupported=false`를 확인했다.
  shader compile은 성공했지만 pixel shader 생성은 실패했으므로 3rd-pass의
  `SV_StencilRef` 출력으로 해결하는 경로는 사용할 수 없다.
- 전용 depth를 이용해 기존 3rd-pass에서 mask를 전달하는 대안은 별도 정확성/성능
  검증이 필요하다. 지원되지 않는 stencil 기능을 가정하거나, 별도 mask pass 또는
  full-screen history 읽기를 몰래 추가하지 않는다.

판정은 **현재 edge의 시간적 누락을 일부 보완할 수 있다는 가설은 지지되지만,
무조건적인 한 프레임 합집합을 최종 해법으로 채택하기에는 근거가 부족함**이다.
GPU 속도 개선/저하 수치는 아직 없다. 기존 ⑥이나 ④를 교체하지 않았다.

다음에는 복구된 얇은 선과 잘못 가져올 가능성이 있는 history를 구분할 수 있는지
검증해야 한다. 현재/이전 표본이 아예 없는 정지 결함은 별도 한계로 유지한다.
그 조건이 정해지면, 기존 spatial 출력과 temporal의 선택 실행을 보존하는 전달
구조를 GPU에서 검증하고 대응하는 ④·⑥과 paired timing을 측정한다. 이번의
부분 복구 효과를 곧바로 고스팅 해결이나 빠른 구현 성공으로 표현하지 않는다.

## 재현 자료

- `dependencies.json`, `input/`: 재사용 commit/path/hash와 기존 trace 검증 기록.
- `bistro-results.json`, `minecraft-results.json`: 58프레임의 mask·RGB 검증, 후보/오차.
- `witnesses.json`: 대표 선의 입력/출력과 선택 여부.
- `stencil-ref-probe.txt`: 별도 장치의 기능 지원/compile/create 결과.
- `Projects/CMAA2/Captures/edge-persistence-gate-20261001/`: 원본 색상 비교와 NPZ, Git 제외.
- `analyze_edge_persistence_gate.py --scene bistro|minecraft` 후
  `create_edge_persistence_media.py`로 분석/이미지를 재생성한다.
