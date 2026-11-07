// Edge-selective temporal route on top of unmodified SMAA (camera/depth reprojection only).
// Selected pixels are the current raw edges plus camera-reprojected previous raw edges,
// marked in the first-pass stencil. The raw RG output keeps current edges only.

// Same edge equations as SMAA.hlsl, except that a pixel without a current edge returns
// zero instead of discarding, so the entry points below decide whether to keep it.
#define discard return (SMAA_EDGE_OUTPUT)0
#include "SMAAWrapper.hlsl"
#undef discard
#include "CatmullRomHistory5Tap.hlsli"

// Adaptive SMAA adds the search tier as a second edge-pass target.
#if defined(SMAA_ADAPTIVE_SEARCH)
#define EDGES_OF(output) (output).edges
#define VELOCITY_TARGET SV_TARGET2
#else
#define EDGES_OF(output) (output)
#define VELOCITY_TARGET SV_TARGET1
#endif

Texture2D previousRawEdges : register(t10);

bool PreviousRawEdgeFrom(float2 uv, float2 velocity) {
    float2 previousUV = uv - velocity;
    bool inBounds = all(previousUV >= 0.0) && all(previousUV < 1.0);
    int2 previousPixel = int2(floor(previousUV * SMAA_RT_METRICS.zw));
    bool previousEdge = any(previousRawEdges.Load(int3(previousPixel, 0)).rg > 0.0);
    return inBounds && previousEdge;
}

#define SELECTED_EDGE_PS(kind)                                                                  \
SMAA_EDGE_OUTPUT Selected##kind##EdgePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0, \
                              float4 offset[3] : TEXCOORD1) SMAA_EDGE_OUTPUT_SEMANTIC {             \
    float2 velocity = velocityTex.SampleLevel(PointSampler, texcoord, 0).rg;                    \
    bool oldEdge = PreviousRawEdgeFrom(texcoord, velocity);                                     \
    SMAA_EDGE_OUTPUT edge = DX10_SMAA##kind##EdgeDetectionPS(position, texcoord, offset);       \
    if (!(any(EDGES_OF(edge) > 0.0) || oldEdge)) discard;                                       \
    return edge;                                                                                \
}

// Case 19: this draw computes the camera velocity instead of a separate full-screen pass.
// Only retained pixels store it, and the resolve reads no others. The lookup uses the
// float16 value that a separate velocity texture would have returned.
#define SELECTED_VELOCITY_EDGE_PS(kind)                                                           \
void Selected##kind##VelocityEdgePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0,   \
                                    float4 offset[3] : TEXCOORD1,                                 \
                                    out SMAA_EDGE_OUTPUT edge SMAA_EDGE_OUTPUT_SEMANTIC,          \
                                    out float2 velocity : VELOCITY_TARGET) {                      \
    velocity = DX10_SMAAGenerateCameraVelocityPS(position, texcoord);                             \
    bool oldEdge = PreviousRawEdgeFrom(texcoord, f16tof32(f32tof16(velocity)));                   \
    edge = DX10_SMAA##kind##EdgeDetectionPS(position, texcoord, offset);                          \
    if (!(any(EDGES_OF(edge) > 0.0) || oldEdge)) discard;                                         \
}

SELECTED_EDGE_PS(Luma)
SELECTED_EDGE_PS(LumaRaw)
SELECTED_EDGE_PS(Color)
SELECTED_EDGE_PS(Depth)
SELECTED_VELOCITY_EDGE_PS(Luma)
SELECTED_VELOCITY_EDGE_PS(LumaRaw)
SELECTED_VELOCITY_EDGE_PS(Color)
SELECTED_VELOCITY_EDGE_PS(Depth)

// Compiled without SMAA_REPROJECTION: the packed velocity alpha has no reader on this route.
void SelectedNeighborhoodPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0, float4 offset : TEXCOORD1,
                            out float4 spatial : SV_TARGET0, out float4 history : SV_TARGET1) {
    spatial = DX10_SMAANeighborhoodBlendingPS(p, uv, offset);
    history = spatial;
}

float3 SelectedHistoryRGB(float2 uv) {
    float2 historyUV = uv - velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    return SampleHistoryCatmullRom5Tap(colorTexPrev, LinearSampler, historyUV, SMAA_RT_METRICS.zw);
}

// The SRVs and RTVs use the hardware sRGB transfer; the blend squares encoded values.
float3 LinearToEncoded(float3 v) {
    v = saturate(v);
    float3 hi = 1.055 * pow(v, 1.0 / 2.4) - 0.055;
    return float3(v.r <= .0031308 ? 12.92 * v.r : hi.r, v.g <= .0031308 ? 12.92 * v.g : hi.g, v.b <= .0031308 ? 12.92 * v.b : hi.b);
}
float3 EncodedToLinear(float3 v) {
    float3 hi = pow((v + 0.055) / 1.055, 2.4);
    return float3(v.r <= .04045 ? v.r / 12.92 : hi.r, v.g <= .04045 ? v.g / 12.92 : hi.g, v.b <= .04045 ? v.b / 12.92 : hi.b);
}

[earlydepthstencil]
float4 SelectedResolvePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float3 c = LinearToEncoded(current.rgb), h = LinearToEncoded(SelectedHistoryRGB(uv));
    return float4(EncodedToLinear(sqrt(lerp(c * c, h * h, 0.8))), current.a);
}

// First frame and resets: the history is the current spatial colour.
[earlydepthstencil]
float4 SelectedSeedResolvePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    return float4(lerp(current.rgb, SelectedHistoryRGB(uv), 0.8), current.a);
}
