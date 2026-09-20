"""Check direct texel access controls and unchanged production shader entries."""
import hashlib, json, re
import validate_temporal_execution_shaders as previous
b=previous.base
rows=[]
for reproj in (0,1):
    for entry in ['DX10_SMAALoadCurrentResolvePS','DX10_SMAALoadCurrentVelocityResolvePS','DX10_SMAALoadContrastMaskPS']:
        blob,asm=b.compile(b.shader/'SMAAWrapper.hlsl',entry,reproj,'ps_5_0','dependency')
        ins=[s.strip() for s in asm.splitlines() if s and not s.startswith('//')]
        loads=[s for s in ins if s.startswith('ld_')]
        samples=[s for s in ins if s.startswith('sample')]
        expected=2 if reproj and 'CurrentVelocity' in entry else 1
        assert len(loads)==expected,(entry,loads)
        if 'Mask' not in entry:
            branch=next(i for i,s in enumerate(ins) if s.startswith('if_'))
            assert all(i<branch for i,s in enumerate(ins) if s.startswith('deriv_'))
            assert any('t4.' in s and s.startswith('sample_l') for s in ins[branch:])
        assert any(s.startswith('imin') for s in ins) and any(s.startswith('imax') for s in ins)
        rows.append(dict(entry=entry,reprojection=reproj,sha256=hashlib.sha256(blob).hexdigest(),
            slots=int(re.search(r'Approximately (\d+) instruction',asm)[1]),loads=loads,samples=samples))
out=b.root/'Docs/Temporal-Contrast-Dependency';out.mkdir(parents=True,exist_ok=True)
probe=b.out/'prefetch-rejected.hlsl'
probe.write_text('''#include "SMAAWrapper.hlsl"
float4 ProbeImplicit(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 v=-SMAA_DECODE_VELOCITY(SMAASamplePoint(velocityTex,uv).rg);
    float4 c=SMAASamplePoint(colorTex,uv);
    float contrast=SMAATemporalContrast(c.rgb);
    [branch] if(contrast>=g_SMAA.padding0)
        c=ContrastExecutionBlend(c,colorTexPrev.SampleLevel(PointSampler,uv+v,0));
    return c;
}
float4 ProbeGrad(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 huv=uv+ContrastExecutionVelocity(uv);
    float2 gx=ddx_fine(huv),gy=ddy_fine(huv);
    float4 c=SMAASamplePoint(colorTex,uv);
    float contrast=SMAATemporalContrast(c.rgb);
    [branch] if(contrast>=g_SMAA.padding0)
        c=ContrastExecutionBlend(c,colorTexPrev.SampleGrad(PointSampler,huv,gx,gy));
    return c;
}
''')
rejected=[]
for entry in ['ProbeImplicit','ProbeGrad']:
    blob,asm=b.compile(probe,entry,1,'ps_5_0','rejected')
    ins=[s.strip() for s in asm.splitlines() if s and not s.startswith('//')]
    branch=next(i for i,s in enumerate(ins) if s.startswith('if_'))
    velocity=next(i for i,s in enumerate(ins) if s.startswith('sample') and 't7.' in s)
    rejected.append(dict(entry=entry,velocity_before_branch=velocity<branch,
        status='Rejected: compiler sank the attempted prefetch; never GPU-benchmarked',
        sha256=hashlib.sha256(blob).hexdigest()))
    assert velocity>branch,(entry,'Compiler behavior changed: review this probe again')
(out/'shader-validation.json').write_text(json.dumps(rows,indent=2)+'\n')
(out/'rejected-prefetch-probes.json').write_text(json.dumps(rejected,indent=2)+'\n')
print('PASS: six direct-load variants; clamped coordinates, pre-branch derivatives and conditional history')
