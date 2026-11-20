#version 330 compatibility
// Pass 2: SMAA blending weights. Pixels without a current edge return zero inside SMAA, so the branch
// replaces the demo's stencil test.
#include "/lib/common.glsl"
#define SMAA_INCLUDE_VS 0
#include "/lib/SMAA.glsl"

uniform sampler2D colortex5;
uniform sampler2D smaaAreaTex;
uniform sampler2D smaaSearchTex;

in vec2 texcoord;
in vec2 pixcoord;
in vec4 offset[3];

/* RENDERTARGETS: 6 */
layout(location = 0) out vec4 outWeights;

void main() {
    outWeights = vec4(0.0);
#if AA_MODE > 0
    outWeights = SMAABlendingWeightCalculationPS(texcoord, pixcoord, offset, colortex5, smaaAreaTex, smaaSearchTex, vec4(0.0));
#endif
}
