# 원본 SMAA 기준선 재검증 결과

**일반 SMAA 1X는 정지 상태에서 흔들리지 않았다. 이전의 지터 On current-spatial을 일반 SMAA 대신 사용한 비교는 정정한다.**

## 브랜치와 코드 범위

- `baseline/original-smaa` / `ee0020d`: 원본 공간 SMAA 계보.
- `baseline/smaa-t2x` / `88893da`: 원본 공간 SMAA에 Standard T2X/R을 추가한 기준선.
- `validation/smaa-baseline-restart`: `88893da`에서 직접 분기한 **기준선 검증 전용**.
- `tooling/baseline-shader-lifetime` / `c513158`: 기존 `684ac91`의 종료 수명 수정 두 파일만 독립 backport.
  검증 브랜치에는 출처를 남겨 cherry-pick했다. 선택적 처리나 지터 보정 알고리즘은 포함하지 않았다.
- 기존 `experiment/temporal-first-edge-selective`는 `214ab43`에서 결론 정정 표시를 추가했다.
  `experiment/first-edge-pattern-stability`의 `0084306`은 중단된 미검증 작업 보존본이다.
- 다음 연구 항목은 검증된 기준선에서 별도 분기한다. 항목 결합은 별도 통합 브랜치에서만 한다.

SMAA 디렉터리 14개 파일을 기준 커밋과 대조했다. 기존 알고리즘·shader·binding은 동일하며
유일한 추가는 기존 UI와 같은 품질 preset을 자동 지정하는 header accessor다.
SMAA.hlsl은 공간 원본 태그와도 동일하다. 원본 default High가 아닌 **명시적 Ultra**로 비교했다.
소스 검증은 `source-audit.json`에 파일별 SHA-256(CRLF/LF 정규화)을 남겼다.

## 독립 실행과 출력 검증

각 장면 AA-Off / O-1X / O-T2X / O-T2X-R / O-1X 반복 / O-T2X-R 반복, 각 240 frame이다.
60 Hz, 1920×1061, 원래 카메라 경로의 60 정지+120 이동+60 정지. R은 camera/depth reprojection이다.
O-1X는 `AAType::SMAA`, AA-Off는 `AAType::None`을 실행하며 current-only 진단 shader로 대체하지 않았다.

| 장면 | mode 설정 검사 | 반복 RGB 불일치 / 비교 수 | 과거 T2X-R RGB 불일치 / 비교 수 | 1X−AA Off 평균 변경 픽셀 |
|---|---:|---:|---:|---:|
| bistro | 1440 PASS | 0 / 480 | 0 / 240 | 35890.2 |
| minecraft | 1440 PASS | 0 / 480 | 0 / 240 | 197037.6 |

초기 20~59 및 후기 200~239에서 AA-Off/1X/T2X/T2X-R의 정지 RGB hash 종류 수와 인접 변화량을 검사했다.

| 장면 | 1X 후기 RGB 종류 / 변화 | 원본 T2X-R 후기 RGB 종류 / 변화 |
|---|---:|---:|
| bistro | 1 / 0.000000 | 1 / 0.000000 |
| minecraft | 1 / 0.000000 | 1 / 0.000000 |

원본 실행과 과거 native 출력이 일치했다는 사실은 해당 장면·경로·preset의 RGB에 한정한다.
이 검사는 pixel 결과와 CPU mode 상태 및 소스 흐름 검사다. 모든 GPU draw를 그래픽 디버거로 캡처한 검사는 아니다.
과거 edge 선택의 정지 떨림이나 채택 결론이 이 일치로 해결되지는 않는다.

## 올바른 SMAA 1X의 CGVQM-2

높을수록 좋다. 기존 supersample **공간 참조 proxy**를 사용하며 절대 ghosting 점수가 아니다.
새 O-1X 네 clip을 측정했다. Native 점수는 독립 capture와 기존 CGVQM 입력/참조의 indexed RGB hash,
범위·설정·공식 commit·Torch/CUDA 일치를 재확인한 뒤 재사용했다. FFV1 RGB round-trip mismatch 0.
공식 commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`, model 2, CUDA, 60 FPS, patch_scale 4, mean.

| 장면 | 구간 | 실제 SMAA 1X | 원본 T2X-R | T2X-R−1X |
|---|---|---:|---:|---:|
| bistro | moving | 96.062752 | 96.191238 | +0.128487 |
| bistro | transition | 95.874573 | 96.719254 | +0.844681 |
| minecraft | moving | 95.172501 | 93.911362 | -1.261139 |
| minecraft | transition | 94.916374 | 94.905739 | -0.010635 |

moving=60~179, transition=160~219. 지터 On current-spatial의 과거 점수를 일반 SMAA 1X 점수로 사용하지 않는다.

## 독립 기준선 GPU 시간

RTX 3060 Ti / DX11 / Ultra / 1920×1061 / hidden window / VSync Off. 장면당 독립 process에서
30초 precondition, 각 mode 300 warmup, 4800 frame×4회, 정/역방향 mode 순서를 교대했다.
PNG 캡처와 GPU 품질 평가는 동시에 실행하지 않았다. 아래는 전체 SMAA scope이며 temporal resolve만의 시간이 아니다.
실측 window 조건의 engineering GPU timing이다. 과거 다른 바이너리의 절대 시간과 직접 차감해 개선율을 주장하지 않는다.

| 장면 | 방식 | SMAA 평균 ms | 반복 평균 표준편차 ms |
|---|---|---:|---:|
| bistro | O-1X | 0.148339 | 0.002418 |
| bistro | O-T2X | 0.172247 | 0.002468 |
| bistro | O-T2X-R | 0.214352 | 0.000321 |
| minecraft | O-1X | 0.220823 | 0.001434 |
| minecraft | O-T2X | 0.247051 | 0.001220 |
| minecraft | O-T2X-R | 0.289141 | 0.000580 |

## 제외한 실행과 재현

- Minecraft `20260928_165112`는 저장 후 종료 코드 -1073740791. Aggregate PASS만으로 채택하지 않고 제외했다.
- Bistro timing `20260928_170619`는 원본에 없는 WholeFrame scope를 요구한 도구 오류로 FAIL. 결과에서 제외하고 기존 SMAA scope만 측정하도록 수정 후 smoke/본 측정을 재실행했다.
- 별도 도구 브랜치의 수명 수정을 적용한 뒤 clean runner로 재실행했다. 원인 전체를 crash stack으로 확정한 것은 아니다.
- 최초 빌드의 Path/PATH 중복은 빌드 프로세스 환경 이름을 정규화하고 node reuse를 끄는 도구에서 처리했다.
- 완료 receipt에는 EXE/report SHA와 실행 시각, mode 검사 결과가 남는다. raw PNG/영상/중간 FFV1은 로컬 보존한다.
- `build_baseline.py` → `run_baseline_restart.ps1 -Phase Capture -Scene ...` → `analyze_baseline_restart.py` →
  `evaluate_baseline_cgvqm.py` → 별도 `-Phase Benchmark` → `summarize_baseline_restart.py` 순서다.

## 이전 연구에서 유지할 제약

지터/선택 상호작용과 paired de-jitter의 잔여 변동은 기존 기록에서 이미 확인됐다.
선택식 계산이 정확하다는 사실을 비선택 영역의 안정성이 확보됐다는 뜻으로 쓰지 않는다.
새 edge 선택 연구는 기준선에서 별도 분기하고, 비선택 출력과 지터 정책부터 명시한 뒤 정지 검증을 통과해야 한다.

## 바로잡은 기준선 영상

왼쪽 AA Off / 가운데 실제 SMAA 1X / 오른쪽 원본 T2X-R. GIF 0.5배속, MP4 60 FPS.
Bistro는 세 패널에 동일 RGB gain 3배를 적용한 관찰용 영상이다. Minecraft는 원래 밝기다.
고정 공통 팔레트/dithering Off의 GIF도 색 양자화 한계가 있으며 loop 재시작은 잔상이 아니다.

### bistro

![bistro 기준선 비교](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/BaselineRestart/bistro/Playback/baseline-transition.gif)

[정속 MP4](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/BaselineRestart/bistro/Playback/baseline-transition-60fps.mp4)

### minecraft

![minecraft 기준선 비교](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/BaselineRestart/minecraft/Playback/baseline-transition.gif)

[정속 MP4](C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/Projects/CMAA2/AutoBench/BaselineRestart/minecraft/Playback/baseline-transition-60fps.mp4)
