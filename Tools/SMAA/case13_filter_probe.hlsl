#include "../../Projects/CMAA2/SMAA/CatmullRomHistory5Tap.hlsli"
Texture2D<float4> probeTexture : register(t0);
StructuredBuffer<float2> probeUV : register(t1);
SamplerState probeSampler : register(s0);
RWStructuredBuffer<float4> probeResult : register(u0);
[numthreads(64,1,1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint count, stride, width, height;
    probeUV.GetDimensions(count, stride);
    if(id.x >= count) return;
    probeTexture.GetDimensions(width, height);
    probeResult[id.x*2] = float4(SampleHistoryCatmullRom5Tap(probeTexture, probeSampler,
                                      probeUV[id.x], float2(width,height)), 1);
    probeResult[id.x*2+1] = probeTexture.SampleLevel(probeSampler, probeUV[id.x], 0);
}
