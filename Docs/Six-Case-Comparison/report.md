# AA 6개 구성: 시간·품질 비교 정리

**2026-09-29 정정 — ⑤·⑥ 채택 철회:** 아래 ⑤·⑥은 전체 화면 pixel shader에서 current와 edge를 읽고 분기한 구현의 보존 기록이다. 선택된 edge만 temporal 실행 대상으로 삼으라는 요구를 충족한 구현으로 사용하지 않는다. 출력 선택 검증 PASS는 실행 범위 검증이 아니다. 원시 측정은 보존하며 ①~④ 기준선 검증은 철회하지 않는다. 새 ⑤·⑥의 독립 브랜치 구현과 실행 범위·성능 검증은 [재구현 결과](rebuilt-edge-execution.md)에서 별도로 제공한다.

기존 실험의 측정 기록을 보존한다. 주 표의 ⑤·⑥은 채택을 철회한 **지터 Off 전체 화면 마스크 분기** 버전이다. 초기 지터 On 버전은 뒤의 별도 표에 보존했다. 6개를 새로 한 실행에 넣어 측정한 최종 비교 행렬은 아니다.

## 1. 무엇을 비교했는가

| 구성 | Spatial AA | Temporal 처리 | 지터 |
|---|---|---|---|
| ① AA-Off | 없음 | 없음 | Off |
| ② SMAA 1X | 원본 SMAA | 없음 | Off |
| ③ Temporal-only | 없음 | 전체 화면 | On |
| ④ 원본 SMAA T2X-R | 원본 SMAA | 전체 화면 | On |
| ⑤ Edge-selective temporal-only | 없음 | 첫 패스 edge | Off |
| ⑥ SMAA + edge-selective temporal | 원본 SMAA | 첫 패스 edge | Off |

③~⑥의 reprojection은 camera/depth 기반이다. Object motion vector까지 검증한 결과가 아니다. ⑤는 공간 혼합을 하지 않지만 선택에 필요한 원본 첫 edge 검출을 실행한다. ⑥은 원본 공간 SMAA 세 패스를 모두 보존한다. ⑤·⑥은 검출된 RG edge를 모두 사용하며, Intel의 non-dominant 제거로 절반을 고른 구현이 아니다.

## 2. AA 처리 시간

[원본 T2X-R=100% 기준 전체 AA·temporal resolve 비교표](baseline-relative.md)를 별도로 제공한다. 서로 다른 실행의 비율은 산술 참고값으로 명시했다.

단위 ms. 표의 값은 **전체 AA GPU scope** 평균 ± 네 반복 평균의 표준편차다. Temporal resolve 단독 시간이나 전체 렌더 프레임 시간이 아니다. 작은 표준편차가 서로 다른 실행·계측 구조 사이의 편향까지 보정해 주지는 않는다.

| 구성 | Bistro | Minecraft | 측정 묶음 |
|---|---:|---:|---|
| ① AA-Off | AA 패스 미실행 | AA 패스 미실행 | — |
| ② SMAA 1X | 0.148339 ± 0.002418 | 0.220823 ± 0.001434 | B |
| ③ Temporal-only | 0.079702 ± 0.000544 | 0.082272 ± 0.000086 | T |
| ④ 원본 SMAA T2X-R | 0.212364 ± 0.002807 | 0.284575 ± 0.001585 | P6 |
| ⑤ Edge-selective temporal-only | 0.103695 ± 0.000066 | 0.116396 ± 0.000218 | P5 |
| ⑥ SMAA + edge-selective temporal | 0.207329 ± 0.000170 | 0.287970 ± 0.000843 | P6 |

**①을 전체 렌더링 0ms로 뜻하는 것이 아니다.** AA 전용 패스를 실행하지 않으며, 다른 구성과 대응하는 전체 프레임 시간은 이 표에 없다.

RTX 3060 Ti, DX11, 1920×1061, Ultra, hidden window, VSync Off. 측정 묶음별 clean process, 30초 사전 실행, mode별 300 warmup, 4,800프레임×4회 정·역 순서를 사용했다. B/T는 기존 AA 전체 timer를 쓰며, P5/P6에는 단계별 timer와 프레임 수명 교정·주기별 history reset이 있다. **묶음이 다른 행을 빼서 정확한 속도 향상률을 계산하지 않는다.** 각 묶음의 두 장면도 별도 실행이다.

| 묶음 | 사용한 완료 결과 | 고정 커밋 |
|---|---|---|
| B | 원본 기준선 재검증: ② | `e14f122` |
| T | Temporal-only 독립 대조: ③ | `e2bbf87` |
| P5 | ⑤의 지터 On/Off 대조 | `2e3ac6c` |
| P6 | ④와 ⑥의 지터 On/Off 대조 | `556f226` |

③에는 첫 edge 검출이 없고 ⑤에는 그 비용이 포함된다. ③·⑤의 공간 AA 생략으로 줄어든 시간을 원본 SMAA의 동일 품질 최적화 효과로 표현하지 않는다.

### 같은 실행에서 확인한 상대 비용

음수는 시간 감소, 양수는 증가다. 아래 비교만 대응 실행 안에서 계산했다.

| 비교 | 장면 | 전체 AA 변화 | Resolve 변화 |
|---|---|---:|---:|
| ⑤ Off 선택 vs edge 검출 포함 Off full | bistro | -5.725% | -18.199% |
| ⑤ Off 선택 vs edge 검출 포함 Off full | minecraft | +2.182% | +7.073% |
| ⑥ Off 선택 vs ④ 원본 T2X-R | bistro | -2.371% | -16.836% |
| ⑥ Off 선택 vs ④ 원본 T2X-R | minecraft | +1.193% | +8.405% |
| ⑥ Off 선택 vs 공간 SMAA Off full | bistro | -2.681% | -16.915% |
| ⑥ Off 선택 vs 공간 SMAA Off full | minecraft | +0.958% | +8.496% |

⑤의 이 대조군은 ③이 아니다. ③에는 없는 edge 검출을 full 쪽에도 넣어 선택의 효과만 분리했다. ④→⑥ Off 비교에는 지터 패턴 변경도 포함된다. 순수 edge 선택 효과는 같은 Off full과의 비교에서 판단한다.

## 3. 품질: CGVQM-2

**높을수록 좋다.** 이동=frame 60~179, 이동 후 정지 전환=160~219. 같은 60 FPS 카메라 경로, 같은 frame index와 supersample spatial reference를 사용했다. 표의 모든 완료 점수는 reference RGB hash·범위·해상도·공식 모델 commit·평가 설정의 일치를 확인했다.

| 구성 | Bistro 이동 | Bistro 정지 전환 | Minecraft 이동 | Minecraft 정지 전환 |
|---|---:|---:|---:|---:|
| ① AA-Off | 미측정 | 미측정 | 미측정 | 미측정 |
| ② SMAA 1X | 96.0628 | 95.8746 | 95.1725 | 94.9164 |
| ③ Temporal-only | 미측정 | 미측정 | 미측정 | 미측정 |
| ④ 원본 SMAA T2X-R | 96.1912 | 96.7193 | 93.9114 | 94.9057 |
| ⑤ Edge-selective temporal-only | 96.0332 | 95.6477 | 95.4060 | 94.9690 |
| ⑥ SMAA + edge-selective temporal | 96.1734 | 95.9116 | 95.2341 | 94.8942 |

①과 ③은 출력·정지 안정성을 검증했지만 이 두 구간의 CGVQM을 아직 측정하지 않았다. 0점이나 다른 방식의 점수로 채우지 않았다. 과거 지터 On current-spatial 진단 결과를 AA-Off 또는 SMAA 1X 점수로 재사용하지 않았다.

공식 CGVQM-2, CUDA, patch scale 4, mean을 사용했다. ⑤·⑥은 메모리 한도 때문에 원래 30프레임 추론 경계를 보존하는 최대 60프레임 단위 실행을 사용했고, 기존 native 점수와 0.00002 이내 일치를 확인했다. FFV1 입력은 RGB 무손실 검증을 통과했다. 참조는 공간 품질 proxy이므로 점수 하나로 고스팅·깜빡임·선명도를 각각 판정하지 않는다.

## 4. 정지 떨림과 이전 지터 On 버전

①~④와 주 표의 지터 Off ⑤·⑥은 **두 장면 모두** 정지 초반 20~59 및 후반 200~239에서 고유 RGB 프레임 수 1, 인접 RGB 평균 절댓값 차이 0이었다. 이는 검사한 정지 구간의 안정성이다. 공간 계단 현상이 없다는 뜻이나 이동 중 품질 보장이 아니다.

이전 지터 On ⑤·⑥은 두 지터 위상이 번갈아 나와 정지 안정성 검사를 통과하지 못했다. 아래 시간은 P5/P6의 On 대조군을 사용해 Off와 같은 실행으로 대응시켰다. CGVQM은 이 On 선택 버전에서 미측정이다.

| 이전 구성 | Bistro AA ms | Minecraft AA ms | Bistro 정지 RGB 차이 | Minecraft 정지 RGB 차이 |
|---|---:|---:|---:|---:|
| ⑤ 지터 On 선택 | 0.103835 | 0.116448 | 1.223442 | 2.797890 |
| ⑥ 지터 On 선택 | 0.206974 | 0.287647 | 1.255586 | 2.954760 |

RGB 차이는 0~255 단위의 인접 프레임 평균 절댓값이며 후반 정지 구간 값이다. 이 실패를 일반 AA-Off/1X의 떨림으로 표현하지 않는다.

주 표 ⑤·⑥ Off의 화면 전체 대비 평균 선택 비율은 Bistro 2.5868%, Minecraft 17.3536%다. ⑤와 ⑥의 edge mask는 모든 캡처 프레임에서 일치했다. 검출 edge 중 이 비율만 선택했다는 뜻은 아니다.

## 5. 철회 전 판단과 당시 남은 비교 항목

- **정지 안정성:** 지터 Off ⑤·⑥에서 기존 교대 떨림이 해소됐다. ⑥의 공간 AA 보존도 검증됐다.
- **성능:** ⑥은 ④ 대비 Bistro에서 AA 시간 2.37% 감소, Minecraft에서 1.19% 증가했다. 두 장면 모두 빨라진 결과는 아니다.
- **품질:** ⑥의 CGVQM은 ④보다 Minecraft 이동 구간에서 높았고, Bistro 정지 전환에서는 낮았다. 전반적인 품질 우위로 단정하지 않는다.
- **미측정:** ①·③ CGVQM 2장면×2구간, 같은 계측·수명·reset 조건으로 묶은 최종 6구성 성능 행렬이 남아 있다. 전체 프레임 시간/FPS까지 6행 모두 채운 표도 아직 아니다.
- **개별 시각 문제:** 이동 고스팅·가려짐 해제·물체 움직임을 분리한 평가가 필요하다. 정지 RGB 차이와 CGVQM만으로 그 검증을 대신하지 않는다.

이 절의 해석은 당시 전체 화면 mask 경로의 기록이다. 새 구현의 실행 범위와 성능은 [⑤·⑥ 재구현 결과](rebuilt-edge-execution.md)를 사용한다.

## 6. 출처와 재현

이 보고서는 구현 변경·재빌드·새 GPU 측정 없이 고정 커밋의 PASS JSON을 읽어 생성했다. `comparison.json`에 반올림 전 수치, 측정 묶음, 정지 검사, 짝 비교, 모든 입력의 commit/path/SHA-256을 보존했다. 입력이 누락되거나 참조 조건이 다르면 생성기가 실패한다.

```powershell
python Tools/SMAA/summarize_six_cases.py
```

아래 고정 버전 상세 기록에 시각 자료, 실행 실패·재검증 이력 및 한계가 포함되어 있다.

- [①·②·④ 원본 기준선 상세 보고서](https://github.com/Anchovia/Adaptive-SMAA/blob/e14f122d841f432b9c633fdd480740e85fc8edff/Docs/Baseline-Restart/report.md)
- [③ Temporal-only 상세 보고서](https://github.com/Anchovia/Adaptive-SMAA/blob/e2bbf8711910d207365f687b7b0c37c03d54ae9d/Docs/Temporal-Only-Control/report.md)
- [⑤ 지터 Off 상세 보고서](https://github.com/Anchovia/Adaptive-SMAA/blob/2e3ac6ce21639552c8cf57c57d18e607a030e0e7/Docs/First-Edge-Pattern-Off/report.md)
- [⑥ 지터 Off 상세 보고서](https://github.com/Anchovia/Adaptive-SMAA/blob/556f2264dbfc3ccf6742c8b4c42d945d2ac0d9f9/Docs/Spatial-First-Edge-Pattern-Off/report.md)
