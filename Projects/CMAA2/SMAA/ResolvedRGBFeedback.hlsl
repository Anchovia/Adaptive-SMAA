// Case 11: feedback RGB only; native current-frame velocity alpha is preserved.
// These MRT outputs share the existing neighborhood/selected-resolve draws.
#include "FirstEdgeStencil.hlsl"

void NeighborhoodFeedbackSeedPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                                float4 offset : TEXCOORD1,
                                out float4 spatial : SV_TARGET0,
                                out float4 visible : SV_TARGET1,
                                out float4 history : SV_TARGET2) {
    spatial = DX10_SMAANeighborhoodBlendingPS(p, uv, offset);
    visible = spatial;
    history = spatial;
}

[earlydepthstencil]
void ResolvedRGBFeedbackPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                           out float4 visible : SV_TARGET0,
                           out float4 history : SV_TARGET1) {
    float weight;
    visible = BilinearHistoryRGBResolve(uv, weight);
    history = float4(visible.rgb, SMAASamplePoint(colorTex, uv).a);
}

// Capture-only witnesses; production binds just visible and history.
[earlydepthstencil]
void ResolvedRGBFeedbackCoveragePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                                   out float4 visible : SV_TARGET0,
                                   out float4 history : SV_TARGET1,
                                   out float coverage : SV_TARGET2,
                                   out float weight : SV_TARGET3) {
    visible = BilinearHistoryRGBResolve(uv, weight);
    history = float4(visible.rgb, SMAASamplePoint(colorTex, uv).a);
    coverage = 1.0;
}
