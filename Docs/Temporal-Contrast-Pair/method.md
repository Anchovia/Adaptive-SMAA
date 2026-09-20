# 원본 T2X-R / ScalarWeight 독립 프로세스 짝 비교

## 측정 전 고정 조건

- A: `O-T2X-R`, B: `ABL-ScalarWeight-001-R` (threshold 0.01).
- Original spatial SMAA Ultra, camera/depth reprojection, paired jitter, spatial-frame history를 유지한다. Object motion 및 최종 8-case 측정이 아닌 engineering ablation이다.
- 선택식, 두 셰이더, 리소스 바인딩을 변경하지 않는다. ScalarWeight는 모든 픽셀에서 velocity/history를 읽고 비후보의 혼합 비중만 0으로 만든다.
- 장면마다 6개의 독립 프로세스, 프로세스마다 두 mode를 한 번씩 측정한다. AB/BA 각각 3회다. 프레임을 독립 반복 표본으로 간주하지 않는다.
- pair index 0..5에서 Bistro는 AB/BA 교대, Minecraft는 BA/AB 교대한다. 각 index에서 Bistro/Minecraft 실행 순서도 교대한다. 무작위 배정은 아니다.
- 모든 프로세스가 원본 O-T2X-R로 정적 t=2에서 30초 예열한다. 이후 mode마다 300프레임 warmup, 4,800프레임 측정한다. 기존 240-frame 카메라 주기와 frame 0 history/jitter reset은 유지한다.
- Hidden, Vsync Off, 1920×1061, 동일 실행파일. PNG 및 candidate readback 없음. 각 명령은 clean runner로 실행 전후 CMAA2 프로세스 0개를 확인한다. Timeout/미완료 자료는 제외하고 별도 기록한다.
- 양쪽 장면과 AB/BA의 240-frame smoke를 먼저 검증한다. 정식 측정 도중 빌드·품질 분석·다른 GPU 작업을 병행하지 않는다.

## 분석 기준

주 지표는 전체 SMAA GPU 시간이다. Resolve와 미변경 Spatial, WholeFrame 및 wall frame interval을 함께 기록한다. 각 프로세스의 B−A 평균 시간 차이 6개에 대해 평균, 표본 표준편차, paired t 95% 구간을 계산한다. AB/BA 그룹별 차이도 별도 제시해 순서 영향을 확인한다. 상대 변화는 평균 시간의 비율과 pair별 상대 변화의 평균을 구분한다.

paired t 구간은 `mean(d) ± t(0.975,5) × sd(d)/sqrt(6)`이다. [NIST paired comparison](https://www.itl.nist.gov/div898/handbook/prc/section3/prc312.htm)을 따른다. 작은 표본, 순차 실행, 같은 GPU·세션의 공통 변동 및 여러 보조 지표 비교의 한계가 있다. 독립 프로세스 재시작이 열·클럭 상태의 통계적 독립까지 보장하지 않는다.

임계값은 [NIST 표](https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm)의 소수 셋째 자리 값 `2.571`을 사용한다.

0을 포함하는 구간을 성능 동등성의 증명으로 해석하지 않는다. 사전 동등성 허용 폭은 정하지 않았으므로 통계적 동등성 검정을 주장하지 않는다. 이 gate는 이전 약 0.1% 차이의 일관성과 순서 민감도를 확인하는 것이며, 결과에 맞춰 반복 수나 성공 기준을 변경하지 않는다.

품질은 이전 Cost/Warp gate의 ScalarWeight 대 기존 대비 선택 출력 hash 일치 결과를 인용한다. 이번에는 렌더링 구현의 diff가 없음을 확인하며 신규 품질 우위나 원본 대비 동일 출력을 주장하지 않는다.

## 사전 smoke 실패 기록

최초 Bistro AB smoke `20260921_022133`은 보고 문구 작성 중 `0xc0000005`로 종료됐다. 예외 주소는 `strnlen`이고 덤프의 stack 주소 후보에 `vaStringTools::Format`이 있었다. 새로 넣은 단일 문자열 인자 Format 호출을 제거하고 고정 문자열 출력으로 바꿨다. 정식 unwind에 의한 전체 호출 경로 확정은 아니며, GPU 알고리즘 오류로 분류하지 않는다. 실패 로그와 덤프는 로컬에 보존하고 미완성 CSV는 성능 분석에서 제외한다. 수정 후 실행파일 하나로 양쪽 장면/순서의 smoke와 본 측정을 수행한다.
