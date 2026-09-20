"""Publish direct-access controls without changing the existing default."""
import hashlib, json, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=root/'Docs/Temporal-Contrast-Dependency'
data={s:{k:json.loads((root/f'tmp/dependency-{s}-{k}.json').read_text())
    for k in ['capture','performance']} for s in ['bistro','minecraft']}
receipts=json.loads((root/'tmp/temporal-dependency-runs.json').read_text(encoding='utf-8-sig'))
bench=[r for r in receipts if r['phase']=='Benchmark']
assert len(bench)==2 and {r['scene'] for r in bench}==set(data)
assert len({r['executable_sha256'] for r in receipts})==1
result={'classification':'Same-selection direct texel access engineering gate, not final eight cases',
    'implementation_commit':subprocess.check_output(['git','-c',f'safe.directory={root.as_posix()}','log','-1','--format=%H','--','Projects/CMAA2/SMAA/TemporalContrastExecution.hlsl'],cwd=root,text=True).strip(),
    'decision':'Keep existing default; neither direct-access variant improves both scenes.',
    'excluded_runs':[{'run':'20260920_103030','scene':'minecraft','exit_code':-1073740791,
        'reason':'Startup failure, no finalized CSV; see startup-failure.md',
        'successful_retry':'20260920_103305','startup_issue_fixed':False}],
    'receipts':receipts,'scenes':{}}
lines=['# Temporal 데이터 접근·의존 관계 검증 결과','',
    '**직접 읽기 두 방식 모두 채택하지 않고 기존 기본값을 유지한다.** 같은 Structured 분기 대비 '
    'current Load는 resolve가 Bistro +1.406%, Minecraft +1.885%였고, '
    'current+velocity Load는 +0.005%, +0.204%로 유의미한 개선을 확인하지 못했다. '
    '기존 선택 방식도 원본 대비 전체 SMAA 시간이 Bistro -3.855%, Minecraft +1.484%로 장면별 한계가 남는다.','',
    '공식 근거와 대조군은 [method.md](method.md), 컴파일 검사는 [shader-validation.json](shader-validation.json)을 따른다.',
    '두 prefetch 시도는 실제 DXBC에서 읽기가 분기 뒤로 이동하여 정적 단계에서 제외했다. '
    '실제 GPU 검증은 current Load와 current+velocity Load에 한정했다.','']
for scene,d in data.items():
    c=d['capture'];p=d['performance'];m=p['modes']
    assert not any(c['bridge_hash_mismatches'].values()) and not any(c['output_hash_mismatches'].values())
    assert c['bottom_right_boundary_mismatched_channels']==0
    result['scenes'][scene]={'capture':{k:v for k,v in c.items() if k!='frame_hashes'},
        'capture_analysis_sha256':hashlib.sha256((root/f'tmp/dependency-{scene}-capture.json').read_bytes()).hexdigest(),
        'performance':{k:v for k,v in p.items() if k!='distributions'}}
    lines += [f'## {scene}','',f"7 mode ×240 frame 출력과 후보 mask hash mismatch 0. 기존 4 mode bridge mismatch 0. 마지막 행/열 mismatch 0. 선택률 {c['selected_percent']:.6f}%.",
        '', '| Mode | SMAA ms | 원본 대비 | Resolve ms | 기존 선택 대비 resolve |', '|---|---:|---:|---:|---:|']
    for n,v in m.items():
        lines.append(f"| {n} | {v['SMAA']['mean_ms']:.6f} | {v['SMAA']['percent_vs_native']:+.3f}% | {v['Resolve']['mean_ms']:.6f} | {v['Resolve']['percent_vs_prior']:+.3f}% |")
    lines += ['', 'Load 후보의 직접 대조군은 Structured다. 같은 branch 형태에서의 차이:',
        '', '| Load 후보 | Structured 대비 SMAA | Structured 대비 resolve |', '|---|---:|---:|']
    for n in ['ABL-LoadCurrent-001-R','ABL-LoadCurrentVelocity-001-R']:
        vals=[(m[n][k]['mean_ms']/m['ABL-Structured-001-R'][k]['mean_ms']-1)*100 for k in ['SMAA','Resolve']]
        lines.append(f'| {n} | {vals[0]:+.3f}% | {vals[1]:+.3f}% |')
    lines += ['', 'Release x64, DX11, RTX 3060 Ti, 1920×1061, hidden, VSync Off. 300 warmup +4,800 frame ×3회, 정/역/정 순서. '
        '각 반복값·분포·WholeFrame·wall FPS/1% low는 results.json에 보존했다.','']
lines += ['## 판단 범위','',
    '- 화면의 같은 위치에서 색상을 가져오는 비용을 바꾼 실험이다. current→판정→velocity→history 의존 관계를 제거하지는 않았다.',
    '- 선택 mask와 출력이 같으므로 기존 선택 방식의 품질 한계도 같다. 고스팅이나 정지 후 교대 깜빡임을 개선했다고 주장하지 않는다.',
    '- CPU/드라이버/GPU clock 변동과 한 GPU·두 장면·세 반복의 한계가 있다. 수십 ns 수준의 차이를 확정 개선으로 채택하지 않는다.',
    '- 실제 warp/cache/stall counter는 측정하지 않았다. prefetch 정적 실패를 GPU 하드웨어 실행 순서 보장으로 해석하지 않는다.', '',
    '## 실행 안정성과 후속 범위','',
    '첫 Minecraft benchmark는 시작 오류로 CSV 생성 전에 종료돼 제외했다. 동일 EXE 재실행 '
    '`20260920_103305`은 정상 종료와 완성된 PASS CSV를 확인했다. '
    '[실패 기록](startup-failure.md)의 공통 shader 수명 문제 가능성은 미해결이며, 재실행 성공을 수정 완료로 표현하지 않는다.','',
    '이번 gate로 확인한 것은 동일 선택·동일 출력에서의 접근 방식 변경 효과다. '
    '다음 구현 변경 전에 시작 오류의 수명 문제를 별도 재현·검증하고, 실행 비용을 더 추정하기보다 '
    '현재 DX11 경로에서 얻을 수 있는 실제 GPU 분석 자료를 확인해야 한다. '
    '선택 수식이나 threshold를 바꾸는 실험은 출력과 깜빡임이 달라지므로 별도 품질 gate로 진행한다.','']
out.mkdir(parents=True,exist_ok=True)
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
(out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
print('Published',out)
