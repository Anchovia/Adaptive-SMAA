# 선택률과 선택 위치의 실행 비용 분리

## 범위와 가설

Original SMAA Ultra + camera/depth reprojection On, 원본 paired jitter와 spatial-frame
history를 유지하는 engineering 진단이다. 최종 8-case 또는 TSCMAA 원본 재현이 아니다.
기본 알고리즘, 공간 shader, history 및 resource/pass 개수는 바꾸지 않는다.

2026-09-20 재확인한 Nsight Systems 카운터 조회는 관리자 권한 부족으로 거부됐다.
현재 token은 Administrator=false다. 관리자 실행을 실제로 성공시켰다고 표현하지 않으며,
시스템 카운터 보안 정책을 변경하지 않는다. 일반 GPU timestamp로 가능한 대조부터 수행한다.

기존 실제 대비 선택과 함께, 화면 x 좌표에서 1픽셀 또는 32픽셀 폭의 세로 줄을 번갈아 선택한다.
1920 너비는 두 패턴의 주기 2/64로 나누어지므로 둘 다 매 프레임 정확히 50%다.
선택식은 `((uint(x) >> shift) & 1) == 0`, shift=0/5다. 두 폭은 **동일 shader bytecode**를
사용하며 constant만 바뀐다. 서로 다른 위치의 texture 접근, cache 및 lane 실행이 함께 바뀌므로
시간 차이를 순수 divergence 비용으로 분리했다고 표현하지 않는다. 화면 줄과 실제 warp 배치를
동일시하지 않는다. 대비 판정이 없으므로 실제 대비 알고리즘의 대체품이나 같은 품질도 아니다.

각 폭에서 branch와 flatten을 짝 비교한다. flatten은 전 픽셀의 velocity/history를 읽고 결과만
선택한다. 따라서 출력은 50% 선택이어도 texture 실행 생략은 아니다. 이 대조는 정확한 동일
출력에서 조건부 실행의 순효과를 본다. 실제 대비 경로의 branch/flatten 대조는 기존 Execution
gate에 이미 있으며 본 gate는 공간 배치의 영향을 추가한다.

## 공식 근거

- [Microsoft HLSL if](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if):
  branch/flatten의 조건부 실행과 양쪽 평가 의미. 실제 FXC /O3 산출물을 함께 검사한다.
- [Microsoft SampleLevel](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel):
  조건부 history/velocity는 기존 explicit LOD 0을 재사용한다.
- [NVIDIA 권한 오류 설명](https://developer.nvidia.com/ERR_NVGPUCTRPERM):
  카운터 접근 거부는 GPU 미지원과 구분한다.
- [Nsight Graphics 지원표](https://docs.nvidia.com/nsight-graphics/UserGuide/appendix.html):
  현재 D3D11 shader profiling 지원은 없다. 하드웨어 stall/cache/warp counter는 미측정이다.

## 조건과 검증

- Release x64, DX11, RTX 3060 Ti, 1920×1061, hidden, VSync Off.
- 원본/대비 전체 선택/대비 threshold 0.01과 합성 4 mode = 성능 7 mode.
- capture에는 current-spatial과 실제 대비 mask를 추가: 9 mode×240 frame.
- 동일 fixed 60 Hz, 60 정지+120 이동+60 정지 경로. capture warmup 60, frame 0 seed/phase reset.
- 합성 결과를 매 픽셀 `CPU mask ? native : current-spatial`과 비교한다. branch/flatten hash도
  비교하며 원본/실제 선택/mask/current는 기존 capture에 연결한다. all-selected는 native와 같다.
- GPU 성능은 PNG/readback 및 CPU 영상 분석과 분리. warmup 300, 4,800 frame×3회 정/역/정.
  SMAA/spatial/resolve/WholeFrame/wall 시간과 분포를 기존 계측기로 기록한다.
- clean runner의 독립 프로세스, exit 0, 완성 PASS CSV, 전후 CMAA2 0개가 필요하다.
- 합성 선택의 고스팅/깜빡임 개선을 주장하지 않는다. 기존 대비 선택의 품질 한계는 그대로다.
- 작은 차이는 반복 변동과 불변 spatial control의 변화와 함께 해석한다.

## 재현

Release 빌드 후 `validate_temporal_locality_shaders.py`를 실행한다.
`Tools/SMAA/run_temporal_locality.ps1 -Phase Smoke|Capture|Benchmark -Scene bistro|minecraft`
를 각각 독립 프로세스로 순차 실행한다. 분석은 `analyze_temporal_locality.py`를 사용한다.
원시 CSV/PNG/profiler 자료는 로컬 tmp/AutoBench에만 보존한다.
