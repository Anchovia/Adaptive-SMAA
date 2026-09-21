# 2차 blend texture를 temporal에서 읽는 비용

시작점 f3f42cf, branch experiment/temporal-blend-weight-selection.
사용자 요청은 품질이나 후보 선택을 바꾸지 않고 기존 2차 패스 결과를 읽는 비용을 확인하는 것이다.
Original 공간 SMAA / 원본 O-T2X-R / camera-depth R On / paired jitter / spatial-frame history를 유지한다.
추가 패스, copy, texture, 후보 판단, early exit, filter 변경은 없다. 1차 edge texture 실험과 구분한다.

기존 GPU-resident RGBA8 blendRT를 SRV t9로 연결한다. CPU→GPU 데이터 복사가 아니다.
화면 전체에서 같은 texel의 RGBA를 Texture2D.Load로 한 번 읽는 조건이다.
3차 패스가 모으는 이웃의 가중치 세 번 읽기를 재현하거나 temporal 후보를 정하지 않는다.

사용하지 않는 읽기는 최적화로 없어질 수 있으므로 기존 runtime 상수 padding0을 0으로 설정하고
`nativeResolve + padding0 * probeRGBA`로 출력을 보존한다. 컴파일 시에는 상수가 0인지 알 수 없다.
이는 측정용 데이터 의존성이지 제안 알고리즘이 아니다. DXBC의 실제 t9 ld, 원래 세 sample,
마지막 산술 명령과 분기 부재를 확인한다. 최종 GPU 기계어 검증과 동일시하지 않는다.

성능 조건:

- O-T2X-R: 원래 shader, t9 연결 없음.
- ABL-BlendBindOnly-R: 원래 shader bytecode, t9 연결/해제만 추가.
- ABL-BlendReadControl-R: 같은 연결, 원본 출력 + runtime-zero × 기존 cbuffer float4.
- ABL-BlendReadOne-R: 같은 연결, 원본 출력 + runtime-zero × blendRT.Load(current texel).

Control과 One은 같은 마지막 vector 산술을 갖도록 bytecode를 확인한다.
One−Control은 texture 좌표/읽기/그에 따른 의존성과 자원 압력의 증분 대용값이고,
One−Native는 연결·측정용 산술까지 포함한 관측 비용이다. 둘 다 순수 DRAM 전달 지연으로 부르지 않는다.
네 방식의 캡처는 원본 PNG RGB와 byte/hash 일치를 검사한다. PNG에는 alpha가 저장되지 않는다. 별도 observable 진단에서는
동일 One shader의 scale을 1로 바꿔 실제 blend 값이 출력에 영향을 주는지 확인하고 timing에서 제외한다.
기존 shader 불변, first-frame seed와 jitter pairing도 확인한다.

RTX 3060 Ti / DX11 / Ultra / 1920×1061 / VSync Off / hidden engineering 측정이다.
이전 실험과 같은 240-frame 경로를 유지한다. 모든 capture frame을 렌더하되 10개만 저장한다.
두 장면 각각 smoke 후 30초 예열, mode당 300 warm-up, 4,800 frame×4회 교차 순서로 비교한다.
PNG와 readback/분석은 timing과 분리한다. CMAA2 명령마다 fresh process, 종료/완성 report 검증을 적용한다.
결과를 final 8-case나 품질 개선, 모든 장면의 데이터 이동 비용으로 일반화하지 않는다.

공식 의미 확인:
- [Microsoft Texture.Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load): 정수 texel 좌표, mip level, filtering 없는 읽기.
- [Microsoft PSSetShaderResources](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-pssetshaderresources): SRV를 pixel stage에 연결. 출력과 겹치는 자원은 동시에 연결하지 않는다.
