#version 330 compatibility
// Final: the anti-aliased image (colortex8), the untouched scene when AA is off, or a debug view.
#include "/lib/common.glsl"

uniform sampler2D colortex0;
uniform sampler2D colortex3;
uniform sampler2D colortex5;
uniform sampler2D colortex8;

in vec2 texcoord;

layout(location = 0) out vec4 outColor;

void main() {
    ivec2 pixel = ivec2(gl_FragCoord.xy);
#if AA_MODE == 0
    vec3 color = texelFetch(colortex0, pixel, 0).rgb;
#else
    vec3 color = texelFetch(colortex8, pixel, 0).rgb;
#endif
#if DEBUG_VIEW > 0
    vec4 edges = texelFetch(colortex5, pixel, 0);
    bool edge = edges.r > 0.0 || edges.g > 0.0;
    vec3 velocity = texelFetch(colortex3, pixel, 0).rgb;
#endif
#if DEBUG_VIEW == 1
    // Red: vertical edge (with the pixel to the left), green: horizontal edge. SMAA's "top" neighbour is
    // texcoord.y - 1 pixel, which is the pixel below on screen in OpenGL.
    color = edge ? vec3(edges.rg, 0.0) : color * 0.25;
#elif DEBUG_VIEW == 2
    // Blue: shortest search, green: middle, red: top tier; white when the mode has no tiers.
#ifdef AA_ADAPTIVE
    vec3 tier = edges.b < 0.25 ? vec3(0.2, 0.4, 1.0) : (edges.b < 0.75 ? vec3(0.2, 1.0, 0.2) : vec3(1.0, 0.3, 0.2));
#else
    vec3 tier = vec3(1.0);
#endif
    color = edge ? tier : color * 0.25;
#elif DEBUG_VIEW == 3
    // Magenta: pixels that take history; cyan tint: pixels without usable history (hand, first frame).
    color = edges.a > 0.5 ? vec3(1.0, 0.0, 1.0) : (velocity.b < 0.5 ? color * 0.35 + vec3(0.0, 0.25, 0.25) : color * 0.35);
#elif DEBUG_VIEW == 4
    // Camera velocity in pixels per frame (16 px = full red/green); blue where there is no usable history.
    color = vec3(abs(velocity.rg) * SMAA_RT_METRICS.zw / 16.0, velocity.b < 0.5 ? 0.5 : 0.0);
#endif
    outColor = vec4(color, 1.0);
}
