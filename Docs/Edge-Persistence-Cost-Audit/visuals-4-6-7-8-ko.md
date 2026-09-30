# ④·⑥·⑦·⑧ 동일 구간 시각 비교

2026-10-01 사용자 요청에 따라 **⑦=개선 전, ⑧=개선 후**로 표시한다.
기존 비용 감사 capture를 사용하며 렌더러 수정, 새 GPU 실행, 새 품질 점수 측정은 없다.

| 표기 | 실제 캡처 폴더 | 구성 | 표본 패턴 |
|---|---|---|---|
| ④ | O-T2X-R | 원본 spatial SMAA + full-screen T2X-R | On |
| ⑥ | A-CurrentEdge-Stencil | spatial SMAA + 현재 first-pass edge 선택 | Off |
| ⑦ | B-PreviousRawEdge-Depth | spatial SMAA + 현재/재투영 직전 raw edge union, 개선 전 depth 전달 | Off |
| ⑧ | E-PreviousRawEdge-FirstStencil | 같은 union, 개선 후 first-pass stencil 전달 | Off |

모두 spatial SMAA를 적용한다. ④의 paired jitter/subsample pattern과 ⑥·⑦·⑧의 Pattern Off 차이를
edge 선택만의 효과로 해석하지 않는다. 원래 감사 문서에서 '개선 ⑦'이라고 부른 구현이 여기서는 ⑧이다.

## 원본과 제작 조건

- Bistro: `D:/SMAAResearchCaptures/edge-persistence-cost-audit-20261001/capture/bistro/20261001_033739`
- Minecraft: `D:/SMAAResearchCaptures/edge-persistence-cost-audit-20261001/capture/minecraft/20261001_035207`
- 각 mode의 240개 final PNG 이름과 1920×1061 크기를 확인한다. 사용한 54프레임 × 4 mode × 2 scene의
  RGB SHA-256을 기존 capture receipt와 대조해 모두 일치함을 확인했다.
- ⑦과 ⑧은 각자의 실제 캡처에서 읽는다. 같은 그림을 복제하지 않는다. 이번 사용 프레임에서도
  두 source의 full RGB hash가 같다. 기존 감사는 두 장면 전체 480프레임 동일성을 검증했다.
- 60 fps 입력의 연속 프레임을 생략하지 않고 10 fps(1/6배속), 프레임당 100 ms로 반복 재생한다.
- nearest 확대만 적용한다. 밝기·대비·선명도 보정은 하지 않는다.
- GIF는 네 mode와 전체 타임라인에 하나의 공통 256색 palette를 사용하고 dithering을 끈다.
  GIF의 색 양자화는 원본과 차이가 있으므로 무손실 animated WebP와 PNG sheet도 제공한다.
- GIF를 다시 읽어 프레임 수·100 ms duration·loop·양자화 입력과의 일치를 검증했다.
  WebP의 모든 복원 RGB는 합성 전 RGB와 완전히 같다. 파일 hash와 GIF 양자화 오차는 JSON에 기록한다.

| 구간 | ROI (x1,y1,x2,y2; 오른쪽/아래 제외) | 확대 |
|---|---|---|
| Minecraft 얇은 선 | 956,524,1020,620 | 3× |
| Bistro 의자 | 1230,582,1358,670 | 2× |
| Bistro 창문 | 906,470,1034,558 | 2× |

세 ROI 모두 이전 `Edge-Persistence-GPU` 자료와 같다. 이동 GIF f126–155, 이동→정지 f172–195,
정지 f190–195. 연속 6프레임 sheet는 각각 f130–135, f178–183, f190–195다.

## 직접 본 프레임과 한계

두 장면의 ④·⑥·⑦·⑧ f131 full PNG 8장과 세 ROI × 세 구간의 6프레임 sheet 9장을 열어 확인했다.
애니메이션 재생을 육안으로 관찰했다고 주장하지 않으며, GIF 자체는 전체 프레임 decode로 검사했다.

Minecraft 이동 sheet에서 ⑥의 선은 f131/f134에 크게 끊기고, ⑦·⑧에서는 그 위치가 일부 이어진다.
그러나 f132에는 ⑦·⑧에서도 선 중간의 단절이 남는다. 따라서 직전 edge 유지가 얇은 선 문제를
해결했다고 할 수 없다. 이번 속도 개선은 ⑦의 출력과 남은 품질 문제까지 보존한다.
Bistro의 의자·창문도 ⑦·⑧이 같다. 이 자료만으로 잔상 감소나 전체 장면 품질 개선을 주장하지 않는다.

## 파일 및 재생

갤러리: `Projects/CMAA2/Captures/edge-persistence-4-6-7-8-20261001/index.html`

같은 디렉터리에서 각 `{minecraft-thin-line,bistro-chairs,bistro-window}-{moving,stop,still}`에 대해
`.gif`, `.webp`, `-six.png`를 제공한다. 큰 이미지 파일은 기존 Captures 정책대로 Git에 넣지 않는다.
메타데이터: [visuals-4-6-7-8.json](visuals-4-6-7-8.json).
생성 도구: `Tools/SMAA/create_persistence_audit_visuals.py` (기존 quality-venv의 Pillow/NumPy 사용).
