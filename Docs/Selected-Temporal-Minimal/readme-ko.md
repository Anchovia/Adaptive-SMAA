# 선택적 temporal 경로 정리 브랜치

브랜치 `tooling/selected-temporal-minimal`은 `experiment/case19-velocity-edge-merge`에서 실험 스위치와 진단 코드를 걷어낸 구현이다. 남긴 경로는 ④ `O-T2X-R`, 선택 경로(`+NoVelocityAlpha`), 19번(`+NoVelocityAlpha+VelocityInEdge`) 세 가지다. `-R`은 계속 camera/depth reprojection만 뜻한다.

## 코드 변화량

기준은 `baseline/original-smaa`(ee0020d)의 `Projects/CMAA2/SMAA` 폴더다. 공백과 빈 줄 변경은 세지 않았다. 코드 줄은 추가 줄에서 주석과 빈 줄을 뺀 값이다.

| 구성 | 추가 | 삭제 | 추가 중 코드 줄 |
|---|---:|---:|---:|
| Adaptive SMAA (`main`) | 181 | 56 | 145 |
| ④ `baseline/smaa-t2x` | 226 | 43 | 194 |
| ⑱ `baseline/selected-temporal-case18` | 1,404 | 59 | 1,152 |
| 19번 `experiment/case19-velocity-edge-merge` | 1,470 | 60 | 1,209 |
| 이 브랜치 (④ + 선택 경로 + 19번) | 545 | 61 | 441 |

`SMAA.hlsl`은 이 브랜치에서도 변경이 없다. 19번에만 필요한 줄은 약 20줄이다. 렌더러 전체(테스트 하니스 147줄 포함)는 +750/-72다.

Adaptive는 기존 패스의 탐색 범위만 바꾸므로 새 패스나 history가 필요 없다. 이 경로는 ④의 history, velocity, resolve 기반(코드 194줄)이 먼저 있어야 하고, ④ 위에 선택 경로와 19번을 더한 양은 코드 247줄이다. Adaptive와 같은 양까지 줄이지는 못했다.

## 걷어낸 것

- 실험 스위치 16개와 경로에서 쓰지 않는 technique
- coverage, 쿼리, DDS 저장 진단 코드와 패스 프로파일 타이머
- edge 식 복사본 4벌. 이제 `#define discard`로 `SMAA.hlsl`의 식을 그대로 쓴다.
- 이전 경우의 셰이더 8개를 `SelectedTemporal.hlsl` 하나로 합쳤다. Catmull-Rom 파일만 라이선스 때문에 따로 둔다.
- 이전 경우의 검증 하니스 11개와 옛 V0/V1/V2 캡처 도구

## 정리 전후 RGB 비교

정리 전 실행 파일(0217183E…)의 캡처와 이 브랜치 실행 파일(dbab5dc7…)의 캡처를 비교했다. 1920×1061, 두 장면, 3개 모드, 모드마다 240프레임의 복호화 RGB가 전부 같았다(`rgb-vs-precleanup.json`, 불일치 0프레임). 비교 도구는 `Tools/SMAA/verify_selected_temporal_minimal.py`다.

RGB가 같으므로 화면 품질 판단은 정리 전과 같고, 19번과 ⑱의 차이도 그대로 남아 있다. 19번은 정리 후에도 ⑱과 RGB가 완전히 같지 않다.

## 측정하지 않은 것

정리 후 시간은 측정하지 않았다. 출력 슬롯 배치가 바뀌었으므로(neighborhood 3슬롯에서 2슬롯, resolve 2슬롯에서 1슬롯) 정리 전 시간을 이 브랜치의 값으로 쓰지 않는다. 하니스의 Smoke와 Benchmark는 그대로 있고, 패스별 Profile 단계는 뺐다.

원본 SMAA가 지원하던 HLSL3/4, GLSL에는 이 경로가 없다(SM5 전용). GPU도 RTX 3060 Ti 한 대에서만 확인했다.
