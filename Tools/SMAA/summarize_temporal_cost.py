"""Publish completed cost optimization gates without promoting nonidentical outputs."""
import argparse,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True)
p.add_argument('--implementation-commit',required=True);a=p.parse_args()
receipts=json.loads(a.receipt.read_text(encoding='utf-8-sig'))
assert len(receipts)==6 and len({r['executable_sha256'] for r in receipts})==1
assert {(r['scene'],r['phase']) for r in receipts}=={(s,p) for s in ('bistro','minecraft') for p in ('Smoke','Capture','Benchmark')}
data={s:{k:json.loads((root/f'tmp/cost-{s}-{k}.json').read_text()) for k in ('capture','performance')}
      for s in ('bistro','minecraft')}
for r in receipts:
    report=Path(r['report']);t=report.read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in t and f"Scene: {r['scene']}" in t
    assert 'DirectX11' in t and '1920 x 1061' in t and 'Vsync:        OFF' in t
    r['report_sha256']=hashlib.sha256(report.read_bytes()).hexdigest()
    if r['phase']=='Capture':assert (root/data[r['scene']]['capture']['capture']).resolve()==report.parent.resolve()
    if r['phase']=='Benchmark':assert (root/data[r['scene']]['performance']['source']).resolve()==report.resolve()
eligible=[n for n,v in data['bistro']['capture']['variants'].items()
          if v['hash_mismatch_frames']==0 and data['minecraft']['capture']['variants'][n]['hash_mismatch_frames']==0]
lines=['# 픽셀별 luma 선택의 비용 최적화 결과','',
       '선택 기준과 후보 픽셀을 유지하고 temporal PS의 계산/접근 비용만 변경했다. '
       '후보 확장, 새 선택 단위, 추가 pass 및 metadata 접근은 없다. '
       '조건과 공식 근거는 [method.md](method.md)를 따른다.','',
       '각 장면 smoke/capture/benchmark 독립 실행. 성능은 300 warmup, 4,800 frame×3회, '
       '품질 저장/분석과 분리했다. 원본 shader 8 variant 불변과 새 shader 14 variant 검사를 통과했다.',
       '', '기존 early-return은 선택되지 않은 픽셀의 velocity/history 읽기를 생략한다. '
       'ScalarWeight 계열은 모든 픽셀을 읽되 비후보 weight만 0으로 하여 같은 화면을 만든다. '
       '실제 fetch 수 감소와 같은 품질의 실행 시간 감소를 구별한다.','']
for scene,d in data.items():
    c=d['capture'];m=d['performance']['modes'];assert not any(c['prior_hash_mismatches'].values())
    lines += [f'## {scene}','',f"11 mode×240 frame. 선택률 {c['selected_percent']:.6f}%. 기존 원본/선택/mask hash bridge 불일치 0.",'',
        '| Mode | 변경 픽셀 합계 | 최대 채널 오차 /255 | 비후보 변경 | PNG 불일치 frame |',
        '|---|---:|---:|---:|---:|']
    for n,v in c['variants'].items():
        lines.append(f"| {n} | {v['changed_pixels']} | {v['max_channel_error']} | {v['noncandidate_changed_pixels']} | {v['hash_mismatch_frames']} |")
    lines += ['', '변경 픽셀은 240 frame에 걸친 합계이며 같은 위치가 여러 frame에서 달라지면 각각 센다. '
        'HistoryLoad 및 재배열 산술은 비동일 출력을 별도로 표시하고 동일 품질 최적화로 채택하지 않는다.', '',
        '| Mode | 두 장면 byte-exact | SMAA ms | 원본 대비 | 기존 선택 대비 | Resolve ms | Resolve 반복 표준편차 ms |',
        '|---|---|---:|---:|---:|---:|---:|']
    for n,v in m.items():
        label='control' if n in ('O-T2X-R','ABL-Contrast-001-R') else 'yes' if n in eligible else 'no'
        lines.append(f"| {n} | {label} | {v['SMAA']['mean_ms']:.6f} | {v['SMAA']['percent_vs_native']:+.3f}% | {v['SMAA']['percent_vs_prior']:+.3f}% | {v['Resolve']['mean_ms']:.6f} | {v['Resolve']['run_std_ms']:.6f} |")
    lines += ['', '| Mode | Resolve 반복 ms | SMAA 원본 대비 반복 차이 ms |', '|---|---|---|']
    for n in ['ABL-Contrast-001-R']+eligible:
        lines.append('| '+n+' | '+', '.join(f'{x:.6f}' for x in m[n]['Resolve']['runs_ms'])+' | '+
            ', '.join(f'{x:+.6f}' for x in m[n]['SMAA']['paired_deltas_vs_native_ms'])+' |')
    lines += ['', '불변 spatial 시간, p95/p99, wall FPS 및 전체 반복 분포는 results.json에 보존했다. '
        '원본보다 작은 시간 차이만으로 개선을 확정하지 않으며 first-mode 초기 변동을 함께 본다.','']
lines += ['## 검토에서 제외한 중복과 범위','',
    '- 기존 current-first/velocity-prefetch 소스 재배치는 동일 DXBC이거나 sample이 branch 안으로 이동했으므로 반복하지 않았다. 이전 Execution/Dependency 보고서의 근거를 유지한다.',
    '- 기존 branch↔flatten 비교는 control로만 재사용했다. 이번 새 변경은 RGBA 결과 선택 대신 scalar weight 제어와 별도의 산술/읽기/선택식 비용 변경이다.',
    '- ScalarMultiply probe는 ScalarWeight보다 같은 경로에 multiply 명령을 하나 더 추가했다. 더 짧은 scalar weight masking을 GPU 후보로 선택했다.',
    '- 기존 선택/ScalarWeight/ScalarFixedThreshold의 /O1,/O2,/O3 instruction stream은 각각 모두 동일했다. compiler-levels.json 참조. 최적화 수준 변경을 새 GPU 개선으로 세지 않았다.',
    '- DXBC slot 감소는 하드웨어 시간 감소가 아니다. FP 산술 재배치와 history Load는 출력 검증을 통해 별도 판정한다.',
    '- Nvidia warp/cache/stall counter는 이전 권한 제한으로 미측정이다. 이 결과로 지배적인 하드웨어 원인을 확정하거나 모든 가능한 구현의 불가능을 증명했다고 표현하지 않는다.',
    '- 다른 selector, 후보 확장, 추가 pass, 다른 graphics API로 연구 질문을 바꾸지 않는다.','']
for d in data.values(): d['performance'].pop('distributions',None) # Already stored per-mode/per-metric.
out=root/'Docs/Temporal-Contrast-Cost'
result=dict(classification='Same-selector temporal PS optimization gate; not final eight-case data',
    implementation_commit=subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}',
        'rev-parse',a.implementation_commit+'^{commit}'],cwd=root,text=True).strip(),
    receipts=receipts,byte_exact_variants_in_both_scenes=eligible,scenes=data)
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
print('Published',out)
