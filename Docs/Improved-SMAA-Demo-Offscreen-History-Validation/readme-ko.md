# 화면 밖 history 거부 검증

브랜치

- `validation/improved-smaa-demo-offscreen-history` (이 문서, `validation/improved-smaa-demo-translation-stability` 57910e0 위에 수정 커밋을 옮겨 왔다)
- `experiment/improved-smaa-demo-offscreen-history` b616dbc (검증 대상, 192a2ab에서 시작)
- `validation/improved-smaa-demo-translation-stability` 57910e0 (비교한 수정 전 캡처를 만든 브랜치)

수정 커밋 b616dbc를 4860746으로 옮겨 와 평행 이동 harness와 함께 빌드했다. 시간 측정은 하지 않았다.

## 확인한 것

| 항목 | 방법 | 결과 |
|---|---|---|
| Release x64 빌드 | MSBuild `CMAA2.sln`, Release x64 | 실험 브랜치와 이 브랜치 모두 성공. 경고는 바꾸지 않은 줄의 기존 경고뿐이다 |
| 셰이더 | FXC 10.0.26100.0, 데모와 같은 매크로로 192a2ab와 비교 | 116개 중 112개 같음. 바뀐 4개는 Cross5 resolve의 LOW, MEDIUM, HIGH, ULTRA다. 원본 SMAA 진입점 11개 × 4프리셋, Adaptive SMAA 11개 × 4프리셋, 나머지 선택 경로 6개 × 4프리셋은 같은 DXBC다 |
| 같은 입력인지 | Off 프레임과 정지(0번) On 프레임을 수정 전 캡처와 SHA-256 비교 | 일곱 경로 × 네 조건 모두 같았다. 카메라 경로와 입력이 같고 정지 상태에서는 수정이 아무것도 바꾸지 않는다 |
| 움직일 때의 차이 | 수정 후 On과 수정 전 On, 수정 전 캡처의 Off, SSRef, WeightDebug로 tde60 계산(`Tools/Validation/compare_offscreen_fix.py`) | 아래 표 |
| 실제 화면 | 줄무늬가 있던 곳을 nearest 8배로 연속 프레임 비교 | 아래 |

캡처는 `-translationCapture`의 `onoff`(Off와 On만)로 찍었다. 카메라, 프레임 시간 조건(fixed60, fixed300, fixedmean, recorded), 저장 구간은 평행 이동 안정성 검증과 같다. 실행마다 CMAA2 프로세스 0개, GPU P8, 60초 이상 입력 없음을 확인했고 끝난 뒤 남은 프로세스는 0개였다.

## 결과

tde60은 1/60초 떨어진 두 프레임 사이 변화 가운데 SSRef에 없는 변화의 평균이다(낮을수록 안정적). 가장자리 띠는 화면 가장자리 32화소(화소의 약 9%)다.

| 실행 | 조건 | Off 동일 | 정지 On 동일 | 바뀐 On 화소(가장자리 32px 비율) | 가장자리 띠 tde60 수정/이전 | 가장자리 띠 수정/Off | 선택 화소 tde60 수정/이전 | 전체 tde60 수정/이전 |
|---|---|---|---|---:|---:|---:|---:|---:|
| Minecraft 2.0 수직 | fixed60 | 예 | 예 | 84991 (51%) | -10.7% | +0.3% | -7.0% | -1.3% |
| Minecraft 2.0 수직 | fixed300 | 예 | 예 | 129759 (62%) | -8.7% | +2.3% | -3.5% | -0.9% |
| Minecraft 2.0 수직 | fixedmean | 예 | 예 | 218850 (61%) | -2.1% | -0.0% | -0.8% | -0.2% |
| Minecraft 2.0 수직 | recorded | 예 | 예 | 42462 (100%) | -0.7% | -2.9% | -0.3% | -0.1% |
| Minecraft 3.5 수직 | fixed60 | 예 | 예 | 55506 (67%) | -3.6% | -0.8% | -2.1% | -0.3% |
| Minecraft 3.5 수직 | fixed300 | 예 | 예 | 87870 (65%) | -10.3% | +0.7% | -8.0% | -1.1% |
| Minecraft 3.5 수직 | fixedmean | 예 | 예 | 156777 (66%) | -2.6% | +0.5% | -2.0% | -0.3% |
| Minecraft 3.5 수직 | recorded | 예 | 예 | 35276 (100%) | -0.9% | -0.6% | -0.7% | -0.1% |
| Minecraft 3.5 수평 | fixed60 | 예 | 예 | 105479 (85%) | -5.2% | +6.3% | -0.6% | -0.5% |
| Minecraft 3.5 수평 | fixed300 | 예 | 예 | 101138 (95%) | -4.0% | +3.2% | -0.5% | -0.3% |
| Minecraft 3.5 수평 | fixedmean | 예 | 예 | 19413 (71%) | -0.3% | +0.8% | -0.0% | -0.0% |
| Minecraft 3.5 수평 | recorded | 예 | 예 | 11713 (97%) | -0.2% | -2.8% | -0.0% | -0.0% |
| Minecraft 2.0 수평 | fixed60 | 예 | 예 | 40636 (87%) | -2.3% | -1.3% | -0.4% | -0.2% |
| Minecraft 2.0 수평 | fixed300 | 예 | 예 | 57588 (98%) | -2.3% | -3.1% | -0.3% | -0.2% |
| Minecraft 2.0 수평 | fixedmean | 예 | 예 | 11253 (99%) | -0.2% | -4.3% | -0.0% | -0.0% |
| Minecraft 2.0 수평 | recorded | 예 | 예 | 9666 (100%) | -0.2% | -5.6% | -0.0% | -0.0% |
| Minecraft 3.5 yaw | fixed60 | 예 | 예 | 784464 (52%) | -20.0% | -5.0% | -2.9% | -2.1% |
| Minecraft 3.5 yaw | fixed300 | 예 | 예 | 265460 (91%) | -5.1% | +11.4% | -0.6% | -0.4% |
| Minecraft 3.5 yaw | fixedmean | 예 | 예 | 242976 (100%) | -1.6% | -0.7% | -0.2% | -0.1% |
| Minecraft 3.5 yaw | recorded | 예 | 예 | 201668 (100%) | -1.3% | -3.0% | -0.1% | -0.1% |
| Bistro 수평 | fixed60 | 예 | 예 | 9608 (64%) | -0.9% | -2.2% | -0.1% | -0.0% |
| Bistro 수평 | fixed300 | 예 | 예 | 978 (94%) | -0.0% | -0.9% | -0.0% | -0.0% |
| Bistro 수평 | fixedmean | 예 | 예 | 1238 (90%) | -0.0% | -2.1% | -0.0% | -0.0% |
| Bistro 수평 | recorded | 예 | 예 | 757 (100%) | -0.0% | -2.5% | -0.0% | -0.0% |
| Bistro 수직 | fixed60 | 예 | 예 | 14685 (48%) | -0.6% | -0.7% | -0.1% | -0.0% |
| Bistro 수직 | fixed300 | 예 | 예 | 18963 (14%) | -0.1% | -1.3% | +0.0% | +0.0% |
| Bistro 수직 | fixedmean | 예 | 예 | 15578 (19%) | -0.0% | -1.3% | -0.0% | -0.0% |
| Bistro 수직 | recorded | 예 | 예 | 671 (100%) | -0.0% | -1.5% | -0.0% | -0.0% |

Minecraft에서 가장자리 띠의 흔들림은 fixed60에서 2~20%, fixed300에서 2~10%, 약 1 kHz(fixedmean, recorded)에서 0.2~2.6% 줄었다. 프레임당 이동이 클수록 한 프레임에 새로 들어오는 띠가 넓어 효과가 컸다. 가장자리 띠 밖의 tde60은 0.2% 안에서 같았다. 바로잡힌 값은 history를 타고 안쪽으로 옮겨 가므로 바뀐 화소는 띠 밖에도 있다(예: Minecraft 2.0 수직 fixed300에서 바뀐 화소의 38%). 28개 경우 어디서도 나빠지지 않았다(가장 큰 증가 Bistro 수직 fixed300 선택 화소 +0.02%). Bistro는 가장자리 문제가 원래 작아 변화도 작았다.

수정 후에도 가장자리 띠가 Off보다 흔들리는 경우가 남았다(Minecraft 3.5 yaw fixed300 +11.4%, 3.5 수평 fixed60 +6.3%). 띠 안에도 질감 경계가 있으므로 다른 원인인 Minecraft 질감 흐림의 몫으로 보인다. 이번 수정은 그 문제를 다루지 않는다.

## 실제 화면

`D:\SMAAResearchCaptures\c33\sheets\streak_before_after_x568_y0.png`(Minecraft 2.0 수직 fixed300, x=568 y=0 64×14, nearest 8배, 120~127프레임 연속)를 직접 열어 확인했다. 수정 전 On은 125~127프레임에 화면 위에서 들어오는 갈색 블록 안에 초록 세로 줄이 있었다. 수정 후 On에는 그 줄이 없고 Off, SSRef와 같은 모습이다. 120~124프레임은 네 줄이 모두 비슷했다. 같은 곳을 넓게(x=520 y=0 160×48, ×3) 잡은 120~150프레임 GIF는 `streak_before_after_x520_y0.gif`이고 그중 126프레임을 꺼내 같은 차이를 확인했다(`gif_frame_126.png`). 이 비교는 수정이 의도대로 동작하는지 본 것이며 화질 우열 판정은 아니다.

## 한계

- 평행 이동 안정성 검증과 같은 일곱 경로만 다시 찍었다. 실제 키 입력이나 마우스 회전, 다른 해상도는 시험하지 않았다.
- c28~c31 타임라인(flythrough) 캡처는 다시 찍지 않았다. 원본 SMAA와 Off 경로는 DXBC와 C++가 그대로이고 이번 실행의 Off 프레임도 같았다는 근거로 대신했다.
- Minecraft 질감 흐림은 그대로 남아 있다.

## 자료

- 이 폴더의 `analysis/*.json`(경로별 비교 결과), `runs.json`
- 캡처: `D:\SMAAResearchCaptures\c33\fix-*`(Git에 넣지 않음), 수정 전 캡처 `D:\SMAAResearchCaptures\c32\tr-*`, 시트와 GIF `D:\SMAAResearchCaptures\c33\sheets\`
