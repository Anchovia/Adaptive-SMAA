# 여섯 구성의 동기화 GIF 비교

수정된 stencil 기준선의 2026-09-30 실제 캡처로 생성했다. 각 GIF는 같은 source frame의 같은 화면 고정 영역을 사용한다. 배치는 ①② / ③④ / ⑤⑥이다. ③·④는 지터 On, ⑤·⑥은 Off다.

원본 RGB에 밝기·색상 보정이나 시간 보간을 하지 않았다. 2배 확대는 nearest-neighbor다. GIF는 모든 시간·구성에 같은 256색 팔레트와 dither Off를 사용한다. 색 양자화가 있으므로 미세한 색 차이는 인접 원본 RGB PNG와 함께 확인한다. MP4는 원래 60fps의 재생용 H264 CRF10이며 무손실 근거로 사용하지 않는다.

이동 구간은 0.5배속, 이동→정지 구간은 0.25배속이다. source frame 180에서 카메라가 정지하고, 반복 재생 끝에서는 시작 frame으로 돌아간다. 화면 고정 crop이므로 이동 물체를 추적한 영상은 아니다. 고스팅이 반드시 발생했다는 주장이나 새 품질 점수는 포함하지 않는다.

## Bistro · 의자 다리 / 이동

Source frames 100~159, crop [1190, 530, 1478, 722].

[여섯 구성 비교 GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/six-way.gif) · [60fps 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/six-way-60fps.mp4) · [인접 원본 RGB](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/adjacent-original-rgb.png)

개별 GIF: [① AA-Off](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/case1.gif) · [② SMAA 1X](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/case2.gif) · [③ Temporal-only](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/case3.gif) · [④ SMAA T2X-R](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/case4.gif) · [⑤ Edge temporal-only](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/case5.gif) · [⑥ SMAA + edge temporal](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-chairs-moving/case6.gif)

## Minecraft · 얇은 경계 / 이동

Source frames 100~159, crop [780, 460, 1068, 652].

[여섯 구성 비교 GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/six-way.gif) · [60fps 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/six-way-60fps.mp4) · [인접 원본 RGB](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/adjacent-original-rgb.png)

개별 GIF: [① AA-Off](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/case1.gif) · [② SMAA 1X](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/case2.gif) · [③ Temporal-only](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/case3.gif) · [④ SMAA T2X-R](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/case4.gif) · [⑤ Edge temporal-only](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/case5.gif) · [⑥ SMAA + edge temporal](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-thin-edges-moving/case6.gif)

## Minecraft · 나뭇잎 / 이동 → 정지

Source frames 160~219, crop [1180, 770, 1468, 962].

[여섯 구성 비교 GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-leaves-stop/six-way.gif) · [60fps 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-leaves-stop/six-way-60fps.mp4) · [인접 원본 RGB](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-leaves-stop/adjacent-original-rgb.png)

개별 GIF: [① AA-Off](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-leaves-stop/case1.gif) · [② SMAA 1X](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-leaves-stop/case2.gif) · [③ Temporal-only](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-leaves-stop/case3.gif) · [④ SMAA T2X-R](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-leaves-stop/case4.gif) · [⑤ Edge temporal-only](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-leaves-stop/case5.gif) · [⑥ SMAA + edge temporal](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/minecraft-leaves-stop/case6.gif)

## Bistro · 창살 / 이동 → 정지

Source frames 160~219, crop [880, 430, 1168, 622].

[여섯 구성 비교 GIF](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/six-way.gif) · [60fps 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/six-way-60fps.mp4) · [인접 원본 RGB](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/adjacent-original-rgb.png)

개별 GIF: [① AA-Off](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/case1.gif) · [② SMAA 1X](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/case2.gif) · [③ Temporal-only](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/case3.gif) · [④ SMAA T2X-R](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/case4.gif) · [⑤ Edge temporal-only](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/case5.gif) · [⑥ SMAA + edge temporal](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/bistro-window-stop/case6.gif)

## ⑤·⑥ 실제 first-pass edge 마스크

흰색은 최종 first-pass RG 중 하나 이상이 0보다 큰 픽셀, 검은색은 선택되지 않은 픽셀이다. 저장된 GPU temporal 실행 coverage와 픽셀 단위로 일치한다. 이번 두 장면의 frame 100~219에서 ⑤·⑥의 edge는 240개 frame pair 모두 동일하므로 공통 마스크로 표시한다. ①~④의 마스크를 나타내는 자료는 아니다.

2026-09-29에 저장한 GPU edge/coverage를 재사용했다. 같은 실행의 최종 RGB가 수정된 2026-09-30 캡처와 동일함을 총 480개 frame에서 확인했다. 새 렌더 실행이나 RGB에서의 edge 재검출은 하지 않았다. [검증 기록](edge-media.json)에 원본 위치·커밋·해시를 보존한다.

확대 영역과 frame 범위는 위 색상 GIF와 동일하다. 확대는 2배 nearest-neighbor, 전체 화면은 원래 해상도다. 이동은 0.5배속, 이동→정지는 0.25배속이며 frame 180에서 정지한다. 제목에 표시한 비율은 해당 frame의 전체 화면 선택 비율이다. 확장·보간·밝기 보정을 하지 않았으며, 고정 회색조 팔레트로 저장한 모든 GIF의 decoded RGB가 렌더한 마스크·문자와 정확히 일치함을 확인했다.

- 전체 화면: [Bistro](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/edge-only/bistro-full-edges.gif) · [Minecraft](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/edge-only/minecraft-full-edges.gif)
- 이동 확대: [Bistro 의자 다리](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/edge-only/bistro-chairs-moving-edges.gif) · [Minecraft 얇은 경계](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/edge-only/minecraft-thin-edges-moving-edges.gif)
- 이동→정지 확대: [Bistro 창살](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/edge-only/bistro-window-stop-edges.gif) · [Minecraft 나뭇잎](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/Captures/stencil-six-case-20260930/edge-only/minecraft-leaves-stop-edges.gif)

## 세 장면의 6-way 색상 / 최종 출력 윤곽 비교

`output-contour-media.json`은 Bistro 의자 다리, Minecraft 얇은 경계, Bistro 창살의 색상 GIF 바로 아래에 같은 ①② / ③④ / ⑤⑥ 배치의 윤곽 GIF를 제시하기 위한 기록이다. 기존 색상 GIF는 그대로 사용한다. 각각 동일 source frame·crop·재생 시간이며 1,080개 원본 RGB 해시가 색상 자료의 입력과 일치한다.

이 윤곽은 **최종 출력 RGB에서 오프라인으로 추출한 시각화**다. 실제 first-pass edge나 temporal 선택 마스크가 아니다. AA-Off와 Temporal-only에도 동일 필터를 적용하여 여섯 최종 결과의 윤곽을 비교할 수 있게 했다. 내부 선택 마스크는 위의 ⑤·⑥ 자료와 구분한다.

표시 RGB의 luma(0.2126R + 0.7152G + 0.0722B)에 동일 3×3 Sobel을 적용한다. 두 축을 4로 나눈 gradient 크기에 고정 표시 배율 4를 적용하고 0~255로 제한한다. 구성별·프레임별 정규화나 threshold 조절은 없다. crop 외곽 1픽셀을 함께 읽어 필터 경계를 보존하며 최종 확대는 nearest-neighbor다. 밝은 윤곽 일부는 표시 범위에서 포화될 수 있으므로 품질 점수나 내부 후보 판정으로 해석하지 않는다. 원본 RGB나 렌더러는 변경하지 않았다.

각 장면의 합성 GIF와 6개 개별 GIF를 저장하고 모든 decode frame이 렌더한 회색조 영상과 일치함을 검사했다. 두 GIF의 프레임·duration은 동일하지만 앱이 별도 GIF의 재생 시작을 동기화한다고 보장하지 않는다. 파일 경로와 해시는 [출력 윤곽 기록](output-contour-media.json)에 있다.
