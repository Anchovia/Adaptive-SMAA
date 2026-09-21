# 선택적 결합과 지터·subsample 패턴의 분리 결과

**두 장면 모두 같은 luma 선택식을 유지한 채 표본 패턴을 끄자 정지 후 두 frame 교대가 사라졌다.** 기존 깜빡임이 paired sample pattern과 선택적 temporal 결합의 상호작용이라는 해석을 지지한다. 따라서 기존 On 결과로 선택식의 모든 조건에서의 실패를 일반화해서는 안 된다.

다만 Off는 temporal supersampling을 포기한 진단이다. 이동 구간과 정지 구간의 결과가 다르며, Off가 원본 T2X-R보다 항상 우수하거나 더 빠르다는 결론은 아니다. 기존 On의 품질 열세 측정도 그 구현의 실제 출력에 대한 유효한 결과로 남는다.

구현 commit `980c272`, 출발점 `a4c24c8`, branch `experiment/temporal-contrast-jitter-ablation`. [실험 조건·재현 방법](method.md). [Bistro 원시 요약](bistro.json), [Minecraft 원시 요약](minecraft.json).

## 실행·정확성

Release x64 빌드 후 두 장면을 각각 독립 clean process에서 캡처했다. 각 10 mode×240 frame, 총 4,800 PNG다. 실행 전후 CMAA2 process 0개와 timeout을 적용했고 두 실행 모두 정상 종료/PASS했다. 두 실행의 EXE SHA-256은 `0E8443CBC4A17B83DC9E53E71CEFF96006D7B9DC389EB7D202ADC6CF12A3C05E`다.

제출 subsample/pattern 설정 4,800 frame 검사, 기존 On control 및 Off 반복 출력의 2,880회 PNG hash 비교, 960 mode-frame의 선택/비선택 출력 검사, 첫 frame seed 8건 모두 통과했다. 이 설정 검사는 CPU 제출값 검사이며 GPU constant readback은 아니다. 원본 shader와 ScalarWeight shader의 소스는 바꾸지 않았다.

## 정지 후 변화

후기 정지 frame 200~239. RGB 변화는 전체 화면의 인접 frame 평균 절댓값 차이(0~255)다. Hash 종류 수는 40 frame의 decoded RGB 기준이며, 모든 조건에서 lag-2 비교 38쌍은 일치했다.

| 장면 | 조건 | RGB frame 종류 | 평균 RGB 변화 |
|---|---|---:|---:|
| bistro | 원본 On | 1 | 0.000000 |
| bistro | Scalar On | 2 | 1.287832 |
| bistro | Full-screen Off | 1 | 0.000000 |
| bistro | Scalar Off | 1 | 0.000000 |
| minecraft | 원본 On | 1 | 0.000000 |
| minecraft | Scalar On | 2 | 0.580355 |
| minecraft | Full-screen Off | 1 | 0.000000 |
| minecraft | Scalar Off | 1 | 0.000000 |

Off에서는 scalar의 선택 mask도 정지 후 고정된다. On에서는 같은 카메라가 정지해도 두 jitter 위상에서 입력 색상과 선택 결과가 달라진다. 다만 이것은 projection과 area subsample 설정을 함께 바꾼 결과이며 projection offset 하나만의 독립 효과로 주장하지 않는다.

## 공간 기준 오차와 시간 변화

RGB MAE와 시간 잔차는 낮을수록 해당 공간 reference에 가깝다. 시간 잔차는 reference의 frame 간 변화량을 뺀 화면 luma 차이다. 순수 ghosting 지표가 아니다. Reference는 기존 2배 선형 해상도·3×3 subpixel grid·8×MSAA의 공간 기준이며 MIP/sharpen 설정을 포함한다. 새 CGVQM이나 성능 benchmark는 실행하지 않았다.

| 장면 | 구간 | 조건 | RGB MAE | PSNR dB | 시간 잔차 |
|---|---|---|---:|---:|---:|
| bistro | 이동 | 원본 On | 0.734975 | 40.390662 | 0.802725 |
| bistro | 이동 | Scalar On | 0.947602 | 38.923882 | 1.308485 |
| bistro | 이동 | Full-screen Off | 0.697627 | 40.475451 | 0.691479 |
| bistro | 이동 | Scalar Off | 0.682249 | 40.169947 | 0.727705 |
| bistro | 전환 | 원본 On | 0.646081 | 41.218424 | 0.320920 |
| bistro | 전환 | Scalar On | 0.955614 | 39.052582 | 1.257903 |
| bistro | 전환 | Full-screen Off | 0.711191 | 39.547393 | 0.264032 |
| bistro | 전환 | Scalar Off | 0.704944 | 39.439134 | 0.268113 |
| bistro | 후기 정지 | 원본 On | 0.582826 | 41.864183 | 0.000000 |
| bistro | 후기 정지 | Scalar On | 0.946144 | 39.293846 | 1.205930 |
| bistro | 후기 정지 | Full-screen Off | 0.709230 | 39.231835 | 0.000000 |
| bistro | 후기 정지 | Scalar Off | 0.709230 | 39.231835 | 0.000000 |
| minecraft | 이동 | 원본 On | 1.987355 | 34.423941 | 2.042829 |
| minecraft | 이동 | Scalar On | 2.050849 | 34.254593 | 2.245626 |
| minecraft | 이동 | Full-screen Off | 1.755661 | 35.246464 | 1.613428 |
| minecraft | 이동 | Scalar Off | 1.728516 | 35.235520 | 1.629974 |
| minecraft | 전환 | 원본 On | 1.733203 | 35.512551 | 0.833942 |
| minecraft | 전환 | Scalar On | 1.856160 | 35.109674 | 1.274656 |
| minecraft | 전환 | Full-screen Off | 1.695712 | 34.733477 | 0.629374 |
| minecraft | 전환 | Scalar Off | 1.684851 | 34.732849 | 0.635931 |
| minecraft | 후기 정지 | 원본 On | 1.471707 | 36.384718 | 0.000000 |
| minecraft | 후기 정지 | Scalar On | 1.621348 | 35.848812 | 0.556121 |
| minecraft | 후기 정지 | Full-screen Off | 1.569443 | 34.653620 | 0.000000 |
| minecraft | 후기 정지 | Scalar Off | 1.569443 | 34.653620 | 0.000000 |

## 같은 패턴에서 선택 처리만 비교

아래 값은 Scalar−Full-screen이다. 양수면 선택 방식의 오차가 더 크다. On→Off 개선 전체를 선택 처리의 개선으로 오인하지 않기 위해 같은 패턴끼리 비교한다.

| 장면 | 구간 | On RGB MAE 차이 | Off RGB MAE 차이 | On 시간 잔차 차이 | Off 시간 잔차 차이 |
|---|---|---:|---:|---:|---:|
| bistro | 이동 | +0.212628 | -0.015378 | +0.505760 | +0.036226 |
| bistro | 후기 정지 | +0.363318 | +0.000000 | +1.205930 | +0.000000 |
| minecraft | 이동 | +0.063494 | -0.027144 | +0.202797 | +0.016546 |
| minecraft | 후기 정지 | +0.149641 | +0.000000 | +0.556121 | +0.000000 |

## 결과 해석

이동 중 Off의 RGB MAE는 두 장면 모두 On보다 낮았다. 하지만 full-screen도 Off에서 개선되며, 같은 Off 조건에서 Scalar를 적용한 추가 효과는 RGB MAE -0.015378/-0.027144와 시간 잔차 +0.036226/+0.016546의 절충이다. Scalar Off의 PSNR도 대응 full-screen Off보다 두 장면 모두 약간 낮다. MAE 하나로 선택 처리의 전반적인 품질 우위를 주장할 수 없다.

후기 정지에서는 원본 On의 RGB MAE가 Bistro 0.582826, Minecraft 1.471707로, Off의 0.709230/1.569443보다 낮았다. 따라서 교대 현상 제거와 temporal supersampling에 의한 정지 공간 품질은 별개다. Bistro에서는 Scalar Off의 이동 PSNR도 원본 On보다 낮아, 이동 시에도 모든 지표가 함께 개선되는 것은 아니다.

이번 결과는 기존 측정을 무효화하지 않는다. 기존 측정은 지터 On에서의 실제 품질 문제를 기록한 것이고, 이번 실험은 그 문제가 표본 패턴과 선택적 결합의 상호작용에 크게 의존함을 추가로 확인했다. 지터 자체가 잘못 구현됐다는 증거나 지터 Off를 최종 기본값으로 채택할 근거는 아니다.

## 실제 선택률

동일 threshold 0.01이며 분모는 전체 2,037,120 pixel이다. 지터 On/Off의 입력이 다르므로 mask 자체는 고정하지 않았다. 선택률은 history를 읽지 않은 비율이 아니다. ScalarWeight는 전체 화면의 velocity/history를 읽는다.

| 장면 | 구간 | On 선택 % | Off 선택 % | On mask 변경 % | Off mask 변경 % |
|---|---|---:|---:|---:|---:|
| bistro | 이동 | 1.483293 | 1.489887 | 1.182727 | 0.811113 |
| bistro | 후기 정지 | 1.701569 | 1.699654 | 1.273759 | 0.000000 |
| minecraft | 이동 | 59.527514 | 59.412141 | 20.775301 | 16.037457 |
| minecraft | 후기 정지 | 63.345974 | 63.207273 | 19.243393 | 0.000000 |

## 영상과 해석 범위

장면별로 기존 고정 ROI의 원본 크기 4-way MP4(240 frame, 60 FPS), 이동·전환·정지의 0.5배속 GIF와 연속 PNG sheet를 만들었다. MP4는 전체 decode frame 수와 PTS, GIF는 frame 수·공통 palette·duration을 검증했다. 영상은 압축/색 양자화를 포함하므로 수치 계산에 사용하지 않았다.

- [Bistro 비교 영상](../../Projects/CMAA2/AutoBench/JitterAblationAnalysis/bistro/four-way-60fps.mp4)
- [Minecraft 비교 영상](../../Projects/CMAA2/AutoBench/JitterAblationAnalysis/minecraft/four-way-60fps.mp4)

열 순서는 원본 On / Scalar On / Full-screen Off / Scalar Off다. 연속 PNG의 행도 같은 순서다. 카메라 이동만 포함하며 object-motion 고스팅 검증이나 다수 관찰자의 지각 평가가 아니다. 정지 안정화와 이동 중 reference 오차를 분리해 보며, 지터 Off의 채택 또는 새 선택식 변경은 이번 실험에서 하지 않았다.
