"""Validate matched-input replay diagnosis, without treating replays as benchmark trials."""
import hashlib
import json
import math
import statistics as st
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'tmp/rd-profiler'
OUT=ROOT/'Docs/Temporal-Contrast-Counters'
MODES=['O-T2X-R','ABL-Contrast-001-R','ABL-ScalarWeight-001-R']
ENTRIES=['DX10_SMAAResolvePS','DX10_SMAAContrastResolvePS','DX10_SMAAScalarWeightResolvePS']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


inputs=json.loads((SOURCE/'inputs.json').read_text(encoding='utf-8'))
assert inputs['status']=='PASS' and len(inputs['captures'])==6
result={'classification':'Matched-input draw replay diagnosis, not live timing or quality evaluation',
        'profile_frame':90,'replays_per_capture':3,'scenes':{}}
lines=['# Temporal draw 하드웨어 카운터', '',
       '동일 frame 90에서 캡처한 temporal draw를 각 3회 재생한 진단이다. 실시간 benchmark 평균이 아니다.', '',
       '| 장면 | 방식 | warp 명령 수 | 원본 대비 | thread 명령 수 | 원본 대비 | texture 요청 수 | 원본 대비 | 명령당 활성 thread |',
       '|---|---|---:|---:|---:|---:|---:|---:|---:|']
exes=set()
for scene in ('bistro','minecraft'):
    src=SOURCE/scene/'results.json'
    data=json.loads(src.read_text(encoding='utf-8'))
    assert data['status']=='PASS' and data['administrator']
    assert [r['mode'] for r in data['replays']]==MODES
    assert len(data['captures'])==3
    exes.add(data['executable_sha256'])
    report=Path(data['capture_report'])
    assert digest(report)==data['capture_report_sha256']
    text=report.read_text(encoding='utf-8-sig')
    assert 'Aggregate: PASS' in text and 'Aggregate: FAIL' not in text
    assert '1920 x 1061' in text and 'Frames: 121' in text and 'Warmup: 300' in text
    inp=[i for i in inputs['captures'] if i['scene']==scene]
    assert [i['mode'] for i in inp]==MODES
    signatures=[]
    for i in inp:
        assert {r['shader_name'] for r in i['resources']}=={'colorTex','colorTexPrev','velocityTex'}
        signatures.append(sorted((r['shader_name'],r['sha256'],r['bytes'],r['format']) for r in i['resources']))
    assert signatures[0]==signatures[1]==signatures[2]
    assert inp[0]['constant_buffers']==[] # Native resolve has no used constant block.
    assert inp[1]['constant_buffers']==inp[2]['constant_buffers']
    assert abs(inp[1]['constant_buffers'][0]['float32'][9]-.01)<1e-9
    summary={}
    for capture,replay,entry in zip(data['captures'],data['replays'],ENTRIES):
        assert digest(Path(capture['path']))==replay['capture_sha256']
        assert replay['shader_entry']==entry and replay['api']=='GraphicsAPI.D3D11'
        assert len(replay['temporal_draw_ids'])==1
        assert replay['missing_counters']==[] and replay['debug_messages']==[]
        assert len(replay['counter_runs'])==3
        names={d['name'] for d in replay['counter_descriptions']}
        assert len(names)==15
        for values in replay['counter_runs']:
            assert set(values)==names and all(v is not None and math.isfinite(v) and v>=0 for v in values.values())
            assert values['PS Invocations']==1920*1061
        stats={n:dict(mean=st.mean(r[n] for r in replay['counter_runs']),
                      min=min(r[n] for r in replay['counter_runs']),
                      max=max(r[n] for r in replay['counter_runs'])) for n in names}
        summary[replay['mode']]=stats
        replay.pop('named_actions',None)
        replay.pop('state_attributes',None)
        assert 'renderdoc_capture, '+replay['mode']+', 90, PASS' in text
    for mode in MODES:
        s=summary[mode];base=summary[MODES[0]]
        cells=[]
        for metric in ('smsp__inst_executed.sum','smsp__thread_inst_executed.sum','l1tex__texin_requests.sum'):
            mean=s[metric]['mean'];ratio=(mean/base[metric]['mean']-1)*100
            s[metric]['percent_vs_original']=ratio
            cells += [f'{mean:,.1f}',f'{ratio:+.2f}%']
        active=s['smsp__average_thread_inst_executed_per_inst_executed.avg.ratio']['mean']
        lines.append('| '+ ' | '.join([scene,mode]+cells+[f'{active:.3f}'])+' |')
    result['scenes'][scene]=dict(summary=summary,source_sha256=digest(src),captures=data,
                               input_texture_hashes=signatures[0],selection_constant=inp[1]['constant_buffers'][0])
assert len(exes)==1
result['executable_sha256']=next(iter(exes))
result['validation']='PASS'
lines += ['', '## 대기 지표', '',
          '아래 값은 활성 warp 기준의 대기 비율 평균이다. 해당 이유가 전체 GPU 시간에서 차지하는 비율이 아니며 인과 기여율로 더하지 않는다.', '',
          '| 장면 | 방식 | L1TEX 의존성 대기 | texture queue 대기 | branch target 대기 |',
          '|---|---|---:|---:|---:|']
for scene,data in result['scenes'].items():
    for mode,s in data['summary'].items():
        keys=['long_scoreboard','tex_throttle','branch_resolving']
        cells=[f"{s['smsp__warp_issue_stalled_'+k+'_per_warp_active.avg.ratio']['mean']:.6f}" for k in keys]
        lines.append('| '+' | '.join([scene,mode]+cells)+' |')
lines += ['', '## 검증 범위', '',
          '- 각 장면의 current/history/velocity 3개 입력 texture가 세 방식에서 모두 byte-hash 일치했다. sRGB/velocity view 형식도 같다.',
          '- 기존 분기와 ScalarWeight의 사용 상수 버퍼가 동일하며 threshold는 float32의 0.01이다. 원본 PS에는 사용되는 상수 버퍼가 없다.',
          '- 6 capture, capture당 temporal draw 1개, 15 counter×3회, PS Invocations 2,037,120 및 debug 오류 없음 검증.',
          '- 동일 capture의 세 번 재생은 독립적인 장면·프레임 반복이 아니다. 단일 이동 pose의 진단으로 한정한다.',
          '- replay GPU Duration은 results.json에 보존하되 실시간 성능 표에 합치지 않는다. 캐시 상태·draw 직렬화·계측이 실행 조건을 바꿀 수 있다.',
          '- 활성 thread 지표는 명령 전반의 평균이며 후보 비율이나 분기 효율 그 자체가 아니다. 32 근처의 미소 초과도 원시 값 그대로 기록한다.',
          '- 카운터는 하드웨어 명령 실행량을 제공하지만 NVIDIA SASS disassembly는 확보하지 못했다. 노출된 DXBC/AMD GCN 선택지를 NVIDIA SASS로 표현하지 않는다.', '']
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
(OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
print('PASS:',OUT)
