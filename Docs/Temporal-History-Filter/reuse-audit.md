# 기존 브랜치에서 temporal 단일 패스로 재사용할 요소

출발점 `0bc13ed`, 새 브랜치 `experiment/temporal-pass-history-filter`.
목표는 현재 SMAA temporal PS 안에서 저비용으로 품질 또는 성능을 개선하는 것이다.
과거 구현을 통째로 merge하거나 compute 후보·compact·indirect·복사 구조를 가져오지 않는다.
기존 SMAA spatial pass, 리소스와 history 저장 구조도 유지한다.

| 기존 작업 | 확인한 근거 | 현재 활용 판단 |
|---|---|---|
| `experiment/candidate-jitter`, `3c2711a` | 비후보에 남는 지터와 no-jitter의 supersampling 손실 | 이미 확인한 제약으로 사용. 새 jitter On/Off 실험을 반복하지 않음 |
| Standard sample-pattern/semantics, `1597a2b`·`37c668c` | 지터와 area subsample을 함께 다뤄야 함. 동일 compute 경로에서 bilinear의 공간 기준 오차가 point보다 일관되게 낮았음 | 필터만 현 pixel resolve에 옮겨 검증. 과거 compute timing/품질 수치를 새 구현 수치로 사용하지 않음 |
| ET2X feedback topology 결과 | SpatialFrame 복원에 추가 copy가 들어가 전체 AA +5.734~7.200%, 구간별 품질 절충 | 현재 Standard의 spatial-frame history를 그대로 사용. 별도 restore copy나 recursive feedback을 추가하지 않음 |
| `research/tscmaa-source-clipping-ablation`, `d54c11a` | YCoCg 부호·box 교정의 일부 효과, source kernel과 기존 kernel의 큰 격차 유지 | 통계 이웃과 다중 샘플이 필요한 clipping은 현재 범위에서 이식하지 않음 |
| `research/tscmaa-sharpen-segment-ablation`, `31b881d` | segment의 일부 이동 개선과 전환 열세, sharpening 제거의 일관된 이득 없음 | 주변 통계를 동반하는 sharpening/segment는 첫 저비용 후보에서 제외 |
| `research/tscmaa-source-candidate-reuse`, `c5b5a14` 및 contrast-tier 연구 | 1st pass 데이터 재사용으로 중복 후보 비용을 줄이지만 목록·후속 실행 구조 의존 | 계산 결과를 temporal에 전달하는 경로를 다시 추가하지 않음 |
| 현재 temporal cost/warp/counter 연구 | 동일 선택이라도 추가 명령과 분기 때문에 느려질 수 있음. Scalar는 texture 접근을 생략하지 않음 | 패스 수만으로 빠르다고 판단하지 않고 전체 AA/resolve 시간을 따로 비교 |

이전 candidate-jitter 문서에서 제안한 비후보 안정화 weight band는 검증된 성공 결과가 아니라
후속 가설이었다. 현재 temporal 패스 안에서 구현할 가능성은 있지만 임의의 weight를
성공한 최적화처럼 이식하지 않는다. 이번에는 과거에 측정 근거가 있었고 변경 범위가 작은
**history 필터** 한 요소만 적용한다.

원본 근거:

- [Candidate jitter 결과](https://github.com/Anchovia/Adaptive-SMAA/blob/3c2711a/Docs/SMAA-Candidate-Jitter-Stabilization-Results-ko.md)
- [Temporal semantics factorial](https://github.com/Anchovia/Adaptive-SMAA/blob/37c668c/Docs/SMAA-Standard-Temporal-Semantics-Factorial-Gate-ko.md)
- [Clipping 결과](https://github.com/Anchovia/Adaptive-SMAA/blob/d54c11a/Docs/SMAA-Recovered-Clipping-Ablation-Results-ko.md)
- [Sharpen/segment 결과](https://github.com/Anchovia/Adaptive-SMAA/blob/31b881d/Docs/SMAA-Recovered-Sharpen-Segment-Results-ko.md)

## 구현 조건

`O-T2X-R`, 같은 명령 순서의 `ABL-HistoryPoint-Control-R`(기존 kind 6),
`ABL-HistoryLinear-R`(25), `ABL-ScalarWeight-001-R`(16),
`ABL-ScalarHistoryLinear-001-R`(26)을 비교한다. 25는 kind 6에서 history sampler만,
26은 kind 16에서 history sampler만 바꾼다. 원본은 수정하지 않는다.

모두 paired jitter On, camera/depth reprojection On, 기존 point current/velocity,
이전 spatial history, 원본 adaptive weight 공식과 sRGB 리소스를 유지한다.
Scalar 선택식과 threshold 0.01은 유지한다. 비후보는 current spatial 그대로이므로
bilinear가 비후보 지터 문제까지 해결한다고 기대하지 않는다.

기존 s0 linear/clamp sampler를 사용해 history RGBA를 LOD 0에서 한 번 읽는다.
따라서 history RGB뿐 아니라 velocity를 인코딩한 alpha도 보간되어 실제 weight가 달라질 수
있다. 이를 순수 RGB 필터 효과로 표현하지 않는다. Point alpha를 따로 읽는 추가 샘플은 없다.
같은 sample 명령 수라도 하드웨어 texel/filter 비용이 같다는 보장은 없다.
[Microsoft D3D11 filter 정의](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_filter).

## 검증·측정 순서

1. FXC에서 native 8 variant 불변과 기존 Scalar 2 variant 불변을 검사한다.
   Point/Linear 4쌍(R On/Off, full/scalar)의 명령 차이가 sampler 선언·피연산자뿐인지 확인한다.
2. Bistro/Minecraft 각각 clean process로 9 mode×240 frame을 캡처한다. 5개 출력,
   mask/spatial control과 Linear 두 출력의 반복이다. 기존 On control hash, 새 Point control의
   native 일치, Linear 반복 hash, 선택/비선택 semantics를 검증한다.
3. 기존 동일 시점 supersample spatial reference와 RGB MAE/PSNR, edge strength,
   시간 변화 잔차 및 정지 hash를 비교한다. 선택률이 같다는 조건을 mask로 검사한다.
   영상은 보조로 제공하며 블러/고스팅을 MAE 하나로 확정하지 않는다.
4. 품질 캡처와 별도 clean process에서 5개 mode를 300 warmup, 4,800 frame×4회 측정한다.
   30초 미측정 예열 후 정순/역순을 두 번씩 적용한다. SMAA/Spatial/Resolve/WholeFrame/WallFrame을
   비교한다. 한 process 안의 네 반복이므로 독립 프로세스 통계나 논문 최종 성능으로 부르지 않는다.
   근소한 timing 차이만으로 가속 또는 동등성을 주장하지 않는다.

이 시험은 **저비용 요소의 재사용 가능성 gate**다. 현재 기본값, 최종 8-case와
공식 SMAA 정의를 바꾸지 않으며 새 품질 요소가 통과해도 자동 채택하지 않는다.

```powershell
python Tools/SMAA/validate_temporal_history_filter.py
Tools/SMAA/run_temporal_history_filter.ps1 -Phase Capture -Scene minecraft
Tools/SMAA/run_temporal_history_filter.ps1 -Phase Capture -Scene bistro
Tools/SMAA/run_temporal_history_filter.ps1 -Phase Benchmark -Scene minecraft
Tools/SMAA/run_temporal_history_filter.ps1 -Phase Benchmark -Scene bistro
```
