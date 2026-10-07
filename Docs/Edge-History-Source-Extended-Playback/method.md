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

두 실제 3D 장면에서 12개 화면 고정 세부 영역과 두 전체 경로를 제공한다.
ROI는 물체 추적이 아니며 nearest 2배로 원본 픽셀을 보존한다. 전체 경로만
Lanczos로 축소한다. 색/밝기 보정은 없다.
이동 130~135, 이동 후반 480~485, 정지 전환 658~663, 정지 700~705의
연속 6-frame PNG를 제공한다. 원본 전체 PNG도 함께 보존한다.

출력은 `Deliverables/SMAA_15_16_17_Extended_20261007/comparison.html`과 manifest다.
영상 생성·decode 검사와 실제 재생 관찰을 구분하며 원본 프레임의 직접 검사 결과는
후속 결과 문서에 기록한다. 기존 품질 성공/실패 판정이나 최종 8-case를 변경하지 않는다.

## 사용자 지정 2개씩 비교

채팅과 이후 비교 자료는 ④↔⑭, ④↔⑮, ④↔⑯, ④↔⑰로 나눈다.
왼쪽은 항상 native ④이고 오른쪽은 해당 독립 구현이다. 단순한 비교 화면 재구성이며
실험 구현을 결합하거나 새로운 성능·품질 측정을 수행하지 않는다.

`create_source_component_pair_playback.py`는 검증한 원본 lossless PNG에서 각 pair를
직접 구성한다. 이미 압축한 MP4/GIF를 잘라서 다시 압축하지 않는다. 장면별 원본
3,600장의 RGB hash와 독립 캡처 사이의 control bridge를 재검사한다. GIF에는 기존
다섯 구현의 공통 256색 palette를 유지하고 decoded pixel hash·길이·프레임 수를 검사한다.
MP4는 전체 decode의 프레임 수·60 fps·PTS 증가를 검사한다.

두 장면의 동일 12개 ROI와 두 전체 경로, 실제 720 frame과 기존 재생 속도를 유지한다.
Pair당 이동·이동 후반·정지 전환·정지의 무손실 연속 PNG도 함께 저장한다.
출력은 `Deliverables/SMAA_4_Pair_Extended_20261007/comparison.html`과 manifest다.
④ Pattern On, ⑭~⑰ Off 표시는 모든 pair에 유지한다.

Minecraft 변환에서 frame99/frame696의 source hash 검사 실패로 중단한 두 실행은
`pair-excluded-attempts.json`에 보존하고 결과에서 제외한다. 각 실패 frame의 세 원본은
독립 재읽기에서 기록된 RGB hash와 일치했지만 최초 실패 원인은 확정하지 않는다.
후속 읽기는 파일의 encoded bytes를 독립 버퍼에 저장한 뒤 decode하고 pinned RGB hash와
일치하는 이미지에만 후속 처리를 허용한다. 불일치 read는 기록·폐기하고 최대 세 번만
재읽으며, 지속 실패는 전체 실행을 중단한다. 이 절차는 hash 검사를 완화하지 않는다.
