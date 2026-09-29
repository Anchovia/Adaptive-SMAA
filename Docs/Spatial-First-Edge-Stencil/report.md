# ⑥ 재구현: 첫 edge의 stencil로 temporal 실행 제한

기존 전체 화면 mask-read/branch ⑥의 채택을 철회하고, 검출 edge 위치에서만 temporal
pixel shader가 실행되는 경로를 구현했다. 원본 공간 SMAA의 RGB 결과, 원본 T2X-R 수식,
camera/depth reprojection과 spatial-frame history를 보존했다. 주 실험은 jitter/area
pattern Off이며, 원본 T2X-R 기준선의 paired pattern On은 변경하지 않았다.

## 구현과 실행 검증

첫 edge pass가 최종 RG와 같은 위치에 stencil=1을 남긴다. 3차 공간 패스에서 current
history와 visible output을 MRT로 함께 저장하고, temporal에서 early stencil test를
통과한 위치만 원본 resolve를 실행한다. Temporal shader에는 edge texture 읽기,
선택 분기, 비선택 current-only 출력이 없다. 추가 render pass나 copy pass는 없다.
매 frame stencil clear와 MRT store 비용은 전체 AA 측정에 포함한다.

| 장면 | 기존 full/mask PSInvocations | 새 경로 평균 PSInvocations | 화면 비율 |
|---|---:|---:|---:|
| Bistro | 2,037,120 | 52,696.90 | 2.5868% |
| Minecraft | 2,037,120 | 353,513.96 | 17.3536% |

두 장면 480 frame 모두 coverage MRT, stencil 통과 sample 수와 최종 RG edge가 일치했다.
원본 ①·②·④ control hash, ⑥의 current RGB와 실제 1X, 선택/비선택 출력, 과거 지터 Off
선택 출력, 진단 Off repeat의 불일치는 모두 0이다. RGBA history/velocity 등 60개 DDS
probe도 full과 selected 사이에 byte-identical했다. 정지 두 구간의 고유 RGB frame은 1이다.

이후 공간 stencil 효과 분리 capture 480 frame도 이전 full/selected 출력과 일치했다.
측정은 RTX 3060 Ti의 D3D11 PSInvocations이며 GPU cache transaction 수와 동일시하지
않는다. Fullscreen triangle은 제출하지만 비선택 sample은 shader 실행 전에 거부된다.

## 원본 T2X-R과 같은 실행에서 비교

단위 ms. 1920×1061 Ultra, hidden, VSync Off, camera/depth reprojection, expansion Off.
30초 사전 실행, 300 warmup, 4,800 frame×4회 교차 순서. 이미지/coverage/query readback Off.

| 장면 | 원본 전체 AA | 새 ⑥ 전체 AA | 변화 | 원본 temporal | 새 temporal | 변화 |
|---|---:|---:|---:|---:|---:|---:|
| Bistro | 0.208051 | 0.133725 | -35.725% | 0.033636 | 0.007269 | -78.390% |
| Minecraft | 0.283972 | 0.218529 | -23.046% | 0.035395 | 0.023274 | -34.246% |

**위 전체 AA 감소율 전체를 temporal 선택만의 효과라고 설명하지 않는다.** Native
wrapper는 stencil을 frame마다 clear하지 않아 과거 edge의 superset에서 2차 공간 shader를
실행할 수 있다. 새 경로의 정확한 stencil은 이 공간 비용도 줄였다. Pattern 변경도 포함한다.
①~④의 화면 출력 검증을 철회하지 않으며 원본 경로는 보존했다.

## 공간 stencil과 pattern을 맞춘 대조

`DIAG-Spatial-ExactStencil-FullTemporal-PatternOff-R`도 새 경로처럼 매 frame stencil을
clear하고 최종 edge만 공간 2차 pass에 사용한다. 이 full-screen control에는 불필요한
MRT를 넣지 않는다. 선택 경로의 추가 출력 저장 비용까지 포함한 비교다.

| 장면 | 대조군 전체 AA | 선택 전체 AA | 변화 | 대조군 temporal | 선택 temporal | 변화 |
|---|---:|---:|---:|---:|---:|---:|
| Bistro | 0.158893 | 0.134902 | -15.099% | 0.033470 | 0.007221 | -78.427% |
| Minecraft | 0.227456 | 0.218968 | -3.732% | 0.035016 | 0.023259 | -33.576% |

전체 AA의 네 반복 변화는 Bistro -14.80~-15.32%, Minecraft -3.46~-4.12%로 모두 감소했다.
MRT로 spatial scope는 각각 0.002273/0.003279 ms 증가했지만 temporal 감소가 이를 넘었다.
서로 다른 두 실행 묶음의 절대 시간을 빼서 효과를 역산하지 않는다.

## 해석과 보존 자료

선택식과 화면 출력은 기존 지터 Off mask 구현과 같고 **실행 범위와 비용을 수정한 결과**다.
새 품질 향상을 주장하지 않는다. 기존 CGVQM 평가로의 연결은 이미지 동일성에 근거하며
이 작업에서 모델을 재실행하지 않았다. Jitter On에서 비선택 영역이 흔들리는 문제를
해결한 별도의 temporal supersampling 방법이라고 주장하지 않는다.

- Base `c51ca28`; 필요한 의존성 `8e5a972`, `28f08fa`만 명시적으로 가져왔다.
- 실행 구현 `037fd8b`, 두 장면 검증 `474fc10`, 공간 효과 분리 control `cef8490`.
- Normal 실행은 `normal-source-audit.json`의 executable hash `04d4c2cb...`;
  isolation은 `source-audit.json`의 `66d5d0e5...`와 대응한다.
- `*-capture.json`, `*-frames.json`: 실행 위치와 출력 검증.
- `*-benchmark.json`, `*-isolation-benchmark.json`: 반올림 전 값, 각 run과 원시 CSV hash.
- `rgba-probes.json`: alpha를 포함한 입력 동일성.
- 초기 stencil clear 누락 실행은 [failed-runs.md](failed-runs.md)에 실패로 보존했다.
- Benchmark runner는 이제 같은 executable의 실행 범위/출력 capture gate가 없거나
  불일치가 남으면 측정을 거부한다.
- ⑤는 별도 baseline-derived 브랜치에서 구현한다. 이 보고서는 ⑥만의 결과다.

구현 근거와 재현 조건은 [design.md](design.md)를 따른다.
