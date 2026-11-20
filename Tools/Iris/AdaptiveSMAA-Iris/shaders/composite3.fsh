#version 330 compatibility
// Pass 3: SMAA neighborhood blending (SMAANeighborhoodBlendingPS without reprojection). The two colour
// fetches are filtered and blended in linear space like the demo's sRGB view; output is sRGB-encoded.
#include "/lib/common.glsl"

uniform sampler2D colortex0;
uniform sampler2D colortex6;

in vec2 texcoord;
in vec4 offset;

/* RENDERTARGETS: 7 */
layout(location = 0) out vec4 outSpatial;

void main() {
    ivec2 pixel = ivec2(gl_FragCoord.xy);
    vec3 color = texelFetch(colortex0, pixel, 0).rgb;
#if AA_MODE > 0
    vec4 a;
    a.x = texture(colortex6, offset.xy).a; // Right
    a.y = texture(colortex6, offset.zw).g; // Top
    a.wz = texture(colortex6, texcoord).xz; // Bottom / Left
    if (dot(a, vec4(1.0)) >= 1e-5) {
        bool h = max(a.x, a.z) > max(a.y, a.w); // max(horizontal) > max(vertical)
        vec4 blendingOffset = h ? vec4(a.x, 0.0, a.z, 0.0) : vec4(0.0, a.y, 0.0, a.w);
        vec2 blendingWeight = h ? a.xz : a.yw;
        blendingWeight /= dot(blendingWeight, vec2(1.0));
        vec4 blendingCoord = blendingOffset * vec4(SMAA_RT_METRICS.xy, -SMAA_RT_METRICS.xy) + texcoord.xyxy;
        vec3 linearColor = blendingWeight.x * BilinearLinear(colortex0, blendingCoord.xy);
        linearColor += blendingWeight.y * BilinearLinear(colortex0, blendingCoord.zw);
        color = LinearToSrgb(linearColor);
    }
#endif
    outSpatial = vec4(color, 1.0);
}
