# 이전 edge 유지의 공간 비용 분석 및 동일 출력 최적화

브랜치: `experiment/edge-persistence-spatial-cost`. 직접 기준선 ⑥ `304f749`, 명시적 의존성 `a8eca21`/`9b9953e`/`24c26fb`. 기존 ①~⑧ 브랜치를 변경하지 않았다.

RTX 3060 Ti, DX11 Release x64, Ultra, 1920×1061, hidden, VSync Off. 각 장면의 독립 clean process 안에서 순서를 교차했다. 전체 성능은 300 warm-up + 4,800프레임×3회이며 패스별 추가 계측·PNG·readback·invocation query는 Off다. 별도 진단은 960프레임×3회로 준비/1차/2차/3차를 계측했다. 두 종류의 절대 시간을 섞지 않는다.

④는 paired sample pattern On, ⑥·⑧·F·U·G는 Off다. F/U/G와 ⑧ 사이의 지터, 선택, history, 재투영, sampling, 혼합식은 같다. Camera/depth motion만 사용한다.

## 진단 계측을 끈 전체 성능

| 장면 | 구성 | 전체 AA ms | ④ 대비 | ⑧ 대비 | temporal ms |
|---|---|---:|---:|---:|---:|
| bistro | ④ 원본 T2X-R | 0.163372 | +0.00% | +10.58% | 0.034198 |
| bistro | ⑥ 현재 edge | 0.139119 | -14.85% | -5.84% | 0.007478 |
| bistro | ⑧ 기존 union | 0.147740 | -9.57% | +0.00% | 0.007751 |
| bistro | F 이전 edge 선행 조회 | 0.140113 | -14.24% | -5.16% | 0.007729 |
| bistro | U depth 표시·union 공간 처리 | 0.147503 | -9.71% | -0.16% | 0.007664 |
| bistro | G depth 표시·현재 edge만 공간 처리 | 0.147232 | -9.88% | -0.34% | 0.007684 |
| minecraft | ④ 원본 T2X-R | 0.234688 | +0.00% | -3.34% | 0.035897 |
| minecraft | ⑥ 현재 edge | 0.224502 | -4.34% | -7.53% | 0.023646 |
| minecraft | ⑧ 기존 union | 0.242792 | +3.45% | +0.00% | 0.024280 |
| minecraft | F 이전 edge 선행 조회 | 0.234403 | -0.12% | -3.46% | 0.024195 |
| minecraft | U depth 표시·union 공간 처리 | 0.245148 | +4.46% | +0.97% | 0.024237 |
| minecraft | G depth 표시·현재 edge만 공간 처리 | 0.242982 | +3.53% | +0.08% | 0.024145 |

## 별도 진단: 1·2·3차 비용

| 장면 | 구성 | 준비 ms | 1차 edge·선택 ms | 2차 weight ms | 3차 blending ms |
|---|---|---:|---:|---:|---:|
| bistro | ⑥ 현재 edge | 0.008317 | 0.027964 | 0.024970 | 0.045825 |
| bistro | ⑧ 기존 union | 0.008332 | 0.035838 | 0.025870 | 0.045398 |
| bistro | F 이전 edge 선행 조회 | 0.008310 | 0.028124 | 0.025858 | 0.045397 |
| bistro | U depth 표시·union 공간 처리 | 0.008336 | 0.035622 | 0.025860 | 0.045482 |
| bistro | G depth 표시·현재 edge만 공간 처리 | 0.008319 | 0.035639 | 0.025528 | 0.045380 |
| minecraft | ⑥ 현재 edge | 0.005965 | 0.028944 | 0.087629 | 0.053723 |
| minecraft | ⑧ 기존 union | 0.005974 | 0.043466 | 0.090135 | 0.053559 |
| minecraft | F 이전 edge 선행 조회 | 0.006008 | 0.035578 | 0.090242 | 0.053775 |
| minecraft | U depth 표시·union 공간 처리 | 0.005990 | 0.045423 | 0.090644 | 0.053679 |
| minecraft | G depth 표시·현재 edge만 공간 처리 | 0.006004 | 0.045317 | 0.088984 | 0.053626 |

## 대응 비교와 반복 변동

| 장면 | 비교 | 전체 AA 차이 ms | 시간 변화율 | 반복별 변화율 |
|---|---|---:|---:|---|
| bistro | ⑧ 기존 union − ⑥ 현재 edge | +0.008621 | +6.20% | +6.05%/+6.22%/+6.32% |
| bistro | F 이전 edge 선행 조회 − ⑧ 기존 union | -0.007626 | -5.16% | -4.89%/-5.49%/-5.10% |
| bistro | F 이전 edge 선행 조회 − ⑥ 현재 edge | +0.000994 | +0.71% | +0.87%/+0.39%/+0.89% |
| bistro | F 이전 edge 선행 조회 − ④ 원본 T2X-R | -0.023259 | -14.24% | -14.22%/-14.44%/-14.06% |
| bistro | G depth 표시·현재 edge만 공간 처리 − U depth 표시·union 공간 처리 | -0.000271 | -0.18% | -0.00%/-0.38%/-0.17% |
| bistro | U depth 표시·union 공간 처리 − ⑧ 기존 union | -0.000237 | -0.16% | -0.14%/-0.09%/-0.25% |
| bistro | G depth 표시·현재 edge만 공간 처리 − ⑧ 기존 union | -0.000507 | -0.34% | -0.14%/-0.46%/-0.43% |
| minecraft | ⑧ 기존 union − ⑥ 현재 edge | +0.018290 | +8.15% | +8.88%/+6.79%/+8.79% |
| minecraft | F 이전 edge 선행 조회 − ⑧ 기존 union | -0.008389 | -3.46% | -3.90%/-2.37%/-4.09% |
| minecraft | F 이전 edge 선행 조회 − ⑥ 현재 edge | +0.009901 | +4.41% | +4.63%/+4.26%/+4.34% |
| minecraft | F 이전 edge 선행 조회 − ④ 원본 T2X-R | -0.000285 | -0.12% | -0.83%/+0.82%/-0.35% |
| minecraft | G depth 표시·현재 edge만 공간 처리 − U depth 표시·union 공간 처리 | -0.002166 | -0.88% | -1.48%/+0.25%/-1.41% |
| minecraft | U depth 표시·union 공간 처리 − ⑧ 기존 union | +0.002357 | +0.97% | +1.22%/+0.83%/+0.86% |
| minecraft | G depth 표시·현재 edge만 공간 처리 − ⑧ 기존 union | +0.000190 | +0.08% | -0.28%/+1.09%/-0.56% |

## 판정

이번 결과에서는 F를 동일 출력의 비용 개선안으로 선정하고, U/G는 비용 분리 실험으로 보존한다. F는 양 장면의 세 반복 모두에서 ⑧보다 전체 AA 시간이 짧았다. 기존 ①~⑧ 및 일반 실행 기본값을 덮어쓰지 않고 전용 F 설정으로 구분한다.
Bistro에서 F는 ⑧ 대비 5.16%, ④ 대비 14.24% 짧다. Minecraft는 ⑧ 대비 3.46% 짧지만 ④ 대비는 평균 −0.12%, 반복별 −0.83/+0.82/−0.35%로 방향이 섞인다. 따라서 Minecraft에서 ④보다 확실히 빠르다는 결론은 내리지 않는다.
⑥ 대비 남은 전체 AA 추가 비용은 Bistro 0.71%, Minecraft 4.41%다. 이전 edge 유지 비용을 완전히 제거한 것은 아니다. 진단의 1차 패스는 ⑧→F에서 각각 0.007714/0.007888 ms 감소했다. ⑧의 2차 패스 증가(⑥ 대비 0.000900/0.002506 ms)보다 1차 증가(0.007874/0.014522 ms)가 컸다. 전체 증가의 주요 구간을 1차로 특정했으며, GPU 내부 stall 원인까지 확정하지 않는다.
G는 2차 실행 픽셀 수를 정확히 줄였지만, 전체 AA 변화는 ⑧ 대비 Bistro −0.34%/Minecraft +0.08%였다. 2차 영역 분리만으로 주요 비용이 해결된다는 가설은 지지되지 않았다. U/G를 F와 결합하는 추가 실험은 수행하지 않았다.
전체 프레임 시간의 F−⑧ 변화는 Bistro −0.16%/Minecraft −0.42%로 AA 구간 변화보다 작다. 특히 Bistro는 반복별 방향이 섞여, 전체 게임 성능의 일관된 향상으로 확대 해석하지 않는다.

## 무엇이 바뀌었는가

- F는 현재 edge가 없다고 판단한 뒤 이전 edge를 읽는 종속 분기를 제거하고, 기존 velocity/이전 raw edge를 먼저 조회한다. 조회량은 늘 수 있으나 같은 재투영 좌표·화면 경계 판정·합집합을 사용한다. DXBC에서 접근과 분기가 실제로 달라지는 것을 확인했다. GPU native scheduling/cache stall까지 직접 계측한 것은 아니다.
- U/G는 1차 패스에서 현재 edge 여부를 depth 1/0에 기록한다. U는 여전히 union에서 2차를 실행하고, G만 depth=1과 union stencil을 함께 검사하여 현재 edge에서만 2차를 실행한다. Temporal은 둘 다 기존 union stencil을 그대로 사용한다. 별도 draw/dispatch/copy는 없다.
- U/G는 표시 비용과 2차 실행 절약을 구분하는 대조다. ⑦에서 비쌌던 3차 패스 depth export를 다시 사용하는 것은 아니다. 하지만 1차의 export도 공짜라고 가정하지 않으며 U−⑧과 G−U로 확인한다.
- Microsoft의 shader-specified stencil reference는 실제 데모 장치에서 미지원이었다. 이 선택 기능에 의존하는 두 stencil bit 출력은 구현 경로에서 제외했다.

F의 변경을 단순화하면 아래와 같다. 실제 HLSL에서는 원래의 재투영 좌표, point sampling과 화면 경계 검사를 유지한다. 이전 raw edge 조회는 모든 픽셀에서 하지만, temporal 색상 읽기·혼합은 기존 union stencil을 통과한 픽셀에서만 실행한다.

```text
기존 ⑧: 현재 edge 계산 → 없으면 이전 edge 조회 → union stencil
변경 F: 이전 edge 조회를 먼저 시작 + 현재 edge 계산 → 같은 union stencil
공통 후속: 기존 SMAA 공간 처리 → union에만 원본 T2X-R 계산
```

## 출력·실행·시각 검증

두 장면에서 각 방식 240프레임을 저장했다. F/U/G 각각의 최종 RGB 480프레임이 ⑧과 byte/hash 일치했다. ⑥·⑧·④도 보존된 기존 캡처와 일치한다. 각 장면 43개 진단 프레임에서 current raw RG, 공간 SMAA DDS, 실제 temporal coverage와 비선택 출력 보존을 검증했다.
G의 2차 passing samples는 현재 raw edge 수와, E/F/U의 수는 union 수와 일치한다. Minecraft f131에서 652,244→520,091개로 2차 실행을 줄였고 temporal 적용 652,244개는 유지했다. GPU query는 성능 측정에서 껐다.
원본 전체 프레임과 이동 130–135, 전환 178–183, 정지 190–195의 연속 PNG 확대를 직접 확인했다. 기존 Minecraft의 얇은 선 단절 등은 그대로이며 새 품질 개선을 주장하지 않는다. CGVQM은 재실행하지 않았다. 검사 이미지 경로는 `inspection-manifest.json`에 기록했다.
같은 ROI의 frame 120–209를 60 FPS로 재생하는 [Bistro 영상](../../tmp/spatial-cost-inspection/bistro-same-output-60fps.mp4)과 [Minecraft 영상](../../tmp/spatial-cost-inspection/minecraft-same-output-60fps.mp4)을 별도 제공한다. 디코딩 프레임 수와 60 Hz timestamp는 검증했지만 재생 영상을 직접 보았다고 주장하지 않는다. H264 발표용 영상이며 품질 입력은 무손실 PNG다.
첫 Bistro capture의 G/frame129 PNG 하나가 디코딩에 실패하여 해당 실행 전체를 제외하고 다시 캡처했다. 실패 자료는 삭제하거나 다른 실행의 프레임으로 메우지 않았다. `excluded-capture.json`에 보존했다.
Minecraft clean smoke 첫 기동은 재질 셰이더의 입력 매크로 누락 오류로 종료됐다. 완성된 결과 파일이 없어 제외했고, 소스/실행파일을 바꾸지 않은 독립 재시도는 PASS했다. 원인 분리가 끝난 오류 수정으로 표현하지 않으며 `excluded-startup.json`에 기록했다.
Capture 이후에는 진단 profile 길이와 안내문만 바꿨다. clean benchmark 길이와 렌더러 소스는 같으며 실행파일 사이의 대응은 `capture-to-timing-source-bridge.json`에 기록했다. Native shader 14개 bytecode 일치 및 추가 edge shader 12개 컴파일을 확인했다.
추가로 네 입력 종류에 세 칸뿐이던 technique 배열을 네 칸으로 교정했다. 사용 중인 LumaRaw 기준선 출력은 기존 hash와 같다.

## 근거와 적용 한계

원본 SMAA와 Unity HDRP의 stencil 기반 weight pass, Microsoft depth/stencil 기능 계약, NVIDIA의 분기·texture latency 지침을 참고했다. 구체적 출처와 선택 기능의 지원 검사는 [설계 기록](method.md)에 있다. TAA survey는 accumulation/history validation을 구분하는 근거이며, 이번 edge union의 품질이나 속도를 입증하는 논문으로 인용하지 않는다.
이번 결과는 두 장면/한 GPU에서 동일 출력을 유지하는 실행 비용 비교다. 지터·dilation·history 알고리즘 변경이나 다른 GPU/모든 장면에서의 최적화 한계 도달을 주장하지 않는다.
