"""Generate the current-read de-jitter report from validated capture/benchmark data."""
import json
from pathlib import Path
from analyze_temporal_dejitter import NATIVE, POINT, LINEAR, SCALAR, SLINEAR, read_receipt, sha

root=Path(__file__).resolve().parents[2]
out=root/'Docs/Temporal-DeJitter'
receipts=root/'tmp/temporal-dejitter-runs.json'
names={NATIVE:'원본 T2X-R',POINT:'Scalar 원위치 Linear',LINEAR:'전체 current de-jitter',
       SCALAR:'기존 Scalar',SLINEAR:'Scalar current de-jitter'}
qs,ps={},{}
for scene in ('bistro','minecraft'):
    qs[scene]=json.loads((out/f'{scene}-quality.json').read_text(encoding='utf-8'))
    ps[scene]=json.loads((out/f'{scene}-performance.json').read_text(encoding='utf-8'))
    for phase,data in (('Capture',qs[scene]),('Benchmark',ps[scene])):
        r,_,_=read_receipt(receipts,scene,phase)
        assert r==data['receipt']
    assert qs[scene]['mismatches']==0 and ps[scene]['validation']=='PASS'

lines=['# Current 읽기 한 번에 통합한 de-jitter 실험 결과','',
    '기존 hybrid de-jitter의 좌표식을 현재 temporal pixel shader에 적용했다. '
    '추가 pass·texture·샘플 명령 없이 current를 Linear로 한 번 읽으며 history는 Point를 유지했다. '
    '기존 luma 선택이 current 읽기 뒤에 있으므로 current 보정은 선택 영역도 바꾼다. '
    '이 실험은 비후보만 보정했던 예전 hybrid의 정확한 이식이 아니라 **current 읽기 재사용의 최소 진단**이다.','',
    '구현 커밋: `ddf512e`. 브랜치: `experiment/temporal-pass-dejitter`. [구현 근거·사전 조건](method.md).','',
    '## 검증','',
    '- 원본 shader 8 variant와 기존 Scalar 2 variant bytecode 불변. 새 10 variant 컴파일 및 sample/derivative/branch 검사 PASS.',
    '- 두 장면 11 mode×240 frame: pattern 설정 5,280회 PASS. 이전 native/spatial/mask/Scalar, 원위치 Linear 대조군 및 새 output 반복 hash 3,360회 mismatch 0.',
    '- 960 mode-frame의 선택/비선택 결과 일치 검사 PASS. 새 선택 영역은 FullDeJitter, 비선택 영역은 DeJitterSpatial과 일치.',
    '- 최초 history가 없을 때 새 두 mode는 같은 draw에서 de-jitter spatial로 seed한다. 새 pass는 없다. 원본 초기화는 유지했다.',
    '- 같은 EXE로 별도 clean process에서 품질 캡처와 성능 측정. 실행 전후 잔류 데모 0, timeout/완료 report 검증.', '',
    'EXE SHA-256: `'+qs['bistro']['receipt']['executable_sha256']+'`','',
    '## CPU mirror와 선택 변화','',
    'S0는 화면 (+.25,+.25) pixel, S1은 (-.25,-.25) pixel이다. 보정은 UV+jitter/resolution이며 '
    'CPU mirror는 기존 spatial PNG를 linear RGB로 변환한 후 같은 quarter-pixel bilinear를 적용해 다시 sRGB로 인코딩한다. '
    'GPU sampler/색 변환 정밀도 차이를 기록하며 byte-exact float mirror라고 표현하지 않는다.','',
    '초기의 이상적 CPU mirror 최대 2 RGB 단계 가정은 일부 frame에서 실패했다. 이를 숨기거나 허용값만 올리지 않고, '
    '같은 PNG를 별도 sRGB texture에 업로드해 production sampling 함수를 실행하는 GPU probe를 추가했다. '
    '이 probe는 데모 패스가 아니며 품질 검증에서만 실행했다. 내부 sampler/변환 오차의 원인을 완전히 분리한 것은 아니다.','',
    '| 장면 | 검사 frame | 이상적 CPU 최대 RGB 차이 | CPU 최대 평균 차이 | 별도 GPU probe 최대 RGB 차이 |','|---|---:|---:|---:|---:|']
for scene,q in qs.items():
    checks=q['cpu_spatial_mirror']
    lines.append(f"| {scene} | {len(checks)} | {max(v['max_rgb_error'] for v in checks)} | {max(v['mean_rgb_error'] for v in checks):.6f} | {max(v['uploaded_texture_gpu_probe_max_rgb_error'] for v in checks)} |")
lines+=['','| 장면·구간 | 기존 선택률 | 보정 후 선택률 | 선택 상태 변경률 | 기존에서 제거 | 새로 추가 |',
        '|---|---:|---:|---:|---:|---:|']
for scene,q in qs.items():
    for w,label in (('moving','이동'),('late_still','정지')):
        v=q['coverage'][w]
        lines.append(f"| {scene} {label} | {v['original_selected_percent']:.4f}% | {v['selected_percent']:.4f}% | {v['selection_change_percent']:.4f}% | {v['removed_percent']:.4f}% | {v['added_percent']:.4f}% |")
lines+=['','선택률은 혼합하는 픽셀 비율이다. 이 Scalar 구현은 velocity/history도 모든 픽셀에서 읽으므로 선택률 감소를 texture 읽기 감소로 해석하지 않는다.','',
        '## 정지 안정성 및 품질','',
        'RGB MAE/PSNR은 동일 pose supersample spatial proxy와 비교했다. 시간 변화 잔차는 '
        '`|(Yt−Yt-1)−(Rt−Rt-1)|`의 화면 평균이며 optical-flow 정렬 또는 순수 고스팅 지표가 아니다. '
        '윤곽 비율은 reference 대비 Sobel 강도다. 떨림 감소와 함께 윤곽 비율도 낮아지면 흐려짐에 의한 변화 가능성을 함께 본다.','']
for scene,q in qs.items():
    lines += [f'### {scene}','','| 구간 | 방식 | RGB MAE | PSNR dB | 시간 변화 잔차 | 윤곽/reference |',
              '|---|---|---:|---:|---:|---:|']
    for w,label in (('moving','이동 60–179'),('transition','전환 160–219'),('late_still','정지 200–239')):
        for m in (NATIVE,SCALAR,LINEAR,SLINEAR):
            v=q['windows'][w][m]
            lines.append(f"| {label} | {names[m]} | {v['rgb_mae']:.6f} | {v['psnr_db']:.3f} | {v['reference_delta_residual']:.6f} | {v['edge_reference_ratio']:.4f} |")
    lines+=['','| 방식 | 정지 RGB frame 종류 | 평균 RGB frame 변화 | 2-frame 간격 불일치 |','|---|---:|---:|---:|']
    for m in (NATIVE,SCALAR,LINEAR,SLINEAR):
        v=q['static_hashes']['late_still'][m]
        lines.append(f"| {names[m]} | {v['unique_rgb_frames']} | {q['windows']['late_still'][m]['rgb_step']:.6f} | {v['lag2_mismatches']} |")
    lines+=['']
summary=['## 핵심 결과','',
    '**추가 패스 없이 통합할 수 있었지만, 이번 current-only 방식은 채택하지 않는다.** '
    'Bistro에서는 일부 개선이 있었으나 Minecraft에서는 원래 안정적인 선택 픽셀에 새 떨림이 발생했다. '
    '아래 품질 변화는 기존 Scalar 대비이고, 비용 변화는 원본 T2X-R 대비다.','',
    '| 장면 | 이동 RGB MAE 변화 | 정지 RGB frame 변화량의 변화 | 전체 AA 시간 변화 |',
    '|---|---:|---:|---:|']
for scene in ('bistro','minecraft'):
    q,p=qs[scene],ps[scene]
    old,new=q['windows']['moving'][SCALAR],q['windows']['moving'][SLINEAR]
    old_s,new_s=q['windows']['late_still'][SCALAR],q['windows']['late_still'][SLINEAR]
    a=p['means'][SLINEAR]['SMAA']['mean_ms'];b=p['means'][NATIVE]['SMAA']['mean_ms']
    summary.append(f"| {scene} | {(new['rgb_mae']/old['rgb_mae']-1)*100:+.2f}% | {(new_s['rgb_step']/old_s['rgb_step']-1)*100:+.2f}% | {(a/b-1)*100:+.3f}% |")
summary+=['','원본 T2X-R의 후기 정지 RGB 변화량은 두 장면 모두 0이다. 지표 변화율은 지각 품질의 백분율이 아니다.','']
insertion=lines.index('## 검증')
lines[insertion:insertion]=summary
groups=json.loads((out/'static-groups.json').read_text(encoding='utf-8'))
lines+=['## 정지 화면의 실패 위치','','Frame 200/201의 두 위상을 비교했다. 후기 정지 전체 구간의 2-frame 간격 hash 일치는 별도로 확인했다. '
        '아래 분류는 관측 위치를 나눈 것으로 새 후보 규칙이 아니다.','',
        '| 장면 | 두 방식·두 위상에서의 선택 상태 | 화면 비율 | 기존 영역 내 RGB 변화 | 보정 후 영역 내 RGB 변화 | 보정 후 전체 변화 기여 |',
        '|---|---|---:|---:|---:|---:|']
group_names={'selected_in_both_methods_both_phases':'항상 선택',
             'unselected_in_both_methods_both_phases':'항상 비선택',
             'other_selection_changes':'그 외 선택 변화'}
for scene,data in groups.items():
    for v in data['groups']:
        lines.append(f"| {scene} | {group_names[v['group']]} | {v['pixel_percent']:.4f}% | {v[SCALAR]['conditional_rgb_step']:.6f} | {v[SLINEAR]['conditional_rgb_step']:.6f} | {v[SLINEAR]['full_frame_rgb_step_contribution']:.6f} |")
lines+=['','두 장면 모두 항상 비선택인 영역의 변화는 줄었지만, 항상 선택된 영역에는 기존 0이던 변화가 생겼다. '
        'Minecraft에서 그 영역은 화면의 약 48.9%이며 새 전체 RGB 변화 중 큰 부분을 차지한다. '
        '선택이 바뀌지 않은 픽셀에서도 악화되었으므로 마스크 변화만으로 이 결과를 설명할 수 없다. '
        'Current만 보정하고 previous spatial sample을 유지한 비대칭이 기존 T2X의 정지 두 표본 상쇄를 바꾼다는 해석과 부합한다.','',
        '정지 상태에서 history weight가 0.5인 경우, 원본은 두 위상에서 `(C0+C1)/2`로 같다. '
        '이번 변형은 `(D0(C0)+C1)/2`와 `(D1(C1)+C0)/2`가 되어 일반적으로 같지 않다. '
        '여기서 D0/D1은 각 위상의 current 좌표 보정이다. 이 식은 current-only 변경의 비대칭을 설명하며, '
        '움직임 중 가중치 변화·선택 변화의 모든 영향을 분리한 증명은 아니다.','',
        '## 성능','','RTX 3060 Ti, DX11, 1920×1061, 숨긴 창, VSync Off. 장면별 새 process, '
    '30초 미측정 예열, mode당 300-frame warmup 및 4,800-frame×4회. 정순/역순 2회씩이다. '
    'PNG·후보 readback·프레임별 pattern 검사를 끄고 CPU 영상 분석과 분리했다. '
    '한 process 안의 반복이며 독립 process 반복이나 동등성 증명이 아니다.','']
for scene,p in ps.items():
    lines += [f'### {scene}','','| 방식 | SMAA ms | 원본 대비 | Resolve ms | 원본 대비 | WholeFrame ms |','|---|---:|---:|---:|---:|---:|']
    for m in (NATIVE,SCALAR,POINT,LINEAR,SLINEAR):
        v,n=p['means'][m],p['means'][NATIVE]
        a,r,w=(v[k]['mean_ms'] for k in ('SMAA','Resolve','WholeFrame'))
        lines.append(f"| {names[m]} | {a:.6f} | {(a/n['SMAA']['mean_ms']-1)*100:+.3f}% | {r:.6f} | {(r/n['Resolve']['mean_ms']-1)*100:+.3f}% | {w:.6f} |")
    lines+=['','| 비교 | 지표 | 변화 ms | 변화 % | 느린 반복 | 정순 변화 ms | 역순 변화 ms |','|---|---|---:|---:|---:|---:|---:|']
    for c,b in ((SLINEAR,SCALAR),(SLINEAR,POINT)):
        for metric in ('SMAA','Resolve'):
            v=p['comparisons'][c+' minus '+b][metric]
            lines.append(f"| {names[c]} − {names[b]} | {metric} | {v['delta_ms']:+.6f} | {v['delta_percent']:+.3f}% | {v['slower_runs']}/4 | {v['forward_mean_delta_ms']:+.6f} | {v['reverse_mean_delta_ms']:+.6f} |")
    lines+=['']
lines+=['## 판정','','현재 읽기 한 번을 바꾸는 통합은 구현 가능했지만, 이번 current-only 최소 구현은 기본 방식으로 채택하지 않는다. '
    '비선택 영역을 보정하려던 변화가 원래 안정적인 선택 영역의 결합도 바꾸었고, Minecraft 정지와 이동 품질에서 퇴행이 나타났다. '
    'Bistro의 정지 수치 개선만으로 성공이라고 판단하지 않는다. '
    '이 결론은 이 current-only 구성에 한정되며 모든 단일 패스 de-jitter/선택적 temporal 방식의 불가능성을 증명하지 않는다.','',
    '## 해석의 범위','','현재 보정은 후보·비후보 모두에 적용되고 새 입력으로 선택하므로, 효과에는 current 필터링·선택 마스크·alpha 기반 weight 변화가 포함된다. '
    'History 필터, history UV와 velocity UV, 저장되는 spatial history는 그대로다. 따라서 완전한 de-jittered temporal reconstruction으로 부르지 않는다. '
    '예전 후보 목록 방식의 비용이나 source TSCMAA 성능으로도 해석하지 않는다.','',
    '정적 두 phase의 difference는 flicker 진단이며 RGB 변화 감소만으로 품질 우위를 확정하지 않는다. '
    'Reference는 2× 선형 해상도/frame 내 3×3 subpixel grid/8×MSAA의 spatial proxy로, 3×3 후보 확장이 아니다. '
    '현재 실험은 camera motion이며 object-motion/disocclusion의 일반적인 개선을 입증하지 않는다.','',
    '원시 경로·hash·mirror 오차·영상 manifest는 장면별 quality JSON, 100 timing 및 100 distribution 행/장면과 반복별 값은 performance JSON에 기록했다. '
    '고정 ROI의 4-way MP4(240 frame, 60 FPS, 전체 decode/PTS 검사), 고정 팔레트 0.5배속 GIF 및 원본 PNG 비교를 생성했다. '
    '영상은 압축/색 양자화를 포함하므로 수치 계산에는 PNG만 사용했다.','']
(out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
print(out/'report.md')
