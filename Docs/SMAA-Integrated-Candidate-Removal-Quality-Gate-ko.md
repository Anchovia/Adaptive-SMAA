# SMAA Integrated Candidate Removal 품질 Gate

## 1. 목적

이 실험은 SMAA 1차 edge pass에 통합한 `IntelFamilyNonDominant` candidate 정책의
non-dominant removal 값을 선별하기 위한 engineering quality gate다. Intel 공개
기본값 `0.50`과 앞선 0.05 간격 count sweep에서 약 50% 후보 영역에 들어온
`0.65`, `0.70`, `0.75`를 동일 조건으로 비교했다.

이 결과는 최종 8-case 품질 결과나 공식 TSCMAA 최적값이 아니다. 공개되지 않은 Intel
원본 candidate 식을 복원한 것도 아니며, 현재 SMAA adaptation의 파라미터 연구다.

## 2. 구현 및 비교 조건

새 자동 캡처 명령은 다음 여섯 출력을 같은 실행에서 순회한다.

```text
O-1X
O-T2X-R
O-ET2X-R [removal=0.50]
O-ET2X-R [removal=0.65]
O-ET2X-R [removal=0.70]
O-ET2X-R [removal=0.75]
```

명령:

```powershell
CMAA2.exe -smaaIntegratedCandidateRemovalQualityCapture <bistro|minecraft> flythrough-wide-yaw-360 150 60 60
```

네 `O-ET2X-R` variant는 removal 이외의 설정을 동일하게 고정했다.

- candidate source: `SMAAFirstPassIntegratedCandidates`
- candidate policy: `IntelFamilyNonDominant`
- edge threshold: `1/22`
- candidate expansion: None
- camera/depth reprojection On; object motion vector 미연결
- deliberate projection jitter Off
- Catmull-Rom 5-tap history sampling
- YCoCg variance clipping
- history weight `0.8`
- DirectX 11, SMAA Ultra, 1920×1017, VSync Off
- `flythrough-wide-yaw-360` profile frame 150~209, fixed 60 Hz
- mode별 첫 capture pose에서 60-frame warm-up 후 60-frame 저장

분석기는 각 mode의 연속 frame·해상도·profile index를 검증하고 동일 pose의 3×3
subpixel/8×MSAA supersample spatial reference와 RGB MAE, PSNR, luma SSIM,
edge strength를 비교한다. O-1X same-frame 거리, adjacent-frame MAE와 2차 시간 차분도
기록한다. adjacent/2차 차분은 optical-flow 정렬이 없으므로 장면 motion을 포함하는 상대
지표다.

## 3. 실행 및 회귀 검증

- Release x64 빌드 PASS
- 3-frame Bistro smoke: 6 mode 모두 연속·고유 PNG, 분석기 PASS
- Bistro 60-frame clean-process capture PASS, 종료 후 잔류 `CMAA2.exe` 0
- Minecraft 60-frame clean-process capture PASS, 종료 후 잔류 `CMAA2.exe` 0
- 대표 비교 시트에서 화면 전체 떨림, 검은 화면, 깨진 reprojection과 새로운 큰 잔상 없음
- 새 O-1X와 기존 full-profile wide capture의 SHA-256: 두 장면 모두 60/60 일치
- 새 O-T2X-R은 첫 pose warm-up의 history 조건 때문에 기존 연속 profile과 각 장면의
  첫 2 frame만 다르고, 이후 58/58 frame은 일치

마지막 항목은 알고리즘 회귀가 아니라 subset 실행이 profile frame 150 pose에서 정지
warm-up한 뒤 시작하는 데 따른 history 초기 조건 차이다. 따라서 이 자료는 parameter
screening용 engineering subset으로만 사용하고, 최종 품질 측정은 전체 timeline 또는
동일한 history pre-roll 조건으로 수행해야 한다.

## 4. 품질 결과

### 4.1 Bistro 저대비 장면

| Mode | Ref RGB MAE ↓ | PSNR ↑ | Luma SSIM ↑ | Edge/ref | O-1X 거리 | Adjacent MAE | 2차 시간 차분 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `O-1X` | 1.571406 | 35.6924 | 0.981582 | 1.007214 | 0.000000 | 24.884706 | 42.336338 |
| `O-T2X-R` | 2.423022 | 32.4482 | 0.963600 | 0.966193 | 2.467350 | 24.522591 | 41.630218 |
| `O-ET2X-R 0.50` | 1.680457 | 35.1628 | 0.979196 | 0.975697 | 0.563346 | 24.590651 | 41.754224 |
| `O-ET2X-R 0.65` | 1.673516 | 35.1957 | 0.979357 | 0.977737 | 0.520945 | 24.608345 | 41.787457 |
| `O-ET2X-R 0.70` | 1.670591 | 35.2094 | 0.979421 | 0.978524 | 0.505087 | 24.614771 | 41.799824 |
| `O-ET2X-R 0.75` | 1.666423 | 35.2283 | 0.979517 | 0.979593 | 0.484700 | 24.623204 | 41.816102 |

`0.50→0.75`에서 reference MAE는 0.835% 감소했지만 O-1X와의 거리는 13.960%
감소했다. Adjacent MAE와 2차 시간 차분은 각각 0.132%, 0.148% 증가했다.

### 4.2 Minecraft 고대비 장면

| Mode | Ref RGB MAE ↓ | PSNR ↑ | Luma SSIM ↑ | Edge/ref | O-1X 거리 | Adjacent MAE | 2차 시간 차분 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `O-1X` | 0.704006 | 36.2155 | 0.987316 | 1.015132 | 0.000000 | 8.237256 | 14.377065 |
| `O-T2X-R` | 1.057942 | 35.1195 | 0.977870 | 0.968213 | 1.073272 | 8.106539 | 14.042110 |
| `O-ET2X-R 0.50` | 0.708865 | 36.5067 | 0.986653 | 0.974120 | 0.252765 | 8.147740 | 14.082375 |
| `O-ET2X-R 0.65` | 0.707463 | 36.4884 | 0.986755 | 0.978938 | 0.222621 | 8.162216 | 14.112880 |
| `O-ET2X-R 0.70` | 0.707005 | 36.4825 | 0.986793 | 0.980931 | 0.210549 | 8.168014 | 14.126008 |
| `O-ET2X-R 0.75` | 0.706717 | 36.4723 | 0.986838 | 0.983351 | 0.196058 | 8.174630 | 14.142194 |

`0.50→0.75`에서 reference MAE는 0.303% 감소했지만 O-1X와의 거리는 22.435%
감소했다. Adjacent MAE와 2차 시간 차분은 각각 0.330%, 0.425% 증가했다.

## 5. Candidate 비율과 함께 본 해석

앞선 동일 integrated core 고정-pose count sweep 결과는 다음과 같다.

| Removal | Bistro candidate/base | Minecraft candidate/base |
|---:|---:|---:|
| 0.50 | 57.417% | 62.766% |
| 0.65 | 52.759% | 52.945% |
| 0.70 | 51.351% | 49.745% |
| 0.75 | 49.561% | 46.063% |

두 장면에서 removal이 커질수록 같은 방향의 trade-off가 나타났다.

- spatial reference 오차와 edge/reference 비율은 소폭 개선됐다.
- 동시에 출력이 O-1X에 더 가까워지고 시간 변화량이 소폭 증가했다.
- 따라서 높은 removal의 선명도 증가는 history 적용 감소에 따른 1X 회귀를 일부 포함할
  수 있으며, ghosting 개선이나 temporal supersampling 향상으로 단정할 수 없다.
- `0.70`은 두 장면 모두 candidate/base가 약 50%이고 큰 품질 artifact가 없어 장면 공통
  robust 중심 후보로 가장 타당하다.
- `0.50`은 Intel 공개 기본값이므로 반드시 control로 유지한다.
- `0.65`와 `0.75`는 비용·품질 trend 및 선택 편향을 확인하는 양쪽 bracket으로 보존한다.

## 6. Gate 판정과 다음 작업

네 removal 값 모두 engineering 품질 gate를 통과했다. 작은 차이를 근거로 일부 값을
사후 제거하면 cherry-picking 위험이 있으므로 다음 readback-Off 반복 성능에는 네 값을
모두 유지한다. 단, 사전에 다음 역할을 명시한다.

- 공개 control: `0.50`
- 장면 공통 robust 중심 후보: `0.70`
- bracket ablation: `0.65`, `0.75`

다음 단계는 Bistro/Minecraft에서 PNG와 candidate readback을 끄고 동일 순서 교차,
300-frame warm-up, 4,800-frame 측정, 최소 3회 반복으로 integrated `O-ET2X`와
`O-ET2X-R`의 네 removal 값을 측정하는 것이다. candidate count는 별도의 readback-On
특성화 결과와 연결한다. 성능 결과 뒤에는 전체 timeline 품질과 CGVQM-2를 사용해
`0.50` 대 `0.70` 중심의 최종 검증을 수행한다.

## 7. 산출물

- Bistro capture: `D:/SMAA-Research-Data/AutoBench/20260828_004354`
- Minecraft capture: `D:/SMAA-Research-Data/AutoBench/20260828_004454`
- 분석: `D:/SMAA-Research-Data/AutoBench/20260828_IntegratedCandidateRemovalQualityGate/Analysis`
- 재현 가능한 분석기: `Tools/SMAA/analyze_integrated_candidate_removal_quality.py`
