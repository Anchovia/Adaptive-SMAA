# First-edge 선택 구현 품질 평가 계획

구현 고정점 `be93be3`, `experiment/temporal-first-edge-selective`에서 수행한다.
셰이더/선택식/지터/weight/history topology를 변경하지 않고 연속 capture 명령만 추가한다.
Original 공간 SMAA, camera/depth reprojection On, 기존 paired jitter와 spatial-frame history.
최종 8-case나 object-motion gate가 아닌 기존 두 실제 장면의 camera-path engineering 평가다.

## 조건

- Bistro/Minecraft, DX11, Ultra, 1920×1061, fixed 60 Hz.
- 기존 240-frame path: 0~59 still, 60~179 moving, 180~239 still. 전체를 매 mode 렌더·저장한다.
- Native O-T2X-R, 새 ABL-FirstEdge-Reuse-R, current spatial, 실제 raw edge RG,
  selective repeat의 다섯 mode. 각 mode는 동일 warm-up와 reset을 적용한다.
- Capture는 fresh process와 timeout을 사용하며 GPU timing과 섞지 않는다.
- 원본 240 frame을 기존 supersampling reference와 함께 캡처한 원본 영상에 hash bridge한다.
  Reference report hash, frame/size, pixel hash를 검증한다. Bridge 실패 시 참조 재사용을 중단한다.
- 모든 frame의 selected=native/nonselected=current 및 selective repeat RGB exact를 확인한다.
- 정지 분석은 initial 20~59, late 200~239; 이동 60~179; 전환 160~219를 사전 지정한다.

## 평가

- RGB MAE/PSNR, sampled luma SSIM, Sobel magnitude/reference로 공간 오차와 윤곽을 비교한다.
  Gradient 증가는 선명도 이득뿐 아니라 aliasing 때문일 수도 있다.
- 인접 RGB 변화, reference의 luma 시간 변화와의 잔차, 정지 두 위상 반복을 분석한다.
  정지에서는 mask always-selected/always-unselected/switching 영역별 변화 기여를 분리한다.
- CGVQM-2는 기존 공식 runner로 moving 120 frame, transition 60 frame에서 native/selected를
  동일 supersampling spatial reference와 비교한다. Lossless FFV1 RGB round-trip 검증을 유지한다.
  이 점수도 순수 ghosting 계측이나 temporal ground truth로 표현하지 않는다.
  Native는 기존 점수를 재사용하되 index를 포함한 test/reference pixel stream hash,
  공식 commit, frame 범위와 설정, Torch/CUDA 버전 일치를 확인한다. Selected만 새 실행한다.
- Full-frame와 기존 screen-fixed ROI(사전 지정 Bistro 420,590,900,910;
  Minecraft 720,240,1200,560)의 reference/native/selected 비교 MP4 및 반속 GIF,
  원본 PNG sequence sheet와 정지 차이 증폭 이미지를 만든다.
- MP4 frame 수/FPS/PTS를 검사한다. 압축/축소/GIF palette 한계를 명시하고 PNG 지표로 보완한다.
- 품질 개선을 구현 중에 섞지 않는다. 단독 회전, 독립 물체 운동, disocclusion ground truth 및
  다양한 장면에 대한 보편적 품질 결론은 이 gate로 내리지 않는다.

## No-TAA 추가 대조군

- 기존 동일 실행의 `DBG-CurrentSpatial-R` 240-frame capture를 재사용한다. 현재 spatial
  SMAA 색상만 출력하며 temporal 결합은 하지 않는다. Paired projection jitter/subsample
  pattern은 유지하므로, 지터를 끈 일반 SMAA 1X 또는 AA Off 결과와 구분한다.
- 동일 moving 60~179 / transition 160~219, 동일 SS spatial reference, 공식 CGVQM-2 설정으로
  두 장면 총 네 clip을 추가 측정한다. 기존 native/selected 결과 파일 hash와 현재 PNG의
  indexed pixel stream hash를 재검증한 뒤 세 방식의 점수를 비교한다.
- No-TAA의 lossless RGB round-trip, frame/해상도/참조 hash, 공식 commit와 Torch/CUDA
  일치를 검증한다. 셰이더·캡처·기존 성능 결과는 변경하지 않는다.
- 이 대조군은 기존 지터 조건에서 temporal 결합의 영향을 분리한다. 지터를 제거한
  spatial-only 방식의 품질이나 순수 고스팅 감소를 이 결과로 대신 판단하지 않는다.
