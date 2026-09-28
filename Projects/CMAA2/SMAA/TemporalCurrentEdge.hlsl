// Diagnostic only: preserve the original current-spatial point sample, including alpha.
// Runtime-zero matched RG sink retains edge work without changing the output.
float4 DX10_SMAACurrentOutputControlPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float4 current=SMAASamplePoint(colorTex,uv);
    current.rg += g_SMAA.padding0*g_SMAA.subsampleIndices.xy;
    return current;
}
float4 DX10_SMAACurrentEdgeReadPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float4 current=SMAASamplePoint(colorTex,uv);
    float2 edge=SMAAReadFirstEdgeLoad(position);
    current.rg += g_SMAA.padding0*edge;
    return current;
}
