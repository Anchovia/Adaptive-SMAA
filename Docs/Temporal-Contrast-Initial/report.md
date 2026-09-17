# Current-color contrast T2X: initial results

원본 T2X-R에서 현재 색상만으로 대비를 근사해 history 접근 전에 처리 여부를 결정한 실험이다.
설계·실행 도구·실패 수정 사항은 [구현 문서](../SMAA-Temporal-Contrast-Experiment-ko.md)를 따른다.

이번 구현은 현재 색상의 공간 대비 근사로 velocity/history 읽기를 생략한다.
시험한 0.005/0.01/0.02에서 전체 SMAA 시간은 Bistro에서 2.53~4.41% 감소하고 Minecraft에서 1.21~2.27% 증가했다.
추가 edge texture와 pass 없이 구현했지만, 시험한 threshold 모두 정지 후 2-frame 교대 변화를 남겼다.
따라서 속도 결과와 별개로 품질 유지 조건은 아직 통과하지 못했다.

## 검증 범위

- RTX 3060 Ti, DirectX 11, Original SMAA Ultra, camera reprojection On, paired jitter 유지.
- 1920×1061, hidden window, VSync Off. 각 장면의 두 방식은 같은 바이너리와 카메라 경로를 사용했다.
- 두 장면 × 9 mode × 240 PNG를 검사했다. 원본 반복 및 All/None 경계 출력이 일치했고, threshold 0.01의 선택/생략 pixel 의미 검증도 통과했다.
- 기존 native shader 8종의 DXBC가 원본 기준점과 같다. 추가 edge texture/list/pass 없음.
- 성능: 설정별 300 warm-up + 4,800 frame × 3회, 정방향/역방향/정방향. 캡처·영상 분석과 분리.
- 아래 변화율은 해당 장면의 동일 실행 native control 대비다. 이전 branch의 절댓값과 비교하지 않는다.

## 전체 SMAA와 resolve 시간

| Scene | Mode | SMAA ms | SMAA 변화 | Resolve ms | Resolve 변화 |
|---|---|---:|---:|---:|---:|
| bistro | O-T2X-R | 0.208283 | +0.000% | 0.033272 | +0.000% |
| bistro | ABL-Contrast-All-R | 0.219084 | +5.185% | 0.043478 | +30.674% |
| bistro | ABL-Contrast-0005-R | 0.203005 | -2.534% | 0.027325 | -17.874% |
| bistro | ABL-Contrast-001-R | 0.200905 | -3.542% | 0.025144 | -24.430% |
| bistro | ABL-Contrast-002-R | 0.199094 | -4.412% | 0.023208 | -30.248% |
| bistro | ABL-Contrast-None-R | 0.195759 | -6.013% | 0.019917 | -40.138% |
| minecraft | O-T2X-R | 0.280306 | +0.000% | 0.034677 | +0.000% |
| minecraft | ABL-Contrast-All-R | 0.290542 | +3.652% | 0.044020 | +26.942% |
| minecraft | ABL-Contrast-0005-R | 0.286679 | +2.274% | 0.040262 | +16.106% |
| minecraft | ABL-Contrast-001-R | 0.285306 | +1.784% | 0.038632 | +11.405% |
| minecraft | ABL-Contrast-002-R | 0.283696 | +1.209% | 0.037120 | +7.043% |
| minecraft | ABL-Contrast-None-R | 0.267823 | -4.453% | 0.020948 | -39.592% |

## 반복 분산과 공간 처리 control

run 평균 3개의 표본 표준편차다. 별도 통계적 유의성 검정을 주장하지 않는다.

| Scene | Mode | SMAA run SD ms | Spatial ms | Spatial 변화 |
|---|---|---:|---:|---:|
| bistro | ABL-Contrast-0005-R | 0.000612 | 0.152190 | +0.412% |
| bistro | ABL-Contrast-001-R | 0.000532 | 0.152264 | +0.461% |
| bistro | ABL-Contrast-002-R | 0.000253 | 0.152372 | +0.531% |
| bistro | ABL-Contrast-All-R | 0.001065 | 0.152118 | +0.364% |
| bistro | ABL-Contrast-None-R | 0.000105 | 0.152328 | +0.502% |
| bistro | O-T2X-R | 0.002079 | 0.151566 | +0.000% |
| minecraft | ABL-Contrast-0005-R | 0.001929 | 0.222962 | +0.338% |
| minecraft | ABL-Contrast-001-R | 0.001363 | 0.223228 | +0.458% |
| minecraft | ABL-Contrast-002-R | 0.001013 | 0.223124 | +0.410% |
| minecraft | ABL-Contrast-All-R | 0.001907 | 0.223082 | +0.392% |
| minecraft | ABL-Contrast-None-R | 0.001096 | 0.223403 | +0.536% |
| minecraft | O-T2X-R | 0.003500 | 0.222212 | +0.000% |

## 정지 후 안정성과 선택 비율

후기 정지 frame 200~239의 화면 luma Δ1이며 단위는 0~255 brightness level이다. 낮은 시간 변화만으로 전반적 품질 우위를 단정하지 않는다.

| Scene | Mode | 후기 정지 luma Δ1 | 서로 다른 출력 수 | 2-frame 간격 일치 / 38 |
|---|---|---:|---:|---:|
| bistro | O-T2X-R | 0.000000 | 1 | 38 |
| bistro | ABL-Contrast-All-R | 0.000000 | 1 | 38 |
| bistro | ABL-Contrast-0005-R | 1.059022 | 2 | 38 |
| bistro | ABL-Contrast-001-R | 1.205930 | 2 | 38 |
| bistro | ABL-Contrast-002-R | 1.285092 | 2 | 38 |
| bistro | ABL-Contrast-None-R | 1.520377 | 2 | 38 |
| minecraft | O-T2X-R | 0.000000 | 1 | 38 |
| minecraft | ABL-Contrast-All-R | 0.000000 | 1 | 38 |
| minecraft | ABL-Contrast-0005-R | 0.242194 | 2 | 38 |
| minecraft | ABL-Contrast-001-R | 0.556121 | 2 | 38 |
| minecraft | ABL-Contrast-002-R | 1.214969 | 2 | 38 |
| minecraft | ABL-Contrast-None-R | 5.294130 | 2 | 38 |

- bistro, threshold 0.01: 평균 1.512%, 범위 1.307~1.718% 선택.

- minecraft, threshold 0.01: 평균 50.449%, 범위 19.370~72.404% 선택.

## 해석과 제한

- 두 장면의 native와 All control은 후기 정지에 안정됐다. 시험한 세 대비 threshold는 두 출력이 번갈아 나오는 변화를 남겼다. 현재 구현을 품질 유지가 입증된 최종 개선안으로 채택하지 않는다.
- GPU 선택률은 threshold 0.01만 별도 mask로 측정했다. 다른 threshold의 선택률을 역산하지 않는다.
- 동일한 절대 linear-luma threshold도 장면의 밝기·질감에 따라 선택률이 크게 달라진다.
- 속도는 표의 실제 측정치로 판단한다. static 교대 변화는 확인됐지만 absolute ghosting, reference 품질, 사용자 지각 임계값은 측정하지 않았다.
- 카메라 경로는 초기 baseline의 flythrough를 두 장면에 공통 적용했다. Bistro는 어두운 외부 장면, Minecraft는 근거리 구조물과 텍스처가 포함된 경로다. 대표적인 모든 게임 장면으로 일반화하지 않는다.
- raw PNG/CSV는 실행별 AutoBench 폴더에, 분석 CSV와 3배 느린 후기 정지 GIF는 `Projects/CMAA2/AutoBench/ContrastAnalysis/<scene>`에 보존했다.
- 최초 jitter 불일치 캡처와 종료 실패 process는 정상 실행으로 세지 않는다. Minecraft 정상 재실행 PNG 2160개와 cached 분석 입력의 완전 일치를 확인한 뒤 계산 결과만 재사용했다.
- 이 실험은 최종 8-case 설정이나 기존 Adaptive/ET2X 결과를 변경하지 않는다.

## Threshold 0.01의 속도 해석

- bistro: resolve 0.033272 → 0.025144 ms (-24.430%), 전체 SMAA 0.208283 → 0.200905 ms (-3.542%).
- minecraft: resolve 0.034677 → 0.038632 ms (+11.405%), 전체 SMAA 0.280306 → 0.285306 ms (+1.784%).

전체 SMAA에는 공간 처리와 공통 부대 비용이 남으므로 resolve 절감률을 전체 AA 절감률로 표현하지 않는다.
모두 선택하는 All control은 추가 대비 판단을 포함한 실험 경로의 오버헤드를 보여준다.
선택률만으로 속도를 예측하지 않고, 장면별 측정치와 반복 분산을 함께 해석한다.
Bistro 첫 native run의 spatial 시간은 후속 run보다 낮았다. 모든 run을 포함해 보고했으며
관측된 시간 차이를 통계적 유의성이나 모든 GPU에서의 개선으로 일반화하지 않는다.

후속 검토에서는 global jitter를 유지한 픽셀에서 temporal 결합을 생략하는 영향과
대비 판정 자체의 프레임별 변화 영향을 분리해야 한다. 현재 데이터만으로 두 원인의 기여도를 단정하지 않는다.
