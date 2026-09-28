// Configuration 6: reuse native first-pass RG after all three spatial SMAA passes.
#include "SMAAWrapper.hlsl"

float4 SpatialFirstEdgePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0) : SV_TARGET {
    float4 current = SMAASamplePoint(colorTex, texcoord);
    float2 edge = edgesTex.Load(int3(int2(position.xy), 0)).rg;
    [branch] if (!any(edge > 0.0)) return current;

    // Native SMAAResolvePS math, reusing the current sample above.
    #if SMAA_REPROJECTION
    float2 velocity = -SMAA_DECODE_VELOCITY(SMAASamplePoint(velocityTex, texcoord).rg);
    float4 previous = SMAASamplePoint(colorTexPrev, texcoord + velocity);
    float delta = abs(current.a * current.a - previous.a * previous.a) / 5.0;
    float weight = 0.5 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
    return lerp(current, previous, weight);
    #else
    float4 previous = SMAASamplePoint(colorTexPrev, texcoord);
    return lerp(current, previous, 0.5);
    #endif
}
