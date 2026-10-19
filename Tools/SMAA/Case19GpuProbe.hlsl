#include "../../Projects/CMAA2/SMAA/Case19LumaGather.hlsli"
Texture2D luma : register(t0);
Texture2D edgeRG : register(t1);
Texture2D edgeRGBA : register(t2);
SamplerState pointClamp : register(s0);
SamplerState linearClamp : register(s1);
cbuffer Params : register(b0) {float4 metrics;}
RWStructuredBuffer<float4> errors : register(u0);
[numthreads(8,8,1)]
void Probe(uint3 p : SV_DispatchThreadID) {
    if(any(p.xy>=uint2(metrics.zw)))return;
    float2 uv=(float2(p.xy)+0.5)*metrics.xy;
    float3 a=float3(luma.SampleLevel(pointClamp,uv,0).r,
        luma.SampleLevel(pointClamp,uv-float2(metrics.x,0),0).r,
        luma.SampleLevel(pointClamp,uv-float2(0,metrics.y),0).r);
    float3 b=Case19GatherLumaCurrentLeftTop(luma,pointClamp,uv,metrics.xy);
    float e=0;
    // Include fractional SMAA search offsets and all screen boundaries.
    [unroll]for(int i=0;i<7;++i) {
        float2 q=uv+float2(-2.0+0.75*i,1.5-0.5*i)*metrics.xy;
        float2 x=edgeRG.SampleLevel(linearClamp,q,0).rg;
        float2 y=edgeRGBA.SampleLevel(linearClamp,q,0).rg;
        e=max(e,max(abs(x.x-y.x),abs(x.y-y.y)));
    }
    errors[p.x+p.y*uint(metrics.z)]=float4(abs(a-b),e);
}
