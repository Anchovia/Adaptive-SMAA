# ②·④·⑤·⑥ 실제 first-pass edge 비교

검증 브랜치: `validation/native-first-pass-edge-visuals`. 수정된 ② 기준선 `15fb796bac3be602ba88727a4593f9fcc033088d`에서 직접 분기했다. ② 및 같은 기준선에 포함된 원본 ④ 대조군의 렌더링 후 실제 GPU edge 텍스처를 읽는 진단 API만 추가했다. ⑤·⑥ 구현을 합치지 않았으며 해당 독립 브랜치의 보존된 RG/coverage 캡처를 재사용했다.

Bistro/Minecraft 각각 frame 100~219에서 **②=⑤=⑥의 RG 원본 데이터가 120/120 frame 모두 byte 단위로 일치**했다. 합계 240 frame이며 흑백 표시만 같은 것이 아니라 두 edge 채널 모두 같다. ④는 원본 paired jitter On으로 다른 표본 위치에서 검출한다. frame 190~219 정지 구간에서 각 장면의 edge 패턴은 ②/⑤/⑥ 각 1개, ④는 2개였다.

④의 edge는 공간 SMAA의 첫 패스 결과이며 temporal 실행 마스크가 아니다. 원본 ④는 전체 화면 temporal을 수행한다. ②는 temporal이 없고, ⑤·⑥에서만 이 edge와 temporal 실행 coverage가 일치한다.

정확성: 새 ②·④ 및 ② 반복의 1,440개 최종 RGB frame이 기존 수정 기준선 해시와 일치했다. ⑤·⑥의 480개 RGB bridge와 480개 edge/실행 coverage 비교도 통과했다. ② 반복 edge 240 frame 일치, 원본 SMAA.cpp/HLSL 소스 불변을 확인했다. 기존 독립 branch ④의 RGB 해시를 사용해 기준선 안의 ④ 대조군과 연결했다.

시각화: 흰색은 실제 RG 중 하나 이상이 0보다 큰 픽셀이다. RGB 재검출·Sobel·확장·threshold 변경은 없다. 원본과 같은 frame/crop, 2배 nearest-neighbor 확대, 이동 0.5배속·이동→정지 0.25배속이다. 고정 회색조 GIF의 모든 decode frame이 렌더한 마스크와 일치했다. 색상은 기존 6-way 자료를 그대로 사용하며, 아래 실제 edge는 ②④ / ⑤⑥ 배치다. 앱의 독립 GIF 재생 시작은 동기화를 보장하지 않는다.

이 자료가 요청된 내부 edge 비교다. 이전 6-way Sobel 자료는 최종 출력의 윤곽 표시일 뿐 내부 edge의 동일성 판단 근거로 사용하지 않는다. 새 품질 점수나 성능 결과는 만들지 않았다.

| 장면 | ②=⑤ RG 동일 | ②=⑥ RG 동일 | ②·④ edge XOR 평균(전체 화면) |
|---|---:|---:|---:|
| bistro | 120/120 | 120/120 | 1.6620% |
| minecraft | 120/120 | 120/120 | 12.9741% |

## Bistro · 의자 다리 / 이동

![기존 ①~⑥ 색상 비교](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/six-way.gif)

![실제 ②·④·⑤·⑥ first-pass edge](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/native-first-pass-edge-20260930/bistro-chairs-moving-actual-edges.gif)

## Minecraft · 얇은 경계 / 이동

![기존 ①~⑥ 색상 비교](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/six-way.gif)

![실제 ②·④·⑤·⑥ first-pass edge](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/native-first-pass-edge-20260930/minecraft-thin-edges-moving-actual-edges.gif)

## Bistro · 창살 / 이동 → 정지

![기존 ①~⑥ 색상 비교](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/six-way.gif)

![실제 ②·④·⑤·⑥ first-pass edge](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/native-first-pass-edge-20260930/bistro-window-stop-actual-edges.gif)

## 실행·출처

Release x64, DX11, Ultra, 1920×1061, fixed60; 기존 still60/move120/still60 경로. 장면별 새 clean process를 사용했다. Bistro 정상 실행은 20260930_214725, Minecraft 정상 실행은 20260930_215306이다. Minecraft 첫 실행 20260930_214953은 셰이더 시작 대기로 캡처 없이 멈춰 제외했고, 해당 PID만 종료한 뒤 같은 실행파일·설정으로 재실행했다. 제외 기록은 excluded-startup.json에 있다. 정상 실행 후 CMAA2 잔류 프로세스는 0개다.

상세 픽셀 수·RG 해시·출처와 실행파일/리포트 해시는 장면별 analysis.json 및 run.json에 기록했다. ⑤·⑥ 및 기존 색상 자료의 pinned provenance는 2b3ca2f의 Docs/Six-Case-Stencil-Lifecycle이다. 원시 이미지·GIF·AutoBench는 Git에 넣지 않았다.

재현: Tools/SMAA/build_baseline.py로 빌드하고 Tools/SMAA/run_native_first_pass_edges.ps1에서 장면별 독립 캡처 후 analyze_native_first_pass_edges.py --scene bistro 또는 --scene minecraft로 검증·GIF 생성을 수행한다. 캡처용 readback은 일반 렌더링과 기존 benchmark에서 실행되지 않는다.
