# 직전 raw edge 유지: GPU 구현·성능·품질 결과

브랜치: `experiment/spatial-edge-persistence-depth`. 수정된 ⑥ 기준선 `304f749`에서 직접 분기했다.
GPU 구현 커밋: `2d4d0ccba06f6f9882c16abffd7489bed52030d7`. 실행 파일 SHA-256: `4ce7ee5efe13dabc6fba47a4649b5539d64d18a2d8d5ad62e5355c9855c91539`.

현재 edge와 재투영한 직전 **raw edge**의 합집합에 원본 temporal 계산을 수행했다. 이전 합집합을 재귀적으로 유지하지 않는다. 추가 draw/dispatch나 전체 색상 복사 패스는 없다. 기존 공간 3차 패스에서 선택 영역을 전용 depth에 기록하고, temporal 패스는 early depth test로 선택 영역에서만 실행한다. 두 selective 구현은 Pattern Off, 원본 ④는 paired pattern On이다.

## 성능

RTX 3060 Ti, DX11 Release x64, SMAA Ultra, 1920×1061, hidden, VSync Off. 장면별 동일 실행의 세 모드를 순서 교차하여 300 warm-up + 4,800프레임 × 6회 측정했다. PNG·GPU readback·진단 query를 모두 끈 별도 clean process 결과다. 음수는 시간 감소, 양수는 시간 증가다.

| 장면 | 방식 | 전체 AA ms | 원본 ④ 대비 | spatial+선택 ms | camera ms | temporal ms | temporal 원본 ④ 대비 |
|---|---|---:|---:|---:|---:|---:|---:|
| bistro | 기존 ⑥: 현재 edge | 0.137204 | -15.11% | 0.105238 | 0.024486 | 0.007459 | -78.19% |
| bistro | 새 구현: 직전 raw edge 유지 | 0.170156 | +5.28% | 0.135144 | 0.024508 | 0.010485 | -69.35% |
| bistro | 원본 ④: SMAA T2X-R | 0.161624 | +0.00% | 0.102883 | 0.024515 | 0.034207 | +0.00% |
| minecraft | 기존 ⑥: 현재 edge | 0.223896 | -4.05% | 0.175565 | 0.024443 | 0.023864 | -33.20% |
| minecraft | 새 구현: 직전 raw edge 유지 | 0.252553 | +8.23% | 0.199040 | 0.024494 | 0.028997 | -18.83% |
| minecraft | 원본 ④: SMAA T2X-R | 0.233352 | +0.00% | 0.173127 | 0.024483 | 0.035724 | +0.00% |

### 새 구현과 기존 ⑥의 차이

| 장면 | 전체 AA 증가 | spatial+선택 증가 | temporal 증가 | spatial 구간 증가 / 전체 AA 증가 |
|---|---:|---:|---:|---:|
| bistro | +0.032952 ms (+24.02%) | +0.029906 ms | +0.003026 ms | 90.8% |
| minecraft | +0.028657 ms (+12.80%) | +0.023475 ms | +0.005134 ms | 81.9% |

공간 구간 증가에는 두 edge texture 접근, 현재 point velocity 접근, 재투영·합집합 계산, SV_Depth 기록 및 그에 따른 GPU 실행 특성이 함께 포함된다. 이를 순수 데이터 전송 시간이라고 부르지 않는다. 정확히 어떤 항목이 지배적인지는 별도 profiler/ablation이 필요하다.

각 run의 mean/median/p95/p99/stddev, wall frame, WholeFrame, 1% low에 대응하는 FPS와 paired 변화율은 장면별 `*-benchmark.json`에 보존했다. 전체 AA만 보고 전체 게임 FPS 향상으로 확대하지 않는다.

## 품질 및 직접 프레임 검사

Minecraft f131/f134의 일부 선 단절은 실제 GPU 출력에서 복원됐다. f132/f135처럼 이미 현재 edge로 처리하던 위치는 동일하고, f137에서도 단절이 남는다. 이동 중 선의 출현/소멸 전체가 해결된 것은 아니다. 정지 후 f181부터 추가 후보가 0이 되어 기존 ⑥과 같아진다. Bistro 의자/창문에서도 전반적 품질 개선을 확정할 만큼 차이가 크지는 않다.

두 장면의 원본 full PNG 및 세 ROI의 6연속 이동·정지전환·정지 프레임을 직접 열어 확인했다. Minecraft는 f136~141까지 추가 검사했다. 구체적 위치와 관찰은 [직접 검사 기록](visual-inspection-ko.md)에 있다.

아래 MAE는 RGB 0~255 단위의 **공간 고해상도 참조와의 오차**다. 절대 temporal/고스팅 정답이 아니며, 이 표로 원본 ④보다 체감 품질이 좋다고 결론내리지 않는다.

| 장면 / 구간 | 기존 ⑥ MAE | 새 GPU MAE | 원본 ④ MAE |
|---|---:|---:|---:|
| bistro / 이동 f60~179 | 0.682871 | 0.678393 | 0.734975 |
| bistro / 정지 전환 f178~185 | 0.704683 | 0.702169 | 0.682078 |
| bistro / 정지 f190~239 | 0.709230 | 0.709230 | 0.582826 |
| minecraft / 이동 f60~179 | 1.599557 | 1.631267 | 1.987355 |
| minecraft / 정지 전환 f178~185 | 1.603877 | 1.618624 | 1.795607 |
| minecraft / 정지 f190~239 | 1.569443 | 1.569443 | 1.471707 |

RGB MAE/PSNR, ROI edge strength, frame change 및 reference-delta residual은 장면별 `*-quality.json`에 있다. 수치의 방향이 엇갈리므로 원본 프레임의 구조 보존 문제를 우선한다.

### CGVQM-2 추가 품질 측정

2026-10-01 후속 평가. 새 GPU 구현은 이동 f60~179, 정지 전환 f160~219를 두 장면에서 새로 평가했다(4회). 기존 ⑥과 원본 ④의 8개 점수는 현재 캡처와 참조의 RGB stream hash가 이전 평가 입력과 정확히 같음을 확인한 뒤 재사용했다. 대조군을 새로 평가했다고 표현하지 않는다.

IntelLabs/CGVQM commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`, model 2, CUDA, patch scale 4, mean pooling, 60 fps. FFV1 변환 후 RGB 불일치 0. 점수는 높을수록 좋지만, 고해상도 **공간** 참조에 대한 보조 지표이며 절대 고스팅 점수가 아니다.

| 장면 / 구간 | 기존 ⑥ | 새 GPU | 원본 ④ | 새−기존 ⑥ | 새−원본 ④ |
|---|---:|---:|---:|---:|---:|
| bistro / 이동 f60~179 | 96.173374 | 96.237839 | 96.191238 | +0.064465 | +0.046600 |
| bistro / 정지 전환 f160~219 | 95.911629 | 95.941154 | 96.719254 | +0.029526 | -0.778099 |
| minecraft / 이동 f60~179 | 95.234108 | 95.293442 | 93.911362 | +0.059334 | +1.382080 |
| minecraft / 정지 전환 f160~219 | 94.894165 | 94.901237 | 94.905739 | +0.007072 | -0.004501 |

차이는 점수 단위이며 품질 향상률(%)이 아니다. 정지 전환 CGVQM 구간은 위 MAE 표의 짧은 전환 구간(f178~185)과 다르다. 전체 평균 점수와 무관하게 Minecraft f132/f135/f137의 남은 선 단절을 품질 실패로 기록한다. 두 selective 방식의 Pattern Off와 원본의 Pattern On 차이도 포함되어 있다.

평가 명령, 입력/참조 hash, 재사용 기록과 공식 소스 hash는 `bistro-cgvqm.json`, `minecraft-cgvqm.json`에 보존했다. 재현 도구는 `Tools/SMAA/evaluate_edge_persistence_cgvqm.py`다.


### 선택 영역

이동 구간 중 진단한 23프레임의 평균이다. 전체 120 이동 프레임의 전수 통계나 GPU 시간 변화율이 아니다.

| 장면 | 기존 ⑥ / 전체 픽셀 | 새 GPU / 전체 픽셀 | 선택 픽셀 상대 증가 |
|---|---:|---:|---:|
| bistro | 2.635% | 3.396% | +28.86% |
| minecraft | 22.779% | 28.487% | +25.06% |

## 검증 범위

- 기존 ④·⑥ 960프레임: 수정 전 기준선 RGB hash와 모두 일치.
- 현재 edge만 depth로 전달하는 대조 모드 480프레임: 기존 ⑥과 모두 일치.
- 새 구현 반복 480프레임: 진단 On/Off 출력 모두 일치.
- 258개 진단 draw: 실제 temporal coverage와 occlusion sample 수 일치. 현재 edge 보존, 비선택=현재 spatial, 기존 선택 픽셀의 출력 보존 확인.
- 76개 GPU/CPU union 비교: texel 경계에서 0.01 이상 떨어진 영역의 mask mismatch 0, native 혼합 RGB 최대 오차 1 level. 경계 인접 mask 차이는 Bistro 18 pixel-frame, Minecraft 21 pixel-frame으로 별도 기록했다. 모든 픽셀이 CPU와 bit-exact하다고 주장하지 않는다.
- 기존 shader 14 variant DXBC 동일, 새 shader 4 variant FXC 통과, Release 빌드 및 두 장면 Test/Smoke/Benchmark PASS.
- 첫 프레임 reset과 반복 capture는 확인했다. 별도 resize/teleport fixture, object motion 및 이전 depth 기반 disocclusion rejection은 이번 결과의 검증 범위가 아니다.

## 판단

한 프레임 전 raw edge를 추가하면 현재 edge 판정에서 누락된 일부 선을 복원할 수 있다. 그러나 이번 구현은 기존 ⑥보다 전체 AA 시간이 늘고, 원본 ④ 대비 전체 AA 시간 우위도 얻지 못했다. 남은 선 소실·단절까지 고려하면 기본 구현으로 채택하거나 속도·품질 동시 개선을 주장할 단계는 아니다. 이 결과는 해당 실행 구조와 두 장면의 실험 결과이며, 아이디어 자체가 모든 구현에서 불가능하다는 결론은 아니다.

## GPU GIF / 원본 비교 자료

열 순서: **기존 ⑥ / 직전 raw edge 유지 GPU / 원본 ④ / 고해상도 공간 참조**. selective 두 방식은 Pattern Off, 원본 ④는 Pattern On이다. 10 fps(1/6 속도), 원본 색상, nearest 확대. GIF 색상 양자화와 별개로 무손실 WebP 및 PNG sheet를 함께 보존했다.

- minecraft-thin-line-moving: [GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/minecraft-thin-line-moving.gif) · [무손실 WebP](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/minecraft-thin-line-moving.webp) · [6연속 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/minecraft-thin-line-moving-six.png)
- minecraft-thin-line-stop: [GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/minecraft-thin-line-stop.gif) · [무손실 WebP](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/minecraft-thin-line-stop.webp) · [6연속 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/minecraft-thin-line-stop-six.png)
- minecraft-thin-line-still: [GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/minecraft-thin-line-still.gif) · [무손실 WebP](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/minecraft-thin-line-still.webp) · [6연속 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/minecraft-thin-line-still-six.png)
- bistro-chairs-moving: [GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-chairs-moving.gif) · [무손실 WebP](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-chairs-moving.webp) · [6연속 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-chairs-moving-six.png)
- bistro-chairs-stop: [GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-chairs-stop.gif) · [무손실 WebP](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-chairs-stop.webp) · [6연속 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-chairs-stop-six.png)
- bistro-chairs-still: [GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-chairs-still.gif) · [무손실 WebP](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-chairs-still.webp) · [6연속 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-chairs-still-six.png)
- bistro-window-moving: [GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-window-moving.gif) · [무손실 WebP](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-window-moving.webp) · [6연속 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-window-moving-six.png)
- bistro-window-stop: [GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-window-stop.gif) · [무손실 WebP](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-window-stop.webp) · [6연속 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-window-stop-six.png)
- bistro-window-still: [GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-window-still.gif) · [무손실 WebP](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-window-still.webp) · [6연속 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/edge-persistence-gpu-20261001/bistro-window-still-six.png)

재현: `Tools/SMAA/run_edge_persistence.ps1`, `analyze_edge_persistence_gpu.py`, `create_edge_persistence_gpu_media.py`. 정확한 명령·시각·binary/report hash는 장면별 JSON에 있다. 알고리즘·공식 API 근거는 [method.md](method.md)에 정리했다.
