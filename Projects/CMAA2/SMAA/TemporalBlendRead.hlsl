// Diagnostic only: padding0 is a runtime zero in timing/output checks.
// Preserve native history reads/blending; force probe data to stay live in DXBC.
float4 DX10_SMAABlendReadControlPS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float4 nativeColor=DX10_SMAAResolvePS(position,uv);
    return nativeColor + g_SMAA.padding0*g_SMAA.subsampleIndices;
}

float4 DX10_SMAABlendReadOnePS(float4 position:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float4 nativeColor=DX10_SMAAResolvePS(position,uv);
    float4 weights=blendTex.Load(int3(int2(position.xy),0));
    return nativeColor + g_SMAA.padding0*weights;
}
