/**
 * Copyright (C) 2013 Jorge Jimenez (jorge@iryoku.com)
 * Copyright (C) 2013 Jose I. Echevarria (joseignacioechevarria@gmail.com)
 * Copyright (C) 2013 Belen Masia (bmasia@unizar.es)
 * Copyright (C) 2013 Fernando Navarro (fernandn@microsoft.com)
 * Copyright (C) 2013 Diego Gutierrez (diegog@unizar.es)
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is furnished to
 * do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software. As clarification, there
 * is no requirement that the copyright notice and permission be included in
 * binary distributions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

// Cost audit alternative: reuse first-pass stencil for the current/previous union.
// Native edge equations copied from SMAA.hlsl. The sole equation-body change is
// discard -> return zero, allowing the wrapper to retain a previous-only pixel.
// Raw RG stays zero there; the union is NEVER fed back as a raw edge.
#include "SMAAWrapper.hlsl"
Texture2D previousRawEdges : register(t10);

float2 PersistenceSMAALumaRawEdgeDetectionPS(float2 texcoord,
                               float4 offset[3],
                               SMAATexture2D(colorTex)
                               #if SMAA_PREDICATION
                               , SMAATexture2D(predicationTex)
                               #endif
                               ) {
    // Calculate the threshold:
    #if SMAA_PREDICATION
    float2 threshold = SMAACalculatePredicatedThreshold(texcoord, offset, SMAATexturePass2D(predicationTex));
    #else
    float2 threshold = float2(SMAA_THRESHOLD, SMAA_THRESHOLD);
    #endif

    // // Calculate lumas:
    // float3 weights = float3(0.2126, 0.7152, 0.0722);
    // //float3 weights = float3(0.299, 0.587, 0.114);
    // float L = dot(SMAASamplePoint(colorTex, texcoord).rgb, weights);
    //
    // float Lleft = dot(SMAASamplePoint(colorTex, offset[0].xy).rgb, weights);
    // float Ltop  = dot(SMAASamplePoint(colorTex, offset[0].zw).rgb, weights);

    // Gather lumas:
    //SMAAGather
    float L     = SMAASamplePoint(colorTex, texcoord).r;
    float Lleft = SMAASamplePoint(colorTex, offset[0].xy).r;
    float Ltop  = SMAASamplePoint(colorTex, offset[0].zw).r;

    // We do the usual threshold:
    float4 delta;
    delta.xy = abs(L - float2(Lleft, Ltop));
    float2 edges = step(threshold, delta.xy);

    // Then discard if there is no edge:
    if (dot(edges, float2(1.0, 1.0)) == 0.0)
        return float2(0.0, 0.0);

    // Calculate right and bottom deltas:
    float Lright    = SMAASamplePoint(colorTex, offset[1].xy).r;
    float Lbottom   = SMAASamplePoint(colorTex, offset[1].zw).r;
    delta.zw = abs(L - float2(Lright, Lbottom));

    // Calculate the maximum delta in the direct neighborhood:
    float2 maxDelta = max(delta.xy, delta.zw);

    // Calculate left-left and top-top deltas:
    float Lleftleft = SMAASamplePoint(colorTex, offset[2].xy).r;
    float Ltoptop   = SMAASamplePoint(colorTex, offset[2].zw).r;
    delta.zw = abs(float2(Lleft, Ltop) - float2(Lleftleft, Ltoptop));

    // Calculate the final maximum delta:
    maxDelta = max(maxDelta.xy, delta.zw);
    float finalDelta = max(maxDelta.x, maxDelta.y);

    // Local contrast adaptation:
    edges.xy *= step(finalDelta, SMAA_LOCAL_CONTRAST_ADAPTATION_FACTOR * delta.xy);

    return edges;
}

float2 PersistenceSMAALumaEdgeDetectionPS(float2 texcoord,
                               float4 offset[3],
                               SMAATexture2D(colorTex)
                               #if SMAA_PREDICATION
                               , SMAATexture2D(predicationTex)
                               #endif
                               ) {
    // Calculate the threshold:
    #if SMAA_PREDICATION
    float2 threshold = SMAACalculatePredicatedThreshold(texcoord, offset, SMAATexturePass2D(predicationTex));
    #else
    float2 threshold = float2(SMAA_THRESHOLD, SMAA_THRESHOLD);
    #endif

    // Calculate lumas:
    float3 weights = float3(0.2126, 0.7152, 0.0722);
    float L = dot(SMAASamplePoint(colorTex, texcoord).rgb, weights);

    float Lleft = dot(SMAASamplePoint(colorTex, offset[0].xy).rgb, weights);
    float Ltop  = dot(SMAASamplePoint(colorTex, offset[0].zw).rgb, weights);

    // We do the usual threshold:
    float4 delta;
    delta.xy = abs(L - float2(Lleft, Ltop));
    float2 edges = step(threshold, delta.xy);

    // Then discard if there is no edge:
    if (dot(edges, float2(1.0, 1.0)) == 0.0)
        return float2(0.0, 0.0);

    // Calculate right and bottom deltas:
    float Lright = dot(SMAASamplePoint(colorTex, offset[1].xy).rgb, weights);
    float Lbottom  = dot(SMAASamplePoint(colorTex, offset[1].zw).rgb, weights);
    delta.zw = abs(L - float2(Lright, Lbottom));

    // Calculate the maximum delta in the direct neighborhood:
    float2 maxDelta = max(delta.xy, delta.zw);

    // Calculate left-left and top-top deltas:
    float Lleftleft = dot(SMAASamplePoint(colorTex, offset[2].xy).rgb, weights);
    float Ltoptop = dot(SMAASamplePoint(colorTex, offset[2].zw).rgb, weights);
    delta.zw = abs(float2(Lleft, Ltop) - float2(Lleftleft, Ltoptop));

    // Calculate the final maximum delta:
    maxDelta = max(maxDelta.xy, delta.zw);
    float finalDelta = max(maxDelta.x, maxDelta.y);

    // Local contrast adaptation:
    edges.xy *= step(finalDelta, SMAA_LOCAL_CONTRAST_ADAPTATION_FACTOR * delta.xy);

    return edges;
}

float2 PersistenceSMAAColorEdgeDetectionPS(float2 texcoord,
                                float4 offset[3],
                                SMAATexture2D(colorTex)
                                #if SMAA_PREDICATION
                                , SMAATexture2D(predicationTex)
                                #endif
                                ) {
    // Calculate the threshold:
    #if SMAA_PREDICATION
    float2 threshold = SMAACalculatePredicatedThreshold(texcoord, offset, predicationTex);
    #else
    float2 threshold = float2(SMAA_THRESHOLD, SMAA_THRESHOLD);
    #endif

    // Calculate color deltas:
    float4 delta;
    float3 C = SMAASamplePoint(colorTex, texcoord).rgb;

    float3 Cleft = SMAASamplePoint(colorTex, offset[0].xy).rgb;
    float3 t = abs(C - Cleft);
    delta.x = max(max(t.r, t.g), t.b);

    float3 Ctop  = SMAASamplePoint(colorTex, offset[0].zw).rgb;
    t = abs(C - Ctop);
    delta.y = max(max(t.r, t.g), t.b);

    // We do the usual threshold:
    float2 edges = step(threshold, delta.xy);

    // Then discard if there is no edge:
    if (dot(edges, float2(1.0, 1.0)) == 0.0)
        return float2(0.0, 0.0);

    // Calculate right and bottom deltas:
    float3 Cright = SMAASamplePoint(colorTex, offset[1].xy).rgb;
    t = abs(C - Cright);
    delta.z = max(max(t.r, t.g), t.b);

    float3 Cbottom  = SMAASamplePoint(colorTex, offset[1].zw).rgb;
    t = abs(C - Cbottom);
    delta.w = max(max(t.r, t.g), t.b);

    // Calculate the maximum delta in the direct neighborhood:
    float2 maxDelta = max(delta.xy, delta.zw);

    // Calculate left-left and top-top deltas:
    float3 Cleftleft  = SMAASamplePoint(colorTex, offset[2].xy).rgb;
    t = abs(C - Cleftleft);
    delta.z = max(max(t.r, t.g), t.b);

    float3 Ctoptop = SMAASamplePoint(colorTex, offset[2].zw).rgb;
    t = abs(C - Ctoptop);
    delta.w = max(max(t.r, t.g), t.b);

    // Calculate the final maximum delta:
    maxDelta = max(maxDelta.xy, delta.zw);
    float finalDelta = max(maxDelta.x, maxDelta.y);

    // Local contrast adaptation:
    edges.xy *= step(finalDelta, SMAA_LOCAL_CONTRAST_ADAPTATION_FACTOR * delta.xy);

    return edges;
}

float2 PersistenceSMAADepthEdgeDetectionPS(float2 texcoord,
                                float4 offset[3],
                                SMAATexture2D(depthTex)) {
    float3 neighbours = SMAAGatherNeighbours(texcoord, offset, SMAATexturePass2D(depthTex));
    float2 delta = abs(neighbours.xx - float2(neighbours.y, neighbours.z));
    float2 edges = step(SMAA_DEPTH_THRESHOLD, delta);

    if (dot(edges, float2(1.0, 1.0)) == 0.0)
        return float2(0.0, 0.0);

    return edges;
}

bool PreviousRawEdgeAt(float2 uv) {
    float2 previousUV = uv - velocityTex.SampleLevel(PointSampler, uv, 0).rg;
    bool inBounds = all(previousUV >= 0.0) && all(previousUV < 1.0);
    int2 previousPixel = int2(floor(previousUV * SMAA_RT_METRICS.zw));
    bool previousEdge = any(previousRawEdges.Load(int3(previousPixel, 0)).rg > 0.0);
    return inBounds && previousEdge;
}


float2 PersistenceLumaRawEdgePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0, float4 offset[3] : TEXCOORD1) : SV_TARGET {
    bool oldEdge = PreviousRawEdgeAt(texcoord);
    #if SMAA_PREDICATION
    float2 edge = PersistenceSMAALumaRawEdgeDetectionPS(texcoord, offset, colorTexGamma, depthTex);
    #else
    float2 edge = PersistenceSMAALumaRawEdgeDetectionPS(texcoord, offset, colorTexGamma);
    #endif
    if (!(any(edge > 0.0) || oldEdge)) discard;
    return edge;
}

float2 PersistenceLumaEdgePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0, float4 offset[3] : TEXCOORD1) : SV_TARGET {
    bool oldEdge = PreviousRawEdgeAt(texcoord);
    #if SMAA_PREDICATION
    float2 edge = PersistenceSMAALumaEdgeDetectionPS(texcoord, offset, colorTexGamma, depthTex);
    #else
    float2 edge = PersistenceSMAALumaEdgeDetectionPS(texcoord, offset, colorTexGamma);
    #endif
    if (!(any(edge > 0.0) || oldEdge)) discard;
    return edge;
}

float2 PersistenceColorEdgePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0, float4 offset[3] : TEXCOORD1) : SV_TARGET {
    bool oldEdge = PreviousRawEdgeAt(texcoord);
    #if SMAA_PREDICATION
    float2 edge = PersistenceSMAAColorEdgeDetectionPS(texcoord, offset, colorTexGamma, depthTex);
    #else
    float2 edge = PersistenceSMAAColorEdgeDetectionPS(texcoord, offset, colorTexGamma);
    #endif
    if (!(any(edge > 0.0) || oldEdge)) discard;
    return edge;
}

float2 PersistenceDepthEdgePS(float4 position : SV_POSITION, float2 texcoord : TEXCOORD0, float4 offset[3] : TEXCOORD1) : SV_TARGET {
    bool oldEdge = PreviousRawEdgeAt(texcoord);
    float2 edge = PersistenceSMAADepthEdgeDetectionPS(texcoord, offset, depthTex);
    if (!(any(edge > 0.0) || oldEdge)) discard;
    return edge;
}
