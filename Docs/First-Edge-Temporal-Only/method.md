# 구성 ⑤: Spatial 보정 없는 첫 edge 선택 temporal

## 독립 브랜치와 의존성

- `experiment/first-edge-temporal-only`는 검증된 공통 기준 `e14f122`에서 직접 분기했다.
- 비교군 ③과 current RGB/velocity-alpha 준비를 재사용하기 위해 구현 커밋 `7c2feeb`만
  `-x`로 가져왔다(현 브랜치 `043056c`). 이전 누적 selective 코드·결과 전체를 상속하지 않았다.
- `Docs/Temporal-Only-Control/method.md`는 가져온 ③의 원래 범위를 설명한다.
  이 브랜치의 현재 범위는 본 문서이며, ⑥ spatial SMAA 유지 구현은 별도 브랜치에서 진행한다.
- 기존 8-case 의미나 원본 SMAA 기준선을 변경하지 않는 진단 구성이다.

## 처리 구조

1. 원본 camera/depth velocity를 생성한다. Object velocity는 없다.
2. 원본 SMAA `edgesDetectionPass`를 같은 입력·preset·shader로 호출한다. RG edge target을
   clear 후 기록하며, 새 luma 후보식·non-dominant 제거·dilation은 없다.
3. ③과 같은 준비 draw로 장면 RGB를 그대로 저장하고 velocity 크기를 alpha에 pack한다.
   **Blending weight calculation과 spatial neighborhood 보정은 실행하지 않는다.**
4. 기존 temporal 단계에서 current를 읽고 첫 edge RG를 정수 texel `Load`한다.
   `any(RG>0)`이면 원본 T2X-R 수식, 아니면 current RGBA를 출력한다.
5. History에는 resolved output이 아닌 각 프레임의 준비 RGBA를 저장한다. 원본 T2X-R의
   point sampling, velocity-alpha weight 0..0.5, seed/reset, paired projection jitter를 유지한다.

비선택 출력은 **지터가 있는 raw current**이며 일반 AA-Off 또는 SMAA 1X가 아니다.
정지 떨림이 나오더라도 임의로 jitter를 끄지 않는다. Pattern-Off, 후보 확장과 ⑥은 별도 항목이다.

## 세 조건의 비용 분리

| ID | Edge 검출 | Resolve |
|---|---|---|
| ABL-TemporalOnly-R | 없음 | 전체 화면 원본 결합 |
| DIAG-TemporalOnly-EdgeDetect-R | 원본 첫 패스 | 전체 화면 원본 결합, mask 읽지 않음 |
| ABL-FirstEdge-TemporalOnly-R | 원본 첫 패스 | 해당 edge만 결합 |

첫 두 조건으로 검출의 추가 비용을, 뒤 두 조건으로 같은 검출 조건에서 선택 resolve의 영향을
비교한다. 선택 resolve 차이는 mask 접근·분기·history 생략의 합이며 순수 데이터 이동 시간은 아니다.
Velocity / edge clear+검출 / current 준비 / resolve / 전체 SMAA timestamp를 분리한다.
추가 timing command가 포함된 engineering 측정이며 GPU ISA·warp 효율·실제 DRAM transaction은 측정하지 않는다.

## 검증 순서

- Release x64 / DX11 / Ultra / 1920×1061, 기존 240-frame 경로(60정지/120이동/60정지), fixed 60Hz.
- 원본 O-T2X-R 및 ③을 기존 독립 capture와 240 frame RGB bridge한다.
- Detect-only의 출력이 ③과 같은지, selective 반복과 모든 frame index가 일치하는지 확인한다.
- ⑤의 매 frame에서 첫 edge RG와 current PNG를 저장한다. 선택 RGB=③ full temporal,
  비선택 RGB=current를 모든 pixel에서 비교한다. 비선택 current를 1X로 대체하지 않는다.
- 10개 대응 frame에서 원본 full SMAA의 실제 첫 edge RG와 별도 첫-pass RG를 정확히 비교한다.
  같은 probe의 input/prepared/velocity DDS는 ③/검출 control/⑤/반복 사이에서 비교한다.
- 후기 정지에서 연속 출력 변화와 lag-2 일치, mask 변화, 두 frame 모두 선택/비선택/전환한
  픽셀의 변화 기여를 분리한다. 선택 개수는 전체 240 frame과 정지/이동 구간을 구분한다.
- 이미지 저장 없는 독립 clean-process Smoke(240 frame) 후 Benchmark(300 warmup,
  4800 frame×4회 정/역 순서, 30초 precondition)를 장면별 실행한다. 숨김 창 engineering이다.
  정식 6-case 품질·CGVQM 결론 또는 visible FPS가 아니다.

## 공식 근거와 과거 결과

[Microsoft HLSL if/branch](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if),
[Texture Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load)를
확인하고 FXC 출력에서 edge Load와 early return 이후의 history/velocity sample을 검사한다.
소스·DXBC 검사는 실제 GPU 처리량 감소의 증거가 아니므로 실측을 분리한다.

기존 `experiment/temporal-first-edge-selective`의 원본 edge 재사용 및 output-mask 검증을 참고하되
그 브랜치의 지터 On current-spatial을 일반 1X로 해석한 결론은 재사용하지 않는다.
`0bc13ed`의 paired-pattern Off 안정화 결과도 유지하며, 이번에는 조건을 바꾸기 전에
실제 첫 edge와 jittered raw current의 불일치를 직접 확인한다.
