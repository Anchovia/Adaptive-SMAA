#version 330 compatibility
// Pass 0: edge luma (the demo's exported luma), camera/depth velocity and a copy of last frame's velocity.
#include "/lib/common.glsl"

/*
const int colortex2Format = R8;
const int colortex3Format = RGBA16F;
const int colortex4Format = RG16F;
const int colortex5Format = RGBA8;
const int colortex6Format = RGBA8;
const int colortex7Format = RGBA8;
const int colortex8Format = RGBA8;
*/
const bool colortex3Clear = false;
const bool colortex5Clear = false;
const bool colortex8Clear = false;

uniform sampler2D colortex0;
uniform sampler2D colortex3;
uniform sampler2D depthtex0;
uniform sampler2D depthtex1;
uniform sampler2D depthtex2;
uniform mat4 gbufferProjectionInverse;
uniform mat4 gbufferModelViewInverse;
uniform mat4 gbufferPreviousModelView;
uniform mat4 gbufferPreviousProjection;
uniform ivec3 cameraPositionInt;
uniform ivec3 previousCameraPositionInt;
uniform vec3 cameraPositionFract;
uniform vec3 previousCameraPositionFract;

in vec2 texcoord;

/* RENDERTARGETS: 2,3,4 */
layout(location = 0) out vec4 outLuma;
layout(location = 1) out vec4 outVelocity;
layout(location = 2) out vec4 outPreviousVelocity;

void main() {
    ivec2 pixel = ivec2(gl_FragCoord.xy);
    outLuma = vec4(LumaForEdges(texelFetch(colortex0, pixel, 0).rgb), 0.0, 0.0, 1.0);
    // colortex3 still holds last frame's velocity here; this pass replaces it below.
    outPreviousVelocity = vec4(texelFetch(colortex3, pixel, 0).rg, 0.0, 1.0);
    outVelocity = vec4(0.0);
#ifdef AA_SELECTED
    // Camera/depth reprojection only (no object motion). depthtex0 includes translucent surfaces;
    // the hand is in depthtex1 but not in depthtex2 and never takes history.
    float depth = texelFetch(depthtex0, pixel, 0).r;
    bool hand = texelFetch(depthtex1, pixel, 0).r < texelFetch(depthtex2, pixel, 0).r;
    vec3 cameraDelta = vec3(cameraPositionInt - previousCameraPositionInt) + (cameraPositionFract - previousCameraPositionFract);
    vec4 view = gbufferProjectionInverse * vec4(vec3(texcoord, depth) * 2.0 - 1.0, 1.0);
    vec3 player = (gbufferModelViewInverse * vec4(view.xyz / view.w, 1.0)).xyz;
    vec4 previousClip = gbufferPreviousProjection * (gbufferPreviousModelView * vec4(player + cameraDelta, 1.0));
    // No previous matrices on the first frame (w = 0). A jump of 16 blocks or more (teleport, respawn,
    // dimension change) starts without history, as the demo does after a camera cut.
    bool usable = !hand && previousClip.w > 0.0 && dot(cameraDelta, cameraDelta) < 256.0;
    // Same convention as the demo: velocity = current UV - previous UV, history UV = UV - velocity.
    vec2 velocity = usable ? texcoord - (previousClip.xy / previousClip.w * 0.5 + 0.5) : vec2(0.0);
    outVelocity = vec4(velocity, usable ? 1.0 : 0.0, 1.0);
#endif
}
