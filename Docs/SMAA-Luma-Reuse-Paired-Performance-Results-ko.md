# Integrated luma 재사용: 전후 교차 성능 측정

작성일: 2026-09-09. 대상: first-pass axial luma 재사용만의 성능 효과.

## 1. 결론

중복 luma Load 8→3 최적화는 Minecraft에서 세 pair 모두 SMAA 시간을 줄였으며,
평균 감소는 1.33~2.11%였다. Bistro는 평균 0.24~0.68% 감소로 작고 Original 두 mode는
첫 pair에서 오히려 소폭 증가했다. 따라서 **장면 의존적인 작은 개선 신호**로 기록한다.
전체 프레임 성능의 일관된 개선이나 ET2X의 주요 병목 해소라고 주장하지 않는다.

미변경 Standard T2X를 기준으로 한 상대 비율도 모든 pair에서 낮아졌다.
그러나 독립 pair는 3개뿐이며, Original Minecraft를 포함한 다수의 raw 시간 차이
95% 구간이 0을 포함하므로 모든 case의 유의한 가속으로 일반화하지 않는다.

재사용 코드는 유지한다. 출력 보존 검증을 통과했고 불필요한 읽기를 제거했지만,
현재 ET2X는 여전히 대응 Standard T2X보다 느리다.

## 2. 통제 조건

- 동일 Release x64 실행파일, DX11, RTX 3060 Ti / Ryzen 5 5600.
- 1920×1017, Ultra, VSync Off, visible window; 앱 UI/PNG 저장/candidate readback Off.
- Bistro/Minecraft 각각 Original/Adaptive × Standard/Edge-selective × reprojection Off/On 8 mode.
- 각 실행: 300 warm-up, mode당 4,800 measurement, 내부 repeat 1.
- 버전당 독립 실행 3회: mode/scene/version당 14,400 timing sample.
- 총 12 clean process, 전체 460,800 measured mode-frame. 내부 validation 모두 PASS.
- variant 순서는 pair별 Before→After, After→Before, Before→After.
  각 variant 안의 장면 순서는 Bistro→Minecraft, 각 실행의 mode 순서는 정방향이다.
  기존 CSV에 mode 정/역 순회 설명이 있어도 이번 내부 repeat는 1이므로 역순 mode 순회는 없다.
- 실행 종료와 잔류 프로세스 0을 확인한 뒤 다음 실행을 시작했다.
- 동일 startTime 1.0 s와 기존 fixed 60 Hz flythrough. 짧은 600-frame 측정과는
  경로 범위가 다르므로 그 절대 ms와 이번 절대 ms를 직접 비교하지 않는다.

실행파일 SHA-256:
`5B2DDAC2E03C31C71BCCD8CA77776DF9E4A651C78054F0222C2BA4F2239F83E6`

전후 shader Git blob:

- Before: `2b6090f3ebeea0f2b70ac12cd9e3745820201c0c` (`0a699dd`의 wrapper).
- After: `71d151dd56e787665b667e467d94f1a452e24009` (`075fc7f` 이후 wrapper).

각 variant 전환 시 위 hash를 검사했다. 공통 실행파일에는 `e8f2258`의 캡처 준비 교정이
있지만 성능 benchmark class는 그 변경의 대상이 아니다. 임시 source 교체는 끝난 뒤
After로 복원했으며 실행파일 hash도 측정 전후 일치했다.
GPU clock/power를 강제로 고정한 실험은 아니며 전체 시스템 변동은 아래 control과 함께 해석한다.

## 3. SMAA total 결과

ms는 세 실행 평균, 변화율은 대응하는 세 pair의 `(After/Before-1)×100` 평균이다.
음수는 시간 감소다. 두 평균 ms의 비율과 pair 평균 변화율은 반올림 외에도 약간 다를 수 있다.

|Scene|Mode|Before ms|After ms|평균 변화|pair 1 / 2 / 3 변화 %|
|---|---|---:|---:|---:|---|
|Bistro|O-ET2X|0.307780|0.307033|-0.24%|+0.560 / -0.699 / -0.578|
|Bistro|O-ET2X-R|0.344244|0.342955|-0.37%|+0.028 / -0.643 / -0.505|
|Bistro|A-ET2X|0.275756|0.273865|-0.68%|-0.232 / -0.861 / -0.959|
|Bistro|A-ET2X-R|0.310888|0.309025|-0.60%|-0.308 / -0.920 / -0.566|
|Minecraft|O-ET2X|0.348267|0.342784|-1.57%|-0.560 / -2.143 / -2.013|
|Minecraft|O-ET2X-R|0.387991|0.382844|-1.33%|-0.476 / -1.722 / -1.778|
|Minecraft|A-ET2X|0.329972|0.322993|-2.11%|-1.205 / -2.749 / -2.386|
|Minecraft|A-ET2X-R|0.368961|0.361440|-2.04%|-1.332 / -2.542 / -2.239|

절대 감소량은 Bistro 약 0.00075~0.00189 ms, Minecraft 약 0.00515~0.00752 ms다.
수정된 integrated pass가 들어 있는 `SMAASpatial1X` scope는 Bistro 0.48~1.07%,
Minecraft 2.10~3.14% 감소했다. 이 scope는 단독 edge shader 시간이 아니라 spatial
단계 묶음이므로 edge pass만의 가속률로 부르면 안 된다.

## 4. Control과 불확실성

미변경 Standard의 SMAA 시간은 평균 Bistro +0.51~0.76%, Minecraft +0.30~0.54%로
증가했다. 이와 비교해 ET2X가 상대적으로 낮아진 방향은 다음 보조 비율에서도 나타난다.

```text
100 × [(After ET2X / After 대응 Standard) / (Before ET2X / Before 대응 Standard) - 1]
```

세 pair 평균은 Bistro -0.92~-1.42%, Minecraft -1.67~-2.55%이고 개별 pair도 모두
음수다. 이는 control drift를 고려하는 보조 진단이며, 시스템 변동을 완벽히 제거한
보정 성능이나 공식 가속률로 대신 쓰지 않는다.

추론 단위는 4,800개의 개별 GPU frame이 아니라 **독립 실행 pair 3개**다.
paired delta(ms)에 t(df=2) 기반 양측 95% 구간을 계산하면 다음과 같다.

|Scene|Mode|After−Before ms의 95% 구간|
|---|---|---|
|Bistro|O-ET2X|[-0.006049, +0.004556]|
|Bistro|O-ET2X-R|[-0.004332, +0.001753]|
|Bistro|A-ET2X|[-0.004610, +0.000829]|
|Bistro|A-ET2X-R|[-0.004257, +0.000532]|
|Minecraft|O-ET2X|[-0.013127, +0.002160]|
|Minecraft|O-ET2X-R|[-0.012258, +0.001964]|
|Minecraft|A-ET2X|[-0.013645, -0.000313]|
|Minecraft|A-ET2X-R|[-0.013327, -0.001715]|

두 Adaptive Minecraft case만 이 개별 구간이 0을 제외한다. 작은 표본이며 여러 mode/
metric을 비교한 데 대한 보정은 하지 않았으므로 확정적인 전체 통계적 우위로 해석하지 않는다.

## 5. WholeFrame과 Standard 대비 남은 비용

ET2X 네 mode의 WholeFrame 평균 변화는 Bistro +0.53~0.99%, Minecraft -1.27~-1.82%였다.
Bistro의 pair별 방향은 +/−/+로 바뀌었고 Standard WholeFrame도 비슷하게 움직였다.
Minecraft의 Standard WholeFrame도 -0.50~-1.51% 감소했다.
따라서 전체 프레임 변화 전부를 luma 재사용 때문이라고 할 수 없다.
WholeFrame은 Present를 제외한 GPU scope이며 표시 FPS가 아니다.

변경 후에도 대응 Standard 대비 SMAA total은 다음만큼 크다(평균 ms 비율).

|Scene|O-ET2X|O-ET2X-R|A-ET2X|A-ET2X-R|
|---|---:|---:|---:|---:|
|Bistro|+31.43%|+23.41%|+35.76%|+26.19%|
|Minecraft|+37.37%|+30.55%|+40.46%|+32.08%|

이는 edge 후보 제한 단독 비용이 아니라 서로 다른 temporal kernel과 전체 파이프라인의
비교다. 이번 결과는 ET2X가 Standard보다 빠르다는 근거가 아니다.

## 6. 원시 자료와 재현

모든 run은 `D:\SMAA-Research-Data\AutoBench` 아래 보존했다.

|Pair|Bistro Before|Bistro After|Minecraft Before|Minecraft After|
|---|---|---|---|---|
|1|20260909_152537|20260909_152922|20260909_152810|20260909_153146|
|2|20260909_153619|20260909_153253|20260909_153856|20260909_153508|
|3|20260909_154003|20260909_154331|20260909_154218|20260909_154549|

실행 명령 형태:

```text
-smaaCandidateStatisticsReadback 0 -smaaEightCasePerformanceBenchmark "<scene> 1 300 4800 1"
```

`Tools/SMAA/run_clean_cmaa2.ps1`을 사용하고 Hidden 스위치를 주지 않았다.
집계 도구 `Tools/SMAA/analyze_luma_reuse_paired_performance.py`는 12개 provenance와
120개 scene/mode/metric 조합의 전후 통계를 검증한다. 각 CSV의 median, frame stddev,
p95/p99, FPS/1% low도 원시 자료로 보존하며, 집계 JSON에는 frame-rate 표도 포함한다.
시퀀스의 percentile을 평균내 전체 percentile로 부르지 않는다.

분석 묶음: `20260909_LumaReusePairedAnalysis`의 `paired-runs.json`,
`paired_results.json`, `paired_summary.md`.
PNG/VRAM traffic/candidate count는 이번 성능 실행에서 측정하지 않았고,
품질·출력 보존 근거는 기존 luma 및 capture-readiness gate를 따른다.

## 7. 다음 판단

중복 Load를 주요 병목이라고 단정했던 가설은 이 작은 시간 차이만으로 지지할 수 없다.
cache 효과나 compiler scheduling 중 무엇이 원인인지는 pass 수준 프로파일링 없이 추측하지 않는다.
이번 미세 최적화는 여기서 마무리하고, 다음 후보 정책 연구를 시작한다면 기존 정책을
유지한 독립 ablation으로 진행한다. 공간 contrast tier가 temporal 필요성을 대신 판별할
수 있는지는 아직 검증하지 않았으며 이번 성능 결과에서 그 결론을 도출하지 않는다.
