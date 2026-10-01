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

// Previous RAW first-pass edges, never the union mask. Bound only for persistence.
Texture2D previousRawEdges : register(t10);

void NeighborhoodCurrentDepthPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                               float4 offset : TEXCOORD1,
                               out float4 history : SV_TARGET0, out float4 visible : SV_TARGET1,
                               out float selectionDepth : SV_Depth) {
    history = DX10_SMAANeighborhoodBlendingPS(p, uv, offset);
    visible = history;
    selectionDepth = any(edgesTex.Load(int3(int2(p.xy), 0)).rg > 0.0) ? 1.0 : 0.0;
}

void NeighborhoodPersistencePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                              float4 offset : TEXCOORD1,
                              out float4 history : SV_TARGET0, out float4 visible : SV_TARGET1,
                              out float selectionDepth : SV_Depth) {
    history = DX10_SMAANeighborhoodBlendingPS(p, uv, offset);
    visible = history;
    bool currentEdge = any(edgesTex.Load(int3(int2(p.xy), 0)).rg > 0.0);
    // Match native resolve's point velocity and history texel, not the velocity
    // blended by the spatial neighborhood shader into history alpha.
    float2 previousUV = uv - velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    bool inBounds = all(previousUV >= 0.0) && all(previousUV < 1.0);
    int2 previousPixel = int2(floor(previousUV * SMAA_RT_METRICS.zw));
    // Texture Load is defined as zero outside the texture; the explicit UV gate
    // also rejects border coordinates instead of clamping old edge marks.
    bool previousEdge = any(previousRawEdges.Load(int3(previousPixel, 0)).rg > 0.0);
    selectionDepth = (currentEdge || (inBounds && previousEdge)) ? 1.0 : 0.0;
}

// Diagnostic only: baseline constant raster depth expressed as a shader export.
void NeighborhoodConstantDepthPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                                float4 offset : TEXCOORD1,
                                out float4 history : SV_TARGET0, out float4 visible : SV_TARGET1,
                                out float selectionDepth : SV_Depth) {
    history = DX10_SMAANeighborhoodBlendingPS(p, uv, offset);
    visible = history;
    selectionDepth = 1.0;
}

// Fullscreen triangle raster depth is 1; both exported values 0/1 satisfy <=.
void NeighborhoodConservativeDepthPS(noperspective centroid float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                              float4 offset : TEXCOORD1,
                              out float4 history : SV_TARGET0, out float4 visible : SV_TARGET1,
                              out float selectionDepth : SV_DepthLessEqual) {
    history = DX10_SMAANeighborhoodBlendingPS(p, uv, offset);
    visible = history;
    bool currentEdge = any(edgesTex.Load(int3(int2(p.xy), 0)).rg > 0.0);
    // Match native resolve's point velocity and history texel, not the velocity
    // blended by the spatial neighborhood shader into history alpha.
    float2 previousUV = uv - velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    bool inBounds = all(previousUV >= 0.0) && all(previousUV < 1.0);
    int2 previousPixel = int2(floor(previousUV * SMAA_RT_METRICS.zw));
    // Texture Load is defined as zero outside the texture; the explicit UV gate
    // also rejects border coordinates instead of clamping old edge marks.
    bool previousEdge = any(previousRawEdges.Load(int3(previousPixel, 0)).rg > 0.0);
    selectionDepth = (currentEdge || (inBounds && previousEdge)) ? 1.0 : 0.0;
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
