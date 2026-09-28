# 현재 색상 출력과 실제 첫-pass edge 읽기 비용 결과

새 두 비교군은 검은 화면 대신 현재 spatial SMAA 색상을 그대로 출력한다.
후보 선택과 T2X 결합은 수행하지 않으며 기존 paired jitter는 유지한다.
따라서 속도 측정용 대조군이며 품질을 유지한 선택적 AA의 완성 결과가 아니다.

## 반복 측정

| 비교군 | Bistro temporal (ms) | Minecraft temporal (ms) |
|---|---:|---:|
| O-T2X-R | 0.033280 | 0.034767 |
| ABL-EdgeReadOne-R | 0.035201 | 0.038460 |
| DIAG-CurrentOutput | 0.019078 | 0.020326 |
| DIAG-CurrentEdge | 0.020422 | 0.023707 |

`CurrentOutput`에는 현재 색상 Point 읽기 1회와 대조용 runtime-zero RG sink가 있다.
`CurrentEdge`에는 같은 현재 색상 읽기와 sink에 실제 first-pass RG Load가 추가된다.
두 출력은 RGB hash가 일치하며 BA는 shader에서 current 값 그대로 통과한다.

- bistro: 현재 색상에 edge 추가 **+0.001343 ms (+7.042%)**. 원본 T2X-R에 edge 추가 +0.001921 ms (+5.773%). CurrentEdge는 원본 temporal보다 -38.636%.
- minecraft: 현재 색상에 edge 추가 **+0.003381 ms (+16.633%)**. 원본 T2X-R에 edge 추가 +0.003693 ms (+10.621%). CurrentEdge는 원본 temporal보다 -31.811%.

위 증가분은 전체 temporal 패스 실행시간 차이로, edge texture의 순수 DRAM 지연이 아니다.
좌표 계산, texture 접근, 의존성, register와 cache 상태 및 cbuffer 대조 입력 차이를 포함한다.
특히 Combined−Native에는 추가 sink가 있고 CurrentEdge−CurrentOutput에는 matched sink가 있으므로
둘의 차이까지 순수한 T2X와 edge의 상호작용이라고 단정하지 않는다.
기존 black-output 실험과 이번 실험은 별도 실행이므로 절대 시간을 직접 빼지 않는다.

## 구현과 검증

두 장면에서 CurrentEdge−CurrentOutput temporal 증가분은 4회 모두 양수였다.
Bistro는 +0.001319~+0.001360 ms, Minecraft는 +0.003330~+0.003433 ms였다.
전체 SMAA 증가분도 각각 +0.001367 ms(+0.697%), +0.003407 ms(+1.258%)이며 4회 모두 양수다.
반면 Bistro WholeFrame은 한 반복에서 CurrentEdge−CurrentOutput이 +0.098215 ms로
크게 변동했다. Resolve 증분은 그 반복에도 +0.001319 ms로 유지됐다.
해당 반복을 삭제하지 않고 모두 보존했으며, 전체 frame/FPS의 개선·악화를 edge 읽기의
효과로 귀속하지 않는다. 이 실험의 결론은 직접 계측한 pass 비용에 한정한다.

- 기존 Original SMAA 공간 세 pass, camera/depth velocity 생성, spatial-frame history
  ping-pong, jitter/subsample pattern 및 공통 resource binding은 유지했다.
- 새 61/62 kind는 기존 temporal pixel pass를 사용한다. 새 pass, texture, copy,
  후보 목록과 edge 선택 분기는 추가하지 않았다. Object motion은 이번 범위에 없다.
- 새 shader는 current t2 Point 읽기 1회만 수행하며, 62에만 t8 RG Load 1회가 추가된다.
  History t4와 velocity t7 읽기, 재투영 좌표, weight/sqrt, temporal blending은 없다.
- DXBC에서 CurrentOutput은 temp 1, CurrentEdge는 temp 2다. 두 shader 모두 RG sink는 mad로
  남고 BA는 current sample의 원래 값이다. DXBC 검사이며 GPU ISA/DRAM 계수 측정은 아니다.
- 원본 spatial/resolve R Off/On 8개 shader bytecode 불변, 기존 combined 실행 명령 불변.
- Release x64 빌드 성공. 두 장면 capture/smoke/benchmark의 완성 보고서와 프로세스 종료 확인.
- Native 20장 RGB PNG의 역사적 capture hash bridge 일치. Combined 20장과 native 일치.
  CurrentOutput/CurrentEdge/기존 current-spatial 진단의 20장씩 RGB hash 일치.
- 실제 raw edge 20장, 총 40,742,400 pixel이 이전 직접 RG 진단과 exact 일치했다.
- 새 CurrentEdge shader에 capture-only scale 1을 넣으면 RG edge가 있는 채널에서만
  양수 변화가 발생하고 B는 불변이다. 모든 프레임에서 실제 읽기 결과의 출력 기여를 확인했다.
  포화/양자화 때문에 모든 edge pixel이 반드시 변해야 한다고 요구하지 않는다.
- 3,360개 rendered-frame jitter/subsample pairing 검사 PASS. PNG에는 alpha가 없으므로
  alpha의 실제 GPU 출력 hash 검증을 했다고 주장하지 않는다.

## 조건과 한계

RTX 3060 Ti / DX11 / Ultra / 1920×1061 / VSync Off / hidden window.
Original SMAA, camera reprojection On 경로, spatial-frame history, paired T2X pattern.
240-frame 고정 경로 (60 still + 120 move + 60 still)를 반복한다.
각 장면은 독립 process에서 30초 예열, mode별 300 warm-up,
4,800 frame × 4회 정순/역순 교차 측정을 수행했다.
PNG 저장, 후보 readback과 CPU 영상 분석은 timing 실행과 분리했다.
같은 프로세스 내 반복이며 여러 날짜/장치에 걸친 검증은 아니다.
Hidden 실행은 engineering pass-cost 결과로 분류하며 논문용 visible-window FPS 결론이 아니다.
Smoke의 짧은 수치로 성능 결론을 내리지 않는다.

현재 색상을 읽고 출력하는 비용을 포함한 진단이지만 전체 화면에서 temporal 안정화를 제거했다.
따라서 원본보다 빠른 정도를 그대로 품질 보존 속도 개선이라고 해석할 수 없다.
실제 edge 선택 시에는 branch와 history/velocity 읽기의 실행 패턴이 달라지므로 후보 비율로
선형 계산할 수 없다. 다음에 선택적 실행을 검토할 때 이 대조군과 이미 구현한 edge-mask
방식을 같은 실행 조건에서 연결하여 별도로 확인해야 한다.

## 자료와 재현

브랜치 `experiment/temporal-current-edge-cost`, 시작점 `4ea2422`.
계획 `1566988`, 구현 및 출력 검증 `92c8493`.
`method.md`, `shader-validation.json`, `*-capture.json`, `*-Smoke.json`,
`*-Benchmark.json`, `tables.md`, `comparisons.json`에 검증/반복별 수치 및 실행 hash를 보존했다.

`validate_temporal_current_edge.py`, Release 빌드 후 `run_temporal_current_edge.ps1`로
Capture/Smoke/Benchmark를 bistro/minecraft 각각 새 process에서 실행한다.
`analyze_temporal_current_edge.py`의 해당 phase/scene과 Summary로 검증·분석한다.
재실행 시 runner의 `-Receipt`, analyzer의 `--receipt` 및 `--output`으로 결과를 분리한다.
원시 PNG/AutoBench/EXE는 Git에 포함하지 않는다.
