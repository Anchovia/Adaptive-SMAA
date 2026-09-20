"""Compile bounded same-selector optimizations before spending time on GPU runs."""
import hashlib, json, re, subprocess
from pathlib import Path
import validate_temporal_contrast_shaders as base

prefix='#include "SMAAWrapper.hlsl"\n'
weight='float d=abs(current.a*current.a-previous.a*previous.a)/5.0; float w=0.5*saturate(1.0-sqrt(d)*SMAA_REPROJECTION_WEIGHT_SCALE);'
reassoc='float d=abs(current.a*current.a-previous.a*previous.a); float w=max(0.5-sqrt(d*(0.25*SMAA_REPROJECTION_WEIGHT_SCALE*SMAA_REPROJECTION_WEIGHT_SCALE/5.0)),0.0);'
setup='float4 current=SMAASamplePoint(colorTex,uv); float c=SMAATemporalContrast(current.rgb);'
sample='float2 velocity=ContrastExecutionVelocity(uv); float4 previous=colorTexPrev.SampleLevel(PointSampler,uv+velocity,0);'
sources={
    'ScalarWeight': setup+sample+weight+'w=c>=g_SMAA.padding0?w:0.0; return lerp(current,previous,w);',
    'ScalarMultiply': setup+sample+weight+'w*=c>=g_SMAA.padding0?1.0:0.0; return lerp(current,previous,w);',
    'ScalarWeightReassociated':setup+sample+reassoc+'w=c>=g_SMAA.padding0?w:0.0; return lerp(current,previous,w);',
    'BranchReassociated':setup+'[branch] if(c<g_SMAA.padding0)return current;'+sample+reassoc+'return lerp(current,previous,w);',
    'HistoryLoad':setup+'[branch] if(c<g_SMAA.padding0)return current; float2 velocity=ContrastExecutionVelocity(uv); int2 p=clamp(int2((uv+velocity)*SMAA_RT_METRICS.zw),int2(0,0),int2(SMAA_RT_METRICS.zw)-1); float4 previous=colorTexPrev.Load(int3(p,0));'+weight+'return lerp(current,previous,w);',
    'SelectorAny':'float4 current=SMAASamplePoint(colorTex,uv); float y=dot(current.rgb,float3(0.2126,0.7152,0.0722)); bool selected=any(abs(float2(ddx_fine(y),ddy_fine(y)))>=g_SMAA.padding0); [branch] if(!selected)return current;'+sample+weight+'return lerp(current,previous,w);',
}
sources['FixedThreshold']=(setup+'[branch] if(c<g_SMAA.padding0)return current;'+sample+weight+'return lerp(current,previous,w);').replace('g_SMAA.padding0','0.01')
sources['ScalarFixedThreshold']=sources['ScalarWeight'].replace('g_SMAA.padding0','0.01')
out=base.root/'tmp/temporal-cost-probes';out.mkdir(parents=True,exist_ok=True)
rows=[]
for name,body in sources.items():
    path=out/(name+'.hlsl')
    path.write_text(prefix+'float4 Probe(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET{'+body+'}\n')
    blob,asm=base.compile(path,'Probe',1,'ps_5_0',name)
    code=[l.strip() for l in asm.splitlines() if l.strip() and not l.strip().startswith('//')]
    rows.append(dict(name=name,sha256=hashlib.sha256(blob).hexdigest(),
        instruction_sha256=hashlib.sha256('\n'.join(code).encode()).hexdigest(),
        instructions=code,slots=int(re.search(r'Approximately (\d+) instruction',asm)[1])))
    print(name,rows[-1]['slots'],rows[-1]['instruction_sha256'],flush=True)
dest=base.root/'Docs/Temporal-Contrast-Cost';dest.mkdir(parents=True,exist_ok=True)
(dest/'probes.json').write_text(json.dumps(rows,indent=2)+'\n')
