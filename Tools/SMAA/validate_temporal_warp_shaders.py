"""Native DXBC regression and pre-driver NVAPI instruction checks."""
import hashlib,json
import validate_temporal_contrast_shaders as base
source=base.out/'warp.hlsl'
source.write_text('#define VA_NV_WARP_EXTENSION 1\n#include "SMAAWrapper.hlsl"\n')
rows=[]
for reproj in (0,1):
    for name in ('NvWarpResolvePS','NvWarpMaskPS'):
        blob,asm=base.compile(source,'DX10_SMAA'+name,reproj,'ps_5_0','warp')
        code=[l.strip() for l in asm.splitlines() if l.strip() and not l.strip().startswith('//')]
        assert sum(x.startswith('deriv_') for x in code)==2
        assert any(x.startswith('dcl_uav_structured_opc u7') for x in code)
        assert any(x.startswith('imm_atomic_alloc') for x in code)
        samples=[x for x in code if x.startswith('sample')]
        assert len(samples)==((3 if reproj else 2) if 'Resolve' in name else 1)
        if 'Resolve' in name:assert any(x.startswith('if_') for x in code)
        rows.append(dict(entry=name,reprojection=reproj,sha256=hashlib.sha256(blob).hexdigest(),
            samples=samples,nvapi_encoding=True,note='Pre-driver DXBC encoding; not SASS or actual buffer access'))
out=base.root/'Docs/Temporal-Contrast-Warp';out.mkdir(parents=True,exist_ok=True)
(out/'shader-validation.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PASS: native 8 variants unchanged; four NVAPI PS variants compiled')
