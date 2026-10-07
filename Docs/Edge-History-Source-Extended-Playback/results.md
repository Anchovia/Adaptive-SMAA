# 긴 재생 비교 완료

④ native SMAA T2X-R, ⑭ fixed0.8, ⑮ clipping, ⑯ recovered5fetch,
⑰ encoded gamma2 blend를 같은 camera pose/frame에서 비교한다.
⑮·⑯·⑰는 기존 독립 구현에서 각각 캡처했고 알고리즘을 결합하지 않았다.
④ Pattern On, ⑭~⑰ Off이며 모두 Original spatial SMAA와 camera/depth R을 사용한다.

## 제공 자료

실제 720 frame, 정지 1초 → 이동 10초 → 정지 1초다.
기존 240-frame 캡처를 반복하거나 보간한 자료가 아니다.

- Bistro: 의자·테이블, 얇은 의자, 창살, 스쿠터, 가로등·화분, 차양.
- Minecraft: 벽 이음선, 얇은 이음선, 나뭇잎, 잔디 이음선, 흰 돌 구조물, 대각선 돌 구조.
- 두 전체 경로를 더해 정상 MP4 14개, 빠른 GIF 14개, 느린 GIF 14개.
- 정상 60 fps/12초/1배, 빠른 50 fps/7.2초/약1.67배, 느린 25 fps/28.8초/약0.42배.
- 빠른 GIF는 source index 0,2,...,718을 사용한다. 나머지는 0~719 전부다.
- nearest 2배의 연속 프레임 sheet 144개와 원본 전체 PNG 40개를 제공한다.

모음: `Deliverables/SMAA_15_16_17_Extended_20261007/comparison.html`.
세부 원본 경로·ROI·frame·속도·hash는 `media-manifest.json`과 각 case의 영수증에 있다.
PNG/GIF/MP4 바이너리와 빌드 산출물은 Git에 올리지 않는다.

## 검증 결과

6개 clean CMAA2 실행 모두 정상 종료하고 잔류 프로세스는 0개다.
각 실행의 3 mode×720 mode check, 타임라인, report hash, trace Off를 확인했다.
각 구현의 첫 180 frame×3 mode는 기존 짧은 캡처와 RGB가 동일하다.
세 독립 캡처 사이에서 비교용 ④·⑭는 각 장면 720 frame 전체가 동일하다.
새 ④의 두 장면 전체도 이전 ⑬ 실험의 검증된 720-frame ④와 일치한다.

생성에 사용한 7,200개 source PNG를 기록된 RGB hash/해상도와 확인했다.
42개 미디어 모두 파일 hash, MP4 전체 decode의 720 frame·60 fps·PTS,
GIF 전체 decode의 720/360 frame·길이·양자화 후 RGB hash 검사를 통과했다.
40개 전체 PNG도 대응 원본의 RGB hash와 동일하고 HTML의 모든 링크가 유효하다.
두 장면의 각 5 mode 모두 frame700~719의 RGB hash가 하나로 유지된다.
이 정지 안정성으로 이동 품질 성공을 주장하지 않는다.

## 원본 프레임 직접 확인 범위

두 장면의 frame480에서 ④·⑭·⑮·⑯·⑰ 전체 원본을 열었다.
추가로 frame130의 ④·⑮ 전체 화면과 아래 nearest 연속 PNG를 직접 확인했다.

| 영역 | 이동 | 이동 후반 | 정지 전환 | 별도 정지 확인 |
|---|---|---|---|---|
| Bistro 얇은 의자 | 130~135 | — | 658~663 | 700~701 |
| Bistro 차양 | — | 480~485 | — | — |
| Minecraft 얇은 이음선 | 130~135 | — | 658~663 | 700~701 |
| Minecraft 잔디 이음선 | 130~135 | — | — | — |
| Minecraft 흰 돌 구조물 | — | 480~485 | — | — |

이동하는 약한 이음선의 프레임별 강도 변화와 기존 얇은 구조의 보존 한계는
여전히 확인 대상이다. 이번 자료로 반짝임·선 단절 해결이나 ⑮~⑰의 품질 우위를
새로 확정하지 않는다. 기존 240-frame 품질/paired 성능 결론은 그대로 보존한다.
다른 모든 ROI/프레임을 직접 육안 전수 검사했다고 표현하지 않는다.
실제로 직접 본 자료는 정지 PNG이며 GIF·영상은 생성 및 전체 decode를 검증했다.
재생을 실제 관찰했다는 별도 주장은 하지 않는다. GIF/MP4의 손실은 원본 PNG와 구분한다.

## 구현과 보존

작업 종료 checkout은 `tooling/source-temporal-extended-playback`이다.
생산 AA 소스의 Git diff는 없고 완료된 ⑰의 실행파일과 shader bytes를 원래
캡처 영수증의 SHA로 복원·확인했다. ⑮·⑯의 긴 캡처 기록은 각각 원래 독립
브랜치에 커밋했다. 원본은 D 드라이브 연구 폴더에 보존해 C 드라이브 추가 부담을 줄였다.
새 GPU 성능 측정, CGVQM 재실행, spatial/temporal 알고리즘 변경은 없다.

## ④와 개별 구현의 2-way 비교

사용자 요청에 따라 ④↔⑭·⑮·⑯·⑰을 각각 별도 파일로 구성했다.
두 실제 장면의 동일 12개 세부 영역과 두 전체 경로에서 정상 MP4 56개,
빠른 GIF 56개, 느린 GIF 56개 및 무손실 연속 PNG 576개를 완성했다.
왼쪽은 항상 ④이고 오른쪽은 해당 독립 구현이다. 길이·속도·ROI와
④ Pattern On / 다른 구현 Off 조건은 기존 비교와 동일하다.

원본 PNG 7,200장의 hash 검사를 통과한 이미지에서 직접 생성했다.
168개 미디어의 전체 decode와 길이/프레임 수/PTS/GIF pixel hash 및 최종 파일
SHA256 검증을 통과했다. PNG 32개 image panel이 해당 독립 원본의 nearest
확대 픽셀과 동일했고 gallery의 모든 링크도 확인했다. 최종 두 scene의
source 읽기 retry는 0이며 불일치 이미지 사용도 0이다. Minecraft의 초기 중단
두 실행은 `pair-excluded-attempts.json`에 기록했고 최종 결과에서 제외했다.

이 task의 직접 열어 본 pair PNG는 Bistro ④↔⑭ 얇은 의자 frame130~131과
Minecraft ④↔⑯ 얇은 이음선 frame130~131이다. 원본 프레임 검사와
실제 애니메이션 재생 관찰을 동일시하지 않는다. 기존 품질 판정은 변경하지 않는다.

모음: `Deliverables/SMAA_4_Pair_Extended_20261007/comparison.html`.
compact 기록은 `pair-media-manifest.json`이며 full manifest와 원본은 local에 보존한다.
생산 AA 소스·브랜치별 실험 구현·기존 성능/품질 수치는 변경하지 않았다.
