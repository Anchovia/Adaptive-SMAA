# 기존 temporal 패스에서 선택 조건의 유효성 검증

현재·이전 색상과 원래 혼합 가중치만 사용하는 선택식을 추가하고 GPU 출력까지 검증했다.
기존 luma 미분 선택보다 정지 변화는 줄었지만, 원본 T2X-R을 대체할 품질 우위는 확인하지 못했다.
Bistro에는 생략한 픽셀의 지터가 남고, Minecraft에서는 원본 출력에 거의 가까워진다.
기본 구현과 원본 기준선은 변경하지 않는다. 이 결과는 제한된 품질 window의 engineering 실험이다.

## 연구 질문과 범위

이전 속도 실험은 같은 선택 결과와 출력을 유지하는 실행 최적화였다.
이번에는 “기존 temporal 패스의 정보로 결합을 생략해도 되는 픽셀을 구분할 수 있는가”를 검사한다.
`experiment/temporal-pass-selection-validity`를 `3bede90`에서 분기했다.
Offline 가설·결과는 `89f0614`, GPU 최소 구현은 `68fbf80`에 분리했다.

Original 공간 SMAA, camera/depth reprojection On, 원래 paired jitter/subsample pattern,
velocity-alpha 기반 가중치, spatial-frame history를 유지한다. 추가 패스, texture, edge 읽기,
후보 목록, dilation, object-motion 또는 Adaptive 공간 처리를 추가하지 않았다.
최종 8-case 및 Intel TSCMAA 전체 구현의 결과가 아니다.

Native는 원본 Point 입력, paired는 이전 실험의 Linear 입력을 뜻한다.
Paired는 current UV+j, history UV-motion-j에서 읽고, velocity는 원래 UV에서 읽는다.
입력과 alpha가 달라지므로 Native와 paired의 차이를 선택식만의 효과로 표현하지 않는다.

## 먼저 수행한 offline 검사

기존 캡처에서 700개 selector/basis/pose 조합을 검사했다. 정한 threshold와 불리한 결과도
[offline 전체 표](offline-tables.md)에 보존했다. 구체적인 조건은 [방법](method.md)과
[최소 구현 선정 근거](offline-decision.md)를 따른다.

PNG current/full 결과의 차이를 linear로 복원한 값은 실제 shader 내부 차이의 근사다.
특히 0.00025는 sRGB8의 최소 linear 간격보다 작아, 서로 다른 PNG 값이면 모두 선택한다.
이때 full 출력과 같아지는 현상은 양자화에 따른 자명한 결과이며 GPU 품질 증거로 제외했다.
고정 threshold 0.0005 하나만 실제 shader에서 검사했다. 장면별 threshold를 달리 고르지 않았다.
실제 GPU mask와 PNG 근사의 선택률은 다르므로 offline 비율을 실시간 후보 수로 사용하지 않는다.

## GPU 선택식

```text
impact   = originalWeight × max(abs(current.rgb − previous.rgb))
selected = impact >= 0.0005
output   = lerp(current, previous, originalWeight × selected)
```

이는 공간 local contrast가 아니라 **현재 history 결합이 출력에 주는 기여의 크기**다.
값이 큰 픽셀에서 결합을 유지하고, 작은 픽셀은 현재 색상으로 출력한다.
공식 TSCMAA 식이나 보편적인 history 신뢰도 판단이라고 부르지 않는다.
큰 차이는 지터뿐 아니라 가려짐 해제·잘못된 재투영에서도 생길 수 있으므로
큰 차이를 선택한다는 사실만으로 고스팅 감소를 주장할 수 없다.

현재/이전 입력을 교환하고 같은 가중치를 쓰는 정지 상황에서는 이 식이 대칭이다.
실제 두 장면의 late-still mask는 두 위상 사이에 바뀌지 않았다.
그러나 **mask가 같아도 생략한 픽셀의 현재 색상은 지터 때문에 바뀔 수 있다.**

구현은 기존 draw의 scalar weight 마스킹이다. R On에서는 current/history/velocity의
세 sample 명령을 그대로 실행하며, 혼합 명령도 실행한다. 선택 픽셀 수 감소를 ALU나
history 접근 생략으로 해석하지 않는다. 미분을 제거한 선택식 교체 비용만 실측한다.
이전 spatial frame을 history로 저장하므로 현재 출력 선택은 다음 history를 바꾸지 않는다.
이 점 때문에 같은 입력의 full/current를 조합한 검사와 실제 GPU 출력을 대응시킬 수 있다.

## 검증과 실행 조건

- Release x64 빌드 성공. 기존 Native 8개와 paired 4개 shader bytecode 불변.
- 신규 10개 R Off/On shader variant 컴파일 통과. 새 선택 경로에 미분·동적 분기 없음.
  R Off는 compile 검증만 했고 품질·성능 실행은 R On이다.
- 두 장면의 기존 대조군 490 PNG hash 비교에서 불일치 0.
- 신규 두 방식의 총 196 frame에서 selected=full, unselected=current RGBA 불일치 0.
  별도 진단 실행의 실제 mask를 사용했으며 mask는 이진값이고 first frame은 0이다.
- 전체 렌더 구간 4,320개 jitter/subsample pattern 검사 통과. 첫 frame은 history를 결합하지 않는다.

RTX 3060 Ti, DX11, SMAA Ultra, 1920×1061, hidden, VSync Off다.
기존 flythrough t=2에서 60 frame 정지, 120 frame 이동, 60 frame 정지를 fixed 60 Hz로 실행한다.
품질은 mode별 240 frame 전부를 렌더하고 0, 140–155, 176–191, 200–215만 저장했다.
각 연속 구간은 16 frame이다. 건너뛴 구간의 차이를 인접 시간 변화로 계산하지 않는다.
전체 타임라인, 독립 object motion 또는 다양한 disocclusion을 검증한 결과는 아니다.

Supersample spatial reference는 이전 캡처와 같은 pose에 대응한다. RGB MAE, reference 대비
시간차 잔차와 gradient 비율은 보조 지표다. 절대 temporal ground truth, 사람의 지각 평가나
CGVQM 본 평가로 표현하지 않는다. 영상은 60 FPS 16-frame MP4 및 0.5배속 GIF를 만들고
MP4 frame 수·PTS를 검증했다. 작은 차이는 GIF 양자화로 사라질 수 있어 PNG 수치를 함께 본다.

성능은 품질·마스크 캡처 및 CPU 영상 분석과 분리했다. 각 명령은 fresh process이며
정상 종료와 완성된 PASS 보고서를 확인했다. 짧은 smoke 후 30초 공통 예열,
mode별 300-frame warm-up, 4,800 frame×4회를 정방향/역방향으로 교차 측정한다.
PNG·진단 mask·후보 readback은 성능 실행에 없다. 같은 프로세스의 4회 반복은
독립 날짜나 다른 GPU의 재현성 검증이 아니다.

## 품질 결과

late-still 인접 RGB 변화(0–255 채널 평균 절대 차이):

| 입력 계열 | 장면 | 기존 luma 선택 | 새 기여도 선택 | 같은 입력의 full 결합 |
|---|---|---:|---:|---:|
| Native | Bistro | 1.287832 | 0.378834 | 0 |
| Native | Minecraft | 0.580355 | 0.000605 | 0 |
| Paired | Bistro | 0.733370 | 0.330569 | 0 |
| Paired | Minecraft | 0.229097 | 0.015820 | 0 |

기존 Native luma 선택은 이전 캡처의 kind16을 사용했다. 이번 실행의 native/full/current
hash가 이전 캡처와 같음을 먼저 확인했다. 위 표는 같은 입력끼리의 선택식 비교다.
원본 Native와 새 paired를 직접 비교해 선택식 효과라고 설명하지 않는다.

정지의 actual 선택률은 Native/paired 순서로 Bistro 18.31%/10.44%,
Minecraft 78.95%/79.56%다. 두 장면 모두 mask 전환은 0이지만 Bistro의 잔여 RGB 변화는
Native 최대 3, paired 최대 4 level이다. 평균만 작다고 모든 픽셀이 안정됐다고 표현하지 않는다.

기존 Native 선택에서 채널 변화가 1보다 컸던 픽셀 중 새 식이 결합을 유지한 비율은
Bistro 62.05%, Minecraft 99.999%다. 따라서 Minecraft의 큰 변화는 거의 모두 흡수하지만
Bistro에서는 상당 부분을 생략한다. 1-level 구분은 분석용 기준이며 가시성 문턱이 아니다.
기존에 변화가 없던 일부 픽셀에 작은 변화가 새로 생긴 결과도 [그룹 분석](static-groups.json)에 남겼다.

Bistro 정지 reference MAE는 원본 0.582826, 새 Native 0.657535이며 원본이 더 낮다.
Minecraft는 원본 1.471707, 새 Native 1.471693으로 사실상 비슷하지만 새 출력에 미세한 지터가 남는다.
Paired는 이전 선택보다 이동·정지의 오차가 줄었지만 full paired보다는 대체로 높다.
Minecraft 정지 gradient/reference는 Native 약 0.917, paired 약 0.808로, paired 입력의
세부 구조 약화도 남는다. 낮은 reference MAE만으로 블러와 고스팅의 개선을 동일시하지 않는다.

두 장면의 8배 정지 차이 이미지에서 기존 구조성 변화가 줄어든 것을 확인했다.
이는 증폭·축소한 진단 이미지의 관찰이며, 실제 재생 시 지각적 우열을 확정하는 평가는 아니다.
모든 구간의 품질·후보 수와 성능 수치는 [GPU 전체 표](gpu-tables.md)에 기록한다.

## 성능과 판단

전체 SMAA 시간의 4회 평균은 다음과 같다.

| 장면 | 원본 T2X-R ms | 새 Native 선택 ms | 변화 | Resolve 변화 |
|---|---:|---:|---:|---:|
| Bistro | 0.207704 | 0.208600 | +0.000897 ms / +0.43% | +0.000339 ms / +1.01% |
| Minecraft | 0.283073 | 0.283632 | +0.000559 ms / +0.20% | +0.000251 ms / +0.72% |

Resolve는 두 장면의 4회 모두 원본보다 증가했다. 전체 SMAA에는 미변경 spatial 구간의
변동도 포함되며 Minecraft는 repeat별 차이의 부호가 섞인다. 위의 작은 평균 차이를
일반적인 확정 증가율로 확대하지 않지만, 속도 개선의 근거는 확보하지 못했다.
WholeFrame도 Native 비교에서 부호가 섞여 frame 전체의 향상을 주장하지 않는다.

Paired 입력을 고정하면 새 선택식의 전체 SMAA는 full paired 대비 Bistro +0.27%,
Minecraft +0.07%이며 Resolve는 각각 +1.04%, +0.73%다. 기존 paired 선택식 대비는
전체 SMAA +0.07% / -0.07%로 반복 변동이 섞인다. 즉 기존 선택보다 정지 변화를 줄인
대가는 이 측정에서 거의 비슷한 비용이지만, full 결합을 앞서는 속도·품질을 확보한 것은 아니다.

반복 결과와 차이의 방향은 GPU 전체 표 및 `timing-comparisons.json`을 기준으로 한다.
후보 비율은 별도의 품질 window에서 측정한 것이며 성능 실행의 평균 비율이 아니다.
초기 smoke의 첫 mode는 미변경 spatial 구간까지 낮게 나와 속도 결론에 사용하지 않는다.
예열·순서 교차를 수행한 반복 결과에서도 전체 AA와 resolve를 함께 평가한다.

이번 실험은 기존 패스의 정보만으로 정지 두 위상에 일관된 선택을 만들 수 있음을 보여준다.
동시에 선택 일관성과 생략 픽셀의 안정성은 별개임을 확인했다. 기본값으로 채택하지 않고
원본과 기존 선택식을 모두 보존한다. 품질이 원본에 가까워진 것과 원본보다 우수한 것은 구분한다.
history를 읽은 뒤 저렴한 lerp만 바꾸는 현재 구조는 핵심 읽기 비용을 절약하지 않는다.

후속 검토가 필요하다면 먼저 같은 정보의 선택식이 Bistro의 잔여 생략 오차까지 낮출 수 있는지,
그 비용과 실제 절약할 연산이 무엇인지 함께 따져야 한다. 후보 수 감소만으로 가속을 약속하지 않는다.
전체 연구가 불가능하다는 결론도 아니지만, 이 고정 문턱의 구현만으로 품질·속도 목표 달성을 선언할 수 없다.

## 재현 및 산출물

1. `validate_temporal_contribution.py`로 컴파일·bytecode 불변 검사.
2. Release x64 빌드 후 `run_temporal_selection.ps1 -Phase Capture -Scene <scene>`.
3. `analyze_temporal_contribution.py --phase Capture --scene <scene>` 및 그룹 분석.
4. 같은 runner의 Smoke, Benchmark를 순차 실행하고 같은 analyzer로 결과 검사.
5. `summarize_temporal_contribution.py`로 검증된 JSON만 집계.

원시 report·PNG·영상은 해당 AutoBench 폴더에 로컬 보존한다. Git에는 코드, 분석 도구와
검증된 JSON/Markdown만 기록한다. 실행파일/report hash와 원시 경로는 각 JSON의 receipt,
frame hash는 quality JSON에 있다. [shader 검사](shader-validation.json),
[Bistro 품질](bistro-quality.json), [Minecraft 품질](minecraft-quality.json)을 함께 참조한다.
