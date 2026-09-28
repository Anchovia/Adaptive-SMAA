# No-TAA 대조군을 포함한 첫 edge 선택 품질 비교

## 비교 범위

**No-TAA는 현재 spatial SMAA 결과만 출력하고 temporal 결합을 하지 않는 대조군이다.**
`DBG-CurrentSpatial-R`의 paired projection jitter/subsample pattern은 유지한다.
따라서 지터를 끈 일반 SMAA 1X 또는 AA 자체를 끈 결과가 아니다. `-R`은 기존 진단 mode의
이름이며, 이 출력 자체는 history를 읽거나 재투영해 결합하지 않는다.
Original 공간 SMAA, 동일 카메라 경로·노출·해상도의 기존 캡처를 그대로 사용했다.
새 패스, 셰이더 변경, 재캡처 또는 성능 재측정은 없다. 최종 8-case가 아닌 engineering 대조 실험이다.

## CGVQM-2 결과

점수는 높을수록 좋다. 이동은 frame 60~179(120장), 이동→정지는 160~219(60장)다.

| 장면 | 구간 | No-TAA (지터 On) | Edge 선택 | 원본 T2X-R | 선택−No-TAA | 원본−No-TAA |
|---|---|---:|---:|---:|---:|---:|
| bistro | moving | 92.918434 | 93.546402 | 96.191238 | +0.627968 | +3.272804 |
| bistro | transition | 89.238823 | 90.612900 | 96.719254 | +1.374077 | +7.480431 |
| minecraft | moving | 85.576050 | 89.761742 | 93.911362 | +4.185692 | +8.335312 |
| minecraft | transition | 77.837791 | 87.015083 | 94.905739 | +9.177292 | +17.067947 |

네 구간 모두 **원본 T2X-R > edge 선택 > No-TAA**다.
이 비교는 edge 선택 방식의 안정화 효과가 전혀 없는지, 원본과 비교했을 때 어느 정도
부족한지를 구분한다. CGVQM 점수 차이를 품질 보존율이나 잔상 감소율로 환산하지 않는다.

## 정지 후기의 프레임 간 변화

기존 전체 PNG 분석의 frame 200~239 지표다. 인접 프레임 RGB 평균 절대 차이(0~255 단위)이며,
고정 카메라·고정 장면에서 남는 변동을 나타낸다. 이동 장면의 차이는 실제 움직임도 포함한다.

| 장면 | No-TAA (지터 On) | Edge 선택 | 원본 T2X-R |
|---|---:|---:|---:|
| bistro | 1.617644 | 1.255586 | 0.000000 |
| minecraft | 5.350120 | 2.954760 | 0.000000 |

Edge 선택은 No-TAA의 변동 일부를 줄이지만 원본처럼 정지 후 변동이 0이 되지는 않는다.
비선택 픽셀의 지터 표본과 위상별 선택 변화가 남는다는 기존 관측과 일치한다.
이 결과로 고스팅 개선을 확정할 수 없으며, 지터 Off 공간 SMAA의 점수도 대신하지 않는다.

## 재현과 검증

- 동일 supersampling spatial reference(2× 선형 해상도, 3×3 subpixel grid, 8×MSAA).
  시간적 ground truth나 고스팅만의 전용 참조로 표현하지 않는다.
- 공식 Intel CGVQM commit `8302ff45b4ff5a691682baf23f7c007d6b591e98`, model 2,
  CUDA, 60 FPS, patch_scale=4, patch_pool=mean을 유지했다.
- No-TAA 네 clip은 새 평가. 모든 test/reference FFV1 RGB encode/decode mismatch 0.
- 기존 native/selected 점수는 결과 파일 SHA-256 및 현재 PNG의 frame index 포함
  pixel stream hash를 다시 검사한 뒤 재사용했다. 참조 hash, 범위·해상도,
  공식 commit·설정과 Torch/CUDA/device도 일치한다.
- `*-no-taa-cgvqm.json`은 새 원시 결과 record, 결과 파일 hash와 비교 점수를 보존한다.
  기존 `*-quality.json`, `*-cgvqm.json` 및 성능 결과는 덮어쓰지 않는다.
- `run_temporal_first_edge_no_taa_cgvqm.py --scene bistro`와 `--scene minecraft`를
  순차 실행한 후 `summarize_temporal_first_edge_no_taa.py`로 이 보고서를 생성한다.

[기존 품질·성능 연결 보고서](report.md)
