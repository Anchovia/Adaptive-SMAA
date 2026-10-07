# ⑮: ⑭에서 history clipping만 분리한 실험

브랜치와 기준 커밋은 case.json에 기록한다. ⑮ clipping / ⑯ history sampling / ⑰ 색 혼합이 이번 작업의 번호다. ⑭ 문서 끝의 과거 예정 번호는 현재 분류에 적용하지 않는다. 세 브랜치는 모두 완료된 ⑭에서 직접 분기하며 누적 결합하지 않는다.

⑭의 Original SMAA Ultra, 현재 또는 camera-reprojected 직전 raw edge의 합집합, hardware stencil 선택, Pattern Off, normalized 5-fetch RGB, fixed history 0.8 및 resolved RGB/current-spatial alpha feedback을 유지한다. Camera/depth reprojection만 사용한다. 비선택 픽셀은 spatial 결과 그대로이며 first/reset의 history invalid 프레임은 기존 ⑭ seed 경로를 사용한다. 새 production pass, copy, texture는 없다. 기본 Off이다.

확보한 Intel Util.hlsl ClipColor의 3×3 YCoCg moment와 gamma=1 범위 제한을 참고한다. 현재 spatial 이웃 8개를 추가로 읽고 중심은 이미 읽은 값을 재사용한다. μ와 σ를 계산해 history YCoCg를 μ±σ에 clamp한 뒤 RGB로 되돌린다. SourceTemporalMath.hlsli가 실제 resolve와 GPU fixture에 공통으로 포함된다.

원본은 signed chroma를 max(0) 처리하고 YCoCg box 양 끝을 RGB로 변환해 RGB min/max로 사용하는 문제가 있었다. 원본 그대로의 공식 포팅이라고 표현하지 않는다. signed chroma 보존, max(variance,0), YCoCg 안에서의 clamp가 안전성 수정이다. Sharpen을 끄고 gamma1을 고정해 clipping과 sharpening 효과를 섞지 않는다. 원본 UNORM/border 대신 SMAA의 linear sample/clamp 규칙을 유지한다.

[Salvi의 temporal supersampling 발표](https://developer.download.nvidia.com/gameworks/events/GDC2016/msalvi_temporal_supersampling.pdf)는 history의 neighborhood 제한을 검토하는 보조 근거다. 여기서는 recovered-source의 component clamp를 사용하며 발표의 ray-box clipping을 동일하게 구현했다고 하지 않는다.

정확성: 28개 기존 entry의 DXBC byte 일치, 새 4 entry compile, GPU helper 2,112 위치의 원색·상수·random·thin-line·화면 밖 clamp 경계 fixture와 독립 CPU 식, 두 장면 seed/reset 및 feedback/alpha/nonselected/selection 검증. 실장면 캡처에서 selected weight는 양쪽 모두 0.8이고 common input/mask가 byte 일치해야 한다.

품질: 같은 240 frame/pose의 ④·⑭·⑮를 캡처한다. ④·⑭ 기존 RGB hash와 각 240 frame을 bridge한다. Supersample spatial proxy MAE/PSNR, 이동/전환/정지의 raw temporal difference는 보조 지표이며 CGVQM 또는 temporal ground truth라고 부르지 않는다. 원본 full-frame 및 nearest 2배 연속 6 frame 검사와 GIF/60fps 영상을 별도로 생성한다. Pattern On ④와 Off 실험의 차이를 clipping 하나의 효과로 해석하지 않는다.

성능: 동일 binary의 별도 clean process Smoke 후 scene당 clean benchmark. PNG/query/readback Off, hidden/VSync Off, 30s precondition, 300 warm-up 및 4,800 frame×6회, mode 순서 정/역 교차. Spatial/Camera/Resolve/AA total을 분리하고 변화율은 같은 run의 ④와 ⑭로 계산한다. 각 명령 전후 CMAA2 프로세스 0개를 검사한다. GPU 다른 작업 없음은 사용자 확인 상태이다.
