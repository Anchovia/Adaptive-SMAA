# No-TAA / edge 선택 / 원본 T2X-R 움직임 비교

왼쪽부터 **No-TAA(공간 SMAA·지터 유지) / edge 선택 / 원본 T2X-R**이다.
No-TAA는 AA 전체 Off나 지터를 끈 SMAA 1X가 아니다. 기존 검증된 PNG에서 동일 프레임과
동일 화면 좌표를 잘랐다. 별도 렌더링이나 알고리즘 변경은 없다.

GIF는 0.5배속, MP4는 원래 60 FPS다. 원본 픽셀 크기이며 보간·선명화·노이즈 제거는 하지 않았다.
Bistro의 어두운 구조는 보기 쉽도록 세 방식에 동일 RGB 밝기 3배를 적용했다.
원래 밝기의 정속 영상도 제공한다. 밝기 조절 자료를 원래 화질 점수로 사용하지 않는다.
고정 공통 256색 팔레트와 dithering Off를 사용해 GIF의 프레임별 색 변화는 줄였지만
색 양자화로 미세한 차이가 사라질 수 있다. 의심스러운 세부는 MP4/원본 PNG로 확인한다.
재생 마지막에서 처음으로 돌아가는 점프는 알고리즘 잔상으로 세지 않는다.

## Bistro: chair legs / table frames / pavement

의자·테이블의 가는 다리와 바닥 무늬가 이동할 때 연속적으로 유지되는지 비교한다.

![bistro-thin-lines-moving](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/bistro-thin-lines-moving.gif)

[정속 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/bistro-thin-lines-moving-60fps.mp4) · [인접 프레임 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/bistro-thin-lines-moving-adjacent-frames.png)

[원래 밝기 정속 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/bistro-thin-lines-moving-original-brightness-60fps.mp4)

## Minecraft: moving foreground edge / background reveal

가까운 블록의 경계와 새로 드러나는 뒤쪽 벽면에서 번짐·경계 떨림을 확인한다. 실제 고스팅이 존재하거나 줄었다는 결론을 전제한 선택은 아니다.

![minecraft-moving-boundary](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/minecraft-moving-boundary.gif)

[정속 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/minecraft-moving-boundary-60fps.mp4) · [인접 프레임 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/minecraft-moving-boundary-adjacent-frames.png)

## Minecraft: torches / stairs / motion to still

frame 180부터 카메라가 멈춘다. 횃불, 계단의 대각 경계와 벽면 무늬가 정지 후에도 번갈아 변하는지 확인한다.

![minecraft-motion-to-still](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/minecraft-motion-to-still.gif)

[정속 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/minecraft-motion-to-still-60fps.mp4) · [인접 프레임 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/minecraft-motion-to-still-adjacent-frames.png)

## Bistro: fixed camera / remaining phase flicker

카메라가 이미 멈춘 구간이다. 얇은 다리와 바닥의 남은 변동을 보기 위한 장면이며 움직임 잔상 장면은 아니다.

![bistro-still](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/bistro-still.gif)

[정속 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/bistro-still-60fps.mp4) · [인접 프레임 PNG](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/bistro-still-adjacent-frames.png)

[원래 밝기 정속 영상](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/FirstEdgeQuality/ThreeWay/bistro-still-original-brightness-60fps.mp4)

ROI는 관찰을 위한 수동 선택이며 전체 장면의 대표성이나 품질 우열의 독립 검증을 뜻하지 않는다.
정량 결과는 [No-TAA 비교 보고서](no-taa-report.md)를 참고한다.
