# ⑤ 실제 history 혼합 비중 진단

수정된 ⑤ `0b4191407b340bdcaab207b7f8b3f1b872731b71`에서 직접 분기했다.
⑥ 진단 `d603d29`의 관측 코드와 분석 도구만 의존성으로 재사용했다.
⑤의 raw color 입력, first-pass final RG stencil, 지터 Off, native point sampling,
velocity-alpha 기반 0..0.5 weight 및 spatial-frame history를 유지한다.
공간 SMAA를 적용하는 ⑥ renderer는 가져오지 않았다.

기존 resolve가 실제 계산한 history weight를 진단용 R32_FLOAT MRT에 기록한다.
선택되지 않은 곳은 -1로 보존하고 선택된 곳만 0..0.5를 기록한다. 별도 알고리즘이나
선택 패스를 추가한 것이 아니다. capture에서만 MRT와 readback이 활성화되며
이번 실행 시간은 성능 결과로 사용하지 않는다.

같은 프레임의 current(raw)와 final을 PNG로 저장해 8-bit RGB 변화량을 계산한다.
정의는 채널별 절대 차이 중 최댓값이다. alpha 및 velocity probe를 사용한 CPU
보조 검사는 DXBC의 mul+mad 반올림을 반영한다. 경계 근처 texel은 이 보조 검사에서만
제외한다. 실제 GPU weight 시각화/통계에는 제외 픽셀이 없다.

독립 clean process로 Bistro/Minecraft를 각각 실행한다. 장면당 240-frame target 진단,
④ native control, target 진단 Off 반복을 비교한다. 정상 완료 run receipt와 분석 JSON이
실제 검증 결과다. 이전 corrected RGB, 기존 GPU coverage, 비선택 current 보존을 모두
검사한다. production 셰이더 6개는 직접 매크로와 엔진 virtual include 두 컴파일 경로에서
기준선 DXBC와 동일하다. compile 실패 시 창을 띄우지 않고 실패 종료하는 기존
`12f5d56`의 실행 도구 변경도 진단 의존성으로 포함한다.

재현 명령은 공통 `verify_history_contribution_shaders.py`, `build_baseline.py`,
`run_history_contribution.ps1 -Scene bistro|minecraft`,
`analyze_history_contribution.py --scene bistro|minecraft`다. 두 독립 브랜치의 검증 결과는
`create_history_contribution_media.py --raw-ref <검증 커밋> --spatial-ref d603d29`로 비교한다.
raw capture와 영상은 저장소에 넣지 않고 경로/hash를 기록한다.

Weight, RGB 변화, 반짝임 억제 효과는 별개다. 비중이 높아도 current/history가 같으면
색 변화가 없고, 변화가 존재해도 품질 개선을 뜻하지 않는다. 이번 진단에서는 jitter,
dilation, TSCMAA history filter·clipping·weight·feedback을 변경하지 않는다.
