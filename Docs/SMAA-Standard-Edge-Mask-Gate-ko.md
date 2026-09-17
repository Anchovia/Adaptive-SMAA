# 원본 SMAA T2X-R의 first-pass edge 한정 resolve 실험

## 목적과 구현 범위

`experiment/standard-t2x-edge-mask`에서 기존 `O-T2X-R`의 temporal 계산은 그대로 두고
적용 픽셀만 첫 edge 패스의 검출 위치로 제한했다. 연구 질문은 **기존 SMAA의 edge
texture를 그대로 사용하면 별도 후보 처리 구조 없이 temporal 비용을 줄일 수 있는가**다.

브랜치 출발점은 현재 연구·측정 도구가 있는 `81c0d23`이다. 오래된 baseline 브랜치로
렌더러 전체를 되돌리지 않고, 그 안에 보존된 Original SMAA / native Standard pixel
resolve 경로를 기준으로 삼았다. 기존 ET2X compute 경로를 이용한 구현이 아니다.
정식 8-case, Original/Adaptive 및 기존 ET2X 기본값은 변경하지 않았다.

| 항목 | O-T2X-R | ABL-Standard-EdgeMask-R |
|---|---|---|
| 공간 처리 | Original SMAA T2X | 동일 |
| projection jitter와 subsample index | 공식 paired pattern | 동일 |
| 재투영 | camera/depth velocity | 동일 |
| history sampling | native point sampler | 동일 함수 |
| history weight | velocity-alpha 기반 0..0.5 | 동일 함수 |
| 다음 프레임 history | 해당 프레임 spatial result | 동일 |
| temporal 적용 범위 | 화면 전체 | 기존 RG edge 중 어느 성분이든 0보다 큰 픽셀 |
| 비후보 출력 | 해당 없음 | 현재 spatial result |

SMAA 3차 neighborhood blending을 완료한 색상을 temporal resolve한다. Edge texture
자체에 색상 TAA를 적용하지 않는다. 기존 resolve draw에서 edge를 한 번 `Load`하고,
비후보는 current point sample을 반환한다. 후보는 수정하지 않은 `SMAAResolvePS`를
직접 호출한다. 기존 edge RT의 SRV를 바인딩하고 draw 이후 해제한다.

별도 edge 검출, 후보 mask 생성·확장 패스, compact 목록, atomic counter, indirect
dispatch, 추가 history 복사나 새 화면 크기의 texture가 없다. 다만 full-screen raster
draw 자체는 유지되므로 모든 픽셀의 실행·마스크 읽기·현재 색상 출력 비용은 남는다.
일반 Standard는 기존 shader entry를 사용하므로 새 GPU 분기가 들어가지 않는다.

이번 후보는 **SMAA 첫 패스에서 살아남은 edge 전체**다. Intel 후보식이나 추가 50%
제거를 적용하지 않는다. TSCMAA 원본 재현이 아니라 native SMAA의 coverage-only
ablation이다. `TemporalSettings.Coverage=FullScreen`은 기존 native 실행 경로를 선택하기
위해 유지하고, 별도 `StandardEdgeMask` 설정과 semantic ID로 실제 history 적용 범위를
명시한다. 설정 변경은 기존 equality/history reset에 포함된다.

Object-motion과 previous-depth rejection은 이번 gate에서 Off로 고정했다.
새 mode에서 previous-depth rejection을 요청하면 지원되지 않는 조합으로 거부한다.
3×3 확장, Catmull-Rom, clipping, weight 변경, resolved-output feedback은 추가하지 않았다.

## 검증 방법과 한계

- Release x64 / DirectX 11 / SMAA Ultra 빌드와 실제 GPU smoke 통과.
- 변경 전 `81c0d23` 대비 luma edge, blending weights, neighborhood blending,
  native resolve의 reprojection Off/On 총 8개 shader variant가 FXC byte-identical.
- 새 mode 전환을 포함한 lifecycle: 61 resets, 163 completed frames,
  36 seed, 127 resolve, 95 reprojection, failures 0.
- Bistro/Minecraft의 `flythrough-wide-yaw-360` frame 150~161에서 각각 원본,
  masked, current spatial, edge mask, masked 독립 반복의 5개 sequence를 검사.
  각 실행은 첫 캡처 pose에서 60-frame warm-up하며 전체 timeline pre-roll은 하지 않는다.
- 후보 위치의 masked RGB는 native Standard RGB와 일치하고, 비후보의 masked RGB는
  current spatial RGB와 일치한다. 반복 RGB도 일치한다. 두 장면 모두 mismatch 0.
- 소스 파일의 원래 UTF-8 BOM을 복원한 최종 빌드로 다시 캡처한 두 장면 각 12 PNG도
  앞선 검증 출력과 SHA-256 일치했다. 최종 반복 성능에는 이 최종 바이너리를 사용했다.
- 이 구간의 선택 픽셀은 화면 기준 Bistro 14.159%, Minecraft 7.139%였다.
  이는 짧은 검증 구간의 비율로, 성능 경로 전체의 후보 비율이 아니다.
- 캡처는 정확성 검사용 engineering subset이다. Full-reference/CGVQM 고스팅 평가나
  전체 움직임→정지 품질 평가가 아니다. 인접 프레임 차이는 camera motion과 원래 렌더링
  변화를 포함하며, 단독 품질 순위로 사용하지 않는다.
- 전역 jitter를 유지한 채 일부 픽셀에서 temporal 결합을 생략하므로 깜빡임과 얇은 구조의
  temporal 안정성 손실을 후속 연속 영상·reference 비교에서 확인해야 한다.

## 반복 성능 결과와 판단

RTX 3060 Ti / 1920×1017 / visible window / VSync Off에서 각 장면을 독립 프로세스로
측정했다. 두 mode의 순서는 정방향→역방향→정방향이며, 각 mode/run은 300 warm-up,
4,800 measurement frames다. Mode당 14,400개의 각 timing sample과 run mean 3개,
readback Off, 내부 PASS를 확인했다. PNG와 debug 출력은 껐다.

| GPU metric (ms) | Bistro Standard | Bistro EdgeMask | 변화 | Minecraft Standard | Minecraft EdgeMask | 변화 |
|---|---:|---:|---:|---:|---:|---:|
| SMAA total | 0.281645 | 0.285855 | +1.495% | 0.293965 | 0.306377 | +4.222% |
| Native temporal resolve | 0.037693 | 0.040879 | +8.452% | 0.038136 | 0.050080 | +31.319% |
| Spatial SMAA T2X | 0.219125 | 0.220146 | +0.466% | 0.231614 | 0.232047 | +0.187% |
| Camera velocity | 0.024800 | 0.024810 | +0.040% | 0.024202 | 0.024224 | +0.091% |
| WholeFrame | 2.938157 | 2.932181 | -0.203% | 1.296137 | 1.309586 | +1.038% |

SMAA run-mean 표준편차는 Bistro Standard/EdgeMask 0.002666/0.001019 ms,
Minecraft 0.001172/0.001122 ms다. Resolve run-mean 표준편차는 각각
0.000097/0.000085 ms, 0.000070/0.000086 ms다. 정확한 median/p95/p99 및 wall interval은
파생 JSON에 보존했다. 세 반복의 평균 비교이며 별도 통계적 유의성 검정을 주장하지 않는다.

**이 실행 구조에서는 속도 향상을 확인하지 못했다.** 추가 GPU pass나 compact/history copy가
없는 native resolve에서도 마스크·분기를 추가한 temporal 구간이 더 비쌌다. 따라서
기존 ET2X의 큰 비용을 줄이는 것과, 간단한 native Standard보다 더 빨라지는 것은 구분해야 한다.
WholeFrame은 Bistro에서 미세하게 감소하고 Minecraft에서는 증가하여 일관된 향상도 없다.

FXC assembly에서는 edge `ld` 다음 `if_z`/current-color 반환이 있고, velocity/history
`sample`은 그 뒤에 남아 있다. 따라서 구현이 비후보에서도 무조건 history를 샘플링하도록
컴파일된 것은 아니다. 마스크 접근, 분기와 GPU 실행 단위 내 후보 혼재, texture/cache 특성
등이 절감량을 상쇄할 수 있다. 어느 하드웨어 요인이 지배적인지는 GPU counter 없이 확정하지
않는다. 이 결과가 모든 선택적 temporal 구조의 불가능성을 뜻하지도 않는다.

이번 branch는 재현 가능한 최소 실험으로 보존한다. 확정 품질 우위나 논문용 성능 성공으로
승격하지 않는다. 후속 실행 구조를 검토한다면 기존 edge/stencil을 이용해 shader 진입
자체를 제한할 수 있는지와 비후보 출력 유지 비용을 함께 따져야 하며, 이번 결과에 그 개선을
구현·측정한 것으로 섞지 않는다.

## 재현

저장소 루트에서 다음 순서로 실행한다. 캡처와 성능은 각 명령마다 새 CMAA2 프로세스를
사용한다. `run_clean_cmaa2.ps1`이 실행 전/후 프로세스 0개와 timeout, 결과 CSV를 검사한다.

```powershell
Tools/SMAA/run_standard_edge_mask_gate.ps1 -Phase Quality -Scene bistro
Tools/SMAA/run_standard_edge_mask_gate.ps1 -Phase Quality -Scene minecraft
Tools/SMAA/run_standard_edge_mask_gate.ps1 -Phase Lifecycle
Tools/SMAA/run_standard_edge_mask_gate.ps1 -Phase Performance -Scene bistro
Tools/SMAA/run_standard_edge_mask_gate.ps1 -Phase Performance -Scene minecraft
Tools/SMAA/run_standard_edge_mask_gate.ps1 -Phase FinalBuildBridge -Scene bistro
Tools/SMAA/run_standard_edge_mask_gate.ps1 -Phase FinalBuildBridge -Scene minecraft
python Tools/SMAA/analyze_standard_edge_mask_gate.py --require-complete
python Tools/SMAA/validate_standard_edge_mask_shaders.py
```

새 실행 묶음에는 `-Receipt <새 JSON 경로>`를 지정하고 분석기에 같은 경로를 넘긴다.
단일 실행은 `-smaaStandardEdgeMaskPerformanceSmoke` / `Benchmark`와
`-smaaCameraMotionSingleModeCapture "<scene> <profile> ABL-Standard-EdgeMask-R ..."`로도 가능하다.
`-smaaTemporalDebugView 1`은 native 경로의 실제 first-pass edge mask,
`3`은 current spatial result를 출력한다. 디버그 출력은 성능에서 꺼 둔다.

상세 실행 경로·명령·바이너리 해시와 파생 검증 수치는
`Standard-Edge-Mask-20260917/results.json`, shader 해시는 `shader-regression.json`에 기록한다.
원시 CSV/PNG는 기존 D드라이브 AutoBench 보관 경로에만 저장한다.

초기 실패는 결과에서 제외했다. 최초 sandbox 캡처는 D드라이브 junction의 출력 경로를
만들지 못해 결과가 없었다. 최초 masked 셰이더는 optional previous-depth wrapper를
중첩 호출하면서 FXC warning-as-error에 걸렸다. 해당 프로세스만 종료하고 native 함수
직접 호출로 수정했으며 이후 shader/GPU 검증은 정상 통과했다.
