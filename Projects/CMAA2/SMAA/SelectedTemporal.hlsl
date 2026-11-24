// Selected temporal route of the improved SMAA (camera/depth reprojection only), on top of unmodified
// SMAA 1X passes. Selected pixels are the current raw edges plus camera-reprojected previous raw edges,
// marked in the first-pass stencil. The raw RG output keeps current edges only.

// Same edge equations as SMAA.hlsl, except that a pixel without a current edge returns
// zero instead of discarding, so the entry points below decide whether to keep it.
#define discard return (SMAA_EDGE_OUTPUT)0
#include "SMAAWrapper.hlsl"
#undef discard
#include "CatmullRomHistory5Tap.hlsli"

Texture2D previousRawEdges : register(t10);

bool PreviousRawEdgeFrom(float2 uv, float2 velocity) {
    float2 previousUV = uv - velocity;
    bool inBounds = all(previousUV >= 0.0) && all(previousUV < 1.0);
    int2 previousPixel = int2(floor(previousUV * SMAA_RT_METRICS.zw));
    bool previousEdge = any(previousRawEdges.Load(int3(previousPixel, 0)).rg > 0.0);
    return inBounds && previousEdge;
}

#define SELECTED_EDGE_PS(kind)                                                            \
SMAA_EDGE_OUTPUT Selected##kind##EdgePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0, \
                              float4 offset[3] : TEXCOORD1) : SV_TARGET {                 \
    float2 velocity = velocityTex.SampleLevel(PointSampler, texcoord, 0).rg;              \
    bool oldEdge = PreviousRawEdgeFrom(texcoord, velocity);                               \
    SMAA_EDGE_OUTPUT edge = DX10_SMAA##kind##EdgeDetectionPS(position, texcoord, offset); \
    if (!(any(edge.rg > 0.0) || oldEdge)) discard;                                        \
    return edge;                                                                          \
}

SELECTED_EDGE_PS(Luma)
SELECTED_EDGE_PS(LumaRaw)
SELECTED_EDGE_PS(Color)
SELECTED_EDGE_PS(Depth)

// Spatial SMAA result for this frame: to the current spatial copy (read by the resolve) and to the
// next history (overwritten by the resolve at the selected pixels).
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

// (c') Cross5: the weight of the official SMAA reprojection, 0.8 * saturate(1 - sqrt(| |v| - |v_prev| |) *
// SMAA_REPROJECTION_WEIGHT_SCALE), where v_prev is the previous-frame velocity that differs most in speed
// among the texel under the history position and its four neighbours (the previous output mixed its colour
// there from at most one of them). The previous velocity is the other of two velocity textures swapped
// every frame (clamped like the history).
Texture2D previousVelocityTex : register(t12);

[earlydepthstencil]
float4 SelectedResolveVelocityCross5PS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float2 v = velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    int2 n = int2(floor((uv - v) * SMAA_RT_METRICS.zw)), last = int2(SMAA_RT_METRICS.zw) - 1;
    const int2 offsets[5] = { int2(0, 0), int2(-1, 0), int2(1, 0), int2(0, -1), int2(0, 1) };
    float delta = 0.0;
    [unroll] for (int i = 0; i < 5; ++i)
        delta = max(delta, abs(length(v) - length(previousVelocityTex.Load(int3(clamp(n + offsets[i], int2(0, 0), last), 0)).rg)));
    float weight = 0.8 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
    float3 c = LinearToEncoded(current.rgb), h = LinearToEncoded(SelectedHistoryRGB(uv));
    return float4(EncodedToLinear(sqrt(lerp(c * c, h * h, weight))), current.a);
}

// First frame and resets: the history is the current spatial colour.
[earlydepthstencil]
float4 SelectedSeedResolvePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    return float4(lerp(current.rgb, SelectedHistoryRGB(uv), 0.8), current.a);
}

// ---------------------------------------------------------------------------------------------------------------
// Validation only (validation/improved-smaa-demo-translation-stability): resolve variants to separate the causes
// of instability under camera translation. The demo uses SelectedResolveVelocityCross5PS only.

// Fixed history weight 0.8 (no velocity test).
[earlydepthstencil]
float4 SelectedResolveFixed08PS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float3 c = LinearToEncoded(current.rgb), h = LinearToEncoded(SelectedHistoryRGB(uv));
    return float4(EncodedToLinear(sqrt(lerp(c * c, h * h, 0.8))), current.a);
}

// The official SMAA comparison: one previous-velocity tap, the texel under the history position.
[earlydepthstencil]
float4 SelectedResolveOfficial1TapPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float2 v = velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    int2 n = int2(floor((uv - v) * SMAA_RT_METRICS.zw)), last = int2(SMAA_RT_METRICS.zw) - 1;
    float delta = abs(length(v) - length(previousVelocityTex.Load(int3(clamp(n, int2(0, 0), last), 0)).rg));
    float weight = 0.8 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
    float3 c = LinearToEncoded(current.rgb), h = LinearToEncoded(SelectedHistoryRGB(uv));
    return float4(EncodedToLinear(sqrt(lerp(c * c, h * h, weight))), current.a);
}

// Weight debug: the Cross5 weight of SelectedResolveVelocityCross5PS, written instead of a colour.
// Output bytes (sRGB target, so the values pass through EncodedToLinear): R = weight / 0.8, G = 255 at every
// selected pixel, B = the largest relative view-depth jump to a 4-neighbour, x2, capped at 1 (0.1 jump = 51).
// The neighborhood pass writes zero in this mode, so G = 0 outside the selection. The weights depend on the
// velocity textures only, so they are the weights of the colour run at the same frame.
Texture2D<float> debugDepthTex : register(t13);

float DebugViewDepth(int2 pixel) {
    int2 last = int2(SMAA_RT_METRICS.zw) - 1;
    pixel = clamp(pixel, int2(0, 0), last);
    float2 uv = (float2(pixel) + 0.5) * SMAA_RT_METRICS.xy;
    float4 clip = float4(uv.x * 2.0 - 1.0, 1.0 - uv.y * 2.0, debugDepthTex.Load(int3(pixel, 0)), 1.0);
    float4 world = mul(g_SMAAReprojection.CurrentViewProjInv, clip);
    return abs(1.0 / world.w);
}

[earlydepthstencil]
float4 SelectedResolveWeightDebugPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float2 v = velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    int2 n = int2(floor((uv - v) * SMAA_RT_METRICS.zw)), last = int2(SMAA_RT_METRICS.zw) - 1;
    const int2 offsets[5] = { int2(0, 0), int2(-1, 0), int2(1, 0), int2(0, -1), int2(0, 1) };
    float delta = 0.0;
    [unroll] for (int i = 0; i < 5; ++i)
        delta = max(delta, abs(length(v) - length(previousVelocityTex.Load(int3(clamp(n + offsets[i], int2(0, 0), last), 0)).rg)));
    float weight = 0.8 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
    int2 pixel = int2(p.xy);
    float d = DebugViewDepth(pixel), jump = 0.0;
    [unroll] for (int j = 1; j < 5; ++j) {
        float dn = DebugViewDepth(pixel + offsets[j]);
        jump = max(jump, abs(dn - d) / max(min(dn, d), 1e-6));
    }
    return float4(EncodedToLinear(float3(weight / 0.8, 1.0, saturate(jump * 2.0))), 1.0);
}

// Weight debug: the neighborhood pass writes zero, so only the selected pixels carry G = 255.
void SelectedNeighborhoodZeroPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0, float4 offset : TEXCOORD1,
                                out float4 spatial : SV_TARGET0, out float4 history : SV_TARGET1) {
    spatial = float4(0.0, 0.0, 0.0, 1.0);
    history = spatial;
}
