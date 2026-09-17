# 움직이는 영상으로 구분할 품질 항목

PSNR·CGVQM이 낮다는 이유만으로 고스팅이나 잔상이 더 심하다고 결론내리지 않는다.
선택적 처리는 잔상을 줄이는 대신 깜빡임이나 공간적 계단 현상을 늘릴 수 있다.
적게 선택했다는 사실만으로 점수가 반드시 떨어지는 것도 아니다.

## 비교 자료

각 scene의 `Projects/CMAA2/AutoBench/ContrastReferenceAnalysis/<scene>/Playback`에 저장했다.
모든 자료의 좌→우 순서는 **SS 공간 기준 영상 / 원본 T2X-R / 대비 0.01 T2X-R**이다.

- `overview-60fps.mp4`: 전체 240 frame을 실제 60 FPS, 4초로 재생한다.
  화면 전체의 움직임을 보는 축소 영상이며 미세한 선은 아래 1:1 crop에서 확인한다.
- `detail-60fps.mp4`: 같은 240 frame을 원본 pixel 크기의 480×320 crop으로 재생한다.
  Bistro는 의자 다리·메뉴판·바닥, Minecraft는 벽면과 전경 구조물 경계를 포함한다.
- `moving-detail-half-speed.gif`: 이동 중 frame 90~149, 0.5배속 보조 영상.
- `transition-detail-half-speed.gif`: 이동→정지 frame 160~219, 0.5배속 보조 영상.
- `late-still-detail-half-speed.gif`: 정지 후기 frame 200~219, 약 0.5배속 보조 영상.
- `moving/stop/still-sequence.png`: 압축 전 RGB crop의 연속 네 frame이다.
  행 순서는 기준/원본/선택 방식, 열은 연속 frame이다.

MP4는 60 FPS와 frame 수 및 일정한 PTS를 전체 decode로 검증했다.
H.264 CRF12 YUV420 인코딩이므로 픽셀 오차 측정에는 사용하지 않는다.
GIF는 하나의 공통 256색 palette와 dithering Off를 적용했지만 색 양자화가 남는다.
GIF의 loop 시작점으로 되돌아가는 순간은 장면의 잔상으로 세지 않는다.
작은 차이의 최종 판정은 원본 PNG와 정속 영상으로 확인한다.

## 관찰 항목과 현재 판단

| 항목 | 확인할 현상 | 현재 근거와 한계 |
|---|---|---|
| 고스팅·잔상 | 이동 방향 뒤에 이전 윤곽이 남거나, 가려짐이 풀린 자리의 색이 늦게 갱신됨 | 검토한 원본 PNG 연속 crop에서 뚜렷한 개선을 확정하지 못했다. 점수 하락을 잔상 악화로 해석하지 않는다. |
| 깜빡임·shimmer | 얇은 선·벽면·반사 부위의 밝기와 형태가 frame마다 번갈아 바뀜 | 정지 후기 새 구현의 2-frame 교대 변화가 확인됐다. 원본은 안정된다. |
| 블러·선명도 | 움직일 때와 멈췄을 때 세부 구조가 유지되는가 | 선명해 보이는 것과 aliasing 증가를 구분해야 하며, 화면 전체 점수로 국소적 선명도를 대체하지 않는다. |

정지 후기 frame 200→201의 **이 crop 내부** RGB 평균 변화는 Bistro 원본 0,
새 구현 1.460773, Minecraft 원본 0, 새 구현 0.493403이다(0~255 RGB level).
이는 해당 위치의 출력 교대 근거이며 사람이 느끼는 깜빡임 강도나 ghosting 점수가 아니다.

여기서 검토한 자료는 연속 PNG와 그 재생용 영상이다. 다수 관찰자의 실시간 재생 평가를
수행한 것은 아니다. 현재 카메라 경로에는 별도의 움직이는 물체 실험이 없으므로,
object-motion 고스팅 감소도 주장하지 않는다.

이 원본 T2X-R의 history는 이전 frame의 spatial 결과다. 여러 frame의 resolve 출력을
재귀적으로 누적하는 기존 TSCMAA-inspired 경로와 잔상 특성을 동일시하지 않는다.
향후 강한 고스팅을 구분할 필요가 있으면 빠른 좌우 이동·가려짐 해제·이동 후 정지를
포함한 별도 장면에서 잔상의 위치와 지속 frame을 확인해야 한다.
