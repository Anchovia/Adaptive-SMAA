# ⑭ 원본 프레임 직접 검사

④·⑬·⑭의 같은 frame index, 카메라 pose, 1920×1061 RGB PNG를 비교한다.
확대 sheet는 nearest 2배이며 밝기·색상 보정과 차이 증폭이 없다.
④는 paired sample pattern On, ⑬·⑭는 Off다. 공간 처리는 모두 Original SMAA Ultra다.
실제 열어 본 정지 PNG/연속 frame sheet와 확인용 GIF·MP4 제작을 구분한다.
영상 재생을 직접 관찰한 기록으로 표현하지 않는다.

## 이동 및 이동→정지

- Bistro thin-chair `(1230,582,1358,670)`: f126–131, f178–183, f190–195.
- Minecraft thin-seam `(956,524,1020,620)`: 같은 세 구간.
- Minecraft leaves `(1420,590,1580,718)`: 같은 세 구간.
- Minecraft grass-seam `(1450,665,1552,719)`: f130–131 보완 확인.
- 전체 문맥: 두 장면의 ⑭ f130, f180, f195 원본 PNG.
  ④·⑬의 기존 동일 RGB 전체 영상과 현재 240-frame hash bridge도 통과했다.

⑭의 식생과 일부 미세 무늬는 ⑬보다 프레임 변화가 완만해 보인다. 그러나 이동 중
가는 경계의 프레임별 강약·단절은 남는다. Minecraft f126–131의 얇은 수직 이음선은
일부 프레임에서 ⑬보다 대비가 약해 보이며 선 보존 성공으로 판정하지 않는다.
Bistro 의자 구조에도 계단과 프레임별 변동이 남는다. 무늬가 완만해 보이는 효과를
전체 반짝임 해결이나 품질 우위로 일반화하지 않는다.

사용자가 지적한 약한 잔디 윗면 이음선은 일부 위치에서 기존 선택 영역 밖이다.
⑭는 선택 마스크가 ⑬과 byte 동일하므로 weight 변경만으로 그 위치를 새로 선택하지 않는다.
같은 ROI의 전체 시간 변화 감소를 해당 이음선 선택·복원 성공으로 해석하지 않는다.

## 정지 후 수렴과 판정 범위

f180부터 카메라가 정지한다. whole RGB의 마지막 변경은 Bistro ④ f182 / ⑬ f189 /
⑭ f209, Minecraft ④ f182 / ⑬ f189 / ⑭ f208이다. 따라서 ⑭의 f190–195는
수렴 중인 post-stop 구간이며 안정 정지로 부르지 않는다. 마지막 hash 변화는
절대 고스팅 지속 시간과 동일한 지표가 아니며 전체 출력의 수렴 지연만 나타낸다.

정지 안정성은 이동 중 선 소실·반짝임 해결과 별개다. Raw 시간 차분에는 카메라 이동과
흐림이 포함되며 supersample reference는 spatial proxy다. 별도 object motion,
previous-depth disocclusion rejection과 절대 고스팅 ground truth는 이번 실험에 없다.
가중치 0.8로 반짝임과 선 끊김을 해결했다고 판정하지 않는다.

수렴 이후 f210–215는 Bistro thin-chair와 Minecraft thin-seam/leaves의
세 쌍씩 6개 연속 원본 frame sheet를 직접 열어 확인했다. 검사한 정지 영역에서는
프레임별 변동이 보이지 않으며 whole RGB hash 안정성과 일치한다. Minecraft 이음선은
이 구간에서 대비가 남아 있지만 이동 f126–131의 약화·단절이 해결됐다는 뜻은 아니다.

원본 `capture_root`, output RGB hash, ROI와 frame 번호는 `*-capture.json`에 있다.
무손실 sheet와 확인용 GIF/MP4의 경로·재생 속도는 `*-media-240.json`에 기록한다.
