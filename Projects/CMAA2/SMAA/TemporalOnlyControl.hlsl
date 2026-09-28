// Diagnostic control, not a replacement for the original SMAA spatial shaders.
#include "SMAAWrapper.hlsl"

float4 TemporalOnlyPreparePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0) : SV_TARGET {
    // Same operations as the native neighborhood shader's zero-weight branch.
    // Preserve scene RGB; pack velocity magnitude needed by the unchanged resolve.
    float4 color = SMAASampleLevelZero(colorTex, texcoord);
    #if SMAA_REPROJECTION
    float2 velocity = SMAA_DECODE_VELOCITY(SMAASampleLevelZero(velocityTex, texcoord));
    color.a = sqrt(5.0 * length(velocity));
    #endif
    return color;
}
