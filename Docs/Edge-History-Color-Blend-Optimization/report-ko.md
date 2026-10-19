# ⑰ 코드 정리·화면 RGB 출력 보존 최적화 결과 (2026-10-19)

두 장면에서 O2+O3 결합 후보의 240프레임 화면 RGB는 원래 ⑰·정리본과 완전히 같았고, 같은 실행의 ⑰ 대비 전체 AA 시간이 감소했다. Minecraft에서는 ④보다 여전히 느리다. 기존 얇은 선 단절 문제는 그대로이며 품질 개선을 주장하지 않는다. O3 계열은 중간 visible texture의 alpha가 달라져 기본값 채택을 보류한다.

대상 semantic ID는 `ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080-EncodedGamma2Blend`다. Original spatial SMAA, current∪reprojected previous raw-edge 선택, camera/depth reprojection, Catmull-Rom 5-fetch RGB, weight 0.8, resolved RGB feedback, current spatial history alpha, paired pattern Off를 유지했다. ⑮/⑯을 누적하지 않았고 Adaptive·확장·새 clipping/sampling/weight/jitter/object motion을 추가하지 않았다. Intel TSCMAA 전체의 공식 포팅이라고 표현하지 않는다.

④는 수정된 stencil lifecycle 위의 native Standard full-screen O-T2X-R와 paired pattern On 대조군이다. ⑰와 선택 범위 외에도 sample pattern·history sampling·weight·feedback topology가 다르므로 두 방식의 차이를 edge 선택 효과 하나로 해석하지 않는다.

후보들은 모두 기본 Off이며 selected feedback 경로에서만 적용한다.

- O1: 전용 D24S8을 stencil만이 아니라 depth+stencil로 함께 clear하는 실행 구조 후보.
- O2: feedback neighborhood pass의 읽히지 않는 depth 쓰기를 끄는 depth/stencil Off state 후보.
- O3: neighborhood/resolve에서 중간 visible MRT 쓰기를 생략하고 같은 RGB의 다음 history를 표시하는 후보. HLSL과 최종 표시 pass 수는 유지한다.

앞선 코드 정리는 설정 검사를 `ValidateSelectedTemporalConfiguration`으로, 중복 자원 누락 조건을 `TemporalResourcesMissing`으로, 진단을 Begin/End helper로 분리했다. 이름 있는 resolve options와 technique 생성 helper로 CPU 구조를 정리했고 HLSL·GPU pass 순서·binding·stencil/history 의미는 바꾸지 않았다. 자세한 감사와 정리 전후 GPU 출력 증거는 [코드 감사](../Edge-History-Color-Blend-Cleanup/audit-ko.md)와 [정리 검증](../Edge-History-Color-Blend-Cleanup/readme-ko.md)에 있다.

기존 `../Edge-History-Source-Color-Blend/bistro-capture.json`의 classification에는 “single history weight ablation”이라는 잔존 문구가 있다. 같은 폴더의 `case.json`(component=source-color-blend, base_case=14)과 실제 `SourceTemporalComponent.hlsl`의 SourceBlend 호출을 우선해, ⑰은 weight를 유지한 독립 색 혼합 실험으로 정정해 해석한다. RGB hash bridge에 사용한 과거 원자료의 bytes는 바꾸지 않았다.

## 핵심 성능 결과

각 장면의 한 optimization process에 ④·⑰·O1·O2·O3·O2+O3를 함께 넣었다. 아래 백분율은 반복마다 같은 실행/반복의 control로 나눈 값의 평균이다. 다른 실행의 ④ 절대값을 공통 분모로 쓰지 않았다.

| 장면 | ④ AA ms | ⑰ AA ms | O3 AA ms | O2+O3 AA ms | 결합 vs ⑰ AA | 결합 vs ④ AA | 결합 vs ⑰ WholeFrame |
|---|---|---|---|---|---|---|---|
| bistro | 0.15887 | 0.14828 | 0.13745 | 0.13572 | -8.47% | -14.57% | -0.63% |
| minecraft | 0.22867 | 0.24997 | 0.23537 | 0.23365 | -6.53% | +2.18% | -1.57% |

AA 감소율을 전체 프레임 감소율로 읽으면 안 된다. 숨김 창의 GPU scope 비교이며 일반적인 visible-window 게임 FPS 결과로 확대하지 않는다.

- bistro WholeFrame 변화의 95% 구간: -1.203% ~ -0.058%. 증가한 반복 1/6개.
- minecraft WholeFrame 변화의 95% 구간: -1.954% ~ -1.182%. 증가한 반복 0/6개.

| 장면 | 설정 | AA 평균 ms | vs ⑰ | paired 95% 하한 / 상한 | AA run-mean SD ms | WholeFrame 평균 ms |
|---|---|---|---|---|---|---|
| bistro | ⑰ (후보 Off) | 0.148280 | — | — | 0.000298 | 2.447916 |
| bistro | ⑰+O1 | 0.150032 | +1.182% | +0.948% / +1.415% | 0.000304 | 2.443600 |
| bistro | ⑰+O2 | 0.147469 | -0.547% | -0.607% / -0.486% | 0.000286 | 2.447778 |
| bistro | ⑰+O3 | 0.137452 | -7.302% | -7.523% / -7.081% | 0.000395 | 2.437657 |
| bistro | ⑰+O2+O3 | 0.135725 | -8.468% | -8.611% / -8.324% | 0.000389 | 2.432458 |
| minecraft | ⑰ (후보 Off) | 0.249968 | — | — | 0.000939 | 1.171324 |
| minecraft | ⑰+O1 | 0.251630 | +0.667% | -0.110% / +1.444% | 0.001076 | 1.173369 |
| minecraft | ⑰+O2 | 0.248288 | -0.672% | -0.760% / -0.585% | 0.001039 | 1.169602 |
| minecraft | ⑰+O3 | 0.235370 | -5.838% | -6.593% / -5.083% | 0.001017 | 1.154762 |
| minecraft | ⑰+O2+O3 | 0.233648 | -6.529% | -6.661% / -6.397% | 0.001100 | 1.152949 |

O1은 일관된 개선이 없어 제외한다. O2 단독 이득은 작다. O3와 결합의 큰 AA 절감은 두 장면에서 재현됐으나, 이 결과는 이 GPU·드라이버·경로의 측정 범위다. 95% 구간은 6개 반복의 Student-t(df=5) 구간이며 다중 비교 보정은 하지 않았다.

| 결합의 O3 단독 대비 추가 AA 변화 | 평균 | 95% 하한 / 상한 |
|---|---|---|
| bistro | -1.2568% | -1.4376% / -1.0760% |
| minecraft | -0.7286% | -1.6353% / +0.1781% |

추가 이득의 구간이 0을 포함하면 결합이 O3보다 확실히 빠르다고 결론내리지 않는다. 주효과를 단순히 더해 결합 효과로 해석하지 않는다.

- minecraft: 결합의 O3 대비 추가 이득은 이번 반복에서 확정하지 않는다.

| 장면 | 설정 | spatial ms | velocity ms | resolve ms | GPU frame median ms | p95 ms | p99 ms | GPU tail 등가 FPS |
|---|---|---|---|---|---|---|---|---|
| bistro | ④ native O-T2X-R | 0.101726 | 0.023937 | 0.033185 | 2.40282 | 2.68066 | 2.74364 | 350.78 |
| bistro | ⑰ (후보 Off) | 0.113935 | 0.023947 | 0.010378 | 2.39769 | 2.67401 | 2.78135 | 349.14 |
| bistro | ⑰+O2+O3 | 0.103486 | 0.023905 | 0.008314 | 2.38473 | 2.66052 | 2.72811 | 354.99 |
| minecraft | ④ native O-T2X-R | 0.169619 | 0.024046 | 0.034990 | 1.13869 | 1.34212 | 1.42574 | 676.78 |
| minecraft | ⑰ (후보 Off) | 0.190305 | 0.024136 | 0.035507 | 1.16941 | 1.34827 | 1.47626 | 664.11 |
| minecraft | ⑰+O2+O3 | 0.180333 | 0.024108 | 0.029184 | 1.15337 | 1.33239 | 1.45117 | 672.66 |

median/p95/p99는 각 반복 통계의 평균이며 전체 표본을 합친 percentile이 아니다. tail 등가 FPS는 WholeFrame GPU의 느린 1% 평균 역수로, 실제 화면 재생 FPS가 아니다. wall frame 통계와 전체 mode별 수치는 `campaign-performance.json`/`optimization-performance.csv`에 있다.

## 코드 정리 전후 ABBA

정리 전 `c7514c2`(렌더러는 원래 ⑰ `5bdd189`와 같고 검증 harness만 추가)와 정리 후 `d2a6315`의 기존 실행 파일을 그대로 사용했다. 각 장면은 전→후→후→전 순서, process마다 300 warm-up + 4,800×6회다. 프로세스 간 절대값은 별도로 표시하며, 정규화는 각 process 자체의 ④로 한다.

| 장면 | 순서 | 동일 실행 ④ AA ms | ⑰ AA ms | ⑰ vs 자체 ④ | ⑰ WholeFrame ms |
|---|---|---|---|---|---|
| bistro | before-bench-1 | 0.159294 | 0.148899 | -6.5251% | 2.451258 |
| bistro | after-bench-1 | 0.159554 | 0.148654 | -6.8314% | 2.447568 |
| bistro | after-bench-2 | 0.157953 | 0.146783 | -7.0716% | 2.454554 |
| bistro | before-bench-2 | 0.159417 | 0.149018 | -6.5227% | 2.457884 |
| minecraft | before-bench-1 | 0.229802 | 0.250629 | +9.0640% | 1.176784 |
| minecraft | after-bench-1 | 0.229686 | 0.250525 | +9.0740% | 1.175142 |
| minecraft | after-bench-2 | 0.229035 | 0.250042 | +9.1752% | 1.173679 |
| minecraft | before-bench-2 | 0.228115 | 0.249349 | +9.3091% | 1.172760 |

| 정리 후−전 (기술 통계) | AA 절대 평균 변화 | 각 실행 ④ 기준 정규화 변화 | WholeFrame 절대 변화 |
|---|---|---|---|
| bistro | -0.8327% | -0.4575% | -0.1430% |
| minecraft | +0.1179% | -0.0567% | -0.0308% |

build당 독립 process가 2개뿐이고 renderer의 GPU 실행 의미를 바꾸지 않은 정리이므로, 이 작은 cross-process 차이를 확정적인 성능 개선으로 보고하지 않는다. 위 최적화본의 ⑰ comparator는 optimization exe의 후보 Off 경로이며, ABBA의 이전 exe 절대값과 같은 실행인 것처럼 합치지 않는다.

## 진단 pass profile와 남은 비용

아래는 별도 process의 pass timer On 진단(300 warm-up, 2,400×3회)이다. 진단 타이머가 꺼진 본 benchmark와 절대값을 섞지 않는다.

| 장면 | 설정 | prepare ms | edge ms | weights ms | neighborhood ms | resolve ms |
|---|---|---|---|---|---|---|
| bistro | ④ native O-T2X-R | 0.008027 | 0.027098 | 0.024389 | 0.042294 | 0.033552 |
| bistro | ⑰ (후보 Off) | 0.007995 | 0.027437 | 0.025381 | 0.053615 | 0.010398 |
| bistro | ⑰+O3 | 0.008020 | 0.027427 | 0.025372 | 0.044625 | 0.008653 |
| bistro | ⑰+O2+O3 | 0.008027 | 0.027452 | 0.025365 | 0.043127 | 0.008389 |
| minecraft | ④ native O-T2X-R | 0.005783 | 0.027969 | 0.086282 | 0.049362 | 0.035333 |
| minecraft | ⑰ (후보 Off) | 0.005832 | 0.034803 | 0.087905 | 0.060499 | 0.035349 |
| minecraft | ⑰+O3 | 0.005839 | 0.034851 | 0.088481 | 0.052587 | 0.029337 |
| minecraft | ⑰+O2+O3 | 0.005813 | 0.034725 | 0.087823 | 0.051043 | 0.029002 |

O3는 neighborhood의 visible slot 1과 resolve의 visible slot 0을 비워 중복 color write를 줄인다. spatial 사본과 다음 history는 유지한다. 앱의 기존 최종 StretchRect는 history를 읽으며 여전히 실행된다. 이 최종 복사는 SMAA scope 밖이고 독립 timestamp가 없으므로 별도 copy 절감 시간으로 보고하지 않는다. Edge scope의 잔여 차이에는 raw-edge union 외에 ④와의 pattern/edge population 차이도 있으므로 전부 선택 효과로 단정하지 않는다.

Minecraft 결합 후보의 native ④ 대비 진단 차이는 edge +0.006756 ms, weights +0.001540 ms, neighborhood +0.001681 ms인 반면 resolve는 -0.006332 ms다. 가장 큰 양의 잔여 항목은 edge scope다. 현재 출력을 유지하면서 이 비용을 더 줄이는 방법은 이번 작업에서 검증하지 못했다. 단일 target 전용 shader의 산술 재배치 등 이전에 기각한 방식을 근거 없이 재시도하지 않았다.

## 출력 검증과 시각적 한계

두 장면 각각 6×240 PNG의 f0~239 연속 index, 1920×1061 RGB, 모드 설정·jitter phase·report hash를 검사했다. 모든 ⑰ 후보는 같은 실행의 ⑰, 정리본 `after-a`, 원래 ⑰ 기록과 mismatch 0이다. ④도 정리본·원래 기록과 mismatch 0이다. 이전 정리 단계의 같은 binary 반복 결정성·mask/history/alpha 진단 결과는 정리 문서에 구분해 보존한다. 이번 O3 gate는 RGB만 인증하며 새 내부 alpha/mask 진단을 했다고 주장하지 않는다.

raw full frame f130/f181/f230와 nearest 3× ROI의 이동 f126~131, 확대 실패 주변 f124~133, 전환 f178~183, 정지 f230를 직접 열었다. Bistro (1230,582)–(1358,670)의 가는 의자 다리·연결부 단절과 Minecraft (956,524)–(1020,620)의 f128/f130 경계 약화·단절 및 f129/f131 재출현이 ⑰와 결합 후보에 똑같이 남았다. CGVQM 재실행이나 품질 개선 판정은 하지 않았다. GIF는 생성·decode 검증했지만 재생을 직접 봤다고 주장하지 않는다.

## 브랜치·환경·재현

- 원래 ⑰: `experiment/edge-history-source-color-blend` @ `5bdd189`.
- 정리: `tooling/edge-history-color-blend-cleanup` @ `d2a6315`, 원래 ⑰에서 직접 분기.
- 최적화: `experiment/edge-history-color-blend-optimization`, 의존성 `d2a6315`. 이번 측정 head는 `6ef1564`; renderer/HLSL은 인계된 후보 그대로다.
- RTX 3060 Ti / driver 610.88, Ryzen 5 5600, DX11 Release x64, SMAA Ultra, 1920×1061, hidden/windowed, VSync Off, fixed 60 Hz. still60/move120/still60, play time 2.0부터의 동일 240-frame loop. camera/depth motion만 사용한다.
- benchmark는 PNG·추가 진단 query·readback·pass timer Off, 30초 precondition, mode당 300 warm-up, 4,800×6회이며 정/역 mode 순서를 교차한다.
- 명령마다 CMAA2 0개 확인→새 process→1,200초 timeout→잔류 0개 확인. 성능 실행 전 P8 및 경쟁 GPU process를 확인해 receipt에 남겼다. 성능 campaign의 process 사이 10초 간격은 초기 정지 완화 가설일 뿐 원인 해결로 주장하지 않는다.

| 실행 파일 | SHA-256 |
|---|---|
| 정리 전 | CA01DDD6602ABC129A49D246B7D93C17E4F92FC3E0570E9DE92864792130B739 |
| 정리 후 | 47E69FD5B3073FDFFBD364FA5F2F3B55ED5107C893B1345E701D2EBBF586D212 |
| 최적화 후보 matrix | C83A5E29CB5A5F79ECF1BC3F2850CE4763FD921C957B4328DBDCDA8BE35C2638 |

```powershell
Tools/SMAA/run_color_blend_campaign.ps1 -Stage Optimization -OutputRoot C:/Users/USER/Desktop/research/tmp/c17-resume-20261019
Tools/SMAA/run_color_blend_campaign.ps1 -Stage CleanupABBA -OutputRoot C:/Users/USER/Desktop/research/tmp/c17-resume-20261019
Tools/SMAA/run_color_blend_campaign.ps1 -Stage Profile -OutputRoot C:/Users/USER/Desktop/research/tmp/c17-resume-20261019
```

실제 인수·UTC 시각·commit·harness/renderer/report/exe hash·GPU 확인은 `runs-20261019.json`에 있다. 각 결과 report는 원시 AutoBench 경로에 보존하며 미디어/빌드/원시 CSV는 Git에 넣지 않았다. 재실행 시 이미 사용한 label은 그대로 덮어쓰지 않고 새 label 또는 명시적인 retry reason을 사용한다.

Microsoft의 [OMSetRenderTargets 문서](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-omsetrendertargets)는 개별 RTV slot의 미결합과 동시 읽기/쓰기 제한을, [depth-stencil 문서](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-depth-stencil)는 DepthEnable FALSE의 test/write 비활성을 설명한다. 이는 API 의미의 근거이며 성능 개선을 보장하는 근거는 아니다. 실측과 코드 흐름의 근거는 `audit-confirmation-20261019.json`, 이전 정리 감사는 `../Edge-History-Color-Blend-Cleanup/audit-ko.md`다.

## 채택 상태

O1은 제외한다. O2는 작은 AA 절감 후보, O3/O2+O3는 화면 RGB 보존 절감 후보로 보존한다. O3와 결합은 중간 visible texture의 alpha가 기존 resolve alpha lerp에서 current spatial alpha로 바뀌므로 중간 texture의 전체 RGBA 동일성을 주장하지 않는다. Scratch와 history는 같은 input의 resource/SRV/RTV 형식을 물려받고, 최종 StretchRect shader는 RGB를 처리한 뒤 alpha=1.0을 출력하는 것을 소스에서 확인했다. 별도의 swap-chain 화면 캡처를 추가했다고 주장하지 않는다. 사용자 결정 전에는 기본 Off를 유지한다. 채택한다면 ⑰ 전용 설정에 적용하는 별도 커밋과 재검증이 필요하다. 이름은 “⑰ 코드 정리본”, “⑰ 화면 RGB 출력 보존 최적화 후보”로 유지하고 새 알고리즘 번호를 부여하지 않는다.

## 원본 픽셀과 비교 자료

- [Bistro ④ vs 결합 후보 GIF](C:/Users/USER/Desktop/research/Reports/Case17-RGB-Optimization-20261019/images/bistro-thin-chair-4-vs-17selected.gif), [Minecraft GIF](C:/Users/USER/Desktop/research/Reports/Case17-RGB-Optimization-20261019/images/minecraft-thin-seam-4-vs-17selected.gif): f60~209, nearest 3×, 평균 0.5배속, 총 5초. GIF는 palette 변환 확인용이다.
- [Bistro 원본 픽셀 확대 f124~133](C:/Users/USER/Desktop/research/Reports/Case17-RGB-Optimization-20261019/images/bistro-thin-chair-failure-window.png), [Minecraft 확대](C:/Users/USER/Desktop/research/Reports/Case17-RGB-Optimization-20261019/images/minecraft-thin-seam-failure-window.png): 첫 행 정리본 ⑰, 둘째 행 결합 후보, 셋째 행 ④, 넷째 행은 별도 표시한 ×16 차이 영상이다.
- [Bistro f130 전체 프레임 PNG](C:/Users/USER/Desktop/research/Reports/Case17-RGB-Optimization-20261019/images/bistro-full-f130-case17-selected.png), [Minecraft f130 PNG](C:/Users/USER/Desktop/research/Reports/Case17-RGB-Optimization-20261019/images/minecraft-full-f130-case17-selected.png): 원본 픽셀의 무손실 복사본이다. 실제 원시 PNG는 `runs-20261019.json`의 각 Capture `capture_root` 아래에 있다.
- [완료 감사](C:/Users/USER/Desktop/research/Reports/Case17-RGB-Optimization-20261019/data/completion-audit-20261019.json), [비교 CSV](C:/Users/USER/Desktop/research/Reports/Case17-RGB-Optimization-20261019/data/optimization-performance.csv). 전체 원시 capture는 2,880 PNG / 6,294,141,909 bytes(약 5.86 GiB)이며 별도 보존했다.
