# 확보 소스 후보 생성 비용 조사와 진단 출력 최적화 결과

진단 mask 쓰기와 base-edge 통계 atomic을 생략해도 전체 AA 시간은 거의 변하지 않았다. 두 장면의 960-frame 출력 동일성은 통과했지만, 주요 후보 생성 병목을 해결하거나 성능 우위를 확보한 결과는 아니다.

## 변경 범위

`research/tscmaa-source-candidate-reuse`에서 `d54c46c`의 source-integrated 후보 PS를 조사했다. Original SMAA, source RGB 후보식, source temporal kernel, camera/depth R, expansion None을 고정했다. Object motion, sampling, clipping, blending, feedback, 후보 compact와 indirect resolve는 변경하지 않았다.

`SMAA_RECOVERED_OPTIONAL_DIAGNOSTICS=1`은 compact resolve에서 소비하지 않는 base/selected mask 및 base-edge counter를 진단이 필요할 때만 쓴다. Readback, forced count 및 mask debug에서는 해당 출력을 유지한다. 0은 기존 unconditional 출력과 bytecode가 같은 대조군이다. 정리 코드는 연구 브랜치에 유지하되 성능 개선 완료로 분류하지 않는다.

## 성능 조건

RTX 3060 Ti / Ryzen 5 5600, Release x64 DX11 Ultra, 1920×1017, VSync/UI/PNG/readback Off. 기존 flythrough start 0 / fixed 60 Hz. 각 장면 3개의 독립 process pair, 전→후 / 후→전 / 전→후. 한 실행은 Standard / Source-Separate / Source-Integrated의 세 mode에 warm-up 300, 측정 4,800 frame, repeat 1이다. 전후 각각 장면별 세 run이므로 mode당 14,400 표본이다. 모든 정식 결과 12개에서 내부 validation과 표본 수를 확인했다. 두 장면의 창 visible=true/minimized=false를 별도 샘플로 확인했다.

같은 실행파일을 사용하고 shader compile switch만 바꿨다. 실행별 exe/shader/candidate hash, 명령, 원시 CSV 위치 및 모든 pass의 평균·median·SD·p95·p99는 동봉 JSON에 기록했다. CPU wall p99 기반 1% low는 기존 정의 1000/p99로 계산한다. WholeFrame은 Present를 제외한다.

## 전체 AA 결과

변화율은 세 pair별 변화율의 평균이다. 단위 ms, 음수는 시간 감소다.

|장면|변경 전|변경 후|평균 변화|각 pair 변화|전후 차이 95% 구간 ms|
|---|---:|---:|---:|---|---|
|bistro|0.469365|0.469182|-0.037%|+0.387%, -0.365%, -0.134%|-0.004663, +0.004296|
|minecraft|0.485874|0.484846|-0.208%|+0.258%, -0.172%, -0.711%|-0.006911, +0.004855|

두 구간 모두 0을 포함한다. n=3의 비보정 t(2) 구간이며 다중 지표를 검사한 서술적 진단이다. 프레임 수를 독립 표본 수로 사용하지 않았다. 이번 결과로 의미 있는 속도 개선을 주장하지 않는다.

|장면|대상|AA 변화|WholeFrame 변화|
|---|---|---:|---:|
|bistro|Standard T2X-R 대조군|+0.699%|+1.793%|
|bistro|Source-Separate 대조군|+0.215%|+2.616%|
|bistro|Source-Integrated 변경 대상|-0.037%|+2.568%|
|minecraft|Standard T2X-R 대조군|+0.146%|+1.496%|
|minecraft|Source-Separate 대조군|+0.129%|+1.953%|
|minecraft|Source-Integrated 변경 대상|-0.208%|+1.632%|

WholeFrame은 미변경 대조군에서도 같은 방향으로 변했다. 따라서 증가분을 최적화의 원인 효과로 단정하지 않는다. 실행 간 환경 변동을 충분히 제거하지 못한 한계가 있으며 전체 프레임 성능 개선도 확인되지 않았다. Standard/Separate로 나눈 AA 비율의 보조 진단도 JSON에 별도로 기록했다.

|장면|현재 Standard T2X-R AA|현재 Source-Integrated AA|Standard 대비|
|---|---:|---:|---:|
|bistro|0.275929|0.469182|+70.04%|
|minecraft|0.291283|0.484846|+66.45%|

위 비교는 jitter, kernel, weight, history topology가 다른 완성 방식 비교다. 후보 선택만의 인과 효과도, 전체 게임 FPS 변화도 아니다.

## 후보 계산 재사용 시도의 실패와 미해결 병목

기존 Original RGB integrated PS는 정적 Load 33개, 약 444 instruction slots였다. 공유 영역을 9개 RGB 입력으로 전개한 안은 Load 9개/227 slots로 줄었지만 후보 동일성을 통과하지 못했다. 산술식을 유지하며 반복된 범위 검사를 Texture.Load의 범위 밖 0 반환으로 대체한 안도 Load 9개/167 slots로 줄었으나 후보가 달랐다. 명시적 mad를 사용한 변형도 통과하지 못했다. [Microsoft Texture.Load 명세](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load)는 범위 밖 자원 읽기의 0 반환을 보장하지만, 산술 최적화 후의 후보 bit 동일성까지 보장하는 것은 아니다.

|시도|Bistro 기준/시도 후보 수|Minecraft 기준/시도 후보 수|실행|
|---|---|---|---|
|9-input 명시적 전개|24466 / 24462|336782 / 336776|20260915_143231|
|Load 분기 제거|24466 / 24462|336782 / 336776|20260915_143410|
|Load 분기 제거 및 명시적 mad|24466 / 24464|336782 / 336792|20260915_143503|

작은 수의 후보 차이라도 이번 출력 보존 gate에는 실패다. 세 변경은 최종 셰이더에서 제거했고 실패 코드와 로그는 tmp/recovered-candidate-reuse에 보존했다. 반올림·최소 정밀도·연산 재배치 영향은 원인 후보이며 아직 정확히 분리하지 않았다. 현재 채택한 진단 출력 정리는 Load 33개를 유지한다. 따라서 앞서 관측한 공간+후보 약 0.145 ms 증가를 이번 변경으로 제거했다고 주장하지 않는다.

## 정확성

- 기본 8-case 96 PNG는 20260914_191019와 hash mismatch 0.
- 두 장면 separate/integrated 480-frame씩, 총 960 frame mismatch 0. 이전 source 결과와도 동일. 기존 camera capture는 readback을 강제로 Off로 하므로 최적화가 활성인 상태의 검증이다.
- Readback-Off debug mask 12-frame×2장면은 이전 mask와 mismatch 0.
- Same-draw snapshot 14단계, candidate/process/indirect args 및 mask/list 집합 PASS. 중복/OOB/overflow 0.
- Forced count 0/65/1,952,640은 명시적 readback Off 요청에서도 진단 counter와 bounds 검사 PASS.
- Lifecycle와 integrated feedback PASS. 기존 공간 PS 4개와 source CS 2개 bytecode 동일. 변경 integrated PS 4개 compile PASS. 최종 Release x64 build PASS.
- 출력 동일성에 근거해 기존 품질 결과를 연결한다. 새 CGVQM을 계산하거나 품질이 향상됐다고 주장하지 않는다.

## 실행 실패와 복구

최초 sandbox 실행은 결과 경로 생성에 실패하여 제외했다. 초기 빌드는 환경 변수 Path/PATH 중복으로 실패했으며 빌드 자식 프로세스의 환경 변수 키를 정규화한 뒤 통과했다.

Minecraft 시작 단계에서 0xc0000409 / offset 0x1ea819의 응용 프로그램 종료가 두 차례 발생했다 (14:55:29, 14:57:06). 덤프의 fast-fail parameter는 7이었다. 실패 실행과 짝이 끊긴 20260915_145459 결과는 본 평균에서 제외했다. 짧은 smoke는 통과했지만 단순 재시도는 다시 실패했다.

저장된 시작 장면은 San Miguel(SceneChoice=5)이었다. Minecraft 재개 측정에서는 AutoBench의 목표 장면 선택 전 초기 장면만 Bistro(0)로 고정했고 여섯 정식 실행이 모두 완료됐다. 실제 측정은 원래 Minecraft 경로와 300 warm-up을 유지했다. 이 변경은 시작 경로 우회이며 근본 원인을 확정한 수정은 아니다. 완료된 Bistro 세 쌍은 기존 시작 설정으로 측정한 자료다. 장면별 pair 내부 조건은 동일하게 유지했고 두 장면의 절대 시간을 직접 비교하지 않는다. 종료 후 사용자 ApplicationSettings.xml을 원본과 SHA-256 동일하게 복원했고 잔류 CMAA2 프로세스는 0개다.

## 다음 단계

추가 후보 최적화는 연산 결과를 보존하는 수치 계약부터 검증해야 한다. 무조건 9-load 안을 채택하지 않는다. 동시에 소스 기반 temporal 품질 저하의 첫 분리 대상으로 YCoCg 통계 이후 RGB clipping endpoint 변환, 음수 chroma 제한, sampling 및 blending을 독립 비교한다. 기존 구현과 source 후보/기존 kernel 조합을 대조군으로 유지하며 3×3/Dual Filter는 별도 후속 범위다.

재현 도구: Tools/SMAA/run_recovered_candidate_overhead.ps1, validate_recovered_candidate_overhead.py, analyze_recovered_candidate_overhead.py. [반복 성능](Recovered-Candidate-Overhead-20260915/performance.json), [정확성](Recovered-Candidate-Overhead-20260915/correctness.json), [컴파일](Recovered-Candidate-Overhead-20260915/compiler.json). PNG, dump, 원시 AutoBench CSV는 저장소에 추가하지 않는다.
