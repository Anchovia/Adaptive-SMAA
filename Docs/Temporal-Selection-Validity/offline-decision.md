# GPU 최소 구현으로 넘기는 조건

700개 selector/basis/pose 행을 검사했다. 모든 고정 threshold와 두 장면의 결과를
offline-tables.md 및 offline.json에 보존한다. 낮은 절대 문턱에서 큰 기여를 결합하는
방향만 선행 검증을 통과시킨다.

중요한 한계: 0.00025는 sRGB8에서 가능한 최소 인접 linear 간격(약 0.0003035)보다 작다.
따라서 PNG proxy에서는 current/full의 어떤 RGB 채널이라도 다르면 선택된다.
이 조건의 full-output 동일성과 정지 변화 0은 양자화에 따른 자명한 결과다.
이를 실시간 selector의 정지 안정화 또는 실제 선택률 증거로 채택하지 않는다.

0.0005 absolute-large는 Bistro에서도 full 출력을 무조건 복제하지 않는다.
validation 정지 pair에서 기존 paired 선택의 RGB 변화 0.733370→0.271927,
Minecraft 0.229097→0.000125였다. Native 입력에서도 1.287832→0.315960,
0.580355→0.000107로 개선 가능성이 있다. 이 값은 CPU PNG 근사이지 GPU 결과가 아니다.
큰 차이를 거부하는 small 조건은 특히 Minecraft 정지 변화가 커져 진행하지 않는다.
relative는 추가 brightness 계산과 proxy 해석이 필요하므로 이번 최소 구현에서 제외한다.

다음 GPU 조건을 고정한다:

`impact = originalWeight * max(abs(current.rgb - reprojectedHistory.rgb))`

`impact >= 0.0005`인 픽셀만 원래 weight로 결합한다. 공간 대비의 미분을 제거하며,
current/history/velocity 읽기는 그대로 수행한다. 같은 조건을 Native Point와 paired Linear
입력에 각각 적용해 필터 효과와 선택식 효과를 분리한다. shader threshold는 linear RGB다.
point/paired 각각의 full 대조군, 이전 paired 선택과 actual GPU mask를 비교한다.

앞선 정지에서 current/history가 교환되고 weight가 같은 경우 이 식은 대칭이다.
실제 움직임, 화면 밖 좌표 또는 disocclusion에 대한 올바른 history 판정이라는 뜻은 아니다.
원본 T2X-R보다 품질이 좋아졌다는 주장은 아직 하지 않는다.

HLSL 비교/보간/LOD0의 의미는 Microsoft의
[step](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-step),
[lerp](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-lerp),
[SampleLevel](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel)
문서로 확인했다. 선택식은 본 연구의 가설이며 공식 TSCMAA/권장 TAA 공식이라고 부르지 않는다.
