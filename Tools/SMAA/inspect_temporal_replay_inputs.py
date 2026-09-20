"""Inspect actual temporal draw inputs in existing captures; no new captures/counters."""
import hashlib
import json
import struct
import traceback
from pathlib import Path
import renderdoc as rd

ROOT=Path.cwd().parents[1]
OUT=ROOT/'tmp/rd-profiler'
result={'captures':[]}
cap=controller=None
try:
    for scene in ('minecraft','bistro'):
        report=json.loads((OUT/scene/'results.json').read_text(encoding='utf-8'))
        assert report['status']=='PASS'
        for capture,replay in zip(report['captures'],report['replays']):
            cap=rd.OpenCaptureFile()
            assert cap.OpenFile(capture['path'],'',None)==rd.ResultCode.Succeeded
            status,controller=cap.OpenCapture(rd.ReplayOptions(),None)
            assert status==rd.ResultCode.Succeeded
            controller.SetFrameEvent(replay['temporal_draw_ids'][0],True)
            pipe=controller.GetPipelineState()
            reflection=pipe.GetShaderReflection(rd.ShaderStage.Pixel)
            info={'scene':scene,'mode':replay['mode'],'resources':[],'constant_buffers':[]}
            result['captures'].append(info)
            info['read_only_doc']=pipe.GetReadOnlyResources.__doc__
            resources=pipe.GetReadOnlyResources(rd.ShaderStage.Pixel)
            for used in resources:
                record={'used_attrs':[n for n in dir(used) if not n.startswith('_')]}
                info['resources'].append(record)
                descriptor=used.descriptor
                record['descriptor_attrs']=[n for n in dir(descriptor) if not n.startswith('_')]
                record['access_attrs']=[n for n in dir(used.access) if not n.startswith('_')]
                record['descriptor']=str(descriptor)
                record['resource']=str(descriptor.resource)
                record['index']=used.access.index
                record['shader_name']=reflection.readOnlyResources[used.access.index].name
                record['format']=descriptor.format.Name()
                raw=controller.GetTextureData(descriptor.resource,rd.Subresource())
                record['bytes']=len(raw)
                record['sha256']=hashlib.sha256(bytes(raw)).hexdigest()
            info['constant_methods']={n:getattr(pipe,n).__doc__ for n in dir(pipe) if 'Constant' in n}
            info['constant_blocks']=len(pipe.GetShaderReflection(rd.ShaderStage.Pixel).constantBlocks)
            for used in pipe.GetConstantBlocks(rd.ShaderStage.Pixel,True):
                d=used.descriptor
                raw=bytes(controller.GetBufferData(d.resource,d.byteOffset,d.byteSize))
                info['constant_buffers'].append(dict(index=used.access.index,bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),hex=raw.hex(),
                    float32=list(struct.unpack('<'+'f'*(len(raw)//4),raw))))
            controller.Shutdown();controller=None
            cap.Shutdown();cap=None
    result['status']='PASS'
except Exception:
    result['status']='FAILED'
    result['error']=traceback.format_exc()
finally:
    if controller is not None: controller.Shutdown()
    if cap is not None: cap.Shutdown()
    (OUT/'inputs.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
raise SystemExit(0 if result['status']=='PASS' else 1)
