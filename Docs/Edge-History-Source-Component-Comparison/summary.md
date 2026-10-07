# ⑮·⑯·⑰: ⑭에서 독립 분기한 소스 요소 비교

⑮ clipping, ⑯ recovered five-fetch sampling, ⑰ gamma2 color blend. 세 구현은 완료된 ⑭에서 직접 분기했으며 서로의 변경을 포함하지 않는다. 후보식·지터·가중치·feedback·spatial 처리를 유지했다. 새 production pass/copy/texture는 없다.

| 새 구현 / 장면 | 전체 AA ms | 같은 실행 ④ ms | 같은 실행 ⑭ ms | AA ④ 대비 | AA ⑭ 대비 | temporal ms | temporal ④ 대비 | temporal ⑭ 대비 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15/bistro | 0.150588 | 0.159216 | 0.148795 | -5.42% | +1.21% | 0.012469 | -62.68% | +18.76% |
| 15/minecraft | 0.265727 | 0.230875 | 0.251232 | +15.10% | +5.77% | 0.049218 | +39.42% | +39.52% |
| 16/bistro | 0.148461 | 0.159024 | 0.148438 | -6.64% | +0.02% | 0.010444 | -68.95% | -0.16% |
| 16/minecraft | 0.250937 | 0.230014 | 0.250396 | +9.10% | +0.22% | 0.035444 | +0.85% | +0.82% |
| 17/bistro | 0.148696 | 0.159285 | 0.148763 | -6.65% | -0.05% | 0.010413 | -68.82% | -0.62% |
| 17/minecraft | 0.250168 | 0.229215 | 0.249952 | +9.14% | +0.09% | 0.035456 | +0.57% | +0.46% |

각 행의 분모는 대응 실험의 같은 run이다. 서로 다른 실행의 시간 하나로 비율을 다시 계산하지 않는다. RTX3060Ti / DX11 Release x64 / Ultra / 1920×1061 / hidden / VSync Off / 300 warm-up +4,800 frame×6회. PNG/query/readback Off의 별도 clean process.

## 품질과 구현 범위

품질은 두 장면 각각 240 frame의 같은 pose에서 원본 PNG와 nearest 확대 연속 프레임, spatial proxy MAE/PSNR, raw temporal difference로 확인했다. CGVQM 재실행 결과가 아니며 raw difference 감소만으로 고스팅/반짝임 해결을 확정하지 않는다. ④ Pattern On, ⑭~⑰ Off 차이를 표시했다.

| 이동 ROI | ④ MAE | ⑭ MAE | ⑮ MAE | ⑯ MAE | ⑰ MAE |
|---|---:|---:|---:|---:|---:|
| bistro/thin-chair | 4.3815 | 5.2443 | 5.3084 | 5.2419 | 5.2235 |
| bistro/windows | 5.3997 | 6.9915 | 6.4647 | 7.0164 | 6.9885 |
| minecraft/thin-seam | 1.6265 | 1.3689 | 1.3907 | 1.3702 | 1.3663 |
| minecraft/leaves | 3.3479 | 3.4306 | 3.5721 | 3.4344 | 3.4251 |
| minecraft/grass-seam | 2.0528 | 2.0685 | 2.1726 | 2.0749 | 2.0664 |

| 이동 ROI | ④ luma 2차 차분 | ⑭ | ⑮ | ⑯ | ⑰ |
|---|---:|---:|---:|---:|---:|
| bistro/thin-chair | 4.5897 | 2.2434 | 2.3930 | 2.2411 | 2.2479 |
| bistro/windows | 7.2574 | 4.0159 | 4.2478 | 3.9883 | 3.9538 |
| minecraft/thin-seam | 2.8512 | 2.4041 | 2.4750 | 2.4022 | 2.4089 |
| minecraft/leaves | 10.3398 | 9.7324 | 9.2834 | 9.7206 | 9.7363 |
| minecraft/grass-seam | 5.1836 | 5.1484 | 5.0072 | 5.1355 | 5.1501 |

## 성능 추정 범위

아래 구간은 동일 프로세스 안의 여섯 paired run으로 계산한 미보정 95% Student-t 구간이다. 서로 다른 세션에 대한 재현 범위가 아니며 다중 비교 보정은 하지 않았다. 구간이 0을 포함하거나 변화가 매우 작으면 안정적인 성능 차이를 주장하지 않는다.

| 실험/장면 | 전체 AA ⑭ 대비 추정 구간 | temporal ⑭ 대비 추정 구간 |
|---|---:|---:|
| 15/bistro | +0.60% ~ +1.81% | +17.14% ~ +20.37% |
| 15/minecraft | +4.88% ~ +6.66% | +37.00% ~ +42.03% |
| 16/bistro | -0.21% ~ +0.24% | -2.08% ~ +1.75% |
| 16/minecraft | -0.57% ~ +1.00% | -0.99% ~ +2.64% |
| 17/bistro | -0.28% ~ +0.19% | -2.56% ~ +1.32% |
| 17/minecraft | -0.91% ~ +1.08% | -1.80% ~ +2.72% |

⑮는 current spatial neighborhood의 gamma1 YCoCg clamp이며 signed chroma/variance/좌표계 안전성 수정과 sharpening Off가 포함된다. 원본 ClipColor의 완전한 동일 구현이라고 표현하지 않는다. ⑯는 원본의 비대칭 계수까지 유지하되 SMAA linear RGB/clamp sampler를 유지한다. ⑰는 원본 encoded RGB square/sqrt 식을 sRGB-view SMAA에 분리 적용한 adapter이며 색 공간 변환과 범위 제한 비용을 포함한다. 원본 UNORM 파이프라인 전체의 비용을 뜻하지 않는다.

세 실험 모두 검사한 이동 얇은 선에서 구조 단절을 해결했다고 판정하지 않는다. 작은 지표 개선/유사 점수로 품질 성공을 주장하지 않는다. 기본 구현은 변경하지 않고 실험 결과로 보존한다. 각각의 detailed report와 정확성 검증은 Evidence/case15, case16, case17에 있다.

## 독립 브랜치와 재현

| 항목 | 브랜치 | 구현·검증 커밋 |
|---|---|---|
| ⑭ 공통 기준 | experiment/edge-history-fixed-weight-080 | 8ed4576 |
| ⑮ clipping | experiment/edge-history-source-clipping | 78e7368 |
| ⑯ sampling | experiment/edge-history-source-sampling | 7adb9ae |
| ⑰ blending | experiment/edge-history-source-color-blend | 77f5e57 |

각 항목은 공통 ⑭에서 직접 분기했다. 결과 취합은 코드 통합이 아니다. 브랜치별 `Tools/SMAA/run_source_temporal_component.ps1`과 analyzer를 사용하며, 비교 자료는 `Tools/SMAA/run_source_component_media.py --comparison`으로 생성한다. 검증된 비교 재생 환경은 Pillow12.3.0 / numpy2.3.5 / PyAV15.1.0이다.

원본 PNG 검사에서 Minecraft의 가는 이음선은 ④보다 ⑭~⑰에서 약해지거나 중간이 끊긴 구간이 남았다. 일부 MAE가 낮더라도 얇은 구조 보존과 반짝임 해결을 뜻하지 않는다. 이번 결과는 두 장면의 해당 경로에 한정하며 edge-selective 전체의 보편적 한계로 확대하지 않는다.

GIF·MP4와 원본 프레임 비교는 이 디렉터리의 `comparison.html`에서 확인한다. 원본 캡처의 중복 파일은 SHA256 확인 후 NTFS hardlink로 저장 공간만 줄였고 모든 경로와 바이트를 보존했다. 운영 기록은 `tmp/source-components-dedup.json`에 있다.
