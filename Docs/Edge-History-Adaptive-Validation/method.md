# ⑫: 검증된 history와 밝기 차이에 따른 adaptive 누적

브랜치: `experiment/edge-history-adaptive-validation`.
공통 기준: stencil 수정⑥ `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459`.
명시적 의존성: `3992640`(⑨ raw edge persistence), `96c495a`(⑩ RGB bilinear),
`b793b74`(⑪ RGB feedback/MRT), `573ecfa`(자동 실행 입력 격리),
`cd8844d`(capture 검증·presentation 도구). ⑪의 최종 결과 커밋을 누적하지 않았다.
의존성에 포함된 옛⑪ 문서는 당시 기록이며 최신⑪ 결과는 원래⑪ 브랜치에 있다.

## 문헌 검토와 선정 이유

| 자료 | 실제 확인한 내용 | 이번 선택과의 관계 |
|---|---|---|
| [Yang et al. 2009, Amortized Supersampling](https://w3.impa.br/~diego/publications/YanEtAl09.pdf), DOI10.1145/1618452.1618481 | 원문4–5쪽의 Eq11, subpixel buffer 재표본화와 합성. 반복 bilinear reprojection의 blur와 누적 강도의 관계를 설명한다. | 강한 누적을 자동 해법으로 간주하지 않는다. 원 논문의4개 subpixel buffer·추가 표본은 이번 한 패스 혼합식과 다르며 구현하지 않았다. |
| [Schied et al. 2018, Gradient Estimation for Real-time Adaptive Temporal Filtering](https://momentsingraphics.de/HPG2018.html) | 저자 공개 초록·algorithm 설명의 같은 표면 재평가를 통한 temporal gradient 추정. | 단순 current/history RGB 차이를 이 논문의 unbiased gradient라고 표현하지 않는다. 재음영·필터 비용을 포함하는 다른 연구 방향으로 검토했다. |
| [Decima SIGGRAPH2017](https://www.advances.realtimerendering.com/s2017/DecimaSiggraph2017.pdf), 39–42쪽 | 얇은 구조, sample pattern, current-frame의4-tap 재구성과 sharpened spatial history 저장. | history4-tap filter와 혼동하지 않는다. 전체 pattern/공간 재구성 변경이 함께 필요한 대안으로 검토했다. |
| [Playdead INSIDE 공개 shader](https://github.com/playdeadgames/temporal/blob/master/Assets/Shaders/TemporalReprojection.shader), [설정](https://github.com/playdeadgames/temporal/blob/master/Assets/Scripts/TemporalReprojection.cs) | rounded3×3 bounds, AABB center 방향 clipping, 정규화된 luminance 차이에 따른 feedback. 공개 기본값0.88–0.97. | 실제 코드로 확인할 수 있는 history validation·adaptive accumulation을 선택했다. 원본 전체 INSIDE TAA 재현은 아니다. |

⑪의 실패 추적에서 선택·weight가 정상인 픽셀에서도 약한 history를 섞으며 선의 대비가
감소했고, 입력 단계부터 선이 약한 frame도 있었다. 새 선택 마스크만으로 해결한다고
보지 않고 history 유효성·누적 강도를 조사한다. 문헌이 성공을 보장하지 않으므로
GPU 정확성, 이동 중 원본 frame 검사, 품질 수치, paired 시간 순서로 검증한다.

## 알고리즘과 원본 대비 변경

기존 Original SMAA Ultra와 current OR reprojected previous raw edge 선택을 유지한다.
Pattern Off, camera/depth reprojection only, bilinear history RGB/point alpha,
비선택=current spatial, next history RGB=resolved output/alpha=current spatial.

선택된 픽셀에서만 현재 spatial3×3 RGB point samples를 읽는다.9개와 중앙 cross5개의
min/max를 각각 구해 평균한 rounded 범위를 사용한다. History를 이 AABB의 중심을
향해 clip한다. 이어
`d=abs(Ycurrent-Yhistory)/max(Ycurrent,Yhistory,0.2)`와 `(1-d)^2`로 feedback을 보간한다.
Rec.709 linear luma를 명시한다. Unity의 color-space luminance 구현과 동일하다고
주장하지 않는다. RGBA8 저장·camera-only velocity·Pattern Off·선택 stencil은 SMAA
adaptation이다. Noise, motion blur, velocity dilation, global jitter는 추가하지 않았다.

| semantic ID suffix | 연구 구성 | history weight |
|---|---|---|
| `ValidatedRGB` — ⑫의 공개 기본값 조건 | rounded bounds + clipping + adaptive feedback | `confidence × lerp(0.88,0.97,(1-d)^2)` |
| `ResponsiveRGB` — ⑫의 명시적 parameter ablation | 같은 계산, 빠른 현재값 반응 범위 | `confidence × lerp(0.05,0.97,(1-d)^2)` |
| `ClippedRGB` — native weight control | clipping + 화면 밖 history 거부 | `confidence × 0.5` |

`confidence=saturate(1-sqrt(abs(currentAlpha²-previousAlpha²)/5)×nativeScale)`는
기존 SMAA alpha rejection을 보존하기 위한 연구 adaptation이다. 화면 밖 history는
weight0으로 거부한다. Previous-depth disocclusion rejection과 object velocity는
포함하지 않으므로 색상 범위 검사를 완전한 visibility 판정으로 표현하지 않는다.
ClippedRGB도 다른 ⑫ 조건처럼 화면 밖 history를 거부한다. ⑪는 clamp sampling을
유지하므로 전역 ⑪↔ClippedRGB 차이를 clipping 하나의 효과라고 단정하지 않는다.
화면 안에 재투영되는 좁은 ROI에서는 기존 weight를 유지한 clipping control로 비교한다.

Production은 기존 선택 temporal draw에서 처리하며 추가 draw·fullscreen copy는0개다.
⑪의 current-spatial texture/MRT 비용과 추가 neighborhood reads는 여전히 존재한다.
속도 개선을 미리 가정하지 않는다. Mask 확장이 아니라 color neighborhood validation이다.

비교군④·⑥·⑨·⑩·⑪와 세⑫ 조건을 같은 경로로 캡처·측정한다.④만 native paired pattern
On이므로④와⑫의 차이를 모두 새 history 계산의 효과로 해석하지 않는다.⑪↔⑫와
clipping-only control로 추가 요소의 효과를 구분한다.

## 검증 기준

- Shader compile/early stencil, 옛 control shader bytecode 보존, Release build.
- 두 장면 first-frame/reset seed, 실제 선택·공통 current/velocity/alpha 동일성.
- Weight 유한·0..0.97, 비선택0, CPU ideal filter/clipping/weight의 안전 주소 오차 기록,
  rounded color box의 blend 범위와 실제 RGB8 출력에서 역산한 feedback interval 검증,
  RGB feedback=visible, alpha=current spatial, 연속 history chain.
- Moving6 frame·transition6 frame·stable6 frame의 nearest 확대와 full frame 확인.
- Supersample spatial proxy MAE·시간 차분·선 대비 추적은 보조 지표.
- Same-binary Smoke 뒤 fresh process Benchmark:300 warm-up,4800 frame×6회,
  순서 교차, PNG/query/readback Off. 변화율은 같은 run④ 기준.
- 실제720-frame long capture와 GIF/MP4. 짧은 sequence 반복·보간 금지.

현재 상태: 구현·검증·측정 완료. 얇은 구조 보존과 반짝임 해결의 품질 gate를 통과하지 못해 채택하지 않았다. 최종 결과는 report.md에 기록한다.

### CPU ideal mirror의 최초 실패와 검사 범위

최초 Bistro 분석은61 frame ResponsiveRGB에서 ideal weight 최대 오차0.005171,
출력 최대2 RGB level로 임의의0.004 weight 허용치를 넘었다. 이 실패를 보존한다.
Renderer·weight·원본 입력은 바꾸지 않았다. 기존 bilinear 실험에서도 CPU ideal filtering과
GPU finite-precision filtering은 byte-exact가 아니었다. 특히 nonlinear clipping/feedback에
필터 오차가 전파되므로 임의 허용치를 단순히 올려 exact mirror PASS라고 하지 않는다.
CPU ideal 오차는 계속 기록한다. 실제 GPU RGB8 출력을 한 encoded level과0.5/255 linear
입력 변환 불확실성의 구간으로 역산해 feedback 식의 일관성을 검사하고, clipped RGB의
rounded AABB 내 blend 범위를 독립적으로 확인한다. 이는 bounded witness이며 실제 GPU
sampled-history export나 모든 하드웨어에 대한 수학적 동일성 증명은 아니다.
