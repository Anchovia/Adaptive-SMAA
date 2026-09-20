"""Five-repeat warmed confirmation of the exact-output scalar-weight candidate."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from analyze_temporal_execution import performance
root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True)
p.add_argument('--implementation-commit',required=True);a=p.parse_args()
receipts=json.loads(a.receipt.read_text(encoding='utf-8-sig'))
assert len(receipts)==4 and len({r['executable_sha256'] for r in receipts})==1
assert {(r['scene'],r['phase']) for r in receipts}=={(s,p) for s in ('bistro','minecraft') for p in ('Smoke','Benchmark')}
modes=['ABL-Contrast-001-R','O-T2X-R','ABL-ScalarWeight-001-R']
data={}
for r in receipts:
    path=Path(r['report']);text=path.read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in text and f"Scene: {r['scene']}" in text
    elapsed=float(re.search(r'Focused preconditioning elapsed seconds: ([0-9.]+)',text)[1])
    assert 30<=elapsed<60
    r['preconditioning_seconds']=elapsed;r['report_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    if r['phase']=='Benchmark':
        data[r['scene']]=performance(path,modes,repeats=5)
        data[r['scene']].pop('distributions',None)
assert set(data)=={'bistro','minecraft'}
# The confirmation modifies only the benchmark driver, not any shader or binding.
diff=subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}',
    'diff','419eef4','--','Projects/CMAA2/SMAA'],cwd=root)
assert not diff, 'Shader/binding changed since exact-output capture; new quality gate required'
commit=subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}',
    'rev-parse',a.implementation_commit+'^{commit}'],cwd=root,text=True).strip()
result=dict(implementation_commit=commit,shader_binding_reference_commit='419eef4',
    shader_binding_diff_empty=True,receipts=receipts,scenes=data)
out=root/'Docs/Temporal-Contrast-Cost'
(out/'focused-results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# 예열 후 scalar weight 최적화 확인','',
       '동일 출력이 확인된 scalar weight만 원본/기존 선택과 재비교했다. '
       '30초의 미측정 렌더링 후 각 mode를 300 frame warmup, 4,800 frame×5회 측정했다. '
       '원본은 정방향/역방향 모두 가운데 순서다. 셰이더와 binding은 출력 검증 commit 419eef4와 같다.', '',
       '이 gate는 기존 후보/품질을 변경하지 않는다. 동일 EXE의 장면별 독립 실행이며 '
       '반복별 차이를 공개한다. 한 프로세스 내부 반복을 독립 GPU/장면 표본으로 취급하지 않는다.','']
for scene,p in data.items():
    m=p['modes'];lines += [f'## {scene}','',
        '| Mode | SMAA ms | 원본 대비 | 기존 선택 대비 | Resolve ms | Resolve 기존 선택 대비 |',
        '|---|---:|---:|---:|---:|---:|']
    for n in modes:
        v=m[n];lines.append(f"| {n} | {v['SMAA']['mean_ms']:.6f} | {v['SMAA']['percent_vs_native']:+.3f}% | {v['SMAA']['percent_vs_prior']:+.3f}% | {v['Resolve']['mean_ms']:.6f} | {v['Resolve']['percent_vs_prior']:+.3f}% |")
    lines += ['', '| 반복 | 원본 SMAA ms | scalar SMAA ms | 차이 ms | 원본 resolve ms | scalar resolve ms |',
        '|---|---:|---:|---:|---:|---:|']
    for i in range(5):
        n=m['O-T2X-R'];v=m['ABL-ScalarWeight-001-R']
        lines.append(f"| {i+1} | {n['SMAA']['runs_ms'][i]:.6f} | {v['SMAA']['runs_ms'][i]:.6f} | {v['SMAA']['paired_deltas_vs_native_ms'][i]:+.6f} | {n['Resolve']['runs_ms'][i]:.6f} | {v['Resolve']['runs_ms'][i]:.6f} |")
    lines+=['']
(out/'focused-report.md').write_text('\n'.join(lines),encoding='utf-8')
print('Published',out/'focused-report.md')
