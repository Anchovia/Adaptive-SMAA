# ⑪: 선택적 temporal RGB 누적 feedback

독립 브랜치 `experiment/edge-persistence-resolved-rgb-feedback`는 corrected ⑥ 공통
기준선 `304f749`에서 분기했다. 필요한 ⑨ raw-edge dependency와 ⑩ bilinear RGB
커밋만 `3992640`/`96c495a`로 가져왔다. 이전 깊이 export·속도 ablation이나 장시간
presentation 변경 전체를 상속하지 않았다.

⑩와의 독립 변수는 **다음 history의 RGB**다. ⑩는 직전 spatial frame, ⑪은 직전
visible temporal result를 저장한다. Alpha는 현재 spatial frame의 velocity metadata로
보존하여 다음 native adaptive weight 계산을 바꾸지 않는다. 이 alpha 처리는 SMAA
adaptation이며 Intel exact port가 아니다. 현재/직전 raw-edge union, Original spatial
Ultra, camera/depth reprojection, paired pattern Off, bilinear RGB/point alpha,
native adaptive history weight `0..0.5`, 비선택=current spatial을 유지한다.

Intel 문서 p.3~4는 resolved output feedback을 명시한다:
[TSCMAA code sample](https://www.intel.com/content/dam/develop/external/us/en/documents/tscmaa-codesample-v1.pdf).
누적 결과의 재투영을 검증하는 가설이며 약0.79 weight, source clipping/5-fetch,
지터·후보 확장·object motion은 이 실험에 추가하지 않는다.

DX11은 같은 subresource를 같은 draw에서 SRV/RTV로 동시에 사용하지 않는다.
[Microsoft OMSetRenderTargets](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-omsetrendertargets)
규칙에 따라 현재 spatial 입력 texture를 별도 한 장 사용한다. 기존 3차 pass의 MRT를
spatial 입력/visible seed/next-history seed 세 target으로 연결하고, 기존 stencil temporal
draw는 visible/next-history를 함께 덮어쓴다. 비선택 next-history는 공간 결과를 유지한다.
추가 생산 draw나 fullscreen CopyResource는 없다. **추가 MRT 쓰기와 texture 비용은
실제 overhead**로 포함한다. 기존 shader entry와 ④·⑩의 자원 경로는 유지한다.

검증: FXC 실제 entry compile 및 기존 생산 DXBC byte 보존; 두 scene Test6에서 첫 seed와
frame3 명시적 reset; 240-frame capture에서 ④·⑩ 전체 decoded RGB hash bridge;
43 trace에서 raw/current/velocity/edge/coverage/weight 입력 동일성, 비선택=current,
⑪ next-history RGB=visible PNG, alpha=current spatial, 연속 trace의 previous=직전 next-history.
캡처-only DDS·coverage·weight·query는 timing에서 비활성이다.

성능: 두 scene 각각 새 clean process, hidden DX11 Release x64, RTX3060Ti,1920×1061,
VSync Off. ⑩/⑪/④를 forward/reverse로300 warmup+4,800 frames×6 반복하며240-frame
timeline 경계마다 동일 reset을 적용한다. 전체 AA와 spatial/camera/resolve를 분리하고
동일 run ④ 및⑩ 대비 변화율을 계산한다. 반복은 한 process의 반복이며 독립 session으로
표현하지 않는다. 같은 binary smoke를 먼저 완료한다.

품질: 같은240 frames의 보존 supersample **spatial proxy**와 ROI RGB MAE/PSNR,
시간 차분·얇은 선 대비를 보조 분석한다. CGVQM은 실행한 경우에만 별도로 보고한다.
전체 무손실 frame, nearest2× thin-line ROI의 moving130–135,transition178–183,
still190–195를 직접 열고 선 단절·출현/소멸·잔상·흐림을 검사한다. 긴720-frame 경로도
presentation 자료로 제공하되 새품질 reference로 사용하지 않는다. 사용자 검토 전
품질 성공이나 기본 채택으로 판정하지 않는다.
