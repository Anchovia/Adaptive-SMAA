# ⑨ 선행 조회와 현재 edge spatial 처리 결합: 결과

2026-10-05. Branch: `experiment/edge-persistence-eager-spatial-mask`. 구현 커밋: `c68fa78`.

**출력과 temporal 대상은 보존했지만, 전체 AA 시간의 추가 감소에는 실패했다.** 현재 edge만 2차 공간 처리하는 J는 기존 ⑨(F)보다 두 장면 모두 평균 시간이 길었다. 이 조합을 기본 구현으로 채택하지 않고 기존 ⑨를 유지한다. 이 결과는 해당 조합의 실패이며 다른 모든 최적화가 불가능하다는 뜻은 아니다.

방법과 출처는 [method.md](method.md), 원시 실행 기록은 [runs.json](runs.json), 직접 확인한 PNG/연속 프레임은 [visual-inspection.json](visual-inspection.json)에 있다.

## 구현과 비교 조건

| 조건 | 첫 edge 패스 | 2차 spatial weight 패스 | Temporal 대상 |
|---|---|---|---|
| F: 기존 ⑨ | 이전 raw edge 및 point velocity 선행 조회 | current+previous union | 같은 union |
| H: 비용 대조군 | F + current edge=1 / previous-only=0 depth 기록 | 같은 union | 같은 union |
| J: 새 조합 | H와 같은 shader/state | current edge만(depth=1, stencil=1) | 같은 union |
| O: 원본 ④ | 원본 SMAA edge | 원본 weight 처리 | full-screen T2X-R |

H/J는 기존 SMAA 전용 DSV를 재사용한다. Scene depth, raw RG edge, history/velocity 계산은 유지한다. 기존 draw/dispatch/copy 개수에 변화가 없고 새로운 production pass나 texture도 없다. 내부 mode 12/13은 실험 설정이며 새로운 사용자 비교 case 번호가 아니다.

F/H/J는 paired pattern Off, O는 원본 paired projection jitter/subsample pattern On이다. 모두 Original spatial, camera/depth reprojection On, spatial-frame history다. Object motion, Adaptive, dilation, sampler·clipping·혼합 변경을 넣지 않았다. 따라서 ④와의 차이를 오직 edge 선택 효과로 해석하지 않는다.

## 전체 AA와 temporal 시간

RTX 3060 Ti, DX11 Release x64, SMAA Ultra, 1920×1061, hidden, VSync Off. 각 benchmark는 새 clean process에서 30초 준비, mode별 300 warm-up, 4,800프레임×3회와 정방향/역방향 순서 교차를 사용했다. PNG, GPU readback, 실행 query, 세부 spatial timer는 Off다. 모든 변화율의 분모는 같은 실행의 대응 조건이다. 음수는 시간 감소다.

| 장면 | 조건 | 전체 AA ms | 같은 실행 ④ 대비 | Temporal ms | Temporal ④ 대비 |
|---|---|---:|---:|---:|---:|
| bistro | F: 기존 ⑨ | 0.135581 | -14.68% | 0.007641 | -77.26% |
| bistro | H: 표시 비용 대조군 | 0.136912 | -13.84% | 0.007619 | -77.33% |
| bistro | J: 현재 edge만 2차 처리 | 0.136624 | -14.02% | 0.007646 | -77.24% |
| bistro | O: 원본 ④ | 0.158905 | +0.00% | 0.033600 | +0.00% |
| minecraft | F: 기존 ⑨ | 0.229526 | +0.35% | 0.023807 | -31.85% |
| minecraft | H: 표시 비용 대조군 | 0.232568 | +1.68% | 0.023736 | -32.06% |
| minecraft | J: 현재 edge만 2차 처리 | 0.231779 | +1.34% | 0.023848 | -31.74% |
| minecraft | O: 원본 ④ | 0.228722 | +0.00% | 0.034936 | +0.00% |

전체 AA는 준비·공간 처리·camera velocity·temporal resolve와 필요한 기존 리소스 작업을 포함한다. Temporal 열은 resolve 결합 단계만이며 공간 처리나 camera velocity 시간을 포함하지 않는다. WholeFrame/WallFrame, p95/p99 및 분포는 각 장면의 `benchmark.json`에 보존했으며 전체 AA 감소와 혼동하지 않는다.

## 비용 분리와 반복 방향

| 장면 | 비교 | 전체 AA 변화 ms | 평균 변화율 | 반복 0/1/2 변화율 | Paired delta SD ms |
|---|---|---:|---:|---|---:|
| bistro | H−F: 표시 비용 | +0.001332 | +0.982% | +1.714% / +0.463% / +0.778% | 0.000872 |
| bistro | J−H: 2차 실행 제한 | -0.000288 | -0.210% | -0.286% / -0.215% / -0.130% | 0.000107 |
| bistro | J−F: 실제 조합 효과 | +0.001044 | +0.770% | +1.423% / +0.247% / +0.647% | 0.000803 |
| minecraft | H−F: 표시 비용 | +0.003042 | +1.325% | +0.966% / +2.190% / +0.825% | 0.001711 |
| minecraft | J−H: 2차 실행 제한 | -0.000789 | -0.339% | +0.191% / -1.367% / +0.167% | 0.002085 |
| minecraft | J−F: 실제 조합 효과 | +0.002254 | +0.982% | +1.159% / +0.793% / +0.993% | 0.000426 |

3회 반복은 제한된 표본이다. 작은 변화율을 보편적 장치 특성으로 일반화하거나 통계적 유의성을 주장하지 않는다. 채택 기준은 기본 ⑨ 대비 전체 AA 감소였고 이번 조합은 그 기준을 충족하지 못했다.

## 별도 spatial profile

이 표는 별도 프로세스의 960프레임×3회 진단 측정이다. 위 clean timing에 세부 scope를 끼워 넣거나 두 실행의 절대값을 더하지 않는다.

| 장면 | 조건 | Prepare ms | 첫 edge ms | 2차 weight ms | 3차 neighborhood ms | 전체 AA ms |
|---|---|---:|---:|---:|---:|---:|
| bistro | F: 기존 ⑨ | 0.008038 | 0.027242 | 0.025070 | 0.044587 | 0.136316 |
| bistro | H: 표시 비용 대조군 | 0.008071 | 0.027639 | 0.025049 | 0.044590 | 0.136699 |
| bistro | J: 현재 edge만 2차 처리 | 0.008020 | 0.027695 | 0.024833 | 0.044595 | 0.136563 |
| bistro | O: 원본 ④ | 0.008039 | 0.026980 | 0.024515 | 0.042092 | 0.158858 |
| minecraft | F: 기존 ⑨ | 0.007951 | 0.034732 | 0.087965 | 0.052261 | 0.230720 |
| minecraft | H: 표시 비용 대조군 | 0.007946 | 0.037966 | 0.087764 | 0.051994 | 0.233411 |
| minecraft | J: 현재 edge만 2차 처리 | 0.007951 | 0.038051 | 0.086799 | 0.052180 | 0.232743 |
| minecraft | O: 원본 ④ | 0.007930 | 0.027922 | 0.085659 | 0.049120 | 0.229546 |

같은 H/J shader를 쓰므로 H−F는 depth 출력과 관련 GPU 상태의 추가 비용을 측정한다. J−H는 이미 표시 비용을 지불한 뒤의 2차 실행 제한 효과다. 첫 edge 증가와 2차 감소를 구분해야 한다. `SV_Depth`에 따른 hardware Early-Z 변화가 가능한 원인이라는 문헌 근거는 있으나, 실제 stall·캐시·occupancy 원인을 Nsight counter로 확정한 결과는 아니다.

- bistro: J−F 첫 edge **+0.000453ms**, 2차 weight **-0.000238ms**. 실제 2차 실행 대상은 줄었으나 첫 패스 비용이 절감분보다 컸다.
- minecraft: J−F 첫 edge **+0.003319ms**, 2차 weight **-0.001166ms**. 실제 2차 실행 대상은 줄었으나 첫 패스 비용이 절감분보다 컸다.

## GPU 실행 대상과 출력 검증

두 장면 각각 F/H/J/O의 240-frame 무손실 RGB를 비교했다. H/J−F mismatch 0이고 F/O는 보존된 `eef2ac6` 캡처와도 mismatch 0이다. Selective 조건마다 43개 실제 draw의 raw RG edge/current spatial/velocity DDS, temporal coverage, 비선택=current spatial, weight·resolve GPU query가 PASS했다.

| 장면 f131 | F/H 2차 passing samples | J 2차 passing samples | 감소율 | F/H/J temporal passing samples |
|---|---:|---:|---:|---:|
| bistro | 69,519 | 52,848 | -23.98% | 69,519 |
| minecraft | 652,244 | 520,091 | -20.26% | 652,244 |

Passing sample 감소를 모든 shader invocation 감소나 같은 비율의 시간 감소로 해석하지 않는다. Helper/quad 실행과 GPU 실행 특성의 차이를 고려해 invocation count도 `capture.json`에 별도로 보존했다. Release 빌드와 모든 입력 종류의 결합 shader 컴파일 PASS, 보존 대조군 DXBC 일치도 확인했다.

## 직접 프레임 검사와 품질 해석

두 장면의 F/H/J 원본 전체 f131 PNG와 이동 f130–135, 이동→정지 f178–183, 정지 f190–195의 연속 6프레임 ROI를 직접 열었다. ROI는 Bistro 의자/테이블 다리 `(1230,582,1358,670)`, Minecraft 벽 이음선 `(956,524,1020,620)`이며 nearest 3×, 색상 보정 없이 비교했다.

모든 비교 조건에서 같은 픽셀과 기존 결함이 보인다. Bistro의 가는 어두운 다리는 이동 중 연결/출현 상태가 변하고, Minecraft 이음선의 연결이 이동/전환 구간에서 끊어지는 구조 보존 실패가 그대로 남는다. 이번 변경이 반짝임·고스팅·선 소실을 개선했다거나 원본 ④와 품질이 동등하다고 결론 내리지 않는다. 측정한 240프레임에서 ⑨ 대비 화면 변경이 없다는 결과다. CGVQM을 새로 실행하거나 새 품질 개선 점수로 재사용하지 않았다.

- [Bistro 이동 연속 6프레임](inspection/bistro-moving-six-frames.png), [전환](inspection/bistro-transition-six-frames.png), [정지](inspection/bistro-still-six-frames.png).
- [Minecraft 이동 연속 6프레임](inspection/minecraft-moving-six-frames.png), [전환](inspection/minecraft-transition-six-frames.png), [정지](inspection/minecraft-still-six-frames.png).
- [Bistro 60fps 비교 영상](inspection/bistro-frames-120-203-60fps.mp4), [Minecraft 60fps 비교 영상](inspection/minecraft-frames-120-203-60fps.mp4): f120–203, 84프레임, 정확한 frame 수와 1/60 PTS decode 검증. 영상은 제작·decode 검증했으며 재생을 보았다고 기록하지 않는다. 품질 판정은 무손실 원본과 연속 정지 프레임에 근거한다.

## 기록과 결론

전체 11개 실행은 같은 EXE 및 shader hash로 정상 완료했다. 각 실행 전후 CMAA2 잔류 프로세스 0, wall-clock timeout, 완성된 PASS CSV 조건을 clean runner가 적용했다. 실패/재시도 실행은 없었다. 보존 CSV는 원시 바이트의 SHA-256을 유지하고 Git에서 줄바꿈/공백 정규화를 끈다.

**기존 ⑨를 유지한다.** H/J는 독립 실험 브랜치의 negative-result 설정으로 보존한다. 현재 edge만 2차 spatial 처리하는 것 자체는 기능적으로 가능하지만, 이번 depth 표시 구현은 전체 비용을 줄이지 못했다. Native ④ 대비 현재 성능 목표 및 기존 ⑨의 품질 한계는 그대로이며, temporal 식·패스 수·후보 확장으로 질문을 바꾸지 않는다.
