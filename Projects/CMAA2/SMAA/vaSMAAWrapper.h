///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Copyright (c) 2017, Intel Corporation
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all copies or substantial portions of 
// the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
// THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, 
// TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
// SOFTWARE.
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//
// Author(s):  Filip Strugar (filip.strugar@intel.com)
//
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#pragma once

#include "Core/vaCoreIncludes.h"
#include "Core/vaUI.h"

#include "Rendering/vaRenderingIncludes.h"

#define INCLUDED_FROM_CPP
#include "SMAAWrapper.hlsl"

namespace VertexAsylum
{
    class vaCameraBase;

    class vaSMAAWrapper : public VertexAsylum::vaRenderingModule, public vaUIPanel
    {
    public:
        // enum Mode { MODE_SMAA_1X, MODE_SMAA_T2X, MODE_SMAA_S2X, MODE_SMAA_4X, MODE_SMAA_COUNT = MODE_SMAA_4X };
        enum Preset { PRESET_LOW, PRESET_MEDIUM, PRESET_HIGH, PRESET_ULTRA, PRESET_CUSTOM, PRESET_COUNT = PRESET_CUSTOM };

        enum class SpatialSearch : int32
        {
            Original,
            AdaptiveContrast
        };

        enum class TemporalCoverage : int32
        {
            Disabled,
            FullScreen,
            EdgeSelective
        };

        enum class ReprojectionMode : int32
        {
            Off,
            CameraDepthMatrices,
            CameraDepthMatricesAndObjectMotion
        };

        enum class JitterPolicy : int32
        {
            None,
            SMAAT2X
        };

        enum class HistorySampler : int32
        {
            Bilinear,
            CatmullRom5Tap
        };

        enum class HistoryClipping : int32
        {
            Off,
            YCoCgVariance
        };

        enum class NonCandidateBase : int32
        {
            CurrentSpatial,
            DeJitteredSpatial
        };

        enum class CandidatePolicy : int32
        {
            AllBaseEdges,
            IntelFamilyNonDominant,
            ExperimentalLocalMeanMax3x3
        };

        enum class TemporalDebugView : int32
        {
            None,
            BaseEdges,
            SelectedCandidates,
            CurrentSpatial,
            HistoryBeforeClipping,
            HistoryAfterClipping,
            ClippingDelta
        };

        struct TemporalCandidateStatistics
        {
            bool                        Valid                       = false;
            uint32                      BaseEdgeCount               = 0;
            uint32                      CandidateCount              = 0;
            uint32                      ProcessCount                = 0;
            uint32                      DispatchGroupCount          = 0;
            uint32                      PixelCount                  = 0;
            CandidatePolicy             Policy                      = CandidatePolicy::AllBaseEdges;

            float GetCandidateToBaseRatio( ) const
            {
                return (BaseEdgeCount > 0)? (float)CandidateCount / (float)BaseEdgeCount : 0.0f;
            }

            float GetCandidateToPixelRatio( ) const
            {
                return (PixelCount > 0)? (float)CandidateCount / (float)PixelCount : 0.0f;
            }
        };

        struct TemporalCandidateValidation
        {
            bool                        Valid                       = false;
            bool                        Passed                      = false;
            uint32                      RequestedCount              = 0;
            uint32                      ExpectedCount               = 0;
            uint32                      ReadbackCount               = 0;
            uint32                      DuplicateCount              = 0;
            uint32                      OutOfRangeCount             = 0;
            uint32                      CapacityOverflowCount       = 0;
        };

        struct TemporalLifecycleDiagnostics
        {
            bool                        Enabled                     = false;
            bool                        Passed                      = true;
            uint32                      ResetCount                  = 0;
            uint32                      CompletedFrameCount         = 0;
            uint32                      SeedFrameCount              = 0;
            uint32                      ResolvedFrameCount          = 0;
            uint32                      ReprojectionFrameCount      = 0;
            uint32                      FrameIndexMismatchCount     = 0;
            uint32                      HistoryStateMismatchCount   = 0;
            uint32                      HistoryResourceMismatchCount = 0;
            uint32                      JitterMismatchCount         = 0;
            uint32                      SubsampleMismatchCount      = 0;
            uint32                      MatrixMismatchCount         = 0;
            int32                       LastFrameIndexBefore        = -1;
            int32                       LastFrameIndexAfter         = -1;
            uint32                      LastWidth                   = 0;
            uint32                      LastHeight                  = 0;
            bool                        LastHistoryValidBefore      = false;
            bool                        LastWasSeed                 = false;
            bool                        LastUsedReprojection        = false;
            vaVector2                   LastJitter                  = vaVector2( 0.0f, 0.0f );
            vaVector4                   LastSubsampleIndices        = vaVector4( 0.0f, 0.0f, 0.0f, 0.0f );

            uint32 GetFailureCount( ) const
            {
                return FrameIndexMismatchCount + HistoryStateMismatchCount
                    + HistoryResourceMismatchCount + JitterMismatchCount
                    + SubsampleMismatchCount + MatrixMismatchCount;
            }
        };

        enum class TemporalVelocityDiagnosticMode : int32
        {
            Disabled,
            StaticCameraZero,
            CameraRightTranslation
        };

        struct TemporalVelocityDiagnostics
        {
            bool                        Valid                       = false;
            bool                        Passed                      = false;
            TemporalVelocityDiagnosticMode
                                        Mode                        = TemporalVelocityDiagnosticMode::Disabled;
            uint32                      PixelCount                  = 0;
            uint32                      FinitePixelCount            = 0;
            uint32                      SignificantXCount          = 0;
            uint32                      ExpectedNegativeXCount     = 0;
            uint32                      HistoryUVInBoundsCount      = 0;
            vaVector2                   MeanVelocity                = vaVector2( 0.0f, 0.0f );
            vaVector2                   MinimumVelocity             = vaVector2( 0.0f, 0.0f );
            vaVector2                   MaximumVelocity             = vaVector2( 0.0f, 0.0f );
            float                       MaximumAbsoluteVelocity     = 0.0f;

            float GetExpectedNegativeXRatio( ) const
            {
                return SignificantXCount > 0? (float)ExpectedNegativeXCount / (float)SignificantXCount : 0.0f;
            }

            float GetHistoryUVInBoundsRatio( ) const
            {
                return FinitePixelCount > 0? (float)HistoryUVInBoundsCount / (float)FinitePixelCount : 0.0f;
            }
        };

        struct TemporalFeedbackDiagnostics
        {
            bool                        Enabled                     = false;
            bool                        Valid                       = false;
            bool                        Passed                      = false;
            uint32                      CompletedFrameCount         = 0;
            uint32                      OutputHistoryCheckCount     = 0;
            uint32                      PreviousHistoryCheckCount   = 0;
            uint32                      ReadbackFailureCount        = 0;
            uint64                      OutputHistoryMismatchBytes  = 0;
            uint32                      PreviousHistoryHashMismatchCount = 0;
            uint64                      LastResolvedHistoryHash     = 0;
            uint64                      LastPreviousHistoryHash     = 0;
        };

        struct CatmullRomDiagnostics
        {
            bool                        Valid                       = false;
            bool                        Passed                      = false;
            uint32                      GPUComparisonSampleCount    = 0;
            uint32                      CPUReferenceSampleCount     = 0;
            float                       MaximumWeightSumError       = 0.0f;
            float                       MaximumSymmetryError        = 0.0f;
            float                       GPUConstantMaximumError     = 0.0f;
            float                       GPUToCPU5TapMaximumError    = 0.0f;
            float                       GPUToCPU5TapRMSE            = 0.0f;
            float                       CPU5TapTo16TapMaximumError  = 0.0f;
            float                       CPU5TapTo16TapRMSE          = 0.0f;
        };

        struct VarianceClippingDiagnostics
        {
            bool                        Valid                       = false;
            bool                        Passed                      = false;
            uint32                      PixelCount                  = 0;
            uint32                      FinitePixelCount            = 0;
            uint32                      OutlierRejectedCount        = 0;
            uint32                      OutlierBoxViolationCount    = 0;
            float                       RGBYCoCgRoundTripMaximumError = 0.0f;
            float                       ConstantCaseMaximumError    = 0.0f;
            float                       InsideHistoryMaximumError   = 0.0f;
            float                       GPUToCPUReferenceMaximumError = 0.0f;
            float                       GPUToCPUReferenceRMSE       = 0.0f;
        };

        struct TemporalSettings
        {
            TemporalCoverage             Coverage                    = TemporalCoverage::Disabled;
            ReprojectionMode             Reprojection                = ReprojectionMode::Off;
            JitterPolicy                 Jitter                      = JitterPolicy::None;
            HistorySampler               Sampler                     = HistorySampler::Bilinear;
            HistoryClipping              Clipping                    = HistoryClipping::Off;
            NonCandidateBase             NonCandidate                = NonCandidateBase::CurrentSpatial;
            CandidatePolicy              Candidates                  = CandidatePolicy::AllBaseEdges;
            float                        HistoryWeight               = 0.5f;
            float                        NonDominantRemovalAmount    = 0.5f;
            float                        EdgeThreshold               = 1.0f / 22.0f;

            bool operator == ( const TemporalSettings & other ) const
            {
                return Coverage == other.Coverage
                    && Reprojection == other.Reprojection
                    && Jitter == other.Jitter
                    && Sampler == other.Sampler
                    && Clipping == other.Clipping
                    && NonCandidate == other.NonCandidate
                    && Candidates == other.Candidates
                    && HistoryWeight == other.HistoryWeight
                    && NonDominantRemovalAmount == other.NonDominantRemovalAmount
                    && EdgeThreshold == other.EdgeThreshold;
            }

            bool operator != ( const TemporalSettings & other ) const
            {
                return !( *this == other );
            }
        };

        struct Settings
        {
            Preset                          Preset;
            SpatialSearch                   Search;

            Settings( )
            {
                this->Preset        = PRESET_HIGH;
                this->Search        = SpatialSearch::Original;
            }
        };

    protected:
        Settings                    m_settings;

        SMAAShaderConstants         m_constants;
        vaTypedConstantBufferWrapper<SMAAShaderConstants>
                                    m_constantsBuffer;

        TemporalSettings            m_temporalSettings;
        int                         m_temporalFrameIndex                = 0;
        TemporalCandidateStatistics m_temporalCandidateStatistics;
        bool                        m_temporalCandidateStatisticsReadbackEnabled = true;
        bool                        m_candidatePolicyOverrideEnabled    = false;
        CandidatePolicy             m_candidatePolicyOverride           = CandidatePolicy::IntelFamilyNonDominant;
        bool                        m_nonDominantRemovalOverrideEnabled  = false;
        float                       m_nonDominantRemovalOverride         = 0.5f;
        bool                        m_historySamplerOverrideEnabled     = false;
        HistorySampler              m_historySamplerOverride            = HistorySampler::CatmullRom5Tap;
        bool                        m_historyClippingOverrideEnabled    = false;
        HistoryClipping             m_historyClippingOverride           = HistoryClipping::YCoCgVariance;
        bool                        m_forcedCandidateCountEnabled        = false;
        uint32                      m_forcedCandidateCount               = 65;
        TemporalDebugView           m_temporalDebugView                  = TemporalDebugView::None;
        TemporalCandidateValidation m_temporalCandidateValidation;
        TemporalLifecycleDiagnostics m_temporalLifecycleDiagnostics;
        uint32                      m_temporalLifecycleFramesSinceReset = 0;
        bool                        m_temporalLastSubsampleIndicesValid = false;
        float                       m_temporalLastSubsampleIndices[4]   = { 0.0f, 0.0f, 0.0f, 0.0f };
        TemporalVelocityDiagnosticMode
                                    m_temporalVelocityDiagnosticMode    = TemporalVelocityDiagnosticMode::Disabled;
        TemporalVelocityDiagnostics m_temporalVelocityDiagnostics;
        bool                        m_temporalVelocityDiagnosticPending = false;
        TemporalFeedbackDiagnostics m_temporalFeedbackDiagnostics;
        CatmullRomDiagnostics       m_catmullRomDiagnostics;
        bool                        m_catmullRomDiagnosticPending    = false;
        VarianceClippingDiagnostics m_varianceClippingDiagnostics;
        bool                        m_varianceClippingDiagnosticPending = false;

        //bool                        m_debugShowEdges;

    protected:
        vaSMAAWrapper( const vaRenderingModuleParams & params );
    public:
        ~vaSMAAWrapper( );

    public:
        void                        SetPreset( Preset preset )
        {
            if( m_settings.Preset != preset )
            {
                m_settings.Preset = preset;
                ResetTemporalHistory( );
            }
        }
        Preset                      GetPreset( ) const                    { return m_settings.Preset; }
        void                        SetSpatialSearch( SpatialSearch search )
        {
            if( m_settings.Search != search )
            {
                m_settings.Search = search;
                ResetTemporalHistory( );
            }
        }
        SpatialSearch               GetSpatialSearch( ) const             { return m_settings.Search; }
        bool                        GetAdaptiveSpatialSearchEnabled( ) const { return m_settings.Search == SpatialSearch::AdaptiveContrast; }

        void                        SetTemporalSettings( const TemporalSettings & settings )
        {
            if( m_temporalSettings != settings )
            {
                m_temporalSettings = settings;
                ResetTemporalHistory( );
            }
        }
        const TemporalSettings &    GetTemporalSettings( ) const       { return m_temporalSettings; }
        bool                        GetTemporalModeEnabled( ) const      { return m_temporalSettings.Coverage != TemporalCoverage::Disabled; }
        bool                        GetTemporalReprojectionEnabled( ) const
        {
            return m_temporalSettings.Reprojection == ReprojectionMode::CameraDepthMatrices
                || m_temporalSettings.Reprojection == ReprojectionMode::CameraDepthMatricesAndObjectMotion;
        }
        bool                        GetObjectMotionReprojectionEnabled( ) const
        {
            return m_temporalSettings.Reprojection == ReprojectionMode::CameraDepthMatricesAndObjectMotion;
        }
        bool                        GetEdgeSelectiveTemporalEnabled( ) const { return m_temporalSettings.Coverage == TemporalCoverage::EdgeSelective; }
        bool                        GetTemporalJitterEnabled( ) const    { return m_temporalSettings.Jitter == JitterPolicy::SMAAT2X; }
        bool                        GetDeJitteredNonCandidateBaseEnabled( ) const
        {
            return m_temporalSettings.NonCandidate == NonCandidateBase::DeJitteredSpatial;
        }
        CandidatePolicy             GetEffectiveCandidatePolicy( ) const { return m_candidatePolicyOverrideEnabled? m_candidatePolicyOverride : m_temporalSettings.Candidates; }
        void                        SetCandidatePolicyOverride( bool enabled, CandidatePolicy policy )
        {
            if( m_candidatePolicyOverrideEnabled != enabled || m_candidatePolicyOverride != policy )
            {
                m_candidatePolicyOverrideEnabled = enabled;
                m_candidatePolicyOverride = policy;
                ResetTemporalHistory( );
            }
        }
        bool                        GetCandidatePolicyOverrideEnabled( ) const { return m_candidatePolicyOverrideEnabled; }
        float                       GetEffectiveNonDominantRemovalAmount( ) const
        {
            return m_nonDominantRemovalOverrideEnabled? m_nonDominantRemovalOverride : m_temporalSettings.NonDominantRemovalAmount;
        }
        void                        SetNonDominantRemovalOverride( bool enabled, float value )
        {
            value = vaMath::Clamp( value, 0.0f, 1.0f );
            if( m_nonDominantRemovalOverrideEnabled != enabled || m_nonDominantRemovalOverride != value )
            {
                m_nonDominantRemovalOverrideEnabled = enabled;
                m_nonDominantRemovalOverride = value;
                ResetTemporalHistory( );
            }
        }
        bool                        GetNonDominantRemovalOverrideEnabled( ) const { return m_nonDominantRemovalOverrideEnabled; }
        HistorySampler              GetEffectiveHistorySampler( ) const { return m_historySamplerOverrideEnabled? m_historySamplerOverride : m_temporalSettings.Sampler; }
        HistoryClipping             GetEffectiveHistoryClipping( ) const { return m_historyClippingOverrideEnabled? m_historyClippingOverride : m_temporalSettings.Clipping; }
        void                        SetHistorySamplerOverride( bool enabled, HistorySampler value )
        {
            if( m_historySamplerOverrideEnabled != enabled || m_historySamplerOverride != value )
            {
                m_historySamplerOverrideEnabled = enabled;
                m_historySamplerOverride = value;
                ResetTemporalHistory( );
            }
        }
        void                        SetHistoryClippingOverride( bool enabled, HistoryClipping value )
        {
            if( m_historyClippingOverrideEnabled != enabled || m_historyClippingOverride != value )
            {
                m_historyClippingOverrideEnabled = enabled;
                m_historyClippingOverride = value;
                ResetTemporalHistory( );
            }
        }
        bool                        GetHistorySamplerOverrideEnabled( ) const { return m_historySamplerOverrideEnabled; }
        bool                        GetHistoryClippingOverrideEnabled( ) const { return m_historyClippingOverrideEnabled; }
        const TemporalCandidateStatistics & GetTemporalCandidateStatistics( ) const { return m_temporalCandidateStatistics; }
        void                        SetTemporalCandidateStatisticsReadbackEnabled( bool enabled )
        {
            if( m_temporalCandidateStatisticsReadbackEnabled != enabled )
            {
                m_temporalCandidateStatisticsReadbackEnabled = enabled;
                m_temporalCandidateStatistics = TemporalCandidateStatistics( );
                ResetTemporalHistory( );
            }
        }
        bool                        GetTemporalCandidateStatisticsReadbackEnabled( ) const { return m_temporalCandidateStatisticsReadbackEnabled; }
        void                        SetForcedCandidateCountForDiagnostics( bool enabled, uint32 count )
        {
            if( m_forcedCandidateCountEnabled != enabled || m_forcedCandidateCount != count )
            {
                m_forcedCandidateCountEnabled = enabled;
                m_forcedCandidateCount = count;
                ResetTemporalHistory( );
            }
        }
        bool                        GetForcedCandidateCountEnabled( ) const { return m_forcedCandidateCountEnabled; }
        uint32                      GetForcedCandidateCount( ) const    { return m_forcedCandidateCount; }
        const TemporalCandidateValidation & GetTemporalCandidateValidation( ) const { return m_temporalCandidateValidation; }
        TemporalDebugView           GetTemporalDebugView( ) const       { return m_temporalDebugView; }
        void                        SetTemporalDebugView( TemporalDebugView value ) { m_temporalDebugView = value; }
        bool                        GetClippingDebugViewsEnabled( ) const
        {
            return m_temporalDebugView == TemporalDebugView::HistoryBeforeClipping
                || m_temporalDebugView == TemporalDebugView::HistoryAfterClipping
                || m_temporalDebugView == TemporalDebugView::ClippingDelta;
        }
        void                        SetTemporalLifecycleDiagnosticsEnabled( bool enabled )
        {
            if( enabled )
            {
                m_temporalLifecycleDiagnostics = TemporalLifecycleDiagnostics( );
                m_temporalLifecycleDiagnostics.Enabled = true;
                ResetTemporalHistory( );
            }
            else
            {
                m_temporalLifecycleDiagnostics.Enabled = false;
            }
        }
        const TemporalLifecycleDiagnostics & GetTemporalLifecycleDiagnostics( ) const { return m_temporalLifecycleDiagnostics; }
        void                        SetTemporalVelocityDiagnosticMode( TemporalVelocityDiagnosticMode mode )
        {
            if( m_temporalVelocityDiagnosticMode != mode )
            {
                m_temporalVelocityDiagnosticMode = mode;
                m_temporalVelocityDiagnostics = TemporalVelocityDiagnostics( );
                m_temporalVelocityDiagnostics.Mode = mode;
                m_temporalVelocityDiagnosticPending = mode != TemporalVelocityDiagnosticMode::Disabled;
            }
        }
        TemporalVelocityDiagnosticMode GetTemporalVelocityDiagnosticMode( ) const { return m_temporalVelocityDiagnosticMode; }
        bool                        GetTemporalVelocityDiagnosticsEnabled( ) const { return m_temporalVelocityDiagnosticMode != TemporalVelocityDiagnosticMode::Disabled; }
        const TemporalVelocityDiagnostics & GetTemporalVelocityDiagnostics( ) const { return m_temporalVelocityDiagnostics; }
        void                        SetTemporalFeedbackDiagnosticsEnabled( bool enabled )
        {
            m_temporalFeedbackDiagnostics = TemporalFeedbackDiagnostics( );
            m_temporalFeedbackDiagnostics.Enabled = enabled;
            if( enabled )
                ResetTemporalHistory( );
        }
        bool                        GetTemporalFeedbackDiagnosticsEnabled( ) const { return m_temporalFeedbackDiagnostics.Enabled; }
        const TemporalFeedbackDiagnostics & GetTemporalFeedbackDiagnostics( ) const { return m_temporalFeedbackDiagnostics; }
        void                        RequestCatmullRomDiagnostics( )
        {
            m_catmullRomDiagnostics = CatmullRomDiagnostics( );
            m_catmullRomDiagnosticPending = true;
        }
        bool                        GetCatmullRomDiagnosticPending( ) const { return m_catmullRomDiagnosticPending; }
        const CatmullRomDiagnostics & GetCatmullRomDiagnostics( ) const { return m_catmullRomDiagnostics; }
        void                        RequestVarianceClippingDiagnostics( )
        {
            m_varianceClippingDiagnostics = VarianceClippingDiagnostics( );
            m_varianceClippingDiagnosticPending = true;
        }
        bool                        GetVarianceClippingDiagnosticPending( ) const { return m_varianceClippingDiagnosticPending; }
        const VarianceClippingDiagnostics & GetVarianceClippingDiagnostics( ) const { return m_varianceClippingDiagnostics; }

        // frame 0/S0 uses SMAA jitter (+0.25, -0.25), while frame 1/S1 uses
        // (-0.25, +0.25) in clip space. vaCameraBase::SetSubpixelOffset flips
        // Y while applying it to the projection matrix.
        vaVector2                   GetTemporalJitterOffset( ) const
        {
            return (m_temporalFrameIndex == 0)? vaVector2( 0.25f, 0.25f ) : vaVector2( -0.25f, -0.25f );
        }

        virtual void                ResetTemporalHistory( )
        {
            m_temporalFrameIndex = 0;
            m_temporalLifecycleFramesSinceReset = 0;
            m_temporalLastSubsampleIndicesValid = false;
            if( m_temporalLifecycleDiagnostics.Enabled )
                m_temporalLifecycleDiagnostics.ResetCount++;
        }

        // Returns the previous frame's unjittered camera view-projection only
        // while the temporal history lifecycle is valid. The sample uses this
        // before opaque rendering to generate a controlled rigid-object motion
        // vector target.
        virtual bool                TryGetPreviousUnjitteredViewProj( vaMatrix4x4 & outMatrix ) const
        {
            outMatrix = vaMatrix4x4::Identity;
            return false;
        }

        // Applies SMAA to currently selected render target using provided inputs
        virtual vaDrawResultFlags   Draw( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor, const shared_ptr<vaTexture> & optionalInLuma = nullptr,
                                            const shared_ptr<vaTexture> & optionalDepth = nullptr, const vaCameraBase * optionalCamera = nullptr,
                                            const shared_ptr<vaTexture> & optionalObjectMotion = nullptr )  = 0;

        // if SMAA is no longer used make sure it's not reserving any memory
        virtual void                CleanupTemporaryResources( )                                                            = 0;

    protected:
        int                         GetTemporalFrameIndex( ) const       { return m_temporalFrameIndex; }
        void                        AdvanceTemporalFrame( )              { m_temporalFrameIndex = (m_temporalFrameIndex + 1) % 2; }

        // virtual void                UpdateConstants( vaRenderDeviceContext & renderContext );

    private:
        virtual void                UIPanelDraw( ) override;
        virtual bool                UIPanelIsListed( ) const override          { return false; }
    };

}
