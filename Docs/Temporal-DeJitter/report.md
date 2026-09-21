# Current 읽기 한 번에 통합한 de-jitter 실험 결과

기존 hybrid de-jitter의 좌표식을 현재 temporal pixel shader에 적용했다. 추가 pass·texture·샘플 명령 없이 current를 Linear로 한 번 읽으며 history는 Point를 유지했다. 기존 luma 선택이 current 읽기 뒤에 있으므로 current 보정은 선택 영역도 바꾼다. 이 실험은 비후보만 보정했던 예전 hybrid의 정확한 이식이 아니라 **current 읽기 재사용의 최소 진단**이다.

구현 커밋: `ddf512e`. 브랜치: `experiment/temporal-pass-dejitter`. [구현 근거·사전 조건](method.md).

## 핵심 결과

**추가 패스 없이 통합할 수 있었지만, 이번 current-only 방식은 채택하지 않는다.** Bistro에서는 일부 개선이 있었으나 Minecraft에서는 원래 안정적인 선택 픽셀에 새 떨림이 발생했다. 아래 품질 변화는 기존 Scalar 대비이고, 비용 변화는 원본 T2X-R 대비다.

| 장면 | 이동 RGB MAE 변화 | 정지 RGB frame 변화량의 변화 | 전체 AA 시간 변화 |
|---|---:|---:|---:|
| bistro | -21.11% | -36.05% | +0.513% |
| minecraft | +6.66% | +242.67% | +0.550% |

원본 T2X-R의 후기 정지 RGB 변화량은 두 장면 모두 0이다. 지표 변화율은 지각 품질의 백분율이 아니다.

## 검증

- 원본 shader 8 variant와 기존 Scalar 2 variant bytecode 불변. 새 10 variant 컴파일 및 sample/derivative/branch 검사 PASS.
- 두 장면 11 mode×240 frame: pattern 설정 5,280회 PASS. 이전 native/spatial/mask/Scalar, 원위치 Linear 대조군 및 새 output 반복 hash 3,360회 mismatch 0.
- 960 mode-frame의 선택/비선택 결과 일치 검사 PASS. 새 선택 영역은 FullDeJitter, 비선택 영역은 DeJitterSpatial과 일치.
- 최초 history가 없을 때 새 두 mode는 같은 draw에서 de-jitter spatial로 seed한다. 새 pass는 없다. 원본 초기화는 유지했다.
- 같은 EXE로 별도 clean process에서 품질 캡처와 성능 측정. 실행 전후 잔류 데모 0, timeout/완료 report 검증.

EXE SHA-256: `DF65EA946CAA2F05CD780D9C466ED7FA7D6A9DAE5E5C61F538AB0E43B1D83A1F`

## CPU mirror와 선택 변화

S0는 화면 (+.25,+.25) pixel, S1은 (-.25,-.25) pixel이다. 보정은 UV+jitter/resolution이며 CPU mirror는 기존 spatial PNG를 linear RGB로 변환한 후 같은 quarter-pixel bilinear를 적용해 다시 sRGB로 인코딩한다. GPU sampler/색 변환 정밀도 차이를 기록하며 byte-exact float mirror라고 표현하지 않는다.

초기의 이상적 CPU mirror 최대 2 RGB 단계 가정은 일부 frame에서 실패했다. 이를 숨기거나 허용값만 올리지 않고, 같은 PNG를 별도 sRGB texture에 업로드해 production sampling 함수를 실행하는 GPU probe를 추가했다. 이 probe는 데모 패스가 아니며 품질 검증에서만 실행했다. 내부 sampler/변환 오차의 원인을 완전히 분리한 것은 아니다.

| 장면 | 검사 frame | 이상적 CPU 최대 RGB 차이 | CPU 최대 평균 차이 | 별도 GPU probe 최대 RGB 차이 |
|---|---:|---:|---:|---:|
| bistro | 6 | 3 | 0.043696 | 1 |
| minecraft | 6 | 4 | 0.073268 | 1 |

| 장면·구간 | 기존 선택률 | 보정 후 선택률 | 선택 상태 변경률 | 기존에서 제거 | 새로 추가 |
|---|---:|---:|---:|---:|---:|
| bistro 이동 | 1.4833% | 1.2905% | 0.6115% | 0.4022% | 0.2094% |
| bistro 정지 | 1.7016% | 1.4737% | 0.6852% | 0.4566% | 0.2287% |
| minecraft 이동 | 59.5275% | 58.9984% | 10.3085% | 5.4188% | 4.8897% |
| minecraft 정지 | 63.3460% | 63.2033% | 11.1440% | 5.6433% | 5.5007% |

선택률은 혼합하는 픽셀 비율이다. 이 Scalar 구현은 velocity/history도 모든 픽셀에서 읽으므로 선택률 감소를 texture 읽기 감소로 해석하지 않는다.

## 정지 안정성 및 품질

RGB MAE/PSNR은 동일 pose supersample spatial proxy와 비교했다. 시간 변화 잔차는 `|(Yt−Yt-1)−(Rt−Rt-1)|`의 화면 평균이며 optical-flow 정렬 또는 순수 고스팅 지표가 아니다. 윤곽 비율은 reference 대비 Sobel 강도다. 떨림 감소와 함께 윤곽 비율도 낮아지면 흐려짐에 의한 변화 가능성을 함께 본다.

### bistro

| 구간 | 방식 | RGB MAE | PSNR dB | 시간 변화 잔차 | 윤곽/reference |
|---|---|---:|---:|---:|---:|
| 이동 60–179 | 원본 T2X-R | 0.734975 | 40.391 | 0.802725 | 0.9589 |
| 이동 60–179 | 기존 Scalar | 0.947602 | 38.924 | 1.308485 | 1.0073 |
| 이동 60–179 | 전체 current de-jitter | 0.758919 | 40.586 | 0.887031 | 0.9376 |
| 이동 60–179 | Scalar current de-jitter | 0.747535 | 40.507 | 0.889128 | 0.9277 |
| 전환 160–219 | 원본 T2X-R | 0.646081 | 41.218 | 0.320920 | 0.9625 |
| 전환 160–219 | 기존 Scalar | 0.955614 | 39.053 | 1.257903 | 1.0039 |
| 전환 160–219 | 전체 current de-jitter | 0.702366 | 41.109 | 0.716689 | 0.9410 |
| 전환 160–219 | Scalar current de-jitter | 0.753309 | 40.595 | 0.827438 | 0.9271 |
| 정지 200–239 | 원본 T2X-R | 0.582826 | 41.864 | 0.000000 | 0.9643 |
| 정지 200–239 | 기존 Scalar | 0.946144 | 39.294 | 1.205930 | 1.0034 |
| 정지 200–239 | 전체 current de-jitter | 0.662491 | 41.540 | 0.607152 | 0.9439 |
| 정지 200–239 | Scalar current de-jitter | 0.747041 | 40.814 | 0.772642 | 0.9276 |

| 방식 | 정지 RGB frame 종류 | 평균 RGB frame 변화 | 2-frame 간격 불일치 |
|---|---:|---:|---:|
| 원본 T2X-R | 1 | 0.000000 | 0 |
| 기존 Scalar | 2 | 1.287832 | 0 |
| 전체 current de-jitter | 2 | 0.643530 | 0 |
| Scalar current de-jitter | 2 | 0.823544 | 0 |

### minecraft

| 구간 | 방식 | RGB MAE | PSNR dB | 시간 변화 잔차 | 윤곽/reference |
|---|---|---:|---:|---:|---:|
| 이동 60–179 | 원본 T2X-R | 1.987355 | 34.424 | 2.042829 | 0.9247 |
| 이동 60–179 | 기존 Scalar | 2.050849 | 34.255 | 2.245626 | 0.9301 |
| 이동 60–179 | 전체 current de-jitter | 2.198365 | 34.058 | 2.598147 | 0.8942 |
| 이동 60–179 | Scalar current de-jitter | 2.187417 | 34.068 | 2.558467 | 0.8914 |
| 전환 160–219 | 원본 T2X-R | 1.733203 | 35.513 | 0.833942 | 0.9291 |
| 전환 160–219 | 기존 Scalar | 1.856160 | 35.110 | 1.274656 | 0.9346 |
| 전환 160–219 | 전체 current de-jitter | 2.108400 | 34.711 | 2.280862 | 0.9004 |
| 전환 160–219 | Scalar current de-jitter | 2.124106 | 34.660 | 2.232164 | 0.8967 |
| 정지 200–239 | 원본 T2X-R | 1.471707 | 36.385 | 0.000000 | 0.9312 |
| 정지 200–239 | 기존 Scalar | 1.621348 | 35.849 | 0.556121 | 0.9366 |
| 정지 200–239 | 전체 current de-jitter | 1.934155 | 35.330 | 1.988969 | 0.9037 |
| 정지 200–239 | Scalar current de-jitter | 1.963378 | 35.243 | 1.935702 | 0.8998 |

| 방식 | 정지 RGB frame 종류 | 평균 RGB frame 변화 | 2-frame 간격 불일치 |
|---|---:|---:|---:|
| 원본 T2X-R | 1 | 0.000000 | 0 |
| 기존 Scalar | 2 | 0.580355 | 0 |
| 전체 current de-jitter | 2 | 2.046913 | 0 |
| Scalar current de-jitter | 2 | 1.988729 | 0 |

## 정지 화면의 실패 위치

Frame 200/201의 두 위상을 비교했다. 후기 정지 전체 구간의 2-frame 간격 hash 일치는 별도로 확인했다. 아래 분류는 관측 위치를 나눈 것으로 새 후보 규칙이 아니다.

| 장면 | 두 방식·두 위상에서의 선택 상태 | 화면 비율 | 기존 영역 내 RGB 변화 | 보정 후 영역 내 RGB 변화 | 보정 후 전체 변화 기여 |
|---|---|---:|---:|---:|---:|
| bistro | 항상 선택 | 0.8375% | 0.000000 | 8.440029 | 0.070686 |
| bistro | 항상 비선택 | 97.5081% | 1.197567 | 0.661425 | 0.644943 |
| bistro | 그 외 선택 변화 | 1.6544% | 7.259680 | 6.522723 | 0.107915 |
| minecraft | 항상 선택 | 48.8816% | 0.000000 | 3.144216 | 1.536942 |
| minecraft | 항상 비선택 | 25.9493% | 0.510078 | 0.240190 | 0.062328 |
| minecraft | 그 외 선택 변화 | 25.1691% | 1.779933 | 1.547373 | 0.389460 |

두 장면 모두 항상 비선택인 영역의 변화는 줄었지만, 항상 선택된 영역에는 기존 0이던 변화가 생겼다. Minecraft에서 그 영역은 화면의 약 48.9%이며 새 전체 RGB 변화 중 큰 부분을 차지한다. 선택이 바뀌지 않은 픽셀에서도 악화되었으므로 마스크 변화만으로 이 결과를 설명할 수 없다. Current만 보정하고 previous spatial sample을 유지한 비대칭이 기존 T2X의 정지 두 표본 상쇄를 바꾼다는 해석과 부합한다.

정지 상태에서 history weight가 0.5인 경우, 원본은 두 위상에서 `(C0+C1)/2`로 같다. 이번 변형은 `(D0(C0)+C1)/2`와 `(D1(C1)+C0)/2`가 되어 일반적으로 같지 않다. 여기서 D0/D1은 각 위상의 current 좌표 보정이다. 이 식은 current-only 변경의 비대칭을 설명하며, 움직임 중 가중치 변화·선택 변화의 모든 영향을 분리한 증명은 아니다.

## 성능

RTX 3060 Ti, DX11, 1920×1061, 숨긴 창, VSync Off. 장면별 새 process, 30초 미측정 예열, mode당 300-frame warmup 및 4,800-frame×4회. 정순/역순 2회씩이다. PNG·후보 readback·프레임별 pattern 검사를 끄고 CPU 영상 분석과 분리했다. 한 process 안의 반복이며 독립 process 반복이나 동등성 증명이 아니다.

### bistro

| 방식 | SMAA ms | 원본 대비 | Resolve ms | 원본 대비 | WholeFrame ms |
|---|---:|---:|---:|---:|---:|
| 원본 T2X-R | 0.208541 | +0.000% | 0.033643 | +0.000% | 2.624868 |
| 기존 Scalar | 0.209100 | +0.268% | 0.033884 | +0.715% | 2.623201 |
| Scalar 원위치 Linear | 0.209192 | +0.312% | 0.033881 | +0.706% | 2.631928 |
| 전체 current de-jitter | 0.209255 | +0.342% | 0.034005 | +1.074% | 2.623432 |
| Scalar current de-jitter | 0.209611 | +0.513% | 0.034257 | +1.824% | 2.622940 |

| 비교 | 지표 | 변화 ms | 변화 % | 느린 반복 | 정순 변화 ms | 역순 변화 ms |
|---|---|---:|---:|---:|---:|---:|
| Scalar current de-jitter − 기존 Scalar | SMAA | +0.000512 | +0.245% | 4/4 | +0.000375 | +0.000648 |
| Scalar current de-jitter − 기존 Scalar | Resolve | +0.000373 | +1.101% | 4/4 | +0.000434 | +0.000312 |
| Scalar current de-jitter − Scalar 원위치 Linear | SMAA | +0.000419 | +0.201% | 4/4 | +0.000439 | +0.000400 |
| Scalar current de-jitter − Scalar 원위치 Linear | Resolve | +0.000376 | +1.110% | 4/4 | +0.000379 | +0.000374 |

### minecraft

| 방식 | SMAA ms | 원본 대비 | Resolve ms | 원본 대비 | WholeFrame ms |
|---|---:|---:|---:|---:|---:|
| 원본 T2X-R | 0.283801 | +0.000% | 0.035059 | +0.000% | 1.250811 |
| 기존 Scalar | 0.284512 | +0.250% | 0.035248 | +0.540% | 1.250330 |
| Scalar 원위치 Linear | 0.284664 | +0.304% | 0.035265 | +0.588% | 1.250634 |
| 전체 current de-jitter | 0.285087 | +0.453% | 0.035563 | +1.437% | 1.250992 |
| Scalar current de-jitter | 0.285363 | +0.550% | 0.035810 | +2.143% | 1.251683 |

| 비교 | 지표 | 변화 ms | 변화 % | 느린 반복 | 정순 변화 ms | 역순 변화 ms |
|---|---|---:|---:|---:|---:|---:|
| Scalar current de-jitter − 기존 Scalar | SMAA | +0.000851 | +0.299% | 3/4 | +0.000102 | +0.001601 |
| Scalar current de-jitter − 기존 Scalar | Resolve | +0.000562 | +1.594% | 4/4 | +0.000547 | +0.000577 |
| Scalar current de-jitter − Scalar 원위치 Linear | SMAA | +0.000699 | +0.246% | 4/4 | +0.001006 | +0.000393 |
| Scalar current de-jitter − Scalar 원위치 Linear | Resolve | +0.000545 | +1.546% | 4/4 | +0.000553 | +0.000538 |

## 판정

현재 읽기 한 번을 바꾸는 통합은 구현 가능했지만, 이번 current-only 최소 구현은 기본 방식으로 채택하지 않는다. 비선택 영역을 보정하려던 변화가 원래 안정적인 선택 영역의 결합도 바꾸었고, Minecraft 정지와 이동 품질에서 퇴행이 나타났다. Bistro의 정지 수치 개선만으로 성공이라고 판단하지 않는다. 이 결론은 이 current-only 구성에 한정되며 모든 단일 패스 de-jitter/선택적 temporal 방식의 불가능성을 증명하지 않는다.

## 해석의 범위

현재 보정은 후보·비후보 모두에 적용되고 새 입력으로 선택하므로, 효과에는 current 필터링·선택 마스크·alpha 기반 weight 변화가 포함된다. History 필터, history UV와 velocity UV, 저장되는 spatial history는 그대로다. 따라서 완전한 de-jittered temporal reconstruction으로 부르지 않는다. 예전 후보 목록 방식의 비용이나 source TSCMAA 성능으로도 해석하지 않는다.

정적 두 phase의 difference는 flicker 진단이며 RGB 변화 감소만으로 품질 우위를 확정하지 않는다. Reference는 2× 선형 해상도/frame 내 3×3 subpixel grid/8×MSAA의 spatial proxy로, 3×3 후보 확장이 아니다. 현재 실험은 camera motion이며 object-motion/disocclusion의 일반적인 개선을 입증하지 않는다.

원시 경로·hash·mirror 오차·영상 manifest는 장면별 quality JSON, 100 timing 및 100 distribution 행/장면과 반복별 값은 performance JSON에 기록했다. 고정 ROI의 4-way MP4(240 frame, 60 FPS, 전체 decode/PTS 검사), 고정 팔레트 0.5배속 GIF 및 원본 PNG 비교를 생성했다. 영상은 압축/색 양자화를 포함하므로 수치 계산에는 PNG만 사용했다.
