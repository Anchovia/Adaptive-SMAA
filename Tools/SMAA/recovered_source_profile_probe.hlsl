// Compile with /D SMAA_TSCMAA_COMPUTE=1; exercises the production functions.
#include "../../Projects/CMAA2/SMAA/RecoveredTSCMAA.hlsl"
RWStructuredBuffer<float4> profileProbe : register(u0);
[numthreads(1,1,1)]
void ProfileProbeCS(uint3 id:SV_DispatchThreadID) {
    int2 p=int2(id.xy), size=int2(35,29);
    uint index=(id.y*35+id.x)*4;
    float2 uv=(float2(p)+float2(0.87,1.11))/float2(size);
    float3 history=BicubicTextureSample(tscmaaHistoryColor,LinearSampler,uv,size.x,size.y);
    float2 center=(float2(p)+0.5)/float2(size);
    float3 current=tscmaaCurrentColor.Load(int3(p,0)).rgb;
    profileProbe[index]=float4(RecoveredFourEdges(p,size));
    profileProbe[index+1]=float4(history,1);
    profileProbe[index+2]=float4(ClipColor(history,current,tscmaaCurrentColor,center,LinearSampler,0.263157904,size.x,size.y),1);
    profileProbe[index+3]=RecoveredTemporalPixel(p,size);
}
