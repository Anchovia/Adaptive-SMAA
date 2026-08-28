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
    // x: candidate edge source enum
    // (0 legacy luma re-detection, 1 SMAA first-pass edge reuse),
    // y: write full-resolution base/candidate diagnostic masks,
    // z: collect the optional base-edge statistics counter.
    float4 TSCMAACandidateSourceParams;
    // xy: current projection jitter in pixel units,
    // z: non-candidate base enum (0 current spatial, 1 de-jittered spatial),
    // w: candidate expansion enum (0 none, 1 current-edge 3x3 dilation,
    // 2 filtered quarter-resolution downsample/upsample,
    // 3 ARM Dual Filtering research adaptation).
    float4 TSCMAAHybridParams;
#else
    VertexAsylum::vaMatrix4x4 CurrentViewProjInv;
    VertexAsylum::vaMatrix4x4 CurrentUnjitteredViewProj;
    VertexAsylum::vaMatrix4x4 PreviousViewProj;
    VertexAsylum::vaVector4 TemporalResolution;
    // Matches the shader-side field description above.
    VertexAsylum::vaVector4 TSCMAAParams;
    VertexAsylum::vaVector4 TSCMAACandidateParams;
    VertexAsylum::vaVector4 TSCMAAResolveParams;
    VertexAsylum::vaVector4 TSCMAACandidateSourceParams;
    VertexAsylum::vaVector4 TSCMAAHybridParams;
#endif
};

// Per-draw rigid-object velocity matrices. These deliberately live outside
// the existing SMAA temporal settings so the object-motion experiment can be
// enabled without changing the meaning of the established camera-only modes.
struct SMAAObjectVelocityConstants
{
#ifndef INCLUDED_FROM_CPP
    float4x4 CurrentObjectToJitteredClip;
    float4x4 CurrentObjectToUnjitteredClip;
    float4x4 PreviousObjectToClip;
#else
    VertexAsylum::vaMatrix4x4 CurrentObjectToJitteredClip;
    VertexAsylum::vaMatrix4x4 CurrentObjectToUnjitteredClip;
    VertexAsylum::vaMatrix4x4 PreviousObjectToClip;
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

cbuffer SMAAObjectVelocityGlobals : register( b3 )
{
    SMAAObjectVelocityConstants g_SMAAObjectVelocity;
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
 Texture2D                          metaTex                             : register( t16 );

#define TSCMAA_CANDIDATE_COUNTER_OFFSET       0
#define TSCMAA_PROCESS_COUNT_OFFSET           4
#define TSCMAA_EDGE_COUNTER_OFFSET            8
#define TSCMAA_DISPATCH_GROUP_COUNT_OFFSET    12
#define TSCMAA_RESOLVE_NUM_THREADS            64

#if defined(SMAA_INTEGRATED_TEMPORAL_CANDIDATES)
// Research-only first-pass outputs. UAV slots start at u2 so the same shader
// remains valid for Original SMAA (one edge RTV) and Adaptive SMAA (edge +
// metadata RTVs). The ordinary SMAA shaders never compile this declaration.
RWStructuredBuffer<uint>             tscmaaIntegratedCandidates        : register( u2 );
RWByteAddressBuffer                  tscmaaIntegratedControl           : register( u3 );
RWTexture2D<float>                   tscmaaIntegratedBaseEdgeMask      : register( u4 );
RWTexture2D<float>                   tscmaaIntegratedCandidateMask     : register( u5 );
RWTexture2D<float>                   tscmaaIntegratedRawCandidateMask  : register( u7 );

float TSCMAAIntegratedSampleLuma(float2 texcoord) {
    float4 sampleValue = SMAASamplePoint(colorTexGamma, texcoord);
    #if defined(SMAA_INTEGRATED_RAW_LUMA)
    return sampleValue.r;
    #else
    return dot(sampleValue.rgb, float3(0.2126, 0.7152, 0.0722));
    #endif
}

float TSCMAAIntegratedLoadLuma(int2 pixel, int2 dimensions) {
    pixel = clamp(pixel, int2(0, 0), dimensions - 1);
    float4 sampleValue = colorTexGamma.Load(int3(pixel, 0));
    #if defined(SMAA_INTEGRATED_RAW_LUMA)
    return sampleValue.r;
    #else
    return dot(sampleValue.rgb, float3(0.2126, 0.7152, 0.0722));
    #endif
}

// Intel's public TSCMAA material exposes the non-dominant-removal parameter,
// but not the lost sample's exact candidate equation. This SMAA adaptation
// relocates the already-established Intel-family ablation into the SMAA edge
// pass and reuses the luma values needed by that pass. It must not be described
// as Intel's original candidate shader.
bool TSCMAAIntegratedSelectCandidate(
    uint2 pixel) {
    uint policy = (uint)(g_SMAAReprojection.TSCMAACandidateParams.y + 0.5);
    if (policy == 0)
        return true;
    if (policy != 1)
        return false;

    uint width;
    uint height;
    colorTexGamma.GetDimensions(width, height);
    int2 dimensions = int2(width, height);
    int2 centerPixel = int2(pixel);

    #define TSCMAA_INTEGRATED_LOAD_LUMA(P) TSCMAAIntegratedLoadLuma(P, dimensions)
    float L = TSCMAA_INTEGRATED_LOAD_LUMA(centerPixel);
    float Lleft = TSCMAA_INTEGRATED_LOAD_LUMA(centerPixel + int2(-1, 0));
    float Ltop = TSCMAA_INTEGRATED_LOAD_LUMA(centerPixel + int2(0, -1));
    float Lright = TSCMAA_INTEGRATED_LOAD_LUMA(centerPixel + int2(1, 0));
    float Lbottom = TSCMAA_INTEGRATED_LOAD_LUMA(centerPixel + int2(0, 1));
    float LtopLeft = TSCMAA_INTEGRATED_LOAD_LUMA(centerPixel + int2(-1, -1));
    float LbottomLeft = TSCMAA_INTEGRATED_LOAD_LUMA(centerPixel + int2(-1, 1));
    float LtopRight = TSCMAA_INTEGRATED_LOAD_LUMA(centerPixel + int2(1, -1));
    #undef TSCMAA_INTEGRATED_LOAD_LUMA

    float2 directionalDelta = abs(L - float2(Lleft, Ltop));
    float2 rightBottomDelta = abs(L - float2(Lright, Lbottom));

    float maximumPerpendicularForVertical = max(
        max(directionalDelta.y, abs(Lleft - LtopLeft)),
        max(rightBottomDelta.y, abs(LbottomLeft - Lleft)));
    float maximumPerpendicularForHorizontal = max(
        max(directionalDelta.x, abs(Ltop - LtopLeft)),
        max(rightBottomDelta.x, abs(LtopRight - Ltop)));

    float removalAmount = g_SMAAReprojection.TSCMAAParams.y;
    float threshold = g_SMAAReprojection.TSCMAACandidateParams.x;
    bool verticalDominant = directionalDelta.x
        - maximumPerpendicularForVertical * removalAmount > threshold;
    bool horizontalDominant = directionalDelta.y
        - maximumPerpendicularForHorizontal * removalAmount > threshold;
    return verticalDominant || horizontalDominant;
}

SMAA_EDGE_OUTPUT DX10_SMAALumaEdgeDetectionIntegratedTemporalCandidatesPS(
    float4 position : SV_POSITION,
    float2 texcoord : TEXCOORD0,
    float4 offset[3] : TEXCOORD1) SMAA_EDGE_OUTPUT_SEMANTIC {
    #if SMAA_PREDICATION
    float2 threshold = SMAACalculatePredicatedThreshold(
        texcoord, offset, SMAATexturePass2D(depthTex));
    #else
    float2 threshold = float2(SMAA_THRESHOLD, SMAA_THRESHOLD);
    #endif

    float L = TSCMAAIntegratedSampleLuma(texcoord);
    float Lleft = TSCMAAIntegratedSampleLuma(offset[0].xy);
    float Ltop = TSCMAAIntegratedSampleLuma(offset[0].zw);

    float4 delta;
    delta.xy = abs(L - float2(Lleft, Ltop));
    float2 edges = step(threshold, delta.xy);
    if (dot(edges, float2(1.0, 1.0)) == 0.0)
        discard;

    float Lright = TSCMAAIntegratedSampleLuma(offset[1].xy);
    float Lbottom = TSCMAAIntegratedSampleLuma(offset[1].zw);
    delta.zw = abs(L - float2(Lright, Lbottom));
    float2 maxDelta = max(delta.xy, delta.zw);

    float Lleftleft = TSCMAAIntegratedSampleLuma(offset[2].xy);
    float Ltoptop = TSCMAAIntegratedSampleLuma(offset[2].zw);
    delta.zw = abs(float2(Lleft, Ltop) - float2(Lleftleft, Ltoptop));
    maxDelta = max(maxDelta.xy, delta.zw);
    float finalDelta = max(maxDelta.x, maxDelta.y);
    edges.xy *= step(finalDelta,
        SMAA_LOCAL_CONTRAST_ADAPTATION_FACTOR * delta.xy);

    uint2 pixel = uint2(position.xy);
    bool baseEdge = any(edges > 0.0);
    bool candidate = baseEdge && TSCMAAIntegratedSelectCandidate(pixel);
    bool writeDiagnosticMasks =
        g_SMAAReprojection.TSCMAACandidateSourceParams.y > 0.5;
    if (writeDiagnosticMasks)
        tscmaaIntegratedBaseEdgeMask[pixel] = baseEdge ? 1.0 : 0.0;

    bool collectBaseEdgeStatistics =
        g_SMAAReprojection.TSCMAACandidateSourceParams.z > 0.5;
    if (baseEdge && collectBaseEdgeStatistics) {
        uint ignoredEdgeIndex;
        tscmaaIntegratedControl.InterlockedAdd(
            TSCMAA_EDGE_COUNTER_OFFSET, 1, ignoredEdgeIndex);
    }

    bool expansionEnabled = g_SMAAReprojection.TSCMAAHybridParams.w > 0.5;
    if (expansionEnabled) {
        tscmaaIntegratedRawCandidateMask[pixel] = candidate ? 1.0 : 0.0;
    } else {
        if (writeDiagnosticMasks)
            tscmaaIntegratedCandidateMask[pixel] = candidate ? 1.0 : 0.0;
        if (candidate) {
            uint candidateIndex;
            tscmaaIntegratedControl.InterlockedAdd(
                TSCMAA_CANDIDATE_COUNTER_OFFSET, 1, candidateIndex);
            uint candidateCapacity;
            uint candidateStride;
            tscmaaIntegratedCandidates.GetDimensions(
                candidateCapacity, candidateStride);
            if (candidateIndex < candidateCapacity)
                tscmaaIntegratedCandidates[candidateIndex] =
                    (pixel.x << 16) | pixel.y;
        }
    }

    return SMAAEncodeEdgeOutput(edges, finalDelta);
}
#endif

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

SMAA_EDGE_OUTPUT DX10_SMAALumaRawEdgeDetectionPS(float4 position : SV_POSITION,
                                    float2 texcoord : TEXCOORD0,
                                    float4 offset[3] : TEXCOORD1) SMAA_EDGE_OUTPUT_SEMANTIC {
    #if SMAA_PREDICATION
    return SMAALumaRawEdgeDetectionPS(texcoord, offset, colorTexGamma, depthTex);
    #else
    return SMAALumaRawEdgeDetectionPS(texcoord, offset, colorTexGamma);
    #endif
}

SMAA_EDGE_OUTPUT DX10_SMAALumaEdgeDetectionPS(float4 position : SV_POSITION,
                                    float2 texcoord : TEXCOORD0,
                                    float4 offset[3] : TEXCOORD1) SMAA_EDGE_OUTPUT_SEMANTIC {
    #if SMAA_PREDICATION
    return SMAALumaEdgeDetectionPS(texcoord, offset, colorTexGamma, depthTex);
    #else
    return SMAALumaEdgeDetectionPS(texcoord, offset, colorTexGamma);
    #endif
}

SMAA_EDGE_OUTPUT DX10_SMAAColorEdgeDetectionPS(float4 position : SV_POSITION,
                                     float2 texcoord : TEXCOORD0,
                                     float4 offset[3] : TEXCOORD1) SMAA_EDGE_OUTPUT_SEMANTIC {
    #if SMAA_PREDICATION
    return SMAAColorEdgeDetectionPS(texcoord, offset, colorTexGamma, depthTex);
    #else
    return SMAAColorEdgeDetectionPS(texcoord, offset, colorTexGamma);
    #endif
}

SMAA_EDGE_OUTPUT DX10_SMAADepthEdgeDetectionPS(float4 position : SV_POSITION,
                                     float2 texcoord : TEXCOORD0,
                                     float4 offset[3] : TEXCOORD1) SMAA_EDGE_OUTPUT_SEMANTIC {
    return SMAADepthEdgeDetectionPS(texcoord, offset, depthTex);
}

float4 DX10_SMAABlendingWeightCalculationPS(float4 position : SV_POSITION,
                                            float2 texcoord : TEXCOORD0,
                                            float2 pixcoord : TEXCOORD1,
                                            float4 offset[3] : TEXCOORD2) : SV_TARGET {
    return SMAABlendingWeightCalculationPS(texcoord, pixcoord, offset, edgesTex,
        #if defined(SMAA_ADAPTIVE_SEARCH)
        metaTex,
        #endif
        areaTex, searchTex, g_SMAA.subsampleIndices);
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

struct SMAAObjectVelocityVertexInput
{
    float3 Position : SV_Position;
    float4 Color : COLOR;
    float4 Normal : NORMAL;
    float2 Texcoord0 : TEXCOORD0;
    float2 Texcoord1 : TEXCOORD1;
};

struct SMAAObjectVelocityVertexOutput
{
    float4 Position : SV_Position;
    float4 CurrentUnjitteredClip : TEXCOORD0;
    float4 PreviousClip : TEXCOORD1;
};

SMAAObjectVelocityVertexOutput DX10_SMAAGenerateRigidObjectVelocityVS(
    const in SMAAObjectVelocityVertexInput input)
{
    SMAAObjectVelocityVertexOutput output;
    const float4 localPosition = float4(input.Position, 1.0);
    output.Position = mul(g_SMAAObjectVelocity.CurrentObjectToJitteredClip, localPosition);
    output.CurrentUnjitteredClip = mul(g_SMAAObjectVelocity.CurrentObjectToUnjitteredClip, localPosition);
    output.PreviousClip = mul(g_SMAAObjectVelocity.PreviousObjectToClip, localPosition);
    return output;
}

float2 DX10_SMAAGenerateRigidObjectVelocityPS(
    const in SMAAObjectVelocityVertexOutput input) : SV_TARGET
{
    const int2 pixel = int2(input.Position.xy);
    const float sceneDepth = depthTex.Load(int3(pixel, 0)).r;
    // The current scene depth already contains alpha-tested coverage. Reject
    // occluded triangles and material holes without needing to reproduce every
    // material shader in this rigid-transform-only pass.
    if(abs(input.Position.z - sceneDepth) > 1.0e-5)
        discard;

    // A point behind either camera cannot provide a valid previous sample.
    // Emit an out-of-bounds displacement so the temporal resolve rejects it.
    if(input.CurrentUnjitteredClip.w <= 1.0e-6 || input.PreviousClip.w <= 1.0e-6)
        return float2(2.0, 2.0);

    const float2 currentNDC = input.CurrentUnjitteredClip.xy / input.CurrentUnjitteredClip.w;
    const float2 previousNDC = input.PreviousClip.xy / input.PreviousClip.w;
    const float2 currentUV = float2(currentNDC.x * 0.5 + 0.5, 0.5 - currentNDC.y * 0.5);
    const float2 previousUV = float2(previousNDC.x * 0.5 + 0.5, 0.5 - previousNDC.y * 0.5);

    // Match the camera velocity convention consumed by both SMAA resolves:
    // historyUV = currentUV - velocity.
    return currentUV - previousUV;
}

#if !defined(SMAA_TSCMAA_COMPUTE)
Texture2D<float> tscmaaDebugMask : register( t10 );
Texture2D<float4> tscmaaDebugColor : register( t11 );

float4 TSCMAADebugMaskPS(float4 position : SV_POSITION,
                         float2 texcoord : TEXCOORD0) : SV_TARGET {
    float mask = tscmaaDebugMask.Load(int3(int2(position.xy), 0));
    return float4(mask, mask, mask, 1.0);
}

float4 TSCMAADebugColorPS(float4 position : SV_POSITION,
                          float2 texcoord : TEXCOORD0) : SV_TARGET {
    return tscmaaDebugColor.Load(int3(int2(position.xy), 0));
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
Texture2D<float>                     tscmaaRawCandidateMaskInput         : register( t13 );
Texture2D<float>                     tscmaaFilteredQuarterMaskInput      : register( t14 );

RWTexture2D<float4>                  tscmaaOutput                        : register( u0 );
RWStructuredBuffer<uint>             tscmaaCandidates                    : register( u1 );
RWByteAddressBuffer                  tscmaaControl                       : register( u2 );
RWByteAddressBuffer                  tscmaaDispatchArgs                  : register( u3 );
RWTexture2D<float>                   tscmaaBaseEdgeMask                  : register( u4 );
RWTexture2D<float>                   tscmaaCandidateMask                 : register( u5 );
RWTexture2D<float4>                  tscmaaClippingDebug                  : register( u6 );
// The u7 intermediate is rebound between passes: full-resolution raw mask
// during extraction and quarter-resolution filtered mask during downsample.
RWTexture2D<float>                   tscmaaExpansionIntermediate          : register( u7 );

int2 TSCMAAClampPixel(int2 pixel, int2 dimensions) {
    return clamp(pixel, int2(0, 0), dimensions - 1);
}

float2 TSCMAALegacyLumaEdgeStrength(int2 pixel, int2 dimensions) {
    pixel = TSCMAAClampPixel(pixel, dimensions);
    float center = tscmaaLuma.Load(int3(pixel, 0));
    float left = tscmaaLuma.Load(int3(TSCMAAClampPixel(pixel + int2(-1, 0), dimensions), 0));
    float top = tscmaaLuma.Load(int3(TSCMAAClampPixel(pixel + int2(0, -1), dimensions), 0));
    return float2(abs(center - left), abs(center - top));
}

float2 TSCMAAFirstPassEdgeDirections(int2 pixel, int2 dimensions) {
    pixel = TSCMAAClampPixel(pixel, dimensions);
    return edgesTex.Load(int3(pixel, 0)).rg;
}

bool TSCMAAUsesFirstPassEdges() {
    return g_SMAAReprojection.TSCMAACandidateSourceParams.x > 0.5;
}

bool TSCMAAIsLegacyBaseEdge(float2 directionalStrength) {
    return any(directionalStrength > g_SMAAReprojection.TSCMAACandidateParams.x);
}

// The first-pass source changes only how the base mask is obtained. For the
// Intel-family policy, luma strengths are still evaluated at surviving SMAA
// edge pixels so its existing contrast ranking remains comparable. AllBase
// needs no luma reads in the first-pass source path.
void TSCMAAGetBaseEdgeAndStrength(
    int2 pixel, int2 dimensions, uint policy,
    out bool baseEdge, out float2 directionalStrength) {
    baseEdge = false;
    directionalStrength = float2(0.0, 0.0);
    if (TSCMAAUsesFirstPassEdges()) {
        baseEdge = any(TSCMAAFirstPassEdgeDirections(pixel, dimensions) > 0.0);
        if (baseEdge && policy == 1)
            directionalStrength = TSCMAALegacyLumaEdgeStrength(pixel, dimensions);
        return;
    }

    directionalStrength = TSCMAALegacyLumaEdgeStrength(pixel, dimensions);
    baseEdge = TSCMAAIsLegacyBaseEdge(directionalStrength);
}

// Adaptation of the local-contrast structure in Intel's public CMAA2 shader:
// each edge competes with connected perpendicular edges. The public TSCMAA
// document supplies the 1/22 threshold and 0.5 removal defaults, but not the
// lost sample's exact candidate-selection shader.
bool TSCMAAIsIntelFamilyNonDominantCandidate(int2 pixel, int2 dimensions, float2 directionalStrength) {
    float maximumPerpendicularForVertical = 0.0;
    maximumPerpendicularForVertical = max(maximumPerpendicularForVertical, TSCMAALegacyLumaEdgeStrength(pixel, dimensions).y);
    maximumPerpendicularForVertical = max(maximumPerpendicularForVertical, TSCMAALegacyLumaEdgeStrength(pixel + int2(-1, 0), dimensions).y);
    maximumPerpendicularForVertical = max(maximumPerpendicularForVertical, TSCMAALegacyLumaEdgeStrength(pixel + int2(0, 1), dimensions).y);
    maximumPerpendicularForVertical = max(maximumPerpendicularForVertical, TSCMAALegacyLumaEdgeStrength(pixel + int2(-1, 1), dimensions).y);

    float maximumPerpendicularForHorizontal = 0.0;
    maximumPerpendicularForHorizontal = max(maximumPerpendicularForHorizontal, TSCMAALegacyLumaEdgeStrength(pixel, dimensions).x);
    maximumPerpendicularForHorizontal = max(maximumPerpendicularForHorizontal, TSCMAALegacyLumaEdgeStrength(pixel + int2(0, -1), dimensions).x);
    maximumPerpendicularForHorizontal = max(maximumPerpendicularForHorizontal, TSCMAALegacyLumaEdgeStrength(pixel + int2(1, 0), dimensions).x);
    maximumPerpendicularForHorizontal = max(maximumPerpendicularForHorizontal, TSCMAALegacyLumaEdgeStrength(pixel + int2(1, -1), dimensions).x);

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

bool TSCMAAIsCandidateAtPixel(
    int2 pixel, int2 dimensions, uint policy, bool baseEdge,
    float2 directionalStrength) {
    if (policy == 0)
        return baseEdge;
    if (policy == 1)
        return baseEdge && TSCMAAIsIntelFamilyNonDominantCandidate(
            pixel, dimensions, directionalStrength);
    float experimentalStrength =
        TSCMAAExperimentalEdgeStrength(pixel, dimensions);
    return baseEdge && TSCMAAIsExperimentalLocallyDominantCandidate(
        pixel, dimensions, experimentalStrength);
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
    bool forcedCountDiagnostics = g_SMAAReprojection.TSCMAACandidateParams.w > 0.5;
    uint linearPixelIndex = dispatchThreadID.y * width + dispatchThreadID.x;
    uint forcedCandidateCount = min((uint)(g_SMAAReprojection.TSCMAACandidateParams.z + 0.5), width * height);
    uint policy = (uint)(g_SMAAReprojection.TSCMAACandidateParams.y + 0.5);
    bool baseEdge = false;
    float2 directionalStrength = float2(0.0, 0.0);
    TSCMAAGetBaseEdgeAndStrength(
        pixel, dimensions, policy, baseEdge, directionalStrength);
    if (forcedCountDiagnostics)
        baseEdge = linearPixelIndex < forcedCandidateCount;
    tscmaaBaseEdgeMask[pixel] = baseEdge ? 1.0 : 0.0;

    if (baseEdge) {
        uint ignoredEdgeIndex;
        tscmaaControl.InterlockedAdd(TSCMAA_EDGE_COUNTER_OFFSET, 1, ignoredEdgeIndex);
    }

    // Keep exact-count diagnostics independent of candidate expansion so the
    // established 0/1/63/64/65/full-capacity boundary test remains exact.
    bool candidate = forcedCountDiagnostics?
        baseEdge : TSCMAAIsCandidateAtPixel(
            pixel, dimensions, policy, baseEdge, directionalStrength);

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

// First half of the 3x3 expansion path. Candidate policy evaluation remains
// one per pixel; the following pass dilates this raw mask with cheap R8 loads.
[numthreads(8, 8, 1)]
void TSCMAAExtractRawCandidatesCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint width;
    uint height;
    tscmaaLuma.GetDimensions(width, height);
    if (dispatchThreadID.x >= width || dispatchThreadID.y >= height)
        return;

    int2 pixel = int2(dispatchThreadID.xy);
    int2 dimensions = int2(width, height);
    uint policy = (uint)(g_SMAAReprojection.TSCMAACandidateParams.y + 0.5);
    bool baseEdge = false;
    float2 directionalStrength = float2(0.0, 0.0);
    TSCMAAGetBaseEdgeAndStrength(
        pixel, dimensions, policy, baseEdge, directionalStrength);
    tscmaaBaseEdgeMask[pixel] = baseEdge ? 1.0 : 0.0;
    if (baseEdge) {
        uint ignoredEdgeIndex;
        tscmaaControl.InterlockedAdd(
            TSCMAA_EDGE_COUNTER_OFFSET, 1, ignoredEdgeIndex);
    }

    bool rawCandidate = TSCMAAIsCandidateAtPixel(
        pixel, dimensions, policy, baseEdge, directionalStrength);
    tscmaaExpansionIntermediate[pixel] = rawCandidate ? 1.0 : 0.0;
}

// Current-edge 3x3 dilation. This is an SMAA research ablation, not a
// recovered Intel TSCMAA source formula.
[numthreads(8, 8, 1)]
void TSCMAADilateCandidates3x3CS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint width;
    uint height;
    tscmaaRawCandidateMaskInput.GetDimensions(width, height);
    if (dispatchThreadID.x >= width || dispatchThreadID.y >= height)
        return;

    int2 pixel = int2(dispatchThreadID.xy);
    int2 dimensions = int2(width, height);
    bool candidate = false;
    [unroll]
    for (int y = -1; y <= 1; y++) {
        [unroll]
        for (int x = -1; x <= 1; x++) {
            candidate = candidate ||
                tscmaaRawCandidateMaskInput.Load(int3(
                    TSCMAAClampPixel(pixel + int2(x, y), dimensions), 0)) > 0.5;
        }
    }

    tscmaaCandidateMask[pixel] = candidate ? 1.0 : 0.0;
    if (!candidate)
        return;

    uint candidateIndex;
    tscmaaControl.InterlockedAdd(
        TSCMAA_CANDIDATE_COUNTER_OFFSET, 1, candidateIndex);
    uint candidateCapacity;
    uint candidateStride;
    tscmaaCandidates.GetDimensions(candidateCapacity, candidateStride);
    if (candidateIndex < candidateCapacity)
        tscmaaCandidates[candidateIndex] =
            (dispatchThreadID.x << 16) | dispatchThreadID.y;
}

// Filtered-quarter expansion pass 1. Each quarter-resolution texel stores the
// exact mean of its corresponding valid 4x4 raw-candidate block. This explicit
// box filter is the documented GPU counterpart of the earlier area-downsample
// proxy and keeps non-multiple-of-four borders deterministic.
[numthreads(8, 8, 1)]
void TSCMAADownsampleCandidatesQuarterCS(
    uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint sourceWidth;
    uint sourceHeight;
    tscmaaRawCandidateMaskInput.GetDimensions(sourceWidth, sourceHeight);
    uint outputWidth;
    uint outputHeight;
    tscmaaExpansionIntermediate.GetDimensions(outputWidth, outputHeight);
    if (dispatchThreadID.x >= outputWidth || dispatchThreadID.y >= outputHeight)
        return;

    uint2 blockStart = dispatchThreadID.xy * 4;
    uint2 blockEnd = min(blockStart + 4, uint2(sourceWidth, sourceHeight));
    float sum = 0.0;
    uint count = 0;
    [unroll]
    for (uint y = 0; y < 4; y++) {
        [unroll]
        for (uint x = 0; x < 4; x++) {
            uint2 sourcePixel = blockStart + uint2(x, y);
            if (sourcePixel.x < blockEnd.x && sourcePixel.y < blockEnd.y) {
                sum += tscmaaRawCandidateMaskInput.Load(
                    int3(sourcePixel, 0));
                count++;
            }
        }
    }
    tscmaaExpansionIntermediate[dispatchThreadID.xy] =
        count > 0 ? sum / (float)count : 0.0;
}

// Filtered-quarter expansion pass 2. Manual bilinear interpolation makes the
// non-nearest reconstruction rule explicit and CPU-reference reproducible.
// Pixels at or above the offline proxy threshold (0.25) are unioned with the
// raw mask and compacted. Candidate expansion must never erase an original
// current-edge candidate.
[numthreads(8, 8, 1)]
void TSCMAAUpsampleCandidatesQuarterCS(
    uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint width;
    uint height;
    tscmaaCandidateMask.GetDimensions(width, height);
    if (dispatchThreadID.x >= width || dispatchThreadID.y >= height)
        return;

    uint quarterWidth;
    uint quarterHeight;
    tscmaaFilteredQuarterMaskInput.GetDimensions(quarterWidth, quarterHeight);
    float2 sourcePosition =
        (float2(dispatchThreadID.xy) + 0.5) *
        (float2(quarterWidth, quarterHeight) / float2(width, height)) - 0.5;
    int2 basePixel = int2(floor(sourcePosition));
    float2 fraction = frac(sourcePosition);
    int2 maximumPixel = int2(quarterWidth, quarterHeight) - 1;
    int2 p00 = clamp(basePixel, int2(0, 0), maximumPixel);
    int2 p10 = clamp(basePixel + int2(1, 0), int2(0, 0), maximumPixel);
    int2 p01 = clamp(basePixel + int2(0, 1), int2(0, 0), maximumPixel);
    int2 p11 = clamp(basePixel + int2(1, 1), int2(0, 0), maximumPixel);
    float top = lerp(
        tscmaaFilteredQuarterMaskInput.Load(int3(p00, 0)),
        tscmaaFilteredQuarterMaskInput.Load(int3(p10, 0)), fraction.x);
    float bottom = lerp(
        tscmaaFilteredQuarterMaskInput.Load(int3(p01, 0)),
        tscmaaFilteredQuarterMaskInput.Load(int3(p11, 0)), fraction.x);
    bool rawCandidate =
        tscmaaRawCandidateMaskInput.Load(int3(dispatchThreadID.xy, 0)) > 0.5;
    bool candidate = rawCandidate || lerp(top, bottom, fraction.y) >= 0.25;

    tscmaaCandidateMask[dispatchThreadID.xy] = candidate ? 1.0 : 0.0;
    if (!candidate)
        return;

    uint candidateIndex;
    tscmaaControl.InterlockedAdd(
        TSCMAA_CANDIDATE_COUNTER_OFFSET, 1, candidateIndex);
    uint candidateCapacity;
    uint candidateStride;
    tscmaaCandidates.GetDimensions(candidateCapacity, candidateStride);
    if (candidateIndex < candidateCapacity)
        tscmaaCandidates[candidateIndex] =
            (dispatchThreadID.x << 16) | dispatchThreadID.y;
}

// ARM SIGGRAPH 2015 Dual Filtering research adaptation. The official filter
// supplies the weights and relative offsets; the two-level candidate-mask
// pyramid, half-input-texel convention, R8 intermediates, and 0.25 threshold
// are controlled SMAA adaptation choices documented in
// Docs/SMAA-ARM-Dual-Filter-Candidate-Expansion-Protocol-ko.md.
float TSCMAAArmDualDownsample(float2 uv, float2 halfPixel) {
    float sum = tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv, 0.0) * 4.0;
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(-halfPixel.x, -halfPixel.y), 0.0);
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2( halfPixel.x,  halfPixel.y), 0.0);
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2( halfPixel.x, -halfPixel.y), 0.0);
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(-halfPixel.x,  halfPixel.y), 0.0);
    return sum / 8.0;
}

float TSCMAAArmDualUpsample(float2 uv, float2 halfPixel) {
    float sum = tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(-halfPixel.x * 2.0, 0.0), 0.0);
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(-halfPixel.x, halfPixel.y), 0.0) * 2.0;
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(0.0, halfPixel.y * 2.0), 0.0);
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(halfPixel.x, halfPixel.y), 0.0) * 2.0;
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(halfPixel.x * 2.0, 0.0), 0.0);
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(halfPixel.x, -halfPixel.y), 0.0) * 2.0;
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(0.0, -halfPixel.y * 2.0), 0.0);
    sum += tscmaaRawCandidateMaskInput.SampleLevel(
        LinearSampler, uv + float2(-halfPixel.x, -halfPixel.y), 0.0) * 2.0;
    return sum / 12.0;
}

float2 TSCMAAArmDualSampleParameters(
    uint2 outputPixel, uint2 outputDimensions, uint2 inputDimensions,
    out float2 halfPixel) {
    halfPixel = 0.5 / float2(inputDimensions);
    return (float2(outputPixel) + 0.5) / float2(outputDimensions);
}

[numthreads(8, 8, 1)]
void TSCMAAArmDualDownsampleCS(
    uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint inputWidth;
    uint inputHeight;
    tscmaaRawCandidateMaskInput.GetDimensions(inputWidth, inputHeight);
    uint outputWidth;
    uint outputHeight;
    tscmaaExpansionIntermediate.GetDimensions(outputWidth, outputHeight);
    if (dispatchThreadID.x >= outputWidth || dispatchThreadID.y >= outputHeight)
        return;

    float2 halfPixel;
    float2 uv = TSCMAAArmDualSampleParameters(
        dispatchThreadID.xy, uint2(outputWidth, outputHeight),
        uint2(inputWidth, inputHeight), halfPixel);
    tscmaaExpansionIntermediate[dispatchThreadID.xy] =
        TSCMAAArmDualDownsample(uv, halfPixel);
}

[numthreads(8, 8, 1)]
void TSCMAAArmDualUpsampleCS(
    uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint inputWidth;
    uint inputHeight;
    tscmaaRawCandidateMaskInput.GetDimensions(inputWidth, inputHeight);
    uint outputWidth;
    uint outputHeight;
    tscmaaExpansionIntermediate.GetDimensions(outputWidth, outputHeight);
    if (dispatchThreadID.x >= outputWidth || dispatchThreadID.y >= outputHeight)
        return;

    float2 halfPixel;
    float2 uv = TSCMAAArmDualSampleParameters(
        dispatchThreadID.xy, uint2(outputWidth, outputHeight),
        uint2(inputWidth, inputHeight), halfPixel);
    tscmaaExpansionIntermediate[dispatchThreadID.xy] =
        TSCMAAArmDualUpsample(uv, halfPixel);
}

[numthreads(8, 8, 1)]
void TSCMAAArmDualUpsampleAndCompactRawUnionCS(
    uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint width;
    uint height;
    tscmaaCandidateMask.GetDimensions(width, height);
    if (dispatchThreadID.x >= width || dispatchThreadID.y >= height)
        return;

    uint inputWidth;
    uint inputHeight;
    tscmaaRawCandidateMaskInput.GetDimensions(inputWidth, inputHeight);
    float2 halfPixel;
    float2 uv = TSCMAAArmDualSampleParameters(
        dispatchThreadID.xy, uint2(width, height),
        uint2(inputWidth, inputHeight), halfPixel);
    // Candidate expansion must never erase an original current-edge
    // candidate. The reconstruction only contributes additional coverage.
    bool rawCandidate =
        tscmaaFilteredQuarterMaskInput.Load(int3(dispatchThreadID.xy, 0)) > 0.5;
    bool candidate = rawCandidate
        || TSCMAAArmDualUpsample(uv, halfPixel) >= 0.25;
    tscmaaCandidateMask[dispatchThreadID.xy] = candidate ? 1.0 : 0.0;
    if (!candidate)
        return;

    uint candidateIndex;
    tscmaaControl.InterlockedAdd(
        TSCMAA_CANDIDATE_COUNTER_OFFSET, 1, candidateIndex);
    uint candidateCapacity;
    uint candidateStride;
    tscmaaCandidates.GetDimensions(candidateCapacity, candidateStride);
    if (candidateIndex < candidateCapacity)
        tscmaaCandidates[candidateIndex] =
            (dispatchThreadID.x << 16) | dispatchThreadID.y;
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

[numthreads(8, 8, 1)]
void TSCMAAVarianceDiagnosticCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint width;
    uint height;
    tscmaaCurrentColor.GetDimensions(width, height);
    if (dispatchThreadID.x >= width || dispatchThreadID.y >= height)
        return;

    int2 pixel = int2(dispatchThreadID.xy);
    float3 currentColor = tscmaaCurrentColor.Load(int3(pixel, 0)).rgb;
    float3 historyColor = tscmaaHistoryColor.Load(int3(pixel, 0)).rgb;
    tscmaaOutput[pixel] = float4(
        TSCMAAVarianceClip(pixel, int2(width, height), currentColor, historyColor), 1.0);
}

float3 TSCMAALinearToSRGB(float3 color) {
    color = max(color, 0.0);
    float3 lower = color * 12.92;
    float3 upper = 1.055 * pow(color, 1.0 / 2.4) - 0.055;
    return lerp(lower, upper, step(0.0031308, color));
}

[numthreads(8, 8, 1)]
void TSCMAADeJitterSpatialCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint width;
    uint height;
    tscmaaCurrentColor.GetDimensions(width, height);
    if (dispatchThreadID.x >= width || dispatchThreadID.y >= height)
        return;

    float2 inverseDimensions = 1.0 / float2(width, height);
    float2 outputUV = (float2(dispatchThreadID.xy) + 0.5) * inverseDimensions;

    // vaCameraBase shifts projected geometry by the configured subpixel
    // offset in screen-pixel coordinates. Sampling the jittered image at
    // outputUV + jitter reconstructs the unjittered pixel-center location.
    float2 sourceUV = outputUV
        + g_SMAAReprojection.TSCMAAHybridParams.xy * inverseDimensions;
    float4 spatialColor =
        tscmaaCurrentColor.SampleLevel(LinearSampler, sourceUV, 0.0);
    if (g_SMAAReprojection.TSCMAAParams.w > 0.5)
        spatialColor.rgb = TSCMAALinearToSRGB(spatialColor.rgb);
    tscmaaOutput[dispatchThreadID.xy] = spatialColor;
}

bool TSCMAAResolveTemporalPixel(int2 pixel, int2 dimensions, out float4 resolvedColor) {
    float2 inverseDimensions = g_SMAAReprojection.TemporalResolution.zw;

    float4 currentColor = tscmaaCurrentColor.Load(int3(pixel, 0));
    float2 currentUV = (float2(pixel) + 0.5) * inverseDimensions;
    float2 historyUV = currentUV;
    [branch]
    if (g_SMAAReprojection.TSCMAAParams.z > 0.5)
        historyUV -= velocityTex.Load(int3(pixel, 0)).xy;

    if (any(historyUV <= 0.0) || any(historyUV >= 1.0)) {
        resolvedColor = currentColor;
        return false;
    }

    float4 historyColor;
    [branch]
    if (g_SMAAReprojection.TSCMAAResolveParams.x > 0.5)
        historyColor = TSCMAASampleHistoryCatmullRom5Tap(historyUV, float2(dimensions));
    else
        historyColor = tscmaaHistoryColor.SampleLevel(LinearSampler, historyUV, 0.0);

    float3 historyBeforeClipping = historyColor.rgb;
    [branch]
    if (g_SMAAReprojection.TSCMAAResolveParams.y > 0.5)
        historyColor.rgb = TSCMAAVarianceClip(pixel, dimensions, currentColor.rgb, historyColor.rgb);

    [branch]
    if (g_SMAAReprojection.TSCMAAResolveParams.z > 0.5) {
        if (g_SMAAReprojection.TSCMAAResolveParams.w < 1.5)
            tscmaaClippingDebug[pixel] = float4(historyBeforeClipping, 1.0);
        else if (g_SMAAReprojection.TSCMAAResolveParams.w < 2.5)
            tscmaaClippingDebug[pixel] = float4(historyColor.rgb, 1.0);
        else
            tscmaaClippingDebug[pixel] = float4(
                saturate(abs(historyColor.rgb - historyBeforeClipping) * 8.0), 1.0);
    }

    float historyWeight = g_SMAAReprojection.TSCMAAParams.x;
    resolvedColor = float4(lerp(currentColor.rgb, historyColor.rgb, historyWeight), currentColor.a);
    if (g_SMAAReprojection.TSCMAAParams.w > 0.5)
        resolvedColor.rgb = TSCMAALinearToSRGB(resolvedColor.rgb);

    return true;
}

// Copy the current spatial result into both the next history and the visible
// destination in one pass. u6 is an auxiliary output in this optimized path;
// clipping debug and dual-output execution are intentionally mutually
// exclusive on the C++ side.
[numthreads(8, 8, 1)]
void TSCMAAInitializeDualOutputCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    int2 dimensions = int2(g_SMAAReprojection.TemporalResolution.xy);
    int2 pixel = int2(dispatchThreadID.xy);
    if (any(pixel >= dimensions))
        return;

    // C++ binds a non-sRGB SRV for this entry point, so this load returns the
    // stored UNORM values directly. Writing them to the two UNORM UAVs keeps
    // byte-equivalent spatial initialization without an expensive pow-based
    // linear-to-sRGB round trip.
    float4 spatialColor = tscmaaCurrentColor.Load(int3(pixel, 0));
    tscmaaOutput[pixel] = spatialColor;
    tscmaaClippingDebug[pixel] = spatialColor;
}

[numthreads(TSCMAA_RESOLVE_NUM_THREADS, 1, 1)]
void TSCMAAResolveCandidatesCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint candidateCount = tscmaaControl.Load(TSCMAA_PROCESS_COUNT_OFFSET);
    if (dispatchThreadID.x >= candidateCount)
        return;

    uint packedPixel = tscmaaCandidates[dispatchThreadID.x];
    int2 pixel = int2(packedPixel >> 16, packedPixel & 0xffff);
    int2 dimensions = int2(g_SMAAReprojection.TemporalResolution.xy);
    float4 resolvedColor;
    if (!TSCMAAResolveTemporalPixel(pixel, dimensions, resolvedColor))
        return;

    tscmaaOutput[pixel] = resolvedColor;
}

[numthreads(TSCMAA_RESOLVE_NUM_THREADS, 1, 1)]
void TSCMAAResolveCandidatesDualOutputCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint candidateCount = tscmaaControl.Load(TSCMAA_PROCESS_COUNT_OFFSET);
    if (dispatchThreadID.x >= candidateCount)
        return;

    uint packedPixel = tscmaaCandidates[dispatchThreadID.x];
    int2 pixel = int2(packedPixel >> 16, packedPixel & 0xffff);
    int2 dimensions = int2(g_SMAAReprojection.TemporalResolution.xy);
    float4 resolvedColor;
    if (!TSCMAAResolveTemporalPixel(pixel, dimensions, resolvedColor))
        return;

    tscmaaOutput[pixel] = resolvedColor;
    tscmaaClippingDebug[pixel] = resolvedColor;
}

// Diagnostic matched-kernel control. It deliberately uses the exact same
// per-pixel document-profile resolve helper as the indirect candidate path,
// while changing only coverage/dispatch from selected pixels to full-screen.
[numthreads(8, 8, 1)]
void TSCMAAResolveFullScreenCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    int2 dimensions = int2(g_SMAAReprojection.TemporalResolution.xy);
    int2 pixel = int2(dispatchThreadID.xy);
    if (any(pixel >= dimensions))
        return;

    float4 resolvedColor;
    if (!TSCMAAResolveTemporalPixel(pixel, dimensions, resolvedColor))
        return;
    tscmaaOutput[pixel] = resolvedColor;
}


[numthreads(8, 8, 1)]
void TSCMAAResolveFullScreenDualOutputCS(uint3 dispatchThreadID : SV_DispatchThreadID) {
    int2 dimensions = int2(g_SMAAReprojection.TemporalResolution.xy);
    int2 pixel = int2(dispatchThreadID.xy);
    if (any(pixel >= dimensions))
        return;

    float4 resolvedColor;
    if (!TSCMAAResolveTemporalPixel(pixel, dimensions, resolvedColor))
        return;
    tscmaaOutput[pixel] = resolvedColor;
    tscmaaClippingDebug[pixel] = resolvedColor;
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
