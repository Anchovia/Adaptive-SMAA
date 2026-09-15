# 확보 소스 기반 sharpening × clipping 방식 분리 검증

기준 커밋: `d54c11abc323151b929a4c2c4e9167049a41069c`.
브랜치: `research/tscmaa-sharpen-segment-ablation`.

## 질문과 범위

앞선 signed-chroma/YCoCg 공간 교정은 이동→정지 일부를 개선했지만 이동 중
기존 document temporal kernel과의 큰 격차는 남았다. 이번에는 중심 표본 강조와
성분별 clamp/segment limiter 두 요인을 2×2로 분리한다. Intel 전체 구현의
재현이나 최종 8-case 결과가 아니라 Original 공간 SMAA에 적용한 중간 ablation이다.
원본 소스 미확보를 설명하는 AGENTS 앞부분은 8.7 이후 확보 기록으로 대체된 과거 상태다.

| 이름 | 중심 표본 sharpening | YCoCg history 제한 |
|---|---|---|
| Sharpen-Component | 0.263157904 | 성분별 clamp |
| NoSharpen-Component | 0 | 성분별 clamp |
| Sharpen-Segment | 0.263157904 | 현재색→history segment limiter |
| NoSharpen-Segment | 0 | 현재색→history segment limiter |

네 조합은 signed Co/Cg 및 YCoCg 공간 clipping을 고정한다. 첫 조합은 이전
SignedChroma-YCoCgClamp와 동일해야 한다. 새 compile switch는 모두 default 0이며
기존 Original/Adaptive, Standard/ET2X, R Off/On 기본값을 바꾸지 않는다.

## 통제 조건

- Original SMAA Ultra, `O-ET2X-R`의 source candidate/source temporal profile.
- source RGB 후보식, threshold 1/22, removal 0.5, first-edge-pass 통합,
  CompactIndirect, 확장 None, 후보 진단 readback Off(별도 mask 검사 제외).
- camera/depth reprojection On, object velocity Off, jitter/paired pattern Off.
- 원본 5-fetch, 검은 border sampling, UNORM 색 처리, history weight 0.789473712,
  square/sqrt 혼합, R8 저장, ResolvedOutput feedback 및 lifecycle 유지.
- 8개 주변 표본, 평균±표준편차, Y 하한 0, variance 비음수 guard 유지.
  document kernel의 관측 min/max 교집합이나 Load/clamp 경계는 가져오지 않는다.

Segment anchor는 **강조 전 현재색**이다. 따라서 sharpening 요인은 통계 계산에만
영향을 준다. document 함수와 같은 방향별 최대 이동량 계산을 사용하되 source의
Co/Cg 축이 절반 크기이므로 해당 축 epsilon도 1e-6에서 5e-7로 환산한다.
anchor가 box 밖이면 현재색을 그대로 반환하거나 box 밖 결과가 나올 수 있다.
이를 무조건적인 box 내부 투영으로 표현하지 않는다. 별도 anchor 보정은 이번 범위가 아니다.

## 검증과 측정 순서

1. 기본 및 교정 control의 Extract/Resolve DXBC 동일성, 네 조합 Extract 동일성.
2. 35×29 크기의 8개 production GPU fixture를 독립 2회 실행한다. 후보/샘플러 불변,
   유한값, CPU clipping 및 최종 R8 계산을 검증한다.
3. 초기 함수 검사에서 outside anchor와 거의 0인 방향의 부호 변경에 민감한 사례가
   발견되었다. CPU 이상적 bilinear와 GPU subtexel filtering 오차를 분리하기 위해
   GPU에서 기록한 history sample을 CPU clipping 입력으로 사용한다. 샘플러 자체 오차는
   별도 0.005 미만으로 검사하고, 이상적 sampler→clip의 합성 오차도 숨기지 않고 기록한다.
   box 불변식은 segment에서는 anchor가 box 안에 있을 때만 검사한다.
4. Bistro/Minecraft 각각 네 조합 12-frame final/mask 검사 후 480-frame 전체 capture.
   동일 첫 pose 60-frame warm-up, fixed 60Hz `flythrough-wide-yaw-360`, 1920×1017.
   후보 mask/비후보 유지, 기존 교정 control 960-frame RGB hash 및 독립 prefix 반복 확인.
5. 동일 supersample spatial-reference proxy에서 MAE/PSNR/temporal-delta residual,
   central 150–329와 transition 410–439의 공식 CGVQM-2, 대표 연속 영상을 비교한다.
   post-still 440–479도 별도 분석한다. reference는 절대 temporal/ghosting 정답이 아니다.
   CGVQM error-map 통계와 프레임별 수치는 저장하되 별도 heatmap 영상 인코딩은 생략한다.
   이 옵션은 모델·점수·통계 계산 이후의 영상 저장만 생략한다. 육안 비교 영상은 PNG에서 만든다.
6. 움직임 격차가 남으면 이 clipping 범위의 추가 탐색을 종료하고 기존 temporal kernel을
   핵심 후보로 유지한다. 품질상 채택 근거가 없으면 비용 본 측정을 확대하지 않는다.
   개선 후보가 있으면 PNG/readback Off, visible 상태, 300 warm-up/4800 frame의
   3개 독립 pair로 전체 AA와 세부 비용을 비교한다. 후보 수나 instruction slots만으로
   속도 이득을 주장하지 않는다.

각 CMAA2 명령은 clean runner로 새 프로세스에서 실행하며 timeout은 600초다.
실행 전후 잔류 프로세스 0, 완성된 결과 CSV를 확인하고 실패/부분 결과는 제외한다.
CGVQM과 CMAA2는 동시에 실행하지 않는다. startup scene은 임시 Bistro로 설정하고
각 runner 종료 시 shader와 사용자 설정 전체 bytes를 복원한다.

표준 및 document 대조군은 이전 검증 결과를 사용하되 같은 reference hash와 정확한
설정을 확인하고 historical control임을 명시한다. 새로 측정한 값으로 표현하지 않는다.

## 실행 중 확인한 기반 코드 결함

두 차례의 시작 단계 앱 종료를 조사해 DX11 concrete shader 소멸 전에 비동기 컴파일을
기다리지 않는 결함을 수정했다(`3e540f6`). 상세 근거와 한계는
`SMAA-DX11-Shader-Lifetime-Fix-ko.md`에 기록한다. 최종 gate의 short/mask/quality는
모두 수정 후 동일 실행파일에서 다시 수집하며, 수정 전 완료된 20개 명령의 자료는
별도 보존하고 새 자료와 픽셀 hash로 비교한다. 실패한 실행은 포함하지 않는다.
