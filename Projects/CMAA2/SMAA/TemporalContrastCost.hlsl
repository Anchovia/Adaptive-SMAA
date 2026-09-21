// Same pixelwise luma selector, no extra pass/resource. Experimental cost controls.
float TemporalOriginalWeight(float4 current, float4 previous) {
#if SMAA_REPROJECTION
    float delta = abs(current.a * current.a - previous.a * previous.a) / 5.0;
    return 0.5 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
#else
    return 0.5;
#endif
}

float TemporalReassociatedWeight(float4 current, float4 previous) {
#if SMAA_REPROJECTION
    // Algebraically identical; floating-point rounding MUST be checked separately.
    float delta = abs(current.a * current.a - previous.a * previous.a);
    return max(0.5 - sqrt(delta * (0.25 * SMAA_REPROJECTION_WEIGHT_SCALE * SMAA_REPROJECTION_WEIGHT_SCALE / 5.0)), 0.0);
#else
    return 0.5;
#endif
}

float4 DX10_SMAAScalarWeightResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    float weight = TemporalOriginalWeight(current, previous);
    weight = contrast >= g_SMAA.padding0 ? weight : 0.0;
    return lerp(current, previous, weight);
}

// Reuse the already-bound linear sampler. One history sampling instruction;
// hardware texel/filter cost is measured, not assumed equal to point sampling.
// RGBA is filtered together, including the velocity-alpha used by the weight.
float4 DX10_SMAAHistoryLinearResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 current = SMAASamplePoint(colorTex, uv);
    float4 previous = colorTexPrev.SampleLevel(LinearSampler, uv + velocity, 0);
    return ContrastExecutionBlend(current, previous);
}

float4 DX10_SMAAScalarHistoryLinearResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(LinearSampler, uv + velocity, 0);
    float weight = TemporalOriginalWeight(current, previous);
    weight = contrast >= g_SMAA.padding0 ? weight : 0.0;
    return lerp(current, previous, weight);
}

float4 DX10_SMAAScalarReassociatedResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    float weight = TemporalReassociatedWeight(current, previous);
    weight = contrast >= g_SMAA.padding0 ? weight : 0.0;
    return lerp(current, previous, weight);
}

float4 DX10_SMAABranchReassociatedResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    [branch] if (contrast < g_SMAA.padding0) return current;
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    return lerp(current, previous, TemporalReassociatedWeight(current, previous));
}

float4 DX10_SMAAHistoryLoadResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    [branch] if (contrast < g_SMAA.padding0) return current;
    float2 velocity = ContrastExecutionVelocity(uv);
    // Candidate for point/clamp equivalence. Fractional UV precision is a gate.
    int2 pixel = clamp(int2((uv + velocity) * SMAA_RT_METRICS.zw), int2(0, 0), int2(SMAA_RT_METRICS.zw) - 1);
    float4 previous = colorTexPrev.Load(int3(pixel, 0));
    return lerp(current, previous, TemporalOriginalWeight(current, previous));
}

float4 DX10_SMAASelectorAnyResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float y = dot(current.rgb, float3(0.2126, 0.7152, 0.0722));
    bool selected = any(abs(float2(ddx_fine(y), ddy_fine(y))) >= g_SMAA.padding0);
    [branch] if (!selected) return current;
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    return lerp(current, previous, TemporalOriginalWeight(current, previous));
}

// Specialize the existing 0.01 threshold; do not change its value or selector.
float4 DX10_SMAAFixedThresholdResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    [branch] if (contrast < 0.01) return current;
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    return lerp(current, previous, TemporalOriginalWeight(current, previous));
}

float4 DX10_SMAAScalarFixedThresholdResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    float weight = TemporalOriginalWeight(current, previous);
    weight = contrast >= 0.01 ? weight : 0.0;
    return lerp(current, previous, weight);
}
