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
    float4 TemporalResolution;
    // x: history weight, y: non-dominant removal amount,
    // z: camera reprojection enabled, w: output requires linear-to-sRGB conversion.
    float4 TSCMAAParams;
    // x: base luma-edge threshold, y: candidate policy enum
    // (0 all base, 1 Intel-family non-dominant, 2 legacy experimental 3x3),
    // z: forced candidate count, w: forced-count diagnostics enabled.
    float4 TSCMAACandidateParams;
    // x: history sampler enum (0 bilinear, 1 Catmull-Rom 5-tap),
    // y: history clipping enum (0 off, 1 YCoCg variance).
    float4 TSCMAAResolveParams;
#else
    VertexAsylum::vaMatrix4x4 CurrentViewProjInv;
    VertexAsylum::vaMatrix4x4 CurrentUnjitteredViewProj;
    VertexAsylum::vaMatrix4x4 PreviousViewProj;
    VertexAsylum::vaVector4 TemporalResolution;
    // Matches the shader-side field description above.
    VertexAsylum::vaVector4 TSCMAAParams;
    VertexAsylum::vaVector4 TSCMAACandidateParams;
    VertexAsylum::vaVector4 TSCMAAResolveParams;
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
    #if SMAA_REPROJECTION
    return SMAAResolvePS(texcoord, colorTex, colorTexPrev, velocityTex);
    #else
    return SMAAResolvePS(texcoord, colorTex, colorTexPrev);
    #endif
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

#if !defined(SMAA_TSCMAA_COMPUTE)
Texture2D<float> tscmaaDebugMask : register( t10 );

float4 TSCMAADebugMaskPS(float4 position : SV_POSITION,
                         float2 texcoord : TEXCOORD0) : SV_TARGET {
    float mask = tscmaaDebugMask.Load(int3(int2(position.xy), 0));
    return float4(mask, mask, mask, 1.0);
}
#endif

#if defined(SMAA_TSCMAA_COMPUTE)

// TSCMAA-inspired selective temporal resolve resources. The public Intel
// material specifies the pipeline, but not the exact candidate-selection
// shader. The documented adaptation is described in
// Docs/SMAA-TSCMAA-Implementation-Plan-ko.md.
Texture2D<float4>                    tscmaaCurrentColor                  : register( t10 );
Texture2D<float4>                    tscmaaHistoryColor                  : register( t11 );
Texture2D<float>                     tscmaaLuma                          : register( t12 );

RWTexture2D<float4>                  tscmaaOutput                        : register( u0 );
RWStructuredBuffer<uint>             tscmaaCandidates                    : register( u1 );
RWByteAddressBuffer                  tscmaaControl                       : register( u2 );
RWByteAddressBuffer                  tscmaaDispatchArgs                  : register( u3 );
RWTexture2D<float>                   tscmaaBaseEdgeMask                  : register( u4 );
RWTexture2D<float>                   tscmaaCandidateMask                 : register( u5 );

#define TSCMAA_CANDIDATE_COUNTER_OFFSET       0
#define TSCMAA_PROCESS_COUNT_OFFSET           4
#define TSCMAA_EDGE_COUNTER_OFFSET            8
#define TSCMAA_DISPATCH_GROUP_COUNT_OFFSET    12
#define TSCMAA_RESOLVE_NUM_THREADS            64

int2 TSCMAAClampPixel(int2 pixel, int2 dimensions) {
    return clamp(pixel, int2(0, 0), dimensions - 1);
}

float2 TSCMAABaseEdgeStrength(int2 pixel, int2 dimensions) {
    pixel = TSCMAAClampPixel(pixel, dimensions);
    float center = tscmaaLuma.Load(int3(pixel, 0));
    float left = tscmaaLuma.Load(int3(TSCMAAClampPixel(pixel + int2(-1, 0), dimensions), 0));
    float top = tscmaaLuma.Load(int3(TSCMAAClampPixel(pixel + int2(0, -1), dimensions), 0));
    return float2(abs(center - left), abs(center - top));
}

bool TSCMAAIsBaseEdge(float2 directionalStrength) {
    return any(directionalStrength > g_SMAAReprojection.TSCMAACandidateParams.x);
}

// Adaptation of the local-contrast structure in Intel's public CMAA2 shader:
// each edge competes with connected perpendicular edges. The public TSCMAA
// document supplies the 1/22 threshold and 0.5 removal defaults, but not the
// lost sample's exact candidate-selection shader.
bool TSCMAAIsIntelFamilyNonDominantCandidate(int2 pixel, int2 dimensions, float2 directionalStrength) {
    float maximumPerpendicularForVertical = 0.0;
    maximumPerpendicularForVertical = max(maximumPerpendicularForVertical, TSCMAABaseEdgeStrength(pixel, dimensions).y);
    maximumPerpendicularForVertical = max(maximumPerpendicularForVertical, TSCMAABaseEdgeStrength(pixel + int2(-1, 0), dimensions).y);
    maximumPerpendicularForVertical = max(maximumPerpendicularForVertical, TSCMAABaseEdgeStrength(pixel + int2(0, 1), dimensions).y);
    maximumPerpendicularForVertical = max(maximumPerpendicularForVertical, TSCMAABaseEdgeStrength(pixel + int2(-1, 1), dimensions).y);

    float maximumPerpendicularForHorizontal = 0.0;
    maximumPerpendicularForHorizontal = max(maximumPerpendicularForHorizontal, TSCMAABaseEdgeStrength(pixel, dimensions).x);
    maximumPerpendicularForHorizontal = max(maximumPerpendicularForHorizontal, TSCMAABaseEdgeStrength(pixel + int2(0, -1), dimensions).x);
    maximumPerpendicularForHorizontal = max(maximumPerpendicularForHorizontal, TSCMAABaseEdgeStrength(pixel + int2(1, 0), dimensions).x);
    maximumPerpendicularForHorizontal = max(maximumPerpendicularForHorizontal, TSCMAABaseEdgeStrength(pixel + int2(1, -1), dimensions).x);

    float removalAmount = g_SMAAReprojection.TSCMAAParams.y;
    float threshold = g_SMAAReprojection.TSCMAACandidateParams.x;
    bool verticalDominant = directionalStrength.x - maximumPerpendicularForVertical * removalAmount > threshold;
    bool horizontalDominant = directionalStrength.y - maximumPerpendicularForHorizontal * removalAmount > threshold;
    return verticalDominant || horizontalDominant;
}

float TSCMAAExperimentalEdgeStrength(int2 pixel, int2 dimensions) {
    pixel = TSCMAAClampPixel(pixel, dimensions);
    float2 edge = edgesTex.Load(int3(pixel, 0)).rg;
    if (max(edge.x, edge.y) <= 0.0)
        return 0.0;

    float center = tscmaaLuma.Load(int3(pixel, 0));
    float left = tscmaaLuma.Load(int3(TSCMAAClampPixel(pixel + int2(-1, 0), dimensions), 0));
    float top = tscmaaLuma.Load(int3(TSCMAAClampPixel(pixel + int2(0, -1), dimensions), 0));
    return max(edge.x * abs(center - left), edge.y * abs(center - top));
}

bool TSCMAAIsExperimentalLocallyDominantCandidate(int2 pixel, int2 dimensions, float strength) {
    float localSum = 0.0;
    float localMaximum = 0.0;

    [unroll]
    for (int y = -1; y <= 1; y++) {
        [unroll]
        for (int x = -1; x <= 1; x++) {
            float neighbourStrength = TSCMAAExperimentalEdgeStrength(pixel + int2(x, y), dimensions);
            localSum += neighbourStrength;
            localMaximum = max(localMaximum, neighbourStrength);
        }
    }

    float localAverage = localSum / 9.0;
    float nonDominantRemovalAmount = g_SMAAReprojection.TSCMAAParams.y;
    float localThreshold = lerp(localAverage, localMaximum, nonDominantRemovalAmount);
    return strength > 0.0 && strength >= localThreshold;
}

[numthreads(8, 8, 1)]
void TSCMAAExtractCandidatesCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint width;
    uint height;
    tscmaaLuma.GetDimensions(width, height);
    if (dispatchThreadID.x >= width || dispatchThreadID.y >= height)
        return;

    int2 pixel = int2(dispatchThreadID.xy);
    int2 dimensions = int2(width, height);
    float2 directionalStrength = TSCMAABaseEdgeStrength(pixel, dimensions);
    bool forcedCountDiagnostics = g_SMAAReprojection.TSCMAACandidateParams.w > 0.5;
    uint linearPixelIndex = dispatchThreadID.y * width + dispatchThreadID.x;
    uint forcedCandidateCount = min((uint)(g_SMAAReprojection.TSCMAACandidateParams.z + 0.5), width * height);
    bool baseEdge = forcedCountDiagnostics?
        linearPixelIndex < forcedCandidateCount : TSCMAAIsBaseEdge(directionalStrength);
    tscmaaBaseEdgeMask[pixel] = baseEdge ? 1.0 : 0.0;

    if (baseEdge) {
        uint ignoredEdgeIndex;
        tscmaaControl.InterlockedAdd(TSCMAA_EDGE_COUNTER_OFFSET, 1, ignoredEdgeIndex);
    }

    uint policy = (uint)(g_SMAAReprojection.TSCMAACandidateParams.y + 0.5);
    bool candidate = forcedCountDiagnostics && baseEdge;
    if (!forcedCountDiagnostics && policy == 0) {
        candidate = baseEdge;
    } else if (!forcedCountDiagnostics && policy == 1) {
        candidate = TSCMAAIsIntelFamilyNonDominantCandidate(pixel, dimensions, directionalStrength);
    } else if (!forcedCountDiagnostics) {
        float experimentalStrength = TSCMAAExperimentalEdgeStrength(pixel, dimensions);
        candidate = TSCMAAIsExperimentalLocallyDominantCandidate(pixel, dimensions, experimentalStrength);
    }

    tscmaaCandidateMask[pixel] = candidate ? 1.0 : 0.0;
    if (!candidate)
        return;

    uint candidateIndex;
    tscmaaControl.InterlockedAdd(TSCMAA_CANDIDATE_COUNTER_OFFSET, 1, candidateIndex);

    uint candidateCapacity;
    uint candidateStride;
    tscmaaCandidates.GetDimensions(candidateCapacity, candidateStride);
    if (candidateIndex < candidateCapacity)
        tscmaaCandidates[candidateIndex] = (dispatchThreadID.x << 16) | dispatchThreadID.y;
}

[numthreads(1, 1, 1)]
void TSCMAAComputeDispatchArgsCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint candidateCount = tscmaaControl.Load(TSCMAA_CANDIDATE_COUNTER_OFFSET);
    uint candidateCapacity;
    uint candidateStride;
    tscmaaCandidates.GetDimensions(candidateCapacity, candidateStride);
    candidateCount = min(candidateCount, candidateCapacity);

    uint dispatchGroupCount = (candidateCount + TSCMAA_RESOLVE_NUM_THREADS - 1) / TSCMAA_RESOLVE_NUM_THREADS;
    tscmaaControl.Store(TSCMAA_PROCESS_COUNT_OFFSET, candidateCount);
    tscmaaControl.Store(TSCMAA_DISPATCH_GROUP_COUNT_OFFSET, dispatchGroupCount);
    tscmaaDispatchArgs.Store(0, dispatchGroupCount);
    tscmaaDispatchArgs.Store(4, 1);
    tscmaaDispatchArgs.Store(8, 1);
}

float4 TSCMAASampleHistoryCatmullRom5Tap(float2 uv, float2 textureSize) {
    float2 samplePosition = uv * textureSize;
    float2 texelPosition1 = floor(samplePosition - 0.5) + 0.5;
    float2 fraction = samplePosition - texelPosition1;

    float2 weight0 = fraction * (-0.5 + fraction * (1.0 - 0.5 * fraction));
    float2 weight1 = 1.0 + fraction * fraction * (-2.5 + 1.5 * fraction);
    float2 weight2 = fraction * (0.5 + fraction * (2.0 - 1.5 * fraction));
    float2 weight3 = fraction * fraction * (-0.5 + 0.5 * fraction);

    float2 weight12 = weight1 + weight2;
    float2 offset12 = weight2 / max(weight12, float2(1.0e-6, 1.0e-6));

    float2 texelPosition0 = texelPosition1 - 1.0;
    float2 texelPosition3 = texelPosition1 + 2.0;
    float2 texelPosition12 = texelPosition1 + offset12;
    texelPosition0 /= textureSize;
    texelPosition3 /= textureSize;
    texelPosition12 /= textureSize;

    float topWeight = weight12.x * weight0.y;
    float leftWeight = weight0.x * weight12.y;
    float centerWeight = weight12.x * weight12.y;
    float rightWeight = weight3.x * weight12.y;
    float bottomWeight = weight12.x * weight3.y;

    float4 result = 0.0;
    result += tscmaaHistoryColor.SampleLevel(LinearSampler, float2(texelPosition12.x, texelPosition0.y), 0.0) * topWeight;
    result += tscmaaHistoryColor.SampleLevel(LinearSampler, float2(texelPosition0.x, texelPosition12.y), 0.0) * leftWeight;
    result += tscmaaHistoryColor.SampleLevel(LinearSampler, texelPosition12, 0.0) * centerWeight;
    result += tscmaaHistoryColor.SampleLevel(LinearSampler, float2(texelPosition3.x, texelPosition12.y), 0.0) * rightWeight;
    result += tscmaaHistoryColor.SampleLevel(LinearSampler, float2(texelPosition12.x, texelPosition3.y), 0.0) * bottomWeight;

    float totalWeight = topWeight + leftWeight + centerWeight + rightWeight + bottomWeight;
    return result / ((abs(totalWeight) > 1.0e-6) ? totalWeight : 1.0);
}

#define TSCMAA_CATMULL_ROM_DIAGNOSTIC_SIZE 16

[numthreads(8, 8, 1)]
void TSCMAACatmullRomDiagnosticCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    if (dispatchThreadID.x >= TSCMAA_CATMULL_ROM_DIAGNOSTIC_SIZE ||
        dispatchThreadID.y >= TSCMAA_CATMULL_ROM_DIAGNOSTIC_SIZE)
        return;

    uint sourceWidth;
    uint sourceHeight;
    tscmaaHistoryColor.GetDimensions(sourceWidth, sourceHeight);

    // Covers [-0.1, 1.1] so the diagnostic also exercises the clamp sampler
    // outside the normalized texture domain.
    float2 uv = (float2(dispatchThreadID.xy) - 1.25) / 12.5;
    tscmaaOutput[dispatchThreadID.xy] =
        TSCMAASampleHistoryCatmullRom5Tap(uv, float2(sourceWidth, sourceHeight));
}

float3 TSCMAARGBToYCoCg(float3 color) {
    float chromaOrange = color.r - color.b;
    float temporary = color.b + chromaOrange * 0.5;
    float chromaGreen = color.g - temporary;
    float luma = temporary + chromaGreen * 0.5;
    return float3(luma, chromaOrange, chromaGreen);
}

float3 TSCMAAYCoCgToRGB(float3 color) {
    float temporary = color.x - color.z * 0.5;
    float green = color.z + temporary;
    float blue = temporary - color.y * 0.5;
    float red = blue + color.y;
    return float3(red, green, blue);
}

float3 TSCMAAClipHistorySegment(float3 currentColor, float3 historyColor, float3 boxMinimum, float3 boxMaximum) {
    float3 direction = historyColor - currentColor;
    float clipAmount = 1.0;

    [unroll]
    for (int component = 0; component < 3; component++) {
        if (direction[component] > 1.0e-6)
            clipAmount = min(clipAmount, (boxMaximum[component] - currentColor[component]) / direction[component]);
        else if (direction[component] < -1.0e-6)
            clipAmount = min(clipAmount, (boxMinimum[component] - currentColor[component]) / direction[component]);
    }

    return currentColor + direction * saturate(clipAmount);
}

float3 TSCMAAVarianceClip(int2 pixel, int2 dimensions, float3 currentColor, float3 historyColor) {
    float3 firstMoment = 0.0;
    float3 secondMoment = 0.0;
    float3 neighbourhoodMinimum = float3(1.0e20, 1.0e20, 1.0e20);
    float3 neighbourhoodMaximum = float3(-1.0e20, -1.0e20, -1.0e20);

    [unroll]
    for (int y = -1; y <= 1; y++) {
        [unroll]
        for (int x = -1; x <= 1; x++) {
            int2 samplePixel = TSCMAAClampPixel(pixel + int2(x, y), dimensions);
            float3 sampleColor = TSCMAARGBToYCoCg(tscmaaCurrentColor.Load(int3(samplePixel, 0)).rgb);
            firstMoment += sampleColor;
            secondMoment += sampleColor * sampleColor;
            neighbourhoodMinimum = min(neighbourhoodMinimum, sampleColor);
            neighbourhoodMaximum = max(neighbourhoodMaximum, sampleColor);
        }
    }

    float3 mean = firstMoment / 9.0;
    float3 variance = max(secondMoment / 9.0 - mean * mean, 0.0);
    float3 standardDeviation = sqrt(variance);
    float3 varianceMinimum = max(mean - standardDeviation, neighbourhoodMinimum);
    float3 varianceMaximum = min(mean + standardDeviation, neighbourhoodMaximum);

    float3 currentYCoCg = TSCMAARGBToYCoCg(currentColor);
    float3 historyYCoCg = TSCMAARGBToYCoCg(historyColor);
    float3 clippedHistory = TSCMAAClipHistorySegment(currentYCoCg, historyYCoCg, varianceMinimum, varianceMaximum);
    return TSCMAAYCoCgToRGB(clippedHistory);
}

float3 TSCMAALinearToSRGB(float3 color) {
    color = max(color, 0.0);
    float3 lower = color * 12.92;
    float3 upper = 1.055 * pow(color, 1.0 / 2.4) - 0.055;
    return lerp(lower, upper, step(0.0031308, color));
}

[numthreads(TSCMAA_RESOLVE_NUM_THREADS, 1, 1)]
void TSCMAAResolveCandidatesCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint candidateCount = tscmaaControl.Load(TSCMAA_PROCESS_COUNT_OFFSET);
    if (dispatchThreadID.x >= candidateCount)
        return;

    uint packedPixel = tscmaaCandidates[dispatchThreadID.x];
    int2 pixel = int2(packedPixel >> 16, packedPixel & 0xffff);
    int2 dimensions = int2(g_SMAAReprojection.TemporalResolution.xy);
    float2 inverseDimensions = g_SMAAReprojection.TemporalResolution.zw;

    float4 currentColor = tscmaaCurrentColor.Load(int3(pixel, 0));
    float2 currentUV = (float2(pixel) + 0.5) * inverseDimensions;
    float2 historyUV = currentUV;
    [branch]
    if (g_SMAAReprojection.TSCMAAParams.z > 0.5)
        historyUV -= velocityTex.Load(int3(pixel, 0)).xy;

    if (any(historyUV <= 0.0) || any(historyUV >= 1.0))
        return;

    float4 historyColor;
    [branch]
    if (g_SMAAReprojection.TSCMAAResolveParams.x > 0.5)
        historyColor = TSCMAASampleHistoryCatmullRom5Tap(historyUV, float2(dimensions));
    else
        historyColor = tscmaaHistoryColor.SampleLevel(LinearSampler, historyUV, 0.0);

    [branch]
    if (g_SMAAReprojection.TSCMAAResolveParams.y > 0.5)
        historyColor.rgb = TSCMAAVarianceClip(pixel, dimensions, currentColor.rgb, historyColor.rgb);

    float historyWeight = g_SMAAReprojection.TSCMAAParams.x;
    float4 resolvedColor = float4(lerp(currentColor.rgb, historyColor.rgb, historyWeight), currentColor.a);
    if (g_SMAAReprojection.TSCMAAParams.w > 0.5)
        resolvedColor.rgb = TSCMAALinearToSRGB(resolvedColor.rgb);

    tscmaaOutput[pixel] = resolvedColor;
}

#endif // SMAA_TSCMAA_COMPUTE

void DX10_SMAASeparatePS(float4 position : SV_POSITION,
                         float2 texcoord : TEXCOORD0,
                         out float4 target0 : SV_TARGET0,
                         out float4 target1 : SV_TARGET1) {
    SMAASeparatePS(position, texcoord, target0, target1, colorTexMS);
}

#endif // #ifndef INCLUDED_FROM_CPP

#endif // #ifndef SMAA_WRAPPER__HLSL
