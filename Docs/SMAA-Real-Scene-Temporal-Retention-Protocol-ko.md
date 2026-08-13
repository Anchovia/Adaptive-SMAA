# 실제 장면 SMAA temporal 유지율 선행 검증

## 목적

Current-edge dilation을 추가하기 전에 현재 edge-selective 구현이 Standard T2X의 history를
실제로 얼마나 화면에 반영하고, temporal 안정화 효과를 얼마나 유지하는지 분리 측정한다.
이 결과 없이 dilation을 먼저 구현하면 얇은 형상 복구와 단순 temporal coverage 증가,
고스팅 증가를 구분하기 어렵다.

## 장면 분류

| 장면 | 용도 |
|---|---|
| Bistro | 저대비 정식 실제 장면 |
| Minecraft Lost Empire | 고대비 정식 실제 장면 |
| San Miguel 2.1 | texture/alpha geometry가 있는 보조 실제 장면 후보. 렌더링·ROI·reference 적합성 검증 뒤 정식 승격 |
| 절차적 thin-lines/rotor/occluder | 변수 통제 및 회귀 확인용 engineering stress만 허용 |
| UNC Power Plant 현재 경로 | loader/scene-selection engineering만 허용. 불완전한 재질·조명 때문에 정식 품질 근거에서 제외 |

## 비교 matrix

| ID | 의미 |
|---|---|
| `O-1X` | temporal history가 없는 공간 기준선 |
| `O-T2X-R` | full-screen Standard T2X + camera reprojection 기준선 |
| `ABL-Candidate-Jitter-R` | Standard jitter를 유지하고 candidate 픽셀에만 temporal resolve |
| `ABL-Candidate-NoJitter-R` | candidate-only에서 deliberate projection jitter만 제거 |
| `O-ET2X-R-Document` | Intel 공개 문서 기반 조립 profile: no deliberate jitter, Catmull-Rom, YCoCg clipping, weight 0.8 |

이 matrix에는 dilation이 없다. Candidate-Jitter와 Candidate-NoJitter의 차이로 projection
jitter의 영향부터 분리하고, 최종 document profile과의 차이로 sampling/clipping/weight의
누적 영향을 확인한다.

## 캡처

새 명령은 다음과 같다.

```powershell
./CMAA2.exe -smaaRealSceneTemporalRetentionCapture `
  "<bistro|minecraft|sanmiguel> <camera-profile> [firstProfileFrame] [captureFrames] [warmupFrames]"
```

Power Plant는 이 명령에서 의도적으로 거부한다. 각 실행은 한 fresh CMAA2 process로 시작하고
정상 종료 후 잔류 CMAA2 process가 0개여야 한다.

같은 범위를 두 번 캡처한다.

1. 일반 final 출력
2. `-smaaTemporalDebugView 3`을 지정한 `CurrentSpatial` 출력

Standard T2X에서도 debug view 3은 temporal resolve 직전 spatial T2X를 출력하되 정상
history feedback과 ping-pong은 계속 수행한다. Edge-selective mode에서는 candidate resolve
직전 spatial input을 출력한다.

## 분석

`Tools/SMAA/analyze_real_scene_temporal_retention.py`는 두 capture를 같은 frame index로
검증하고 다음을 기록한다.

- `final - CurrentSpatial` RGB MAE
- final과 spatial이 1/255, 2/255, 8/255보다 크게 다른 화면 픽셀 비율
- O-1X same-frame 출력과의 거리
- 인접 frame luma 변화 및 2차 시간 차분
- O-1X에서 한 번 구해 모든 mode에 공통 적용한 Farneback optical-flow aligned residual
- O-1X→O-T2X-R 감소분을 100%로 둔 보조 temporal 안정화 유지율

`final - CurrentSpatial`은 화면에 실제 나타난 history 영향의 대용값이다. history sample과
현재 색이 같은 픽셀에서는 history가 적용돼도 차이가 0일 수 있으므로 정확한 shader sample
count나 history 적용률로 표현하지 않는다. Optical-flow aligned residual도 blur가 작게 만들
수 있으므로 단독 품질 순위가 아니다. 기존 CGVQM/reference/error-map 및 대표 연속 프레임과
함께 해석한다.

## 의사결정

1. Candidate-Jitter가 Standard의 안정화와 출력 기여를 유지하는데 NoJitter/document
   profile에서 급감하면 temporal 손실의 주원인은 edge mask보다 jitter 제거 쪽이다.
2. Candidate-Jitter부터 Standard 대비 크게 떨어지면 candidate coverage 자체가 temporal
   sampling을 과도하게 제한한다.
3. 실제 장면에서 얇은 구조의 미복구가 확인될 때만 current-edge dilation을 진행한다.
4. 의미 있는 고스팅이 없고 얇은 구조 복구 문제도 관측되지 않으면 previous-edge dilation과
   current-edge dilation을 불필요하게 추가하지 않는다.
5. Dilation을 진행하면 3×3/5×5/7×7과 filtered downsample-upsample을 독립 ablation하고,
   품질·고스팅·temporal 유지·candidate 수·GPU 시간을 모두 측정한다.
