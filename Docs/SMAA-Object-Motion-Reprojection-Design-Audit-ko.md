# SMAA Object-Motion Reprojection 설계 감사

작성일: 2026-08-27
대상 브랜치: `codex/object-motion-reprojection-audit`

## 1. 감사 목적

현재 `O-T2X-R`, `O-ET2X-R`, `A-T2X-R`, `A-ET2X-R`은 depth와 현재·이전
camera matrix를 이용한 **camera-motion reprojection**만 지원한다. 카메라가 고정된
상태에서 물체만 움직이면 현재 픽셀의 정확한 이전 위치를 계산하지 못한다.

이번 감사의 목적은 다음과 같다.

1. 현재 구현이 실제로 camera motion만 처리하는지 코드 수준에서 다시 확인한다.
2. CMAA2 renderer가 rigid object의 현재·이전 transform을 전달할 수 있는지 확인한다.
3. 원본 SMAA, 원본 demo와 Adaptive SMAA 경로를 대규모로 변경하지 않는 최소 구현을
   결정한다.
4. object velocity와 disocclusion rejection을 한 번에 섞지 않고 단계별로 검증할
   프로토콜을 정한다.
5. 기존 8-case 결과의 의미를 조용히 바꾸지 않도록 mode와 결과 분류 원칙을 정한다.

이번 문서는 **구현 전 설계 감사**다. Object motion vector 구현이나 품질·성능 결과를
완료했다고 뜻하지 않는다.

---

## 2. 1차 근거와 적용 범위

### 2.1 공식 SMAA source에서 확인되는 내용

`Projects/CMAA2/SMAA/SMAA.hlsl`의 공식 SMAA 주석과 resolve에는 다음이 명시돼 있다.

- Temporal reprojection에는 velocity buffer가 필요하다.
- 정적 geometry에는 이전 depth buffer가 대안이 될 수 있다.
- moving object의 ghosting을 줄이려면 reprojection만으로 부족할 수 있어 현재·이전
  sample의 velocity 차이로 history weight를 감쇠한다.
- 공식 resolve는 velocity를 반대로 적용해 현재 UV에서 previous UV를 찾는다.

현재 wrapper의 저장 convention은 다음과 같다.

```text
velocity = currentUV - previousUV
historyUV = currentUV - velocity
```

공식 `SMAAResolvePS`는 같은 의미로 `previousColorTex`를 sample한다.

### 2.2 Intel TSCMAA와 이번 확장의 관계

Intel 공개 TSCMAA 문서는 depth와 현재·이전 view/projection을 이용한 history
reprojection, candidate-only processing, Catmull-Rom 계열 sampling과 YCoCg clipping을
설명한다. 현재 연구는 이를 SMAA에 적용한 document-based adaptation이다.

Object motion 지원은 유실된 Intel sample source를 복원한 것이 아니다. 이번 프로젝트의
renderer에 rigid-object velocity를 추가해 history coordinate의 정확도를 높이는
**별도 engine integration**이다.

---

## 3. 현재 camera-motion velocity 경로

### 3.1 상수와 shader

`Projects/CMAA2/SMAA/SMAAWrapper.hlsl`의 `SMAAReprojectionConstants`에는 다음 세
camera matrix가 있다.

- `CurrentViewProjInv`
- `CurrentUnjitteredViewProj`
- `PreviousViewProj`

Object transform 또는 previous object transform은 없다.

`DX10_SMAAGenerateCameraVelocityPS`는 current depth에서 world position을 복원한 뒤,
같은 world position을 현재 unjittered camera와 이전 camera에 각각 투영한다.

```text
current depth
→ current world position 복원
→ current unjittered camera에 투영
→ previous camera에 같은 world position 투영
→ currentUV - previousUV 저장
```

같은 world position을 두 camera에 투영하므로 정적 geometry의 camera motion은 처리하지만,
물체 자체의 transform 변화는 포함하지 않는다.

### 3.2 wrapper lifecycle

`Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp`는 다음 순서로 동작한다.

1. current jittered/inverse matrix와 current unjittered matrix 계산
2. wrapper에 저장된 previous camera matrix 사용
3. full-screen camera velocity pass 실행
4. Standard 또는 Edge-selective temporal resolve 실행
5. current unjittered matrix를 다음 frame의 previous matrix로 저장

History reset 시 previous camera matrix도 무효화되므로 첫 temporal frame은 current
matrix를 previous로 사용한다.

### 3.3 Standard T2X와 ET2X의 차이

Standard `-R` mode는 공식 `SMAAResolvePS`를 사용한다. Spatial pass에서 velocity
magnitude를 alpha에 저장하고, resolve에서 현재·이전 alpha 차이가 크면 history weight를
줄인다.

현재 ET2X `-R` compute resolve는 다음과 같다.

```text
historyUV = currentUV - velocity
화면 밖 history 거부
Catmull-Rom 또는 bilinear history sampling
선택적 YCoCg variance clipping
고정 history weight 0.8
```

ET2X는 현재 velocity magnitude 차이에 따른 별도 history-weight 감쇠를 사용하지 않는다.
따라서 object velocity가 추가돼도 disocclusion validity가 자동으로 완전히 해결되는 것은
아니다.

---

## 4. Renderer와 scene transform 감사

## 4.1 Scene object

`Modules/Scene/vaScene.h`의 `vaSceneObject`에는 다음 값이 있다.

- current local transform: `m_localTransform`
- current computed world transform: `m_computedWorldTransform`
- current scene tick index: `m_lastSceneTickIndex`

Previous local/world transform 또는 motion validity는 없다.

`Modules/Scene/vaScene.cpp`의 `TickRecursive`는 매 tick마다 current world transform을
덮어쓴다. 기존 값을 보존하지 않는다.

### 판정

현재 scene graph만으로는 object velocity를 계산할 수 없다. 이전 computed world
transform을 명시적으로 한 frame 보존해야 한다.

## 4.2 Render selection과 draw list

`vaSceneObject::SelectForRendering`은 current world transform만
`vaRenderMeshDrawList::Entry`에 넣는다.

현재 `Entry`가 보유하는 transform 관련 값은 다음 하나뿐이다.

```text
Transform = current world transform
```

Scene object는 persistent UID를 갖지 않고 draw list는 distance에 따라 정렬될 수 있다.
따라서 draw-list index 또는 정렬 순서로 이전 transform cache를 대응시키는 방식은
안전하지 않다.

### 판정

Scene object에서 계산한 `PreviousTransform`과 validity를 current transform과 함께 draw
entry에 직접 전달하는 방식이 가장 단순하고 결정적이다.

## 4.3 Mesh와 skinning

`vaRenderMesh::StandardVertexAnimationPart` 선언은 남아 있지만 실제 standard vertex
buffer, material shader와 draw path에는 bone index/weight buffer, current/previous bone
palette 또는 skinning shader가 연결돼 있지 않다. Assimp importer의
`aiProcess_LimitBoneWeights` flag만 존재하며 실제 renderer skinning 지원으로 이어지지
않는다.

### 판정

첫 구현 범위는 **rigid object transform motion**으로 제한한다. Skinned/deforming mesh
velocity를 지원한다고 표현하면 안 된다.

## 4.4 Opaque, alpha-tested, transparent coverage

일반 scene은 depth pre-pass 또는 forward opaque pass에서 current depth를 완성한다.
Alpha-tested material도 visible fragment만 depth에 남는다.

Object velocity를 별도 geometry pass로 출력할 때 current depth를 `equal` 조건으로
재사용하면 다음 장점이 있다.

- 현재 visible opaque surface만 velocity를 덮어쓴다.
- alpha-test hole은 current depth와 일치하지 않아 velocity를 쓰지 않는다.
- occluded geometry는 current depth와 일치하지 않아 제외된다.
- material별 alpha-test shader를 velocity pass에서 다시 구현하지 않아도 현재 visibility
  coverage를 재사용할 수 있다.

Transparent mesh는 current opaque depth를 쓰지 않으며 별도 blending order가 필요하므로
첫 구현에서 제외한다.

---

## 5. 렌더 시점과 기존 경로 보존 가능성

`Projects/CMAA2/CMAA2Sample.cpp`의 frame 순서는 다음과 같다.

```text
scene Tick
→ render selection 생성
→ depth/forward/transparent rendering
→ tonemap/luma
→ SMAA Draw
→ render selection Reset
```

따라서 SMAA가 실행될 때 current draw list와 current depth는 아직 유효하다.

기존 full-screen camera velocity를 먼저 생성하고, 같은 R16G16 velocity target에 움직인
rigid object만 depth-equal geometry pass로 덮어쓰는 구조가 가능하다.

```text
camera/depth full-screen velocity
→ moving rigid-object velocity overwrite
→ 기존 SMAA spatial/temporal resolve
```

Static object는 full-screen camera velocity가 이미 정확하므로 다시 그릴 필요가 없다.
`CurrentTransform != PreviousTransform`인 entry만 object pass에 제출하면 추가 geometry
비용을 움직이는 물체로 제한할 수 있다.

이 방식은 원본 SMAA edge/blending shader, Adaptive spatial search와 candidate extraction을
수정하지 않는다. 변경 범위는 previous transform 전달, velocity 생성과 wrapper 입력
연결에 한정할 수 있다.

---

## 6. 구현 대안 비교

| 대안 | 설명 | 장점 | 문제 | 판정 |
|---|---|---|---|---|
| A. Main pass MRT | color/depth rendering 때 velocity도 동시에 출력 | coverage와 transform이 가장 정확함 | 모든 material shader와 render target 구성을 변경, 원본 demo 침범 큼 | 보류 |
| B. App-owned external velocity | sample이 camera+object velocity를 만들고 wrapper에 전달 | SMAA wrapper를 일반 input consumer로 유지 | camera matrix/history lifecycle 중복, 새 renderer module 필요 | 장기적으로 깔끔하나 1차 구현에는 큼 |
| C. Wrapper 내 object overwrite | wrapper의 기존 camera velocity 뒤에 draw list로 moving object를 depth-equal 출력 | 기존 lifecycle과 texture 재사용, 변경 범위 작음 | wrapper가 mesh draw list를 optional input으로 알게 됨 | **1차 권장** |
| D. Previous depth만 사용 | 이전 depth에서 static history coordinate 계산 | static geometry에는 공식 SMAA 주석과 부합 | 독립 object transform을 계산하지 못함 | object motion 해결책 아님 |

### 권장 결정

첫 구현은 **C. Wrapper 내 moving rigid-object velocity overwrite**로 한다.

다만 기능을 wrapper 기본값으로 즉시 켜지 않고 독립 toggle로 추가한다. 기능 검증과
회귀 검증 후 최종 `-R` 정의를 변경할지 별도로 결정한다.

---

## 7. 권장 데이터 구조

## 7.1 Scene object

추가 예정 값:

```text
m_previousComputedWorldTransform
m_previousComputedWorldTransformValid
```

Tick 규칙:

1. 첫 valid scene tick에서는 current transform을 계산하고 previous를 current와 같게
   초기화한다.
2. 이후 tick에서는 기존 current를 previous로 보존한 뒤 새 current를 계산한다.
3. Parent가 움직이면 child의 computed world transform도 달라지므로 rigid hierarchy
   motion이 자동으로 포함된다.
4. Scene 생성·전환에서는 previous validity를 초기화한다.

첫 frame에는 temporal history 자체가 seed 상태이므로 artificial velocity를 만들지 않는다.

## 7.2 Draw entry

추가 예정 값:

```text
Transform
PreviousTransform
PreviousTransformValid
```

Draw-list 정렬 이후에도 current와 previous가 같은 entry에 들어 있으므로 별도 object ID
lookup이 필요 없다.

## 7.3 Object velocity constants

Moving entry마다 다음 clip transform을 계산한다.

```text
CurrentObjectToUnjitteredClip = CurrentWorld * CurrentUnjitteredViewProj
PreviousObjectToClip          = PreviousWorld * PreviousViewProj
```

Raster coverage는 current jittered camera와 기존 mesh depth-offset convention을 따라 current
depth와 일치시켜야 한다. Velocity 값은 다음과 같다.

```text
currentUV  = project(CurrentObjectToUnjitteredClip, localPosition)
previousUV = project(PreviousObjectToClip, localPosition)
velocity   = currentUV - previousUV
```

현재 renderer vertex shader에는 view-space depth offset이 있으므로 object velocity VS의
`SV_Position`은 기존 current raster position 계산을 그대로 재현해야 한다. Velocity용
current/previous UV는 원래 local position의 두 transform으로 계산한다. 이 차이는 GPU
reference test에서 허용 오차를 기록한다.

---

## 8. 8-case 의미 보존 규칙

현재 `ReprojectionMode::CameraDepthMatrices`와 기존 `-R` 결과는 camera-motion
reprojection을 뜻한다. Object velocity를 기본 On으로 바로 합치면 이전 결과와 새 결과가
같은 ID인데 다른 알고리즘이 되는 문제가 생긴다.

따라서 다음 순서를 사용한다.

### 8.1 Engineering 단계

새 독립 설정을 둔다.

```text
ObjectMotionReprojection::Off
ObjectMotionReprojection::RigidTransforms
```

또는 같은 의미의 diagnostic override를 둔다. 기본값은 `Off`다.

기존 8 mode와 capture를 object toggle Off로 실행했을 때 이전 hash와 같아야 한다.

### 8.2 검증 후 연구 정의 결정

Rigid object velocity가 정확하고 object-motion 결과가 개선되면 다음 중 하나를 명시적으로
선택한다.

1. 최종 `-R`을 camera + rigid object velocity로 재정의하고 AGENTS.md·UI·보고서를
   갱신한 뒤 모든 `-R` formal 결과를 다시 측정한다.
2. 기존 `-R`은 camera-only로 유지하고 object-motion 지원을 별도 ablation으로 보고한다.

이 결정 전에는 새 object toggle 결과를 기존 8-case 최종 결과와 섞지 않는다.

---

## 9. Disocclusion은 별도 문제다

Object velocity는 현재 visible object pixel을 올바른 이전 위치로 보낸다. 하지만 새로
드러난 배경 pixel은 현재 background velocity를 사용해 이전 frame에서 foreground가 있던
위치를 sample할 수 있다.

즉 다음 두 문제는 분리해야 한다.

| 문제 | 필요한 정보 |
|---|---|
| moving object의 history coordinate 오정렬 | current/previous object transform velocity |
| 새로 드러난 영역의 stale history | previous depth 또는 surface/ID validity |

Standard SMAA resolve는 current/previous velocity magnitude 차이로 history weight를
감쇠해 일부 disocclusion을 완화할 수 있다. ET2X는 현재 고정 0.8 weight와 variance
clipping을 사용하므로 별도 validity가 더 중요할 수 있다.

### 후속 depth rejection 권장 구조

Object velocity가 먼저 통과한 뒤 별도 toggle로 다음을 구현한다.

1. Previous depth를 ping-pong history로 보존한다.
2. Current pixel의 예상 previous clip depth를 velocity 생성 단계에서 함께 출력한다.
3. `historyUV`의 실제 previous depth와 예상 previous depth를 비교한다.
4. 차이가 임계값보다 크면 history를 reject한다.
5. Threshold는 view-space 또는 상대 depth 기준으로 별도 sweep한다.

Depth rejection은 object velocity와 같은 커밋에 섞지 않는다.

---

## 10. 1차 구현 범위

### 포함

- rigid opaque object transform motion
- opaque alpha-tested surface의 current depth coverage 재사용
- camera + rigid object composite velocity
- current/previous transform lifecycle
- moving-entry-only geometry overwrite
- velocity debug view와 GPU/CPU reference test
- 기존 Standard T2X와 ET2X 양쪽에서 같은 velocity texture 사용
- object toggle Off일 때 기존 출력 byte-identical 회귀 검증

### 제외

- skinned mesh와 vertex deformation
- particle velocity
- transparent surface velocity
- material animation에 의한 apparent motion
- previous depth 기반 disocclusion rejection
- object ID/history ID rejection
- 최종 8-case 정의 자동 변경

제외 항목을 지원한다고 표현하지 않는다.

---

## 11. 검증 프로토콜

## 11.1 CPU transform lifecycle test

새 자동 test에서 다음을 확인한다.

- 첫 tick: previous=current 초기화, motion invalid
- 정지 object: 다음 tick에서 previous=current
- 알려진 translation: previous/current matrix와 이동량 일치
- 알려진 rotation: analytical previous/current matrix와 일치
- moving parent + static child: child world motion 포함
- scene 전환: previous validity reset
- draw-list 정렬 후에도 current/previous pair 보존

## 11.2 GPU object velocity test

기존 procedural stress scene은 논문용 실사 장면이 아니라 **engineering validation
fixture**로만 사용한다.

검증 대상:

- 고정 camera + 정지 background: velocity 약 0
- 고정 camera + moving occluder: X velocity 부호와 크기
- 고정 camera + rotating rotor: 회전 방향에 따른 pixel velocity 방향
- camera + object 동시 이동: composite velocity
- static object에서 object pass를 끈 camera fullscreen 결과와 일치
- moving object 밖의 velocity texture가 camera-only 결과와 byte 또는 tolerance 내 일치
- 모든 finite pixel에서 `historyUV=currentUV-velocity` convention 유지

## 11.3 기존 경로 회귀

Object toggle Off 상태에서 다음을 다시 실행한다.

- Release x64 build
- temporal lifecycle test
- existing camera velocity test
- history feedback test
- static stability test
- 8-mode 축소 capture hash comparison
- candidate/3×3 expansion smoke

원본 SMAA, Adaptive spatial path와 candidate mask는 object toggle Off에서 달라지면 안 된다.

## 11.4 품질 gate

첫 quality gate는 다음 다섯 출력을 같은 fixed 60 Hz object-motion/combined timeline에서
비교한다.

| 출력 | 의미 |
|---|---|
| `O-1X` | spatial control |
| `O-T2X-R camera-only` | 기존 Standard 기준선 |
| `O-T2X-R camera+rigid` | Standard + object velocity |
| `O-ET2X-R camera-only` | 기존 edge-selective 기준선 |
| `O-ET2X-R camera+rigid` | edge-selective + object velocity |

검증 지표:

- rotor/occluder ROI의 same-frame reference error
- motion-compensated temporal residual
- moving object trail
- disocclusion ROI
- edge strength와 temporal variation
- object velocity 적용 pixel 수

Procedural stress 결과는 correctness gate로 사용하고 논문 대표 장면 결론은 실제 textured
dynamic scene이 확보된 뒤 별도로 측정한다.

## 11.5 성능 gate

GPU timestamp를 최소 다음으로 분리한다.

- camera fullscreen velocity
- moving rigid-object velocity draw
- Standard temporal resolve 또는 ET2X candidate resolve
- 전체 SMAA
- WholeFrame

Object가 없는 장면에서는 object pass 제출 수가 0인지 확인한다. 움직이는 object 수와
triangle 수를 함께 기록해 비용을 해석한다.

---

## 12. 위험과 대응

| 위험 | 대응 |
|---|---|
| draw-list index로 object가 잘못 대응됨 | previous transform을 같은 entry에 직접 저장 |
| 첫 frame의 identity→current 가짜 motion | previous validity와 history seed 사용 |
| alpha-test hole에 velocity가 써짐 | current depth-equal coverage 재사용 |
| static geometry 전체 재렌더 비용 | transform이 실제로 바뀐 entry만 제출 |
| transparent/skinned object가 누락됨 | 1차 범위에서 명시적으로 제외 |
| object velocity만으로 disocclusion 해결 주장 | previous-depth rejection을 별도 단계로 유지 |
| 기존 `-R` 의미가 바뀜 | default Off engineering toggle과 명시적 재정의 gate 사용 |
| pause/deltaTime 0에서 previous transform이 오래됨 | fixed-time formal test 우선, 이후 zero-tick lifecycle 진단 추가 |
| 큰 teleport에서 잘못된 history | screen-out reject 확인 후 object-cut reset 정책을 후속 추가 |

---

## 13. 감사 결론

1. 현재 `-R` mode는 확인된 대로 camera/depth reprojection만 지원한다.
2. Renderer에는 previous object transform과 skinned velocity 지원이 없다.
3. 그러나 SMAA 실행 시 current draw list와 depth가 남아 있어, 기존 camera velocity 위에
   **움직인 rigid opaque object만 depth-equal로 덮어쓰는 최소 구현이 가능하다.**
4. 이 구현은 원본 SMAA edge/blending, Adaptive spatial search와 candidate expansion을
   직접 변경하지 않는다.
5. Object velocity는 moving surface의 history coordinate를 교정하지만 disocclusion
   validity를 완전히 해결하지 않는다. Previous-depth rejection은 후속 독립 단계다.
6. 기존 8-case 의미와 과거 결과를 보존하기 위해 object motion은 우선 default-Off
   engineering toggle로 구현해야 한다.
7. 기능·회귀·품질 gate를 통과한 뒤에만 최종 `-R`을 camera+rigid motion으로 재정의할지
   결정하고, 재정의하면 기존 `-R` formal 측정을 전부 다시 수행한다.

## 14. 다음 구현 순서

1. Previous rigid world transform lifecycle과 draw-entry 전달
2. Object-motion toggle 및 CLI override
3. Moving-entry-only depth-equal velocity overwrite shader/pass
4. CPU transform lifecycle test
5. GPU object velocity sign·magnitude·coverage test
6. Object toggle Off 기존 8-mode hash 회귀
7. `O-T2X-R`/`O-ET2X-R` camera-only vs camera+rigid quality gate
8. GPU 비용 측정
9. 결과에 따라 final `-R` 정의 결정
10. 필요한 경우 previous-depth disocclusion rejection 별도 구현
