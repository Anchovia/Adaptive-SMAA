# ⑰: ⑭에서 색 혼합만 분리한 실험

브랜치와 기준 커밋은 case.json에 기록한다. ⑮ clipping / ⑯ history sampling / ⑰ 색 혼합이 이번 작업의 번호다. ⑭ 문서 끝의 과거 예정 번호는 현재 분류에 적용하지 않는다. 세 브랜치는 모두 완료된 ⑭에서 직접 분기하며 누적 결합하지 않는다.

⑭의 Original SMAA Ultra, 현재 또는 camera-reprojected 직전 raw edge의 합집합, hardware stencil 선택, Pattern Off, normalized 5-fetch RGB, fixed history 0.8 및 resolved RGB/current-spatial alpha feedback을 유지한다. Camera/depth reprojection만 사용한다. 비선택 픽셀은 spatial 결과 그대로이며 first/reset의 history invalid 프레임은 기존 ⑭ seed 경로를 사용한다. 새 production pass, copy, texture는 없다. 기본 Off이다.

확보 Intel TAA_Edge.hlsl의 blend는 encoded RGB를 제곱해 weighted sum을 만든 뒤 sqrt한다. SMAA의 current/history SRV와 visible/history RTV는 sRGB 변환을 사용해 shader sample은 이미 linear RGB다. 이 값에 직접 제곱을 적용하면 원본의 색 공간 의미와 달라진다.

⑰는 sample된 linear RGB를 standard sRGB 식으로 encoded 값에 변환하고, 원본 gamma2 square/sqrt 혼합을 수행한 뒤 다시 linear RGB로 바꿔 기존 sRGB RTV에 출력한다. Filter는 ⑭의 linear-domain normalized5-fetch 그대로다. 유효 encoded 입력을 위해 RGB0..1 범위 제한을 포함한다. 이는 sampler/domain 변경을 섞지 않은 blend-function adapter이며 원본 UNORM 파이프라인 전체 포팅은 아니다. 정확한 기존 linear blend를 gamma2 근사로 바꾸는 것이므로 단순히 원본 식을 가져오면 품질이 올라간다고 가정하지 않는다. 색 공간 변환 ALU 비용도 포함해 측정한다.

[Microsoft Direct3D11 규격의 sRGB 변환 및 view 의미](https://microsoft.github.io/DirectX-Specs/d3d/archive/D3D11_3_FunctionalSpec.htm)는 자동 decode/encode 확인의 근거다. SourceTemporalMath.hlsli에 실제 함수가 있고 production과 GPU fixture가 공유한다.

정확성: 28개 기존 entry의 DXBC byte 일치, 새 4 entry compile, GPU helper 2,112 위치의 원색·상수·random·thin-line·화면 밖 clamp 경계 fixture와 독립 CPU 식, 두 장면 seed/reset 및 feedback/alpha/nonselected/selection 검증. 실장면 캡처에서 selected weight는 양쪽 모두 0.8이고 common input/mask가 byte 일치해야 한다.

품질: 같은 240 frame/pose의 ④·⑭·⑰를 캡처한다. ④·⑭ 기존 RGB hash와 각 240 frame을 bridge한다. Supersample spatial proxy MAE/PSNR, 이동/전환/정지의 raw temporal difference는 보조 지표이며 CGVQM 또는 temporal ground truth라고 부르지 않는다. 원본 full-frame 및 nearest 2배 연속 6 frame 검사와 GIF/60fps 영상을 별도로 생성한다. Pattern On ④와 Off 실험의 차이를 색 혼합 하나의 효과로 해석하지 않는다.

성능: 동일 binary의 별도 clean process Smoke 후 scene당 clean benchmark. PNG/query/readback Off, hidden/VSync Off, 30s precondition, 300 warm-up 및 4,800 frame×6회, mode 순서 정/역 교차. Spatial/Camera/Resolve/AA total을 분리하고 변화율은 같은 run의 ④와 ⑭로 계산한다. 각 명령 전후 CMAA2 프로세스 0개를 검사한다. GPU 다른 작업 없음은 사용자 확인 상태이다.

GPU fixture는 실제 helper와 독립 CPU 변환식을 비교하고 current==history 입력의 identity도 검사한다. Negative/overshoot sampled 값의 범위 제한을 명시하며 neighborhood history clipping이라고 부르지 않는다. Source coefficient와 sampled domain이 다르므로 전체 원본 TSCMAA 결과와 동일하다는 주장을 하지 않는다.

재생 자료 생성은 `Tools/SMAA/run_source_component_media.py`를 bundled Python으로 실행한다. 검증된 환경은 Pillow12.3.0 / numpy2.3.5 / PyAV15.1.0이다. 기존 venv의 PyAV만 가져오고 bundled 이미지 라이브러리를 유지한다. 이전 streaming 환경의 제외 기록은 excluded-media-attempts.json에 보존했다. 원본 PNG와 GPU 품질·성능 자료는 변경하지 않았다.
