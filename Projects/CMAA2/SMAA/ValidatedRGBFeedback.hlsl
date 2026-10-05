// SMAA adaptation of Playdead's rounded 3x3 neighborhood, AABB-center clipping,
// and normalized luminance feedback. Source provenance and differences:
// Docs/Edge-History-Adaptive-Validation/method.md; MIT notice below.
#include "FirstEdgeStencil.hlsl"

float3 ValidatedHistoryRGB(float2 uv, float3 history) {
    float3 lo9 = 1.0, hi9 = 0.0, lo5 = 1.0, hi5 = 0.0;
    [unroll] for(int y=-1; y<=1; ++y) {
        [unroll] for(int x=-1; x<=1; ++x) {
            float3 c = SMAASamplePoint(colorTex, uv + float2(x,y)*SMAA_RT_METRICS.xy).rgb;
            lo9=min(lo9,c);hi9=max(hi9,c);
            if(x==0 || y==0) {lo5=min(lo5,c);hi5=max(hi5,c);}
        }
    }
    float3 lo=0.5*(lo9+lo5), hi=0.5*(hi9+hi5);
    float3 center=0.5*(lo+hi), extent=0.5*(hi-lo)+1e-8;
    float3 displacement=history-center;
    float3 unit=abs(displacement/extent);
    float scale=max(1.0,max(unit.x,max(unit.y,unit.z)));
    return center+displacement/scale;
}

float4 ValidatedRGBResolve(float2 uv, int policy, out float weight) {
    float4 current=SMAASamplePoint(colorTex,uv);
    float2 historyUV=uv;
    float confidence=1.0;
#if SMAA_REPROJECTION
    historyUV-=SMAA_DECODE_VELOCITY(SMAASamplePoint(velocityTex,uv).rg);
    float alpha=SMAASamplePoint(colorTexPrev,historyUV).a;
    float delta=abs(current.a*current.a-alpha*alpha)/5.0;
    confidence=saturate(1.0-sqrt(delta)*SMAA_REPROJECTION_WEIGHT_SCALE);
#endif
    float3 history=SMAASampleLevelZero(colorTexPrev,historyUV).rgb;
    history=ValidatedHistoryRGB(uv,history);
    // Unity color-space luminance is replaced by explicit linear Rec.709.
    float currentLuma=dot(current.rgb,float3(0.2126,0.7152,0.0722));
    float historyLuma=dot(history,float3(0.2126,0.7152,0.0722));
    float difference=abs(currentLuma-historyLuma)/max(currentLuma,max(historyLuma,0.2));
    float agreement=1.0-difference;
    // Policy1: published defaults. Policy2: declared wider-response ablation.
    // Policy3: clipping only, preserving native alpha-derived weight.
    weight=confidence*(policy==3?0.5:lerp(policy==2?0.05:0.88,0.97,agreement*agreement));
    // Reject out-of-screen history instead of trusting clamp-addressed history.
    if(any(historyUV<0.0) || any(historyUV>1.0)) weight=0.0;
    return float4(lerp(current.rgb,history,weight),current.a);
}

#define VALIDATED_ENTRY(NAME,POLICY) \
[earlydepthstencil] void NAME(float4 p:SV_POSITION,float2 uv:TEXCOORD0, \
 out float4 visible:SV_TARGET0,out float4 history:SV_TARGET1) { \
 float weight;visible=ValidatedRGBResolve(uv,POLICY,weight);history=visible; }
#define VALIDATED_COVERAGE_ENTRY(NAME,POLICY) \
[earlydepthstencil] void NAME(float4 p:SV_POSITION,float2 uv:TEXCOORD0, \
 out float4 visible:SV_TARGET0,out float4 history:SV_TARGET1, \
 out float coverage:SV_TARGET2,out float weight:SV_TARGET3) { \
 visible=ValidatedRGBResolve(uv,POLICY,weight);history=visible;coverage=1.0; }

VALIDATED_ENTRY(ValidatedRGBFeedbackPS,1)
VALIDATED_COVERAGE_ENTRY(ValidatedRGBFeedbackCoveragePS,1)
VALIDATED_ENTRY(ResponsiveRGBFeedbackPS,2)
VALIDATED_COVERAGE_ENTRY(ResponsiveRGBFeedbackCoveragePS,2)
VALIDATED_ENTRY(ClippedRGBFeedbackPS,3)
VALIDATED_COVERAGE_ENTRY(ClippedRGBFeedbackCoveragePS,3)

/*
Copyright (c) <2015> <Playdead>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
*/
