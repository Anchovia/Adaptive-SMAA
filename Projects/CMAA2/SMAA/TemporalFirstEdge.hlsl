// Exact completed first-pass edge RG. No contrast proxy, expansion or new threshold.
// Native Standard temporal semantics, including spatial-frame history, are preserved.
float4 DX10_SMAAFirstEdgeReusePS(float4 position:SV_POSITION,float2 texcoord:TEXCOORD0):SV_TARGET {
    float4 current=SMAASamplePoint(colorTex,texcoord);
    float2 edge=SMAAReadFirstEdgeLoad(position);
    [branch]
    if (!any(edge>0.0))
        return current;
    #if SMAA_REPROJECTION
    float2 velocity = -SMAA_DECODE_VELOCITY(SMAASamplePoint(velocityTex, texcoord).rg);
    float4 previous = SMAASamplePoint(colorTexPrev, texcoord + velocity);
    float delta = abs(current.a * current.a - previous.a * previous.a) / 5.0;
    float weight = 0.5 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
    return lerp(current, previous, weight);
    #else
    float4 previous = SMAASamplePoint(colorTexPrev, texcoord);
    return lerp(current, previous, 0.5);
    #endif
}

// Prior experiment/standard-t2x-edge-mask entry body copied unchanged; only name differs.
float4 DX10_SMAAFirstEdgeLegacyPS(float4 position : SV_POSITION,
                                float2 texcoord : TEXCOORD0) : SV_TARGET {
    [branch]
    if (!any(edgesTex.Load(int3(int2(position.xy), 0)).rg > 0.0))
        return SMAASamplePoint(colorTex, texcoord);
    #if SMAA_REPROJECTION
    return SMAAResolvePS(texcoord, colorTex, colorTexPrev, velocityTex);
    #else
    return SMAAResolvePS(texcoord, colorTex, colorTexPrev);
    #endif
}
