# 선택적 temporal 결합과 표본 패턴의 상호작용

기준 commit `a4c24c8`, branch `experiment/temporal-contrast-jitter-ablation`.
현재 luma 선택식과 threshold 0.01을 유지하고 표본 패턴의 영향을 분리하는 진단이다.
새 선택식, 후보 확장, history rejection, spatial Adaptive를 추가하지 않는다.

## 네 가지 조건

| 이름 | Temporal 계산 | Projection jitter | Area texture subsample indices |
|---|---|---|---|
| O-T2X-R | 원본 full-screen | 기존 2-phase | 기존 S0/S1 |
| ABL-ScalarWeight-001-R | 동일 계산, 비선택 weight 0 | 기존 2-phase | 기존 S0/S1 |
| ABL-Standard-PatternOff-R | 원본 full-screen | 0 | 1X의 (0,0,0,0) |
| ABL-ScalarWeight-001-PatternOff-R | 동일 계산, 비선택 weight 0 | 0 | 1X의 (0,0,0,0) |

지터 Off는 projection만 끄고 S0/S1을 계속 교대하는 조합이 아니다. 공식 SMAA가
설명하는 jitter/subsample pairing을 고려해 둘을 함께 변경한다.
[공식 통합 안내](https://github.com/iryoku/smaa/blob/master/SMAA.hlsl),
[공식 sample의 subsample 처리](https://github.com/iryoku/smaa/blob/master/Demo/DX10/Code/SMAA.cpp).

Off는 temporal supersampling을 제거한 진단이며 공식 SMAA T2X라고 부르지 않는다.
전체 공간 처리와 표본 패턴의 효과를 포함하므로 projection jitter 하나의 독립 효과로
해석하지 않는다. 두 Off 조건끼리는 같은 1X spatial 경로를 사용한다.

Camera/depth velocity, 원본 point history sampling, alpha 기반 가변 weight 0~0.5,
spatial-frame history ping-pong, first-frame seed, 모든 reset은 유지한다.
Object motion은 포함하지 않는다. 원본 On을 최종 비교 기준으로 보존한다.
샘플 패턴을 바꾸면 입력 색상도 달라지므로 같은 선택식을 써도 후보 mask는 달라질 수 있다.
이 때문에 On/Off의 실제 후보 수와 mask 전환도 별도로 센다.

## 실행과 검증

`-smaaTemporalContrastJitterCapture bistro|minecraft`는 기존 240-frame fixed-60-Hz
카메라 경로(60 정지→120 이동→60 정지)와 60-frame resource warmup을 사용한다.
모드마다 frame 0에서 history와 phase를 다시 초기화한다. 네 출력 외에 On/Off의
mask/current-spatial control, 두 Off 출력의 반복 실행을 함께 저장한다(총 10 sequence).
장면별 clean process, 1,200초 timeout, 실행 전후 CMAA2 process 0개 조건을 적용한다.

매 capture frame의 CPU에서 제출한 subsample constants와 pattern 설정, jitter offset
크기를 검사한다. 이는 GPU constant-buffer readback이 아니므로 그렇게 표현하지 않는다.
On 출력/native/mask/current-spatial은 기존 capture와 전체 frame PNG hash를 비교한다.
Off 두 mode는 모드 전환 후 반복 capture와 전체 frame hash를 비교한다.
모든 frame에서 선택 출력은 대응 원본 출력, 비선택 출력은 대응 spatial control과 같아야 한다.
첫 frame은 두 출력 모두 대응 spatial control과 같아야 한다.

정지 구간의 RGB hash 종류 수·lag-2 hash·인접 변화, 이동·전환의 reference 대비 RGB
MAE/PSNR과 화면 luma 시간 차분 잔차를 계산한다. 공간 supersample reference는 기존
동일 경로 자료를 재사용하고, 공통 On 출력의 hash 일치로 타임라인 대응을 확인한다.
Reference는 공간 기준이지 절대 temporal ground truth가 아니다. 새 CGVQM 평가나
GPU 성능 benchmark는 이번 원인 분리 실험의 범위가 아니다.

## 판정 원칙

Off에서 정지 깜빡임이 사라지는 것은 패턴과 선택적 결합의 상호작용을 지지한다.
그것만으로 선택 방식의 품질 우위나 지터 제거의 채택을 결정하지 않는다. 공간 세부 구조
손실, 이동 중 불안정성과 대응 full-screen Off 대비 차이도 함께 확인한다.
또한 품질 변화의 전부가 지터 때문이라거나 기존 측정이 무효였다고 해석하지 않는다.

```powershell
Tools/SMAA/run_temporal_contrast.ps1 -Phase JitterCapture -Scene minecraft -Receipt tmp/temporal-jitter-runs.json
Tools/SMAA/run_temporal_contrast.ps1 -Phase JitterCapture -Scene bistro -Receipt tmp/temporal-jitter-runs.json
```

NumPy/Pillow/PyAV가 설치된 Python에서 장면별로 분석한다. 원시 capture는 Git 외부의
AutoBench에 보존하고 실행파일·보고서 hash 및 경로는 장면별 JSON에 기록한다.

```powershell
& 'C:/Users/USER/Desktop/research/.research-tools/cgvqm-venv/Scripts/python.exe' `
  Tools/SMAA/analyze_temporal_contrast_jitter.py --scene minecraft `
  --receipt tmp/temporal-jitter-runs.json `
  --output Projects/CMAA2/AutoBench/JitterAblationAnalysis/minecraft `
  --summary Docs/Temporal-Contrast-Jitter/minecraft.json
```

Bistro는 명령의 `minecraft` 세 곳을 `bistro`로 바꾼다. 품질 표의 RGB MAE/PSNR은
모든 frame에서 계산하며, 시간 잔차는 `|(test_t-test_(t-1))-(ref_t-ref_(t-1))|`의
화면 luma 평균이다. 화면 좌표 기반 잔차이므로 순수 고스팅이나 optical-flow 정렬
오차로 부르지 않는다. 각 구간 평균의 첫 frame 차분은 직전 frame을 사용한다.
초기 정지는 20~59, 이동 60~179, 전환 160~219, 후기 정지는 200~239다.
시퀀스마다 원본 PNG에서 계산하고, MP4/GIF는 육안 확인용으로만 사용한다.
