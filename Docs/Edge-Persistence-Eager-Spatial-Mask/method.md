# ⑨ 선행 조회와 현재 edge spatial 처리의 결합 실험

사용자 승인: 2026-10-05. Branch: `experiment/edge-persistence-eager-spatial-mask`.
Direct base: 수정된 ⑥ `304f749`. 명시적 의존성: `e54f0db`의 SMAA renderer 6개 파일과
비대화형 셰이더 오류 처리 3개 파일. Application은 직접 기준선에서 새 harness 연결만 추가했다.
검증 도구의 통계/타임라인은 기존 도구에서 재사용하되 독립 4조건으로 구성했다.

| 조건 | 첫 패스 | 2차 weight 패스 | Temporal |
|---|---|---|---|
| F: 기존 ⑨ | 이전 raw edge/point velocity 선행 조회 | current+previous union | 같은 union |
| H: 구분 표시 대조군 | F + 현재 edge=1/기타=0 depth 출력 | 같은 union | 같은 union |
| J: 현재 edge만 spatial | H와 동일 | depth=1 및 union stencil | 같은 union |
| O: 원본 ④ | 원본 SMAA | 원본 SMAA | 원본 full-screen T2X-R |

H와 J는 같은 edge 셰이더와 상태를 사용한다. J만 기존 2차 pass의 depth equality 검사로
현재 edge를 한정한다. 표시에는 기존 SMAA 전용 DSV를 사용하고 scene depth는 바꾸지 않는다.
추가 draw/dispatch/copy는 없다. 내부 mode 12/13은 H/J이며 새로운 사용자 case 번호가 아니다.
F/H/J는 paired pattern Off, O는 On이다. F/H/J의 temporal 선택, UV/경계, raw RG,
spatial shader 수식, sampling/혼합, spatial-frame history와 camera/depth motion을 고정한다.

## 근거 및 가설의 한계

앞선 G 실험은 ⑧에서 현재 edge만 2차 처리했고, ⑨의 선행 조회와 결합하지 않았다.
2차 passing sample 감소와 최종 출력 보존은 확인했으나 전체 비용 개선은 충분하지 않았다.
이번에는 이미 측정된 ⑨를 기준으로 표시 비용 H−F, 실행 제한 효과 J−H,
실제 개선 J−F를 구분한다. 큰 성능 개선을 전제하지 않는다.

- [Microsoft depth/stencil 상태](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_depth_stencil_desc): depth comparison과 stencil comparison의 명시적 설정.
- [NVIDIA shader 성능 지침](https://developer.nvidia.com/blog/advanced-api-performance-shaders/): 하드웨어 depth/stencil 검사로 픽셀 실행을 제외할 수 있으나 pixel depth 출력 등은 Early-Z를 방해할 수 있다.
- [원본 SMAA](https://github.com/iryoku/smaa/blob/master/Demo/DX10/Shaders/SMAA.fx): 원래 2차 weight 처리의 stencil 이용 구조. 이전 edge 합집합은 본 연구의 adaptation이다.

위 문서는 기능과 측정 가설의 근거이며 이 GPU에서 속도 개선을 입증하는 자료가 아니다.
Microsoft/NVIDIA는 2026-10-05 재확인했다. 기존 장치가 미지원한 shader-specified stencil reference는 사용하지 않는다.

## 검증 및 측정

- Release x64 빌드. 네 입력 종류의 결합 셰이더 컴파일, 보존 F 및 기존 대조군 DXBC 일치.
- F/O의 양 장면 240-frame RGB는 보존된 `eef2ac6` 결과와 hash bridge. H/J의 최종 RGB는 F와 일치해야 한다.
- 장면별 selective condition마다 43개 진단 frame의 raw RG/current spatial/velocity DDS 및 실제 temporal coverage 확인. 비선택 출력은 current spatial 유지.
- GPU query에서 F/H의 2차 passing samples는 union 수, J는 current raw edge 수. Temporal passing samples는 셋 모두 union 수.
- 원본 전체 PNG, 이동 f130–135/전환 f178–183/정지 f190–195 연속 6프레임 ROI를 직접 확인. 출력 동일성은 기존 얇은 선 결함의 품질 개선을 뜻하지 않는다.
- Clean process/timeout/잔류 프로세스 0을 각 명령에 적용. Hidden, RTX 3060 Ti, DX11 Ultra, 1920×1061, VSync Off.
- Clean 성능: 30초 준비 + mode별 300 warm-up + 4,800프레임 × 3회, 순서 교차. PNG/query/readback 및 세부 spatial timer Off.
- 별도 진단 Profile: 960프레임 × 3회로 준비/첫 edge/2차 weight/3차 blending을 분리. Clean 절대값과 섞지 않는다.
- 최종 판단은 같은 실행 F 대비 J의 전체 AA 감소와 반복 방향. H/J 또는 2차 시간만의 감소로 성공이라 하지 않는다. 실패도 보존한다.
