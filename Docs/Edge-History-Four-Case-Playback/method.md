# ④·⑩·⑬·⑭ 확장 비교 영상

비교 전용 브랜치 `experiment/edge-history-four-case-playback`, 기준 ⑭ 완료 커밋
`8ed45765e63d7e73ba63e17be329fef693dc65b4`를 사용한다. 이번 작업은 알고리즘
변경이나 새 번호 실험이 아니라 실제 720프레임 비교 자료의 확장이다.
기존 shader/C++/실행 바이너리는 변경하지 않는다.

|번호|처리|pattern|history RGB|다음 history|가중치|
|---|---|---|---|---|---|
|④ O-T2X-R|Original SMAA + 전체 화면 원본 T2X-R|On|point|현재 spatial 프레임|원본 adaptive 0..0.5|
|⑩ ABL-ET2X-R-PreviousRawEdge-BilinearRGB|현재/재투영 직전 raw edge 선택|Off|bilinear|현재 spatial 프레임|원본 adaptive 0..0.5|
|⑬ ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB|⑩과 같은 선택|Off|normalized 5-fetch Catmull–Rom|resolved RGB / current spatial alpha|원본 adaptive 0..0.5|
|⑭ ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080|⑬과 같은 선택|Off|⑬과 동일|⑬과 동일|고정 0.8|

모두 Original spatial SMAA Ultra·camera/depth reprojection On이다. Object velocity,
추가 clipping·dilation은 없으며 ④↔선택 구현은 coverage 외 pattern·sampler·feedback
차이도 있으므로 후보 선택 단독 효과로 해석하지 않는다.

Bistro/Minecraft 각각 fixed60, flythrough start2초에서 정지60 + 이동600 + 정지60의
720 실제 프레임을 사용한다. 60fps 영상은 12초, 50fps GIF는 14.4초다.
프레임 복제·보간·밝기/색상 보정은 없다. ROI는 화면 고정이며 물체 추적은 아니다.
후반에 처음의 구조가 화면 밖으로 나가면 해당 구조의 소실 증거로 해석하지 않는다.

⑭ 새 long capture의 ④ 및 Bistro ⑬ RGB와 기존 ⑬ long capture control을 전부 대조한다.
Bistro는 기존 ④·⑩·⑬의 실제 2,160 PNG를 확인한다. Minecraft는 기존 ④·⑩ 1,440 PNG와
이번 새 ⑬ 720 PNG를 저장된 RGB hash와 확인한다. 공통 pose인
처음180프레임에서 ⑭의 완료된 short capture와도 연결한다. 새 diagnostic readback은
없으며 장면마다 fresh process·timeout·Aggregate PASS와 전후 CMAA2 0개를 확인한다.

C드라이브 공간을 보존하기 위해 같은 RGB임을 확인한 새 ④ 및 Bistro ⑬ 중복 PNG만 제거하고,
기존 D드라이브 original control과 새 ⑭/Minecraft ⑬ 원본을 사용한다. 원본 경로·hash·재사용 및
공간 정리 증거는 `*-inputs.json`, `*-duplicate-storage.json`에 기록한다.

Minecraft의 최초 병렬 원본 비교는 ⑬ f98 불일치와 기존 PNG 읽기 오류로 중단했다.
새 ⑬을 독립적으로 다시 확인해 720개 저장된 기준 RGB hash와 모두 일치했고,
⑭ short-prefix 180개도 모두 일치했다. 알고리즘 차이로 추정하지 않으며 Minecraft ⑬은
새 캡처 원본을 사용한다. 실패와 재검사는 `minecraft-control-differences.json` 및
`minecraft-inputs.json`에 보존한다.

GIF는 공통 palette·dither Off로 저장하고 모든 decode frame RGB hash를 검증한다.
MP4는 60fps H264 CRF12로 저장하고 모든 frame 수·PTS·average rate를 확인한다.
두 형식은 손실 확인용이며 무손실 원본 PNG/nearest 2배 frame sheet를 함께 보존한다.
기존 성능·품질 점수는 변경하지 않으며 긴 경로의 추가 supersample reference는 없다.

전체 원본과 이동·전환·정지 연속6프레임의 직접 검사 기록은 `inspection.md`에 남긴다.
판단은 실제 열어 본 PNG와 재생용 영상 제작을 구분한다. 원시 PNG/DDS, GIF/MP4,
AutoBench 파일은 Git에 추가하지 않는다.
