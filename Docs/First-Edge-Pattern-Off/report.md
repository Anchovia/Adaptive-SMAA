# 5번 첫 패스 edge 선택 temporal — 지터 Off 결과

공통 기준선 `c51ca28`에서 독립적으로 분리한 5번의 sample-pattern ablation이다. 원본 spatial/temporal 셰이더 계산, camera/depth reprojection과 각 프레임 입력을 저장하는 history 구조를 보존했다. 원본 TSCMAA 전체의 재현으로 해석하지 않는다.

## 구현과 검증

⑤는 원본 첫 단계 edge detection과 raw RGB/velocity-alpha 준비만 수행하며 공간 혼합 보정은 하지 않는다. Pattern Off는 projection jitter를 끈다. 원래 area-texture pass가 없는 경로이고, 현재 RGB는 AA-Off와 일치한다.

선택식은 기존 첫 패스의 `any(edge.rg > 0)`다. 후보 확장·새 판정식·새 렌더 패스는 추가하지 않았다. 선택 픽셀은 대응하는 Pattern Off 전체 temporal 출력과 같고, 비선택 픽셀은 현재 입력 그대로다. 두 장면 각각 240프레임의 모든 픽셀에서 이 규칙을 확인했다. 독립 재실행 hash와 기존 On/원본 control hash도 일치했다.

## 정지 안정성과 선택 비율

| 장면 | 전체 평균 선택 비율 | On 후반 정지 RGB 차이 | Off 후반 정지 RGB 차이 | Off 고유 프레임 수 |
|---|---:|---:|---:|---:|
| bistro | 2.5868% | 1.223442 | 0.000000 | 1 |
| minecraft | 17.3536% | 2.797890 | 0.000000 | 1 |

RGB 차이는 0~255 단위 인접 프레임 평균 절댓값이다. 정지 초반 20~59 및 후반 200~239 모두 Off 선택 출력의 프레임 차이와 mask 전환이 0이다. 이것은 고정 카메라의 2위상 교대 해소를 의미하며 이동 중 깜빡임·고스팅 해소까지 증명하지 않는다.

Minecraft 첫 오프라인 분석에서는 기존 O-1X PNG의 정지 RGB 판독이 일시적으로 불일치했다. 원본 파일 hash와 선택 출력 검사는 모두 일치했고, 같은 PNG의 세 차례 독립 재판독도 일치했다. 원인은 확정하지 않았다. 해당 분석은 제외하고 CGVQM 종료 후 같은 분석 코드와 엄격한 0 오차 기준으로 전체 240프레임을 다시 검사해 PASS했다. 렌더 코드나 원시 캡처를 바꾸거나 허용 오차를 넓히지 않았다. 실패와 재검증은 `validation-notes.json`에 보존했다.

## 품질

공식 CGVQM-2, 60 FPS, patch scale 4/mean, CUDA를 사용했다. 모든 FFV1 중간 영상은 RGB 무손실 round-trip을 검증했다. 기존 native control과 reference의 pixel hash 연결을 확인했다. 높은 점수가 좋다. reference는 같은 pose의 supersample spatial proxy이며 절대 temporal/고스팅 정답은 아니다.

⑥에서 확인된 시스템 commit 한도를 피하기 위해 동일한 제한 실행 방법을 재사용했다. 공식 구현이 원래 사용하는 30프레임 추론 경계에 맞춰 최대 60프레임씩 호출하고 동일 개수 patch의 점수를 평균했다. 원본 모델·전처리·공간 patch·평가 프레임은 변경하지 않았다. 각 장면의 기존 120프레임 native 점수와 0.00002 이내 일치를 먼저 검증했다. 실패 실행은 점수에 포함하지 않았다.

| 장면·구간 | 원본 SMAA T2X-R | Off full | Off selective | selective − 원본 |
|---|---:|---:|---:|---:|
| bistro moving | 96.191238 | 96.220001 | 96.033230 | -0.158009 |
| bistro transition | 96.719254 | 95.711517 | 95.647652 | -1.071602 |
| minecraft moving | 93.911362 | 95.328606 | 95.406033 | +1.494671 |
| minecraft transition | 94.905739 | 94.918213 | 94.968971 | +0.063232 |

moving=60~179, transition=160~219. ⑤와 원본 SMAA T2X-R의 차이는 공간 혼합 유무·표본 패턴·선택 처리 차이를 모두 포함한다. 순수 selection 효과는 동일한 Off raw full과 Off raw selective 사이에서 판단한다. SMAA T2X의 subpixel 표본 누적 이점은 Off에서 보존되지 않는다.

## GPU 성능

RTX 3060 Ti, DX11 Release, 1920×1061, Ultra, hidden window. 각 장면은 별도 clean process이며 30초 사전 실행, mode별 300 warmup, 4,800프레임×4회 정·역 교차 순서로 측정했다. 캡처·readback·CGVQM 작업과 동시에 실행하지 않았다. 아래는 run mean의 평균이며 전체 프레임 시간과 temporal resolve는 구분한다.

| 장면 | On full AA ms | Off full AA ms | Off selective AA ms | Off selective vs On full | Off selective vs Off full |
|---|---:|---:|---:|---:|---:|
| bistro | 0.109972 | 0.109992 | 0.103695 | -5.708% | -5.725% |
| minecraft | 0.113861 | 0.113910 | 0.116396 | +2.226% | +2.182% |

⑤의 성능 표에서 full은 동일한 edge detection 비용을 포함하는 temporal-only 대조군이다. 원본 spatial SMAA T2X-R의 전체 시간으로 부르면 안 된다.

| 장면 | On full resolve ms | Off full resolve ms | Off selective resolve ms | Off selection 증감 | 짝 비교 4회 범위 |
|---|---:|---:|---:|---:|---:|
| bistro | 0.033999 | 0.033990 | 0.027804 | -18.199% | -18.389~-18.050% |
| minecraft | 0.035678 | 0.035656 | 0.038178 | +7.073% | +6.810~+7.360% |

WholeFrame, wall mean FPS·1% low, 각 scope의 median/std/p95/p99와 4회 mean은 `*-benchmark.json`에 보존했다. 작은 차이는 이 장면·해상도·GPU 조건의 결과이며 일반화하지 않는다.

## 결과 사용 범위

정지 교대 문제의 원인 분리는 통과했다. 이동 품질 점수와 처리 비용은 위 표의 별도 결과로 사용한다. 이 실험만으로 후보 확장이나 다른 sampling/clipping을 채택하지 않는다. object-motion vector, 변형 물체 및 disocclusion 검증을 수행한 결과가 아니다. 기존 최종 8-case 의미와 기본 pattern On은 변경하지 않았다.

## 재현 자료

- `source-shader-audit.json`: native source 보존, 선택 셰이더 DXBC, source·executable hash.
- `*-capture.json`, `*-frames.csv`: 원본 hash bridge, 선택/비선택 규칙, static 결과, raw 경로.
- `validation-notes.json`: 제외한 오프라인 분석과 동일 기준 전체 재검증 기록.
- `*-cgvqm.json`: 공식 모델·환경·RGB round-trip·reference hash 및 점수.
- `*-smoke.json`, `*-benchmark.json`: 실행 receipt와 짝 비교 통계.
- `visual-provenance.json`: 정지 GIF/PNG 및 이동 60 FPS MP4 경로. 시각 자료는 정지 On artifact가 큰 ROI를 선택한 보조 자료다.

명령: `Tools/SMAA/run_edge_pattern.ps1 -Phase Capture|Smoke|Benchmark -Scene bistro|minecraft`. 분석은 `analyze_edge_pattern.py`, `evaluate_edge_pattern_cgvqm.py`, `visualize_edge_pattern.py`, 이 요약 생성기로 수행한다. D 드라이브 raw 결과는 Git에 넣지 않고 경로·hash를 기록했다.
