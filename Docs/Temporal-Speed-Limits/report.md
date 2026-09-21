# 기존 temporal 패스의 동일 출력 속도 최적화

**새 실행 변형 10개를 검증했지만 두 장면에서 공통으로 채택할 속도 개선은 확보하지 못했다.**
읽기 생략은 Bistro에서 이득, Minecraft에서 손해였고, 공통 계산 제거는 긴 반복에서도
전체 AA의 안정적인 감소로 이어지지 않았다. 기본 구현과 기준선은 변경하지 않는다.
이는 현재 출력·선택식·DX11/RTX 3060 Ti 범위에서 확인한 한계이며 모든 구현의 불가능 증명이 아니다.

## 범위

`experiment/temporal-pass-speed-limits`를 `af2c35b`에서 분기했다. 구현 커밋은
`0561a9f`다. 품질 개선은 보류하고, 직전 선택적 paired de-jitter 구현(kind33)의
픽셀 선택과 출력을 유지하면서 실행 비용을 줄이는 데 범위를 한정했다.

Original 공간 SMAA, camera/depth reprojection On, paired jitter, spatial-frame history,
current/history Linear sampling, 원래 velocity-alpha weight와 luma derivative threshold
0.01을 유지한다. 모든 변형은 기존 temporal draw 안에서 실행한다. 새 패스, texture,
후보 목록, 다른 패스의 edge 읽기, dilation 또는 Adaptive 공간 처리는 추가하지 않았다.
Intel TSCMAA의 완전 재현이나 최종 8-case 측정이라고 표현하지 않는다.

`O-T2X-R`은 공식 Standard 경로의 대조군이다. 새 변형과의 동일 출력 검사는 원본 T2X-R이
아니라 직전 선택적 paired 구현을 기준으로 한다. 원본과 선택적 구현의 필터·출력 차이는
이전 단계부터 존재한다.

## 비교한 실행 방식

1. 비선택 픽셀에서 velocity/history 읽기와 혼합 계산을 생략하는 분기.
2. jitter의 위상 선택과 정규화 계산을 기존 상수 버퍼의 padding으로 전달하는 방식.
   기존 48-byte 버퍼와 기존 update를 재사용하며 새 upload를 만들지 않는다.
3. 두 변경의 결합과 velocity 읽기를 앞에 둔 prefetch 배치.
4. warp 전체가 비선택이면 읽기를 생략하는 vote-any.
5. jitter 두 위상별 상수를 컴파일한 PS를 기존 draw에서 선택하는 방식.
6. 4/8/16 lane 묶음별로 읽기를 생략하는 방식.
7. warp의 선택 lane 수가 8/16보다 적을 때만 픽셀별 early return을 하는 방식.

Prefetch는 FXC가 UniformBranch와 동일한 명령열로 최적화하여 중복 runtime 측정을 제외했다.
위상 두 PS는 한 실행 방식으로 센다. 실제 장면에서 비교한 새로운 실행 변형은 총 10개다.
선택 밀도와 lane 묶음은 **실행 여부만** 바꾸며, 선택 픽셀이나 최종 혼합 가중치를 바꾸지 않는다.
lane 순서를 화면의 quad/tile 배치라고 가정하지 않는다.

분기 전에 luma 미분을 계산하고 조건부 texture 읽기는 명시적 LOD0를 사용한다.
NVAPI의 vote-any/ballot/lane ID는 공식 SDK의 의미를 따르며, 실행 휴리스틱 자체는 연구용이다.
새 Group/Density 경로에는 ballot와 lane ID 지원 조회를 추가했다. 기존 샘플링에서 실패한
단순 소스 순서·분기 재표현을 무작정 반복하지 않고, 이번 Linear 입력과 보정된 위치 때문에
실행 비용이 달라질 수 있는 항목만 재검증했다. 공식 문서와 제외 근거는 [방법](method.md)에 있다.

## 정확성 검증

- Native 8개와 기존 paired 4개 shader variant의 컴파일 bytecode가 이전과 동일했다.
- 신규 24개 shader variant(R Off/On 포함)를 경고를 오류로 처리하여 컴파일했다.
  texture sample 명령 수, resource 슬롯, 미분과 분기의 순서를 검사했다.
- 두 장면의 첫 matrix 7개, 후속 matrix 8개 mode를 각각 240 frame 렌더했다.
  각 mode에서 53개 PNG만 저장하여 총 1,590개 비교에서 불일치 0이었다.
  이 중 424개는 이전 캡처의 native/paired 대조군과 연결하는 비교다.
- 전체 렌더 구간의 paired pattern 검사 7,200개가 통과했다. 첫 frame, 이동 시작/종료와
  정지 두 위상을 포함한다. 전체 240 frame의 pixel 동일성이나 모든 입력의 동치 증명은 아니다.

Release x64 빌드와 두 장면의 각 단계 smoke가 통과했다. 최초 공통 schedule 함수의 FXC
X4000 경고는 명시적 entry 함수로 수정한 뒤 통과했으며 실패 shader는 GPU에서 실행하지 않았다.
Group의 Minecraft 캡처 후 기능 지원 조회를 보강하여 다시 빌드했다. 실제 샘플링 코드는 같고
실행파일 hash 차이는 각 receipt에 남겼다. 이후 Group 성능과 최종 측정은 같은 실행파일을 사용한다.

## 측정 조건

RTX 3060 Ti, DirectX 11, SMAA Ultra, 1920×1061, hidden, VSync Off다.
카메라는 기존 flythrough t=2에서 60-frame 정지, 120-frame 이동, 60-frame 정지를 반복한다.
30초 미측정 렌더링, mode별 300-frame warmup 뒤 screen은 2,400 frame×3회,
최종 확인은 4,800 frame×4회다. 정/역 mode 순서를 교차한다.

각 명령은 독립 프로세스이고 전후 잔류 CMAA2가 0인지 확인한다. 성능 측정에는 PNG 저장과
후보 readback을 넣지 않았으며 CPU 영상 분석도 병행하지 않았다. 같은 프로세스의 대응 mode를
비교하며 서로 다른 단계의 절대 시간을 직접 빼서 개선량으로 해석하지 않는다.
Smoke 시간은 정식 성능 결론에 사용하지 않는다. p95/p99, median, Wall FPS, 1% low와
각 반복값은 장면별 JSON에 보존한다.

## Screen 결과

분기·warp 실행은 Bistro에서 유리하지만 Minecraft에서 불리했다. UniformBranch의 첫 screen
전체 AA는 Bistro `0.201329 ms`(기존 선택 `0.211825 ms`), Minecraft `0.290281 ms`
(기존 선택 `0.287374 ms`)였다. 한 장면의 이득을 두 장면 공통 개선으로 보고하지 않는다.

후속 Group4/8/16과 Density8/16도 이 상충을 해소하지 못했다. 기존 선택 대비 전체 AA가
Bistro에서는 약 4.5~4.7% 감소했지만 Minecraft에서는 약 1.4~1.6% 증가했다.
따라서 이 다섯 변형은 최종 채택 후보에서 제외했다. warp 투표와 실행 흐름 조절 역시
무비용이 아니라는 관측이며, 이번 실시간 측정만으로 특정 GPU stall의 기여율까지 단정하지 않는다.

위상 특화의 Bistro resolve 차이는 첫 screen에서 약 −0.029 µs였지만 후속 screen에서는
약 +0.001 µs였다. 작은 평균 차이만으로 가속이라고 선언하지 않고 uniform scalar와 함께
긴 교차 반복으로 확인했다.

## 최종 4회 반복 확인

| 전체 AA GPU 시간 | Bistro | Minecraft |
|---|---:|---:|
| 원본 O-T2X-R | 0.210604 ms | 0.283521 ms |
| 기존 선택적 paired 구현 | 0.211866 ms | 0.285019 ms |
| UniformScalar | 0.211896 ms | 0.284994 ms |
| PhaseScalar | 0.212007 ms | 0.285044 ms |

UniformScalar의 기존 선택 대비 평균 변화는 Bistro **+0.014%**, Minecraft **−0.009%**다.
PhaseScalar는 각각 **+0.066%**, **+0.009%**다. 이 차이를 공통 성능 향상으로 판정하지 않는다.
특히 Minecraft의 UniformScalar는 정순에서 +0.762 µs, 역순에서 −0.812 µs였고,
수정하지 않은 Spatial scope도 같은 방향으로 달라졌다. 순서에 연결된 변동을 제거하지 않은
작은 전체 시간 평균을 확정적인 최적화 효과로 주장할 수 없다.

Resolve 평균 감소는 UniformScalar가 Bistro/Minecraft −0.034/−0.021 µs,
PhaseScalar가 −0.014/−0.032 µs다. Bistro UniformScalar의 resolve 차이는 정순 −0.260 µs,
역순 +0.192 µs로 방향도 바뀌었다. GPU 명령 수가 줄었다는 사실을 실제 속도 향상과 동일시하지 않는다.
native 대비로는 두 후보 모두 resolve와 전체 AA가 각 장면 4/4 반복에서 느렸다.

현재 선택적 paired 구현은 같은 최종 실행에서 원본보다 전체 AA가 Bistro +0.599%,
Minecraft +0.529% 느렸다. 새 두 후보도 원본보다 +0.520~0.666% 느렸다.
이 차이는 선택식뿐 아니라 기존 paired 재구성과 Linear filtering의 비용도 포함한다.
원본과 완전히 동일한 화질에서 후보 선택 하나만 바꾼 비용으로 해석하지 않는다.

## 판정

추가 패스 없이 같은 출력을 유지하는 범위에서, 조건부 읽기·공통 계산·위상 특화·warp 및
lane 그룹·선택 밀도에 따른 실행 흐름을 비교했다. 앞선 Point 입력 연구의 명령 재배치,
Load 전환, weight 재배열과 compiler 실험까지 고려할 때, 현재는 새 중복 비용이나
공통 가속 후보를 찾았다는 근거가 없다. 실패한 문법 변경을 다시 반복하는 것으로 이어가지 않는다.

이번 속도 단계는 **기본값 채택 없음, 부정 결과 보존**으로 마무리한다. 품질 평가는 새로
하지 않았으며, 기존 구현의 남아 있는 정지 떨림이나 blur가 해결됐다는 주장도 하지 않는다.
화질·선택식·정밀도를 바꾸어 더 빨라지는 방법은 동일 출력 최적화와 분리할 후속 가설이다.
독립 세션 반복이나 사전에 정한 동등성 허용 폭이 없으므로 통계적 동등성 검증이라고도 부르지 않는다.

## 재현 자료와 해석 범위

[전체 측정표](tables.md), [검증·실행 출처](results.json), [컴파일 결과](shader-validation.json)를
함께 사용한다. 원시 report의 hash, 실행파일 hash, 정확한 인자와 시각은 각 JSON receipt에 있다.
원시 PNG, 실행파일, cache는 저장소에 추가하지 않는다.

실행은 `Tools/SMAA/run_temporal_speed.ps1`의 Capture/Smoke/ScreenBenchmark,
GroupCapture/GroupSmoke/GroupScreenBenchmark, Benchmark 순서이며 장면별로 실행한다.
완료 후 `analyze_temporal_speed.py --scene <scene> --phase <phase>`와
`summarize_temporal_speed.py`로 검증·정리한다. 재실행 시 별도 Receipt를 사용하고 분석기의
`--receipt`와 `--output-dir`, 요약 도구의 `--results-dir`로 원래 결과를 보존한다.
저장된 과거 baseline 캡처가 없으면 그 baseline부터 확보해야 한다.

이번 단계에서 GPU counter capture용 opt-in 연결은 준비했지만 새 하드웨어 카운터 측정은
수행하지 않았다. 이전 [Point 입력 카운터 결과](../Temporal-Contrast-Counters/conclusion.md)는
참고 자료이며 이번 Linear/paired 변형의 카운터로 대체 인용하지 않는다.
NVIDIA 외 GPU, 다른 해상도·장면, FP16 또는 다른 selector에 대한 불가능 증명도 아니다.
