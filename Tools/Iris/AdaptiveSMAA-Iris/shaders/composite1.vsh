#version 330 compatibility
// Pass 1: SMAA edge detection.
#include "/lib/common.glsl"
#define SMAA_INCLUDE_PS 0
#include "/lib/SMAA.glsl"

out vec2 texcoord;
out vec4 offset[3];

void main() {
    gl_Position = ftransform();
    texcoord = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    SMAAEdgeDetectionVS(texcoord, offset);
}
