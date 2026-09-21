// Current-sample-only de-jitter diagnostic. No new pass or texture binding.
// vaCameraBase translates projected geometry by (+j.x,+j.y) screen pixels.
// T2X subsample index 1 is screen jitter (+.25,+.25); 2 is (-.25,-.25).
// Index 0 (paired pattern disabled) must produce zero correction.
float2 TemporalDeJitterUV(float2 uv) {
    float index = g_SMAA.subsampleIndices.x;
    float phase = index == 1.0 ? 0.25 : (index == 2.0 ? -0.25 : 0.0);
    return uv + phase * SMAA_RT_METRICS.xy;
}

float4 TemporalCurrentLinear(float2 uv) {
    return colorTex.SampleLevel(LinearSampler, uv, 0);
}

// Center-linear control separates sampler selection from the coordinate shift.
float4 DX10_SMAAScalarCurrentLinearResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = TemporalCurrentLinear(uv);
    float contrast = SMAATemporalContrast(current.rgb);
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    float weight = TemporalOriginalWeight(current, previous);
    weight = contrast >= g_SMAA.padding0 ? weight : 0.0;
    return lerp(current, previous, weight);
}

// This changes the current sample for ALL pixels. It is not the old hybrid's
// noncandidate-only replacement. History UV/filter/storage stay unchanged to
// isolate current-read reuse, so this is not a complete de-jittered T2X resolve.
float4 DX10_SMAACurrentDeJitterResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = TemporalCurrentLinear(TemporalDeJitterUV(uv));
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    return ContrastExecutionBlend(current, previous);
}

float4 DX10_SMAAScalarDeJitterResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = TemporalCurrentLinear(TemporalDeJitterUV(uv));
    // The shifted/filtered input changes the selector. Never label same-mask.
    float contrast = SMAATemporalContrast(current.rgb);
    float2 velocity = ContrastExecutionVelocity(uv);
    float4 previous = colorTexPrev.SampleLevel(PointSampler, uv + velocity, 0);
    float weight = TemporalOriginalWeight(current, previous);
    weight = contrast >= g_SMAA.padding0 ? weight : 0.0;
    return lerp(current, previous, weight);
}

// Valid history is the opposite member of the paired T2X pattern. The wrapper
// seeds invalid history with DeJitterSpatial instead of assuming an old phase.
// Velocity remains at the original UV; this is an explicit motion-boundary
// approximation, not per-object motion or disocclusion reconstruction.
float4 DX10_SMAAPairedDeJitterResolvePS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float index = g_SMAA.subsampleIndices.x;
    float2 jitter = (index == 1.0 ? 0.25 : (index == 2.0 ? -0.25 : 0.0)) * SMAA_RT_METRICS.xy;
    float2 currentUV = uv + jitter;
    float4 current = TemporalCurrentLinear(currentUV);
    float2 velocity = ContrastExecutionVelocity(uv);
    float2 previousUV = uv + velocity - jitter;
    float4 previous = colorTexPrev.SampleLevel(LinearSampler, previousUV, 0);
    return ContrastExecutionBlend(current, previous);
}

float4 DX10_SMAADeJitterMaskPS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float contrast = SMAATemporalContrast(TemporalCurrentLinear(TemporalDeJitterUV(uv)).rgb);
    float selected = contrast >= g_SMAA.padding0 ? 1.0 : 0.0;
    return float4(selected.xxx, 1.0);
}

float4 DX10_SMAADeJitterSpatialPS(float4 position : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    return TemporalCurrentLinear(TemporalDeJitterUV(uv));
}
