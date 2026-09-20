# ScalarWeight 품질 검증 조건

## 비교 범위

`O-T2X-R`과 `ABL-ScalarWeight-001-R`의 비교다. Original spatial SMAA,
camera/depth reprojection, 공식 paired jitter/subsample pattern과 이전 spatial-frame
history를 유지한다. Object motion, Adaptive spatial, 후보 확장 실험이 아니며 최종
8-case 결과로 사용하지 않는다. Shader와 renderer는 이번 작업에서 변경하지 않았다.

ScalarWeight는 현재 색상의 linear-light luma에 대해
`max(abs(ddx_fine(luma)), abs(ddy_fine(luma))) >= 0.01`을 사용한다.
선택되지 않은 픽셀은 history weight가 0이다. 모든 픽셀의 velocity/history를 읽으므로
선택 비율은 texture 접근을 생략한 비율이나 최종 weight가 양수인 비율이 아니다.
예전 `ABL-Contrast-001-R`은 동일 선택식의 early-return 구현이다.

## 기존 품질 자료의 재사용 검증

2026-09-21 Cost capture의 ScalarWeight/branch/native/mask와 2026-09-17의 품질
평가용 출력 및 reference control을 비교한다. 두 장면 각각 240 frame, 1920×1061,
고정 60 Hz, 초기 정지 60 frame → 이동 120 frame → 정지 60 frame이다.

각 장면에서 6개 sequence pair, 총 1,440개의 PNG SHA-256 비교를 한다.
ScalarWeight↔예전 branch, ScalarWeight↔같은 capture branch, native↔예전 native,
mask↔예전 mask, native↔reference capture의 native, mask↔reference capture의 mask다.
추가로 decode한 native/ScalarWeight의 전체 RGB stream hash를 예전 품질 JSON과 비교하고,
모든 frame에서 선택 픽셀은 native와, 비선택 픽셀은 당시 current-spatial control과
정확히 같은지 검사한다. 누락·추가 frame과 해상도 차이는 실패 처리한다.

CGVQM-2는 새로 실행하지 않는다. 이동 60~179와 전환 160~219의 현재 PNG와 reference를
다시 읽고 frame index를 포함한 RGB hash를 원래 공식 실행 결과와 비교한다.
원래 FFV1 왕복 무손실 검증 결과와 score 일치도 확인한 뒤 그 점수를 재사용한다.
RGB MAE/PSNR/SSIM과 선택 비율도 정확히 같은 출력에 대한 기존 결과를 사용한다.

## 새로 계산하는 진단

- 정지 후기 200~239: RGB frame hash 종류 수, 두 frame 간격의 불일치 수,
  인접 frame RGB 절댓값 차이의 평균. 인접 차이는 201~239의 39쌍만 사용한다.
- 같은 정지 구간의 ScalarWeight 변화량을 두 frame 모두 비선택, 모두 선택,
  선택 여부가 바뀐 위치로 나눈다. 그룹별 절댓값 변화 합/전체 합과 변경 픽셀 수를
  기록한다. 선택 변화 자체가 모든 깜빡임의 원인이라고 가정하지 않는다.
- 기존 영상 검토에서 정한 고정 ROI를 그대로 사용한다. Bistro `(420,590)-(900,910)`,
  Minecraft `(720,240)-(1200,560)`. 가로 480×세로 320이며 object tracking은 아니다.
- ROI의 RGB MAE, 표시 RGB luma의 수평·수직 전방 차분과 reference 차분 사이 MAE,
  평균 절대 차분 크기의 reference 대비 비율을 계산한다. ROI 우측·하단 한 줄을
  제외한 공통 영역에서 두 방향을 같은 비중으로 집계한다. 이것은 세부 구조 오차의
  보조 지표이며 순수 블러·선명도나 고스팅 점수가 아니다. Shader의 linear luma와
  이 표시 RGB 분석 공간은 구분한다.

## 육안 검토 자료와 한계

세 열은 공간 supersample reference / 원본 T2X-R / ScalarWeight 순서다.
같은 crop의 240 frame을 60 FPS MP4로 만들고 전체 decode의 frame 수·PTS를 검증한다.
이동·전환·정지의 0.5배속 GIF는 공통 palette와 dithering Off를 사용한다.
연속 PNG sheet와 정지 차이 ×8도 제공한다. ×8 이미지는 미세 변화의 위치를 보여주는
진단 자료이며 실제 체감 강도가 아니다. MP4/GIF는 압축·색 양자화가 있으므로 수치는
원본 PNG에서만 계산한다. 연속 PNG 검토를 다수 관찰자의 정속 영상 평가로 표현하지 않는다.

Reference는 한 시점의 2배 선형 해상도·3×3 subpixel sampling·8×MSAA를 합친
공간 기준이다. 여기서 3×3은 후보 dilation이 아니다. 기존 MIP/sharpen 설정을 포함해
절대 temporal ground truth로 보지 않는다. CGVQM 하락과 ghosting 악화를 동일시하지
않는다. 기존 카메라 경로의 가려짐 경계는 볼 수 있지만 별도 object-motion이나
깊이로 표시한 disocclusion mask가 없어 고스팅 감소율·잔상 지속 시간을 확정하지 않는다.

## 재현

활성 worktree 루트에서 실행한다. Python 환경에는 NumPy, Pillow, PyAV가 필요하다.
기존 Cost receipt `tmp/temporal-cost-final-runs.json` 및 그 안의 원시 capture가 필요하다.
원시 영상은 Git 외부 AutoBench에 보존하며 실행별 경로와 hash는 `results.json`에 있다.

```powershell
& 'C:/Users/USER/Desktop/research/.research-tools/cgvqm-venv/Scripts/python.exe' `
  Tools/SMAA/analyze_scalar_temporal_quality.py --root . `
  --output Projects/CMAA2/AutoBench/ScalarQualityReview `
  --summary Docs/Temporal-Contrast-Scalar-Quality/results.json
```

새 GPU 실행이나 성능 측정은 없다. 성능 판단에는 별도 독립 프로세스 짝 비교인
`Docs/Temporal-Contrast-Pair/report.md`를 사용하고, 예전 branch timing을 ScalarWeight의
속도로 옮기지 않는다.
