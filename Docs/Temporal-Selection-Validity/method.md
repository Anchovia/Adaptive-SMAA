# Temporal 선택 조건의 유효성: 선행 offline gate

시작점 3bede90, branch experiment/temporal-pass-selection-validity.
기존 패스 안의 current/history/velocity-alpha weight만 사용한다. 추가 pass, 후보 확장,
별도 history feedback, object motion, Adaptive 공간 처리는 추가하지 않는다.
원본 O-T2X-R과 직전 선택적 paired 구현을 보존한다.

먼저 이전 캡처를 재사용하여 history 결합이 출력에 주는 영향의 크기를 분석한다.
새 renderer 구현이나 threshold를 선택하기 전에 다음 조건을 기록한다.

- Native 입력: 기존 current spatial과 원본 T2X-R 결과.
- Paired 입력: corrected spatial과 full paired 결과. 기존 gradient 선택은 대조군.
- 두 입력 계열을 따로 분석해 선택식 변경과 재구성 필터 변경을 혼동하지 않는다.
- CPU feature proxy는 sRGB PNG를 linear로 역변환한 뒤 full/current 차이의 RGB max다.
  실제 shader의 `weight * max(abs(history-current))`에 대응하는 근사다.
  PNG 양자화 때문에 정확한 내부 shader 값이나 실제 GPU mask라고 표현하지 않는다.
- 큰 차이에서 결합(무시하기 어려운 변화를 안정화)과 작은 차이에서 결합
  (큰 불일치의 history 거부)을 모두 검사한다. RGB max로 luma-only 색상 누락을 피한다.
- absolute threshold: 0.00025/0.0005/0.001/0.002/0.004/0.008/0.016.
  relative threshold: 0.01/0.02/0.04/0.08 × max(current/full RGB, 0.01).
  relative proxy의 brightness에도 full result가 쓰인다는 근사를 명시한다.
- 정지의 두 위상 일관성, 선택률, reference MAE, 원본 대비 오차와 시간 변화 잔차를 비교한다.
  reference는 supersample spatial proxy이며 ghosting ground truth가 아니다.

두 장면 모두 frame 20/21, 80/81, 100/101을 development로, 140/141,160/161,
180/181,200/201을 validation으로 사용한다. 같은 경로의 상관된 pose이므로 독립 일반화
검증은 아니다. 모든 정해진 후보를 보고하며 장면별 다른 threshold를 고르지 않는다.
baseline보다 명확히 유망한 trade-off만 최소 GPU 구현으로 넘어간다. 단순히 full resolve에
가까워진 결과를 원본 T2X-R보다 품질이 좋아졌다고 부르지 않는다.

history를 읽은 뒤 선택하므로 이 조건은 history read를 절약하지 않는다. runtime 비용은
실제 GPU 구현 뒤 별도 smoke와 반복 측정으로만 판단한다. CPU 처리 시간이나 후보 비율을
GPU 속도로 환산하지 않는다. 생산 코드 변경 전 이 gate 결과를 별도 커밋으로 보존한다.
