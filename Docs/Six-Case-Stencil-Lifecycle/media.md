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
