# Standard T2X Temporal Semantics 2×2×2 Factorial Gate

## 1. 목적

기존 `O-T2X-R`과 FullScreenDocument compute 경로의 차이는 candidate coverage 외에도
history sampler, history weight 정책, history feedback topology가 동시에 달랐다. 이 gate는
다음 세 축을 동일한 compute resolve 경로에서 직교 분해한다.

| 축 | 수준 0 | 수준 1 |
|---|---|---|
| History sampler | Point | Bilinear |
| History weight | SMAA velocity-alpha adaptive `0..0.5` | Fixed `0.5` |
| History feedback | 이전 spatial frame | resolve 결과의 recursive feedback |

공식 Standard control 두 개와 Pattern On/Off 각각의 8개 factorial cell을 합쳐 총 18개
mode를 비교했다. Pattern On/Off는 projection jitter와 대응 SMAA T2X subsample index를
항상 한 쌍으로 전환했다. 모든 compute cell은 clipping Off, clamp history bounds,
Original SMAA spatial path, camera/depth reprojection을 공통으로 사용했다.

이 실험은 final 8-case를 늘리지 않는 진단 gate다.

## 2. 캡처와 무결성

### 중앙 이동 구간

- 범위: `flythrough-wide-yaw-360` profile frame `150..329`
- Bistro: `D:\SMAA-Research-Data\AutoBench\20260902_193642`
- Minecraft: `D:\SMAA-Research-Data\AutoBench\20260902_194347`
- 각 장면: 18 mode × 180 frame = 3,240 PNG

### 이동→정지 구간

- 범위: profile frame `410..439`
- Bistro: `D:\SMAA-Research-Data\AutoBench\20260902_200941`
- Minecraft: `D:\SMAA-Research-Data\AutoBench\20260902_201207`
- 각 장면: 18 mode × 30 frame = 540 PNG

Window capture는 mode마다 profile frame 0에서 60프레임 warm-up한 뒤, 요청 구간 직전까지
PNG를 저장하지 않고 temporal pre-roll했다. 기존 전체 타임라인 공식 control과 비교한
두 장면 `O-T2X-R`/`ABL-Standard-PatternOff-R` 총 840 frame의 byte hash mismatch는 0이다.

pre-roll 없이 요청 pose에서 history를 새로 시작했던 다음 초기 부분 캡처는 formal 결과에서
제외했다.

- `20260902_190441`
- `20260902_191042`
- `20260902_191635`
- `20260902_191754`

분석 결과:

- `D:\SMAA-Research-Data\AutoBench\20260902_StandardSemanticsFactorial-Formal\CentralMotion`
- `D:\SMAA-Research-Data\AutoBench\20260902_StandardSemanticsFactorial-Formal\Transition`

Supersample 입력은 동일 pose의 spatial-reference proxy이며 absolute temporal ground truth가
아니다.

## 3. 공식 Standard와 compute mirror의 경계

`Point + Adaptive + Spatial` cell은 공식 Standard temporal 의미를 common compute 경로에
옮긴 mirror다. 그러나 움직임 구간에서 공식 pixel-shader 경로와 byte-exact하지 않았다.

| Scene | 구간 | Pattern | Mirror MAE→official | Pixel mismatch | Max channel error | Reference MAE 차이 |
|---|---|---|---:|---:|---:|---:|
| Bistro | 중앙 이동 | On | 0.057726 | 14.620267% | 88 | +0.004791 |
| Bistro | 중앙 이동 | Off | 0.054344 | 13.580931% | 97 | +0.014306 |
| Minecraft | 중앙 이동 | On | 0.049456 | 12.683944% | 107 | +0.012563 |
| Minecraft | 중앙 이동 | Off | 0.047005 | 11.907566% | 110 | +0.018493 |

평균 오차는 8-bit RGB 기준 약 `0.047~0.058`로 작지만 드문 큰 차이가 있으므로 compute
mirror를 공식 경로의 exact reproduction이라고 표현하지 않는다. Pattern Off의 후기 정지
구간에서는 두 장면 모두 mirror와 공식 control이 다시 byte-exact했다.

따라서 공식 경로와 compute 경로의 절대 비교보다, 동일 compute 경로 안의 factorial
주효과를 이 gate의 주된 인과 증거로 사용한다.

## 4. 중앙 이동 결과

양수는 두 번째 수준이 spatial-reference RGB MAE를 증가시킨 것이고, 음수는 감소시킨
것이다.

| Scene | Pattern | Bilinear−Point | Fixed−Adaptive | Resolved−Spatial |
|---|---|---:|---:|---:|
| Bistro | On | -0.104051 | +0.448788 | +0.404449 |
| Bistro | Off | -0.223632 | +0.907410 | +0.322408 |
| Minecraft | On | -0.054795 | +0.110461 | +0.226964 |
| Minecraft | Off | -0.123672 | +0.312264 | +0.194655 |

핵심 관찰:

1. `ResolvedOutput` recursive feedback는 모든 중앙 이동 조건에서 reference MAE를 높였다.
2. Bilinear sampling은 모든 중앙 이동 조건에서 Point보다 reference MAE가 낮았다.
3. Fixed `0.5` weight는 평균적으로 adaptive weight보다 오차가 컸다. 다만 factor interaction
   때문에 Minecraft Pattern On의 개별 최적 cell은 `Bilinear + Fixed + Spatial`이었다.
4. 따라서 단일 factor의 평균 효과를 모든 장면의 절대 최적 설정으로 해석하면 안 된다.

## 5. 이동→정지 결과

| Scene | 구간 | Pattern | Bilinear−Point | Fixed−Adaptive | Resolved−Spatial |
|---|---|---|---:|---:|---:|
| Bistro | 이동→정지 | On | -0.033628 | +0.003111 | +0.259119 |
| Bistro | 이동→정지 | Off | -0.092833 | +0.037641 | +0.022245 |
| Minecraft | 이동→정지 | On | -0.040998 | +0.042929 | +0.264076 |
| Minecraft | 이동→정지 | Off | -0.090797 | +0.072584 | +0.071730 |
| Bistro | 후기 정지 | On | -0.010367 | +0.013259 | +0.256733 |
| Bistro | 후기 정지 | Off | -0.042797 | +0.022733 | +0.016348 |
| Minecraft | 후기 정지 | On | -0.032010 | +0.051881 | +0.265260 |
| Minecraft | 후기 정지 | Off | -0.059468 | +0.065589 | +0.077877 |

Pattern On에서 `ResolvedOutput` feedback의 열세가 두 장면 모두 약 `+0.26`으로 반복됐다.
Pattern Off에서는 영향이 더 작고 interaction에 따라 일부 resolved cell이 개별 최적값이
되었다. 따라서 motion-to-still 열세는 candidate coverage만으로 설명되지 않으며,
sample pattern과 recursive feedback의 상호작용을 함께 봐야 한다.

## 6. 현재 결론

1. 기존 ET2X의 motion-to-still 열세를 edge coverage 하나의 문제로 단정할 수 없다.
2. 같은 compute 경로에서 `ResolvedOutput` recursive feedback가 가장 크고 일관된 품질
   저하 요인으로 나타났다.
3. Bilinear sampling은 이 spatial-reference 지표에서는 Point보다 일관되게 유리했다.
4. Fixed history weight는 장면·pattern interaction이 있어 기본 해법으로 바로 채택할 수 없다.
5. Intel 공개 TSCMAA 자료는 resolve 결과의 history feedback을 포함하므로, document profile을
   즉시 spatial-frame feedback으로 교체하지 않는다. 먼저 별도 ablation으로 효과와 비용을
   검증한다.
6. 이번 결과는 sampler/weight/feedback의 진단이며 candidate coverage, Catmull-Rom,
   variance clipping, history weight `0.8`의 최종 우열을 직접 판정하지 않는다.

## 7. 다음 gate

1. `O-ET2X-R`에서 candidate source/policy/coverage, sampler, clipping, weight, pattern을
   고정하고 feedback만 `ResolvedOutput`/`SpatialFrame`으로 비교한다.
2. 같은 캡처에서 중앙 이동과 이동→정지를 모두 측정해 한 구간만 좋아지는 설정을 배제한다.
3. 두 feedback topology의 GPU 시간을 분리해 recursive history copy 제거가 실제 비용 감소로
   이어지는지 확인한다.
4. compute mirror의 움직임 중 rare large mismatch는 history coordinate/bounds, point sampling
   좌표, velocity-alpha 전달과 pixel/compute resource path 순으로 추가 감사한다.
5. 위 gate가 끝나기 전에는 final 8-case 기본 semantics를 변경하지 않는다.

## 8. 크래시 및 실행 판정 보강

반복된 `0xC0000005` 팝업을 조사하면서 Microsoft ProcDump의 first-chance access-violation
감시 아래 다음을 재실행했다.

- temporal lifecycle test: PASS
- 410-frame pre-roll + 18 mode × 1 frame: 18/18 PNG, PASS
- Bistro 18 mode × 30 frame: 540/540 PNG, PASS
- Minecraft 18 mode × 30 frame: 540/540 PNG, PASS
- 위 감시 실행의 `0xC0000005` dump: 0
- 종료 후 잔류 `CMAA2.exe`: 0

현재 빌드에서 확정적으로 재현되는 접근 위반은 확인되지 않았다. 장시간 캡처 종료 시점의
간헐 문제 가능성은 남으므로, `run_clean_cmaa2.ps1`은 이제 정상 exit code뿐 아니라 새
AutoBench `_results.csv`가 실제 완성됐을 때만 PASS를 출력한다. 실패 또는 부분 결과는 formal
결과로 사용하지 않는다.
