"""Summarize validated contribution-gate captures and matched timing runs."""
import json, statistics as st
from analyze_temporal_contribution import OUT, MODES, NEW, NATIVE, FULL, OLD

names={NATIVE:'원본 T2X-R',FULL:'Full paired',OLD:'기존 paired 선택',NEW[0]:'새 Native 선택',NEW[1]:'새 paired 선택'}
lines=['# Contribution 선택식: 검증된 GPU 결과 표','',
       '품질은 16-frame window 평균이다. RGB 변화는 인접 프레임의 채널 평균 절대 차이(0–255), MAE는 supersample spatial proxy 대비다.','']
comparisons={}
exe_hashes=set()
for scene in ('bistro','minecraft'):
    q=json.loads((OUT/f'{scene}-quality.json').read_text())
    t=json.loads((OUT/f'{scene}-Benchmark.json').read_text())
    smoke=json.loads((OUT/f'{scene}-Smoke.json').read_text())
    assert t['validation']==smoke['validation']=='PASS'
    assert q['selection_mismatches']==0 and q['baseline_hash_comparisons']==245
    for x in (q,t,smoke):exe_hashes.add(x['receipt']['executable_sha256'])
    lines.extend([f'## {scene}','', '| 구간 | 방식 | RGB MAE | 인접 RGB 변화 | reference 시간차 잔차 | gradient/reference |',
                  '|---|---|---:|---:|---:|---:|'])
    for window,ms in q['windows'].items():
        for m,v in ms.items():
            lines.append(f"| {window} | {names[m]} | {v['rgb_mae']:.6f} | {v['rgb_step']:.6f} | {v['reference_delta_residual']:.6f} | {v['gradient_reference_ratio']:.6f} |")
    lines.extend(['','| 구간 | 방식 | 선택 픽셀 평균 / 2,037,120 | 선택률 | mask 전환률 |','|---|---|---:|---:|---:|'])
    for window,ms in q['coverage'].items():
        for m,v in ms.items():
            lines.append(f"| {window} | {names[m]} | {v['selected_pixels']:.1f} | {v['selected_percent']:.4f}% | {v['switch_percent']:.4f}% |")
    lines.extend(['','| 방식 | 전체 SMAA ms ± run SD | Resolve ms | Spatial ms | WholeFrame ms |','|---|---:|---:|---:|---:|'])
    for m,v in t['means'].items():
        rs=[r['mean_ms'] for r in t['timing_rows'] if r['mode']==m and r['metric']=='SMAA']
        lines.append(f"| {names[m]} | {v['SMAA']:.6f} ± {st.stdev(rs):.6f} | {v['Resolve']:.6f} | {v['Spatial']:.6f} | {v['WholeFrame']:.6f} |")
    pairs=[(NEW[0],NATIVE),(NEW[1],FULL),(NEW[1],OLD)]
    stats=[]
    lines.extend(['','| 비교(새−대조) | 지표 | 평균 차이 ms | 평균 차이 % | 각 repeat의 차이 ms |','|---|---|---:|---:|---|'])
    for new,base in pairs:
        for metric in ('SMAA','Resolve','WholeFrame'):
            lookup={(r['mode'],r['run']):r['mean_ms'] for r in t['timing_rows'] if r['metric']==metric}
            delta=[lookup[new,i]-lookup[base,i] for i in range(4)]
            mean=st.mean(delta);pct=100*(t['means'][new][metric]/t['means'][base][metric]-1)
            stats.append(dict(new=new,base=base,metric=metric,delta_ms=mean,delta_percent=pct,paired_repeat_deltas_ms=delta,paired_sd_ms=st.stdev(delta)))
            lines.append(f"| {names[new]} − {names[base]} | {metric} | {mean:+.6f} | {pct:+.3f}% | "+', '.join(f'{d:+.6f}' for d in delta)+' |')
    comparisons[scene]=stats
    lines.extend(['','| 실행 | 결과 폴더 |','|---|---|'])
    for phase,x in [('Capture',q),('Smoke',smoke),('Benchmark',t)]:
        lines.append(f"| {phase} | `{x['receipt']['report'].replace(chr(92),'/').split('/')[-2]}` |")
    lines.append('')
assert len(exe_hashes)==1,exe_hashes
lines.extend(['반복은 동일 프로세스의 교차 순서 4회다. 독립 날짜·GPU의 재현성 또는 작은 차이의 통계적 확증으로 해석하지 않는다.',
              '후보 비율은 품질 window에서 별도로 얻었다. 4,800-frame 성능 실행의 평균 후보 비율로 치환하지 않는다.',''])
(OUT/'gpu-tables.md').write_text('\n'.join(lines),encoding='utf-8')
(OUT/'timing-comparisons.json').write_text(json.dumps(comparisons,indent=2)+'\n')
print(json.dumps(comparisons,indent=2))
