"""Production frame-90 captures and NVIDIA per-draw replay counters via RenderDoc 1.44."""
import ctypes
import hashlib
import json
import math
import time
import traceback
from pathlib import Path
import renderdoc as rd

ROOT = Path.cwd().parents[1]
OUT = ROOT/'tmp/rd-profiler'
job = json.loads((OUT/'job.json').read_text(encoding='utf-8-sig'))
scene = job['scene']
assert scene in ('bistro', 'minecraft')
DEST = OUT/scene
DEST.mkdir(exist_ok=True)
data = dict(scene=scene, administrator=bool(ctypes.windll.shell32.IsUserAnAdmin()),
            classification='Per-draw replay diagnosis; not live GPU timing', captures=[], replays=[])
target = cap = controller = None
NAMES = [
    'GPU Duration', 'PS Invocations',
    'smsp__inst_executed.sum', 'smsp__thread_inst_executed.sum',
    'smsp__average_thread_inst_executed_per_inst_executed.avg.ratio',
    'l1tex__texin_requests.sum', 'l1tex__t_sector_pipe_tex_mem_texture_hit_rate.avg.pct',
    'lts__t_requests_srcunit_tex.sum', 'lts__t_sector_hit_rate.avg.pct', 'dram__bytes.sum',
    'smsp__warp_issue_stalled_long_scoreboard_per_warp_active.avg.ratio',
    'smsp__warp_issue_stalled_tex_throttle_per_warp_active.avg.ratio',
    'smsp__warp_issue_stalled_branch_resolving_per_warp_active.avg.ratio',
    'smsp__warp_issue_stalled_math_pipe_throttle_per_warp_active.avg.ratio',
    'smsp__warp_issue_stalled_not_selected_per_warp_active.avg.ratio',
]


def save():
    (DEST/'results.json').write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')


def actions(items, path=()):
    for a in items:
        names = path+(a.customName,)
        yield a, names
        yield from actions(a.children, names)


try:
    app = ROOT/'Projects/CMAA2/CMAA2.exe'
    data['executable_sha256'] = hashlib.sha256(app.read_bytes()).hexdigest()
    before = set((app.parent/'AutoBench').glob('*/*_results.csv'))
    opts = rd.CaptureOptions()
    opts.apiValidation=False
    opts.captureCallstacks=False
    launch=rd.ExecuteAndInject(str(app), str(app.parent),
        '-smaaTemporalCounterCapture '+scene+' -smaaNonInteractiveShaderCompile', [],
        str(DEST/'capture'), opts, False)
    if launch.result != rd.ResultCode.Succeeded:
        raise RuntimeError('Capture launch: '+str(launch.result))
    target=rd.CreateTargetControl('',launch.ident,'SMAA frame-90 counter captures',False)
    if target is None:
        raise RuntimeError('Target control unavailable')
    data['target_pid']=target.GetPID()
    save()
    deadline=time.monotonic()+120
    while target.Connected() and time.monotonic()<deadline:
        msg=target.ReceiveMessage(None)
        if msg.type==rd.TargetControlMessageType.NewCapture:
            data['captures'].append(dict(path=msg.newCapture.path, renderdoc_frame=msg.newCapture.frameNumber))
            save()
    if target.Connected():
        raise RuntimeError('Capture timed out')
    target.Shutdown();target=None
    reports=set((app.parent/'AutoBench').glob('*/*_results.csv'))-before
    assert len(reports)==1, 'Expected exactly one new completed report'
    report=reports.pop()
    report_text=report.read_text(encoding='utf-8-sig')
    modes=['O-T2X-R','ABL-Contrast-001-R','ABL-ScalarWeight-001-R']
    assert 'Aggregate: PASS' in report_text and 'Aggregate: FAIL' not in report_text
    for mode in modes:
        assert 'renderdoc_capture, '+mode+', 90, PASS' in report_text
    assert len(data['captures'])==3
    data['capture_report']=str(report)
    data['capture_report_sha256']=hashlib.sha256(report.read_bytes()).hexdigest()
    for capture,mode in zip(data['captures'],modes):
        path=Path(capture['path'])
        assert path.name.startswith(mode+'_'), path
        cap=rd.OpenCaptureFile()
        status=cap.OpenFile(str(path),'',None)
        assert status==rd.ResultCode.Succeeded, str(status)
        status,controller=cap.OpenCapture(rd.ReplayOptions(),None)
        assert status==rd.ResultCode.Succeeded, str(status)
        replay=dict(mode=mode,capture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    api=str(controller.GetAPIProperties().pipelineType))
        data['replays'].append(replay)
        flat=list(actions(controller.GetRootActions()))
        draws=[a for a,names in flat if any('SMAATemporalResolve' in n for n in names)
               and bool(a.flags & rd.ActionFlags.Drawcall)]
        replay['temporal_draw_ids']=[a.eventId for a in draws]
        replay['named_actions']=[dict(event=a.eventId,name=a.customName) for a,names in flat if a.customName]
        assert len(draws)==1, 'Expected one temporal draw'
        event=draws[0].eventId
        controller.SetFrameEvent(event,True)
        pipe=controller.GetPipelineState()
        refl=pipe.GetShaderReflection(rd.ShaderStage.Pixel)
        replay['pixel_shader']=str(pipe.GetShader(rd.ShaderStage.Pixel))
        replay['shader_entry']=refl.entryPoint
        disassembly=controller.DisassembleShader(rd.ResourceId.Null(),refl,'DXBC')
        (DEST/(mode+'.dxbc.txt')).write_text(disassembly,encoding='utf-8')
        replay['shader_dxbc_sha256']=hashlib.sha256(disassembly.encode()).hexdigest()
        descriptions={controller.DescribeCounter(c).name: controller.DescribeCounter(c)
                      for c in controller.EnumerateCounters()}
        selected=[descriptions[n] for n in NAMES if n in descriptions]
        replay['missing_counters']=[n for n in NAMES if n not in descriptions]
        replay['counter_descriptions']=[dict(id=int(d.counter),name=d.name,description=d.description,
            unit=str(d.unit),result_type=str(d.resultType),byte_width=d.resultByteWidth) for d in selected]
        replay['state_attributes']=[n for n in dir(controller.GetD3D11PipelineState().pixelShader) if not n.startswith('_')]
        save()
        # RenderDoc replays all draw ranges, then retain only the identified temporal draw.
        replay['counter_runs']=[]
        for repeat in range(3):
            rows=controller.FetchCounters([d.counter for d in selected])
            values={}
            for row in rows:
                if row.eventId!=event:
                    continue
                d=next(d for d in selected if d.counter==row.counter)
                if d.resultType==rd.CompType.Float:
                    v=row.value.d if d.resultByteWidth==8 else row.value.f
                elif d.resultType==rd.CompType.UInt:
                    v=row.value.u64 if d.resultByteWidth==8 else row.value.u32
                else:
                    raise RuntimeError('Unexpected counter type')
                values[d.name]=v if math.isfinite(v) else None
            assert all(d.name in values for d in selected), 'Missing draw counters'
            replay['counter_runs'].append(values)
            save()
        replay['debug_messages']=[m.description for m in controller.GetDebugMessages()]
        controller.Shutdown();controller=None
        cap.Shutdown();cap=None
        save()
    data['status']='PASS'
except Exception:
    data['status']='FAILED'
    data['error']=traceback.format_exc()
finally:
    if controller is not None: controller.Shutdown()
    if cap is not None: cap.Shutdown()
    if target is not None: target.Shutdown()
    save()
raise SystemExit(0 if data['status']=='PASS' else 1)
