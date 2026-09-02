# FullScreenDocument Sample-Pattern 2×4 Component Ladder Gate

## 1. 목적

이 gate는 `ABL-Document-FullScreen-PatternOn-R`에서 확인된 motion→still 품질 역전과
후기 정지 2-frame variation이 document temporal kernel의 어느 구성요소에서 처음
나타나는지 확인한다. 최종 8-case를 늘리지 않는 full-screen 진단 실험이다.

## 2. 비교 행렬

K0~K3의 모든 cell은 Original SMAA spatial path, FullScreenDocument compute resolve,
camera/depth reprojection, resolve-output history feedback과 history lifecycle을 공유한다.
Pattern On은 projection jitter와 대응 SMAA T2X subsample index를 함께 켜며, Pattern
Off는 두 요소를 함께 끈다.

| 단계 | History sampler | Clipping | History weight | History source |
|---|---|---|---:|---|
| K0 | Bilinear | Off | 0.5 fixed | Previous resolved output |
| K1 | Catmull-Rom 5-tap | Off | 0.5 fixed | Previous resolved output |
| K2 | Catmull-Rom 5-tap | YCoCg variance | 0.5 fixed | Previous resolved output |
| K3 | Catmull-Rom 5-tap | YCoCg variance | 0.8 fixed | Previous resolved output |

외부 control로 `O-T2X-R`과 `ABL-Standard-PatternOff-R`도 같은 capture에 포함했다. 다만
코드 재감사 결과 공식 Standard resolve는 point history sampling, velocity-alpha 기반
가변 history weight `0~0.5`, 직전 spatial-frame history를 사용한다. 따라서 Standard와
K0의 차이는 실행 경로 하나가 아니며 참고값으로만 사용한다.

## 3. 구현 및 검증

- 새 진단 mode 6개: K0/K1/K2 각각 Pattern On/Off
- 기존 K3 pair 재사용: `ABL-Document-FullScreen-PatternOn-R` / `ABL-Document-FullScreen-R`
- 새 capture 명령: `-smaaDocumentKernelComponentLadderCapture`
- Release x64 빌드: PASS
- Temporal lifecycle: 33 phases, reset 58, frame 99, seed 33, resolve 66,
  reprojection 86, failure 0
- 10-way engineering smoke: mode당 5 PNG, PASS
- Formal capture: Bistro/Minecraft 각각 10 mode × 480 frames
- 기존 4개 control sequence hash bridge: 장면당 4개, 총 8개 sequence mismatch 0
- 잔류 `CMAA2.exe`: 0

### 원시 및 분석 경로

- Lifecycle: `D:/SMAA-Research-Data/AutoBench/20260902_150749`
- Smoke: `D:/SMAA-Research-Data/AutoBench/20260902_150836`
- Bistro formal capture: `D:/SMAA-Research-Data/AutoBench/20260902_151454`
- Minecraft formal capture: `D:/SMAA-Research-Data/AutoBench/20260902_152414`
- Spatial analysis: `D:/SMAA-Research-Data/AutoBench/20260902_DocumentKernelComponentLadder/SpatialAnalysis`
- New ladder CGVQM: `D:/SMAA-Research-Data/AutoBench/20260902_DocumentKernelComponentLadder/CGVQM-NewLadder`
- Combined CGVQM analysis: `D:/SMAA-Research-Data/AutoBench/20260902_DocumentKernelComponentLadder/CGVQM-Analysis`

## 4. 공식 CGVQM-2 검증

- IntelLabs/CGVQM commit: `8302ff45b4ff5a691682baf23f7c007d6b591e98`
- GPU: NVIDIA GeForce RTX 3060 Ti, CUDA
- 새 K0~K2: 24/24 jobs PASS
- Standard/K3 재사용 결과를 포함한 총 40/40 validation PASS
- 모든 test/reference FFV1 RGB round-trip mismatch 0
- 각 scene/window의 10개 mode가 동일 reference pixel hash 사용

점수는 높을수록 좋다.

| Scene | Window | Std On | Std Off | K0 On | K0 Off | K1 On | K1 Off | K2 On | K2 Off | K3 On | K3 Off |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Bistro | Central motion | 94.133018 | 96.395256 | 93.903664 | 95.445160 | 94.286842 | 95.622330 | 95.932449 | 97.503708 | 95.235268 | 96.483780 |
| Bistro | Motion→still | 95.126778 | 94.449066 | 93.818260 | 94.851151 | 94.041016 | 94.836929 | 92.286308 | 94.737526 | 93.765358 | 94.746887 |
| Minecraft | Central motion | 95.986458 | 97.464355 | 96.897392 | 98.025848 | 97.223083 | 98.238174 | 97.098259 | 98.219849 | 96.553169 | 97.481895 |
| Minecraft | Motion→still | 94.646790 | 93.618713 | 93.396431 | 93.861580 | 93.626038 | 93.960670 | 91.926147 | 93.855148 | 93.528343 | 93.836052 |

## 5. Pattern On/Off 결과

아래는 `Off - On` 점수다. 양수면 Pattern Off가 더 좋다.

| Scene | Window | K0 | K1 | K2 | K3 |
|---|---|---:|---:|---:|---:|
| Bistro | Central motion | +1.541496 | +1.335487 | +1.571259 | +1.248512 |
| Bistro | Motion→still | +1.032890 | +0.795914 | +2.451218 | +0.981529 |
| Minecraft | Central motion | +1.128456 | +1.015091 | +1.121590 | +0.928726 |
| Minecraft | Motion→still | +0.465149 | +0.334633 | +1.929001 | +0.307709 |

Document feedback path에서는 가장 단순한 K0부터 두 장면·두 window 모두 Pattern Off가
우수했다. 따라서 기존 K3의 Pattern-On 열세를 Catmull-Rom, clipping 또는 0.8 weight가
처음 만든 것으로 볼 수 없다.

## 6. 구성요소별 영향

### K0→K1: Catmull-Rom 5-tap

- Pattern On: 네 scene/window에서 `+0.222755~+0.383179`
- Pattern Off: central motion `+0.177170/+0.212326`, transition
  `-0.014221/+0.099091`

Catmull-Rom은 대체로 소폭 개선했으며 문제의 최초 원인이 아니다.

### K1→K2: YCoCg variance clipping

- Pattern On central: Bistro `+1.645607`, Minecraft `-0.124825`
- Pattern On transition: Bistro `-1.754707`, Minecraft `-1.699890`
- Pattern Off central: Bistro `+1.881378`, Minecraft `-0.018326`
- Pattern Off transition: `-0.099403/-0.105522`

Clipping은 장면과 motion phase에 매우 민감했다. 특히 Pattern On transition에서는 두
장면 모두 큰 하락을 만들었다.

### K2→K3: history weight 0.5→0.8

- Pattern On central: `-0.697182/-0.545090`
- Pattern On transition: `+1.479050/+1.602196`
- Pattern Off central: `-1.019928/-0.737953`
- Pattern Off transition: `+0.009361/-0.019096`

0.8 weight는 Pattern On의 transition 손실을 크게 회복하지만 central motion 점수를
낮췄다. 모든 phase에서 우수한 단일 고정값으로 판단할 수 없다.

## 7. 후기 정지 2-frame 진단

같은 pose supersample spatial proxy를 제거한 temporal residual에서 Pattern On K0가 이미
큰 1-frame 변화와 매우 작은 2-frame 변화를 보였다.

| Scene | Mode | Δ1 residual | Δ2 residual |
|---|---|---:|---:|
| Bistro | K0 On | 1.524063 | 0.005024 |
| Bistro | K2 On | 1.881585 | 0.046428 |
| Bistro | K3 On | 0.649936 | 0.054012 |
| Minecraft | K0 On | 1.364133 | 0.004767 |
| Minecraft | K2 On | 1.669681 | 0.021602 |
| Minecraft | K3 On | 0.583506 | 0.030635 |

즉 2-phase variation은 K0에서 이미 존재하며 clipping이 키우고 0.8 weight가 줄이지만
제거하지 못한다. 이는 paired pattern과 resolved-output feedback 계열의 상호작용을
우선 조사해야 한다는 근거다.

## 8. 코드 재감사 정정

공식 SMAA `SMAAResolvePS`와 현재 DX11 wrapper를 다시 추적해 다음을 확인했다.

1. Standard reprojection은 current/history를 point sample한다.
2. Neighborhood blending 결과 alpha에는 `sqrt(5 * |velocity|)`가 저장된다.
3. Resolve weight는 두 alpha의 차이로 계산되며 `0~0.5`로 감쇠한다.
4. Standard ping-pong history에는 각 프레임의 spatial T2X 결과가 저장되고 visible
   resolve 출력은 다음 history로 feedback되지 않는다.
5. Document/ET2X는 resolve 출력을 다음 history로 feedback한다.

따라서 과거 `O-T2X-R`을 “bilinear + fixed 0.5”라고 기록한 문구와
Standard→CandidateOnly를 coverage-only로 해석한 attribution을 정정했다. 과거 측정값은
보존하지만 해당 단일원인 결론에는 사용하지 않는다.

## 9. 결론

1. Document feedback 경로에서 paired sample pattern은 K0부터 central motion과
   motion→still 품질을 모두 낮췄다.
2. Catmull-Rom은 대체로 소폭 개선하며 최초 원인이 아니다.
3. Clipping과 0.8 weight는 phase별 trade-off를 크게 바꾸지만 K0에서 시작된 문제를
   일관되게 해결하지 못한다.
4. 현재 결과만으로 document/ET2X profile에 paired SMAA pattern을 재활성화하지 않는다.
5. Standard-K0는 sampler, weight policy, feedback topology와 실행 경로가 함께 달라 직접
   attribution할 수 없다.

## 10. 다음 gate

motion-phase heuristic이나 persistence를 추가하기 전에 FullScreenDocument 경로에서
다음 세 축을 직교 분리한다.

1. Point / Bilinear history sampling
2. Velocity-alpha adaptive `0~0.5` / fixed `0.5` history weight
3. Previous spatial-frame / resolved-output feedback history

먼저 공식 Standard 의미를 compute path에서 재현해 공식 Standard 출력과 대조한 뒤,
paired Pattern On/Off와 위 세 축의 interaction을 측정한다. 이 gate가 끝나기 전에는
K0-Standard 차이를 특정 구성요소의 효과로 표현하지 않는다.
