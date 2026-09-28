# ⑤ 첫 패스 edge 선택 temporal-only 검증

## 범위와 현재 판단

`experiment/first-edge-temporal-only`에서 합의한 ⑤만 분리했다. 원본 SMAA 첫 패스의 RG edge를
직접 읽고 그 픽셀에서만 원본 T2X-R 수식을 실행한다. 공간 blending-weight/neighborhood
보정은 실행하지 않는다. 원본 세 공간 패스를 포함하는 ⑥의 결과가 아니다.

선택 출력의 정확성은 통과했지만 정지 품질은 통과하지 못했다. 양쪽 장면 모두 전체 화면
temporal은 정지에서 같은 출력을 유지했고, edge 선택은 두 지터 위상을 반복했다. 이 결과를
일반 No-AA/1X의 떨림이나 원본 SMAA의 회귀로 해석하지 않는다.

## 코드와 비교군

- 공통 기준 `e14f122`에서 직접 분기했다. ③의 입력 준비·대조군을 재사용하는 의존성
  `7c2feeb`만 cherry-pick하여 `043056c`로 가져왔다. ⑤ 구현은 `a774772`다.
- `SMAA::detectFirstEdges`는 기존 edge shader·Ultra preset·입력·RG8 target을 그대로 쓴다.
  `SMAA.hlsl`과 기존 `go`/`reproject`/`edgesDetectionPass` 본문은 변경하지 않았다.
- `FirstEdgeTemporalOnlyPS`는 current와 RG edge를 읽는다. RG가 모두 0이면 current를
  반환한다. 그 외에는 기존 velocity 재투영·point history sampling·alpha 기반 가중치
  `0..0.5`·혼합을 실행한다. 새로운 luma 선택식·확장·clipping·compact 패스는 없다.
- 준비 단계는 장면 RGB를 바꾸지 않고 원본 velocity 크기를 alpha에 기록한다. History는
  각 프레임의 준비 입력이며 최종 resolve feedback으로 변경하지 않았다. 전역 paired jitter를
  유지하므로 비선택 출력은 지터가 있는 raw current다.
- R은 camera/depth reprojection이다. Object-motion velocity 검증은 이 항목에 포함하지 않는다.

| 비교군 | 공간 보정 | 실제 첫 edge 검출 | Temporal |
|---|---|---|---|
| ③ `ABL-TemporalOnly-R` | 없음 | 없음 | 원본 전체 화면 결합 |
| `DIAG-TemporalOnly-EdgeDetect-R` | 없음 | 있음 | 원본 전체 화면 결합, edge 미참조 |
| ⑤ `ABL-FirstEdge-TemporalOnly-R` | 없음 | 있음 | RG edge가 있는 픽셀만 결합 |
| ④ `O-T2X-R` | 원본 세 공간 패스 | 있음 | 원본 전체 화면 결합; 이번에는 캡처 대조군 |

## 구현 검증

Release x64 빌드가 통과했다. FXC `ps_4_1`의 reprojection Off/On 두 변형에서 정수 edge Load
1회와 비선택 조기 반환을 확인했다. History와 velocity sample은 조기 반환 뒤에 존재한다.
실제 캡처와 측정은 R-On이며 R-Off는 컴파일 검사 범위다. DXBC 검사만으로 실제 GPU의
메모리 transaction이나 warp 효율을 검증했다고 주장하지 않는다.

Bistro/Minecraft 각각 1920×1061, Ultra, fixed 60 Hz, 240프레임(정지60/이동120/정지60)을
같은 경로·reset·warm-up으로 캡처했다.

| 검사 | 장면당 범위 | 결과 |
|---|---:|---|
| ③ 출력과 이전 독립 ③ 캡처 | 240프레임 | RGB 불일치 0 |
| ④ 출력과 독립 원본 기준선 | 240프레임 | RGB 불일치 0 |
| 검출만 추가한 대조군과 ③ | 240프레임 | RGB 불일치 0 |
| ⑤와 동일 실행의 reset 후 반복 | 240프레임 | RGB 불일치 0 |
| 선택 RGB=③, 비선택 RGB=current | 488,908,800 픽셀 | 불일치 0 |
| ⑤ edge RG와 원본 full SMAA/검출 대조군/반복 | 10 대응 프레임 | 불일치 0 |
| raw input/준비 RGBA/velocity의 raw 계열 모드 간 비교 | 10 대응 프레임 | 불일치 0 |
| input RGB=준비 RGB=current PNG 및 첫 프레임 seed | 저장된 probe | 불일치 0 |

③과 ④는 공간 처리 유무가 다르므로 서로 같은 RGB를 기대하지 않는다. 선택 픽셀의
수식 대조는 같은 raw 입력을 사용하는 ③과 수행했다. GPU 디버거 draw capture 검증이나
모든 해상도·장면의 일반적 정확성 보장은 아니다.

## 실제 선택량

아래 비율의 분모는 화면 전체 2,037,120픽셀이다. Intel non-dominant 제거 후 후보 비율이나
검출 edge의 50%가 아니다. 이 실험은 검출된 RG edge를 추가 제거 없이 모두 사용한다.

| 장면 | 전체 240프레임 평균 선택 수 | 전체 평균 비율 | 이동 구간 평균 비율 |
|---|---:|---:|---:|
| Bistro | 52,833.81 | 2.594% | 2.568% |
| Minecraft | 353,814.63 | 17.368% | 20.703% |

## 정지 떨림의 위치

초기 정지 20~59와 후기 정지 200~239에서 ③/④는 RGB 고유 프레임이 1개였고, ⑤는 2개였다.
⑤의 두 프레임 간격 비교는 각 구간 38/38쌍이 정확히 일치했다. 시간에 따라 누적되는
불안정성 대신 두 지터 위상의 교대가 관측된 것이다.

후기 정지의 RGB 평균 절댓값 변화는 0~255 단위이며, 아래 두 기여의 합이 전체 변화다.

| 장면 | ③/④ 연속 프레임 변화 | ⑤ 변화 | 양쪽 비선택 픽셀 기여 | 선택 상태 변경 픽셀 기여 |
|---|---:|---:|---:|---:|
| Bistro | 0 / 0 | 1.223442 | 1.001136 | 0.222306 |
| Minecraft | 0 / 0 | 2.797890 | 1.640866 | 1.157024 |

두 프레임 모두 선택된 픽셀의 변화 기여는 두 장면 모두 0이다. 선택 상태가 바뀐 픽셀은
Bistro 57,616개, Minecraft 419,604개였다. 공간 edge 검출이 없다고 해서 해당 raw 픽셀이
지터 변화에도 안정적이라는 뜻은 아님을 이번 캡처에서 직접 확인했다.

이는 정지 안정성 진단이다. CGVQM, 이동 중 절대 고스팅·선명도 우열 또는 supersample
reference 품질은 아직 측정하지 않았다. 이 문제가 있는 상태를 완성된 품질 개선안으로
채택하지 않는다. 지터 제거나 후보 확장을 이 브랜치에 추가하지 않았다.

## 성능

RTX 3060 Ti / DX11 / 1920×1061 / Ultra / 숨김 창. 각 명령을 독립 프로세스로 실행했고
장면별 smoke 후 30초 precondition, 조건별 300프레임 warm-up, 4,800프레임×4회로 측정했다.
세 조건의 순서는 정방향/역방향으로 교차했다. PNG·DDS·RG8 저장과 이미지·마스크 readback은
껐다. 계측용 GPU timestamp query의 결과 읽기는 유지했다.
240프레임 카메라 경로를 20회 반복하므로 경로 끝에서 시작으로 되돌아가는 경계도 포함된다.
각 조건에 같은 경로를 사용했지만 하나의 연속 4,800프레임 이동 품질 시퀀스는 아니다.

전체 AA scope는 camera velocity + 선택적 edge 검출 + RGB/alpha 준비 + resolve와 주변 GPU
명령을 포함한다. 전체 렌더 프레임 시간이나 FPS가 아니다. 세부 timer 삽입의 영향이 있으므로
이전 브랜치에서 측정한 절대값과 직접 빼지 않는다. ④는 이번 실행의 timing matrix에 없으며,
이 표를 원본 공간 SMAA T2X-R보다 ⑤가 빠르다는 증거로 사용하지 않는다.

단위는 ms, 네 반복 평균이다.

| 장면 | 구성 | Camera velocity | Edge 검출 | 입력 준비 | Resolve | 전체 AA scope |
|---|---|---:|---:|---:|---:|---:|
| Bistro | ③ 전체 화면 temporal | 0.023748 | — | 0.021796 | 0.033476 | 0.079037 |
| Bistro | 검출 + 전체 화면 temporal | 0.023788 | 0.029845 | 0.022236 | 0.033299 | 0.109201 |
| Bistro | ⑤ 검출 + edge temporal | 0.023808 | 0.029864 | 0.022239 | 0.027551 | 0.103488 |
| Minecraft | ③ 전체 화면 temporal | 0.023685 | — | 0.023489 | 0.035173 | 0.082372 |
| Minecraft | 검출 + 전체 화면 temporal | 0.023764 | 0.030447 | 0.023973 | 0.035038 | 0.113243 |
| Minecraft | ⑤ 검출 + edge temporal | 0.023772 | 0.030432 | 0.023971 | 0.037904 | 0.116109 |

검출 비용과 선택 resolve의 효과를 구분하여 다음 차분으로 해석한다.

| 장면 | 검출 추가: 전체 scope 증가 | 같은 검출 조건에서 선택 resolve 변화 | 같은 검출 조건에서 전체 scope 변화 | ③ 대비 ⑤ 전체 scope 변화 |
|---|---:|---:|---:|---:|
| Bistro | +0.030164 (+38.16%) | -0.005748 (-17.26%) | -0.005714 (-5.23%) | +0.024450 (+30.94%) |
| Minecraft | +0.030871 (+37.48%) | +0.002866 (+8.18%) | +0.002866 (+2.53%) | +0.033737 (+40.96%) |

4회 반복의 같은 검출 조건 resolve 변화율 범위:

- Bistro: -17.49% ~ -16.96%.
- Minecraft: +7.83% ~ +8.56%.

Bistro에서는 선택 resolve가 절약한 시간보다 새로 필요한 edge 검출 비용이 컸다.
Minecraft에서는 같은 검출 조건에서도 선택 resolve 비용이 증가했다. 후보 수 감소만으로
속도 향상을 보장할 수 없으며, 이 결과를 단순히 데이터 전송 또는 분기 divergence 한 가지
원인으로 확정하지 않는다. Nsight의 실제 GPU ISA/warp/메모리 트래픽은 이번에 측정하지 않았다.

반복 산포와 꼬리 지연도 보존했다. 아래 p95/p99는 네 run의 각 percentile을 평균한 값이며
모든 sample을 합친 pooled percentile이 아니다. 모든 수치는 ms다.

| 장면 | 구성 | 전체 평균 ± run-mean 표준편차 | 전체 run p95 평균 | 전체 run p99 평균 | Resolve 평균 ± run-mean 표준편차 |
|---|---|---:|---:|---:|---:|
| Bistro | ③ 전체 화면 temporal | 0.079037 ± 0.000333 | 0.086016 | 0.087296 | 0.033476 ± 0.000137 |
| Bistro | 검출 + 전체 화면 temporal | 0.109201 ± 0.000370 | 0.115968 | 0.116992 | 0.033299 ± 0.000091 |
| Bistro | ⑤ 검출 + edge temporal | 0.103488 ± 0.000150 | 0.108032 | 0.108544 | 0.027551 ± 0.000036 |
| Minecraft | ③ 전체 화면 temporal | 0.082372 ± 0.000082 | 0.093184 | 0.094464 | 0.035173 ± 0.000046 |
| Minecraft | 검출 + 전체 화면 temporal | 0.113243 ± 0.000044 | 0.123904 | 0.124928 | 0.035038 ± 0.000013 |
| Minecraft | ⑤ 검출 + edge temporal | 0.116109 ± 0.000145 | 0.131072 | 0.132096 | 0.037904 ± 0.000115 |

`*-benchmark-timings.csv`는 각 run의 mean/median/p95/p99/sample 표준편차를,
`*-benchmark-performance.json`은 반복별 차분과 평균을 담는다. 두 smoke 및 두 benchmark는
모든 metric의 sample 수와 정/역 mode 순서, EXE/report hash, Aggregate PASS를 확인했다.
숨김 창의 비용 분리용 engineering 결과다. WholeFrame/FPS/1% low와 visible 조건의 최종
6구성 비교, matched-quality 성능 우위는 별도 단계로 남아 있다.

## 재현과 자료

- [구현/실험 방법](method.md), [소스·DXBC 감사](source-shader-audit.json)
- [Bistro 전체 검증](bistro-capture.json), [Minecraft 전체 검증](minecraft-capture.json)
- 프레임별 선택량·변화·기여: `bistro-frames.csv`, `minecraft-frames.csv`
- 로컬 시각 자료: `tmp/first-edge-only-visuals/{scene}-static-phases.gif` 및 두 원본 RGB PNG 패널.
  프레임220/221의 변화가 가장 큰 320×320 ROI를 고정 64픽셀 격자에서 선정했다.
  GIF는 공통 256색 palette와 4 FPS로 느리게 표시한 진단이며 정상 재생속도 영상이 아니다.
  좌표·선정식·hash는 [visual-provenance.json](visual-provenance.json)에 기록했다.
- 실행: `Tools/SMAA/run_first_edge_only.ps1 -Phase Capture|Smoke|Benchmark -Scene bistro|minecraft`.
  각 명령은 별도 clean process이며 모든 실행 전후 CMAA2 잔류 프로세스가 0개여야 한다.
- 분석: `analyze_first_edge_only.py`, `analyze_first_edge_only_performance.py`,
  `visualize_first_edge_only.py`, `summarize_first_edge_only.py`.
  원시 PNG/DDS/RG8/AutoBench/EXE는 Git에서 제외한다.

다음 독립 연구 항목은 ⑥이다. 같은 검증된 공통 기준에서 원본 공간 SMAA 세 패스를 유지하고,
이미 생성된 첫 edge를 temporal에서 사용하는 구조를 별도 브랜치로 구현·검증한다.
⑤의 선택량·정지 품질·전체 비용을 ⑥의 결과로 대신 사용하지 않는다.
