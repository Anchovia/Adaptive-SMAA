// Included only by explicitly opted-in NVAPI pixel shader variants.
#define NV_SHADER_EXTN_SLOT u7
#include "../../../External/NVAPI/nvHLSLExtns.h"

float4 DX10_SMAANvWarpResolvePS(float4 position:SV_POSITION, float2 uv:TEXCOORD0):SV_TARGET {
    float4 current=SMAASamplePoint(colorTex,uv);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    // Vote before any divergent return; every active lane sees the same branch.
    [branch] if(NvAny(selected)==0) return current;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(PointSampler,uv+velocity,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}
float4 DX10_SMAANvWarpMaskPS(float4 position:SV_POSITION, float2 uv:TEXCOORD0):SV_TARGET {
    float3 current=SMAASamplePoint(colorTex,uv).rgb;
    bool selected=SMAATemporalContrast(current)>=g_SMAA.padding0;
    return float4(selected,NvAny(selected)!=0,0,1);
}
