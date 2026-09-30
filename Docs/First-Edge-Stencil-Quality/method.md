# 첫 edge 선택 구현의 품질 평가

Branch: `research/first-edge-stencil-quality`, 직접 base `c51ca28`.
이 브랜치는 분석 도구와 결과만 포함하며 렌더러·shader·①~⑥ 구현을 바꾸지 않는다.
⑤ `ba1761d`, ⑥ `53ff61d`의 독립 구현과 기존 기준선의 검증된 캡처를 사용한다.
도구 의존성은 `tool-imports.json`, flow 함수 출처는 `flow-provenance.json`에 기록한다.

## 비교와 재사용 조건

① AA-Off, ② original SMAA 1X, ③ raw full-screen temporal, ④ original SMAA T2X-R,
⑤ raw first-edge stencil, ⑥ original spatial + first-edge stencil을 비교한다.
①·②는 지터 Off, ③·④는 원본 paired pattern On, ⑤·⑥은 pattern Off다.
추가 raw/spatial full-screen Pattern-Off 대조군을 이용해 pattern과 선택 효과를 분리한다.
모든 temporal은 camera/depth reprojection과 원본 point/history-weight 계산을 사용한다.
Independent object-motion velocity나 최종 8-case 연구 완료를 의미하지 않는다.

두 장면은 Bistro/Minecraft, 1920×1061 Ultra, fixed 60 FPS이며 240 frame의
정지 0~59 / 이동 60~179 / 정지 180~239 경로다. Frame 180은 마지막 이동 pose에
도착하는 프레임이므로 단순한 무조건 history 오류로 분류하지 않는다.
새 출력과 기존 CGVQM 입력의 index+RGB hash, 동일 reference hash, 모델 commit,
patch scale/pooling/device 설정이 같을 때만 기존 점수를 재사용한다. ①·③ 점수만 새로 계산한다.
CGVQM 이동 window는 60~179, 전환 window는 160~219다. 기존에 검증된 30-frame 추론
경계를 보존한 60-frame 분할을 재사용하며 모델 코드는 수정하지 않는다.

## 분석 지표

- 원본 RGB에서 full-frame/ROI MAE, MSE 기반 PSNR, luma SSIM을 계산한다.
- 얇은 구조는 reference의 Sobel edge 오차와 gradient 크기 비율도 기록한다. 비율이
  높다고 선명도가 무조건 좋다고 하지 않으며 과도한 aliasing도 함께 확인한다.
- Optical flow는 모든 mode에 공통인 SS-Reference에서 계산한다. 기존 Farneback
  함수·파라미터와 합성 이동 검사를 재사용하며 forward/backward error <=1 pixel과
  in-bounds 조건을 만족한 위치만 정렬 지표에 사용한다. 유효 비율도 함께 기록한다.
- 정렬 후 mode의 시간 차분에서 reference의 시간 차분을 뺀 잔차를 기록한다.
  정상적인 장면 변화/표본 재구성 오차와 정렬 오차를 완전히 제거한 ground truth는 아니다.
- 가려짐 경계는 reference 오차와 연속 확대 영상으로 별도 확인한다. Flow 불일치를
  진짜 disocclusion mask라고 부르거나 단일 오차를 절대 고스팅 양으로 부르지 않는다.
- 이동 후 정지 안정화는 각 mode 자체의 후기 정지 frame 239와의 차이를 측정한다.
  안정화 속도와 reference에 대한 정확도를 분리한다.
  마지막 40-frame 전체의 byte 일치를 요구하며, 마지막 frame만 자기 자신과 일치하는
  경우를 안정화로 잘못 세지 않는다. 불일치의 면적·크기도 따로 확인한다.
- Edge 선택 여부가 시간에 따라 바뀌는 위치와 비선택 영역의 오차도 별도로 기록한다.
  영역 구분은 모든 mode에 공통으로 ⑥의 jitter Off RG mask를 사용한다. 전환은 같은
  화면 좌표의 mask 차이이며, 동일 물체를 추적한 후보 지속성 지표는 아니다.

## 사전 고정한 화면 ROI

공통 reference frame 100의 구조를 보고 정했으며 결과 순위로 고르지 않았다.
좌표는 원본 1920×1061의 `(left, top, right, bottom)`이며 object tracking은 아니다.

| 장면 | ROI | 좌표 | 확인 대상 |
|---|---|---|---|
| Bistro | chair-legs | (320,540,720,820) | 얇은 의자·테이블 다리 |
| Bistro | foreground-boundary | (560,440,920,720) | 가로등·입간판과 배경 경계 |
| Bistro | window-rails | (880,420,1240,700) | 창살·의자와 고대비 배경 |
| Minecraft | stone-steps | (230,610,590,890) | 계단·블록 윤곽 |
| Minecraft | foliage | (1210,735,1570,1015) | 세부 잎 무늬의 shimmer |
| Minecraft | foreground-boundary | (980,250,1340,530) | 앞쪽 블록과 뒤쪽 벽 경계 |

비교 영상은 동일 frame의 MP4 60 FPS와 확대 PNG로 만든다. 표시용 확대·Bistro 밝기
배율은 모든 mode에 동일하게 적용하고 명시한다. 수치는 배율을 적용하지 않은 PNG에서만
계산한다. MP4/GIF의 압축·팔레트 차이를 품질 수치로 사용하지 않는다.

Supersample 참조는 동일 pose의 공간 품질 proxy이며 완전한 temporal ground truth가 아니다.
검사 범위 밖의 물체 움직임/큰 가려짐 해제 상황은 별도 후속 검증으로 남긴다.

## 재현 순서

렌더러를 실행하는 실험이 아니라 고정 commit에 기록된 기존 PNG를 분석하는 작업이다.
캡처 경로와 source commit은 `stencil_quality_common.py` 및 `*-sources.json`에 있다.
실제 이미지 index/RGB hash가 기존 score 입력과 같아야 점수를 재사용한다.
원시 캡처와 대용량 영상은 Git에 넣지 않고 D 드라이브에 보존한다.

1. 기존 CGVQM 전용 환경에서 `evaluate_stencil_quality.py --scene bistro`와
   `--scene minecraft`를 각각 실행한다. 공식 모델 commit/runtime과 기존 분할 추론
   bridge를 검사하고, 누락된 ①·③ 점수를 계산한다.
2. `quality-requirements-lock.txt`의 독립 환경에서 `analyze_stencil_quality.py`와
   `visualize_stencil_quality.py`를 장면별로 실행한다. 기존 CGVQM 환경은 변경하지 않는다.
3. 모든 장면의 CGVQM·metrics·visuals가 PASS일 때 `report_stencil_quality.py`로
   비교표와 그래프를 생성한다. raw PNG stream hash 및 영상 frame/PTS 검증을 포함한다.

명령 파일은 모두 `Tools/SMAA/` 아래에 있다. 원시 자료가 저장된 D 드라이브의 출력
경로는 로컬 설정이며, 다른 환경에서 재실행할 때에는 manifest 경로를 명시적으로 옮겨야 한다.
논문용 비교의 범위를 넓히려면 별도 장면·동작 검증이 필요하며 이 분석이 이를 대신하지 않는다.

## 저장공간 정리 이후의 재현

2026-09-30 사용자 요청으로 저장공간을 정리하면서, 완료된 평가의 `LosslessInputs/`
아래 FFV1 입력 변환 파일을 삭제했다. 원본 PNG 전체 프레임과 완료된 변환 검증 기록이
남은 경우에만 정리했으며, 측정 JSON/CSV·오류 지도·비교 영상·원본 캡처는 보존했다.
결과 JSON의 FFV1 경로와 round-trip 기록은 측정 당시의 provenance이며 현재 파일의
존재를 보장하지 않는다. 새 추론이 필요한 경우 보존된 PNG에서 다시 변환한다.
보고서 열람과 저장된 점수 비교에는 입력 영상 재생성이 필요하지 않다.
정리 후 보고서 입력·비교 자료 32개 hash가 이전과 일치함을 확인했다.
