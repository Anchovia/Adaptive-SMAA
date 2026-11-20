#version 330 compatibility
// Pass 4: selected-route resolve (SelectedResolvePS / SelectedResolveVelocityCross5PS /
// SelectedSeedResolvePS). Selected pixels mix the spatial result with the Catmull-Rom history at
// UV - velocity; the result is both this frame's output and the next frame's history.
#include "/lib/common.glsl"
#include "/lib/history.glsl"

// SMAA.glsl default, used by the official SMAA reprojection weight.
#define SMAA_REPROJECTION_WEIGHT_SCALE 30.0

uniform sampler2D colortex3;
uniform sampler2D colortex4;
uniform sampler2D colortex5;
uniform sampler2D colortex7;
uniform sampler2D colortex8;

in vec2 texcoord;

/* RENDERTARGETS: 8 */
layout(location = 0) out vec4 outHistory;

void main() {
    ivec2 pixel = ivec2(gl_FragCoord.xy);
    vec3 spatial = texelFetch(colortex7, pixel, 0).rgb;
    outHistory = vec4(spatial, 1.0);
#ifdef AA_SELECTED
    if (texelFetch(colortex5, pixel, 0).a > 0.5) {
        vec2 velocity = texelFetch(colortex3, pixel, 0).rg;
        vec2 historyUV = texcoord - velocity;
        // colortex8 still holds last frame's output here. Alpha 0 means no history yet (first frame or
        // recreated buffers): the demo's seed frame, whose history is this frame's spatial result.
        if (texelFetch(colortex8, pixel, 0).a < 0.5) {
            vec3 seedHistory = SampleHistoryCatmullRom5Tap(colortex7, historyUV, SMAA_RT_METRICS.zw);
            outHistory.rgb = LinearToSrgb(mix(SrgbToLinear(spatial), seedHistory, 0.8));
        } else {
            float weight = 0.8;
#ifdef AA_CROSS5
            // (c') Cross5: the largest speed difference against last frame's velocity at the texel under
            // the history position and its four neighbours.
            ivec2 n = ivec2(floor(historyUV * SMAA_RT_METRICS.zw));
            ivec2 last = ivec2(SMAA_RT_METRICS.zw) - 1;
            float speed = length(velocity);
            float delta = abs(speed - length(texelFetch(colortex4, clamp(n, ivec2(0), last), 0).rg));
            delta = max(delta, abs(speed - length(texelFetch(colortex4, clamp(n + ivec2(-1, 0), ivec2(0), last), 0).rg)));
            delta = max(delta, abs(speed - length(texelFetch(colortex4, clamp(n + ivec2(1, 0), ivec2(0), last), 0).rg)));
            delta = max(delta, abs(speed - length(texelFetch(colortex4, clamp(n + ivec2(0, -1), ivec2(0), last), 0).rg)));
            delta = max(delta, abs(speed - length(texelFetch(colortex4, clamp(n + ivec2(0, 1), ivec2(0), last), 0).rg)));
            weight = 0.8 * clamp(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE, 0.0, 1.0);
#endif
            // The blend squares sRGB-encoded values, as the demo's resolve does.
            vec3 history = LinearToSrgb(SampleHistoryCatmullRom5Tap(colortex8, historyUV, SMAA_RT_METRICS.zw));
            outHistory.rgb = sqrt(mix(spatial * spatial, history * history, weight));
        }
    }
#endif
}
