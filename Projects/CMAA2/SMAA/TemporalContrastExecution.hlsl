// Same-selection execution controls. Existing native/contrast entries stay unchanged.
// HLSL branch/flatten and explicit-LOD semantics: see the experiment report.
float4 ContrastExecutionBlend(float4 current, float4 previous) {
#if SMAA_REPROJECTION
    float delta = abs(current.a * current.a - previous.a * previous.a) / 5.0;
    float weight = 0.5 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
#else
    float weight = 0.5;
#endif
    return lerp(current, previous, weight);
}

float2 ContrastExecutionVelocity(float2 uv) {
#if SMAA_REPROJECTION
    return -SMAA_DECODE_VELOCITY(velocityTex.SampleLevel(PointSampler, uv, 0).rg);
#else
    return float2(0, 0);
#endif
}

float4 DX10_SMAALodResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 current = SMAASamplePoint(colorTex, uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    return ContrastExecutionBlend(current, previous);
}

float4 DX10_SMAACurrentFirstResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    return ContrastExecutionBlend(current, previous);
}

float4 DX10_SMAAStructuredResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    [branch]
    if (contrast >= g_SMAA.padding0) {
        float2 velocity = ContrastExecutionVelocity(uv);
        float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
        current = ContrastExecutionBlend(current, previous);
    }
    return current;
}

float4 DX10_SMAAFlattenResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    [flatten]
    if (contrast >= g_SMAA.padding0) {
        float2 velocity = ContrastExecutionVelocity(uv);
        float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
        current = ContrastExecutionBlend(current, previous);
    }
    return current;
}

float4 DX10_SMAAPrefetchVelocityResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    // Attempted prefetch control: FXC may sink this read into the branch.
    // Inspect DXBC before attributing any timing change to scheduling.
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 current = SMAASamplePoint(colorTex, uv);
    float contrast = SMAATemporalContrast(current.rgb);
    [branch]
    if (contrast >= g_SMAA.padding0) {
        float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
        current = ContrastExecutionBlend(current, previous);
    }
    return current;
}
