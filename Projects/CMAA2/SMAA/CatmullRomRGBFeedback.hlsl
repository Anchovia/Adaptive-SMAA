// Case 13 changes only the history RGB reconstruction filter from case 11.
#include "FirstEdgeStencil.hlsl"
#include "CatmullRomHistory5Tap.hlsli"

float4 CatmullRomHistoryRGBResolve(float2 uv, out float historyWeight) {
    float4 current = SMAASamplePoint(colorTex, uv);
#if SMAA_REPROJECTION
    float2 velocity = -SMAA_DECODE_VELOCITY(SMAASamplePoint(velocityTex, uv).rg);
    float2 historyUV = uv + velocity;
    float4 previous = SMAASamplePoint(colorTexPrev, historyUV);
    float delta = abs(current.a * current.a - previous.a * previous.a) / 5.0;
    historyWeight = 0.5 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
#else
    float2 historyUV = uv;
    float4 previous = SMAASamplePoint(colorTexPrev, historyUV);
    historyWeight = 0.5;
#endif
    previous.rgb = SampleHistoryCatmullRom5Tap(colorTexPrev, LinearSampler,
                                              historyUV, SMAA_RT_METRICS.zw);
    return lerp(current, previous, historyWeight);
}

[earlydepthstencil]
void CatmullRomRGBFeedbackPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                             out float4 visible : SV_TARGET0,
                             out float4 history : SV_TARGET1) {
    float weight;
    visible = CatmullRomHistoryRGBResolve(uv, weight);
    history = float4(visible.rgb, SMAASamplePoint(colorTex, uv).a);
}

[earlydepthstencil]
void CatmullRomRGBFeedbackCoveragePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                                     out float4 visible : SV_TARGET0,
                                     out float4 history : SV_TARGET1,
                                     out float coverage : SV_TARGET2,
                                     out float weight : SV_TARGET3) {
    visible = CatmullRomHistoryRGBResolve(uv, weight);
    history = float4(visible.rgb, SMAASamplePoint(colorTex, uv).a);
    coverage = 1.0;
}
