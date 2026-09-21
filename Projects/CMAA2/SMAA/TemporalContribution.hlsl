// Experimental contribution gate in the existing temporal draw.
// Reads are unchanged; selection occurs AFTER history sampling and weight calculation.
float TemporalContributionMask(float4 current, float4 previous, float weight) {
    float3 delta=abs(current.rgb-previous.rgb);
    float impact=weight*max(delta.r,max(delta.g,delta.b));
    return step(g_SMAA.padding0,impact);
}

float4 DX10_SMAAContributionNativePS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 current=SMAASamplePoint(colorTex,uv);
    float4 previous=SMAASamplePoint(colorTexPrev,uv+velocity);
    float weight=TemporalOriginalWeight(current,previous);
    float selected=TemporalContributionMask(current,previous,weight);
    return lerp(current,previous,weight*selected);
}

float4 DX10_SMAAContributionNativeMaskPS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 current=SMAASamplePoint(colorTex,uv);
    float4 previous=SMAASamplePoint(colorTexPrev,uv+velocity);
    float weight=TemporalOriginalWeight(current,previous);
    float selected=TemporalContributionMask(current,previous,weight);
    return float4(selected.xxx,1);
}

float4 DX10_SMAAContributionPairedPS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float index=g_SMAA.subsampleIndices.x;
    float2 jitter=(index==1.0?.25:(index==2.0?-.25:0))*SMAA_RT_METRICS.xy;
    float4 current=TemporalCurrentLinear(uv+jitter);
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    float selected=TemporalContributionMask(current,previous,weight);
    return lerp(current,previous,weight*selected);
}

float4 DX10_SMAAContributionPairedMaskPS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    float index=g_SMAA.subsampleIndices.x;
    float2 jitter=(index==1.0?.25:(index==2.0?-.25:0))*SMAA_RT_METRICS.xy;
    float4 current=TemporalCurrentLinear(uv+jitter);
    float2 velocity=ContrastExecutionVelocity(uv);
    float4 previous=colorTexPrev.SampleLevel(LinearSampler,uv+velocity-jitter,0);
    float weight=TemporalOriginalWeight(current,previous);
    float selected=TemporalContributionMask(current,previous,weight);
    return float4(selected.xxx,1);
}

float4 DX10_SMAAContributionZeroMaskPS(float4 p:SV_POSITION,float2 uv:TEXCOORD0):SV_TARGET {
    return float4(0,0,0,1);
}
