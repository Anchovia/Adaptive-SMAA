# ⑪ 선택적 resolved RGB feedback — 현재 검증 결과

⑪은 독립 브랜치 `experiment/edge-persistence-resolved-rgb-feedback`에 구현했다.
현재 단계의 결론은 **RGB 누적 구현의 정확성은 검증됐으나, 직접 프레임 비교에서
이동 중 얇은 선의 대비 감쇠·재출현이 남아 있어 품질 개선 gate는 통과하지 못했고
정식 성능 측정은 보류**라는 것이다. 사용자가 게임 실행 중이라고 알려
진행 중인 benchmark만 중단했다. 게임 부하가 있는 측정값은 표에 넣지 않았다.

## 구현 차이

| 구성 | Spatial SMAA | 선택 영역 | History RGB | Pattern | History weight |
|---|---|---|---|---|---|
| ④ `O-T2X-R` | Original Ultra | 전체 화면 | 직전 spatial frame | On | 원본 alpha 기반 0..0.5 |
| ⑩ `ABL-ET2X-R-PreviousRawEdge-BilinearRGB` | Original Ultra | 현재 edge + 재투영한 직전 raw edge | 직전 spatial frame, bilinear | Off | 원본 point alpha 기반 0..0.5 |
| ⑪ `ABL-ET2X-R-PreviousRawEdge-ResolvedRGB` | Original Ultra | ⑩와 동일 | 직전 temporal 출력 RGB, bilinear | Off | ⑩와 동일 |

⑪은 alpha에 현재 spatial velocity 정보를 보존한다. 따라서 RGB feedback 변경과
weight 변경을 섞지 않았다. Camera/depth reprojection만 사용하며 object motion을
지원한다고 표현하지 않는다. 지터, 3×3 확장, clipping, 5-fetch나 높은 고정 weight는
이 실험에 추가하지 않았다. 확보한 Intel TSCMAA 전체와 같은 구현이라고 하지 않는다.

기존 3차 spatial pass에서 현재 spatial 입력, 화면 seed, 다음 history seed를 MRT로
함께 저장하고, 기존 선택적 temporal draw에서 화면과 다음 history를 동시에 갱신한다.
비선택 픽셀은 현재 spatial 결과를 유지한다. 추가 draw나 전체 화면 CopyResource는
없지만 **별도 current-spatial texture 한 장과 추가 MRT 쓰기 비용은 있다**. 시간 측정이
끝나기 전에는 이 비용이 작거나 성능을 개선한다고 단정하지 않는다.

## 정확성 확인

- Release x64 build, 16 shader compile, 기존 ⑩ 생산 entry 10개의 DXBC byte 보존: PASS.
- 두 scene Test6의 first-frame seed와 frame3 reset: PASS.
- 두 scene × 240 frame에서 기존 ④·⑩ 대조군 총960 decoded RGB frame mismatch: 0.
- Scene별43 진단 frame에서 raw/current/velocity/edge/coverage/weight 입력 일치: PASS.
- ⑪ 저장 history RGB=실제 화면 출력, alpha=현재 spatial alpha: mismatch0.
- 연속 진단38곳/scene에서 이번 previous history=직전 stored history: mismatch0.
- 비선택 픽셀=current spatial 결과: mismatch0.

캡처 진단용 readback·coverage·weight·query는 정식 timing에서 끈다. 초기 Minecraft
capture의 원본④ mode-check 실패는 해당 실행 전체를 제외했다. 자동 실험 중 AA
단축키로 mode를 바꿀 수 있는 sample 입력 경로를 차단하고, 실패 설정값을 저장하도록
보완한 뒤 위 대조군 bridge를 재검증했다. 기존 실패 로그만으로 실제 입력 원인을
단정하지 않는다. [제외 기록](excluded-runs.json)을 보존한다.

## 직접 프레임 검사와 보조 지표

두 scene의 원본 전체 frame130과 얇은 선 확대를 직접 열었다. 이동130–135,
이동→정지178–183, 안정 정지190–195를 각각 연속6 frame으로 비교했다.
확대는 nearest2×이며 밝기·색상 보정을 하지 않았다. 검사한 경로·해시는
[직접 검사 기록](visual-inspection.json)에 있다. 실시간 영상을 직접 보았다고 주장하지
않으며, 아래 GIF/MP4는 사용자의 재생 확인을 위해 제공한다.

Bistro 의자 다리에서는 ⑩·⑪이 시각적으로 매우 가깝고, ④의 얇은 선 디테일을
회복했다고 판정할 수 없다. Minecraft 이음선에서도 ⑩·⑪의 가는 경계 대비가
프레임마다 바뀌며, ⑪에서 선 연속성이 확실히 개선됐다는 증거는 확인하지 못했다.
안정 정지 구간의 안정성은 이동 중 반짝임 제거를 의미하지 않는다. 현재로서는
**feedback 하나만으로 반짝임 해결 성공 또는 기본 채택으로 판정하지 않는다**.

### 사용자 요청에 따른 ④·⑪ 직접 비교 확대 (2026-10-06)

새 기법을 제안하기 전에 보존된 원본 PNG로 ④와 ⑪을 직접 대조했다. 새 GPU 실행,
렌더 캡처, CGVQM 또는 성능 측정은 하지 않았다. 두 장면에서 이동126–131·150–155,
이동→정지178–183, 안정 정지190–195의 연속6 frame씩을 확인했다. Bistro의 의자 다리와
창틀, Minecraft의 벽 이음선과 나뭇잎을 각각 nearest2×로 검사했다. 전체 화면130·180도
열었다. 문제가 보인 Minecraft 이음선은124–135로 전후를 확장해 nearest4×로 확인했다.
Bistro 의자 다리의 세부 ROI는126–131을 nearest3×로 확인했다. 밝기·색상 보정은 없다.

| 검사 대상 | 직접 확인한 현상 | 판정 범위 |
|---|---|---|
| Minecraft 벽 이음선124–135 | ⑪에서 세로 선 일부가 크게 희미해졌다가 재출현한다. 특히129의 아래쪽 선은④에 남아 있으나⑪에서는 매우 약하고,130에서는⑪에도 다시 뚜렷해진다. | 이동 중 선 연속성·대비 보존 문제를 확인했다. 단순한 고정 선명도 차이로 처리하지 않는다. |
| 같은 이음선의④ | ④도127·132 등에서 선 일부가 약해진다.150–155에는⑪이 선을 더 유지하는 프레임도 있다. | 모든 프레임에서⑪이④보다 나쁘거나④가 완전히 안정적이라고 일반화하지 않는다. |
| Bistro 의자 다리126–131·150–155 | ⑪에서도 가는 다리의 픽셀 계단과 대비 변화가 남는다.④의 회색 부분 표본과 다른 강한 경계가 나타난다. | 안정화 성공은 확인되지 않았다. 이 ROI에서 의자 다리 전체가 사라졌다고 판정한 것은 아니다. |
| 창틀·나뭇잎 |⑪의 미세 경계·텍스처 변동이 남으며, 구조 유지의 일관된 우위를 확인하지 못했다. | 잔상 길이·고스팅 감소의 확정 근거로 사용하지 않는다. |
| 안정 정지190–195 | 두 장면 모두 각 case의 전체 RGB가 연속5쌍에서 완전히 동일하다. | 검사한 안정 정지 구간의 떨림은 없으며, 이동 중 결함과 구분한다. |

따라서⑪은 **이동 중 얇은 구조 유지와 반짝임 해결을 위한 품질 gate 미통과**로 기록한다.
GPU feedback 저장과 비선택 출력 검증의 PASS는 그대로 유효하지만, 품질 PASS를 뜻하지
않는다.④는 Pattern On,⑪은 Off이고 선택 영역·sampling·feedback도 다르므로, 이 관찰만으로
선택 마스크·누적 weight·지터 중 어느 요소가 원인인지 확정하지 않는다. 후속 판단은 실패
위치의 current spatial·실제 선택 여부·history·혼합 후 출력을 연결해서 조사한 뒤 한다.

[직접 검사 기록](frame-review-4-vs-11.json)에 원본·확대 좌표·frame·hash를 보존했다.
[④·⑪ 비교 PNG와 동일 구간 GIF](C:/Users/USER/Desktop/research/Deliverables/SMAA_4_11_FrameReview_20261006/comparison.html)
는 사용자 검토용이다. GIF는76 frame(120–195)을25fps로 재생하고 팔레트 손실이 있으므로
판정은 무손실 PNG를 기준으로 했다. GIF의 실제 재생을 직접 보았다고 주장하지 않는다.

아래는 supersample **spatial proxy** 대비 ROI RGB MAE다. 낮을수록 해당 참조와 가까우나
절대 temporal ground truth 또는 반짝임 점수가 아니다. Bistro ROI=(1230,582,1358,670),
Minecraft ROI=(956,524,1020,620). Moving60–179, transition172–189, still190–239.

| Scene/window | ④ RGB MAE | ⑩ RGB MAE | ⑪ RGB MAE |
|---|---:|---:|---:|
| bistro moving | 4.3815 | 5.4926 | 5.3126 |
| bistro transition | 4.0526 | 5.5773 | 5.4382 |
| bistro still | 3.8968 | 5.8828 | 5.8197 |
| minecraft moving | 1.6265 | 1.2654 | 1.2535 |
| minecraft transition | 1.7016 | 1.7712 | 1.7589 |
| minecraft still | 1.2391 | 1.9865 | 1.9773 |

⑪의 MAE가 ⑩보다 조금 낮아도 이것만으로 체감 품질 우위를 확정하지 않는다.
⑪ CGVQM은 아직 실행하지 않았다. 보존④·⑩의 공식 점수와 새로운⑪ 점수는 입력·참조
hash bridge를 확인한 별도 CUDA 분석 후에만 함께 표로 정리한다.

## 성능과 남은 작업

**정식 paired 성능 수치 없음.** 사용자가 게임 중이라고 알려 Bistro benchmark를
해당 프로세스만 종료했다. 부분 수치와 관련 Smoke는 정식 성능 자료에서 제외했다.
Minecraft benchmark는 시작하지 않았다. 다른 구현의 이전 절대 시간을⑪의 결과로
대체하지 않는다.

게임 종료 후 same-binary Smoke → scene별④·⑩·⑪4800 frame×6회 교차 Benchmark →
보조 CGVQM → 실제720-frame long capture 순서로 이어간다. 추가 GPU 작업 없이
보존240 frame으로 만든 현재 영상은 정상60fps4초, 느린 GIF25fps9.6초다. 긴 영상을
만들기 위해 짧은 source를 반복하지 않았다.

[현재 GIF·영상 모음](C:/Users/USER/Desktop/research/Deliverables/SMAA_4_10_11_Feedback_20261006/comparison.html)

재개 명령과 실행파일 해시는 [재개 지점](resume.md)에 기록했다. 사용자 영상 검토 및
idle-GPU 수치가 확보되기 전에는⑪을 최종 연구 구현으로 확정하지 않는다.
