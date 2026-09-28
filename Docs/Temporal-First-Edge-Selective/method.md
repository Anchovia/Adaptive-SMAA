# 실제 첫-pass edge 선택과 원본 T2X-R 결합 gate

시작점 `13afeb2`, 브랜치 `experiment/temporal-first-edge-selective`.
Original SMAA / camera reprojection On / Standard native temporal semantics.
최종 8-case를 바꾸지 않는 선택적 coverage ablation이다. TSCMAA 전체 이식이 아니다.

현재 pixel의 기존 첫-pass RG8 edge에서 `any(RG > 0)`인 모든 pixel만 temporal 결합한다.
새 luma proxy, 추가 threshold, Intel suppression, dilation, 후보 목록이나 새 pass를 사용하지 않는다.
현재 색상을 먼저 한 번 읽고 비edge면 반환한다. Edge면 native와 같은 velocity, point history,
velocity-alpha weight 0..0.5 및 lerp를 수행하며 이미 읽은 current를 재사용한다.
원본 paired jitter, subsample index, history reset 및 spatial-frame history는 유지한다.
History는 최종 resolve feedback이 아니므로 각 mode가 다음 프레임의 동일 spatial history를 읽는다.

## 같은 프로세스의 다섯 비교군

| Mode | Kind | 의미 |
|---|---:|---|
| O-T2X-R | 0 | 원본 전체 화면 T2X-R |
| ABL-EdgeReadOne-R | 56 | 원본 + 첫 edge 읽기, 기존 runtime-zero sink |
| DIAG-CurrentEdge | 62 | 현재 spatial 색상 + 첫 edge 읽기, 기존 runtime-zero sink |
| ABL-FirstEdge-Reuse-R | 63 | current를 먼저 읽어 재사용하는 선택적 T2X-R |
| ABL-FirstEdge-Legacy-R | 64 | 예전 edge-mask 함수 본문 그대로 이식한 edge-first 대조군 |

Legacy는 `experiment/standard-t2x-edge-mask`의 함수 이름만 바꾸어 가져온다.
과거와 동일한 선택 규칙을 새 harness에서 재측정하는 것이지 새로운 후보 알고리즘이 아니다.
예전 실행과 해상도/window/harness가 다르므로 그 절대 시간과 직접 차감하지 않는다.
새 두 shader에는 진단용 zero sink가 없다. Selective−CurrentEdge는 sink 유무와 compiler
스케줄도 다른 전체 shader 차이이며 순수 branch 비용으로 부르지 않는다.

Microsoft [if/branch](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if)
및 [Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load)
문서를 확인했다. `[branch]`는 조건별 실행을 요청하고 Load는 integer texel 접근을 사용한다.
이를 속도 보장으로 해석하지 않고 DXBC와 실제 GPU timing으로 검증한다.

## 검증과 측정

- Native 8개 DXBC 및 두 read-only control 명령 불변.
- Legacy 본문 source 일치. 새 selector의 edge Load, 실제 분기 및 조건부 t7/t4 읽기를 확인한다.
- Capture-only current spatial, raw edge와 selective 반복 출력을 추가한다.
  Raw edge의 RGB/직전 control hash bridge와 jitter phase를 검증한다.
- 모든 선택 pixel은 native RGB, 모든 비선택 pixel은 current RGB와 exact 비교한다.
  Legacy/Reuse/Reuse-repeat도 서로 RGB hash 일치해야 한다. PNG는 alpha를 저장하지 않는다.
- 후보 비율은 capture한 10개 frame에서만 집계하며 전체 benchmark 평균으로 표현하지 않는다.
- Release build, 두 장면 sparse capture와 smoke 통과 후 본 측정한다.
- RTX 3060 Ti / DX11 / Ultra / 1920×1061 hidden / VSync Off. 기존 240-frame 경로 유지.
  30초 예열, mode별 300 warm-up, 4,800 frame × 4회 순서 정방향/역방향 교차.
  각 명령은 fresh process, timeout, 완료 PASS 보고서 및 잔류 프로세스 0 확인.
- PNG 저장/후보 readback/CPU 이미지 분석은 본 측정과 분리한다.
- Temporal 및 전체 SMAA 비용을 둘 다 비교한다. 숨김 실행은 engineering 결과이며
  논문용 visible FPS 결과가 아니다. 후보 비율에 비례한 속도 개선을 가정하지 않는다.
- 이번 gate는 선택 연산 정확성과 속도다. 지터가 남아 비후보에서 시간 안정화가 사라지는
  기존 품질 한계를 해결했다고 주장하지 않는다. 정량 품질 평가는 이번 범위 밖이다.
