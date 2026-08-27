# SMAA 1차 Edge Pass 통합 Temporal Candidate Core

## 1. 목적

기존 `O-ET2X`/`O-ET2X-R` prototype은 SMAA의 공간 처리 전체를 수행한 뒤 full-resolution
compute shader에서 temporal 후보를 다시 판정했다. 이 구조는 구현 검증용 기초 틀로는
유효하지만, Intel 공개 TSCMAA 자료가 설명하는 “edge detection 단계에서 temporal 후보를
추려 compact하고 indirect processing으로 넘기는 구조”와 거리가 있었고 추가 full-screen
dispatch 병목을 만들었다.

이번 변경의 목적은 다음과 같다.

- 원본 SMAA edge→weight→neighborhood 순서와 출력은 유지한다.
- SMAA 1차 luma edge pixel shader가 공간 edge RT를 기록하는 바로 그 draw에서 temporal
  base/candidate mask, compact list와 counter를 함께 기록한다.
- 후보 생성 뒤에는 indirect dispatch args와 candidate resolve만 수행한다.
- 기존 `LegacyLumaRedetect`와 post-pass `SMAAFirstPassEdges`는 비교 ablation으로 보존한다.
- 공개되지 않은 Intel 원본 candidate 식과 현재 adaptation 식을 동일하다고 표현하지 않는다.

## 2. 구현 구조

### 기존 prototype

```text
SMAA edge detection
→ SMAA blending weight calculation
→ SMAA neighborhood blending
→ full-screen candidate prepare/clear
→ full-screen candidate extraction 또는 luma 재검출
→ indirect args
→ selected candidate temporal resolve
```

### 새 통합 경로

```text
SMAA edge detection
  ├─ 기존 edge RT 출력
  └─ temporal base/candidate mask + compact list/counter 출력
→ SMAA blending weight calculation
→ SMAA neighborhood blending
→ indirect args
→ selected candidate temporal resolve
```

후보 buffer와 mask clear는 필요하므로 남지만, 별도 full-screen candidate extraction
dispatch는 실행하지 않는다. 통합 후보 계산 비용은 `SMAASpatial1X` 안에 포함되며,
`TSCMAAClearIntegratedCandidateBuffers`는 오직 buffer/mask clear 비용만 뜻한다.

## 3. 원본 보존 경계

- 일반 `SMAA::go` 호출의 새 candidate 출력 인자는 기본 `nullptr`이다.
- Standard `O-T2X`, `O-T2X-R`과 SMAA 1X는 기존 edge technique을 그대로 사용한다.
- Edge-selective document profile만 `SMAAFirstPassIntegratedCandidates`를 요청한다.
- Original은 기존 단일 edge RT를, Adaptive는 기존 edge+metadata MRT를 유지한다.
- integrated shader는 기존 SMAA luma edge threshold 및 local contrast filtering 계산을
  동일하게 수행하고 같은 encoded edge output을 반환한다.
- 확장 ablation은 raw candidate mask를 통합 pass에서 기록한 뒤 기존 3x3,
  FilteredQuarter, ARM Dual Filtering 후속 경로를 재사용한다.

## 4. Candidate 식의 연구상 분류

Intel 공개 자료에서 확인된 기본값은 edge threshold `1/22`, non-dominant removal `0.5`와
edge 후보 compact/indirect 처리 구조다. 그러나 유실된 sample shader의 정확한 후보 식은
확인하지 못했다.

현재 `IntelFamilyNonDominant` 식은 기존에 검증한 연결 edge local-contrast 구조를 SMAA
1차 pass로 옮긴 adaptation이다. 따라서 다음 표현만 사용한다.

> Intel TSCMAA 공개 문서의 구조와 기본값을 참고한 SMAA adaptation

“공식 TSCMAA candidate shader”, “완전한 공식 포팅” 또는 “원본 식 재현”이라고 부르지
않는다.

## 5. Engineering 검증

### 5.1 빌드 및 lifecycle

- Visual Studio 2022, Release x64 빌드 PASS
- runtime PS 5.0 integrated edge shader compile PASS
- 8-mode temporal lifecycle: reset 48, completed frame 75, seed 25, resolve 50,
  reprojection 62, failure 0
- 모든 자동 실행 전후 잔류 `CMAA2.exe` 0개 확인

### 5.2 post-pass와 integrated 출력 동일성

동일 설정에서 기존 post-pass `SMAAFirstPassEdges`와 새 integrated source를 비교했다.

| 검증 대상 | 결과 |
|---|---:|
| Bistro/Minecraft policy sweep의 base/candidate/process count | 전체 값 동일 |
| candidate debug mask, `O-ET2X`/`O-ET2X-R` 각 2 frame | mismatch 0 pixel |
| base edge mask, 각 2 frame | mismatch 0 pixel |
| current spatial output, 각 2 frame | mismatch 0 pixel |
| final temporal output, 각 3 frame | mismatch 0 pixel |

즉 이번 변경은 검증된 post-pass candidate 결과를 1차 edge draw로 이동한 구조 변경이며,
해당 비교 frame에서는 공간·temporal 출력 변화가 없었다.

### 5.3 동일 실행 GPU smoke

RTX 3060 Ti, 1920×1017, Release x64, SMAA Ultra, VSync Off, readback On,
30-frame warm-up + 60-frame 측정의 단일 engineering smoke 결과다. 정식 성능 결론으로
사용하지 않는다.

| Mode | source | SMAA GPU 평균 |
|---|---|---:|
| `O-ET2X` | Legacy luma 재검출 | 0.293649 ms |
| `O-ET2X` | post-pass SMAA edge 재사용 | 0.301056 ms |
| `O-ET2X` | 1차 pass 통합 | 0.229820 ms |
| `O-ET2X-R` | Legacy luma 재검출 | 0.326212 ms |
| `O-ET2X-R` | post-pass SMAA edge 재사용 | 0.331435 ms |
| `O-ET2X-R` | 1차 pass 통합 | 0.262042 ms |

통합 경로는 post-pass edge 재사용보다 SMAA total이 `O-ET2X` 23.662%,
`O-ET2X-R` 20.937% 낮았다. candidate 계산이 1차 pixel shader에 합쳐져
`SMAASpatial1X` 자체는 약 7% 증가했지만 약 0.077 ms의 full-screen extraction pass가
사라져 net SMAA 시간이 감소했다. WholeFrame과 실제 표시 FPS는 단일 smoke 변동이
크므로 결론을 내리지 않는다. 이후 readback Off 반복 본 측정이 필요하다.

## 6. 0.05 간격 removal sweep

명령:

```powershell
CMAA2.exe -smaaIntegratedCandidateRemovalSweep
```

조건:

- source: `SMAAFirstPassIntegratedCandidates` 강제
- policy: `IntelFamilyNonDominant`
- expansion: None
- edge threshold: `1/22` 고정
- removal: `0.00~1.00`, 0.05 간격 21개
- 장면: 고정 pose의 Bistro와 Minecraft
- shadow map 안정화 뒤 counter readback
- 각 단계에서 base 안정성, candidate 단조 감소, process=candidate,
  `groups=ceil(candidate/64)` 검증

두 번의 독립 clean-process 실행 결과 파일은 전체 내용이 동일했고 Aggregate PASS였다.

| Removal | Bistro candidate/base | Minecraft candidate/base |
|---:|---:|---:|
| 0.00 | 100.000% | 100.000% |
| 0.50 | 57.417% | 62.766% |
| 0.65 | 52.759% | 52.945% |
| 0.70 | 51.351% | 49.745% |
| 0.75 | 49.561% | 46.063% |
| 1.00 | 43.515% | 32.733% |

Intel 문서의 약 50% 목표에 가장 가까운 값은 고정 pose 기준 Bistro `0.75`, Minecraft
`0.70`으로 달랐다. 이는 장면 독립적인 “최적값”을 후보 비율만으로 정할 수 없다는
근거다.

## 7. 파라미터 최적화 연구 계획

파라미터 탐색은 다음 단계로 분리한다.

1. 공개 기본값 `0.50`을 반드시 control로 유지한다.
2. 1차 finalist는 `0.50`, `0.65`, `0.70`, `0.75`로 둔다.
3. Bistro 저대비와 Minecraft 고대비에서 동일 camera path로 연속 PNG와 후보 비율을
   측정한다.
4. supersample spatial reference, CGVQM-2, RGB MAE/PSNR/SSIM, edge strength,
   temporal variation 및 대표 GIF를 함께 평가한다.
5. history 사용 감소가 고스팅 감소처럼 보이는 퇴행을 막기 위해 O-1X와 Standard T2X-R
   control을 함께 둔다.
6. 품질 gate를 통과한 값만 readback Off, 300 warm-up, 4,800 frame×3회 성능 측정으로
   올린다.
7. 장면별 최적값과 두 장면 공통 robust 값이 다르면 둘을 분리 보고하고, tuning 장면과
   검증 장면을 나눠 overfitting을 확인한다.

`0.05`는 범위가 0~1인 removal에 적절하다. 반면 edge threshold 기본값은 약 `0.04545`라
0.05 단위가 너무 크다. threshold를 후속 탐색할 때는 removal finalist를 먼저 고정하고
`0.005` 정도의 간격으로 기본값 주변을 별도 sweep한다. 두 축을 처음부터 전 조합하면
품질 캡처와 반복 성능 비용이 과도하고 원인 분리가 어려우므로 순차 탐색을 사용한다.

## 8. 현재 결론과 제한

- 중복 full-screen candidate extraction을 제거하는 구조는 구현·출력 동일성·GPU smoke를
  통과했다.
- 단일 smoke에서는 SMAA GPU 비용 감소가 명확했지만 아직 정식 반복 성능 결론은 아니다.
- 0.05 sweep은 후보 수 특성화이며 품질 최적값을 정한 결과가 아니다.
- candidate formula 자체는 여전히 공개 자료 기반 SMAA adaptation이다.
- 현재 `-R`은 camera/depth reprojection이며 object motion vector는 기본 8-case에 아직
  포함되지 않는다.

## 9. 후속 removal 품질 gate

계획한 `0.50/0.65/0.70/0.75` matched quality gate를 Bistro/Minecraft에서 완료했다.
네 값 모두 catastrophic artifact 없이 engineering gate를 통과했으며, 공개 기본값
`0.50`, 장면 공통 robust 중심 후보 `0.70`, bracket `0.65/0.75`의 역할을 사전에
구분한 상태로 readback-Off 반복 성능 측정에 올린다. 상세 조건과 결과는
`Docs/SMAA-Integrated-Candidate-Removal-Quality-Gate-ko.md`를 기준으로 한다.
