# Adaptive 단계 정리 브랜치

브랜치 `tooling/adaptive-tier-minimal`은 `baseline/selected-temporal`(b6c3ebc)에서 분기했다. Adaptive 단계 연구 네 브랜치에서 채택한 변경 네 가지만 기준선 위에 다시 넣은 정리 구현이다. `-R`은 계속 camera/depth reprojection만 뜻한다.

## 브랜치 목록

이 연구는 다섯 브랜치에 나뉘어 있다. 끝 커밋은 문서를 더할 때마다 바뀌므로 갈라진 커밋과 핵심 커밋만 적었다. 다섯 브랜치 모두 push하지 않았다. 마지막 정리 브랜치는 앞의 네 브랜치에서 채택한 변경만 기준선 위에 다시 넣은 구현이다.

| 브랜치 | 갈라진 커밋 | 담긴 작업 | 결과 | 핵심 커밋 |
|---|---|---|---|---|
| `experiment/adaptive-tier-validation` | db30281 (`experiment/selected-temporal-reprojection-off`) | 대비 단계를 데이터로 다시 정하기(0.5%, 1% 한도), 탐색 끝 좌표 수정, 단계 값 지우기 기본값 끄기, 고정 비용 진단, 대각 탐색 조사, 0.5% Ultra 단계의 8-case 적용 | 1% 단계의 SMAA 시간은 같은 프리셋 원본 대비 Ultra Bistro −8.5%, Minecraft −5.8%, High −0.8%, −0.9%였고 Medium은 원본과 거의 같았고 Low는 +0.6%였다 | 187cdea, 4cf063c, 6e87915, d5d619c, cb8139a, e4abf3c, 1d47eea, 77118a6, 06df3ec |
| `experiment/adaptive-tier-cost-reduction` | 06df3ec (단계 브랜치) | 단계 값을 edge 타깃에 담기(B5G6R5, RGBA8), RGBA8 방식의 8-case 적용 | RGBA8에 담으면 출력은 같고 1% 단계가 네 프리셋 모두 원본보다 빨라졌다(Ultra −9.3%, −6.9%, Low −0.2%, −0.4%). 8-case의 AA 시간은 같은 경로 원본보다 Bistro 5.0~8.6%, Minecraft 4.7~6.0% 짧았다. B5G6R5는 매 프레임 지우기로 보이는 비용이 12 µs 넘게 들어 쓰지 않았다 | 8efbf6e, a9a9d1a, 379c1af, 2d7aae6, e8a2640 |
| `experiment/adaptive-tier-weights-cost` | e8a2640 (비용 줄이기 브랜치) | weights 패스에 남은 비용 줄이기(탐색 끝 좌표를 한 번에 계산하는 SharedEnds) | 출력은 같고 명령 슬롯이 280에서 270으로 줄었지만 시간 차이가 없어 쓰지 않았다. 남은 비용은 탐색 루프의 RGBA8 텍셀 읽기로 보인다 | a59e3f4, fdfc771, 3cc998e, 25d84f0 |
| `experiment/adaptive-edge-threshold` | e8a2640 (비용 줄이기 브랜치) | Adaptive edge threshold 올리기(전체 상향, finalDelta 구간별) | 전체로 올려도 구간별로 올려도 첫 단계부터 한도의 7배 이상이어서 프리셋 값을 그대로 쓴다 | 7e86d76, c21ab07, 61431bb, 7b6017a |
| `tooling/adaptive-tier-minimal` | b6c3ebc (`baseline/selected-temporal`) | 채택한 네 변경(1% 단계, 탐색 끝 좌표 수정, 단계 값 지우기 없음, RGBA8 edge 타깃 세 번째 채널)만 기준선(④, 선택 경로, 19번) 위에 다시 넣은 정리 구현 | 출력은 연구 구성과 두 장면 240프레임 PNG 바이트까지 같고 Original은 기반과 같다. 기준선 대비 SMAA 폴더 추가는 +109/−27(코드 91줄)로 이전 Adaptive(9eda8a0)의 +158/−49(코드 151줄)보다 코드 60줄 적다. 시간은 재지 않았다 | 4c30ee7, a3e4b01, c25adff |

예외와 주의할 점은 다음과 같다.

- RGBA8 방식을 8-case에 적용한 커밋(2d7aae6, e8a2640)은 작업 단위마다 브랜치를 나누는 규칙을 정하기 전에 만들어 비용 줄이기 브랜치에 같이 있다.
- edge threshold 브랜치의 a787806은 weights 비용 브랜치의 fdfc771(사전 컴파일 검사 도구 수정)과 같은 변경을 가져온 것이다.
- 고정 비용 진단 커밋(ca86a6e, b7e8d3a, d5d619c)은 단계 브랜치 중간에 들어 있다. 기록을 고치지 않고 그대로 두었다.
- 단계 브랜치에서 멈춘 RG8 1% 8-case Minecraft 캡처는 다시 돌리지 않는다. 비용 줄이기 브랜치의 RGBA8 8-case 캡처(Bistro `20261118_171531`, Minecraft `20261118_172633`)가 같은 하니스의 RG8 1% 구성도 함께 찍었고 두 구성의 출력이 PNG 바이트까지 같았다.
- 각 브랜치의 요약(`summary-ko.md`)에는 그 브랜치 작업까지의 결과만 들어 있다. 다른 브랜치의 결과는 위 표의 결과 칸과 브랜치 이름으로 찾는다.

## 기반

작업 지시에서 권장한 `baseline/selected-temporal`(b6c3ebc)을 그대로 기반으로 썼다. 이 커밋에는 Adaptive가 없다. 이전 Adaptive는 그 위의 9eda8a0(20번, 21번)에서 처음 들어갔다. 그래서 이 브랜치도 9eda8a0처럼 원본 SMAA, ④ `O-T2X-R`, 선택 경로, 19번 위에 Adaptive를 더한다. 같은 기반이라 이전 Adaptive와 줄 수를 바로 비교할 수 있다. reprojection Off 경우(feef6cd)는 기반에 없어서 넣지 않았다.

## 넣은 것

| 변경 | 위치 | 내용 |
|---|---|---|
| 프리셋별 1% 단계 | `SMAA.hlsl` 프리셋 블록 | 아래 표의 경계와 직교 탐색 수. 가장 높은 단계가 프리셋의 직교 최대값(`SMAA_MAX_SEARCH_STEPS`)을 대신하고 대각 탐색은 프리셋 값을 그대로 쓴다 |
| 탐색 끝 좌표 수정 | `SMAA.hlsl` `SMAA_SEARCH_END` | 가장 높은 단계에서는 원본과 같은 끝 좌표 `offset[2]`를 쓰고 낮은 단계는 `texcoord ± 2·steps·픽셀`을 쓴다 |
| 단계 값 지우기 없음 | 없음 | 단계 값을 따로 담는 타깃이 없어서 지우기, 연결, 읽기가 모두 없다 |
| 단계 값을 edge 타깃 세 번째 채널에 담기 | `SMAA.hlsl` `SMAAEncodeEdgeOutput`, `SMAA.cpp` | Adaptive edge 패스가 `float3(edge, 단계)`를 RGBA8 edge 타깃에 쓰고 weights 패스가 같은 텍셀의 B 채널로 단계를 고른다. 0.5는 128/255로 저장돼도 가운데 단계를 고른다 |

| 프리셋 | 경계(luma) | 직교 탐색 수(낮음/가운데/높음) | 대각 |
|---|---|---|---|
| Ultra | 19.5/255, 51.5/255 | 3 / 8 / 20 | 16 |
| High | 31.5/255, 51.5/255 | 2 / 6 / 12 | 8 |
| Medium | 38.5/255, 76.5/255 | 3 / 6 / 8 | 없음 |
| Low | 51.5/255, 63.5/255 | 2 / 3 / 4 | 없음 |

C++ 쪽은 `SMAA` 생성자 인자 `adaptiveSearch`가 `SMAA_ADAPTIVE_SEARCH` 매크로를 넣고 edge 타깃을 RGBA8로 만든다. 래퍼는 `SetAdaptiveSearch`와 `GetAdaptiveSearch`로 Adaptive를 켜고 끄며 값이 바뀌면 SMAA 객체를 다시 만든다. SMAA 1X와 세 temporal 경로 모두 같은 스위치를 쓴다. Original은 래퍼가 `adapterDesc`를 넘기지 않아 원래부터 RG8 edge이고 이 브랜치에서도 그대로다.

## 넣지 않은 것

연구 브랜치에만 있는 설정은 하나도 넣지 않았다. MetaProbe, 단계 타깃 지우기 스위치(ClearMeta), B5G6R5 edge, SharedEnds, Adaptive edge threshold, 단계 sweep 매크로(`SMAA_ADAPTIVE_T1` 등의 덮어쓰기, `SMAA_RESEARCH_MAX_SEARCH_STEPS`), 탐색 반복 횟수 세기, staging readback 진단, pass별 GPU 타이머, 1X 연구 하니스(`AdaptiveTierValidation.inl`)가 여기에 들어간다.

## 하니스

`ColorBlendOptimization.inl`이 세 경로(④, 선택 경로, 19번)를 Original과 Adaptive로 돌린다(6모드, Ultra). 새 `SpatialCapture` 단계는 SMAA 1X(jitter와 history 없음)를 네 프리셋에서 Original과 Adaptive로 캡처한다(8모드, 이름은 O-1X, O-High, O-Medium, O-Low, A-1X, A-High, A-Medium, A-Low). 타임라인은 기존과 같다(정지 60, 이동 120, 정지 60, 1920×1061, 60프레임 warm-up). 실행은 `Tools/SMAA/run_color_blend_preservation.ps1 -Harness Optimization -Phase {Capture|SpatialCapture}`로 명령마다 프로세스 하나씩 했다.

## 셰이더 검사

`Tools/SMAA/audit_adaptive_tier_minimal_shaders.py --base b6c3ebc --research 019db06`로 DX11 경로가 쓰는 모든 entry point(VS 4, SMAA PS 7, 선택 경로 PS 11)를 네 프리셋에서 FXC로 컴파일했다. 매크로는 `SMAA::SMAA`, 프로파일은 `vaSMAAWrapperDX11::CreateTechnique`를 따랐다. Adaptive의 비교 대상은 연구 브랜치 끝(019db06)을 1% RGBA8 단계 모드(`A-*-T3-1p-E4`, `+Tier1pRGBA8`)가 넘긴 매크로로 컴파일한 결과다. 선택 경로 셰이더는 reprojection On만 비교했다. 연구 브랜치에는 기반에 없는 reprojection Off 변형이 있기 때문이다.

| 비교 | 검사한 셰이더 | 바이트 동일 | 시맨틱 표기만 다름 | 그 밖의 차이 |
|---|---:|---:|---:|---:|
| Original, 기반(b6c3ebc) 대비 | 176 | 176 | 0 | 0 |
| Adaptive, 연구 구성 대비 | 132 | 68 | 64 | 0 |

바이트가 다른 64개는 모두 edge 패스 셰이더다. 연구 브랜치는 edge 출력을 구조체 멤버 `SV_Target0`으로, 이 브랜치는 원본 셰이더처럼 `float3` 반환값 `SV_TARGET`으로 선언했다. 그래서 DXBC의 출력 시그니처에 들어가는 이름 표기만 다르고 디스어셈블한 명령은 같았다. weights, blend, resolve 셰이더는 바이트까지 같다. 결과는 `shader-audit.json`이다.

## 출력 비교

2026-11-19, RTX 3060 Ti, 드라이버 621.14, 1920×1061 숨김 창. 이 브랜치 실행 파일(262FD7D1…, c25adff의 소스)로 temporal 6모드와 SMAA 1X 8모드를 장면마다 독립 프로세스 하나씩으로 캡처했다. 기반 실행 파일(c19-minimal worktree, b6c3ebc, DBAB5DC7…)로 Original 세 경로도 같은 날 다시 캡처했다. 비교 상대인 연구 캡처는 1X가 `tier-in-edges-rgba8`(Bistro 20261118_153027, Minecraft 20261118_153924), temporal이 RGBA8 8-case(Bistro 20261118_171531, Minecraft 20261118_172633)다. 모든 쌍을 240프레임 PNG 파일 바이트(SHA-256)로 비교했다. 도구는 `Tools/SMAA/verify_adaptive_tier_minimal.py`이고 결과는 `verify-bistro.json`, `verify-minecraft.json`이다.

| 묶음 | 이 브랜치 모드 | 비교 상대 | Bistro | Minecraft |
|---|---|---|---:|---:|
| SMAA 1X Adaptive | A-1X, A-High, A-Medium, A-Low | 연구 A-U/H/M/L-T3-1p-E4 | 4 × 240/240 | 4 × 240/240 |
| SMAA 1X Original | O-1X, O-High, O-Medium, O-Low | 연구 같은 이름 | 4 × 240/240 | 4 × 240/240 |
| temporal Adaptive | A-T2X-R, A-선택 경로, A-19번 | 연구 `+Tier1pRGBA8` | 3 × 240/240 | 3 × 240/240 |
| temporal Original | ④, 선택 경로, 19번 | 기반 실행 파일 | 3 × 240/240 | 3 × 240/240 |
| temporal Original | ④, 선택 경로, 19번 | 연구 같은 이름 | 3 × 240/240 | 3 × 240/240 |

Adaptive 출력은 두 장면의 1X 네 프리셋과 세 temporal 경로 모두 연구 브랜치의 같은 구성과 PNG 바이트까지 같았다. Original 출력은 기반 실행 파일과 바이트까지 같았다. 출력이 연구 구성과 같으므로 연구 브랜치에서 한 품질 판단(같은 프리셋 원본과 구분되지 않음)이 이 구현에도 그대로 해당한다. 이번에는 PNG를 따로 다시 보지 않았다.

Bistro 첫 temporal 캡처(20261119_213212)에서는 Original 19번의 frame 88 한 장이 기반, 연구와 달랐다. 이 PNG는 1410160번째 바이트의 bit 7 하나가 뒤집혀 IDAT 청크 CRC가 맞지 않았고 복호화도 되지 않았다. 기반과 연구 쪽 파일은 CRC가 정상이었다. 렌더링이 달라서는 CRC가 깨지지 않으므로 PNG를 만든 뒤 생긴 파일 손상으로 봤다. 같은 실행 파일로 Bistro temporal을 한 번 더 찍었고(20261119_214900, 라벨 min-r2) 첫 캡처와 다른 파일은 frame 88 하나뿐이었다. 다시 찍은 캡처는 모든 쌍이 240/240 같았고 위 표의 Bistro temporal 값은 이 캡처의 결과다. 첫 캡처의 비교는 `verify-bistro-first.json`에 남겼다. 앞선 분석에서 PNG를 읽을 때 한 비트가 가끔 다르게 나온 적이 있었는데 이번에는 디스크의 파일 자체가 달랐다. 메모리 불안정일 가능성이 있지만 확인하지 않았다.

## 실행 기록

| 라벨 | 장면 | 단계 | 실행 파일 | 캡처 폴더 |
|---|---|---|---|---|
| min | Bistro | Capture | 이 브랜치 | `min/capture/bistro/20261119_213212` (frame 88 파일 손상) |
| min-r2 | Bistro | Capture | 이 브랜치 | `min-r2/capture/bistro/20261119_214900` |
| min | Minecraft | Capture | 이 브랜치 | `min/capture/minecraft/20261119_213505` |
| min-spatial | Bistro | SpatialCapture | 이 브랜치 | `min-spatial/spatial/bistro/20261119_213752` |
| min-spatial | Minecraft | SpatialCapture | 이 브랜치 | `min-spatial/spatial/minecraft/20261119_214145` |
| base | Bistro | Capture | 기반 (c19-minimal) | `base/capture/bistro/20261119_214525` |
| base | Minecraft | Capture | 기반 (c19-minimal) | `base/capture/minecraft/20261119_214715` |

캡처 폴더의 상위 경로는 `D:/SMAAResearchCaptures/c24-minimal/`이다. 실행마다 CMAA2 프로세스가 0개인지, GPU가 P8이고 사용률이 20% 아래인지 확인했고 프로세스 사이를 10초 이상 띄웠다. 모든 실행이 Aggregate PASS로 끝났고 끝난 뒤 남은 프로세스는 없었다. Minecraft는 두 실행 파일 모두 시작에서 멈추지 않았다. 새 worktree에는 앱이 처음 실행될 때 만드는 `ApplicationSettings.xml`이 없어서 c24 worktree의 파일을 복사했다(c19-minimal의 파일과 내용이 같다). 영수증은 `runs.json`이다.

## 코드 양

기준은 이전 표와 같다. `Projects/CMAA2/SMAA` 폴더의 `.cpp .h .inl .hlsl .hlsli`만 세고 공백과 빈 줄 변경은 세지 않는다. 코드 줄은 추가 줄에서 빈 줄, `//` 주석, 블록 주석을 뺀 값이다. 계산은 `Tools/SMAA/count_smaa_lines.py`이고 결과는 `line-counts.json`이다.

기준선(b6c3ebc) 대비 Adaptive 추가분은 다음과 같다.

| 구성 | 추가 | 삭제 | 코드 줄 | 셰이더 (추가/삭제/코드) | C++ (추가/삭제/코드) |
|---|---:|---:|---:|---|---|
| 이 브랜치 | 109 | 27 | 91 | 90 / 22 / 75 | 19 / 5 / 16 |
| 이전 Adaptive (9eda8a0) | 158 | 49 | 151 | 114 / 38 / 109 | 44 / 11 / 42 |
| 연구 브랜치 끝 (019db06) | 554 | 57 | 470 | 248 / 40 / 215 | 306 / 17 / 255 |

이 브랜치는 이전 Adaptive보다 추가 줄이 49줄, 코드 줄이 60줄(40%) 적다. 단계 값 R8 타깃과 그 연결 코드가 없어졌고 끝 좌표 수정은 네 호출을 매크로 하나로 바꿨다. 연구 브랜치 끝에는 연구용 설정과 reprojection Off 경우가 함께 들어 있다.

| 파일 | 종류 | 추가 | 삭제 | 코드 줄 |
|---|---|---:|---:|---:|
| `SMAA.hlsl` | 셰이더 | 80 | 12 | 65 |
| `SMAAWrapper.hlsl` | 셰이더 | 4 | 4 | 4 |
| `SelectedTemporal.hlsl` | 셰이더 | 6 | 6 | 6 |
| `SMAA.cpp` | C++ | 8 | 2 | 6 |
| `SMAA.h` | C++ | 2 | 1 | 2 |
| `vaSMAAWrapper.h` | C++ | 4 | 0 | 3 |
| `vaSMAAWrapperDX11.cpp` | C++ | 5 | 2 | 5 |

원본 SMAA(`baseline/original-smaa`, ee0020d) 대비는 다음과 같다.

| 구성 | 추가 | 삭제 | 코드 줄 |
|---|---:|---:|---:|
| Adaptive SMAA (`main`) | 181 | 56 | 132 |
| 기준선 (④ + 선택 경로 + 19번) | 545 | 61 | 439 |
| 이전 결합 (기준선 + 이전 Adaptive, 9eda8a0) | 690 | 97 | 577 |
| 이 브랜치 (기준선 + 이 Adaptive) | 647 | 81 | 523 |

추가와 삭제는 이전 문서의 표(181/56, 545/61, 690/97)와 같다. 코드 줄은 이전 표(134, 441, 579)보다 2줄씩 적다. 이번 스크립트는 파일 전체를 읽고 `/* */` 안에 막아 둔 옛 코드도 주석으로 세기 때문이다. 예를 들어 `main`의 `SMAA.cpp` 190행이 그렇다. 기준선 대비 이전 Adaptive의 코드 151줄은 두 방식이 같다.

원본 SMAA 대비 Adaptive만의 줄 수는 이렇게 본다. 기준선은 `SMAA.hlsl`을 바꾸지 않으므로 이 브랜치의 `SMAA.hlsl` 변경(+80/−12, 코드 65줄)이 원본 대비 Adaptive 셰이더 변경 전체다. `main` Adaptive의 `SMAA.hlsl`은 +114/−36(코드 80줄)이었다. 선택 경로에 Adaptive를 잇는 `SelectedTemporal.hlsl` 6줄을 빼면 이 브랜치의 Adaptive는 +103/−21(코드 85줄)이고 `main` Adaptive 전체는 +181/−56(코드 132줄)이다. `main`의 줄 수에는 이 브랜치에 없는 R8 단계 타깃과 외부 저장소 연결 코드, 그리고 중괄호 줄 바꿈만 바꾼 줄이 들어 있다.

## 시간 측정

하지 않았다. 이 작업에는 시간 측정 허락이 없었다. 연구 브랜치에서 잰 시간이 이 구현에도 그대로 해당하는지는 재지 않았다.
