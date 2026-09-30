# 얇은 선 소실 지점 추적 결과

2026-10-01. `validation/spatial-edge-thin-line-trace`는 수정된 ⑥ 기준선
`304f749`에서 직접 분기했다. 이전 전체 화면 Pattern-Off 실험을 합치지 않았다.
이번 변경은 입력 저장과 진단 도구이며, AA 알고리즘 개선 구현은 아니다.

현재 프레임의 edge만 선택하는 ⑥에서는 **선이 사라진 프레임에 edge 선택도 함께
꺼져, history에 남은 선조차 사용할 수 없는 사례**가 확인됐다. 선이 다시 나타나면
이전 배경색과 섞여 약해지는 반대 사례도 있다. 선택된 위치의 history weight를
높이는 것만으로 두 문제를 함께 해결할 수 없다. 두 장면 전체의 모든 결함을
하나의 원인으로 설명한 결과는 아니다.

## 비교 대상과 변경 범위

| 대상 | Spatial | Temporal | Paired jitter/subsample pattern | History |
|---|---|---|---|---|
| ⑥ Edge Off | Original SMAA | 실제 1st-pass edge stencil에서만 native T2X-R 실행 | Off | 이전 spatial frame |
| ④ Native On | Original SMAA | 전체 화면 native T2X-R | On | 이전 spatial frame |
| ⑥ 반복 | ⑥과 동일 | 진단 readback/query Off | Off | 이전 spatial frame |

재투영은 camera/depth 기반이다. Object-motion 지원을 추가하지 않았다.
후보 확장, jitter, sampler, clipping, history weight와 feedback 방식은 변경하지 않았다.
⑥ 비선택 픽셀에서는 여전히 현재 spatial 결과만 출력한다. CPU 진단에서 비선택
위치의 history를 가상으로 조회한 것은 실제 GPU 실행이나 새 full-screen AA가 아니다.

SMAA HLSL 4개는 기준선과 동일하다(줄바꿈 정규화 후 SHA-256 검증).
Release x64 빌드 및 Bistro smoke를 통과했다. Renderer commit은 `9fefa77`이며,
실행 파일 SHA-256과 각 실행 기록은 `source-audit.json`, `*-run.json`에 있다.
컴파일 실패를 자동 실행에서 모달 창 없이 종료하는 기존 guard만 제한적으로 재사용했다.

## 검증 결과

두 장면은 독립 clean process에서 Ultra, 1920×1061, fixed 60 Hz,
warm-up 60프레임, 정지60/이동120/정지60 타임라인으로 각각 캡처했다.

| 검증 | 결과 |
|---|---|
| 각 장면 3 mode ×240 최종 RGB | 총 **1,440프레임**, 수정 기준선과 전부 일치 |
| 입력 저장 | 각 장면 2 mode ×32프레임, 총 **128개** trace |
| ⑥ 실제 GPU coverage와 1st-pass edge | 전부 일치 |
| ⑥ 비선택 출력과 current spatial | 전부 byte 일치 |
| Resolve invocation/sample query | ⑥은 선택 픽셀 수, ④는 전체 픽셀 수와 일치 |
| 연속 trace의 이전 history | 직전 current spatial RGBA와 일치 |
| CPU point 조회·native weight 재구성 | 불확실 경계 제외 RGB 최대 오차 **1/255** |
| 기존 GPU weight 진단과 겹치는 ROI | 허용 오차 2×10⁻⁶ 이내 |

Point sampling의 texel 경계에 가까운 좌표는 불확실로 표시했다. 아래 대표 픽셀은
모두 그 범위 밖이다. 입력 sRGB/UNORM 변환과 GPU FMA 때문에 CPU RGB와 실제 출력에
최대 1단계의 차이가 있으며 CPU 가상 출력과 실제 GPU 출력을 구분해 보존했다.
이 PASS는 **출력 보존·진단 정확성** 검증이며, 품질 개선 PASS가 아니다.

## 프레임에서 확인한 실패 과정

Minecraft의 화면상 얇은 수직 경계를 f130..135에서 추적했다. ROI는
`(964,524)..(996,588)`이며, 좌표 원점은 좌측 상단, 0-based다.
모든 RGB는 밝기 조정 없는 원본 8-bit 값이다.

| 프레임·좌표 | 현재 spatial RGB | 재투영 point history RGB | 현재 edge 선택 | 실제 ⑥ 출력 RGB | 해석 |
|---|---|---|---|---|---|
| f130 (971,544) | 115,111,107 | 113,107,97 | On | 114,109,102 | 현재·이전 모두 어두운 선 신호 |
| f131 (971,544) | 163,162,150 | 115,111,107 | **Off** | 163,162,150 | 현재 선 소실, 이전 선은 있지만 미사용 |
| f132 (972,544) | 114,108,101 | 161,161,149 | On | 140,138,128 | 선 재출현, 이전 배경과 섞여 약화 |
| f134 (972,544) | 163,163,150 | 113,109,105 | **Off** | 163,163,150 | 같은 실패가 다른 프레임에서도 재현 |
| f135 (973,544) | 108,103,100 | 162,162,149 | On | 138,137,127 | 현재 선을 밝은 history가 약화 |

f131의 raw AA 입력도 `(163,162,150)`으로 이미 선이 없다. 따라서 이 위치의
최초 소실은 spatial SMAA나 temporal resolve가 만든 것이 아니다. 그 입력에서는
현재 edge가 검출되지 않아, 남아 있는 이전 선을 결합할 기회도 사라진다.
f131/f134의 재투영한 이전 위치에는 이전 edge 표시가 존재한다.
이는 **현재 edge 선택의 시간적 누락**을 확인하는 증거이며, 이전 edge 재사용을
이미 구현했거나 그 방법의 품질·성능이 검증됐다는 뜻은 아니다.

독립 브랜치 `validation/spatial-edge-coverage-pattern-control`의 실제 GPU
full-screen Pattern-Off 출력도 다시 대조했다. 동일 프레임의 ⑥ 전체 RGB가 이번
출력과 정확히 같은 것을 먼저 확인했다. 전체 화면 결합은 f131에서 `(142,140,131)`,
f134에서 `(141,140,130)`을 출력하므로, 이 두 위치에서는 이전 선 신호를 일부 살린다.
하지만 기존 연속 프레임 검사에서 이 대조군 역시 선 보존과 반짝임에 문제가 있었으므로,
**전체 화면 결합으로 바꾸면 해결된다는 결론은 아니다.**

반대로 f132/f135에서는 현재 edge가 선택되고 정상적인 약 0.5 history weight로
계산이 수행됐음에도 선이 약해진다. 이는 누락된 shader 실행이나 일반적인 weight=0
문제와 구분된다. 현재/이전의 선 표본이 번갈아 나타나는 입력을 어떻게 보존할지가
필요하며, history weight를 일괄적으로 높이면 이 경우에는 배경의 영향이 더 커진다.

## 정지 구간은 별개의 한계

f190..195의 Bistro 의자·창문, Minecraft ROI를 각각 확인했다.

- ⑥은 camera velocity=0이고 current spatial, point history, final RGB가 모두 같다.
  프레임 사이에도 동일하다. 남아 있는 계단·끊김은 안정된 결함이며, 정지 hash가
  같다는 사실이 좋은 AA 품질을 의미하지 않는다.
- ④는 두 표본 위상의 raw/current 입력이 번갈아 바뀌지만 최종 결과는 동일하다.
  검사한 창문 사선 등에서 ⑥보다 경계가 부드럽게 보인다.
- ⑥의 동일한 current/history 두 값을 weight만 바꾸어 섞어서는 새 선 정보를
  만들어낼 수 없다. 주변 필터로 모양을 바꾸는 것과 독립적인 subpixel 표본을
  확보하는 것은 별개다.

④와 ⑥은 coverage와 sample pattern 둘 다 다르므로, 여기서 두 효과의 크기를
독립적으로 수치화하지 않았다. 별도 Pattern-Off 대조군 결과와 함께 해석해야 한다.

## 직접 검사한 시각 자료

원본 전체 PNG를 열어 장면·시점·화면 구성을 확인하고, 아래 연속 프레임 sheet를
직접 열어 AA 입력→spatial→선택→가상 history→최종 출력의 관계를 확인했다.
밝기 보정이나 차이 증폭은 하지 않았다.

| 장면·영역 | 프레임 | 확인 범위 |
|---|---|---|
| Minecraft 얇은 수직 경계 | 130..135 | 선 상단/하단의 소실·재출현, 선택 누락, 혼합 약화 |
| Minecraft 정지 전환·정지 | 178..183, 190..195 | 전환 후 남는 계단과 안정된 입력/출력 |
| Bistro 의자·다리 | 130..135 | 복잡한 세부 선이 입력에서부터 달라지는 과정 |
| Bistro 창문 사선 | 178..183, 190..195 | 입력 계단과 공간 보정, 정지 후 남는 경계 결함 |

전체 화면 직접 검사: Minecraft f131의 ④/⑥, Bistro f180의 ④/⑥.
추가로 f127..138 전후 입력을 저장해 경계 밖 프레임도 추적할 수 있다.
`media.json`에 PNG/WebP 절대 경로, ROI, 프레임, 배율, hash를 기록했다.
WebP는 원본 색상의 lossless 6fps(0.1배속) 비교 자료이며 decode 결과와 길이를
검증했다. 이번 직접 관찰은 정지 PNG/연속 sheet 기준이며 실시간 동영상 재생을
직접 관찰했다고 주장하지 않는다. 재생 자료는 확인용으로 별도 제공한다.

## TSCMAA를 다음에 어떻게 참고할 것인가

확보 소스 `AASample/Intel/TAA/TAA_Edge.hlsl`은 bicubic history sampling,
ClipColor와 history weight `0.789473712`를 사용한다. 현재 native SMAA T2X-R의
point sampler·가변 0..0.5 weight·이전 spatial history와는 다르다.
공개 문서의 약 0.8과 확보 소스의 실제 상수도 구분해야 한다.

그러나 **현재 후보에 들어오지 않은 위치는 temporal 내부 sampler·weight·clipping을
바꿔도 실행되지 않는다.** 이번 f131/f134의 누락을 그 변경만으로 고칠 수 없다.
또 현재 경로에는 clipping이 없으므로 이번 실패를 clipping 탓으로 돌릴 수 없다.
선택 후보를 더 줄이는 TSCMAA 후보식을 가져오는 것도 이 누락의 직접 해법은 아니다.

다음 항목은 독립 브랜치에서 **현재 edge에서 사라졌지만 직전 프레임에 존재했던
선의 정보를 제한적으로 유지할 수 있는지** 먼저 검증하는 것이 타당하다. 이번 입력으로
재투영된 이전 edge가 누락 위치를 얼마나 포함하고, 가려짐 해제에서는 잔상을 만들지
먼저 분석한다. GPU 구현 전에 필요한 데이터·실행 범위·추가 비용을 명시해야 한다.
단순히 모든 픽셀에서 history를 읽거나 새 패스를 붙이면 저비용 목표와 충돌한다.

선택 누락과 별도로, 선택된 위치의 history 보존/신뢰도 문제는 다른 항목에서
sampler 또는 feedback 한 요소씩 비교한다. 기존 factorial/feedback 실험 자료를
재사용하되, 다른 실행 경로의 결과를 이번 stencil 경로의 성공으로 간주하지 않는다.
현재 정보가 실제로 없는 부분의 복원 한계도 별도로 남긴다. 이번에는 새 후보식,
지터, dilation 또는 TSCMAA 복합 kernel을 적용하지 않았다.

## 저장 자료와 재현

- `findings.json`: 대표 픽셀, 이전 edge 존재 여부, 정지 구간 검사와 외부 출력 hash bridge.
- `bistro-capture-validation.json`, `minecraft-capture-validation.json`: 전체 검증과 원본 DDS hash.
- 원본: `D:/SMAAResearchCaptures/thin-line-trace-20261001/capture/`.
- Bistro run: `20261001_004246`; Minecraft run: `20261001_004448`.
- 도구: `run_thin_line_trace.ps1`, `analyze_thin_line_trace.py`,
  `summarize_thin_line_trace.py`, `create_thin_line_trace_media.py`.
- readback/query가 포함된 실행이므로 **성능 수치를 만들지 않았다.** CGVQM도 재실행하지
  않았다. 이번 산출물은 원인 추적과 후속 실험 선정 자료다.
