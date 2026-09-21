# Temporal 패스의 current 읽기 한 번으로 de-jitter 재사용

출발점 `6929181`, 브랜치 `experiment/temporal-pass-dejitter`.
목표는 추가 pass/texture/sample 명령 없이 현재 luma 선택식의 정지 떨림을 줄일 수 있는지 확인하는 것이다.
Original spatial SMAA, camera/depth reprojection On, paired projection/area pattern On,
Point history, 원본 velocity-alpha weight와 spatial-frame history를 유지한다.
기존 history Linear 실험을 결합하지 않는다. 최종 8-case 결과가 아닌 engineering ablation이다.

## 기존 구현과 현재 제약

`experiment/candidate-jitter-real-scene`의 `TSCMAADeJitterSpatialCS`는 전체 current spatial을
`UV + currentScreenJitter / resolution`에서 bilinear로 읽어 base를 만들고, 후보는 기존
indirect resolve로 덮어썼다. 결과는 `Docs/SMAA-Hybrid-Resolve-Ablation-Results-ko.md`다.
별도 pass 및 출력/feedback 구조를 가져오지 않고 좌표 보정식만 검토한다.

현재 선택은 current 색상을 읽은 뒤 luma 미분으로 결정된다. 기존 원위치 선택을 정확히
보존하면서 비후보만 다른 위치에서 읽으려면 일반적으로 두 번째 current 읽기가 필요하다.
따라서 이번 최소 구현은 모든 픽셀의 current 읽기를 보정하고, 그 값으로 새 선택을 한다.
후보 current, current alpha, 선택 마스크도 달라진다. 기존 hybrid의 정확한 재현이나
동일 선택식의 실행 구조만 바꾼 실험으로 표현하지 않는다.

History의 필터·UV와 velocity UV를 그대로 둔다. 그러므로 current만 보정한 진단이며
완전한 unjittered T2X reconstruction이라고 표현하지 않는다. 특히 candidate 경계/얇은 물체와
움직임에서 서로 다른 위치의 current/history 결합에 따른 한계가 있을 수 있다.

## 좌표와 sampler 근거

`Modules/Scene/vaCameraBase.cpp`의 projection translation은 X `+2*j.x/width`,
Y `-2*j.y/height`다. 화면 UV의 아래 방향 Y를 고려하면 geometry는 화면에서 `+j` 이동한다.
따라서 unjittered 위치를 근사하려면 jittered image를 `UV+j/resolution`에서 읽는다.
현재 wrapper의 S0 화면 jitter는 (+.25,+.25), S1은 (-.25,-.25)이며,
SMAA subsample index 1/2와 대응한다. 이미 전달되는 subsample index로 offset을 계산하므로
새 constant buffer나 per-frame upload를 추가하지 않는다. index 0은 offset 0이다.

기존 linear/clamp sampler의 `SampleLevel(...,0)`를 사용한다.
[Microsoft SampleLevel](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel),
[D3D11_FILTER](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_filter).
샘플 명령이 하나여도 bilinear는 주변 texel을 사용하므로 Point와 동일 비용을 가정하지 않는다.
RGBA를 함께 필터링하므로 velocity-alpha로 계산하는 실제 weight도 바뀔 수 있다.

## 대조군과 검증

성능 비교는 다음 다섯 mode다.

| 이름 | kind | current | 선택 |
|---|---:|---|---|
| O-T2X-R | 0 | 기존 Point | 전체 |
| ABL-ScalarWeight-001-R | 16 | 기존 Point | 기존 threshold .01 |
| ABL-ScalarCurrentLinear-001-R | 27 | 원위치 Linear | 원위치 필터 값, threshold .01 |
| ABL-CurrentDeJitter-R | 28 | 보정 위치 Linear | 전체 |
| ABL-ScalarDeJitter-001-R | 29 | 보정 위치 Linear | 보정된 값, threshold .01 |

Capture에는 원본 mask/spatial, 보정 mask/spatial 및 새로운 두 resolve의 반복을 추가해
장면별 11 mode×240 frame을 저장한다. 새 resolve의 최초 유효 history가 없는 frame에는
동일한 fullscreen draw에서 보정 spatial shader(kind 31)를 사용해 자기 current로 seed한다.
비보정 self-history와 섞는 첫 frame의 오차를 피하며 새 pass나 history copy는 없다.
이후 history 저장은 기존의 각 frame spatial 그대로다. 이 초기화 차이를 비용/품질에서 기록한다.

검사 항목:

- FXC native 8 variant와 기존 Scalar 2 variant 불변, 새 10 variant(R Off/On) 컴파일.
- resolve sample 명령 R On 3개/Off 2개; mask/spatial은 1개. Scalar 미분 2개, divergent branch 없음.
- CPU affine-image sign probe와 실제 GPU 보정 spatial의 linear-light CPU mirror 비교.
- 이상적 CPU mirror의 최대 RGB 차이 2 이하라는 초기 가정은 Minecraft frame 0에서 실패했다
  (최대 4, 평균 0.037140, 6,111,360 channel 중 7개가 3 이상). 허용값을 높여 PASS로 바꾸지 않는다.
  별도 sRGB texture에 같은 spatial PNG를 업로드해 실제 production sampling 함수를 실행한
  독립 GPU probe를 추가했고, 장면 출력과 최대 1 RGB 단계 이내인지 확인한다.
  CPU mirror 차이와 그 초기 가정의 통과 여부는 결과 JSON에 그대로 보존한다.
  이 probe는 데모의 패스가 아니며 품질 검증에서만 실행한다. 정확한 sampler/변환 오차의
  내부 원인은 분리하지 않았고, 이상적인 float64 CPU 식과 byte-exact라고 주장하지 않는다.
- 기존 capture의 native/spatial/mask/Scalar hash, 원위치 Linear control, 새 output 반복 hash.
- 새 mask가 선택한 픽셀은 FullDeJitter, 비선택은 DeJitterSpatial과 byte 일치. 최초 seed 일치.
- mask 변경률·선택률, 정지 RGB phase, 기준 영상 오차·윤곽·시간 변화와 비교 영상.

## 측정 조건

품질은 기존 Bistro/Minecraft의 240-frame 경로와 정렬된 supersample spatial proxy를 사용한다.
전역 shutter/지터 제거 또는 후보 확장은 추가하지 않는다. RGB reference proxy와 시간 변화
잔차만으로 절대 ghosting 감소 또는 시각적 우위를 단정하지 않는다.

성능은 품질 분석과 분리한 clean process, 30초 미측정 예열, 300-frame mode별 warmup,
4,800-frame×4회, 정순/역순 2회씩이다. SMAA/Spatial/Resolve/WholeFrame/WallFrame을 따로
보고한다. 한 process의 네 반복이며 독립성 또는 동등성을 증명하지 않는다.

```powershell
python Tools/SMAA/validate_temporal_dejitter.py
cmd /c Tools\SMAA\build_dejitter_probe.cmd
Tools/SMAA/run_temporal_dejitter.ps1 -Phase Capture -Scene minecraft
Tools/SMAA/run_temporal_dejitter.ps1 -Phase Capture -Scene bistro
Tools/SMAA/run_temporal_dejitter.ps1 -Phase Benchmark -Scene minecraft
Tools/SMAA/run_temporal_dejitter.ps1 -Phase Benchmark -Scene bistro
```
