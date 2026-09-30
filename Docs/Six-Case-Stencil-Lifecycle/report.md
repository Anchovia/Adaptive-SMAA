# Stencil 초기화 수정 후 여섯 구성 재검증

여섯 구성을 기존 검증 커밋에서 각각 새 브랜치로 분리했다. SMAA 공간 처리의 전용 stencil 초기화 누락을 수정하고, 이미 초기화하던 ⑤·⑥에는 중복 호출을 넣지 않았다. ①·③은 수정 코드를 포함하지만 사용하지 않는 SMAA stencil을 초기화하지 않는다. 기존 브랜치와 측정 자료는 그대로 보존했다.

이 수정은 Intel CMAA2 데모의 SMAA 통합 누락을 보완한 것이다. SMAA 자체의 새 알고리즘이나 temporal 선택의 개선 효과로 계산하지 않는다. [Intel wrapper](https://github.com/GameTechDev/CMAA2/blob/071c6b0857559f4e36f614362e6d2aab1b61938a/Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp#L270), [SMAA 저자 데모의 초기화](https://github.com/iryoku/smaa/blob/71c806a838bdd7d517df19192a20f0c61b3ca29d/Demo/DX10/Code/Demo.cpp#L601).

① Minecraft 성능 실행 중 시작 단계 멈춤 2건은 제외했다. 시작 장면을 요청 장면으로 맞춘 같은 바이너리의 재실행이 정상 완료됐으며, 그 결과만 채택했다. 내부 멈춤 원인까지 확정한 것은 아니다. 제외 기록은 case1/excluded-startup-stalls.json에 보존했다.

## 검증 조건

- Release x64, DX11, RTX 3060 Ti, SMAA Ultra, 1920×1061, VSync Off, hidden.
- Bistro/Minecraft, fixed 60 Hz, 정지 60 / 이동 120 / 정지 60 프레임.
- 캡처와 성능은 독립 프로세스. 실행 전후 CMAA2 잔류 프로세스 0, timeout 적용.
- 성능: 30초 사전 실행, mode별 300 warm-up, 4,800프레임×6회, mode 순서 교차. PNG·후보 및 실행 통계 진단 readback Off, GPU timestamp 계측 유지.
- 각 branch의 기존 shader와 lookup 데이터는 변경하지 않았다.
- ③은 동일 temporal-only 구현을 공통 프레임 시작/종료 수정 c51ca28 위로 옮긴 기존 eb5117c에서 분기했다.

## 출력 및 품질

여섯 구성 모두 두 장면의 240프레임 전체 RGB가 이전 해당 구성과 일치했다. 같은 캡처 실행에서 리소스와 history를 초기화한 뒤 반복한 출력도 일치했다. ④ 대조군의 RGB도 모든 브랜치에서 동일했다. 따라서 기존 CGVQM-2 점수를 재사용한다. 모델을 다시 실행한 결과가 아니며 품질이 개선됐다는 주장도 아니다.

| 구성 | Bistro 이동 | Bistro 전환 | Minecraft 이동 | Minecraft 전환 |
|---|---:|---:|---:|---:|
| ① AA-Off | 95.8146 | 95.5780 | 95.3416 | 94.9866 |
| ② SMAA 1X | 96.0628 | 95.8746 | 95.1725 | 94.9164 |
| ③ Temporal-only | 96.2490 | 96.7925 | 95.0927 | 96.2164 |
| ④ SMAA T2X-R | 96.1912 | 96.7193 | 93.9114 | 94.9057 |
| ⑤ Edge temporal-only | 96.0332 | 95.6477 | 95.4060 | 94.9690 |
| ⑥ SMAA + edge temporal | 96.1734 | 95.9116 | 95.2341 | 94.8942 |

점수는 높을수록 좋다. 이동=60~179, 전환=160~219. Supersample spatial reference 기반으로, 절대 고스팅 ground truth가 아니다. ③·④는 원본 paired pattern On, ⑤·⑥은 Off이므로 품질 차이를 모두 edge 선택 효과로 해석하지 않는다.

## 전체 AA GPU 시간

변화율은 **각 브랜치의 같은 실행에서 측정한 수정된 ④** 대비다. 아래 ④ 행의 절대값을 모든 행의 공통 분모로 사용하지 않는다. 각 실행의 분모와 반복별 변화율은 summary.json 및 case별 benchmark.json에 기록했다. 음수는 시간 감소다.

| 구성 | Bistro ms | 같은 실행 ④ ms | ④ 대비 | Minecraft ms | 같은 실행 ④ ms | ④ 대비 |
|---|---:|---:|---:|---:|---:|---:|
| ① AA-Off | 0.000000 | 0.157567 | -100.00% | 0.000000 | 0.226484 | -100.00% |
| ② SMAA 1X | 0.093239 | 0.157383 | -40.76% | 0.159555 | 0.227371 | -29.83% |
| ③ Temporal-only | 0.079834 | 0.158056 | -49.49% | 0.082369 | 0.227452 | -63.79% |
| ④ SMAA T2X-R | 0.159045 | 0.159045 | +0.00% | 0.227015 | 0.227015 | +0.00% |
| ⑤ Edge temporal-only | 0.097097 | 0.157625 | -38.40% | 0.117412 | 0.233494 | -49.72% |
| ⑥ SMAA + edge temporal | 0.139708 | 0.163778 | -14.70% | 0.223577 | 0.233375 | -4.20% |

①은 AA 처리가 없어 0으로 표기한다. 초기화 비용은 전체 AA 시간에 포함한다. 전체 프레임/FPS 개선율과 동일하지 않다.

## Temporal resolve GPU 시간

| 구성 | Bistro ms | 같은 실행 ④ ms | ④ 대비 | Minecraft ms | 같은 실행 ④ ms | ④ 대비 |
|---|---:|---:|---:|---:|---:|---:|
| ③ Temporal-only | 0.033892 | 0.033756 | +0.40% | 0.035185 | 0.035042 | +0.41% |
| ④ SMAA T2X-R | 0.033570 | 0.033570 | +0.00% | 0.034963 | 0.034963 | +0.00% |
| ⑤ Edge temporal-only | 0.007269 | 0.033564 | -78.34% | 0.023548 | 0.035888 | -34.39% |
| ⑥ SMAA + edge temporal | 0.007627 | 0.034289 | -77.76% | 0.023746 | 0.035728 | -33.54% |

Resolve에는 camera velocity 생성이나 입력 준비·공간 처리가 포함되지 않으며, 그 비용은 전체 AA에 포함된다. ⑤·⑥은 기존 early-stencil 경로를 유지하고 비선택 픽셀의 temporal shader 실행을 막는다. 전체 AA 감소율과 resolve 감소율을 구분해야 한다.

## 브랜치와 결과 해석

- ① AA-Off: `baseline/aa-off-stencil-lifecycle` / `eb1d05a44eb7f0995fa811ab4352cd6d42d15ab4`
- ② SMAA 1X: `baseline/smaa-1x-stencil-lifecycle` / `15fb796bac3be602ba88727a4593f9fcc033088d`
- ③ Temporal-only: `baseline/temporal-only-stencil-lifecycle` / `3274633951d07a752c8d20e03a47fe1cd6b11461`
- ④ SMAA T2X-R: `baseline/smaa-t2x-r-stencil-lifecycle` / `8a08824dbf9ed17dc09d0d306336718f422ee9ad`
- ⑤ Edge temporal-only: `experiment/first-edge-temporal-only-stencil-lifecycle` / `0b4191407b340bdcaab207b7f8b3f1b872731b71`
- ⑥ SMAA + edge temporal: `experiment/spatial-first-edge-stencil-lifecycle` / `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459`

기존 초기화 누락 기준선으로 계산한 개선율은 과거 실행 조건의 기록으로 보존하고, 이후 성능 비교는 이번 수정 기준선을 사용한다. 이번 측정은 여섯 control의 재정비이며 최종 Original/Adaptive 8-case 연구 완료를 의미하지 않는다.
