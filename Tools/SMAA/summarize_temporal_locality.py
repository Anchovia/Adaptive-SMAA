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
    if r['phase']=='Capture': assert (root/Path(data[r['scene']]['capture']['capture'])).resolve()==report.parent.resolve()
    if r['phase']=='Benchmark': assert (root/Path(data[r['scene']]['performance']['source'])).resolve()==report.resolve()
out=root/'Docs/Temporal-Contrast-Locality'
# This publisher documents this completed gate. Refuse contradictory reruns
# rather than silently retaining its qualitative conclusion with different data.
for scene,d in data.items():
    modes=d['performance']['modes']
    assert modes['DIAG-Stripe32-Branch-R']['Resolve']['mean_ms'] < modes['DIAG-Stripe1-Branch-R']['Resolve']['mean_ms']
    assert abs(modes['DIAG-Stripe32-Flatten-R']['Resolve']['mean_ms']/modes['DIAG-Stripe1-Flatten-R']['Resolve']['mean_ms']-1)<0.01
    assert (modes['ABL-Contrast-001-R']['SMAA']['percent_vs_native']<0)==(scene=='bistro')
result=dict(classification='Synthetic locality diagnostics, not AA quality or final eight-case results',
    implementation_commit=subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}',
        'log','-1','--format=%H','--','Projects/CMAA2/TemporalContrastExperiment.inl'],cwd=root,text=True).strip(),
    profiler_probe=json.loads(a.profiler.read_text(encoding='utf-8-sig')),receipts=receipts,scenes=data)
lines=['# 동일 50% 선택률의 배치별 실행 비용','',
       '## 판단','',
       '선택률만으로 실행 비용을 예측할 수 없다. 두 장면 모두 같은 50% 선택과 같은 branch shader에서 '
       '1px 간격 대신 32px 폭으로 선택 위치를 모으면 temporal 시간이 약 22% 줄었다. '
       '전체 fetch 후 선택하는 flatten에서는 폭에 따른 차이가 1% 미만이었다. '
       '따라서 조건부 실행과 선택 위치의 조합이 비용에 영향을 준다는 실험 근거를 확보했다.', '',
       '실제 대비 방식은 전체 선택 대조에서 원본보다 약 9~10 us의 resolve 비용을 추가한다. '
       'Bistro에서는 생략 이득이 이를 상쇄했지만 Minecraft에서는 상쇄하지 못했다. '
       '원본 대비 전체 SMAA는 각각 -3.87%, +1.24%다. 현재 경로에는 추가 후보 pass가 없으므로 '
       '별도 pass 비용으로 설명하지 않는다.', '',
       '이번 변경은 진단 도구 추가이며 실제 AA 최적화 채택이 아니다. 기본 알고리즘을 유지한다. '
       '32px 줄무늬를 실제 후보 정책으로 쓰거나 무조건 넓은 블록으로 확장하는 결론은 내리지 않는다. '
       '후속 설계는 판정의 비용과 선택 분포를 함께 다뤄야 하며, 선택 기준을 바꾸면 반드시 품질 gate가 필요하다.', '',
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
    native=m['O-T2X-R']['Resolve']['mean_ms'];all_selected=m['ABL-Contrast-All-R']['Resolve']['mean_ms']
    actual=m['ABL-Contrast-001-R']['Resolve']['mean_ms']
    narrow=m['DIAG-Stripe1-Branch-R']['Resolve']['mean_ms'];wide=m['DIAG-Stripe32-Branch-R']['Resolve']['mean_ms']
    narrow_flat=m['DIAG-Stripe1-Flatten-R']['Resolve']['mean_ms'];wide_flat=m['DIAG-Stripe32-Flatten-R']['Resolve']['mean_ms']
    lines += [f'실제 대비 경로: 전체 선택 시 원본보다 {(all_selected-native)*1000:+.3f} us, '
        f'부분 선택으로 전체 선택 대비 {(actual-all_selected)*1000:+.3f} us, '
        f'최종적으로 원본 대비 {(actual-native)*1000:+.3f} us다.', '',
        f'같은 50%/같은 branch shader에서 32px 폭은 1px 폭보다 {(wide/narrow-1)*100:+.2f}%다. '
        f'반면 전체 fetch 후 선택하는 flatten의 폭 차이는 {(wide_flat/narrow_flat-1)*100:+.2f}%다. '
        '조건부 실행에서 선택 위치의 영향이 커지는지 판단하는 대조이며, 하드웨어 원인별 기여율은 아니다.', '']
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
