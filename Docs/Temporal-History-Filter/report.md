# 기존 연구의 history 필터를 temporal 단일 패스에 재사용한 결과

이번 실험은 **기존 선택식의 떨림 해결책을 완성한 것이 아니라, 추가 패스 없이 가져올 수 있는 필터 요소 하나를 검증한 결과**다. 기존 선택 마스크와 paired jitter를 유지한 Point/Linear 대조군을 만들었으며, 필터의 효과와 선택적 결합의 효과를 구분했다.

구현 커밋: `145cf2d`. 브랜치: `experiment/temporal-pass-history-filter`. [기존 브랜치 감사와 측정 전 조건](reuse-audit.md).

## 바꾼 부분과 보존한 부분

Temporal pixel shader의 history sampler만 Point에서 기존 Linear로 바꿨다. 현재 색상·velocity는 기존 Point로 읽고, 현재 luma 미분 선택식과 threshold 0.01, paired jitter, Original spatial SMAA, camera/depth reprojection 및 spatial-frame history를 유지했다. 추가 pass·resource·history 읽기 명령은 없다. Scalar는 비선택 픽셀의 혼합 비중을 0으로 만들며 velocity/history 접근을 생략하지 않는다.

RGBA를 함께 필터링하므로 history RGB와 velocity를 인코딩한 alpha가 모두 변할 수 있다. 혼합 비중 공식은 같아도 실제 비중은 달라진다. 따라서 순수 RGB 필터 효과 또는 비용이 없는 변경이라고 표현하지 않는다.

## 정확성 및 비교 조건

- FXC: 원본 8 variant 및 기존 Scalar 2 variant의 bytecode 유지. Point/Linear 4쌍의 명령 차이는 sampler 선언·피연산자뿐이다.
- 두 장면 9 mode×240 frame: paired-pattern 검사 4,320회 PASS. 기존 출력/마스크/spatial, Point 대조군 및 Linear 반복 hash 비교 3,360회 mismatch 0.
- 두 장면 합계 960 mode-frame에서 선택 영역은 해당 full-screen 출력, 비선택 영역은 spatial 출력과 정확히 일치했다.
- 품질 캡처와 성능 측정은 별도 clean process로 실행했다. 모든 실행의 EXE SHA-256은 아래와 같다.

`493327353A245621914955A794C532F1F88FA8B05E7FC7096A8F5C10C83646AA`

## 품질: 동일 시점 supersample spatial reference

RGB MAE와 시간 변화 잔차는 낮을수록 기준 영상에 가깝다. 시간 변화 잔차는 `|(Yt−Yt-1)−(Rt−Rt-1)|`의 화면 평균이며 순수 고스팅 지표가 아니다. 윤곽 비율은 reference 대비 Sobel 강도다. 비율이 낮아지는 것은 윤곽이 약해졌다는 뜻이며 그 자체로 품질 향상 또는 저하를 확정하지 않는다.

### bistro

| 구간 | 방식 | RGB MAE | PSNR dB | 시간 변화 잔차 | 윤곽/reference |
|---|---|---:|---:|---:|---:|
| 이동 60–179 | 원본 T2X-R | 0.734975 | 40.391 | 0.802725 | 0.9589 |
| 이동 60–179 | 전체 화면 Linear | 0.675566 | 40.997 | 0.729054 | 0.9386 |
| 이동 60–179 | Scalar Point | 0.947602 | 38.924 | 1.308485 | 1.0073 |
| 이동 60–179 | Scalar Linear | 0.943760 | 39.084 | 1.301158 | 1.0049 |
| 전환 160–219 | 원본 T2X-R | 0.646081 | 41.218 | 0.320920 | 0.9625 |
| 전환 160–219 | 전체 화면 Linear | 0.625293 | 41.415 | 0.295051 | 0.9553 |
| 전환 160–219 | Scalar Point | 0.955614 | 39.053 | 1.257903 | 1.0039 |
| 전환 160–219 | Scalar Linear | 0.954210 | 39.107 | 1.255410 | 1.0029 |
| 정지 200–239 | 원본 T2X-R | 0.582826 | 41.864 | 0.000000 | 0.9643 |
| 정지 200–239 | 전체 화면 Linear | 0.582826 | 41.864 | 0.000000 | 0.9643 |
| 정지 200–239 | Scalar Point | 0.946144 | 39.294 | 1.205930 | 1.0034 |
| 정지 200–239 | Scalar Linear | 0.946144 | 39.294 | 1.205930 | 1.0034 |

| 방식 | 정지 구간 서로 다른 RGB 프레임 수 | 정지 RGB 프레임 변화 평균 |
|---|---:|---:|
| 원본 T2X-R | 1 | 0.000000 |
| 전체 화면 Linear | 1 | 0.000000 |
| Scalar Point | 2 | 1.287832 |
| Scalar Linear | 2 | 1.287832 |

이동 중 선택률은 두 Scalar 방식 모두 1.4833% (평균 30216.5/2,037,120픽셀)이다. 이 비율은 혼합되는 픽셀 비율이며 history 읽기를 생략한 비율이 아니다.

첫 프레임 spatial seed와 다른 채널 수: `{'O-T2X-R': 0, 'ABL-HistoryLinear-R': 0, 'ABL-ScalarWeight-001-R': 0, 'ABL-ScalarHistoryLinear-001-R': 0}`.

### minecraft

| 구간 | 방식 | RGB MAE | PSNR dB | 시간 변화 잔차 | 윤곽/reference |
|---|---|---:|---:|---:|---:|
| 이동 60–179 | 원본 T2X-R | 1.987355 | 34.424 | 2.042829 | 0.9247 |
| 이동 60–179 | 전체 화면 Linear | 1.836351 | 35.051 | 1.830527 | 0.8936 |
| 이동 60–179 | Scalar Point | 2.050849 | 34.255 | 2.245626 | 0.9301 |
| 이동 60–179 | Scalar Linear | 1.923109 | 34.802 | 2.069963 | 0.9027 |
| 전환 160–219 | 원본 T2X-R | 1.733203 | 35.513 | 0.833942 | 0.9291 |
| 전환 160–219 | 전체 화면 Linear | 1.668793 | 35.755 | 0.744978 | 0.9181 |
| 전환 160–219 | Scalar Point | 1.856160 | 35.110 | 1.274656 | 0.9346 |
| 전환 160–219 | Scalar Linear | 1.802625 | 35.318 | 1.202024 | 0.9251 |
| 정지 200–239 | 원본 T2X-R | 1.471707 | 36.385 | 0.000000 | 0.9312 |
| 정지 200–239 | 전체 화면 Linear | 1.471707 | 36.385 | 0.000000 | 0.9312 |
| 정지 200–239 | Scalar Point | 1.621348 | 35.849 | 0.556121 | 0.9366 |
| 정지 200–239 | Scalar Linear | 1.621348 | 35.849 | 0.556121 | 0.9366 |

| 방식 | 정지 구간 서로 다른 RGB 프레임 수 | 정지 RGB 프레임 변화 평균 |
|---|---:|---:|
| 원본 T2X-R | 1 | 0.000000 |
| 전체 화면 Linear | 1 | 0.000000 |
| Scalar Point | 2 | 0.580355 |
| Scalar Linear | 2 | 0.580355 |

이동 중 선택률은 두 Scalar 방식 모두 59.5275% (평균 1212646.9/2,037,120픽셀)이다. 이 비율은 혼합되는 픽셀 비율이며 history 읽기를 생략한 비율이 아니다.

첫 프레임 spatial seed와 다른 채널 수: `{'O-T2X-R': 0, 'ABL-HistoryLinear-R': 0, 'ABL-ScalarWeight-001-R': 0, 'ABL-ScalarHistoryLinear-001-R': 0}`.

## 성능: 동일 실행 안의 대조군

RTX 3060 Ti, DX11, 1920×1061, VSync Off, 숨긴 창. 장면별 새 프로세스, 30초 미측정 예열, mode당 300-frame warmup, 4,800-frame 측정×4회. 정순/역순을 두 번씩 적용했다. PNG·후보 readback·프레임별 pattern 진단은 껐고 CPU 영상 분석도 함께 실행하지 않았다. 네 반복은 동일 프로세스 안의 반복이며 독립 프로세스 4회 또는 동등성 검증으로 해석하지 않는다.

### bistro

| 방식 | 전체 SMAA ms | 원본 대비 | Resolve ms | 원본 대비 | WholeFrame ms |
|---|---:|---:|---:|---:|---:|
| 원본 T2X-R | 0.210340 | +0.000% | 0.033237 | +0.000% | 2.621902 |
| Point 명령 대조군 | 0.210691 | +0.167% | 0.033256 | +0.056% | 2.628927 |
| 전체 화면 Linear | 0.210905 | +0.269% | 0.033389 | +0.457% | 2.629505 |
| Scalar Point | 0.210977 | +0.303% | 0.033476 | +0.717% | 2.629444 |
| Scalar Linear | 0.211219 | +0.418% | 0.033624 | +1.165% | 2.635615 |

| 필터 변경 비교 | 지표 | 변화 ms | 변화 % | 느린 반복 | 정순 변화 ms | 역순 변화 ms |
|---|---|---:|---:|---:|---:|---:|
| 전체 화면 Linear − Point 명령 대조군 | SMAA | +0.000214 | +0.102% | 2/4 | +0.000663 | -0.000235 |
| 전체 화면 Linear − Point 명령 대조군 | Resolve | +0.000133 | +0.401% | 4/4 | +0.000146 | +0.000120 |
| Scalar Linear − Scalar Point | SMAA | +0.000242 | +0.115% | 2/4 | +0.000765 | -0.000281 |
| Scalar Linear − Scalar Point | Resolve | +0.000149 | +0.444% | 4/4 | +0.000159 | +0.000138 |

### minecraft

| 방식 | 전체 SMAA ms | 원본 대비 | Resolve ms | 원본 대비 | WholeFrame ms |
|---|---:|---:|---:|---:|---:|
| 원본 T2X-R | 0.282487 | +0.000% | 0.034796 | +0.000% | 1.247334 |
| Point 명령 대조군 | 0.283000 | +0.181% | 0.034808 | +0.035% | 1.241637 |
| 전체 화면 Linear | 0.283149 | +0.234% | 0.034949 | +0.441% | 1.245541 |
| Scalar Point | 0.283187 | +0.248% | 0.035017 | +0.634% | 1.244427 |
| Scalar Linear | 0.283211 | +0.256% | 0.035123 | +0.941% | 1.243478 |

| 필터 변경 비교 | 지표 | 변화 ms | 변화 % | 느린 반복 | 정순 변화 ms | 역순 변화 ms |
|---|---|---:|---:|---:|---:|---:|
| 전체 화면 Linear − Point 명령 대조군 | SMAA | +0.000149 | +0.053% | 2/4 | +0.000701 | -0.000402 |
| 전체 화면 Linear − Point 명령 대조군 | Resolve | +0.000141 | +0.405% | 4/4 | +0.000049 | +0.000233 |
| Scalar Linear − Scalar Point | SMAA | +0.000023 | +0.008% | 2/4 | +0.000699 | -0.000652 |
| Scalar Linear − Scalar Point | Resolve | +0.000107 | +0.305% | 3/4 | -0.000005 | +0.000218 |

## 이번 재사용 실험의 판단

History Linear는 현재 temporal 패스 안에서 적용할 수 있었고 이동 중 spatial-reference 오차를 줄였다. 그러나 전체 화면 대조군에서도 개선이 나타나므로 선택적 temporal 처리만의 효과가 아니다. Scalar의 정지 구간 두 위상 교대와 RGB 변화량은 두 장면 모두 기존과 같았다. 비선택 픽셀은 여전히 current spatial을 출력하므로 이 필터로 해당 지터를 없앨 수 없다.

필터는 후속 실험의 독립 옵션으로 보존한다. 현재 luma 선택식을 최종 구현으로 채택하거나 이 결과를 가속·품질 우위의 완성으로 표현하지 않는다. 다음 핵심 작업은 현재 temporal 패스가 읽는 current/history 색상과 기존 혼합 비중으로 안정적인 생략 위치를 구분할 수 있는지 검증하는 것이다. 새 조건은 먼저 실패 픽셀에 대한 구분력을 확인한 뒤 구현하며, history를 읽고 나서 판단하면 그 읽기 비용은 절약하지 못한다는 제약을 유지한다.

## 해석 범위와 재현 자료

Point 대조군은 원본과 출력이 같으므로 그 timing 차이는 입력/출력 품질 차이로 설명할 수 없다. 명령 배치와 실행 순서·클럭 등 계측 변동을 고려해야 한다. 필터 변경은 같은 명령 순서의 Point 대조군과도 비교했다. 근소한 전체 AA 차이를 곧바로 가속 성공이나 무비용으로 판정하지 않는다.

Reference는 2× 선형 해상도, frame 내 3×3 subpixel grid, 8×MSAA의 spatial proxy다. 여기의 3×3은 후보 확장이 아니다. 기존 MIP/sharpen tuning을 포함하며 temporal ground truth가 아니다. 실험은 두 장면의 camera motion 범위이고 object motion/disocclusion 일반화를 검증하지 않았다.

영상은 고정 화면 ROI의 4-way 비교이며 object tracking이 아니다. MP4는 CRF12/YUV420, GIF는 고정 256색 팔레트의 보조 자료다. 픽셀 판정은 PNG로 수행했다. MP4 전체 decode로 240 frame, 60 FPS, PTS 간격을 확인했다.

- `minecraft-quality.json`, `bistro-quality.json`: 원본 경로·hash·품질·선택률·정지 상태·영상 manifest.
- `minecraft-performance.json`, `bistro-performance.json`: 실행 receipt, 100개 timing 및 100개 distribution 행/장면, 반복별 평균·순서 효과.
- `shader-validation.json`: Point/Linear shader 명령 및 bytecode 근거.
- `Tools/SMAA/analyze_temporal_history_filter.py`: 품질/성능 검증 및 계산.
- `Tools/SMAA/write_temporal_history_filter_report.py`: 이 표의 재생성.

원시 PNG/영상/벤치마크 폴더는 Git에 포함하지 않는다. 결과는 기본 SMAA나 최종 8-case 정의를 변경하지 않는다.
