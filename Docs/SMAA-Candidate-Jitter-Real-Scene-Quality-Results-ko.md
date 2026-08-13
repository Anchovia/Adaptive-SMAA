# Candidate-Jitter 실제 장면 품질·후보 coverage 결과

## 1. 목적

실제 장면에서 `ABL-Candidate-Jitter-R`이 Standard `O-T2X-R`의 temporal 효과를
유지하는 것과 별개로 다음을 확인했다.

1. supersample spatial reference에 대한 품질도 개선되는가
2. 실제 얇은 구조·세부 구조를 current-edge candidate가 충분히 포함하는가
3. current-edge dilation을 구현할 근거가 있는가

이번 단계는 dilation을 구현하기 전의 **engineering 선행 분석**이다. Intel 원본
TSCMAA 재현이나 dilation 적용 결과로 표현하지 않는다.

## 2. 조건과 정렬 검증

- GPU/API/preset: RTX 3060 Ti, DirectX 11, SMAA Ultra
- 해상도: 1920×1017
- 장면: 저대비 Bistro, 고대비 Minecraft Lost Empire
- 경로: `yaw-fast-360`의 실제 회전 frame 60~119
- 비교 frame: mode별 60 frame
- reference: 2× 선형 해상도, 3×3 subpixel grid, 8×MSAA spatial proxy
- current-edge dilation: 비활성화

새 5-way capture의 index 0~59는 profile frame 60~119를 뜻한다. 새 `O-1X`와 기존
formal `O-1X`의 대응 frame을 PNG SHA-256으로 비교한 결과는 다음과 같다.

| Scene | 비교 frame | SHA-256 mismatch |
|---|---:|---:|
| Bistro | 60 | 0 |
| Minecraft | 60 | 0 |

따라서 기존 supersample reference의 frame 60~119와 새 capture가 동일 pose임을
`O-1X` deterministic bridge로 확인했다. temporal mode는 warm-up/history 시작 상태가
달라질 수 있으므로 기존 capture와의 byte-identical 조건으로 정렬을 주장하지 않는다.

## 3. 비교 구성

| ID | 의미 |
|---|---|
| `O-1X` | spatial control, history 없음 |
| `O-T2X-R` | full-screen Standard T2X + camera reprojection |
| `ABL-Candidate-Jitter-R` | candidate-only + Standard projection jitter |
| `ABL-Candidate-NoJitter-R` | candidate-only + no deliberate jitter |
| `O-ET2X-R-Document` | document profile: candidate-only, no-jitter, Catmull-Rom, clipping, weight 0.8 |

`ABL-Candidate-Jitter-R`은 Intel 공식 mode가 아니라 candidate selection과 projection
jitter의 영향을 분리하기 위해 만든 연구 ablation이다.

## 4. Intel CGVQM 60-frame 결과

동일 60-frame subset을 무손실 FFV1로 변환한 뒤 Intel CGVQM-2, CUDA, patch scale 3,
mean pooling으로 평가했다. test/reference 영상의 decode 후 RGB mismatch는 모든 실행에서
0이었다.

| Mode | Bistro CGVQM-2 ↑ | Minecraft CGVQM-2 ↑ |
|---|---:|---:|
| `O-1X` | 96.917892 | 99.190315 |
| `O-T2X-R` | 93.396896 | 97.408432 |
| `ABL-Candidate-Jitter-R` | 94.298035 | 97.746803 |
| `ABL-Candidate-NoJitter-R` | 97.072746 | 99.115166 |
| `O-ET2X-R-Document` | 96.790794 | 98.917198 |

Candidate-Jitter는 Standard보다 Bistro +0.9011점, Minecraft +0.3384점 높았지만
`O-1X`보다 각각 2.6199점, 1.4435점 낮았다. 앞선 temporal 유지율 측정에서
Candidate-Jitter가 Standard 출력 효과의 90% 이상을 유지했지만, 그 temporal 영향이
이번 spatial reference fidelity의 우위로 이어지지는 않았다.

CGVQM reference는 temporal history가 없는 spatial proxy다. 따라서 이 순위를 절대적인
temporal 품질 또는 ghosting 순위로 해석하지 않고, 연속 frame·ROI·기존 camera-motion
분석과 함께 사용한다.

## 5. 실제 장면 ROI 결과

### 5.1 ROI 선정

| Scene | ROI | 실제 구조 | Frame |
|---|---|---|---:|
| Bistro | `bar_bottles` | 병 외곽, 선반, wine-rack 대각선 | 0~7 |
| Bistro | `windows_chairs` | 창살, 의자·테이블 다리, radiator, lamp arm | 26~38 |
| Minecraft | `distant_city` | 원거리 건물 silhouette와 좁은 틈 | 0~7 |
| Minecraft | `tree_ledge_silhouette` | 나뭇잎 alpha silhouette와 원거리 ledge | 23~32 |

Minecraft는 정식 고대비 장면으로는 유효하지만 실제 thin-line geometry가 적다. 따라서
Minecraft ROI는 고대비 세부 구조 보조 근거이며 전선 복구 장면으로 표현하지 않는다.

### 5.2 RGB MAE 대 spatial reference

| ROI | `O-1X` | `O-T2X-R` | Candidate-Jitter | Candidate-NoJitter | Document |
|---|---:|---:|---:|---:|---:|
| Bistro bottles | 2.4496 | 3.6003 | 3.3897 | 2.4839 | 2.6654 |
| Bistro windows/chairs | 1.3497 | 2.2326 | 2.0472 | 1.3327 | 1.4036 |
| Minecraft distant city | 1.2542 | 2.5899 | 2.5157 | 1.3815 | 1.4824 |
| Minecraft tree/ledge | 0.5379 | 0.9949 | 0.8614 | 0.5121 | 0.5455 |

네 ROI 모두 Candidate-Jitter는 Standard보다 reference MAE가 낮았지만 NoJitter와
Document보다 높았다. Candidate-Jitter의 reference 구조 영역 edge/reference 비율도
0.8712~0.9487로 `O-1X`의 0.9483~0.9886보다 낮았다. 따라서 현재 자료로
Candidate-Jitter가 실제 얇은 구조를 더 잘 복구하거나 더 선명하다고 주장할 수 없다.

## 6. Offline current-edge 확장 coverage

GPU shader를 수정하기 전에 저장된 `SelectedCandidates` mask를 offline으로 확장했다.
Reference 구조는 각 ROI의 Sobel magnitude 상위 25%이며 threshold 최솟값은 8이다.
이는 정확한 AA 필요 픽셀 ground truth가 아니라 동일 조건의 상대 coverage 지표다.

아래 표는 `ABL-Candidate-Jitter-R` mask 결과다.

| ROI | 방식 | 화면 후보 비율 | Reference 구조 recall |
|---|---|---:|---:|
| Bistro bottles | Base | 12.32% | 41.25% |
|  | 3×3 dilation | 33.37% | 88.39% |
|  | 5×5 dilation | 46.81% | 95.77% |
|  | 7×7 dilation | 56.29% | 97.87% |
|  | 1/4 filtered proxy | 20.00% | 58.98% |
| Bistro windows/chairs | Base | 8.82% | 29.78% |
|  | 3×3 dilation | 26.25% | 72.83% |
|  | 5×5 dilation | 39.18% | 85.76% |
|  | 7×7 dilation | 48.33% | 90.94% |
|  | 1/4 filtered proxy | 12.65% | 36.92% |
| Minecraft distant city | Base | 13.26% | 41.46% |
|  | 3×3 dilation | 41.98% | 93.72% |
|  | 5×5 dilation | 58.47% | 98.14% |
|  | 7×7 dilation | 68.45% | 98.85% |
|  | 1/4 filtered proxy | 20.48% | 54.39% |
| Minecraft tree/ledge | Base | 2.24% | 8.88% |
|  | 3×3 dilation | 7.11% | 26.20% |
|  | 5×5 dilation | 10.49% | 34.09% |
|  | 7×7 dilation | 13.00% | 38.34% |
|  | 1/4 filtered proxy | 2.90% | 10.89% |

3×3은 모든 ROI에서 구조 recall을 크게 높였지만 화면 후보 비율도 약 2.7~3.2배로
증가했다. 5×5와 7×7은 추가 recall 증가보다 작업량 증가가 커지는 구간이 나타났다.
1/4 filtered proxy는 area downsample, bilinear upsample, threshold 0.25라는 구현 가정을
사용했으며 현재 설정에서는 3×3보다 coverage 증가가 작았다.

이 결과는 후보 확장 시 예상 coverage와 작업량만 보여준다. 실제 temporal resolve를
실행하지 않았으므로 ghosting, flicker, 얇은 선 복구와 GPU 시간 결과가 아니다.

## 7. 결론과 다음 결정

1. Candidate-Jitter는 temporal 출력 효과를 유지하지만, 이번 실제 장면에서 O-1X나
   no-jitter/document보다 reference fidelity가 좋지 않았다.
2. current-edge base mask는 선택한 reference 구조의 상당 부분을 포함하지 않는다.
3. 3×3 dilation은 가장 작은 커널인데도 coverage 증가가 충분히 커 첫 구현 대상으로
   타당하다.
4. 5×5, 7×7과 filtered downsample-upsample은 3×3의 실제 품질 이득과 비용을 확인한
   뒤에만 진행한다.
5. 3×3은 `ABL-Candidate-Jitter-R`과 `O-ET2X-R-Document`에 직교 toggle로 적용해
   dilation 효과와 jitter policy 효과를 섞지 않는다.
6. 다음 실험에서는 후보 비율, reference/CGVQM, 연속 frame, temporal 유지율,
   camera-motion ghosting과 candidate/resolve GPU 시간을 함께 비교한다.

## 8. 산출물

### Bistro

- ROI 분석: `D:/SMAA-Research-Data/AutoBench/20260813_200915/CandidateJitterRealSceneQuality`
- CGVQM: `D:/SMAA-Research-Data/AutoBench/20260813_200915/CandidateJitterCGVQM`

### Minecraft

- ROI 분석: `D:/SMAA-Research-Data/AutoBench/20260813_201442/CandidateJitterRealSceneQuality`
- CGVQM: `D:/SMAA-Research-Data/AutoBench/20260813_201442/CandidateJitterCGVQM`

각 ROI 분석 폴더에는 frame별 CSV, JSON, 정렬 hash CSV, 비교 PNG와 GIF가 있다. 각
CGVQM mode 폴더에는 결과 JSON, frame별 error-map 통계 CSV와 검증된 무손실 입력이 있다.
