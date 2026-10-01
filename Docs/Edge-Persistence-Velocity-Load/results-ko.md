# ⑨ velocity 읽기 비용 단독 실험 결과 — 2026-10-01

새 정수 `Load` 방식에서 전체 AA 시간 감소를 확인하지 못했다. **속도 최적화로 채택하지 않고 기존 ⑨를 유지한다.** 이는 이번 읽기 명령 교체에 대한 결과이며 모든 최적화가 불가능하다는 결론이 아니다.

Branch: `experiment/edge-persistence-velocity-load`. 구현 커밋: `a90c107`. 수정된 ⑥ `304f749`에서 직접 분기하고, 명시한 ⑨ 렌더러 의존성만 가져왔다. 자세한 의존성과 실행 조건은 [method.md](method.md)에 있다.

## 변경 범위

⑨가 **첫 edge 패스에서 이전 raw edge를 재투영할 때** 읽는 velocity 한 곳만 point `SampleLevel(uv, 0)`에서 `Load(int2(SV_Position.xy), mip 0)`로 교체했다. Temporal resolve는 바꾸지 않았다. 원래 보간 UV로 이전 좌표를 계산하고, 현재 edge·이전 raw edge의 합집합, 화면 경계, spatial SMAA, 혼합, history 및 Pattern Off를 유지했다. 읽는 횟수와 데이터 양을 줄인 변경은 아니다. 새 실행 패스나 추가 복사는 없다. 진단용 전체 화면 probe는 캡처에서만 실행했다.

L은 실험 이름이며 사용자 비교 번호 ⑩으로 확정하지 않았다. ⑥·⑨·④는 같은 실행의 보존 대조군이다.

## 전체 AA 및 temporal 시간

RTX 3060 Ti, DX11 Release x64, Ultra, 1920×1061, hidden, VSync Off. 장면마다 별도 clean process에서 30초 준비 후 mode별 300 warm-up + 4,800프레임 × 3회, 순서 정방향/역방향 교차. PNG, staging readback, coverage query와 세부 spatial timer는 Off. 전체 AA에는 공간 처리·필요한 준비·camera velocity·temporal resolve가 포함된다. Temporal 열은 결합 단계만이다. 양수는 느려짐, 음수는 시간 감소다.

| 장면 | 방식 | 전체 AA ms | 같은 실행 ④ 대비 | temporal ms | temporal ④ 대비 |
|---|---|---:|---:|---:|---:|
| bistro | ⑥ 현재 edge | 0.138843 | -14.85% | 0.007426 | -78.27% |
| bistro | ⑨ 기존 point 읽기 | 0.139651 | -14.35% | 0.007657 | -77.59% |
| bistro | L 정수 Load 실험 | 0.140069 | -14.10% | 0.007619 | -77.71% |
| bistro | ④ 원본 T2X-R | 0.163053 | +0.00% | 0.034176 | +0.00% |
| minecraft | ⑥ 현재 edge | 0.225382 | -4.14% | 0.023824 | -33.34% |
| minecraft | ⑨ 기존 point 읽기 | 0.234941 | -0.08% | 0.024227 | -32.22% |
| minecraft | L 정수 Load 실험 | 0.236258 | +0.48% | 0.024341 | -31.90% |
| minecraft | ④ 원본 T2X-R | 0.235118 | +0.00% | 0.035742 | +0.00% |

④는 paired jitter/subsample pattern On, 나머지는 Off다. 따라서 ④와의 차이를 이번 Load 변경 효과나 edge 선택만의 효과로 해석하지 않는다. **이번 실험의 효과는 아래 L−⑨로 판단한다.**

| 장면 | L−⑨ 전체 AA ms | 평균 시간 변화 | 각 반복의 변화율 | 짝 차이의 표준편차 ms |
|---|---:|---:|---|---:|
| bistro | +0.000418 | +0.30% | +0.368% / -0.003% / +0.534% | 0.000384 |
| minecraft | +0.001317 | +0.56% | +1.05% / -0.58% / +1.22% | 0.002344 |

절대 차이가 작고 반복 간 변동이 있으므로 보편적인 성능 악화율이나 통계적 확정치로 주장하지 않는다. 반복 평균에서 개선되지 않았고, 아래 첫 패스 측정에서도 절약이 없어서 채택 근거가 없다. WholeFrame 및 분포·각 run 값은 장면별 `benchmark.json`에 보존했다.

## 첫 패스 비용 — 별도 진단 측정

세부 timer를 켠 960프레임 × 3회 실행이다. 위 clean 전체 AA 측정과 별도 실행이므로 두 표의 절대 시간을 서로 빼서 해석하지 않는다.

| 장면 | ⑨ 첫 edge 패스 ms | L 첫 edge 패스 ms | 변화 | 각 반복 변화율 |
|---|---:|---:|---:|---|
| bistro | 0.028204 | 0.028572 | +1.31% | +0.93% / +2.15% / +0.84% |
| minecraft | 0.035530 | 0.036119 | +1.66% | +2.17% / +1.05% / +1.76% |

실제 LumaRaw 셰이더의 FXC DXBC는 기존 47개에서 L 49개 명령으로 늘었다. 정수 좌표 읽기가 소스상 단순해 보여도 GPU 실행 비용이 줄어든다고 보장할 수 없다. 이것만으로 명령 두 개가 시간 차이의 전부라고 단정하거나 특정 cache/메모리 병목으로 확정하지 않는다.

## 출력 검증과 직접 프레임 검사

- Release x64 빌드 통과. 네 edge 입력 형식의 L 셰이더 컴파일 통과. 기존 대조군 셰이더 14종과 ⑨ 네 입력 형식의 DXBC는 보존 소스와 일치했다.
- Bistro·Minecraft 각 240프레임에서 L/⑨ 최종 RGB 불일치 0. ⑥·⑨·④의 보존된 240프레임 대조군과도 RGB 불일치 0.
- 장면별 selective mode마다 43개의 진단 프레임: 실제 temporal coverage와 샘플 수, 현재 raw RG, current spatial/velocity DDS, 비선택=current 조건을 확인했다. L/⑨ 선택 영역 차이 0.
- 실제 edge-pass VS와 viewport를 사용한 전체 화면 probe에서 point/Load velocity float bit 및 현재 texel 좌표 불일치 모두 0. 진단 모드 3개 × 43프레임 × 2장면을 검사했다.
- 두 장면의 F/L 원본 f131 전체 화면을 직접 열고, 이동 f130–135·이동→정지 f178–183·정지 f190–195의 연속 6프레임 ROI를 nearest 3배로 직접 비교했다. 원본의 밝기·색상은 보정하지 않았다.

Bistro 의자/얇은 경계 ROI `(1230,582)-(1358,670)`와 Minecraft 벽 경계 ROI `(956,524)-(1020,620)`에서 두 방식은 같았다. Minecraft 이동 구간의 가는 경계가 부분적으로 약해지거나 끊기는 모습과 Bistro 얇은 구조의 픽셀별 불연속은 양쪽에 남는다. 따라서 기존 ⑨의 얇은 구조 문제나 반짝임·고스팅을 해결한 결과가 아니다. 이번에는 CGVQM을 다시 돌리거나 새 품질 개선으로 해석하지 않았다.

[Bistro 이동 6프레임](inspection/bistro-moving-six-frames.png) · [Bistro 전환](inspection/bistro-transition-six-frames.png) · [Bistro 정지](inspection/bistro-still-six-frames.png)

[Minecraft 이동 6프레임](inspection/minecraft-moving-six-frames.png) · [Minecraft 전환](inspection/minecraft-transition-six-frames.png) · [Minecraft 정지](inspection/minecraft-still-six-frames.png)

동일 원본 f120–203의 [Bistro 60fps 영상](inspection/bistro-frames-120-203-60fps.mp4)과 [Minecraft 60fps 영상](inspection/minecraft-frames-120-203-60fps.mp4)도 제공한다. 각각 84프레임과 1/60초 PTS를 decode로 검증했다. 직접 검사한 것은 위 원본 PNG와 연속 프레임 sheet이며, 영상을 실제 재생 관찰했다고 주장하지 않는다. MP4는 손실 압축된 재생 자료이고 화소 동일성 검증에는 쓰지 않았다.

## 공식 문서 및 해석 한계

[Microsoft Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load)는 정수 texel/mip 접근, [SV_Position](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-semantics)은 pixel center 좌표를 정의한다. 이 계약으로 동일 현재 texel을 읽는 가설을 만들고 GPU probe로 확인했다. [NVIDIA shader 성능 지침](https://developer.nvidia.com/blog/advanced-api-performance-shaders/)은 texture/분기/레지스터 비용의 실제 측정을 강조하며 point sampling에도 빠른 경로가 있음을 설명한다. 어느 자료도 Load가 항상 빠르다고 보장하지 않는다.

동등성 범위는 이번 full-resolution, zero-origin viewport와 두 장면·해상도다. viewport offset, MSAA texture, 다른 GPU/driver의 속도는 검증하지 않았다. Camera/depth velocity를 사용하며 object motion 지원 실험이 아니다.

## 보존 자료

- `*-capture.json`: RGB hashes, trace/coverage 및 입력 probe 검증.
- `*-benchmark.json`, `*-profilebenchmark.json`: 원시 run 평균, 분포, 대응 control 변화율.
- `source-audit.json`: 기존/실험 셰이더 DXBC 및 소스 hash.
- `visual-inspection.json`, `inspection/`: 원본 위치, ROI, 실제 확인 범위와 보존한 비교 자료.
- `runs.json`, `raw/`: 실행 receipt, exe/shader/report hashes 및 원시 CSV.

초기 짧은 Test는 데모 및 분석기 모두 PASS였다. 상위 PowerShell 호출자가 PowerShell script 뒤에 native용 `$LASTEXITCODE`를 검사해 잘못된 후속 오류를 낸 것은 orchestration 문제로 구분했다. 같은 Test를 성공할 때까지 재실행하지 않았고, 이후 wrapper는 PowerShell 예외와 native 종료 코드를 구분했다. 본 Capture/Benchmark 결과는 별도로 모두 검증했다.
