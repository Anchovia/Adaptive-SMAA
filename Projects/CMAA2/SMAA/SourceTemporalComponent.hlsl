// Case14: replace only case13's adaptive weight with the Intel document's 0.8.
// Keep selection, history RGB reconstruction, spatial alpha and feedback topology.
#include "FirstEdgeStencil.hlsl"
#include "CatmullRomHistory5Tap.hlsli"
#include "SourceTemporalMath.hlsli"

float4 SourceComponentResolve(float2 uv, out float historyWeight) {
    float4 current = SMAASamplePoint(colorTex, uv);
#if SMAA_REPROJECTION
    float2 velocity = -SMAA_DECODE_VELOCITY(SMAASamplePoint(velocityTex, uv).rg);
    float2 historyUV = uv + velocity;
#else
    float2 historyUV = uv;
#endif
    float4 previous = SMAASamplePoint(colorTexPrev, historyUV);
    previous.rgb = SampleHistoryCatmullRom5Tap(colorTexPrev, LinearSampler,
                                              historyUV, SMAA_RT_METRICS.zw);
    previous.rgb=SourceClipHistory(colorTex,LinearSampler,uv,SMAA_RT_METRICS.zw,current.rgb,previous.rgb);
    historyWeight = 0.8;
    return lerp(current, previous, historyWeight);
}

[earlydepthstencil]
void SourceComponentPS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                              out float4 visible : SV_TARGET0,
                              out float4 history : SV_TARGET1) {
    float weight;
    visible = SourceComponentResolve(uv, weight);
    history = float4(visible.rgb, SMAASamplePoint(colorTex, uv).a);
}

[earlydepthstencil]
void SourceComponentCoveragePS(float4 p : SV_POSITION, float2 uv : TEXCOORD0,
                                      out float4 visible : SV_TARGET0,
                                      out float4 history : SV_TARGET1,
                                      out float coverage : SV_TARGET2,
                                      out float weight : SV_TARGET3) {
    visible = SourceComponentResolve(uv, weight);
    history = float4(visible.rgb, SMAASamplePoint(colorTex, uv).a);
    coverage = 1.0;
}
