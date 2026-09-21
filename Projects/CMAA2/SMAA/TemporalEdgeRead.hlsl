// Diagnostic only. Runtime padding0=0 preserves output while retaining the read.
// First-pass edge RG, no thresholding, filtering, candidate test or extra output.
#include "TemporalEdgeAccess.hlsl"
float4 DX10_SMAAEdgeReadControlPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float4 nativeColor=DX10_SMAAResolvePS(position,uv);
    nativeColor.rg += g_SMAA.padding0*g_SMAA.subsampleIndices.xy;
    return nativeColor;
}

float4 DX10_SMAAEdgeReadOnePS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float4 nativeColor=DX10_SMAAResolvePS(position,uv);
    float2 edge=SMAAReadFirstEdgeLoad(position);
    nativeColor.rg += g_SMAA.padding0*edge;
    return nativeColor;
}

float4 DX10_SMAAEdgeReadPointPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float4 nativeColor=DX10_SMAAResolvePS(position,uv);
    float2 edge=SMAAReadFirstEdgePoint(uv);
    nativeColor.rg += g_SMAA.padding0*edge;
    return nativeColor;
}
float4 DX10_SMAAEdgeReadEarlyLoadPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 edge=SMAAReadFirstEdgeLoad(position);
    float4 nativeColor=DX10_SMAAResolvePS(position,uv);
    nativeColor.rg += g_SMAA.padding0*edge;
    return nativeColor;
}
float4 DX10_SMAAEdgeReadEarlyPointPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 edge=SMAAReadFirstEdgePoint(uv);
    float4 nativeColor=DX10_SMAAResolvePS(position,uv);
    nativeColor.rg += g_SMAA.padding0*edge;
    return nativeColor;
}
// Capture only: R is exact float-RG mismatch; GB are the actual Load RG.
float4 DX10_SMAAEdgeReadVerifyPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 reference=SMAAReadFirstEdgeLoad(position);
    float2 sampledEdge=SMAAReadFirstEdgePoint(uv);
    return float4(any(reference!=sampledEdge)?1.0:0.0,reference,1.0);
}
