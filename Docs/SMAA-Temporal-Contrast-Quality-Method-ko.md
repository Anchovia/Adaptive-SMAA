# Temporal contrast 선택의 기준 영상 품질 평가

`experiment/standard-t2x-reuse`의 세 threshold 0.005/0.01/0.02를
원본 `O-T2X-R`과 비교한다. 공간 SMAA와 temporal 계산식을 바꾸지 않고,
기존 캡처에 대응하는 supersample spatial reference와 세 선택 마스크를 추가했다.

## 입력과 대응 검증

- 1920×1061, DX11, Original SMAA Ultra, camera-motion reprojection On.
- fixed 60 Hz, 원본 flythrough time 2초에서 60 frame 정지, 120 frame 이동,
  time 4초에서 60 frame 정지. 기존 240-frame 품질 캡처와 같은 경로다.
- 새 quality capture는 원본 T2X-R, 세 threshold의 mask, SS-Reference를 각각 저장한다.
  mode마다 60 frame warm-up과 timeline 시작 시 history/jitter reset을 적용한다.
- 원본 240장 및 기존 threshold 0.01 mask 240장의 파일 SHA-256 일치를 확인한 뒤
  기존 세 threshold의 최종 출력과 새 reference를 연결한다.
- 세 mask의 이진 값과 포함 관계 `0.02 ⊆ 0.01 ⊆ 0.005`를 모든 frame에서 검사한다.
  세 최종 출력 모두 선택 pixel은 원본 T2X-R, 생략 pixel은 현재 spatial 결과와 일치해야 한다.
- 모든 CMAA2 실행은 독립 process이며 정상 종료와 실행 전후 process 0개를 확인한다.

## 기준 영상의 정의

기존 renderer의 `SuperSampleReference`를 사용한다. 가로·세로 2배 해상도,
frame 안에서 3×3 subpixel grid, 8×MSAA이며 모든 subpixel sample은 같은 장면 시점을 공유한다.
여기서 3×3은 기준 영상을 만드는 표본 배치이며 temporal 후보의 3×3 dilation이 아니다.
temporal history를 사용하지 않는다. baseline 기본값인 MIP bias 0.95,
sharpen 0.12, derivative bias 0.20을 기록한다. 이 튜닝을 포함한 공간 기준 영상이며
절대 temporal ground truth나 무조건 완벽한 reference라고 표현하지 않는다.

Bistro 후기 정지 reference는 처음 적용한 PNG hash 단일값 검사에 실패했다.
확인 결과 인접 frame에서 RGB8의 극소수 channel 값만 1 level씩 달랐다.
검사를 없애는 대신 frame별 최대 변화·변경 channel 수·평균 변화량을 결과에 보존하고,
최대 1 level 및 16 channel 이내라는 수치적 변화 상한으로 재검사한다.
이 상한은 관측 후 설정한 engineering 검증 조건이며 지각 품질 임계값이 아니다.
Minecraft reference는 후기 정지에 PNG가 완전히 같았다.

## 측정 지표

- RGB MAE, RGB PSNR: 240 frame 전체의 화면 RGB8 결과를 기준 영상과 비교한다.
  PSNR은 각 frame dB의 산술 평균이다. MAE 단위는 0~255 RGB level이다.
- Luma SSIM: 11×11 Gaussian, sigma 1.5, 반사 경계, 5-pixel border 제외.
  보조 지표로 frame 0,10,...,230에서 계산한다. 각 구간 표에는 그 구간의 표본 평균을 기록한다.
  이동 구간은 12개, 정지 후기는 4개의 SSIM 표본이다.
- Sobel edge/reference 비율: 기준 영상에 비해 선명도·고주파 성분이 어떻게 바뀌는지 보는
  보조 지표다. 높은 값이 항상 좋은 품질을 의미하지 않는다.
- 시간 변화: 화면 luma의 인접 frame 차이와
  `abs((test[t]-test[t-1])-(reference[t]-reference[t-1]))` 평균.
  후자는 기준 영상의 화면상 변화를 뺀 잔차이며 optical flow나 순수 ghosting 지표가 아니다.
- CGVQM-2: Intel 구현 commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`,
  CUDA, patch scale 4, mean pooling, 60 FPS. 점수가 높을수록 해당 기준 영상에 대한
  지각 품질 예측이 좋다. 점수 차이의 통계적 유의성이나 사람의 확정적 선호를 주장하지 않는다.
  PNG→RGB FFV1→decoded RGB의 완전 일치를 검사한다.
- 1061 높이는 4의 배수가 아니므로 공식 CGVQM이 error-map 해상도 경고를 출력한다.
  모든 비교 영상에 동일한 원본 해상도와 공식 경로를 적용하며 임의 crop이나 score 보정을 하지 않는다.
- CGVQM은 이동 frame 60~179와 이동→정지 frame 160~219를 별도 clip으로 평가한다.
  두 구간은 일부 겹친다. clip 경계의 모델 padding 영향을 포함하므로 독립 표본 평균처럼 합치지 않는다.
  공식 per-frame error-map 통계와 기준 영상 차이 이미지를 함께 보존한다.

## 선택 픽셀 수

원본 temporal resolve 대상은 frame당 `1920×1061 = 2,037,120 pixel`이다.
세 GPU mask에서 흰 pixel 수를 직접 세고 평균·최소·최대와 비율을 보고한다.
분모는 검출 edge 수가 아니라 전체 출력 pixel 수다. 선택은 velocity/history 읽기와
T2X 계산을 수행한다는 뜻이며, native 가변 weight 때문에 history의 실제 기여가 0인 경우도 있다.
현재 색상 읽기와 최종 쓰기는 생략되지 않는다. 이 개수를 GPU 실행 시간 감소율로 해석하지 않는다.

## 실행

```powershell
Tools/SMAA/run_temporal_contrast.ps1 -Phase QualityCapture -Scene bistro -QualityFrames 12 -Receipt tmp/contrast-quality-smoke.json
Tools/SMAA/run_temporal_contrast.ps1 -Phase QualityCapture -Scene bistro -Receipt tmp/contrast-quality-runs.json
Tools/SMAA/run_temporal_contrast.ps1 -Phase QualityCapture -Scene minecraft -Receipt tmp/contrast-quality-runs.json
python Tools/SMAA/analyze_temporal_contrast_reference.py --scene bistro --capture <old-capture> --quality-capture <new-capture> --output <analysis>
python Tools/SMAA/run_temporal_contrast_cgvqm.py --analysis <analysis> --cgvqm-root <official-CGVQM-clone>
python Tools/SMAA/create_temporal_contrast_playback.py --analysis <analysis>
```

CGVQM 단계는 기존 CGVQM 전용 Python 환경에서 실행한다. CMAA2 캡처가 모두 종료된 뒤
GPU 영상 평가는 순차 실행한다. 이번 작업은 품질 측정이며 기존 속도 수치는 다시 측정하지 않는다.
