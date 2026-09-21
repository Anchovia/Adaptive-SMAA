// Microbenchmark only: no native resolve, current/velocity/history reads or blending.
// Runtime padding0=0 matches black output; scale=1 proves exact edge RG dataflow.
float4 DX10_SMAAEdgeOnlyOutputPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    return float4(g_SMAA.padding0*g_SMAA.subsampleIndices.xy,0.0,1.0);
}
float4 DX10_SMAAEdgeOnlyReadPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 edge=SMAAReadFirstEdgeLoad(position);
    return float4(g_SMAA.padding0*edge,0.0,1.0);
}
