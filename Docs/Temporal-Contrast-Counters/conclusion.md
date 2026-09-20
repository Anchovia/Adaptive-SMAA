# GPU 카운터로 확인한 temporal 대비 선택의 비용

**Minecraft에서는 선택 픽셀을 줄여도 GPU의 warp 단위 명령량은 줄지 않았다.** 같은 frame 90의 원본·기존 분기·ScalarWeight를 캡처해 실제 NVIDIA 카운터를 수집했다. 입력 texture가 모두 같다는 검증 후에도 기존 분기는 texture 요청을 줄이는 대신 warp 명령량이 늘었고, ScalarWeight는 texture 요청 절감 없이 명령량이 늘었다.

이는 이전의 장면별 성능 차이를 뒷받침하는 하드웨어 근거다. 다만 단일 pose의 capture replay 진단이며, 전체 시간의 모든 차이를 인과적으로 분해하거나 모든 최적화가 불가능하다고 증명한 결과는 아니다.

## 핵심 수치

원본 `O-T2X-R` 대비, 동일 temporal draw의 3회 replay 평균이다. Original spatial SMAA, camera/depth reprojection, 기존 paired jitter와 spatial-frame history를 유지했다.

| 장면 / 방식 | texture 요청 변화 | warp 명령 변화 | thread 명령 변화 | 명령당 활성 thread 평균 |
|---|---:|---:|---:|---:|
| Bistro 기존 분기 | −65.20% | −36.23% | −38.27% | 30.98 |
| Minecraft 기존 분기 | −24.68% | +12.28% | −0.12% | 28.46 |
| Bistro ScalarWeight | 약 0% | +35.71% | +35.71% | 약 32 |
| Minecraft ScalarWeight | 약 0% | +35.71% | +35.71% | 약 32 |

여기서 texture 요청은 `l1tex__texin_requests.sum`, warp/thread 명령은 각각 `smsp__inst_executed.sum` 및 `smsp__thread_inst_executed.sum`이다. 요청 수를 픽셀 수나 HLSL sample 호출 수로 동일시하지 않는다. 활성 thread 평균도 후보율이나 분기 효율 자체가 아니다.

### 왜 기존 분기는 Minecraft에서 느려질 수 있는가

후보가 아닌 픽셀의 후속 계산을 생략해도, 선택 판정은 필요하고 GPU는 warp 단위로 명령을 실행한다. 이번 Minecraft draw에서 thread별로 합산한 실제 명령은 원본과 거의 같았고, warp 단위 명령은 12.28% 많았다. 명령당 활성 thread 평균은 원본 약 32에서 28.46으로 낮아졌다. 따라서 “후보가 절반이면 계산도 절반”이라는 설명은 실제 실행량과 맞지 않는다.

반면 Bistro는 texture 요청과 두 명령 지표가 함께 크게 감소했다. 기존 실시간 결과에서 Bistro 분기는 빨랐고 Minecraft 분기는 느렸다는 관측과 방향이 일치한다. 이번 카운터 수치를 전체 경로 평균이나 이전 240-frame 평균 후보율에 직접 대입하지 않는다.

### ScalarWeight가 원본을 이기지 못한 이유에 대한 근거

ScalarWeight는 모든 픽셀에서 velocity/history를 읽으며 선택 계산을 더한다. 실제 texture 요청은 원본과 거의 같았고 warp 및 thread 명령량은 약 35.71% 늘었다. 이 방식이 기존 Minecraft 분기의 손해를 줄였다는 점과, 원본보다 빨라지는 근거를 확보하지 못했다는 점은 함께 성립한다. 명령량 +35.71%를 실행 시간 +35.71%로 해석하지 않는다.

## 대기 지표가 말해 주는 범위

세 방식 모두 L1TEX 연산 결과에 대한 의존성을 기다리는 `long_scoreboard` 지표가 컸다. Minecraft 평균은 원본 0.9009, 분기 0.8585, ScalarWeight 0.8831이었다. 이것은 활성 warp에 대한 대기 비율이며 전체 GPU 시간 중 메모리 병목의 점유율이 아니다.

분기의 `branch_resolving` 지표가 증가했지만 값 자체는 Minecraft 약 0.00649였다. 이를 근거로 “분기 주소 계산 자체가 전체 slowdown의 주원인”이라고 단정할 수 없다. 추가 명령, 활성 thread 분포, texture 의존 관계가 함께 달라졌다는 것까지 확인했다. 실제 NVIDIA SASS/명령별 stall attribution은 확보하지 못했으며 cache miss 또는 stall 하나의 기여율을 계산하지 않았다.

## 이번 작업의 판정

- 관리자 권한 조회와 DX11 per-draw NVIDIA 카운터 수집에 성공했다. 이전의 권한 차단 상태는 이번 관리자 실행에서 해소됐다.
- 두 장면×3 mode의 frame 90 capture, 각 draw 15개 카운터×3회 재생을 완료했다.
- current/history/velocity 입력의 byte hash와 SRV 형식이 장면별 세 mode에서 모두 일치했다. 두 선택 구현의 상수 버퍼와 threshold 0.01도 일치했다.
- 실제 temporal shader, 단일 draw event 및 2,037,120 PS invocations를 확인했다. 카운터 누락·비유한값·replay debug 오류가 없었다.
- HLSL·GPU 리소스 처리·기본 설정은 변경하지 않았다. 새 코드는 opt-in capture와 계측 도구뿐이다. RenderDoc이 주입되지 않은 일반 실행에 DLL을 로드하지 않는다.

**현재 선택식·출력·단일 DX11 temporal PS를 유지하며 검증한 구현들에서는 두 장면 모두 원본보다 빠른 공통 구현이 없다.** 카운터에서도 바로 제거할 수 있는 중복 요청이나 새로 검증된 무비용 경로는 발견하지 못했다. 따라서 근거 없이 분기 문법 교체를 반복하거나 다른 선택식·후보 확장을 속도 개선으로 포함하지 않는다. 새 최적화 변경은 적용하지 않았다.

이 결과는 속도 목표 미달과 부분 개선을 함께 설명하는 연구 근거다. [이전 독립 실행 비교](../Temporal-Contrast-Pair/conclusion.md)의 실시간 시간과 이번 replay counter를 구분해 사용한다. 품질 우위는 이번 작업에서 평가하지 않았다. 실행 순서에 따른 전체 시간 변동의 물리적 원인도 이번 단일-frame replay로 확정하지 않는다.

[전체 카운터 표](report.md), [검증 통계·출처·입력 hash](results.json), [공식 근거와 재현 절차](method.md).
