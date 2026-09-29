# ⑥ Spatial SMAA + first-edge temporal: sample-pattern Off ablation

## 범위와 계보

- 브랜치: `experiment/spatial-first-edge-pattern-off`.
- 공통 기준선: `c51ca28` (`e14f122` 원본 기준선 검증 + 프레임 Begin/End 짝 수정).
- 명시적 최소 의존성: `8e5a972` → 이 브랜치의 `1956c1b`. 원본 spatial SMAA를 보존한 ⑥ 구현만 재사용한다.
- ⑤ temporal-only는 별도 기준선 유래 브랜치에서 검증한다. 이 브랜치에 ⑤ 구현을 합치지 않는다.

## 변경

기본값 On인 `SetTemporalSamplePatternEnabled`만 추가한다. Off에서는 projection offset을 `(0,0)`으로 고정하고 공간 처리 호출의 area-texture subsample indices를 `MODE_SMAA_1X`로 선택한다. 모드 변경 시 history를 초기화한다.

원본 edge detection, blending weight, neighborhood blending 셰이더와 native T2X-R resolve 계산은 변경하지 않는다. 카메라/depth velocity 생성, point history sampling, velocity-alpha 혼합 가중치, spatial-frame history ping-pong도 유지한다. 선택식은 기존 첫 패스의 `any(edge.rg > 0)`다. 비선택 픽셀은 현재 공간 SMAA 결과를 출력한다. 렌더 패스, dilation, clipping, resolved-output feedback을 추가하지 않는다.

이 변형은 지터 표본을 누적하는 원본 SMAA T2X와 동일한 기법이 아니다. `PatternOff` ablation으로 명시한다. Intel TSCMAA 전체 재현이나 core 완료로 표현하지 않는다.

## 검증

1. On full/On selective/Off full/Off selective의 네 조건으로 selection과 pattern의 영향을 구분한다.
2. 두 장면 각각 240프레임, 고정 60 Hz, still60/move120/still60. 모든 mode와 cycle 시작 시 history 초기화.
3. 기존 On 두 조건과 AA-Off/진짜 O-1X의 240프레임 파일 hash를 다시 연결한다. Off selective를 독립 mode에서 재실행해 반복 hash를 비교한다.
4. 현재 spatial RGB=진짜 O-1X RGB, full/selected current 동일, selected output=Off full output, nonselected output=current RGB를 매 프레임 확인한다.
5. 실제 Draw에 전달한 camera offset과 CPU 제출 subsample indices를 기록한다. 정지 초반/후반의 고유 RGB 프레임 수, 인접 차이와 mask 전환을 확인한다.
6. 품질은 기존 hash-aligned supersample spatial reference에 대한 공식 CGVQM-2의 이동(60~179) 및 정지 전환(160~219) 구간으로 비교한다. 이것을 절대 고스팅 ground truth로 해석하지 않는다.
7. 성능은 PNG/readback 없는 별도 clean process에서 smoke 후 300 warmup, 4,800프레임×4회 교차 순서로 측정한다. GPU WholeFrame/SMAA/camera/spatial/resolve, wall interval을 따로 기록한다.

정지 떨림 해소, 이동 품질, 속도는 독립 결론으로 보고한다. C 드라이브 여유 공간 때문에 큰 캡처는 D 드라이브에 보관하며 정확한 경로와 hash를 결과 JSON에 남긴다.

## CGVQM 메모리 제한 실행

120프레임의 전체 입력을 한 호출에서 준비하면 이 PC의 2 GiB pagefile 조건에서 분석 프로세스의 private commit이 약 34.1 GB에 도달했다. 시스템의 남은 commit은 약 0.5 GB였고, CUDA 할당 오류로 종료됐다. 이 실행의 점수는 없으며 SMAA 캡처 실패로 분류하지 않는다. 시스템 설정과 공식 CGVQM 소스는 변경하지 않는다.

고정된 공식 CGVQM commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`의 `cgvqm.py`는 `clip_size=min(fps,30)`으로 독립 temporal patch를 처리한다. 60 FPS의 동일 크기 입력에서 120프레임을 60+60으로 나누면 기존의 네 30프레임 patch 구간이 그대로 유지된다. 각 부분의 spatial patch 개수도 동일하므로 mean pooling 점수의 산술평균은 원래 전체 평균과 수학적으로 같다. 부동소수점 reduction 순서 차이는 허용 범위 `0.00002`를 넘지 않아야 한다.

`cgvqm_bounded_window.py`는 공식 runner를 최대 60프레임씩 실행하고 개별 원본 결과를 모두 보존한다. 각 장면의 기존 native 120프레임 점수, 전체 test/reference pixel hash, 무손실 round-trip을 먼저 연결한 후 새 점수를 사용한다. 실제 bridge 오차는 `*-cgvqm.json`에 기록한다. 평가 구간을 줄이거나 frame rate, patch scale, 모델, reference를 바꾸는 방식은 사용하지 않는다.
