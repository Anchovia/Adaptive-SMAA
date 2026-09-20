"""Publish measured execution controls and explicitly limited conclusions."""
import hashlib, json, subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[2]
out=root/'Docs/Temporal-Contrast-Execution'
data={s:{k:json.loads((root/f'tmp/execution-{s}-{k}.json').read_text())
         for k in ['capture','performance']} for s in ['bistro','minecraft']}
receipts=json.loads((root/'tmp/temporal-execution-runs.json').read_text(encoding='utf-8-sig'))
bench_receipts=[r for r in receipts if r['phase']=='Benchmark']
assert len(bench_receipts)==2 and {r['scene'] for r in bench_receipts}=={'bistro','minecraft'}
assert len({r['executable_sha256'] for r in bench_receipts})==1
compact={'classification':'Same-selection execution ablation; not final eight-case results',
         'implementation_commit':subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}','rev-parse','HEAD'],cwd=root,text=True).strip(),
         'receipts':receipts,'scenes':{}}
lines=['# Temporal contrast 실행 비용 분리 결과','',
       '## 판단','',
       '기본 구현을 유지한다. 같은 선택 결과에서 structured branch는 기존 early-return 대비 두 장면 모두 resolve 평균 변화가 0.1% 미만이다. '
       'Flatten은 Minecraft resolve를 5.25%, 전체 SMAA를 0.59% 줄였으나 원본 T2X-R보다 전체 SMAA가 1.26% 느리며, '
       'Bistro에서는 기존 선택 대비 resolve가 41.77% 증가했다. 범용 개선으로 채택할 근거가 없다.','',
       'SM5와 explicit LOD0 자체의 resolve 차이는 0.000024 ms 이내다. 반면 all-selected 대비 판정/분기 경로는 '
       'LOD0 control보다 Bistro 0.010163 ms, Minecraft 0.009499 ms 비싸다. Minecraft의 선택 생략은 '
       '그 경로에서 0.005472 ms를 줄여 추가 비용을 상쇄하지 못했다. 판정 연산과 조건부 texture 접근의 의존 관계가 '
       '주요 조사 대상이며, divergence와 cache/latency 중 지배적인 hardware 원인은 아직 분리하지 않았다.','',
       '다음 설계는 판정 비용 및 current→판정→velocity→history 의존 관계를 낮추는 방향을 검토한다. '
       '선택 기준/공간적 판단 단위를 바꾸는 경우 이번 동일 출력 최적화와 분리하여 mask·깜빡임·고스팅을 다시 검증한다. '
       '별도 pass/목록 생성이나 scene별 임의 전환을 기본 해법으로 도입하지 않는다.','',
       '공식 근거와 조건은 [method.md](method.md), DXBC 검증은 [shader-validation.json](shader-validation.json)을 따른다.',
       '픽셀 선택률은 GPU 실행 명령 감소율이 아니다. DXBC와 GPU timestamp로 원인을 좁혔으며 hardware warp/cache/stall counter는 측정하지 않았다.','']
for s,d in data.items():
    c=d['capture'];p=d['performance']
    assert all(v==0 for v in c['prior_hash_mismatches'].values()) and all(v==0 for v in c['control_hash_mismatches'].values())
    compact['scenes'][s]={'capture':{k:v for k,v in c.items() if k not in ('frame_hashes','per_frame_locality')},'performance':p}
    compact['scenes'][s]['capture_analysis_sha256']=hashlib.sha256((root/f'tmp/execution-{s}-capture.json').read_bytes()).hexdigest()
    lines += [f'## {s}','',f"240 frame ×11 mode capture, 기존 5 mode hash bridge와 모든 대조군 출력 hash mismatch 0. 선택률 {c['selection_percent']:.6f}%.",
              '', '| Mode | SMAA ms | native 대비 | Resolve ms | 기존 선택 대비 resolve |',
              '|---|---:|---:|---:|---:|']
    for n,m in p['modes'].items():
        lines.append(f"| {n} | {m['SMAA']['mean_ms']:.6f} | {m['SMAA']['percent_vs_native']:+.3f}% | {m['Resolve']['mean_ms']:.6f} | {m['Resolve']['percent_vs_prior']:+.3f}% |")
    lines += ['', '4,800 frame ×3회 평균. 각 반복의 값, p95/p99, median, 표준편차, WholeFrame 및 wall FPS/1% low는 results.json에 보존한다.',
              '', '| Resolve 대조 (앞−뒤) | 평균 차이 ms |', '|---|---:|']
    for label,a,b in [('SM5−원본','ABL-NativeSM5-R','O-T2X-R'),
        ('LOD0−SM5','ABL-Lod-R','ABL-NativeSM5-R'),
        ('gradient/branch all−LOD0','ABL-Contrast-All-R','ABL-Lod-R'),
        ('기존 선택−all','ABL-Contrast-001-R','ABL-Contrast-All-R'),
        ('structured−기존 선택','ABL-Structured-001-R','ABL-Contrast-001-R'),
        ('flatten−기존 선택','ABL-Flatten-001-R','ABL-Contrast-001-R'),
        ('동일 DXBC: CurrentFirst−LOD0','ABL-CurrentFirst-R','ABL-Lod-R'),
        ('동일 DXBC: Prefetch−Structured','ABL-PrefetchVelocity-001-R','ABL-Structured-001-R')]:
        lines.append(f"| {label} | {p['modes'][a]['Resolve']['mean_ms']-p['modes'][b]['Resolve']['mean_ms']:+.6f} |")
    lines += ['', 'gradient/branch 대조는 판정 연산과 그에 따른 실행 의존 관계를 함께 포함한다. 분기 하드웨어 비용만의 분리는 아니다.',
              '', '| 화면 tile | 혼합 tile 비율 | 선택 pixel이 있는 tile 비율 |', '|---|---:|---:|']
    for n,v in c['locality'].items():
        lines.append(f"| {n} | {v['mixed_fraction']*100:.3f}% | {v['active_fraction']*100:.3f}% |")
    lines += ['', '부분 bottom tile 제외. 화면상의 분포 대용값이며 실제 warp 배치/분기 효율이 아니다.','']
lines += ['## 해석의 범위','',
          '- 첫 native 반복의 spatial 시간이 후속 반복보다 낮았다. 모든 반복을 유지했다. 전체 AA의 작은 차이는 이 변동을 포함하며, 불변 spatial 코드의 시간 차이를 알고리즘 개선으로 해석하지 않는다.',
          '- Minecraft flatten의 기존 선택 대비 resolve/전체 SMAA 감소와 원본 대비 열세는 세 반복 모두 같은 방향이었다. 통계적 유의성 또는 다른 GPU에서의 재현을 주장하지 않는다.',
          '- SM5와 explicit LOD control은 native와 동일 출력이다. 실제 측정 차이로만 비용을 해석한다.',
          '- CurrentFirst/Lod와 PrefetchVelocity/Structured는 각 쌍이 동일 DXBC다. 쌍의 timing 차이는 소스 순서 최적화 효과가 아니다.',
          '- Flatten은 history/velocity를 fullscreen으로 읽는다. 빨라지더라도 선택적 sample 절약에 성공한 것은 아니다.',
          '- 출력 동일성이 확인된 구현들은 기존 대비 선택 방식의 품질도 동일하다. 정지 후 두 프레임 교대 깜빡임은 남아 있으며 고스팅 개선을 새로 입증하지 않는다.',
          '- 단일 GPU, 두 장면, 세 반복 결과다. 기본 mode 자동 전환이나 scene별 임의 정책은 추가하지 않았다.', '']
out.mkdir(parents=True,exist_ok=True)
(out/'results.json').write_text(json.dumps(compact,indent=2)+'\n',encoding='utf-8')
(out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
print('Published',out)
