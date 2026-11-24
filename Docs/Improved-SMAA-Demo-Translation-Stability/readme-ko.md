# 개선된 SMAA 데모의 평행 이동 안정성 검증

base 커밋은 `validation/improved-smaa-demo-temporal-toggle` afbaaca다. 기준선 `baseline/improved-smaa-demo` 1d54b7f와 toggle 브랜치 `experiment/improved-smaa-demo-temporal-toggle` 192a2ab는 건드리지 않았다. 데모가 쓰는 셰이더(Cross5 resolve, seed, neighborhood, edge)는 afbaaca와 같은 DXBC로 컴파일되는 것을 확인했고 진단용 변형은 이 브랜치에만 있다. 시간 측정은 하지 않았다.

브랜치

- `validation/improved-smaa-demo-translation-stability` (이 문서, afbaaca에서 시작)
- `experiment/improved-smaa-demo-temporal-toggle` 192a2ab (사용자가 돌려 본 Temporal 켜기/끄기 데모)
- `validation/improved-smaa-demo-temporal-toggle` afbaaca (그 검증, 이 브랜치가 harness를 이어받았다)

## 확인하려던 것

사용자는 toggle 데모로 Minecraft에서 수평이나 수직으로 움직일 때 temporal 안정성이 너무 떨어진다고 했다. 요청받은 원인 후보는 세 가지였다. (1) 평행 이동에서는 깊이마다 화면 속도가 달라 실루엣에서 Cross5가 history를 버린다. (2) 실시간 데모는 프레임 시간이 매 프레임 달라 속도 크기도 흔들리고 Cross5가 그 차이로 가중치를 낮춘다. (3) jitter가 없어 sub-pixel 평행 이동의 계단 crawl이 남는다.

## 방법

카메라는 데모의 free-flight 조작에서 A/D(수평)나 Q/E(수직) 한 키를 누르고 있는 움직임을 그대로 계산했다. 이동 속도 20, 1.4초에 걸친 0.3→1.0 가속, 입력 smoothing(1 − exp(−200 dt))이 컨트롤러와 같다. 시작 자세는 flythrough play time 2.0(c28~c31과 같은 자세로 Minecraft에서는 가까운 블록 두 개가 화면의 절반 넘게 차지한다)과 Minecraft의 play time 3.5(트인 지형)다. 대조로 같은 자세에서 움직이지 않고 0.4 rad/s로 yaw만 하는 실행을 더했다. yaw에서는 화면 속도가 깊이와 상관없다.

프레임 시간은 실제 데모에서 기록했다(`-translationDtRecord`, 보이는 창, UI 켬, VSync 끔, 1920×1061, 새 항목 Ultra, 같은 키 움직임). Minecraft는 평균 1.037 ms(약 964 FPS)였고 연속한 두 프레임의 시간 차이가 평균의 9.6%(p95 30%)였다. Bistro는 평균 2.47 ms(약 405 FPS), 17%(p95 64%)였다. 보고받은 약 300 FPS와 다르므로 고정 1/300초 조건을 더했다. 조건은 다음 네 가지이고 모두 0.5초 동안 같은 경로를 움직인다.

| 조건 | 프레임 시간 | 저장한 프레임 |
|---|---|---|
| fixed60 | 1/60초 | 정지 마지막 프레임과 이동 30프레임 전체 |
| fixed300 | 1/300초 | 정지 마지막 프레임과 0.4초 뒤 31프레임 |
| fixedmean | 기록 구간의 평균(Minecraft 1.036 ms, Bistro 2.500 ms) | 같은 방식으로 마지막 0.1초 |
| recorded | 기록한 값 그대로(300행부터) | 같은 방식으로 마지막 0.1초 |

mode는 Off(Temporal 끔, 같은 프리셋의 Adaptive SMAA 1X), On(데모의 Cross5), Fixed08(가중치 0.8 고정), Official1Tap(공식 SMAA처럼 history 위치 한 화소의 이전 속도만 비교), WeightDebug(On과 같은 가중치를 색으로 기록하고 4-이웃 상대 깊이 차도 함께 기록), SSRef(데모의 SuperSampleReference를 같은 자세로)다. 모두 Ultra, 고정 1920×1061 숨김 창, mode마다 history를 새로 시작하고 30프레임 정지 뒤 움직였다. 자동 노출은 매 프레임 바로 맞춘다(c28~c31과 같다). 실행마다 CMAA2 프로세스 0개, GPU P8, 60초 이상 입력 없음을 확인한 독립 프로세스 하나로 돌렸고 끝난 뒤 남은 프로세스는 0개였다.

지표는 다음과 같다. 어느 것도 ground truth는 아니다.

- tde60은 1/60초 떨어진 두 프레임 사이의 변화 가운데 SSRef에 없는 변화의 평균 |(out_k − out_k−s) − (ref_k − ref_k−s)|다. s는 1/60초에 해당하는 프레임 수다(fixed60 1, fixed300 5, Minecraft recorded 16, Bistro recorded 7). 60 Hz 화면에 실제로 보이는 프레임끼리의 흔들림에 가깝다. 연속한 두 렌더 프레임으로 잰 값(tde)도 따로 남겼다.
- 선택 화소는 그 프레임 WeightDebug에서 선택 경로가 resolve한 화소다. 그중 4-이웃과 상대 깊이 차가 10% 이상이면 깊이 경계(실루엣), 나머지는 질감 경계로 나눴다.
- edge strength는 luma Sobel 크기의 평균을 SSRef와 나눈 값이다. 1보다 작으면 SSRef보다 흐리다.

## 결과

전체 표는 `results-tables.md`, 원래 값은 `analysis/`에 있다. 아래 퍼센트는 On이 Off보다 tde60이 얼마나 다른지다(음수면 On이 안정적).

| 실행 | fixed60 | fixed300 | fixedmean | recorded |
|---|---:|---:|---:|---:|
| Minecraft 3.5 수평, 질감 경계 | +23.7% | +12.6% | +11.5% | +1.5% |
| Minecraft 3.5 수직, 질감 경계 | −2.6% | +21.4% | +13.0% | −1.4% |
| Minecraft 2.0 수직, 질감 경계 | +11.7% | +18.4% | +18.2% | −4.4% |
| Minecraft 2.0 수평, 질감 경계 | −0.1% | −1.5% | +3.1% | −3.9% |
| Minecraft 3.5 yaw, 질감 경계 | −3.8% | +7.6% | +2.7% | −1.4% |
| Minecraft 평행 이동 네 실행, 깊이 경계 | −1.8 ~ +1.4% | −5.5 ~ −12.1% | −11.3 ~ −15.4% | −9.2 ~ −16.6% |
| Bistro 수평, 선택 화소 전체 | −7.1% | −12.2% | −10.7% | −13.8% |
| Bistro 수직, 선택 화소 전체 | −10.3% | −13.1% | −11.6% | −15.7% |

Bistro에서는 모든 움직임과 조건에서 On이 Off보다 안정적이었다. Minecraft 평행 이동의 질감 경계는 고정 프레임 시간(60, 300, 기록 평균) 12개 경우 중 8개에서 On이 Off보다 11~24% 더 흔들렸다. 실루엣(깊이 경계)은 On이 대부분 나았다.

### 속도와 history 위치는 맞다

평행 이동에서는 화면 속도가 깊이에 따라 달라서 깊이를 잘못 복원하면 yaw에서는 드러나지 않는 오차가 생긴다. 이를 가리려고 On의 속도 텍스처를 DDS로 저장해(`-Velocity` 실행) Off 프레임 k−1을 s × velocity로 옮겨 프레임 k와 비교했다. s = 0.80~1.20 가운데 잔차가 가장 작은 값은 Minecraft 3.5 수평, 수직, Minecraft 2.0 yaw의 fixed60과 fixed300 모두 1.00이었다(예: 3.5 수평 fixed60 잔차 s=0.90 10.53, 1.00 7.93, 1.10 10.04). 3.5 수평 fixed60에서 64×64 조각의 위상 상관으로 잰 이동은 속도의 0.97배(p10~p90 0.90~1.03)였다. history를 가져오는 위치 자체는 맞다.

### 원인 1. Minecraft 질감 경계가 history 재표본화로 흐려지고 선명도가 출렁인다

Minecraft 블록 질감은 nearest로 확대된 픽셀 아트라서 가까운 면에서는 텍셀 경계가 거의 모두 SMAA 경계로 잡히고 선택 경로에 들어간다. 이 화소들은 Cross5 가중치가 높다(평행 이동 fixed300의 질감 경계 평균 가중치 0.60~0.73). 매 프레임 이전 출력을 Catmull-Rom 5-tap으로 소수 화소 위치에서 다시 표본화해 0.8로 섞으므로 움직이는 동안 텍셀 경계가 부드러워진다. 멈추면 표본 위치가 정수가 되어 Off와 같아진다.

- 선택 화소의 edge strength(SSRef 대비)는 움직이는 동안 Minecraft에서 On이 Off보다 0.3~7% 낮았다(예: 3.5 수평 recorded Off 1.006, On 0.978, 3.5 yaw Off 0.992, On 0.958). 정지 프레임에서는 두 값이 같았다. Bistro도 0.4~3.5% 낮았지만 아래처럼 흔들림은 늘지 않았다.
- Minecraft 3.5 수평 fixed300의 흙 블록 면(x=1008, y=880, 64×48)에서 1/60초 간격 edge strength의 상대 표준편차는 Off 1.1%, SSRef 1.0%, On 2.1%, Fixed08 2.6%였다. 평균은 Off 91.5, SSRef 93.1, On 90.1이었다. On은 더 흐리고 흐린 정도가 표본 위치에 따라 출렁인다.
- 실루엣에서 8화소 이상 떨어진 질감 경계만 화면 속도별로 나눈 fixed300 tde60에서도 On이 Off보다 컸다. 3.5 수평 0.5~1 px/frame +11.3%, 1~2 px/frame +43.4%, 3.5 수직 2~4 px/frame +56.5%, 4~8 px/frame +17.9%였고 yaw(Minecraft 2.0)는 +8.2~8.6%였다. 실루엣 근처 잔상과 상관없이 면 안쪽에서도 생기는 현상이고 가까운 면이 빨리 움직이는 평행 이동에서 더 컸다.
- Bistro 질감에는 이렇게 날카로운 텍셀 경계가 드물고 질감 경계의 tde60도 On이 계속 작았다.

### 원인 2. 화면 밖에서 들어오는 내용에 화면 가장자리의 history가 늘어붙는다

카메라가 위로 가면 내용이 화면 위에서 들어온다. 새로 들어온 화소의 history 위치(uv − v)는 화면 밖인데 resolve는 이를 검사하지 않고 Catmull-Rom 표본과 Cross5의 이전 속도 모두 가장자리 화소로 clamp한다. 그래서 이전 프레임 맨 윗줄 내용이 세로 줄무늬로 늘어나 섞이고 Cross5도 거부하지 못한다. Minecraft 2.0 수직 fixed300의 화면 맨 위(x=568, y=0, 64×14)에서 125~127프레임에 On과 Fixed08에만 갈색 블록 안 초록 세로 줄이 보였다(Off와 SSRef에는 없다). 화면 가장자리 32화소 띠는 화소의 약 9%인데 On이 Off보다 나빠진 양 가운데 이 띠의 비중이 Minecraft 2.0 수직 fixed60에서 43%, 3.5 수직 fixed300에서 31%, 3.5 yaw fixed60에서 24%였다(다른 경우 9~17%, Bistro 2~5%).

### 가설 1. 실루엣의 Cross5 거부는 맞지만 On을 Off보다 나쁘게 만들지는 않는다

깊이 경계 화소 중 가중치 0.4 미만 비율은 평행 이동에서 fixed60 85~96%, fixed300 54~89%, 약 1 kHz 10~77%였고 yaw에서는 0~3%였다. 평행 이동의 시차가 실루엣에서 Cross5를 크게 작동시키는 것은 맞다. 그래도 깊이 경계의 tde60은 fixed300과 약 1 kHz에서 On이 Off보다 5~17% 작았고 fixed60에서는 비슷했다. 거부를 없앤 Fixed08은 선택 화소 tde60이 Off보다 Minecraft 평행 이동에서 15~627%, Bistro 평행 이동에서 2~59% 커서 거부가 잔상을 막고 있다. 거부는 실루엣에서 On의 이득을 줄일 뿐 나빠지는 원인은 아니었다. 다만 거부가 덜 된 실루엣 화소에서는 가까운 블록 가장자리가 뒷면 색을 끌어오는 경우가 있었다. Minecraft 2.0 수직 fixedmean의 x=1332 세로선에서 실루엣 마지막 어두운 화소가 Off 73, SSRef 65, On 99, Fixed08 167이었다.

### 가설 2. 프레임 시간 변동은 가중치를 낮추지만 흔들림을 늘리지 않았다

기록한 프레임 시간을 쓰면 같은 평균의 고정 값보다 질감 경계 가중치가 크게 낮아졌다(0.4 미만 비율 Minecraft 3.5 수직 32.7% 대 2.1%, 2.0 수직 25.1% 대 1.7%, Bistro 수직 17.6% 대 1.3%). 그런데 On/Off 차이는 모든 평행 이동 실행에서 recorded 쪽이 더 좋았다(Minecraft 3.5 수평 −1.6% 대 +6.2%, 2.0 수직 −8.1% 대 +8.0%, Bistro 수직 −15.7% 대 −11.6%). Minecraft에서는 history를 덜 쓰면 원인 1의 흐림이 줄기 때문이다. 이 가설은 흔들림의 원인으로 지지되지 않았다.

### 가설 3. jitter 없음과 높은 프레임 속도 때문에 화면에 보이는 이득이 작다

가중치 0.8은 프레임 단위라서 약 1 kHz에서는 history가 약 5 ms만 남는다. Minecraft 2.0 수평 recorded에서 연속한 렌더 프레임 사이의 tde는 On이 Off보다 39% 작았지만 1/60초 간격 tde60은 7%만 작았다. 3.5 yaw recorded도 33% 대 4%였다. jitter가 없어 history에는 같은 계단 모양이 조금씩 밀린 것만 쌓이므로 60 Hz로 보이는 프레임끼리의 crawl을 거의 줄이지 못한다. 고정 60 Hz에서는 프레임당 이동이 커서 실루엣과 일부 질감 경계가 거부되어 역시 이득이 작다. 거부가 거의 없는 yaw에서도 Minecraft의 1/60초 이득은 3.5 자세 −6.8~+3.9%, 2.0 자세 −6.3~−13.9%였다. jitter 자체를 따로 넣어 본 실험은 하지 않았다.

### 정리

측정한 실제 속도(약 964 FPS) 조건에서 Minecraft 평행 이동의 On은 Off와 거의 같거나 조금 나았다(선택 화소 −1.6~−8.1%). 보고받은 300 FPS 근처(fixed300)에서는 Minecraft 평행 이동 네 실행 중 세 곳에서 질감 경계가 On에서 13~21% 더 흔들렸다. 사용자가 본 불안정은 Cross5의 실루엣 거부나 프레임 시간 변동이 주원인이 아니다. Minecraft 픽셀 아트 질감이 history 재표본화로 움직이는 동안 흐려지고 출렁이는 것과 화면 가장자리로 들어오는 내용의 clamp 줄무늬가 겹친 결과로 보인다. 그 위에 프레임 단위 가중치라서 높은 FPS에서는 60 Hz 화면에 보이는 안정화가 원래 작다. 사용자 PC의 실제 FPS와 창 크기는 확인하지 못했다.

## 직접 본 프레임

원본 PNG를 nearest로 확대한 시트를 직접 열어 확인했다. GIF는 같은 ROI의 모든 저장 프레임을 Off, On, Fixed08, Official1Tap, SSRef 순으로 나란히 놓은 느린 재생(8 프레임/초)이고 시트 판단은 정지 프레임으로 했다.

| 시트 | 조건, ROI, 프레임 | 본 것 |
|---|---|---|
| `sheets\minecraft35_h\sheet_fixed300_x1008_y880.png`, `sheet_fixed300_s5_x1008_y880.png` | Minecraft 3.5 수평 fixed300, x=1008 y=880 64×48 ×4, 121~128프레임 연속과 125~150프레임 1/60초 간격 | 가까운 흙 블록 텍셀이 On, Fixed08, Official1Tap에서 Off와 SSRef보다 흐리다 |
| `sheets\minecraft_v\sheet_fixedmean_x1312_y352.png` | Minecraft 2.0 수직 fixedmean, x=1312 y=352, 431~438프레임 연속 | 가까운 블록 아래쪽 실루엣 화소가 On에서 밝아지고 Fixed08에서 크게 밝아진다 |
| `sheets\minecraft_v\sheet_fixed300_s5_x568_y0.png`, `zoom_silhouette_ghost_x568_y0.png` | Minecraft 2.0 수직 fixed300, x=568 y=0, 125~150프레임 1/60초 간격과 120~127프레임 연속 ×8 | 화면 위에서 들어오는 갈색 블록에 On과 Fixed08만 초록 세로 줄이 섞인다(125~127) |
| `sheets\bistro_h\sheet_fixed300_s5_x928_y504.png` | Bistro 수평 fixed300, x=928 y=504, 125~150프레임 1/60초 간격 | On은 Off, SSRef와 거의 같고 Fixed08에만 기둥 가장자리 잔상선이 있다(140, 145) |

시트와 GIF는 `D:\SMAAResearchCaptures\c32\sheets\` 아래에 있다(Git에 넣지 않음). 이 비교는 원인 확인용이며 화질 우열 판정은 아니다.

## 고칠 방향 후보

채택은 사용자 결정이다. 아래는 이번 증거로 고른 후보이고 아직 하나도 구현하거나 측정하지 않았다.

| 후보 | 기대 효과 | 단점과 확인할 것 |
|---|---|---|
| 1. history 위치가 화면 밖이면 가중치 0 | 원인 2의 가장자리 줄무늬가 사라진다. 비교 한 번이라 비용이 거의 없고 화면 밖 history는 언제나 틀린 값이라 잃는 것이 없다 | 가장자리 띠만 고친다(이번 측정에서 On 악화분의 9~43%). 면 안쪽 흐림은 그대로다 |
| 2. history를 현재 3×3 이웃 범위로 clamp | 원인 1의 흐림과 출렁임, 실루엣이 뒷면 색을 끌어오는 경우를 함께 줄일 수 있다 | temporal 평활도 줄어든다. 예전 선택 경로 실험의 (a) clamp를 Cross5와 함께 쓰는 형태라 그때 문제였던 깜빡임과 비용을 다시 재야 한다. Cross5가 없앤 1px 선이 다시 생기는지 확인해야 한다 |
| 3. 더 날카로운 history 표본(16-tap Catmull-Rom 등) | 5-tap 근사의 흐림을 줄여 원인 1을 낮춘다 | 표본 수와 비용이 늘고 링잉이 생길 수 있다. 소수 위치마다 남는 흐림이 완전히 없어지지는 않는다 |
| 4. 프레임 시간에 맞춘 가중치(w = 1 − 0.2^(dt·60))와 dt로 나눈 Cross5 | 높은 FPS에서도 60 Hz 기준으로 같은 길이의 history를 써서 가설 3의 작은 이득을 키운다 | history를 더 오래 쓰므로 원인 1의 흐림과 실루엣 잔상이 늘 수 있다. Fixed08 결과처럼 거부가 약해지면 크게 나빠진다. 1이나 2와 함께가 아니면 권하지 않는다 |
| 5. Cross5 유지 | Fixed08은 모든 경우 훨씬 나빴고 Official1Tap은 Cross5와 비슷하거나 조금 나빴다 | 가중치 식을 바꾸는 것만으로는 이번 문제가 풀리지 않는다 |

먼저 해 볼 만한 것은 위험이 거의 없는 1이고 Minecraft 질감 문제는 2나 3을 별도 실험 브랜치에서 비교해야 한다.

## 이번 브랜치에서만 바꾼 것

- `SelectedTemporal.hlsl`에 `SelectedResolveFixed08PS`, `SelectedResolveOfficial1TapPS`, `SelectedResolveWeightDebugPS`, `SelectedNeighborhoodZeroPS`를 더했다. 데모가 쓰는 진입점 네 개는 afbaaca와 같은 DXBC다.
- `SMAA::resolveVariant`와 `vaSMAAWrapper::SetResolveVariant`, `SaveVelocityForValidation`, `CMAA2Sample::GetFreeFlightControllerForValidation`
- `Projects/CMAA2/TranslationStability.inl`(`-translationCapture`, `-translationDtRecord`), 실행 스크립트의 Translation, DtRecord mode와 `-Velocity`, `-StartTime`, P8을 90초까지 기다리는 처리
- `Tools/Validation/analyze_translation_stability.py`, `translation_sheets.py`, `translation_sharpness.py`, `translation_speed_bins.py`, `verify_translation_velocity.py`, `translation_tables.py`

## 실행 기록과 한계

- 실행 기록은 `runs.json`에 있다. dt 기록 2회, 평행 이동과 yaw 캡처 9회, 속도 저장 3회가 PASS였다. 3.5 수직의 첫 실행은 시작 2초 만에 0xC0000409로 끝나 프레임을 하나도 저장하지 못했고 다시 돌린 실행은 PASS였다. 다시 생기지 않아 원인은 확인하지 못했다.
- 변형 설정이 SMAA에 전달되지 않은 상태로 찍은 첫 Minecraft 두 실행은 결과에서 빼고 지웠다.
- 저장 공간 때문에 fixed60을 뺀 조건은 마지막 0.1초만 저장했다. 조건마다 화면 내용이 달라 조건끼리의 절대값은 비교하지 않았다.
- 실제 키 입력이나 마우스 회전이 섞인 움직임은 재현하지 않았다. 사용자 PC의 실제 FPS와 창 크기, 화면 주사율은 모른다.
- SSRef는 공간 supersample 기준이라 temporal ground truth가 아니다. tde60은 SSRef와 다른 변화를 재는 상대 지표다.
- 고칠 방향 후보는 구현하지 않았다.

## 자료

- 이 폴더: `results-tables.md`, `analysis/*.json`(실행별 요약, 속도 검사, 속도별 질감 경계, edge strength), `runs.json`
- 캡처(Git에 넣지 않음): `D:\SMAAResearchCaptures\c32\`의 `tr-m35-h`, `tr-m35-v`, `tr-m35-y`, `tr-m-h`, `tr-m-v`, `tr-m-y`, `tr-b-h`, `tr-b-v`, `tr-b-y`, 속도 저장 `vel-m35-h`, `vel-m35-v`, `vel-m-y`, 프레임 시간 `dt-m\dt.csv`, `dt-b\dt.csv`, 분석 `analysis\`, 시트와 GIF `sheets\`
