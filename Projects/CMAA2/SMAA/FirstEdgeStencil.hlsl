// Native first-pass edges, hardware stencil rejection, native T2X-R math.
// No edge SRV read, selection branch, or full-screen current-color return here.
#include "SMAAWrapper.hlsl"

#define EXACT_EDGE_ENTRY(name, original) \
float2 name(float4 p : SV_POSITION, float2 uv : TEXCOORD0, float4 offset[3] : TEXCOORD1) : SV_TARGET { \
    float2 edge = original(p, uv, offset); \
    if (!any(edge > 0.0)) discard; \
    return edge; \
}
// Native discard happens BEFORE local contrast adaptation. This final test makes
// stencil identical to the final stored RG, including edges removed by adaptation.
EXACT_EDGE_ENTRY(ExactLumaEdgePS, DX10_SMAALumaEdgeDetectionPS)
EXACT_EDGE_ENTRY(ExactLumaRawEdgePS, DX10_SMAALumaRawEdgeDetectionPS)
EXACT_EDGE_ENTRY(ExactColorEdgePS, DX10_SMAAColorEdgeDetectionPS)
EXACT_EDGE_ENTRY(ExactDepthEdgePS, DX10_SMAADepthEdgeDetectionPS)

void NeighborhoodRetainPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                         float4 offset : TEXCOORD1,
                         out float4 history : SV_TARGET0, out float4 visible : SV_TARGET1) {
    history = DX10_SMAANeighborhoodBlendingPS(p, uv, offset);
    visible = history;
}

[earlydepthstencil]
float4 FirstEdgeStencilPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    return DX10_SMAAResolvePS(p, uv);
}

// Capture-only coverage witness. Never used for performance measurement.
[earlydepthstencil]
void FirstEdgeStencilCoveragePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                               out float4 visible : SV_TARGET0, out float coverage : SV_TARGET1) {
    visible = DX10_SMAAResolvePS(p, uv);
    coverage = 1.0;
}

// RGB-only sampler experiment. Point alpha and native weight remain unchanged.
float4 BilinearHistoryRGBResolve(float2 uv, out float historyWeight) {
#if SMAA_REPROJECTION
    float2 velocity = -SMAA_DECODE_VELOCITY(SMAASamplePoint(velocityTex, uv).rg);
    float4 current = SMAASamplePoint(colorTex, uv);
    float4 previous = SMAASamplePoint(colorTexPrev, uv + velocity);
    float delta = abs(current.a * current.a - previous.a * previous.a) / 5.0;
    float weight = 0.5 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
    previous.rgb = SMAASampleLevelZero(colorTexPrev, uv + velocity).rgb;
    historyWeight = weight;
    return lerp(current, previous, weight);
#else
    float4 current = SMAASamplePoint(colorTex, uv);
    float4 previous = SMAASamplePoint(colorTexPrev, uv);
    previous.rgb = SMAASampleLevelZero(colorTexPrev, uv).rgb;
    historyWeight = 0.5;
    return lerp(current, previous, 0.5);
#endif
}

[earlydepthstencil]
float4 BilinearHistoryRGBPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float weight;
    return BilinearHistoryRGBResolve(uv, weight);
}

// R32 weight and coverage are capture-only. Production has one color target.
[earlydepthstencil]
void BilinearHistoryRGBCoveragePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                                out float4 visible : SV_TARGET0, out float coverage : SV_TARGET1,
                                out float weight : SV_TARGET2) {
    visible = BilinearHistoryRGBResolve(uv, weight);
    coverage = 1.0;
}

[earlydepthstencil]
void FirstEdgeStencilWeightCoveragePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                                     out float4 visible : SV_TARGET0, out float coverage : SV_TARGET1,
                                     out float weight : SV_TARGET2) {
    visible = DX10_SMAAResolvePS(p, uv);
#if SMAA_REPROJECTION
    float2 velocity = -SMAA_DECODE_VELOCITY(SMAASamplePoint(velocityTex, uv).rg);
    float4 current = SMAASamplePoint(colorTex, uv);
    float4 previous = SMAASamplePoint(colorTexPrev, uv + velocity);
    float delta = abs(current.a * current.a - previous.a * previous.a) / 5.0;
    weight = 0.5 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
#else
    weight = 0.5;
#endif
    coverage = 1.0;
}
