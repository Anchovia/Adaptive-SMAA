# SMAA Document Kernel × Temporal Sample-Pattern 상호작용 결과

## 1. 목적

이 gate는 `O-T2X-R`의 paired SMAA T2X sample pattern이 Standard temporal kernel과
document-based temporal kernel에서 같은 효과를 내는지 분리한다. 이전 gate에서는
Standard kernel의 pattern을 끄면 central motion 품질은 좋아졌지만 motion→still
transition 품질은 낮아졌다. 그러나 document kernel에는 같은 Pattern-On control이 없어
이 차이가 sample pattern 자체인지 kernel과의 상호작용인지 판단할 수 없었다.

이번 결과는 최종 8-case를 늘리거나 `O-ET2X-R`의 기본 설정을 변경하지 않는 diagnostic
quality gate다.

## 2. DeJitter 재감사와 실험 범위

기존 `ABL-Candidate-DeJitter-R`은 jittered spatial image를
`outputUV + jitter / resolution` 위치에서 bilinear sample하는 screen-space 근사다.
별도의 unjittered scene render가 아니며 기존 측정에서 경계 연화와 reference 오차가
확인되어 최종 방식으로 탈락했다.

따라서 edge-selective Pattern-On의 비후보 영역을 이 DeJitter 결과로 채우면 다음 두
요소가 섞인다.

- paired sample pattern On/Off 효과
- full-screen bilinear inverse-jitter filtering 효과

이 비교는 공정한 pattern×coverage gate가 아니므로 만들지 않았다. 대신 안정적인 spatial
base를 유지할 수 있는 full-screen 경로에서 kernel×pattern 2×2를 먼저 구성하고,
Pattern-Off 상태에서만 기존 full-screen↔edge coverage pair를 연결했다.

## 3. 비교 행렬

모든 temporal mode는 Original SMAA, camera/depth reprojection, 같은 history lifecycle을
사용한다. projection jitter와 SMAA subsample index는 공식 SMAA T2X의 paired pattern으로
항상 함께 On/Off한다.

| Mode | Coverage | Pattern | Sampler | Clipping | History weight | History source |
|---|---|---|---|---|---:|---|
| `O-T2X-R` | Full-screen | On | Point | Off | velocity-alpha adaptive 0~0.5 | 직전 spatial frame |
| `ABL-Standard-PatternOff-R` | Full-screen | Off | Point | Off | velocity-alpha adaptive 0~0.5 | 직전 spatial frame |
| `ABL-Document-FullScreen-PatternOn-R` | Full-screen | On | Catmull-Rom 5-tap | YCoCg variance | 0.8 | 직전 resolve output feedback |
| `ABL-Document-FullScreen-R` | Full-screen | Off | Catmull-Rom 5-tap | YCoCg variance | 0.8 | 직전 resolve output feedback |
| `O-ET2X-R` | Integrated first-pass edge | Off | Catmull-Rom 5-tap | YCoCg variance | 0.8 | 직전 resolve output feedback |

`O-1X`는 spatial-only control이다. 새 Pattern-On document mode는 진단군이며 Intel 공식
TSCMAA mode 또는 최종 연구 case가 아니다.

## 4. 구현

- `SMAA_O_ABLATION_DOCUMENT_FULLSCREEN_PATTERN_ON_R`을 추가했다.
- full-screen document resolve가 `JitterPolicy`에 따라 SMAA spatial mode를 선택하게 했다.
  - Pattern On: `MODE_SMAA_T2X`
  - Pattern Off: `MODE_SMAA_1X`
- Pattern On에서는 projection jitter와 `(1,1,1,0)/(2,2,2,0)` subsample index가 함께
  교대한다.
- Catmull-Rom sampling, YCoCg clipping, history weight 0.8, camera/depth reprojection과
  feedback history는 기존 full-screen document control과 동일하다.
- Standard production 4개 mode와 최종 8-case 정의는 변경하지 않았다.

## 5. 구현 검증

- Release x64: PASS, error 0
- Python analyzer syntax: PASS
- temporal lifecycle:
  - 27 phases
  - reset 51, completed frame 81
  - seed 27, resolve 54, reprojection 68
  - failure 0, PASS
- 6-mode 5-frame smoke: mode별 5/5 PNG, 정상 종료
- Bistro formal capture: 6 modes × 480 frames, 잔류 CMAA2 process 0
- Minecraft formal capture: 6 modes × 480 frames, 잔류 CMAA2 process 0
- 기존 O-1X/O-T2X-R/O-ET2X-R/Document-Off 8개 sequence hash bridge: mismatch 0
- 새 Pattern-Off와 이전 formal Pattern-Off 2개 sequence × 480 PNG: mismatch 0

## 6. 측정 조건

- GPU: NVIDIA GeForce RTX 3060 Ti
- API/preset: DirectX 11, SMAA Ultra
- 해상도: 1920×1017
- 장면: Bistro, Minecraft
- camera profile: `flythrough-wide-yaw-360`
- fixed timestep: 60 Hz
- profile: 480 frames, mode별 60-frame first-pose warm-up
- reference: 동일 pose 2× linear resolution, 3×3 subpixel grid, 8×MSAA
- CGVQM-2: IntelLabs 공식 commit
  `8302ff45b4ff5a691682baf23f7c007d6b591e98`, CUDA, patch scale 4, mean pooling
- window:
  - central motion: frame 150~329
  - motion→still transition: frame 410~439
- 모든 CGVQM test/reference FFV1 round-trip pixel mismatch: 0

## 7. CGVQM-2 결과

점수는 높을수록 좋다. CGVQM-2는 full-reference perceptual video metric이며 절대
ghosting ground truth는 아니다.

| Scene | Window | O-1X | Standard On | Standard Off | Document On | Document Off | Edge Off |
|---|---|---:|---:|---:|---:|---:|---:|
| Bistro | central motion | 96.981567 | 94.133018 | 96.395256 | 95.235268 | 96.483780 | 96.688606 |
| Bistro | motion→still | 94.410881 | 95.126778 | 94.449066 | 93.765358 | 94.746887 | 94.560982 |
| Minecraft | central motion | 97.565102 | 95.986458 | 97.464355 | 96.553169 | 97.481895 | 97.515762 |
| Minecraft | motion→still | 93.409264 | 94.646790 | 93.618713 | 93.528343 | 93.836052 | 93.739021 |

### 7.1 Standard kernel의 pattern 효과

`Standard Off − Standard On`:

| Scene | Central motion | Motion→still |
|---|---:|---:|
| Bistro | +2.262238 | -0.677711 |
| Minecraft | +1.477898 | -1.028076 |

Standard kernel에서는 Pattern Off가 central motion에서 높지만 Pattern On이
motion→still에서 높다. 즉 paired pattern의 정지 전환 temporal accumulation 이점이
재현된다.

### 7.2 Document kernel의 pattern 효과

`Document Off − Document On`:

| Scene | Central motion | Motion→still |
|---|---:|---:|
| Bistro | +1.248512 | +0.981529 |
| Minecraft | +0.928726 | +0.307709 |

Document kernel에서는 Pattern Off가 두 구간과 두 장면 모두 높다. Standard와 달리
Pattern On의 transition 이점이 재현되지 않았다.

### 7.3 같은 pattern에서 kernel 효과

| Scene | Window | Document − Standard |
|---|---|---:|
| Bistro | Pattern On, central | +1.102249 |
| Bistro | Pattern On, motion→still | -1.361420 |
| Minecraft | Pattern On, central | +0.566711 |
| Minecraft | Pattern On, motion→still | -1.118446 |
| Bistro | Pattern Off, central | +0.088524 |
| Bistro | Pattern Off, motion→still | +0.297821 |
| Minecraft | Pattern Off, central | +0.017540 |
| Minecraft | Pattern Off, motion→still | +0.217339 |

Pattern Off에서는 document kernel이 Standard kernel보다 두 구간 모두 소폭 높다. 반면
Pattern On에서는 central motion은 개선하지만 transition은 크게 악화한다. 따라서
sample pattern 효과는 temporal kernel과 독립적이지 않다.

## 8. Spatial-reference 및 정지 plateau 보조 결과

동일 pose spatial-reference RGB MAE도 Document Off가 Document On보다 낮았다.

| Scene | Window | Document Off − On RGB MAE |
|---|---|---:|
| Bistro | central motion | -0.314563 |
| Bistro | motion→still | -0.170662 |
| Minecraft | central motion | -0.167869 |
| Minecraft | motion→still | -0.093656 |

후기 정지 frame 420~479의 temporal-delta residual은 다음과 같다.

| Scene | Standard On | Document On | Document Off | Edge Off |
|---|---:|---:|---:|---:|
| Bistro | 0.006888 | 0.649936 | 0.002778 | 0.001521 |
| Minecraft | 0.004612 | 0.583506 | 0.004408 | 0.002654 |

Document Pattern-On은 카메라가 멈춘 뒤에도 큰 2-phase 변화가 남는 신호를 보였다.
현재 결과만으로 Catmull-Rom, clipping, weight 0.8 중 어느 요소가 원인이라고 단정하지
않는다.

## 9. 결론

1. paired SMAA T2X sample pattern의 효과는 temporal kernel에 따라 달라진다.
2. Standard kernel에서는 Pattern On이 motion→still 품질을 높였지만, 현재 document
   kernel에서는 같은 이점이 사라지고 두 장면 모두 악화됐다.
3. 따라서 `O-ET2X-R`의 transition 손실을 해결하기 위해 document profile에 sample
   pattern을 단순히 다시 켜는 방식은 채택하지 않는다.
4. edge-selective Pattern-On을 기존 bilinear DeJitter와 결합한 결과도 공정한 대조군이
   아니므로 만들지 않는다.
5. 다음 gate는 full-screen에서 Pattern On/Off 각각에 Catmull-Rom, YCoCg clipping,
   history weight 0.8을 한 단계씩 추가하는 2×4 component ladder다. 이를 통해 transition
   반전과 정지 plateau 변화의 최초 발생 지점을 찾은 뒤에만 개선식을 설계한다.

## 10. 결과 경로

- Bistro capture:
  `D:/SMAA-Research-Data/AutoBench/20260902_122510`
- Minecraft capture:
  `D:/SMAA-Research-Data/AutoBench/20260902_123040`
- spatial/reference analysis:
  `D:/SMAA-Research-Data/AutoBench/20260902_DocumentSamplePatternInteraction/Analysis`
- Document Pattern-On CGVQM:
  `D:/SMAA-Research-Data/AutoBench/20260902_DocumentSamplePatternInteraction/CGVQM-DocumentPatternOn`
- integrated CGVQM analysis:
  `D:/SMAA-Research-Data/AutoBench/20260902_DocumentSamplePatternInteraction/CGVQM-Analysis`
