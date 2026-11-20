// Shared definitions for every program of the pack.
#include "/lib/settings.glsl"

#if AA_MODE == 2 || AA_MODE == 4 || AA_MODE == 6
#define AA_ADAPTIVE
#endif
#if AA_MODE >= 3
#define AA_SELECTED
#endif
#if AA_MODE >= 5
#define AA_CROSS5
#endif

uniform float viewWidth;
uniform float viewHeight;

// SMAA configuration (Ultra preset; Adaptive adds the 1% contrast tiers of SMAA.glsl).
#define SMAA_RT_METRICS vec4(1.0 / viewWidth, 1.0 / viewHeight, viewWidth, viewHeight)
#define SMAA_GLSL_3
#define SMAA_PRESET_ULTRA
#ifdef AA_ADAPTIVE
#define SMAA_ADAPTIVE_SEARCH
#endif
#ifdef TIERS_AT_MAX
#define SMAA_ADAPTIVE_TIERS_AT_MAX
#endif

// Buffers (all written by full-screen composite passes, so no pixel keeps stale data):
//  colortex2 luma for edge detection (R8)            colortex3 camera velocity rg, history-usable b (RGBA16F, kept)
//  colortex4 previous frame's velocity (RG16F)        colortex5 edges rg, search tier b, selected a (RGBA8, kept)
//  colortex6 blending weights (RGBA8)                 colortex7 spatial SMAA result (RGBA8)
//  colortex8 output and next history, a = valid (RGBA8, kept)

// The demo reads and writes colour through sRGB views, so its blending, history filtering and the
// resolve's encoded values work on the sRGB transfer. Minecraft's colortex0 holds display (sRGB-encoded)
// values in RGBA8, so this pack decodes and encodes with the same piecewise curve.
vec3 SrgbToLinear(vec3 v) {
    return mix(pow((v + 0.055) / 1.055, vec3(2.4)), v / 12.92, lessThanEqual(v, vec3(0.04045)));
}
vec3 LinearToSrgb(vec3 v) {
    v = clamp(v, 0.0, 1.0);
    return mix(1.055 * pow(v, vec3(1.0 / 2.4)) - 0.055, 12.92 * v, lessThanEqual(v, vec3(0.0031308)));
}

// The demo's edge luma (vaShared.hlsl RGBToLumaForEdges): Rec. 601 weights on the square root of the
// tonemapped linear colour, stored in R8_UNORM.
float LumaForEdges(vec3 encoded) {
    return dot(sqrt(SrgbToLinear(encoded)), vec3(0.299, 0.587, 0.114));
}

// Bilinear filtering of an sRGB-encoded RGBA8 buffer in linear space with clamp-to-edge addressing,
// as a D3D11 linear sampler does on an sRGB view.
vec3 BilinearLinear(sampler2D tex, vec2 uv) {
    vec2 position = uv * SMAA_RT_METRICS.zw - 0.5;
    ivec2 i = ivec2(floor(position));
    vec2 f = position - vec2(i);
    ivec2 last = ivec2(SMAA_RT_METRICS.zw) - 1;
    vec3 c00 = SrgbToLinear(texelFetch(tex, clamp(i, ivec2(0), last), 0).rgb);
    vec3 c10 = SrgbToLinear(texelFetch(tex, clamp(i + ivec2(1, 0), ivec2(0), last), 0).rgb);
    vec3 c01 = SrgbToLinear(texelFetch(tex, clamp(i + ivec2(0, 1), ivec2(0), last), 0).rgb);
    vec3 c11 = SrgbToLinear(texelFetch(tex, clamp(i + ivec2(1, 1), ivec2(0), last), 0).rgb);
    return mix(mix(c00, c10, f.x), mix(c01, c11, f.x), f.y);
}
