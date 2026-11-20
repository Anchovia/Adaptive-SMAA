#version 330 compatibility
// Pass 1: SMAA luma edges (rg), the Adaptive search tier (b) and the selected-route flag (a).
// Selected pixels are the current raw edges plus camera-reprojected previous raw edges, as in
// SelectedTemporal.hlsl; the flag replaces the demo's stencil. rg keeps the current edges only.
#include "/lib/common.glsl"
#define SMAA_INCLUDE_VS 0
// Same edge equations as SMAA.glsl, except that a pixel without a current edge returns zero instead of
// discarding: every pixel of this full-screen pass must be written.
#define discard return SMAA_EDGE_OUTPUT(0.0)
#include "/lib/SMAA.glsl"
#undef discard

uniform sampler2D colortex2;
uniform sampler2D colortex3;
uniform sampler2D colortex5;

in vec2 texcoord;
in vec4 offset[3];

/* RENDERTARGETS: 5 */
layout(location = 0) out vec4 outEdges;

void main() {
    outEdges = vec4(0.0);
#if AA_MODE > 0
    SMAA_EDGE_OUTPUT edge = SMAALumaRawEdgeDetectionPS(texcoord, offset, colortex2);
    outEdges.rg = edge.rg;
#ifdef AA_ADAPTIVE
    outEdges.b = edge.b;
#endif
#ifdef AA_SELECTED
    vec3 velocity = texelFetch(colortex3, ivec2(gl_FragCoord.xy), 0).rgb;
    vec2 previousUV = texcoord - velocity.rg;
    bool previousEdge = false;
    if (all(greaterThanEqual(previousUV, vec2(0.0))) && all(lessThan(previousUV, vec2(1.0)))) {
        // colortex5 still holds last frame's raw edges here.
        vec2 previous = texelFetch(colortex5, ivec2(floor(previousUV * SMAA_RT_METRICS.zw)), 0).rg;
        previousEdge = any(greaterThan(previous, vec2(0.0)));
    }
    bool currentEdge = any(greaterThan(edge.rg, vec2(0.0)));
    outEdges.a = (velocity.b > 0.5 && (currentEdge || previousEdge)) ? 1.0 : 0.0;
#endif
#endif
}
