// Native first-pass edges, hardware stencil rejection, native T2X-R math.
// No edge SRV read, selection branch, or full-screen current-color return here.
#ifdef VA_COMPILED_AS_SHADER_CODE
// The engine supplies application macros through this virtual include, not /D.
#include "MagicMacrosMagicFile.h"
#endif
#ifdef SMAA_CAPTURE_HISTORY_WEIGHT
// Per-invocation observation of the weight calculated by the native resolve.
// Only the capture entry point defines this; production shaders are unchanged.
static float capturedHistoryWeight = 0.0;
#define SMAA_REPORT_HISTORY_WEIGHT(value) capturedHistoryWeight = (value)
#endif
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

#ifdef SMAA_CAPTURE_HISTORY_WEIGHT
[earlydepthstencil]
void FirstEdgeHistoryContributionPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
    out float4 visible : SV_TARGET0, out float coverage : SV_TARGET1,
    out float historyWeight : SV_TARGET2) {
    visible = DX10_SMAAResolvePS(p, uv);
    coverage = 1.0;
    historyWeight = capturedHistoryWeight;
}
#endif
