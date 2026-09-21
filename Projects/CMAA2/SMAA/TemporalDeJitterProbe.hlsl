// Standalone verification entry; not compiled or dispatched by the demo.
#define SMAA_HLSL_4_1 1
#define SMAA_PRESET_ULTRA 1
#define SMAA_REPROJECTION 1
#define SMAA_RT_METRICS float4(1.0/1920.0,1.0/1061.0,1920,1061)
#include "SMAAWrapper.hlsl"
RWTexture2D<float4> probeOut : register(u0);
[numthreads(8,8,1)]
void ProbeCS(uint3 p : SV_DispatchThreadID) {
    if(p.x >= 1920 || p.y >= 1061) return;
    float2 uv = (float2(p.xy)+.5)*SMAA_RT_METRICS.xy;
    probeOut[p.xy] = DX10_SMAADeJitterSpatialPS(float4(p.xy,0,1), uv);
}
