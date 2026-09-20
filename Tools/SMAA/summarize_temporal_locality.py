"""Publish only completed, paired locality diagnostics with explicit attribution limits."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True)
p.add_argument('--profiler',type=Path,required=True);a=p.parse_args()
receipts=json.loads(a.receipt.read_text(encoding='utf-8-sig'))
assert len(receipts)==6 and len({x['executable_sha256'] for x in receipts})==1
assert {(x['scene'],x['phase']) for x in receipts}=={(s,p) for s in ('bistro','minecraft') for p in ('Smoke','Capture','Benchmark')}
data={s:{k:json.loads((root/f'tmp/locality-{s}-{k}.json').read_text())
         for k in ('capture','performance')} for s in ('bistro','minecraft')}
for r in receipts:
    report=Path(r['report']);text=report.read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in text and f"Scene: {r['scene']}" in text
    assert 'DirectX11' in text and '1920 x 1061' in text and 'Vsync:        OFF' in text
    r['report_sha256']=hashlib.sha256(report.read_bytes()).hexdigest()
    if r['phase']=='Capture': assert Path(data[r['scene']]['capture']['capture'])==report.parent
    if r['phase']=='Benchmark': assert Path(data[r['scene']]['performance']['source'])==report
out=root/'Docs/Temporal-Contrast-Locality'
result=dict(classification='Synthetic locality diagnostics, not AA quality or final eight-case results',
    implementation_commit=subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}',
        'log','-1','--format=%H','--','Projects/CMAA2/TemporalContrastExperiment.inl'],cwd=root,text=True).strip(),
    profiler_probe=json.loads(a.profiler.read_text(encoding='utf-8-sig')),receipts=receipts,scenes=data)
lines=['# 동일 50% 선택률의 배치별 실행 비용','',
       'GPU 성능 카운터는 권한 부족으로 수집하지 못했다. 아래는 DX11 GPU timestamp와 '
       '컴파일 산출물/픽셀 검증을 결합한 대조 실험이다. 하드웨어 warp/cache/stall을 측정한 결과가 아니다.',
       '', '## 검증','',
       '원본 spatial/resolve 8 shader variant의 baseline DXBC 일치 및 새 shader 4 variant 검사를 통과했다. '
       '두 stripe 폭은 같은 shader를 사용하고 uniform shift만 바꾼다. branch에서는 velocity/history가 '
       '조건부이고 flatten에서는 모든 픽셀에서 계산 후 선택한다.',
       '', '각 장면 smoke, capture, benchmark가 각각 독립 프로세스로 정상 종료했다. '
       '성능은 300 warmup, 4,800 frame×3회이며 capture/분석과 분리했다. '
       '실행파일, CSV hash와 분포/반복별 수치는 [results.json](results.json)에 있다.',
       '', '공식 문서, 실험 가설 및 조건은 [method.md](method.md)를 따른다.','']
for scene,d in data.items():
    c=d['capture'];m=d['performance']['modes']
    assert not any(c['prior_hash_mismatch'].values()) and not any(c['synthetic_wrong_pixels'].values())
    assert not any(c['branch_flatten_hash_mismatch'].values()) and c['all_selected_hash_mismatch']==0
    lines += [f'## {scene}','',
        f"9 mode×240 frame 검증. 실제 대비 선택률 {c['contrast_selected_percent']:.6f}%. "
        '합성 두 폭은 매 프레임 1,018,560/2,037,120 픽셀(50%). '
        'CPU 선택식으로 조합한 native/current와 합성 결과의 불일치 픽셀 0, '
        'branch/flatten 출력 및 기존 control hash 불일치 0.',
        '', '| Mode | SMAA ms | 원본 대비 | Resolve ms | Resolve 반복 표준편차 ms |',
        '|---|---:|---:|---:|---:|']
    for n,v in m.items():
        lines.append(f"| {n} | {v['SMAA']['mean_ms']:.6f} | {v['SMAA']['percent_vs_native']:+.3f}% | {v['Resolve']['mean_ms']:.6f} | {v['Resolve']['run_std_ms']:.6f} |")
    lines += ['', '| 대조 (앞−뒤) | Resolve 평균 차이 ms | 반복별 차이 ms |', '|---|---:|---|']
    for label,left,right in [
        ('대비 전체 선택−원본','ABL-Contrast-All-R','O-T2X-R'),
        ('실제 부분 선택−대비 전체 선택','ABL-Contrast-001-R','ABL-Contrast-All-R'),
        ('32px branch−1px branch','DIAG-Stripe32-Branch-R','DIAG-Stripe1-Branch-R'),
        ('1px branch−1px flatten','DIAG-Stripe1-Branch-R','DIAG-Stripe1-Flatten-R'),
        ('32px branch−32px flatten','DIAG-Stripe32-Branch-R','DIAG-Stripe32-Flatten-R'),
        ('32px flatten−1px flatten','DIAG-Stripe32-Flatten-R','DIAG-Stripe1-Flatten-R')]:
        l=m[left]['Resolve'];r=m[right]['Resolve']
        paired=[x-y for x,y in zip(l['runs_ms'],r['runs_ms'])]
        lines.append(f"| {label} | {l['mean_ms']-r['mean_ms']:+.6f} | "+', '.join(f'{x:+.6f}' for x in paired)+' |')
    lines += ['', '전체 SMAA의 반복별 spatial control(ms): '+
        '; '.join(f"{n}: "+','.join(f'{v:.6f}' for v in m[n]['Spatial']['runs_ms']) for n in ('O-T2X-R','ABL-Contrast-001-R'))+'.','']
lines += ['## 해석의 경계','',
    '- 같은 선택률/같은 shader의 폭 비교는 화면 배치에 따른 실행 비용을 조사한다. branch 효율, texture locality 및 실제 lane 배치는 함께 영향을 줄 수 있어 각각의 hardware 원인을 분리하지 못한다.',
    '- 대비 전체 선택−원본은 대비 연산, 판단에 따른 의존 관계 및 실행 구조의 추가 비용이다. 순수 derivative 명령 비용만의 측정이 아니다. SM5/LOD 자체의 대조는 이전 Execution gate를 참고한다.',
    '- 합성 정책은 대비를 보지 않으며 실제 후보 위치도 다르다. 빠르더라도 AA 품질을 만족하는 최적화로 채택하지 않는다.',
    '- 현재 구현은 추가 pass가 없는 temporal PS 내부 선택이다. 이번 비용을 별도 후보 pass 또는 다른 pass 데이터 전송 탓으로 돌리지 않는다.',
    '- 기존 기본값은 유지했다. 합성 선택을 기본으로 바꾸거나 장면별 전환을 추가하지 않았다. 실제 대비 선택의 잔상/정지 후 교대 깜빡임이 개선됐다고 주장하지 않는다.',
    '- 단일 RTX 3060 Ti, 두 장면, 세 반복이다. 작은 변화의 통계적 유의성이나 다른 GPU에서의 우위를 주장하지 않는다.','']
out.mkdir(parents=True,exist_ok=True)
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
(out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
print('Published',out)
