# ④·⑭·⑮·⑯·⑰ 긴 재생 비교

이 항목은 `tooling/source-temporal-extended-playback`의 발표·프레임 검사 도구다.
출발점은 완료된 ⑰의 `5bdd189`이며 AA 구현을 바꾸거나 독립 실험을 결합하지 않는다.
⑮·⑯·⑰는 각각의 기존 독립 브랜치/실행파일에서 캡처한다. 비교용 ④·⑭는
같은 카메라 경로의 RGB hash가 전체 프레임에서 일치해야 공유한다.

## 캡처와 재생

- Bistro/Minecraft, Original spatial SMAA Ultra, 1920×1061, fixed 60 Hz.
- 모두 camera/depth reprojection On. ④ paired pattern On, ⑭~⑰ Off.
- 시작 camera play time 2.0, 60 frame 정지 → 600 frame 이동 → 60 frame 정지.
- 각 모드의 실제 720 frame을 새 clean CMAA2 프로세스로 캡처한다.
- C 드라이브 공간을 보호하도록 원본 PNG는 `D:/SMAAResearchCaptures/source-temporal-components-long`에 저장한다.
- 진단 trace와 GPU 성능 측정은 끈다. 기존 성능/품질 점수를 새로 계산하지 않는다.

| 재생 자료 | source frame 선택 | 출력 | 길이 | 실제 60 Hz 대비 속도 |
|---|---|---|---|---|
| 정상 MP4 | 0~719 전부 | 60 fps | 12 s | 1× |
| 빠른 GIF | 0,2,...,718 | 50 fps | 7.2 s | 약 1.67× |
| 느린 GIF | 0~719 전부 | 25 fps | 28.8 s | 약 0.42× |

프레임 보간·반복으로 길이를 늘리지 않는다. 빠른 GIF의 프레임 생략 때문에
한 프레임 결함의 판정에는 정상 영상, 느린 GIF와 원본 PNG를 함께 사용한다.
GIF의 공통 256색 palette와 H264 yuv420p는 손실이 있는 재생용이다.

## 검증

`create_source_component_extended_playback.py`는 실행 영수증과 report SHA,
720개의 mode check, 타임라인, 진단 Off, PNG index/해상도/RGB hash,
독립 캡처 간 ④·⑭ 전체 hash bridge를 검사한다. MP4 전체 decode의 프레임 수·60 fps·PTS와
GIF 전체 decode의 프레임 수·길이·양자화된 RGB hash를 검사한다.

두 실제 3D 장면에서 11개 화면 고정 세부 영역과 두 전체 경로를 제공한다.
ROI는 물체 추적이 아니며 nearest 2배로 원본 픽셀을 보존한다. 전체 경로만
Lanczos로 축소한다. 색/밝기 보정은 없다.
이동 130~135, 이동 후반 480~485, 정지 전환 658~663, 정지 700~705의
연속 6-frame PNG를 제공한다. 원본 전체 PNG도 함께 보존한다.

출력은 `Deliverables/SMAA_15_16_17_Extended_20261007/comparison.html`과 manifest다.
영상 생성·decode 검사와 실제 재생 관찰을 구분하며 원본 프레임의 직접 검사 결과는
후속 결과 문서에 기록한다. 기존 품질 성공/실패 판정이나 최종 8-case를 변경하지 않는다.
