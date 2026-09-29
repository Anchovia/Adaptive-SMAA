# ⑤ 재구현: 공간 혼합 없이 첫 edge에서만 temporal 실행

과거 전체 화면 mask-read/branch ⑤의 완료 판정을 철회하고, native first-pass edge에서만
temporal pixel shader가 실행되는 구현으로 교체했다. ⑥과 별도로 `c51ca28`에서 직접 분기한
`experiment/first-edge-temporal-only-stencil`의 결과다. ①~④의 원본 경로를 변경하지 않았다.

## 구현과 검증

첫 edge pass의 최종 RG와 동일한 stencil을 기록한다. 기존 raw 준비 pass에서 raw history와
visible output을 MRT로 함께 저장하고, early stencil을 통과한 edge만 원본 T2X-R 계산을
실행한다. 비선택 영역은 이미 저장한 raw 색상을 유지한다. Spatial weight calculation과
neighborhood blending은 실행하지 않는다. Native shader와 `SMAA::go/reproject`는 원본이다.

Temporal shader에는 edge texture 읽기, 선택 분기, 비선택 current-only 출력이 없다.
화면 전체 triangle은 제출하지만 비선택 sample은 temporal shader 실행 전에 거부된다.
Raw history 준비와 camera velocity 생성까지 선택 픽셀로 제한했다는 뜻은 아니다.
③과 달리 ⑤에는 edge detection 비용이 필요하며, 이 비용과 stencil clear/MRT 저장 모두
전체 AA 시간에 포함한다. 기존 ⑤에 render/copy pass를 추가하지 않았다.

| 장면 | 기존 full/mask PSInvocations | 새 ⑤ 평균 PSInvocations | 화면 비율 |
|---|---:|---:|---:|
| bistro | 2,037,120 | 52,696.90 | 2.5868% |
| minecraft | 2,037,120 | 353,513.96 | 17.3536% |

두 장면 480 frame에서 coverage, stencil 통과 sample 수, native RG edge가 모두 일치했다.
선택 출력은 full-Off T2X-R과 같고, 비선택 출력은 실제 AA-Off/raw current와 같다.
①·②·④ control hash, 이전 지터 Off 선택 출력, 진단 Off repeat의 불일치는 모두 0이다.
60개 DDS probe의 input/prepared RGBA 및 velocity도 full과 selected 사이에 byte-identical하다.
⑤/⑥의 native RG edge 480 frame도 byte-identical하며 정지 두 구간의 고유 RGB frame은 1이다.
PSInvocations는 해당 RTX 3060 Ti에서의 측정값이며 물리 cache transaction 수로 해석하지 않는다.

## 같은 raw 입력과 pattern의 full-screen 대조

단위 ms. RTX 3060 Ti, D3D11, 1920×1061 Ultra, hidden, VSync Off, camera/depth R.
30초 사전 실행, 300 warmup, 4,800 frame×4회 교차 순서. 이미지/coverage/query readback Off.
두 경로 모두 raw 입력·edge detection·pattern Off를 사용한다. Full control은 불필요한 MRT
저장을 하지 않으므로 선택 실행에 필요한 추가 저장 비용까지 반영하는 비교다.
이 control은 edge detection이 없는 기준선 ③ 자체가 아니다.

| 장면 | full 전체 AA | 새 ⑤ 전체 AA | 변화 | full temporal | 새 temporal | 변화 |
|---|---:|---:|---:|---:|---:|---:|
| bistro | 0.112980 | 0.098990 | -12.383% | 0.033260 | 0.007131 | -78.559% |
| minecraft | 0.114805 | 0.114498 | -0.267% | 0.034999 | 0.023062 | -34.105% |

전체 AA 변화의 네 반복 범위:

- bistro: -12.505~-12.110%.
- minecraft: -0.445~-0.131%.

| 장면 | edge 검출 추가 비용 | raw/MRT 준비 추가 비용 | temporal 절감 |
|---|---:|---:|---:|
| bistro | +0.000890 | +0.011281 | -0.026129 |
| minecraft | +0.000814 | +0.010831 | -0.011936 |

Minecraft의 전체 AA 차이는 약 0.000306 ms로 매우 작다. Temporal 절감 대부분이 raw/MRT
준비와 정확한 stencil 생성 비용으로 상쇄돼 실질적으로 비슷한 수준으로 해석한다. WholeFrame은
평균 +0.036%이고 반복 방향도 섞여 있으므로 전체 렌더링 속도 향상을 주장하지 않는다.

## 원본 ④와 같은 실행의 비교

④는 공간 SMAA와 paired pattern On, ⑤는 공간 혼합 없음과 pattern Off다. 따라서 아래
전체 AA 차이는 구성 전체의 차이이며 temporal 선택만의 효과 또는 동등 품질 주장이 아니다.

| 장면 | ④ 전체 AA | ⑤ 전체 AA | 변화 | ④ temporal | ⑤ temporal | 변화 |
|---|---:|---:|---:|---:|---:|---:|
| bistro | 0.210149 | 0.098990 | -52.895% | 0.033221 | 0.007131 | -78.533% |
| minecraft | 0.283959 | 0.114498 | -59.678% | 0.034889 | 0.023062 | -33.898% |

## 해석과 자료

이번 변경은 기존 지터 Off 선택 출력의 실행 범위를 바로잡은 것으로 새 품질 향상을
주장하지 않는다. 이전 Off 결과와 이미지가 같으므로 기존 품질 평가에 연결할 수 있으나
이번 작업에서 CGVQM 모델을 재실행하지 않았다. Jitter On의 비선택 표본 떨림을 해결한
새 supersampling 기법이 아니다. Object-motion vector는 사용하지 않는다.

⑥의 stale spatial stencil에 따른 2차 pass 절감은 ⑤에 그 pass가 없어 발생하지 않는다.
①~④와 과거 진단 자료는 보존하며, 과거 fullscreen-mask 경로는 DIAG로만 남긴다.

- [설계 및 공식 근거](design.md): 원본 의존성과 구현 범위.
- `source-audit.json`: native 코드 보존, DXBC early-depth 선언, edge SRV/분기 부재.
- `*-capture.json`, `*-frames.json`: 출력과 GPU 실행 범위.
- `*-input-bridge.json`: alpha를 포함한 입력 및 ⑤/⑥ edge 동일성.
- `*-benchmark.json`: 반올림 전 값, 네 반복, 원시 CSV 경로와 SHA-256.
- `run-receipts.json`: 실행 시각, clean process 완료, 동일 executable 추적.
- Benchmark runner는 같은 executable의 출력/실행 및 입력 검증을 통과해야 실행된다.

⑤ 분석기의 첫 실행은 원래 ⑤ 캡처에 AA-Off/1X 파일이 없어서 중단됐다. 같은 timeline의
기존 ⑥ 캡처에 보존된 실제 AA-Off/1X/④ control로 경로를 바로잡아 검증했다. 누락 자료를
현재 출력으로 대체하지 않았으며, 이 분석 경로 수정은 shader/executable을 바꾸지 않았다.
