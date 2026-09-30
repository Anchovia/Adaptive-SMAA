"""Write the final audit from completed, validated paired runs only."""
import json,statistics
from pathlib import Path
R=Path(__file__).resolve().parents[2];D=R/'Docs/Edge-Persistence-Cost-Audit'
A='A-CurrentEdge-Stencil';B='B-PreviousRawEdge-Depth';E='E-PreviousRawEdge-FirstStencil';O='O-T2X-R'
S='S-StorageOnly-Stencil';K='K-ConstantDepth-Stencil';P='P-UnionPrep-Stencil';L='L-PreviousRawEdge-ConservativeDepth'
labels={A:'⑥ 현재 edge',B:'⑦ 기존 depth 전달',E:'⑦ 개선 stencil 전달',O:'④ 원본 SMAA T2X-R'}
data={scene:json.loads((D/(scene+'-benchmark.json')).read_text()) for scene in ['bistro','minecraft']}
captures={scene:json.loads((D/(scene+'-capture.json')).read_text()) for scene in data}
audit=json.loads((D/'source-audit.json').read_text())
for scene,d in data.items():
    assert d['receipt']['executable_sha256'].lower()==audit['executable_sha256'].lower()
    assert all(v==0 for v in captures[scene]['mismatched_frames'].values())
    assert len(captures[scene]['selection_validation'])==43
lines=['# 직전 raw edge 유지: 비용 원인과 동일 출력 개선', '',
       '검증 브랜치: `validation/edge-persistence-cost-audit`. 렌더러 커밋: `9b9953e`.',
       '기존 ⑥/⑦ 및 ④는 서로 다른 case다. ⑦의 개선 전후는 선택 결과·출력이 같은 구현 변형이다.', '',
       '## 결과', '',
       'RTX 3060 Ti, DX11 Release x64, Ultra, 1920×1061, hidden, VSync Off. 장면별 같은 실행에서',
       '9조건을 300 warm-up + 4,800프레임 × 3회 측정했다. 반복별 정/역순을 교차했다.',
       'PNG·readback·invocation query는 Off. 변화율은 해당 실행의 ④를 분모로 계산하며 이전 실행의 절대값을 혼용하지 않는다.', '',
       '| 장면 | 구성 | 전체 AA ms | ④ 대비 | spatial ms | camera ms | temporal ms | temporal ④ 대비 |',
       '|---|---|---:|---:|---:|---:|---:|---:|']
for scene,d in data.items():
    m=d['means']
    for mode in [O,A,B,E]:
        v=m[mode];lines.append(f'| {scene} | {labels[mode]} | {v["SMAA"]:.6f} | {100*(v["SMAA"]/m[O]["SMAA"]-1):+.2f}% | {v["SF_Spatial"]:.6f} | {v["SR_CameraVelocity"]:.6f} | {v["SR_Resolve"]:.6f} | {100*(v["SR_Resolve"]/m[O]["SR_Resolve"]-1):+.2f}% |')
lines+=['','## 비용 분리','','| 장면 | 버퍼 교대 S−A | 고정 depth export K−S | union 준비 P−K | union temporal/gate B−P | 기존 ⑦−⑥ | 개선 ⑦−⑥ | 개선 ⑦ vs 기존 ⑦ |','|---|---:|---:|---:|---:|---:|---:|---:|']
for scene,d in data.items():
    m=d['means'];v=lambda x:m[x]['SMAA']
    lines.append(f'| {scene} | {v(S)-v(A):+.6f} ms | {v(K)-v(S):+.6f} ms | {v(P)-v(K):+.6f} ms | {v(B)-v(P):+.6f} ms | {v(B)-v(A):+.6f} ms | {v(E)-v(A):+.6f} ms | {100*(v(E)/v(B)-1):+.2f}% |')
lines+=['',
 '원인 분리의 핵심은 K다. 후보 판정용 이전 edge/velocity 읽기나 재투영 계산을 추가하지 않고 raster depth와 같은',
 '상수 1만 셰이더에서 출력한다. 원래 ⑥도 depth 쓰기는 켜져 있으므로 이 차이는 단순한 depth',
 'write On/Off가 아니다. FXC 명령 슬롯은 원래 38, K는 39이며 임시 레지스터 수는 5로 같다.',
 '고정 depth export만으로 큰 비용 증가가 재현되므로, 기존 ⑦의 추가 비용 대부분을 edge 저장/읽기의',
 '불가피한 비용으로 설명했던 해석은 정정한다. GPU의 세부 ROP/cache stall은 별도 counter로 확인하지 않았다.', '',
 'S−A 같은 작은 차이는 buffer 교대뿐 아니라 자원 주소/캐시 배치 등의 영향을 포함하며 순수 전송시간이 아니다.',
 'P−K는 union 계산과 데이터 의존 depth 출력 패턴 차이를 포함한다. B−P는 선택 영역 확대와 depth/stencil',
 'gate 차이를 함께 포함한다. 모든 차이를 개별 texture fetch의 독립 비용으로 환산하지 않는다.', '',
 '## 개선 코드', '',
 '원래 ⑦은 3차 spatial pass에서 union을 계산해 SV_Depth로 전달했다. 개선안은 1차 edge pass에서',
 '현재 edge가 없는 위치만 이전 raw edge를 point velocity로 재투영해 검사하고 기존 stencil에 union을 표시한다.',
 'raw RG에는 현재 프레임 edge만 저장한다. 3차 pass는 원래 NeighborhoodRetainPS로 돌아가며 temporal은',
 '기존 early stencil 검사 뒤 native resolve를 실행한다. 추가 draw/dispatch나 color copy는 없다.', '',
 '2차 spatial pass는 previous-only 위치에서도 실행되지만 raw RG=0으로 weight=0을 생성해야 한다.',
 '이로 인한 출력 변화가 없는지 raw edge와 current spatial DDS 및 최종 RGB로 검사했다.',
 '이는 SMAA edge 계산식, history sampler/weight/feedback, jitter/dilation을 바꾸는 품질 기법이 아니다.', '',
 '## 검증 및 범위', '']
for scene,c in captures.items():
    lines.append(f'- {scene}: A/B/E/④ 각 240프레임. E−B RGB mismatch 0; A/B/④와 보존된 캡처 mismatch 0. 43개 trace에서 E/B coverage, raw RG, current spatial DDS가 같고 비선택 출력은 current spatial과 같다. Pipeline query passing samples도 coverage와 일치했다.')
lines+=['- 기존 native shader 14개 DXBC가 기준 ⑥과 같다. 복사된 4종 edge 함수는 early discard→zero return 외 계산식이 같다.',
        '- 최초 8조건 Bistro capture 1,920프레임은 `bistro-depth-controls-capture.json`에 보존했다. A/S/K/D/P 동등성과 B/L 동등성도 240프레임으로 확인했다.',
        '- 최종 Bistro capture 이후 변경은 harness 보고 문구/설명 주석/공백 정리였다. renderer 계산식을 수정하지 않았고 최종 benchmark EXE SHA는 source-audit와 일치한다. Minecraft는 최종 EXE로 캡처했다.',
        '- 출력 동일성만 검증했으며 새 CGVQM 또는 품질 개선을 주장하지 않는다. 기존 ⑦에서 남아 있던 얇은 선 단절/반짝임 문제도 그대로다.',
        '- 이 두 camera-motion 장면/해상도/GPU의 제한된 검증이다. Resize/camera cut/object motion과 다른 GPU를 포함한 범용 검증 또는 최적 속도 한계 도달을 주장하지 않는다.', '',
        '## 반복별 전체 AA 변화율', '',
        '| 장면 | 비교 | run 0 | run 1 | run 2 |', '|---|---|---:|---:|---:|']
for scene,d in data.items():
    for control in [O,A,B]:
        vals=d['comparisons'][control][E]['SMAA']['paired_run_percent']
        lines.append(f'| {scene} | 개선 ⑦ vs {labels[control]} | '+' | '.join(f'{v:+.2f}%' for v in vals)+' |')
lines+=['','## 출처','','구현 계약과 GPU 처리 원리는 [NVIDIA shader guidance](https://developer.nvidia.com/blog/advanced-api-performance-shaders/),',
 '[Microsoft HLSL semantics](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-semantics),',
 '[Microsoft stencil operations](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_stencil_op)를 확인했다.',
 '[MJP의 depth export 실험](https://therealmjp.github.io/posts/to-earlyz-or-not-to-earlyz/)은 보조 근거다.',
 '현재 pass3는 DepthFunc ALWAYS로 모든 pixel을 실행하므로 단순히 Early-Z culling 상실이라고 단정하지 않는다.',
 'Conservative depth도 같은 선택을 유지하지만 이 구성의 주요 비용을 제거하지 못했다. 상세 조건은 [method.md](method.md).','']
for scene,d in data.items():lines.append(f'- {scene} benchmark: `{d["receipt"]["report"]}`')
(D/'results-ko.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Saved',D/'results-ko.md')
