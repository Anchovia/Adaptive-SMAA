# ⑯: ⑭에서 history sampling만 분리한 실험

브랜치와 기준 커밋은 case.json에 기록한다. ⑮ clipping / ⑯ history sampling / ⑰ 색 혼합이 이번 작업의 번호다. ⑭ 문서 끝의 과거 예정 번호는 현재 분류에 적용하지 않는다. 세 브랜치는 모두 완료된 ⑭에서 직접 분기하며 누적 결합하지 않는다.

⑭의 Original SMAA Ultra, 현재 또는 camera-reprojected 직전 raw edge의 합집합, hardware stencil 선택, Pattern Off, fixed history 0.8 및 resolved RGB/current-spatial alpha feedback을 유지한다. Camera/depth reprojection만 사용한다. 비선택 픽셀은 spatial 결과 그대로이며 first/reset의 history invalid 프레임은 기존 ⑭ seed 경로를 사용한다. 새 production pass, copy, texture는 없다. 기본 Off이다.

확보 Intel Util.hlsl의 BicubicTextureSample 5-fetch 좌표와 계수식을 별도 helper로 가져온다. ⑭의 정규화한 cross5-fetch를 대체하고, 원본의 (A+B) 비대칭 항도 의도적으로 보존한다. 이 항을 수정하는 별도 실험을 섞지 않는다. 원본의 RGB UNORM 입력과 border addressing은 변경하지 않은 SMAA 파이프라인의 linear RGB/clamp와 다르므로 전체 원본 sampling의 pixel-exact 포팅이 아니다. Point alpha와 fixed0.8, 후보 coverage, feedback을 그대로 유지한다.

정확성: 28개 기존 entry의 DXBC byte 일치, 새 4 entry compile, GPU helper 2,624 위치의 원색·상수·random·thin-line·화면 밖 clamp 경계 fixture와 독립 CPU 식, 두 장면 seed/reset 및 feedback/alpha/nonselected/selection 검증. 실장면 캡처에서 selected weight는 양쪽 모두 0.8이고 common input/mask가 byte 일치해야 한다.

품질: 같은 240 frame/pose의 ④·⑭·⑯를 캡처한다. ④·⑭ 기존 RGB hash와 각 240 frame을 bridge한다. Supersample spatial proxy MAE/PSNR, 이동/전환/정지의 raw temporal difference는 보조 지표이며 CGVQM 또는 temporal ground truth라고 부르지 않는다. 원본 full-frame 및 nearest 2배 연속 6 frame 검사와 GIF/60fps 영상을 별도로 생성한다. Pattern On ④와 Off 실험의 차이를 sampling 하나의 효과로 해석하지 않는다.

성능: 동일 binary의 별도 clean process Smoke 후 scene당 clean benchmark. PNG/query/readback Off, hidden/VSync Off, 30s precondition, 300 warm-up 및 4,800 frame×6회, mode 순서 정/역 교차. Spatial/Camera/Resolve/AA total을 분리하고 변화율은 같은 run의 ④와 ⑭로 계산한다. 각 명령 전후 CMAA2 프로세스 0개를 검사한다. GPU 다른 작업 없음은 사용자 확인 상태이다.

GPU fixture의 random texture 오차는 source16 약0.010134, 동일 sampler의 case14 control 약0.010195이다. Texel center 64개에서 source/control RGB 차이는 모든 fixture 0이며 상수·원색을 보존한다. 단순히 PASS를 위해 허용값을 늘리지 않고 기존 case13 필터 검증의 1/64 보간 정밀도 witness와 동일 control을 재검사했다. CPU ideal sampling과 hardware 결과는 byte-exact가 아니다. 초기 0.006 assertion 실패는 numeric-gpu-audit.json의 최종 값과 이 설명으로 보존한다. Shader 식은 이 검토 과정에서 바꾸지 않았다.
