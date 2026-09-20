"""Publish validated exact-output and five-repeat warp execution results."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True)
p.add_argument('--implementation-commit',required=True);a=p.parse_args()
receipts=json.loads(a.receipt.read_text(encoding='utf-8-sig'))
assert len(receipts)==6 and len({x['executable_sha256'] for x in receipts})==1
assert {(r['scene'],r['phase']) for r in receipts}=={(s,p) for s in ('bistro','minecraft') for p in ('Smoke','Capture','Benchmark')}
data={s:{k:json.loads((root/f'tmp/warp-{s}-{k}.json').read_text()) for k in ('capture','performance')} for s in ('bistro','minecraft')}
for r in receipts:
    path=Path(r['report']);t=path.read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in t and 'NVAPI VOTE_ANY supported: 1' in t
    assert f"Scene: {r['scene']}" in t and '1920 x 1061' in t and 'DirectX11' in t and 'Vsync:        OFF' in t
    r['report_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    if r['phase']!='Capture':
        elapsed=float(re.search(r'Focused preconditioning elapsed seconds: ([0-9.]+)',t)[1]);assert 30<=elapsed<60
        r['preconditioning_seconds']=elapsed
    if r['phase']=='Capture':assert (root/data[r['scene']]['capture']['capture']).resolve()==path.parent.resolve()
    if r['phase']=='Benchmark':assert (root/data[r['scene']]['performance']['source']).resolve()==path.resolve()
for d in data.values():
    assert not any(d['capture']['prior_hash_mismatches'].values())
    assert not any(d['capture']['output_hash_mismatches'].values())
commit=subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}','rev-parse',a.implementation_commit+'^{commit}'],cwd=root,text=True).strip()
out=root/'Docs/Temporal-Contrast-Warp'
result=dict(implementation_commit=commit,classification='NVIDIA-specific same-output execution experiment; not final eight-case result',receipts=receipts,scenes=data)
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# 동일 선택 결과를 보존한 warp 실행 측정','','조건과 공식 근거는 [method.md](method.md), 최종 판정은 [conclusion.md](conclusion.md)를 따른다.','',
    '별도 실행에서 두 장면 각 6 mode×240 frame 출력 검사, 4 mode×4,800 frame×5회 성능 측정을 완료했다. '
    '성능은 30초 미측정 렌더링과 각 mode 300-frame warmup을 거쳤다. '
    '정방향/역방향 순서를 교차했고 PNG 저장과 이미지 분석을 성능 실행에서 분리했다.','']
for scene,d in data.items():
    c=d['capture'];m=d['performance']['modes']
    lines += [f'## {scene}','',f"기존 control hash/새 output hash 불일치 0. 선택률 {c['selected_percent']:.6f}%, 별도 debug PS vote coverage {c['diagnostic_vote_coverage_percent']:.6f}%.",
        'Vote coverage는 debug PS의 값이며 실제 resolve의 hardware counter로 해석하지 않는다.','',
        '| Mode | SMAA ms | 원본 대비 | 기존 선택 대비 | Resolve ms | Resolve 원본 대비 |',
        '|---|---:|---:|---:|---:|---:|']
    for name in ['O-T2X-R','ABL-Contrast-001-R','ABL-ScalarWeight-001-R','ABL-NvWarp-001-R']:
        v=m[name];lines.append(f"| {name} | {v['SMAA']['mean_ms']:.6f} | {v['SMAA']['percent_vs_native']:+.3f}% | {v['SMAA']['percent_vs_prior']:+.3f}% | {v['Resolve']['mean_ms']:.6f} | {v['Resolve']['percent_vs_native']:+.3f}% |")
    lines += ['', '| 반복 | Warp−원본 SMAA ms | Warp−기존 선택 SMAA ms | Warp−원본 resolve ms | Warp−기존 선택 resolve ms |',
        '|---|---:|---:|---:|---:|']
    w=m['ABL-NvWarp-001-R']
    for i in range(5):lines.append(f"| {i+1} | {w['SMAA']['paired_deltas_vs_native_ms'][i]:+.6f} | {w['SMAA']['paired_deltas_vs_prior_ms'][i]:+.6f} | {w['Resolve']['paired_deltas_vs_native_ms'][i]:+.6f} | {w['Resolve']['paired_deltas_vs_prior_ms'][i]:+.6f} |")
    lines+=['','median, p95/p99, 반복 분산, 불변 spatial 및 WholeFrame/wall FPS는 results.json에 보존했다.','']
(out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
print('Published',out/'report.md')
