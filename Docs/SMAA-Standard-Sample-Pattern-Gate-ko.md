# SMAA Standard T2X Temporal Sample-Pattern 원인 분리 결과

## 1. 목적

이 실험은 `O-ET2X-R`이 `O-T2X-R`보다 motion→still 구간에서 낮은 temporal 품질을 보인 원인이
edge-selective coverage인지, Standard SMAA T2X의 temporal subpixel sample pattern인지 분리하기 위한
후속 quality gate다.

이전 coverage-only gate에서 `ABL-Document-FullScreen-R`은 `O-ET2X-R`보다 transition CGVQM-2가
Bistro `+0.185905`, Minecraft `+0.097031` 높았지만, 여전히 `O-T2X-R`보다 각각 `-0.379891`,
`-0.810738` 낮았다. 따라서 coverage만으로 Standard 대비 차이를 설명할 수 없었다.

## 2. 공식 SMAA T2X 감사 결과

공식 SMAA HLSL의 T2X 설명과 현재 코어 구현을 대조한 결과, 다음 두 요소는 독립 설정이 아니라
한 쌍의 temporal sample pattern이다.

| Frame | Projection jitter | SMAA subsample indices |
|---|---|---|
| S0 | `(0.25, -0.25)` | `(1, 1, 1, 0)` |
| S1 | `(-0.25, 0.25)` | `(2, 2, 2, 0)` |

따라서 projection jitter만 끄고 T2X subsample index는 계속 교대시키는 조합은 유효한 SMAA T2X
control이 아니다. 이번 실험에서는 두 요소를 함께 On/Off하는 하나의 개념 축으로 정의했다.

## 3. 새 진단군

`ABL-Standard-PatternOff-R`을 추가했다.

| 항목 | O-T2X-R | ABL-Standard-PatternOff-R |
|---|---|---|
| Temporal coverage | Full-screen | Full-screen |
| Temporal resolve | Standard | Standard |
| History sampler | Point | Point |
| History weight | velocity-alpha adaptive 0~0.5 | velocity-alpha adaptive 0~0.5 |
| History source | 직전 spatial T2X frame | 직전 spatial 1X frame |
| Clipping | Off | Off |
| Reprojection | Camera/depth | Camera/depth |
| History lifecycle | 동일 | 동일 |
| Projection jitter | SMAA T2X | Off |
| SMAA spatial subsample | T2X indices 1/2 | SMAA 1X, zero indices |

즉 바뀌는 요소는 유효한 SMAA T2X temporal subpixel sample pattern 전체뿐이다. 이 진단군은
최종 8-case를 늘리지 않으며 원본 `O-T2X-R` 동작도 변경하지 않는다.

## 4. 구현 및 검증

- Standard full-screen resolve 경로가 temporal settings의 jitter policy에 따라 `MODE_SMAA_T2X` 또는
  `MODE_SMAA_1X`를 선택하도록 했다.
- production `O-T2X`, `O-T2X-R`, `A-T2X`, `A-T2X-R`은 계속 `SMAAT2X` jitter를 사용하므로 기존
  `MODE_SMAA_T2X` 경로가 그대로 유지된다.
- Pattern-Off 진단군만 jitter `(0,0)`과 subsample `(0,0,0,0)`을 함께 사용한다.
- lifecycle test에 Pattern-Off phase를 추가했다.

검증 결과:

- Release x64 빌드: PASS
- temporal lifecycle: 26 phases, reset 49, frame 78, seed 26, resolve 52, reprojection 65,
  failure 0, PASS
- 5-frame × 5-mode smoke: 각 mode 5/5 PNG, 정상 종료
- Bistro formal capture: 480 frames × 5 modes = 2,400 PNG, clean process PASS
- Minecraft formal capture: 480 frames × 5 modes = 2,400 PNG, clean process PASS
- 기존 formal control과 hash bridge: 8 sequences × 480 frames, byte mismatch 0

## 5. 측정 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- API/preset: DirectX 11, SMAA Ultra
- 해상도: 1920×1017
- 장면: Bistro, Minecraft
- camera profile: `flythrough-wide-yaw-360`
- profile frame: 0~479, fixed 60 Hz
- mode별 warm-up: 60 frames
- spatial reference: 동일 pose 2× linear resolution, 3×3 subpixel grid, 8×MSAA
- CGVQM-2: Intel 공식 commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`, CUDA,
  patch scale 4, mean pooling
- formal window: central motion 150~329, motion→still transition 410~439
- FFV1 test/reference 왕복 mismatch: 0

## 6. 공식 CGVQM-2 결과

점수는 높을수록 좋다. CGVQM-2는 full-reference perceptual video metric이며 절대 ghosting
ground truth는 아니다.

| Scene | Window | O-1X | O-T2X-R | PatternOff-R | FullDocument-R | O-ET2X-R |
|---|---|---:|---:|---:|---:|---:|
| Bistro | central motion | 96.981567 | 94.133018 | 96.395256 | 96.483780 | 96.688606 |
| Bistro | motion→still | 94.410881 | 95.126778 | 94.449066 | 94.746887 | 94.560982 |
| Minecraft | central motion | 97.565102 | 95.986458 | 97.464355 | 97.481895 | 97.515762 |
| Minecraft | motion→still | 93.409264 | 94.646790 | 93.618713 | 93.836052 | 93.739021 |

### Sample pattern의 직접 효과

`PatternOff-R − O-T2X-R`:

| Scene | Central motion | Motion→still |
|---|---:|---:|
| Bistro | +2.262238 | -0.677711 |
| Minecraft | +1.477898 | -1.028076 |

central motion에서는 Pattern-Off가 더 높고, motion→still에서는 Standard가 더 높다.

### 나머지 document kernel 효과

`FullDocument-R − PatternOff-R`:

| Scene | Central motion | Motion→still |
|---|---:|---:|
| Bistro | +0.088524 | +0.297821 |
| Minecraft | +0.017540 | +0.217339 |

sample pattern과 full-screen coverage를 모두 Off/동일하게 둔 상태에서 Catmull-Rom 5-tap,
YCoCg clipping, history weight 0.8의 document kernel은 두 구간 모두 점수를 소폭 회복했다.

### Coverage 효과

`O-ET2X-R − FullDocument-R`:

| Scene | Central motion | Motion→still |
|---|---:|---:|
| Bistro | +0.204826 | -0.185905 |
| Minecraft | +0.033867 | -0.097031 |

edge-selective coverage는 central motion에서 유리했지만 motion→still에서 불리했다. 다만 그 차이는
Standard sample pattern On/Off 차이보다 작았다.

## 7. Spatial-reference 보조 결과

central motion의 RGB MAE는 Pattern-Off가 Standard보다 Bistro `0.688243`, Minecraft `0.369958`
낮았다. 반대로 후기 정지에서 Pattern-Off는 O-1X와 동일한 평균 RGB MAE로 수렴했고 Standard보다
Bistro `0.081648`, Minecraft `0.108075` 높았다.

이는 Pattern-Off가 이동 중 동일-pose spatial 오차를 줄이는 대신, 정지 상태에서 두 subpixel phase를
누적하는 Standard T2X의 temporal supersampling 이점을 잃는다는 CGVQM 결과와 같은 방향이다.

## 8. 결론

1. 이전 motion→still 열세는 edge coverage만의 문제가 아니다.
2. Standard SMAA T2X의 paired jitter/subsample pattern은 central camera motion에서는 현재 reference
   조건의 perceptual 오차를 키우는 주요 요인이지만, motion→still에서는 2-frame subpixel accumulation
   이점을 제공한다.
3. Pattern-Off가 대체로 O-1X에 가까워진 결과는 full-screen Standard resolve만 남겨서는 temporal
   supersampling 이점이 제한적임을 보여준다.
4. document kernel과 edge-selective coverage는 central motion 품질을 추가로 개선하지만, 정지 전환의
   Standard sample diversity를 완전히 대체하지 못한다.
5. 따라서 다음 개선은 단순히 temporal candidate coverage를 늘리는 방식보다, 이동 중 ET2X의 장점을
   유지하면서 정지 전환에서 유효한 temporal sample diversity를 복구하는 controlled profile을 먼저
   설계·검증해야 한다.

## 9. 해석 제한 및 다음 gate

- 현재 `-R`은 camera/depth reprojection이며 object motion vector를 뜻하지 않는다.
- supersample reference는 동일 pose spatial proxy이며 절대 temporal ground truth가 아니다.
- 이번 결과는 Bistro/Minecraft의 고정 wide camera path 두 장면에 한정된다.
- 다음에는 document kernel에서 paired SMAA T2X sample pattern을 On/Off한 full-screen 및
  edge-selective control을 구성해 kernel×pattern interaction을 확인해야 한다.
- edge-selective pattern-On에서 비후보 픽셀이 jittered spatial base로 남지 않도록 기존 de-jitter base
  경로를 먼저 재감사해야 한다.
- 이 interaction gate가 끝나기 전에는 motion-phase heuristic이나 candidate persistence를 최종
  개선안으로 확정하지 않는다.

## 10. 결과 경로

- 캡처
  - Bistro: `D:\SMAA-Research-Data\AutoBench\20260902_111537`
  - Minecraft: `D:\SMAA-Research-Data\AutoBench\20260902_112023`
- spatial/temporal proxy 분석:
  `D:\SMAA-Research-Data\AutoBench\20260902_StandardSamplePattern\Analysis`
- Pattern-Off CGVQM 원시 결과:
  `D:\SMAA-Research-Data\AutoBench\20260902_StandardSamplePattern\CGVQM-PatternOff`
- CGVQM 통합 분석:
  `D:\SMAA-Research-Data\AutoBench\20260902_StandardSamplePattern\CGVQM-Analysis`
