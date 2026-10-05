# ④·⑥·⑨·⑩ 품질 재평가 및 사용자 비교 자료

⑩는 `ABL-ET2X-R-PreviousRawEdge-BilinearRGB`다. 현재+재투영 직전 raw edge의 선택은 ⑨와 같고,
history RGB filtering만 point→bilinear로 바뀐다. Point alpha와 원본 adaptive weight는 유지한다.
이번 작업은 같은 독립 실험 브랜치의 품질 평가 보완이며 렌더러·AA 구현·기준선은 수정하지 않았다.
최종 채택 여부는 사용자 영상·원본 프레임 검토 후 결정한다.

## 실제 수행 범위

- 기존 실제 GPU 캡처의 두 장면×240프레임×4구성=1,920 PNG를 읽어 저장 RGB hash와 일치 검증했다.
- 전체 화면과 두 ROI의 RGB MAE·PSNR을 다시 계산했다. 새 GPU 캡처 또는 속도 재측정은 하지 않았다.
- CGVQM-2 이동60–179와 전환160–219를 네 구성·두 장면에서 평가했다. 총16 window/24개 완료 모델 프로세스다.
- 같은 frame131의 네 구성 원본 전체 PNG, 이동130–135·전후127–138·전환178–183·정지190–195의
  nearest2× 연속 sheet를 이번 요청에서 직접 열었다. 넓은 ROI의 이동 sheet도 검사했다.
- ④·⑥·⑨·⑩ 순서의 GIF25FPS/7.2초와 MP4 60FPS/3초를 재생성하고 decode로 길이·순서·PTS를 검증했다.
  실제 실시간 재생을 시청했다고 표현하지 않는다. 직접 관찰은 원본 PNG와 연속 sheet에 근거한다.

## CGVQM-2

높을수록 좋다. 전체 화면의 보조 지표이며 얇은 선의 연속성이나 고스팅만을 평가하는 점수가 아니다.

| 구성 | Bistro 이동 | Bistro 전환 | Minecraft 이동 | Minecraft 전환 |
|---|---:|---:|---:|---:|
| ④ 원본 SMAA T2X-R | 96.191235 | 96.719254 | 93.911362 | 94.905739 |
| ⑥ 현재 edge 선택 | 96.173374 | 95.911629 | 95.234108 | 94.894165 |
| ⑨ 현재+직전 raw edge 선택 | 96.237839 | 95.941154 | 95.293442 | 94.901237 |
| ⑩ ⑨+history RGB bilinear | 96.356331 | 95.980339 | 95.965633 | 95.196068 |

## Supersample spatial proxy 대비 오차

동일 pose/index의 spatial proxy를 사용한다. 절대 temporal ground truth가 아니다. RGB MAE는 8-bit level이다.

| 장면 | 구성 | 이동 전체 RGB MAE ↓ | 이동 전체 PSNR dB ↑ | 얇은 선 ROI MAE ↓ |
|---|---|---:|---:|---:|
| bistro | 4 | 0.734975 | 40.3768 | 4.381512 |
| bistro | 6 | 0.682871 | 40.1358 | 5.807495 |
| bistro | 9 | 0.678393 | 40.3729 | 5.684190 |
| bistro | 10 | 0.657544 | 40.8588 | 5.492582 |
| minecraft | 4 | 1.987355 | 34.3516 | 1.626500 |
| minecraft | 6 | 1.599557 | 34.9934 | 1.398820 |
| minecraft | 9 | 1.631267 | 35.2242 | 1.399701 |
| minecraft | 10 | 1.440077 | 36.0783 | 1.265436 |

## 원본 프레임 관찰

- Minecraft f131/f134의 ⑩에는 얇은 세로선 상단의 단절·소실이 남는다. f127–138 출현·소멸도 관찰된다.
  이를 단순 선명도 차이로 축소하지 않는다. 대표 f131(971,544)의 ⑨ RGB=(142,140,131),
  ⑩=(150,148,138)로 이 위치에서는 선이 더 약해진다. f134에는 반대 방향의 변화도 있다.
- Bistro 의자/바닥 ROI에서는 국소적인 filtering 변화가 있지만 원본④의 얇은 구조를 모두 회복하지 못한다.
- 두 장면 f190–239에서 ⑨·⑩ RGB는50프레임 모두 같았다. 정지 안정성과 이동 품질은 구분한다.
- 독립 object-motion/disocclusion 장면을 이번에 평가하지 않았으므로 전역 고스팅 개선을 확정하지 않는다.
- ④는 jitter/subsample On, ⑥·⑨·⑩는 Off다. RGB filter 효과의 직접 대조는⑨↔⑩다.
- 수치가 높거나 오차가 작더라도, 위 선 소실을 품질 동등·개선 성공으로 덮지 않는다.

## 공식 평가 경계 및 제외 실행

Intel 공식 CGVQM commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`과 CUDA/patch_scale4/mean pooling을 사용했다.
모델과 공식 소스를 수정하지 않았다. 긴120프레임 실행의 CPU 메모리 부족 후, 기존 절차의60프레임
독립 호출을 사용했다. 공식30프레임 temporal patch 경계를 유지하며 동일 patch 수의 mean score를 합친다.
부동소수 reduction 순서 차이를 고려해 두 장면의④ 이동/전환을 기존 full-window score와2e-5 이내로 검증했다.
모든 완료 호출에서 test/reference FFV1 decoded RGB mismatch0이다. 원본 해상도1920×1061 및 공식 spatial padding은 유지했다.
최종 PNG만 포함한 입력은 원본 파일을 바이트 그대로 복사하고 SHA-256을 비교했다. 진단 PNG는 평가 입력에 넣지 않았다.
완료된 장면의 임시 PNG 복사본과 반복 생성한 참조 FFV1 복사본은 저장 공간을 위해 제거했다.
원본 test/reference PNG, test FFV1, 결과·로그 및 해시 불일치 제외 실행은 보존했다. 참조 FFV1은 원본 PNG로 재생성할 수 있다.
120프레임 OOM, 진단 PNG 이름 검증 실패, 일부 번호만 복사한 초기 입력 집합 검증 실패는 점수 없이 제외했다.
Minecraft⑨ 전환의 최초 모델 결과는 입력 metadata hash가 원본/복사본의 hash와 달라 별도로 보존하고 제외했다.
독립 재읽기는 두 환경에서 같은 원본 hash를 냈지만 최초 불일치 원인은 확정하지 않았다. 새 프로세스에서 재평가한 검증 결과만 채택했다.
각 실패는 평가 입력 준비 단계이며 AA 코드를 수정한 것이 아니다.

## 비교 자료

- [Bistro GIF25FPS](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/tmp/edge-bilinear-history-rgb-media/bistro-sampler-slow.gif)
- [Minecraft GIF25FPS](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/tmp/edge-bilinear-history-rgb-media/minecraft-sampler-slow.gif)
- [Bistro MP4 60FPS](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/tmp/edge-bilinear-history-rgb-media/bistro-sampler-60fps.mp4)
- [Minecraft MP4 60FPS](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/tmp/edge-bilinear-history-rgb-media/minecraft-sampler-60fps.mp4)
GIF 공통256색 palette와 H.264는 표시 보조 자료다. 평가는 원본 PNG로 수행했다.
