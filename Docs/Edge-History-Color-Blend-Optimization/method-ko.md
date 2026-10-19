# ⑰ 출력 보존 최적화: 후보와 측정 방법

브랜치 `experiment/edge-history-color-blend-optimization`. 의존성: 출력 동일성이 검증된 ⑰ 코드 정리본
`d2a6315` (`tooling/edge-history-color-blend-cleanup`). 원래 ⑰ (`5bdd189`)은 비교 기준으로 남긴다.
새 알고리즘·품질 기능(후보 확장, dilation, Dual Filter, clipping/sampling/weight/jitter 변경, object motion,
Adaptive 결합)은 추가하지 않는다.

2026-10-19 사용자 지시 "성능측정까지 다 진행해줘"에 따라 출력 캡처와 후속 성능 campaign을 재개한다.
새 실행 파일/드라이버의 결과는 2026-10-17 중간 수치와 구분한다. runner의 `-WorktreeRoot`는
정리 전/후의 기존 실행 파일을 그 경로의 clean runner로 실행하고 해당 worktree에 receipt를 남긴다.
이 옵션으로 과거 worktree의 runner 수정본과 실행 파일을 덮어쓰지 않고 동일한 창 준비 조건을 적용한다.
실행 직전 GPU 상태와 GPU process 목록을 receipt에 보존한다.

## 후보 (모두 기본 Off, ⑰의 selected feedback 경로에만 적용, ④ 경로 불변)

| ID | 커밋 | 변경 | 출력 보존 근거 |
|---|---|---|---|
| O1 | `6b851df` | SMAA 전용 D24S8을 stencil만이 아니라 depth+stencil로 함께 clear | SMAA의 어떤 pass도 depth plane을 읽지 않는다(edge·weight·resolve는 depth Off, neighborhood는 ALWAYS) |
| O2 | `2827827` | feedback neighborhood pass를 depth/stencil Off state로 실행 | [Microsoft depth-stencil 안내](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-depth-stencil): DepthEnable FALSE는 depth test와 depth write를 막는다. 쓰인 depth는 원래 읽히지 않는다 |
| O3 | `d85db5e` | visible render-target slot을 unbind하고 next history를 앱이 직접 표시 | ⑰의 visible RGB와 next-history RGB는 모든 픽셀에서 같다. 같은 shader(DXBC 동일)가 slot 0만 비운 채 실행된다. [OMSetRenderTargets](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-omsetrendertargets): 여덟 slot은 각각 설정되거나 비어 있을 수 있다 |

O3에서 바뀌는 것은 visible alpha뿐이다(resolve의 alpha lerp → current spatial alpha). PNG는 RGB만 저장하고 표시 swap chain도
alpha를 쓰지 않는다. neighborhood 쓰기는 3 → 2 full-screen target, resolve 쓰기는 2 → 1 target으로 줄고 앱의 기존 최종 복사
(`StretchRect`)는 scratch 대신 history texture를 읽는다.

O1의 속도 향상은 일차 자료로 보장되지 않는다. [NVIDIA clear 지침](https://developer.nvidia.com/blog/advanced-api-performance-clears)은
clear 묶음과 depth clear 값만 다루며, 결합 clear가 빠르다는 주장은 [제3자 포럼 글](https://community.khronos.org/t/color-vs-depthstencil-clear/58801)이다.
따라서 측정 가설로만 둔다.

처음 O3를 단일 target 전용 shader로 만들었을 때 FXC가 RGB 산술의 명령 순서와 register 배치를 바꿔 산술 동일성을 증명할 수 없었다.
그 방식은 폐기하고 shader를 바꾸지 않는 slot unbind 방식으로 바꿨다. 기존 14개 entry의 DXBC byte 동일성은
`Tools/SMAA/audit_color_blend_shaders.py`로 확인했다.

## 이전 기록으로 제외한 방식

- 지연 → 선행 이전 edge 조회: 이미 채택된 현재 구조.
- 2차 weight pass current-only gating, SV_StencilRef(장치 미지원), SV_Depth export(고정 비용 큼), velocity 정수 Load,
  resolve current/velocity 직접 Load: 이전 측정에서 개선 없음 또는 불가.
- edge union 사전 계산(velocity pass에서 이전 edge bit 생성): 서로 다른 full-screen draw의 texcoord와 half velocity 양자화가
  bit 단위로 같다는 보장이 없어 출력 동일성을 증명할 수 없으므로 이번에는 구현하지 않았다.

## 측정

- RTX 3060 Ti, DX11 Release x64, SMAA Ultra, 1920×1061, hidden/windowed, VSync Off, fixed 60 Hz timeline.
- 측정 전 GPU 유휴(P8)와 게임 프로세스 부재를 확인했다(`tmp/perf-gpu-log.txt`). 사용자가 2026-10-17 측정을 허용했다.
- 각 명령은 독립 clean process. 앞뒤 CMAA2 0개, 1,200초 timeout, Aggregate PASS를 확인한다.
- Profile(진단): pass별 GPU timer On, 300 warm-up + 2,400 × 3. 결과는 원인 위치 파악용이며 속도 결론이 아니다.
- Benchmark: PNG·query·readback·pass timer Off, 30초 precondition, 300 warm-up + 4,800 × 6, mode 순서 정/역 교차.
  같은 process 안에서 ④, ⑰(정리본 경로, 후보 Off), ⑰+O1, ⑰+O2, ⑰+O3를 측정한다.
- 변화율은 반복마다 같은 실행의 ④와 ⑰로 계산하고 평균한다. 95% 구간은 Student-t(df=5), 다중 비교 보정 없음.
  다른 실행의 절대 시간을 분모로 쓰지 않는다. 전체 AA(`SMAA` scope)와 WholeFrame을 구분한다.
- 정리 전/후 binary 비교는 Preservation harness로 ABBA(전·후·후·전) 순서로 따로 측정한다.
