// Edge-selective temporal route on top of unmodified SMAA (camera/depth reprojection only).
// Selected pixels are the current raw edges plus camera-reprojected previous raw edges,
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

// Case 19: this draw computes the camera velocity instead of a separate full-screen pass.
// Only retained pixels store it, and the resolve reads no others. The lookup uses the
// float16 value that a separate velocity texture would have returned.
#define SELECTED_VELOCITY_EDGE_PS(kind)                                                           \
void Selected##kind##VelocityEdgePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0,   \
                                    float4 offset[3] : TEXCOORD1,                                 \
                                    out SMAA_EDGE_OUTPUT edge : SV_TARGET0, out float2 velocity : SV_TARGET1) { \
    velocity = DX10_SMAAGenerateCameraVelocityPS(position, texcoord);                             \
    bool oldEdge = PreviousRawEdgeFrom(texcoord, f16tof32(f32tof16(velocity)));                   \
    edge = DX10_SMAA##kind##EdgeDetectionPS(position, texcoord, offset);                          \
    if (!(any(edge.rg > 0.0) || oldEdge)) discard;                                                \
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

// History rejection experiment: each filter below is a separate entry point that changes only
// how much of the history the selected pixel keeps. Selection, Catmull-Rom sampling, the 0.8
// weight, feedback and the absent jitter stay as in SelectedResolvePS.

float4 SelectedBlend(float4 current, float3 historyLinear, float weight) {
    float3 c = LinearToEncoded(current.rgb), h = LinearToEncoded(historyLinear);
    return float4(EncodedToLinear(sqrt(lerp(c * c, h * h, weight))), current.a);
}

// (a) Clamp the history to the per-channel min/max of the current spatial 3x3 neighbourhood.
// The clamp runs on linear values; the transfer is monotonic per channel, so this equals the
// same clamp on encoded values.
[earlydepthstencil]
float4 SelectedResolveClampPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    int2 pixel = int2(p.xy), last = int2(SMAA_RT_METRICS.zw) - 1;
    float3 lo = current.rgb, hi = current.rgb;
    [unroll] for (int y = -1; y <= 1; ++y)
        [unroll] for (int x = -1; x <= 1; ++x) {
            float3 n = colorTex.Load(int3(clamp(pixel + int2(x, y), int2(0, 0), last), 0)).rgb;
            lo = min(lo, n); hi = max(hi, n);
        }
    return SelectedBlend(current, clamp(SelectedHistoryRGB(uv), lo, hi), 0.8);
}

// (b) Previous-depth disocclusion test after 322ad90: the current pixel is moved into the
// previous camera, and its expected previous depth is compared with the previous frame's depth
// at the history position (centre point sample, clamped address like the colour history).
// A mismatch keeps the current spatial colour (history weight 0).
Texture2D<float> previousDepthTex : register(t11);
// Tolerances of the 322ad90 gate: absolute in view-depth units plus a share of the expected depth.
#define SELECTED_DEPTH_ABSOLUTE_TOLERANCE 0.01
#define SELECTED_DEPTH_RELATIVE_TOLERANCE 0.005

bool SelectedPreviousDepthMatches(float2 uv, int2 pixel, float2 historyUV) {
    float depth = depthTex.Load(int3(pixel, 0)).r;
    float4 world = mul(g_SMAAReprojection.CurrentViewProjInv, float4(uv.x * 2.0 - 1.0, 1.0 - uv.y * 2.0, depth, 1.0));
    world /= world.w;
    float4 previousClip = mul(g_SMAAReprojection.PreviousViewProj, world);
    if (!(previousClip.w > 1.0e-6))
        return false;
    float expected = previousClip.z / previousClip.w;
    float actual = previousDepthTex.SampleLevel(PointSampler, historyUV, 0.0);
    if (!(expected >= 0.0 && expected <= 1.0 && actual >= 0.0 && actual <= 1.0))
        return false;
    float unpackMul = g_SMAAReprojection.PreviousDepthUnpack.x, unpackAdd = g_SMAAReprojection.PreviousDepthUnpack.y;
    float expectedDenominator = unpackAdd - expected, actualDenominator = unpackAdd - actual;
    if (abs(expectedDenominator) <= 1.0e-8 || abs(actualDenominator) <= 1.0e-8)
        return false;
    float expectedView = unpackMul / expectedDenominator, actualView = unpackMul / actualDenominator;
    if (!(expectedView > 0.0 && actualView > 0.0 && expectedView < 3.4e38 && actualView < 3.4e38))
        return false;
    float tolerance = SELECTED_DEPTH_ABSOLUTE_TOLERANCE + SELECTED_DEPTH_RELATIVE_TOLERANCE * expectedView;
    return abs(actualView - expectedView) <= tolerance;
}

[earlydepthstencil]
float4 SelectedResolveDepthPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float2 historyUV = uv - velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    [branch] if (!SelectedPreviousDepthMatches(uv, int2(p.xy), historyUV))
        return current;
    return SelectedBlend(current, SelectedHistoryRGB(uv), 0.8);
}

// (c) Velocity weighting as in the official SMAA resolve (O-T2X-R), scaled to the 0.8 weight.
// SelectedNeighborhoodVelocityAlphaPS (compiled with SMAA_REPROJECTION) packs
// sqrt(5 * |velocity|) into the spatial and history alpha, and the resolve keeps current.a, so
// the history alpha at historyUV holds the previous frame's velocity magnitude.
void SelectedNeighborhoodVelocityAlphaPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0, float4 offset : TEXCOORD1,
                                         out float4 spatial : SV_TARGET0, out float4 history : SV_TARGET1) {
    spatial = DX10_SMAANeighborhoodBlendingPS(p, uv, offset);
    history = spatial;
}

[earlydepthstencil]
float4 SelectedResolveVelocityPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float2 historyUV = uv - velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    float previousA = SMAASamplePoint(colorTexPrev, historyUV).a;
    float delta = abs(current.a * current.a - previousA * previousA) / 5.0;
    float weight = 0.8 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
    return SelectedBlend(current, SelectedHistoryRGB(uv), weight);
}

// (c') The weight of (c) from a velocity ping-pong instead of the packed alpha: the resolve reads
// the current velocity at uv and the previous frame's velocity at historyUV = uv - velocity, both
// float16 and per pixel (the alpha of (c) holds sqrt(5|v|) in 8 bits, antialiased by the
// neighborhood pass). The neighborhood pass stays SelectedNeighborhoodPS.
// Case 19 writes the velocity on retained pixels only. Its target is cleared to
// SELECTED_VELOCITY_UNKNOWN before the edge pass, so a history position that was not retained in
// the previous frame reads the sentinel. The default rule treats it as zero velocity (full weight at
// rest, close to no history while the camera moves). The Keep variant uses the current velocity
// instead, which keeps the 0.8 weight of the route without the filter.
Texture2D previousVelocityTex : register(t12);
#define SELECTED_VELOCITY_UNKNOWN 1024.0

#define SELECTED_RESOLVE_VELOCITY_PINGPONG(name, unknown)                                            \
[earlydepthstencil]                                                                                 \
float4 name(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {                            \
    float4 current = SMAASamplePoint(colorTex, uv);                                                 \
    float2 v = velocityTex.SampleLevel(PointSampler, uv, 0).rg;                                      \
    float2 vp = previousVelocityTex.SampleLevel(PointSampler, uv - v, 0).rg;                         \
    if (any(abs(vp) > 0.5 * SELECTED_VELOCITY_UNKNOWN)) vp = unknown;                                \
    float weight = 0.8 * saturate(1.0 - sqrt(abs(length(v) - length(vp))) * SMAA_REPROJECTION_WEIGHT_SCALE); \
    return SelectedBlend(current, SelectedHistoryRGB(uv), weight);                                  \
}
SELECTED_RESOLVE_VELOCITY_PINGPONG(SelectedResolveVelocityPingPongPS, float2(0.0, 0.0))
SELECTED_RESOLVE_VELOCITY_PINGPONG(SelectedResolveVelocityPingPongKeepPS, v)

// (c') footprint variants: the speed difference of (c') is taken as the largest one over a set of
// previous-velocity texels around historyUV instead of the single texel under it. The weight formula,
// the unknown rule (zero) and the history sample stay those of (c'). Texels are loaded with the
// coordinates clamped to the target, as the clamp samplers of the history and of (c') do.
//   Cross5: the texel (c') reads, n = floor(historyUV * size), and its four neighbours. The colour
//     of the previous output at n comes from n and, through the neighbourhood blending of SMAA,
//     from at most one of these neighbours.
//   Footprint12: the twelve texels SampleHistoryCatmullRom5Tap reads, with i = floor(position - 0.5):
//     rows j and j+1 over columns i-1..i+2, and columns i and i+1 over rows j-1 and j+2. It holds
//     the Cross5 set of n (n is i or i+1 on each axis).
// Every set holds the texel of (c'), so the weight never exceeds the (c') weight.
float SelectedPreviousSpeedDelta(int2 texel, int2 maxTexel, float speed) {
    float2 vp = previousVelocityTex.Load(int3(clamp(texel, int2(0, 0), maxTexel), 0)).rg;
    if (any(abs(vp) > 0.5 * SELECTED_VELOCITY_UNKNOWN)) vp = float2(0.0, 0.0);
    return abs(speed - length(vp));
}

[earlydepthstencil]
float4 SelectedResolveVelocityCross5PS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float2 v = velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    float speed = length(v);
    int2 maxTexel = int2(SMAA_RT_METRICS.zw) - 1;
    int2 n = int2(floor((uv - v) * SMAA_RT_METRICS.zw));
    float delta = SelectedPreviousSpeedDelta(n, maxTexel, speed);
    delta = max(delta, SelectedPreviousSpeedDelta(n + int2(-1, 0), maxTexel, speed));
    delta = max(delta, SelectedPreviousSpeedDelta(n + int2(1, 0), maxTexel, speed));
    delta = max(delta, SelectedPreviousSpeedDelta(n + int2(0, -1), maxTexel, speed));
    delta = max(delta, SelectedPreviousSpeedDelta(n + int2(0, 1), maxTexel, speed));
    float weight = 0.8 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
    return SelectedBlend(current, SelectedHistoryRGB(uv), weight);
}

[earlydepthstencil]
float4 SelectedResolveVelocityFootprint12PS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    float2 v = velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    float speed = length(v);
    int2 maxTexel = int2(SMAA_RT_METRICS.zw) - 1;
    int2 b = int2(floor((uv - v) * SMAA_RT_METRICS.zw - 0.5));
    float delta = 0.0;
    [unroll] for (int x = -1; x <= 2; ++x) {
        delta = max(delta, SelectedPreviousSpeedDelta(b + int2(x, 0), maxTexel, speed));
        delta = max(delta, SelectedPreviousSpeedDelta(b + int2(x, 1), maxTexel, speed));
    }
    [unroll] for (int column = 0; column <= 1; ++column) {
        delta = max(delta, SelectedPreviousSpeedDelta(b + int2(column, -1), maxTexel, speed));
        delta = max(delta, SelectedPreviousSpeedDelta(b + int2(column, 2), maxTexel, speed));
    }
    float weight = 0.8 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
    return SelectedBlend(current, SelectedHistoryRGB(uv), weight);
}

// First frame and resets: the history is the current spatial colour.
[earlydepthstencil]
float4 SelectedSeedResolvePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, uv);
    return float4(lerp(current.rgb, SelectedHistoryRGB(uv), 0.8), current.a);
}
