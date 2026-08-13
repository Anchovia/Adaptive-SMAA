# 실제 장면 SMAA temporal 유지율 선행 측정 결과

## 1. 결론

Current-edge dilation을 구현하기 전에 현재 edge-selective 경로의 temporal 동작을 실제
장면에서 분해했다. 이번 결과는 다음을 보여준다.

1. Candidate-only 경로가 history를 전혀 사용하지 않는 것은 아니다.
2. Candidate-Jitter는 O-1X와의 same-frame 출력 거리를 Standard `O-T2X-R` 대비
   Bistro 94.07%, Minecraft 91.48% 유지했다.
3. 같은 candidate 정책에서 deliberate projection jitter만 끄면 이 값이 Bistro 14.10%,
   Minecraft 14.57%로 급감했다.
4. `O-ET2X-R-Document`도 각각 19.30%, 19.73%로 O-1X에 가까웠다.
5. Candidate mask 내부에서는 NoJitter/document profile도 `final - CurrentSpatial` 차이가
   남았다. 즉 제한된 후보에서는 history가 실제 화면에 반영되지만, 전역 temporal sample
   diversity를 제거한 결과 전체 출력 효과가 크게 줄었다고 해석하는 것이 타당하다.

따라서 현재 temporal 손실을 candidate selection 하나의 문제로 단정하면 안 된다. 세
장면에서 재현된 핵심 분기점은 candidate mask 존재보다 deliberate projection jitter의
On/Off였다. Dilation은 얇은 선 주변의 temporal 후보 coverage를 늘릴 수 있지만, jitter가
없는 현재 document profile의 근본적인 temporal supersampling 손실을 혼자 복구한다고
가정할 수 없다.

## 2. 측정 범위

- GPU: RTX 3060 Ti
- API/preset: DirectX 11, SMAA Ultra
- 해상도: 1920×1017
- profile: `yaw-fast-360`의 실제 360° 회전 frame 60~119
- mode별 warm-up: 첫 회전 pose에서 60 frame
- mode별 저장: 60 frame
- 각 final/spatial/mask capture는 별도 fresh CMAA2 process
- 모든 실행의 종료 후 잔류 CMAA2 process: 0
- current-edge dilation: 비활성화

이번 60-frame subset은 실제 회전 전체를 포함하지만 60-frame pre/post still을 포함한 완전한
180-frame profile이 아니므로 `engineering`으로 분류한다. 이전 formal CGVQM/reference
결과를 대체하지 않으며, temporal 손실 원인 분리를 위한 선행 측정이다.

## 3. 비교 구성

| ID | 구성 |
|---|---|
| `O-1X` | spatial control, history 없음 |
| `O-T2X-R` | full-screen Standard T2X + camera reprojection |
| `ABL-Candidate-Jitter-R` | candidate-only + Standard projection jitter |
| `ABL-Candidate-NoJitter-R` | candidate-only + no deliberate jitter |
| `O-ET2X-R-Document` | candidate-only + no deliberate jitter + Catmull-Rom + clipping + weight 0.8 |

각 구성에서 일반 final 출력과 `TemporalDebugView::CurrentSpatial`을 같은 frame index로
저장했다. Edge-selective mode에는 `SelectedCandidates` mask도 별도로 저장했다.

## 4. 전체 출력 기준 결과

`Standard 대비 출력 효과`는 각 mode와 O-1X의 same-frame RGB MAE를 `O-T2X-R=100%`로
정규화한 값이다. projection jitter와 history가 함께 만든 최종 출력 차이를 나타내며 정확한
history sample count는 아니다.

| Scene | Candidate-Jitter | Candidate-NoJitter | O-ET2X-R-Document |
|---|---:|---:|---:|
| Bistro | 94.07% | 14.10% | 19.30% |
| Minecraft | 91.48% | 14.57% | 19.73% |
| San Miguel | 93.06% | 18.01% | 25.02% |

San Miguel은 동일 방향을 보인 engineering 보조 장면일 뿐, 현재 diffuse+alpha 중심 renderer와
ROI/reference 적합성 검증이 끝나지 않아 정식 논문 장면으로 분류하지 않는다.

## 5. 후보 내부 관측 history 영향

Candidate mask 안에서 `final - CurrentSpatial` RGB MAE를 계산했다. 이 값은 후보 픽셀의
최종 출력에 temporal resolve가 만든 관측 차이다. history 색이 현재 색과 같으면 적용돼도
0이 될 수 있으므로 정확한 적용 횟수는 아니다.

| Scene | 후보 화면 비율 | Candidate-Jitter | Candidate-NoJitter | Document |
|---|---:|---:|---:|---:|
| Bistro | 8.718% | 6.376 | 3.771 (59.14%) | 5.172 (81.12%) |
| Minecraft | 4.639% | 6.724 | 4.422 (65.76%) | 5.996 (89.18%) |
| San Miguel | 10.394% | 10.208 | 6.929 (67.88%) | 10.279 (100.69%) |

괄호는 같은 장면 Candidate-Jitter MAE 대비 비율이다. 전체 출력이 O-1X에 가까워졌어도
후보 안의 history 영향은 완전히 사라지지 않았다. 이는 현재 구현이 “temporal resolve 자체를
수행하지 않는다”기보다 “화면의 약 5~10% 후보에만 수행하고 전역 jitter diversity도 끈다”는
설명과 일치한다.

## 6. Optical-flow 보조 지표 제한

O-1X에서 구한 공통 Farneback flow로 인접 frame을 정렬했지만 `yaw-fast-360`은 6°/frame의
급격한 회전이라 forward/backward consistency 유효 비율이 Bistro 29.73%, Minecraft
38.58%, San Miguel 46.57%에 그쳤다. 또한 Standard `O-T2X-R`의 aligned residual이
O-1X보다 항상 작지 않아 정규화 안정화 유지율은 N/A인 경우가 있었다. 따라서 이 profile의
핵심 근거는 flow 단독 순위가 아니라 다음 조합이다.

- O-1X same-frame 출력 거리
- final/CurrentSpatial 차이
- candidate mask 내부 차이
- 기존 supersample reference/CGVQM/error-map
- 대표 연속 frame 육안 검사

## 7. 결과 경로

### Bistro

- final: `D:/SMAA-Research-Data/AutoBench/20260813_200915`
- CurrentSpatial: `D:/SMAA-Research-Data/AutoBench/20260813_201003`
- candidate mask: `D:/SMAA-Research-Data/AutoBench/20260813_202432`
- analysis: `D:/SMAA-Research-Data/AutoBench/20260813_200915/TemporalRetentionAnalysis`

### Minecraft

- final: `D:/SMAA-Research-Data/AutoBench/20260813_201442`
- CurrentSpatial: `D:/SMAA-Research-Data/AutoBench/20260813_201521`
- candidate mask: `D:/SMAA-Research-Data/AutoBench/20260813_202654`
- analysis: `D:/SMAA-Research-Data/AutoBench/20260813_201442/TemporalRetentionAnalysis`

### San Miguel (`engineering`)

- final: `D:/SMAA-Research-Data/AutoBench/20260813_201733`
- CurrentSpatial: `D:/SMAA-Research-Data/AutoBench/20260813_201825`
- candidate mask: `D:/SMAA-Research-Data/AutoBench/20260813_202903`
- analysis: `D:/SMAA-Research-Data/AutoBench/20260813_201733/TemporalRetentionAnalysis`

## 8. 다음 작업 결정

1. Dilation 구현 전에 Candidate-Jitter를 기준으로 얇은 실제 형상이 끊기거나 복구되지 않는
   ROI를 Bistro/Minecraft에서 먼저 찾는다.
2. 기존 formal CGVQM/reference의 같은 frame 범위와 이번 5-way 출력을 연결해 Candidate-Jitter
   자체의 ghosting/blur trade-off를 확인한다.
3. 얇은 구조 미복구가 확인되면 current-edge 3×3 dilation을 첫 최소 구현으로 추가한다.
4. 3×3에서 효과가 확인될 때만 5×5/7×7과 filtered downsample-upsample을 확장한다.
5. Dilation은 Candidate-Jitter와 document/no-jitter profile 양쪽에 직교 적용해 edge 확장과
   jitter policy 효과를 섞지 않는다.
6. 품질 개선과 함께 candidate 비율, history 관측 영향, ghosting, flicker와 GPU 시간을 모두
   측정한다.

이 결과만으로 dilation의 성공 여부나 TSCMAA adaptation의 최종 품질 우위를 주장하지 않는다.

## 9. 후속 진행 상태

위 1~2번의 실제 장면 ROI 및 같은 frame reference/CGVQM 연결을 완료했다.

- 새 60-frame `O-1X`와 기존 formal `O-1X` frame 60~119의 SHA-256 mismatch는
  Bistro와 Minecraft 모두 0/60이었다.
- Candidate-Jitter는 CGVQM-2에서 대응 Standard보다 Bistro +0.9011점,
  Minecraft +0.3384점 높았지만 O-1X보다 각각 2.6199점, 1.4435점 낮았다.
- 실제 ROI의 offline mask 분석에서 3×3 dilation은 reference 구조 recall을 크게
  높이는 대신 후보 화면 비율을 약 2.7~3.2배 늘렸다.
- 따라서 다음 구현은 3×3 current-edge dilation 하나로 제한하고, 5×5/7×7 및 filtered
  downsample-upsample은 그 품질·성능 결과 뒤로 보류한다.

상세 수치와 해석 제한은
`Docs/SMAA-Candidate-Jitter-Real-Scene-Quality-Results-ko.md`를 기준으로 한다.
