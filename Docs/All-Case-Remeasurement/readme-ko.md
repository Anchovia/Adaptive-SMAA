①~⑰의 독립 소스를 고정하고 속도·품질을 다시 측정했다. 실행 목록, branch/commit,
생산 소스 해시는 protocol.json, 실행 파일과 결과 CSV 해시는 run-provenance.json에 있다.
이 17개는 과거 연구 항목의 비교이며 최종 Original/Adaptive × Standard/Selective ×
reprojection Off/On 8-case 행렬을 대체하지 않는다.

스텐실 초기화가 수정된 대응 기준선을 사용했다. Original 공간 SMAA가 필요한 경로의
전용 stencil을 edge 단계 전에 초기화하며, 사용하지 않는 ①·③에 불필요한 clear를
추가하지 않았다. 이 수정은 Intel CMAA2 sample의 SMAA 통합 코드 문제를 바로잡은 것으로,
SMAA 알고리즘 자체의 결함이나 선택적 temporal 알고리즘의 성과로 표현하지 않는다.

성능은 RTX 3060 Ti, DX11 Release x64, Ultra, 1920×1061, hidden/windowed, VSync Off에서
장면별 300 warm-up + 4,800프레임 × 6회 측정했다. 각 번호의 동일 실행 파일 안에서
대상과 수정된 원본 ④를 교차 측정했다. 백분율의 분모는 해당 실행의 ④이며 공통 표의
④ 절대값을 모든 행의 분모로 사용하지 않았다. 공간·선택 준비, camera velocity,
temporal resolve와 전체 AA 비용을 구분했다. 전체 렌더링 시간의 변화는 performance.json의
whole_frame에서 별도로 확인한다. 전체 AA 감소율을 전체 GPU frame 감소율로 읽지 않는다.

속도 측정에는 캡처·진단 query·GPU readback을 사용하지 않았다. 각 Smoke/Benchmark/Capture
명령은 독립 CMAA2 프로세스이며 앞뒤 잔류 프로세스 0개와 완성된 CSV의 Aggregate PASS를
확인했다. 정상 완료된 명령 102개만 정식 자료로 채택했고 초기 준비 실패 4개는
excluded-runs.json에 따로 보존했다. 초기 정지 3개의 정확한 원인은 확정하지 않았다.

품질은 두 장면 각 240프레임을 새로 캡처했다. same-index supersample 공간 참조에 대한
PSNR·luma SSIM과, temporal 없는 ②의 공통 optical flow로 정렬한 ROI 잔차를 계산했다.
이전 CGVQM 점수를 새 점수로 옮겨 쓰지 않았으며 이번에는 CGVQM 모델을 재실행하지 않았다.
공간 참조는 temporal ground truth가 아니다. 잔차가 낮아도 흐림이나 선 소실일 수 있다.

전체 화면과 의자·창문·Minecraft 경계·나뭇잎·잔디의 원본 PNG를 직접 열었다. 이동
f126~131, 정지 전환 f178~183, 실패 주변 f124~133, 정지 f230을 검사했고 ⑫은 f234~239를
추가 검사했다. visual-inspection.json과 completion-audit.json에 실제 검사 범위,
수치 예외와 검사 sheet의 해시를 기록했다. 생성한 GIF를 직접 재생 관찰했다고 주장하지
않는다. ④ vs 각 번호의 두 방식 비교 GIF 80개는 f60~209를 건너뛰지 않고 0.5배속으로
제공한다. 모든 GIF의 150프레임·총 5초를 확인했다. 팔레트 변환이 없는 PNG가 판정 기준이다.

새 ④의 총 480프레임은 기존 검증된 ④와 RGB hash mismatch 0이다. 각 번호 실행의
native ④도 새 공통 ④와 일치한다. ⑦↔⑧과 ⑧↔⑨는 두 장면 240프레임씩 모두 일치한다.
⑧은 비용 감사의 FirstStencil, ⑨는 velocity integer Load 방식이다.

⑥은 ④ 대비 전체 AA가 Bistro 15.11%, Minecraft 4.12% 감소했지만 이동 중 품질 문제가
남아 있다. ⑰은 Bistro 6.79% 감소, Minecraft 9.46% 증가로 일관된 성능 우위가 아니다.
⑬은 이번 공간 참조 점수가 가장 높지만 이것을 temporal 품질 전체의 최우수로 확정하지
않는다. ⑭·⑰의 움직임 보정 잔차가 더 낮은 것과 별개로 Minecraft f128·f130의 가는
경계와 Bistro 의자의 구조 보존 실패가 남아 있다.

③·④는 원본 paired pattern On, ⑤~⑰은 Off다. 모든 temporal 구성의 reprojection은
camera/depth만 처리한다. 후보 확장, object-motion velocity, Adaptive 공간 처리의
효과는 이번 비교에 섞지 않았다. ⑮·⑯·⑰은 각각 ⑭에 clipping, sampling, 색 혼합을
독립 적용한 것으로 세 요소를 순차 누적한 구현이 아니다. 확보 TSCMAA 전체의 exact port로
표현하지 않는다.

결과 표는 comparison.md, 원시 지표 요약은 performance.json/quality.json, 검증 완료
목록은 completion-audit.json이다. 대용량 원본 캡처·GIF·실행 파일은 Git에 넣지 않았다.
로컬 GIF 갤러리는 Deliverables/SMAA_All_17_Remeasurement_20261007/comparison.html이다.
