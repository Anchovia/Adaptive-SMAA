// Same paired output; derivatives execute before any divergent flow.
float4 DX10_SMAASpeedBranchPS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float index=g_SMAA.subsampleIndices.x;
    float2 jitter=(index==1.0 ? 0.25 : (index==2.0 ? -0.25 : 0.0))*SMAA_RT_METRICS.xy;
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    [branch] if(!selected) return current;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    return lerp(current,previous,weight);
}
float4 DX10_SMAASpeedUniformScalarPS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=float2(g_SMAA.padding1,g_SMAA.padding2);
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}
float4 DX10_SMAASpeedUniformBranchPS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=float2(g_SMAA.padding1,g_SMAA.padding2);
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    [branch] if(!selected) return current;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    return lerp(current,previous,weight);
}
float4 DX10_SMAASpeedUniformPrefetchPS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=float2(g_SMAA.padding1,g_SMAA.padding2);
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    float2 velocity=ContrastExecutionVelocity(uv);
    [branch] if(!selected) return current;
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    return lerp(current,previous,weight);
}
#if VA_NV_WARP_EXTENSION
float4 DX10_SMAASpeedUniformWarpPS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=float2(g_SMAA.padding1,g_SMAA.padding2);
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    [branch] if(NvAny(selected)==0) return current;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}
#endif

float4 DX10_SMAASpeedPhasePositivePS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=.25*SMAA_RT_METRICS.xy;
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}

float4 DX10_SMAASpeedPhaseNegativePS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=-.25*SMAA_RT_METRICS.xy;
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}

#if VA_NV_WARP_EXTENSION
float4 DX10_SMAASpeedGroup4PS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=float2(g_SMAA.padding1,g_SMAA.padding2);
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    uint votes=NvBallot(selected);
    // Lane groups, not assumed to be screen-space quads or tiles.
    uint groupMask=15u << (uint(NvGetLaneId()) & ~3u);
    [branch] if((votes & groupMask)==0) return current;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}
float4 DX10_SMAASpeedGroup8PS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=float2(g_SMAA.padding1,g_SMAA.padding2);
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    uint votes=NvBallot(selected);
    // Lane groups, not assumed to be screen-space quads or tiles.
    uint groupMask=255u << (uint(NvGetLaneId()) & ~7u);
    [branch] if((votes & groupMask)==0) return current;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}
float4 DX10_SMAASpeedGroup16PS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=float2(g_SMAA.padding1,g_SMAA.padding2);
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    uint votes=NvBallot(selected);
    // Lane groups, not assumed to be screen-space quads or tiles.
    uint groupMask=65535u << (uint(NvGetLaneId()) & ~15u);
    [branch] if((votes & groupMask)==0) return current;
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}
float4 DX10_SMAASpeedDensity8PS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=float2(g_SMAA.padding1,g_SMAA.padding2);
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    uint votes=NvBallot(selected);
    // Warp-uniform density chooses execution only; pixel selection is fixed.
    [branch] if(countbits(votes)<8u) {
        [branch] if(!selected) return current;
    }
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}
float4 DX10_SMAASpeedDensity16PS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 jitter=float2(g_SMAA.padding1,g_SMAA.padding2);
    float4 current=TemporalCurrentLinear(uv+jitter);
    bool selected=SMAATemporalContrast(current.rgb)>=g_SMAA.padding0;
    uint votes=NvBallot(selected);
    // Warp-uniform density chooses execution only; pixel selection is fixed.
    [branch] if(countbits(votes)<16u) {
        [branch] if(!selected) return current;
    }
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    weight=selected?weight:0.0;
    return lerp(current,previous,weight);
}
#endif
