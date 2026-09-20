"""Run with installed qrenderdoc --python; capability probe, not a timing benchmark."""
import ctypes
import hashlib
import json
import time
import traceback
from pathlib import Path
import renderdoc as rd

# qrenderdoc executeFile does not define __file__. Launch from root/tmp/rd-profiler.
ROOT = Path.cwd().parents[1]
OUT = ROOT / 'tmp/rd-profiler'
OUT.mkdir(parents=True, exist_ok=True)
result = {'purpose': 'DX11 replay counter availability; not production performance',
          'administrator': bool(ctypes.windll.shell32.IsUserAnAdmin()), 'captures': []}
target = cap = controller = None


def save():
    (OUT/'counter-probe.json').write_text(json.dumps(result, indent=2), encoding='utf-8')


try:
    app = ROOT/'Projects/CMAA2/CMAA2.exe'
    result['executable_sha256'] = hashlib.sha256(app.read_bytes()).hexdigest()
    options = rd.CaptureOptions()
    options.apiValidation = False
    options.captureCallstacks = False
    launch = rd.ExecuteAndInject(str(app), str(app.parent),
        '-smaaTemporalPairSmoke minecraft AB -smaaNonInteractiveShaderCompile', [],
        str(OUT/'native-capability'), options, False)
    result['launch_result'] = str(launch.result)
    if launch.result != rd.ResultCode.Succeeded:
        raise RuntimeError('RenderDoc launch failed: '+str(launch.result))
    target = rd.CreateTargetControl('', launch.ident, 'SMAA counter capability probe', False)
    if target is None:
        raise RuntimeError('Target control unavailable')
    result['target_pid'] = target.GetPID()
    save()
    # Warmup snapshot only. No claim that this matches a benchmark profile frame.
    target.QueueCapture(1000, 1)
    deadline = time.monotonic()+120
    while target.Connected() and time.monotonic() < deadline:
        message = target.ReceiveMessage(None)
        if message.type == rd.TargetControlMessageType.NewCapture:
            result['captures'].append(dict(path=message.newCapture.path,
                                          frame=message.newCapture.frameNumber))
            save()
    if target.Connected():
        raise RuntimeError('Capture target did not exit within 120 seconds')
    target.Shutdown()
    target = None
    if len(result['captures']) != 1:
        raise RuntimeError('Expected one warmup capture')
    path = Path(result['captures'][0]['path'])
    result['capture_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    cap = rd.OpenCaptureFile()
    status = cap.OpenFile(str(path), '', None)
    if status != rd.ResultCode.Succeeded:
        raise RuntimeError('OpenFile: '+str(status))
    status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    if status != rd.ResultCode.Succeeded:
        raise RuntimeError('Replay: '+str(status))
    result['api'] = str(controller.GetAPIProperties().pipelineType)
    descriptions = []
    for c in controller.EnumerateCounters():
        d = controller.DescribeCounter(c)
        descriptions.append(dict(id=int(c), name=d.name, description=d.description,
                                 category=d.category, unit=str(d.unit),
                                 result_type=str(d.resultType), result_byte_width=d.resultByteWidth))
    result['counters'] = descriptions
    result['disassembly_targets'] = list(controller.GetDisassemblyTargets(False))
    result['debug_messages'] = [m.description for m in controller.GetDebugMessages()]
    result['status'] = 'CAPABILITY_QUERIED'
except Exception:
    result['status'] = 'FAILED'
    result['error'] = traceback.format_exc()
finally:
    if controller is not None:
        controller.Shutdown()
    if cap is not None:
        cap.Shutdown()
    if target is not None:
        target.Shutdown()
    save()
raise SystemExit(0 if result['status'] == 'CAPABILITY_QUERIED' else 1)
