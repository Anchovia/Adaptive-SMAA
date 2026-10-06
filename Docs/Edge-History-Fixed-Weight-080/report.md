# ⑭: TSCMAA 문서 history 가중치 0.8 단독 실험 결과

구현·정확성 검사·두 장면 반복 성능 측정·품질 프레임 검사와 확인용 영상 제작을 완료했다. 가중치 변경만으로 선 단절·반짝임 해결이나 최종 품질 우위를 확인하지 못했다. 실험 완료와 개선 성공을 구분한다.

브랜치 `experiment/edge-history-fixed-weight-080`, 기준 ⑬ `ebe68da448c79fb468dc55684d744a5eaf854788`, 구현 커밋 `1331eae`.

## 구현과 비교 조건

|번호|선택·pattern|history RGB / feedback|history 가중치|
|---|---|---|---|
|④ 원본 O-T2X-R|전체 화면 / On|point / spatial frame|원본 velocity-alpha adaptive 0..0.5|
|⑬|현재 OR 재투영 직전 raw edge / Off|normalized 5-fetch Catmull–Rom / resolved RGB, spatial alpha|원본 adaptive 0..0.5|
|⑭|⑬과 동일|⑬과 동일|고정 0.8|

모두 Original SMAA Ultra와 camera/depth reprojection을 사용한다. ⑭는 `0.2*current + 0.8*history`로 누적하며 비선택 픽셀은 current spatial RGB를 유지한다. 원본 velocity-alpha 기반 가중치 감쇠도 고정값으로 대체하므로 단순 0.5→0.8 배율 변경으로 해석하지 않는다. invalid history/reset seed는 기존 규칙을 유지한다. ⑬ 대비 새 production pass/copy/texture는 0개이며 clipping·후보 확장·object motion·previous-depth rejection은 넣지 않았다. Default Off다.

가중치 출처는 [Intel TSCMAA 문서](https://www.intel.com/content/dam/develop/external/us/en/documents/tscmaa-codesample-v1.pdf)의 0.8이다. 확보 원본 소스의 활성 계수 약 0.789473712와 동일한 수치는 아니다. ④↔⑭는 pattern, sampler, coverage와 feedback 차이도 있으므로 원인 비교는 ⑬↔⑭로 제한한다.

## 성능

RTX 3060 Ti, DX11 Release x64, Ultra, 1920×1061, hidden, VSync Off. 장면마다 새 독립 프로세스에서 30초 precondition, mode당 300 warm-up + 4,800프레임×6회, 정/역순 교차 측정했다. PNG·diagnostic query·readback Off, pass timestamp On. 두 장면 Smoke/Benchmark PASS, 전후 잔류 CMAA2 0개다. 숨긴 창의 중간 GPU scope 비교이며 최종 visible 8-case/FPS 결과가 아니다.

음수는 시간 감소다. 비율은 같은 run의 대응 기준으로 계산한 여섯 변화율의 평균이다. 전체 AA에는 공간·edge 선택/feedback 준비·camera velocity·resolve가 포함된다.

|장면|번호|전체 AA ms|④ 대비|temporal ms|temporal ④ 대비|전체 AA ⑬ 대비|
|---|---|---:|---:|---:|---:|---:|
|bistro|4|0.157184|+0.00%|0.033425|+0.00%|+7.47%|
|bistro|13|0.146263|-6.95%|0.010237|-69.37%|+0.00%|
|bistro|14|0.146461|-6.82%|0.010441|-68.76%|+0.14%|
|minecraft|4|0.225783|+0.00%|0.034807|+0.00%|-8.38%|
|minecraft|13|0.246425|+9.14%|0.034969|+0.47%|+0.00%|
|minecraft|14|0.246611|+9.23%|0.035055|+0.71%|+0.08%|

⑭−⑬ paired Student-t 95% 구간(df5, 다중 비교 보정 없음):

- bistro: 전체 AA +0.136% / [-0.20141902749331184, 0.47308927673325696]; temporal +1.985% / [0.5879043079655992, 3.3827682949811537].
- minecraft: 전체 AA +0.079% / [-0.7804496541732872, 0.938443576687675]; temporal +0.262% / [-1.7994295550385961, 2.324205440149532].

각 여섯 반복은 한 프로세스 안의 반복이며 독립 세션 여섯 개가 아니다. Median/p95/p99/stddev/WholeFrame/wall/1% low와 run별 값은 `*-benchmark.json`, `*-performance-runs.csv`에 보존했다.

## 정확성 및 품질

기존 24 shader entry의 DXBC byte 동일, 신규 4 entry compile PASS다. 두 장면 각각 test 6프레임 및 capture 43 same-draw trace에서 input/raw edge/velocity/coverage 동일, 선택 가중치 0.8·비선택 0, 비선택 RGB=current spatial, feedback RGB=visible 및 alpha=current spatial, 연속 history chain과 reset을 검증했다. ④·⑬ 두 control은 각 장면 240 RGB 프레임 모두 기존 ⑬ 기록과 일치했다.

원본 무손실 PNG/nearest 2배 연속 sheet를 직접 확인했다. 상세 frame/ROI와 관찰은 `inspection.md`에 있다. 이동 f126–131, 전환 f178–183, post-stop f190–195 및 수렴한 정지 f210–215를 구분한다. 영상 재생을 직접 관찰한 검사로 표현하지 않는다.

⑭의 일부 무늬 변화는 완만하지만 Minecraft 얇은 이음선의 강약·단절과 Bistro 가는 의자 구조의 프레임 변화가 남는다. 일부 선 대비가 약해 보이는 프레임도 있으므로 구조 보존 성공으로 판정하지 않는다. 약한 잔디 윗면 이음선은 선택 영역 밖인 위치가 있어 weight만 바꾸어 해결되지 않는다.

아래는 supersample spatial proxy 대비 보조 지표다. Raw luma 2차 시간 차분에는 카메라 이동·흐림이 포함되므로 절대 반짝임/고스팅 점수가 아니다.

|장면·ROI|번호|이동 reference RGB MAE ↓|raw luma 2차 시간 차분|
|---|---|---:|---:|
|bistro thin-chair|4|4.38151|4.58969|
|bistro thin-chair|13|5.38230|3.02507|
|bistro thin-chair|14|5.24429|2.24337|
|minecraft thin-seam|4|1.62650|2.85116|
|minecraft thin-seam|13|1.23416|2.77546|
|minecraft thin-seam|14|1.36893|2.40410|
|minecraft leaves|4|3.34791|10.33975|
|minecraft leaves|13|3.06935|11.79819|
|minecraft leaves|14|3.43061|9.73238|
|minecraft grass-seam|4|2.05283|5.18364|
|minecraft grass-seam|13|1.80855|5.73565|
|minecraft grass-seam|14|2.06854|5.14838|

f180부터 카메라가 정지한다. 전체 RGB 마지막 변경 frame:

- bistro: ④ f182, ⑬ f189, ⑭ f209.
- minecraft: ④ f182, ⑬ f189, ⑭ f208.

⑭의 정지 후 수렴은 느려졌다. 이 whole-RGB 변화 지속을 절대 ghosting 지속 frame으로 해석하지 않는다. 별도 object motion/가려짐 해제 ground truth와 CGVQM-2 모델 재실행은 이번 ⑭에서 수행하지 않았다. 기존 다른 출력의 점수를 ⑭ 점수로 재사용하지 않는다.

## 확인 자료와 보존

[④·⑬·⑭ 비교 갤러리](C:/Users/USER/Desktop/research/Deliverables/SMAA_14_Quality_20261006/comparison.html): 두 장면 240 실제 프레임, 60fps 영상 4초, 느린 25fps GIF 9.6초. ROI 7개, GIF 7개, crop 영상 7개, 전체 경로 영상 2개. 반복·보간으로 길이를 늘리지 않았다. 모든 GIF decoded pixel hash와 MP4 frame count/rate/PTS를 검증했다. 손실 확인용 GIF/MP4와 무손실 PNG를 구분한다.

⑭는 단독 가중치 실험 기록으로 보존하며 기본 구현이나 최종 8-case를 변경하지 않는다. ⑮ 후보식·⑯ clipping·⑰ sampling/color blending은 아직 구현하지 않았다. 출처·기준 버전은 `method.md`, 재현 정보는 `provenance.json`, 원본 경로와 hash/ROI/프레임은 `*-capture.json`, 영상 확인은 `*-media-240.json`에 있다. Build binary·raw PNG/DDS·GIF/MP4·AutoBench 원시 파일은 Git에 올리지 않는다.
