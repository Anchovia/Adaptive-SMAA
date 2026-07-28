// DX11 proxy for using SMAA.hlsl shaders (since there's no DX10 effects/techniques)

#ifndef SMAA_WRAPPER__HLSL
#define SMAA_WRAPPER__HLSL

// only used if using dynamic constants or using MSAA
struct SMAAShaderConstants
{
    /**
     * This is only required for temporal modes (SMAA T2x).
     */
#ifndef INCLUDED_FROM_CPP
    float4 subsampleIndices;
#else
    float subsampleIndices[4];
#endif
    /**
     * This is required for blending the results of previous subsample with the
     * output render target; it's used in SMAA S2x and 4x, for other modes just use
     * 1.0 (no blending).
     */
    float blendFactor;
    /**
     * This can be ignored; its purpose is to support interactive custom parameter
     * tweaking.
     */
    float threshld;
    float maxSearchSteps;
    float maxSearchStepsDiag;
    float cornerRounding;

    float padding0;
    float padding1;
    float padding2;
};

struct SMAAReprojectionConstants
{
#ifndef INCLUDED_FROM_CPP
    float4x4 CurrentViewProjInv;
    float4x4 CurrentUnjitteredViewProj;
    float4x4 PreviousViewProj;
    float4 CurrentJitterUV;
#else
    VertexAsylum::vaMatrix4x4 CurrentViewProjInv;
    VertexAsylum::vaMatrix4x4 CurrentUnjitteredViewProj;
    VertexAsylum::vaMatrix4x4 PreviousViewProj;
    VertexAsylum::vaVector4 CurrentJitterUV;
#endif
};

// the rest below is shader only code
#ifndef INCLUDED_FROM_CPP

// this line is VA framework specific (ignore when using outside of VA)
#ifdef VA_COMPILED_AS_SHADER_CODE
#include "MagicMacrosMagicFile.h"
#endif


cbuffer SMAAGlobals : register( b0 )
{
    SMAAShaderConstants g_SMAA;
}

cbuffer SMAAReprojectionGlobals : register( b1 )
{
    SMAAReprojectionConstants g_SMAAReprojection;
}


// Use a real macro here for maximum performance!
#ifndef SMAA_RT_METRICS // This is just for compilation-time syntax checking.
#define SMAA_RT_METRICS float4(1.0 / 1280.0, 1.0 / 720.0, 1280.0, 720.0)
#endif

// Set the HLSL version:
#ifndef SMAA_HLSL_4_1
#define SMAA_HLSL_4
#endif

#ifndef SMAA_EDGE_GUIDED_TEMPORAL
#define SMAA_EDGE_GUIDED_TEMPORAL 0
#endif

#ifndef SMAA_EDGE_GUIDED_TEMPORAL_STABILIZED
#define SMAA_EDGE_GUIDED_TEMPORAL_STABILIZED 0
#endif

#ifndef SMAA_EDGE_GUIDED_TEMPORAL_HISTORY_MODE
#define SMAA_EDGE_GUIDED_TEMPORAL_HISTORY_MODE 0
#endif

#ifndef SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS
#define SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS 1
#endif

#ifndef SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS
#define SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS 1
#endif

// Set preset defines:
#ifdef SMAA_PRESET_CUSTOM
#define SMAA_THRESHOLD              g_SMAA.threshld
#define SMAA_MAX_SEARCH_STEPS       g_SMAA.maxSearchSteps
#define SMAA_MAX_SEARCH_STEPS_DIAG  g_SMAA.maxSearchStepsDiag
#define SMAA_CORNER_ROUNDING        g_SMAA.cornerRounding
#endif

SamplerState                        LinearSampler                       : register( s0 );
SamplerState                        PointSampler                        : register( s1 );

#include "SMAA.hlsl"

 /**                                                                    
  * Pre-computed area and search textures                               
  */                                                                    
 Texture2D                          areaTex                             : register( t0 );
 Texture2D                          searchTex                           : register( t1 );

/**
  * Input textures
  */
 Texture2D                          colorTex                            : register( t2 );
 Texture2D                          colorTexGamma                       : register( t3 );
 Texture2D                          colorTexPrev                        : register( t4 );
 Texture2DMS<float4, 2>             colorTexMS                          : register( t5 );
 Texture2D                          depthTex                            : register( t6 );
 Texture2D                          velocityTex                         : register( t7 );
                                                                        
 /**                                                                    
  * Temporal textures                                                   
  */                                                                    
 Texture2D                          edgesTex                            : register( t8 );
 Texture2D                          blendTex                            : register( t9 );
 Texture2D                          edgesTexPrev                        : register( t10 );
                                                                        
 /**
 * Function wrappers
 */
void DX10_SMAAEdgeDetectionVS(float4 position : POSITION,
                              out float4 svPosition : SV_POSITION,
                              inout float2 texcoord : TEXCOORD0,
                              out float4 offset[3] : TEXCOORD1) {
    svPosition = position;
    SMAAEdgeDetectionVS(texcoord, offset);
}

void DX10_SMAABlendingWeightCalculationVS(float4 position : POSITION,
                                          out float4 svPosition : SV_POSITION,
                                          inout float2 texcoord : TEXCOORD0,
                                          out float2 pixcoord : TEXCOORD1,
                                          out float4 offset[3] : TEXCOORD2) {
    svPosition = position;
    SMAABlendingWeightCalculationVS(texcoord, pixcoord, offset);
}

void DX10_SMAANeighborhoodBlendingVS(float4 position : POSITION,
                                     out float4 svPosition : SV_POSITION,
                                     inout float2 texcoord : TEXCOORD0,
                                     out float4 offset : TEXCOORD1) {
    svPosition = position;
    SMAANeighborhoodBlendingVS(texcoord, offset);
}

void DX10_SMAAResolveVS(float4 position : POSITION,
                        out float4 svPosition : SV_POSITION,
                        inout float2 texcoord : TEXCOORD0) {
    svPosition = position;
}

void DX10_SMAASeparateVS(float4 position : POSITION,
                         out float4 svPosition : SV_POSITION,
                         inout float2 texcoord : TEXCOORD0) {
    svPosition = position;
}

float2 DX10_SMAALumaRawEdgeDetectionPS(float4 position : SV_POSITION,
                                    float2 texcoord : TEXCOORD0,
                                    float4 offset[3] : TEXCOORD1) : SV_TARGET {
    #if SMAA_PREDICATION
    return SMAALumaRawEdgeDetectionPS(texcoord, offset, colorTexGamma, depthTex);
    #else
    return SMAALumaRawEdgeDetectionPS(texcoord, offset, colorTexGamma);
    #endif
}

float2 DX10_SMAALumaEdgeDetectionPS(float4 position : SV_POSITION,
                                    float2 texcoord : TEXCOORD0,
                                    float4 offset[3] : TEXCOORD1) : SV_TARGET {
    #if SMAA_PREDICATION
    return SMAALumaEdgeDetectionPS(texcoord, offset, colorTexGamma, depthTex);
    #else
    return SMAALumaEdgeDetectionPS(texcoord, offset, colorTexGamma);
    #endif
}

float2 DX10_SMAAColorEdgeDetectionPS(float4 position : SV_POSITION,
                                     float2 texcoord : TEXCOORD0,
                                     float4 offset[3] : TEXCOORD1) : SV_TARGET {
    #if SMAA_PREDICATION
    return SMAAColorEdgeDetectionPS(texcoord, offset, colorTexGamma, depthTex);
    #else
    return SMAAColorEdgeDetectionPS(texcoord, offset, colorTexGamma);
    #endif
}

float2 DX10_SMAADepthEdgeDetectionPS(float4 position : SV_POSITION,
                                     float2 texcoord : TEXCOORD0,
                                     float4 offset[3] : TEXCOORD1) : SV_TARGET {
    return SMAADepthEdgeDetectionPS(texcoord, offset, depthTex);
}

float4 DX10_SMAABlendingWeightCalculationPS(float4 position : SV_POSITION,
                                            float2 texcoord : TEXCOORD0,
                                            float2 pixcoord : TEXCOORD1,
                                            float4 offset[3] : TEXCOORD2) : SV_TARGET {
    return SMAABlendingWeightCalculationPS(texcoord, pixcoord, offset, edgesTex, areaTex, searchTex, g_SMAA.subsampleIndices);
}

float4 DX10_SMAANeighborhoodBlendingPS(float4 position : SV_POSITION,
                                       float2 texcoord : TEXCOORD0,
                                       float4 offset : TEXCOORD1) : SV_TARGET {
    #if SMAA_REPROJECTION
    return SMAANeighborhoodBlendingPS(texcoord, offset, colorTex, blendTex, velocityTex);
    #else
    return SMAANeighborhoodBlendingPS(texcoord, offset, colorTex, blendTex);
    #endif
}

float4 DX10_SMAAResolvePS(float4 position : SV_POSITION,
                          float2 texcoord : TEXCOORD0) : SV_TARGET {
    #if SMAA_EDGE_GUIDED_TEMPORAL
    // V3 hypothesis: use temporal history only at current-frame SMAA edges.
    // Non-edge pixels retain the current spatial SMAA result.
        #if SMAA_EDGE_GUIDED_TEMPORAL_STABILIZED
        // T2X projection jitter moves the current image in screen space. Sample
        // the current edge support at its jittered location, and de-jitter
        // non-edge pixels before bypassing temporal history.
        float2 currentJitteredUV = texcoord + g_SMAAReprojection.CurrentJitterUV.xy;
        float2 pixelSize = SMAA_RT_METRICS.xy;
        float currentEdgeSupport = 0.0;
        [unroll]
        for (int y = -SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS; y <= SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS; y++) {
            [unroll]
            for (int x = -SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS; x <= SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS; x++) {
                float2 currentEdges = edgesTex.SampleLevel(PointSampler, currentJitteredUV + float2(x, y) * pixelSize, 0.0).rg;
                currentEdgeSupport = max(currentEdgeSupport, max(currentEdges.r, currentEdges.g));
            }
        }

        float previousEdgeSupport = 0.0;
        #if SMAA_REPROJECTION
        float2 velocity = -SMAA_DECODE_VELOCITY(velocityTex.SampleLevel(LinearSampler, currentJitteredUV, 0.0));
        float2 previousJitteredUV = texcoord + velocity + g_SMAAReprojection.CurrentJitterUV.zw;
            #if SMAA_EDGE_GUIDED_TEMPORAL_HISTORY_MODE != 0
            bool previousInBounds = all(previousJitteredUV >= 0.0) && all(previousJitteredUV <= 1.0);
            if (previousInBounds) {
            [unroll]
            for (int previousY = -SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS; previousY <= SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS; previousY++) {
                [unroll]
                for (int previousX = -SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS; previousX <= SMAA_EDGE_GUIDED_TEMPORAL_SUPPORT_RADIUS; previousX++) {
                    float2 previousEdges = edgesTexPrev.SampleLevel(PointSampler, previousJitteredUV + float2(previousX, previousY) * pixelSize, 0.0).rg;
                    previousEdgeSupport = max(previousEdgeSupport, max(previousEdges.r, previousEdges.g));
                }
            }
            }
            #endif
        #endif

        float historySupport = currentEdgeSupport;
        #if SMAA_EDGE_GUIDED_TEMPORAL_HISTORY_MODE == 1
        // V3c: one-frame edge hysteresis.
        historySupport = max(currentEdgeSupport, previousEdgeSupport);
        #elif SMAA_EDGE_GUIDED_TEMPORAL_HISTORY_MODE == 2
        // V4/V4b: require the current and reprojected previous edge.
        historySupport = min(currentEdgeSupport, previousEdgeSupport);
        #endif

        float4 currentDeJittered = colorTex.SampleLevel(LinearSampler, currentJitteredUV, 0.0);
        if (historySupport <= 0.0)
            return currentDeJittered;

        #if SMAA_REPROJECTION
        // Keep edge and non-edge output in the same unjittered coordinate
        // system. The previous spatial SMAA buffer contains the opposite T2X
        // jitter, so reproject in unjittered space and then add its jitter.
        float4 previousDeJittered = colorTexPrev.SampleLevel(LinearSampler, previousJitteredUV, 0.0);
        float delta = abs(currentDeJittered.a * currentDeJittered.a - previousDeJittered.a * previousDeJittered.a) / 5.0;
        float weight = 0.5 * saturate(1.0 - sqrt(delta) * SMAA_REPROJECTION_WEIGHT_SCALE);
        return lerp(currentDeJittered, previousDeJittered, weight);
        #else
        return currentDeJittered;
        #endif
        #else
        float2 currentEdges = edgesTex.SampleLevel(PointSampler, texcoord, 0.0).rg;
        if (max(currentEdges.r, currentEdges.g) <= 0.0)
            return colorTex.SampleLevel(PointSampler, texcoord, 0.0);
        #endif
    #endif

    #if SMAA_REPROJECTION
    return SMAAResolvePS(texcoord, colorTex, colorTexPrev, velocityTex);
    #else
    return SMAAResolvePS(texcoord, colorTex, colorTexPrev);
    #endif
}

float2 DX10_SMAATemporalEdgeStatsPS(float4 position : SV_POSITION,
                                    float2 texcoord : TEXCOORD0) : SV_TARGET {
    uint statsWidth;
    uint statsHeight;
    edgesTex.GetDimensions(statsWidth, statsHeight);
    float2 pixelSize = 1.0 / float2(statsWidth, statsHeight);
    float2 currentJitteredUV = texcoord + g_SMAAReprojection.CurrentJitterUV.xy;

    float currentEdgeSupport = 0.0;
    [unroll]
    for (int y = -SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS; y <= SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS; y++) {
        [unroll]
        for (int x = -SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS; x <= SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS; x++) {
            float2 currentEdges = edgesTex.SampleLevel(PointSampler, currentJitteredUV + float2(x, y) * pixelSize, 0.0).rg;
            currentEdgeSupport = max(currentEdgeSupport, max(currentEdges.r, currentEdges.g));
        }
    }

    float2 velocity = -SMAA_DECODE_VELOCITY(velocityTex.SampleLevel(LinearSampler, currentJitteredUV, 0.0));
    float2 previousJitteredUV = texcoord + velocity + g_SMAAReprojection.CurrentJitterUV.zw;
    float previousEdgeSupport = 0.0;
    bool previousInBounds = all(previousJitteredUV >= 0.0) && all(previousJitteredUV <= 1.0);
    if (previousInBounds) {
        [unroll]
        for (int previousY = -SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS; previousY <= SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS; previousY++) {
            [unroll]
            for (int previousX = -SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS; previousX <= SMAA_TEMPORAL_EDGE_STATS_SUPPORT_RADIUS; previousX++) {
                float2 previousEdges = edgesTexPrev.SampleLevel(PointSampler, previousJitteredUV + float2(previousX, previousY) * pixelSize, 0.0).rg;
                previousEdgeSupport = max(previousEdgeSupport, max(previousEdges.r, previousEdges.g));
            }
        }
    }

    return float2(currentEdgeSupport > 0.0 ? 1.0 : 0.0,
                  previousEdgeSupport > 0.0 ? 1.0 : 0.0);
}

float2 DX10_SMAAGenerateCameraVelocityPS(float4 position : SV_POSITION,
                                         float2 texcoord : TEXCOORD0) : SV_TARGET {
    float depth = depthTex.Load(int3(int2(position.xy), 0)).r;
    float4 currentClip = float4(texcoord.x * 2.0 - 1.0,
                               1.0 - texcoord.y * 2.0,
                               depth,
                               1.0);
    float4 worldPosition = mul(g_SMAAReprojection.CurrentViewProjInv, currentClip);
    worldPosition /= worldPosition.w;

    float4 currentUnjitteredClip = mul(g_SMAAReprojection.CurrentUnjitteredViewProj, worldPosition);
    float4 previousClip = mul(g_SMAAReprojection.PreviousViewProj, worldPosition);
    float2 currentUnjitteredNDC = currentUnjitteredClip.xy / currentUnjitteredClip.w;
    float2 previousNDC = previousClip.xy / previousClip.w;
    float2 currentUnjitteredUV = float2(currentUnjitteredNDC.x * 0.5 + 0.5,
                                        0.5 - currentUnjitteredNDC.y * 0.5);
    float2 previousUV = float2(previousNDC.x * 0.5 + 0.5,
                               0.5 - previousNDC.y * 0.5);

    // Official SMAA resolve negates this value before adding it to the current
    // UV, so store currentUV - previousUV (the motion-blur convention).
    return currentUnjitteredUV - previousUV;
}

void DX10_SMAASeparatePS(float4 position : SV_POSITION,
                         float2 texcoord : TEXCOORD0,
                         out float4 target0 : SV_TARGET0,
                         out float4 target1 : SV_TARGET1) {
    SMAASeparatePS(position, texcoord, target0, target1, colorTexMS);
}

#endif // #ifndef INCLUDED_FROM_CPP

#endif // #ifndef SMAA_WRAPPER__HLSL
