// Diagnostic only. Runtime padding0=0 preserves output while retaining the read.
// First-pass edge RG, no thresholding, filtering, candidate test or extra output.
float4 DX10_SMAAEdgeReadControlPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float4 nativeColor=DX10_SMAAResolvePS(position,uv);
    nativeColor.rg += g_SMAA.padding0*g_SMAA.subsampleIndices.xy;
    return nativeColor;
}

float4 DX10_SMAAEdgeReadOnePS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float4 nativeColor=DX10_SMAAResolvePS(position,uv);
    float2 edge=edgesTex.Load(int3(int2(position.xy),0)).rg;
    nativeColor.rg += g_SMAA.padding0*edge;
    return nativeColor;
}
