# Contrast-tier temporal candidate: 코드 재사용 조사 및 실험 설계

작성일: 2026-09-09. 기준 커밋: `3fdb7e0`.
상태: **설계 단계. 새 정책 구현·GPU 검증·품질/성능 측정은 하지 않았다.**

## 1. 조사 결론

기존 first-pass의 `finalDelta`를 temporal 후보 선별에도 사용할 수 있다.
이 값은 Original SMAA에도 이미 계산되고, Adaptive SMAA에서는 이를 3단계로
분류해 공간 탐색 길이를 결정한다. 따라서 새 정책을 Adaptive에만 묶을 필요가 없으며,
metadata texture를 temporal 단계에서 다시 읽는 구조도 필요하지 않다.

그러나 이 값이 temporal 안정화가 필요한 pixel을 판별한다는 근거는 아직 없다.
본 설계는 **기존 contrast 정보로 후보 선별 비용을 줄일 수 있는지 검증하는 독립 가설**이다.
공식 TSCMAA 후보식, 공식 SMAA temporal 확장 또는 검증된 최적 정책으로 표현하지 않는다.

## 2. 실제 코드 대응

|위치|현재 동작|새 실험에서의 용도|
|---|---|---|
|`SMAAWrapper.hlsl`, `DX10_SMAALumaEdgeDetectionIntegratedTemporalCandidatesPS`|luma/방향 차이와 finalDelta 계산, SMAA edge pruning, candidate 선별|기존 finalDelta와 pruning 이후 baseEdge를 그대로 사용|
|`SMAA.hlsl`, `SMAAEncodeEdgeOutput`|Adaptive에서 finalDelta를 0 / 0.5 / 1 metadata로 인코딩|동일 경계 0.1, 1/3을 진단 정책에 재사용|
|`SMAA.hlsl`, blending-weight pass|metadata에 따라 축 탐색 4/8/기존 최대, 대각선 3/절반/기존 최대|이번 후보 실험에서는 변경하지 않음|
|`SMAAWrapper.hlsl`, `TSCMAAIntegratedSelectCandidate`|Intel-family 정책에서 추가 대각선 3개 Load와 방향별 비교|새 정책 분기는 이 Load 전에 반환하도록 설계|
|`vaSMAAWrapper.h`, `CandidatePolicy`|AllBaseEdges / IntelFamilyNonDominant / ExperimentalLocalMeanMax3x3|기존 enum 값 보존, 별도 Experimental 정책 추가 예정|
|`vaSMAAWrapperDX11.cpp`, candidate constant 설정|정책 ID를 TSCMAACandidateParams.y로 전달|기존 전달 경로 재사용 가능|
|`CMAA2Sample.cpp`, 정책 이름/CLI override|현재 -1, 0, 1, 2 허용|새 ID의 명시적 이름/검증 및 진단 capture 필요|

파일은 모두 `Projects/CMAA2` 아래에 있다. 조사 시점의 주요 위치는
`SMAA/SMAAWrapper.hlsl:214`, `:256`, `SMAA/SMAA.hlsl:691`, `:1251`이다.
행 번호보다 함수 이름을 기준으로 이후 변경을 추적한다.
원본 참조는 로컬 브랜치가 아니라 `origin/baseline/original-smaa`를 읽었으며,
그 버전에도 finalDelta와 local-contrast edge pruning이 존재함을 확인했다.

## 3. finalDelta의 정확한 의미

현재 first-pass에서 다음과 같이 계산한다. C는 현재 pixel이고 L/T/R/B는
좌/상/우/하, LL/TT는 두 pixel 떨어진 좌/상이다. 아래 L(...)는 구현과 동일한 luma다.

```text
dx  = abs(L(C) - L(L))
dy  = abs(L(C) - L(T))
dr  = abs(L(C) - L(R))
db  = abs(L(C) - L(B))
dll = abs(L(L) - L(LL))
dtt = abs(L(T) - L(TT))
finalDelta = max(dx, dy, dr, db, dll, dtt)
```

이는 현재 edge 방향의 대비 하나가 아니라 **주변 여섯 밝기 차이의 최댓값**이다.
주변 강한 경계의 영향으로 tier가 높아질 수 있다. Gamma/RGB 및 raw-luma 입력 의미는
기존 경로를 그대로 사용하며 선형 휘도나 물리적인 조도 대비라고 바꿔 부르지 않는다.

SMAA는 threshold를 통과한 RG edge에 추가 local-contrast pruning을 적용한다.
새 정책도 pruning 이후 `baseEdge = any(edges > 0)`를 반드시 전제한다.
이미 discard된 pixel이나 검출되지 않은 얇은 선의 빈 부분을 이 정책만으로 복구할 수 없다.

기존 Adaptive 연구는 이 값을 이용해 **탐색 길이**를 줄였다.
새 가설은 이를 이용해 **temporal 처리 pixel 수**를 바꾼다. 같은 값을 쓰더라도
다른 목적의 알고리즘이며, 기존 Adaptive 결과가 새 정책의 품질 근거가 되지는 않는다.

## 4. 최소 후보 정책

기존 3개 enum ID는 보존하고 다음 세 Experimental ID를 추가하는 안으로 설계한다.
ID 3/4/5는 예정값이며 구현 시 기존 충돌 여부를 다시 확인한다.

|정책|후보 조건(항상 baseEdge와 AND)|역할|
|---|---|---|
|IntelFamilyNonDominant|기존 방향별 비교, threshold/removal 유지|현재 기준 정책|
|AllBaseEdges|true|모든 SMAA base pixel을 처리하는 coverage control|
|ExperimentalContrastHigh|finalDelta >= 1/3|높은 tier만 선택|
|ExperimentalContrastMediumHigh|finalDelta >= 0.1|중간·높은 tier 선택|
|ExperimentalContrastLow|finalDelta < 0.1|낮은 tier 제거의 손실을 확인하는 보완 진단|

원래 tier 경계는 low <0.1, medium [0.1,1/3), high >=1/3이다.
0.333 근삿값 대신 기존 코드의 `(1.0 / 3.0)` 표현과 경계 포함 규칙을 유지한다.
초기 실험에서 threshold sweep, 상위 50% 강제 선택, 프레임별 threshold 적응은 하지 않는다.
`High`가 최선이라는 가정도 하지 않는다.

의도한 개념 코드는 다음과 같다. 실제 HLSL에 아직 추가하지 않았다.

```text
baseEdge = any(prunedSMAAEdges > 0)
if experimental tier policy:
    candidate = baseEdge AND tierCondition(finalDelta)
else:
    candidate = baseEdge AND existingCandidateRule(...)
```

새 정책에서는 Intel-family removal과 추가 후보 threshold `1/22`를 적용하지 않는다.
SMAA base threshold/pruning은 계속 적용된다. 로그에는 Intel 파라미터가
해당 정책에서 비활성임을 표시해야 하며, 이를 동일한 공식 후보 조건이라고 부르면 안 된다.
기존 Intel 정책을 통과한 후보와 tier를 다시 AND하는 실험은 선별 비용을 보존하므로
이번 비용 대체 가설과 다르다. 첫 구현에 섞지 않는다.

## 5. 구현 비용과 금지 사항

계획한 경로는 first-pass의 지역 변수 finalDelta를 직접 전달/사용한다.
Original에 R8 metadata MRT를 새로 만들지 않으며, 기존 Adaptive metadata도 다시 Load하지 않는다.
새 full-screen pass, downsample, compact 형식 변경, history resource 변경은 필요하지 않다.
기존 compact/indirect와 resolve를 그대로 사용한다.

다만 '추가 texture 읽기 없는 설계'는 '추가 GPU 비용 0'이라는 뜻이 아니다.
정책 분기, register lifetime, 후보 수 변화의 비용은 측정해야 한다.
특히 같은 shader에 기존 Intel 분기도 남으므로 FXC에 Load 명령이 남을 수 있다.
단순 전체 instruction count가 아니라 실제 새 정책 분기에서 대각선 Load를 실행하지
않는지 disassembly의 control flow와 GPU 검증을 확인해야 한다.
후보가 많아지면 선별식이 싸져도 compact/resolve/전체 SMAA는 느려질 수 있다.

Integrated source에서만 새 정책을 지원한다. Legacy/Post-pass source와의 조합은
조용히 all-false로 처리하거나 luma를 재검출하지 말고 명시적으로 거부한다.
현재 integrated selector는 policy 0/1 이외에 false를 반환하므로 enum/CLI만 추가하는
불완전한 구현을 금지한다. 기존 정책, 기본 8-case 설정은 그대로 보존한다.

## 6. 검증 순서와 통과 조건

### 6.1 구현 정확성

1. 기존 enum 숫자·default·원본 SMAA spatial shader 결과 보존.
2. 신규 정책/source 조합의 CLI 검증, 정책 전환 시 history reset, 종료 시 override 복원.
3. RGB/raw 및 Original/Adaptive shader compile. 원래 spatial edge/metadata 출력 회귀 확인.
4. threshold 바로 아래/같음/바로 위 float32 경계 검사. 화면 가장자리, edge 없는 pixel 검사.
5. 필요할 때만 diagnostic float finalDelta를 readback해 CPU tier 분류와 GPU mask를 대조.
   진단 RT/readback은 성능 측정에서 제외한다. 캡처된 최종색으로 finalDelta를 역추정하지 않는다.
6. candidate mask가 base의 부분집합인지, High가 MediumHigh의 부분집합인지 확인.
   Low와 MediumHigh의 교집합은 공집합, 합집합은 AllBase와 일치해야 한다.
7. compact count=process count, 중복/범위 밖/overflow 0, 비후보=current spatial 검증.
8. 짧은 독립 반복 capture의 phase/hash와 기존 lifecycle/feedback 회귀 통과.

위 목록은 앞으로 할 검사이며 통과 결과가 아니다.

### 6.2 작은 품질 screening

첫 구현 gate는 **Original spatial + camera/depth reprojection On**으로 고정한다.
Document 설정의 jitter Off, Catmull-Rom 5-tap, YCoCg clipping, history weight 0.8,
ResolvedOutput feedback, CompactIndirect, expansion None을 동일하게 유지한다.
현재 -R은 camera/depth이며 object-motion 개선을 포함했다고 표현하지 않는다.

위 5개 후보 정책을 같은 pose/window에서 비교한다. 처음에는 Bistro/Minecraft의
기존 wide 결합 경로에서 central-motion 60 frame과 motion-to-still 30 frame을 사용한다.
단, 이전 긴 sequence와 비교할 때는 같은 초기 warm-up과 prefix pre-roll을 적용한다.
정지 첫 pose에서 바로 부분구간을 시작한 capture를 긴 timeline history와 동일하다고
취급하지 않는다. 이 조건을 지원하는 전용 capture가 필요하다.

O-1X와 O-T2X-R은 품질 해석 control이며 새 후보 정책과 다른 temporal kernel임을 명시한다.
동일 pose supersample spatial reference, 얇은 구조 ROI, temporal 변화/잔상 연속 영상,
history 영향 범위를 함께 확인한다. O-1X에 가까워진 것을 품질 향상으로 단정하지 않는다.
통과하면 San Miguel의 검증된 textured thin-geometry 경로로 확대한다.
절차적 풍차/얇은 선은 회귀 fixture일 뿐 실제 장면 품질 근거로 사용하지 않는다.

### 6.3 성능 및 채택

품질을 심하게 잃지 않는 정책만 visible, readback Off의 짝 비교로 확대한다.
동일 300 warm-up/4,800 frame/최소 3회, mode 순서 통제와 clean process를 적용한다.
후보 수·tier 비율 특성화는 별도 실행한다. SMAA total, spatial scope, compact/args,
resolve, WholeFrame을 함께 본다. 기존 timer가 spatial 묶음이면 edge 단독 시간으로
표기하지 않는다.

기존 Intel-family보다 작거나 비슷한 후보 수만으로 채택하지 않는다.
얇은 선 temporal 유지, 고스팅/flicker/정지 전환 품질과 실제 GPU 시간을 함께 판단한다.
품질 비교에서 후보 수 자체의 영향이 의심되면 후속 coverage-matched 대조를 설계하되,
초기 결과를 사후 threshold 조정으로 덮어쓰지 않는다.

## 7. 후속 범위

Original에서 독립 효과를 확인한 뒤 Adaptive spatial 결합, reprojection Off,
3×3/ARM 확장과의 interaction을 각각 분리한다. 최종 8-case ID를 새 정책 ID로 대체하지 않는다.
High가 저대비 thin edge를 버려 실패하거나 MediumHigh가 거의 AllBase라 비용을 늘리는
결과도 유효한 연구 결과로 보존한다.

다음 실제 작업은 신규 정책과 경계/mask 검증의 최소 구현이다.
이번 설계에서는 branch 생성, 렌더 코드 수정, benchmark 실행을 하지 않았다.
