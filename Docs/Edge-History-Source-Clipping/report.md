# ⑭ 기준의 15번 source-clipping 단독 비교

⑮ clipping만으로 검사한 얇은 선 끊김을 해결하지 못했다. 이동 참조 오차와 시간 차분이 일부 ROI에서 늘었고, 추가 비용도 발생해 이번 조건에서는 기본 구현으로 채택하지 않는다. 이는 현재 범위·gamma1·clamp 설정의 결과이며 clipping 일반의 불가능성을 뜻하지 않는다.

브랜치: `experiment/edge-history-source-clipping`. 직접 기준: ⑭ `8ed45765e63d7e73ba63e17be329fef693dc65b4`. 새로운 clipping/sampling/blend 세 항목은 각각 독립이며 결합하지 않았다. 후보 선택식은 변경하지 않았다.

## GPU 성능

RTX 3060 Ti / DX11 Release x64 / Ultra / 1920×1061 / hidden / VSync Off. Scene별 동일 프로세스의 ④·⑭·새 구현을 300 warm-up + 4,800 frame×6회 정/역 순서로 반복했다. PNG·readback·진단 query Off. 변화율은 같은 run의 대조군으로 계산한 평균이며 실행 사이 절대시간을 분모로 섞지 않았다.

| 장면 | 방식 | 전체 AA ms | ④ 대비 | ⑭ 대비 | temporal ms | temporal ④ 대비 | temporal ⑭ 대비 |
|---|---|---:|---:|---:|---:|---:|---:|
| bistro | ④ T2X-R | 0.159216 | +0.00% | +7.00% | 0.033414 | +0.00% | +218.23% |
| bistro | ⑭ fixed0.8 | 0.148795 | -6.55% | +0.00% | 0.010501 | -68.58% | +0.00% |
| bistro | 15 source-clipping | 0.150588 | -5.42% | +1.21% | 0.012469 | -62.68% | +18.76% |
| minecraft | ④ T2X-R | 0.230875 | +0.00% | -8.10% | 0.035305 | +0.00% | +0.07% |
| minecraft | ⑭ fixed0.8 | 0.251232 | +8.82% | +0.00% | 0.035281 | -0.07% | +0.00% |
| minecraft | 15 source-clipping | 0.265727 | +15.10% | +5.77% | 0.049218 | +39.42% | +39.52% |

## 品질 수치와 프레임 검사

Supersample spatial proxy에 대한 RGB MAE(0~255, 낮을수록 작음)와 raw luma 2차 시간 차분(낮을수록 작음)을 함께 기록했다. 차분 감소는 blur와 motion의 영향도 포함해 반짝임/고스팅 해결을 단독 입증하지 않는다. CGVQM을 새로 실행한 결과가 아니다. ④는 paired Pattern On, ⑭와 새 구현은 Off이다.

| 장면 / 이동 ROI | ⑭ 참조 MAE | 새 MAE | ⑭ 2차 차분 | 새 2차 차분 |
|---|---:|---:|---:|---:|
| bistro/thin-chair | 5.2443 | 5.3084 | 2.2434 | 2.3930 |
| bistro/windows | 6.9915 | 6.4647 | 4.0159 | 4.2478 |
| minecraft/thin-seam | 1.3689 | 1.3907 | 2.4041 | 2.4750 |
| minecraft/leaves | 3.4306 | 3.5721 | 9.7324 | 9.2834 |
| minecraft/grass-seam | 2.0685 | 2.1726 | 5.1484 | 5.0072 |

두 장면 각각 240 frame의 ④·⑭ RGB는 기존 검증 자료와 byte-hash mismatch 0이었다. Same-draw current/raw/velocity/edge/coverage도 ⑭와 새 구현 사이 mismatch 0. 24개 진단 frame의 selected weight0.8, nonselected current output, feedback RGB/current alpha와 연속 history chain 검증을 통과했다. Test에서는 first frame와 frame3 reset을 검사했다.

32 shader entry compile 중 기존 28개 DXBC byte 일치. 독립 CPU 식과 실제 helper의 GPU fixture 결과는 numeric-gpu-audit.json에 있다. Fixtures의 허용 오차는 GPU의 sRGB 변환/보간 정밀도를 포함하며 pixel-exact 계산이라고 표현하지 않는다.

원본 full frame, 이동126~131 / 전환178~183 / 안정210~215의 nearest 2배 연속 프레임을 검사했다. 영상·GIF는 원본 PNG를 사용한 확인용이며 손실이 있다. Animated playback을 직접 시청한 것으로 표현하지 않는다. ROI는 화면 고정 영역이며 object tracking이 아니다.

## 구현과 원본 차이

- Signed Co/Cg retained; variance clamped nonnegative; history clamped in YCoCg, not inverse-transformed RGB corner endpoints
- Sharpening deliberately Off to isolate history range limiting
- SMAA linear sRGB-view domain, clamp sampler, mask/stencil and history lifecycle retained; not full original TSCMAA port
- Source component bypassed while history invalid; preserves original seed/reset output

자세한 조건: method.md / 재현: Tools/SMAA/run_source_temporal_component.ps1 / 성능 raw CSV와 JSON: 같은 디렉터리 / 품질: scene-capture.json, scene-quality-per-frame.csv.
