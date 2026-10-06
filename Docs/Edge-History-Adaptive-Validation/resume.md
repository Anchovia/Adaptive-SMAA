# 2026-10-06 완료 기록

사용자가 승인한 ⑪ 성능 측정, 논문·공개 구현 기반 ⑫ 독립 구현·속도·품질 비교,
긴 GIF/MP4와 C·D 공간 정리를 완료했다. 진행 중인 benchmark/capture/model 작업은 없다.

⑪ 브랜치: `experiment/edge-persistence-resolved-rgb-feedback`.
최신 결과 `752390c` 및 `2e7136f`를 해당 원격 브랜치에 push했다.

⑫ 브랜치: `experiment/edge-history-adaptive-validation`.
공통 base는 `304f749`, 명시적 최소 의존성은 case.json에 기록했다.
구현 커밋 `98f88bc`는 push됐으며 최종 결과는 별도의 결과 커밋에 보존한다.

완료 범위:

- 원문 논문과 공개 Playdead 구현 검토, 원본 대비 변경·가정·라이선스 기록.
- Release build와 22개 shader 설정, 옛 control DXBC 보존.
- 두 scene seed/reset Test, 240-frame × 8조건 Capture 및 172 trace witness/scene.
- ④·⑩·⑪ 총 1,440 RGB control frame 일치. CPU ideal mirror와 GPU 필터의 한계 기록.
- 각 scene의 독립 clean process에서 300 warm-up, 4,800 frame × 6회 paired Benchmark.
- 두 scene 공식 CGVQM-2 보조 평가와 FFV1 decoded RGB/reference hash 확인.
- 짧은/긴 원본 PNG 연속 프레임 직접 검사. 실제 720-frame × 8조건 × 2scene 캡처.
- 두 긴 캡처의 첫 180프레임은 8조건 모두 짧은 캡처와 RGB 불일치 0.
- 두 scene/6 ROI 긴 GIF·MP4, 전체 8조건 영상, decoded frame 수·FPS·PTS 검증.
- C·D의 완료된 캡처를 SHA-256 동일 hardlink로 정리. 원본 pixel·경로 보존.

결론과 전체 비교: [report.md](report.md).
⑫ 공개 기본값의 전체 AA 변화는 ④ 대비 Bistro −6.20%, Minecraft +11.31%다.
⑥은 같은 측정에서 여전히 ④보다 빠르다. ⑫는 얇은 선 보존과 반짝임을 함께 해결하지
못해 채택하지 않았다. 기본 Off다. 최종 8-case 연구 방법의 확정이나 연구 불가능성의
증명이 아니다. ①·②·③·⑤·⑦·⑧의 과거 수치는 당시 paired 기준을 유지한다.

검토 자료:

- C:/Users/USER/Desktop/research/Deliverables/SMAA_12_Quality_20261006/comparison.html
- C:/Users/USER/Desktop/research/Deliverables/SMAA_12_Long_20261006/comparison.html
- D:/SMAAResearchCaptures/edge-history-adaptive-validation

다음 사용자의 영상 검토와 후속 실험 선택을 기다린다. 승인된 ⑪·⑫ 작업의 필수 단계는
남아 있지 않다. Renderer/default/후속 연구 항목을 임의로 변경하지 않는다.
