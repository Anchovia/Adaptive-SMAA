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

        enum class TemporalCoverage : int32
        {
            Disabled,
            FullScreen,
            EdgeSelective
        };

        enum class ReprojectionMode : int32
        {
            Off,
            CameraDepthMatrices
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
            SelectedCandidates
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

        struct TemporalSettings
        {
            TemporalCoverage             Coverage                    = TemporalCoverage::Disabled;
            ReprojectionMode             Reprojection                = ReprojectionMode::Off;
            JitterPolicy                 Jitter                      = JitterPolicy::None;
            HistorySampler               Sampler                     = HistorySampler::Bilinear;
            HistoryClipping              Clipping                    = HistoryClipping::Off;
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

            Settings( )
            {
                this->Preset        = PRESET_HIGH;
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
        bool                        m_candidatePolicyOverrideEnabled    = false;
        CandidatePolicy             m_candidatePolicyOverride           = CandidatePolicy::IntelFamilyNonDominant;
        bool                        m_forcedCandidateCountEnabled        = false;
        uint32                      m_forcedCandidateCount               = 65;
        TemporalDebugView           m_temporalDebugView                  = TemporalDebugView::None;
        TemporalCandidateValidation m_temporalCandidateValidation;

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
        bool                        GetTemporalReprojectionEnabled( ) const { return m_temporalSettings.Reprojection == ReprojectionMode::CameraDepthMatrices; }
        bool                        GetEdgeSelectiveTemporalEnabled( ) const { return m_temporalSettings.Coverage == TemporalCoverage::EdgeSelective; }
        bool                        GetTemporalJitterEnabled( ) const    { return m_temporalSettings.Jitter == JitterPolicy::SMAAT2X; }
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
        const TemporalCandidateStatistics & GetTemporalCandidateStatistics( ) const { return m_temporalCandidateStatistics; }
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

        // frame 0/S0 uses SMAA jitter (+0.25, -0.25), while frame 1/S1 uses
        // (-0.25, +0.25) in clip space. vaCameraBase::SetSubpixelOffset flips
        // Y while applying it to the projection matrix.
        vaVector2                   GetTemporalJitterOffset( ) const
        {
            return (m_temporalFrameIndex == 0)? vaVector2( 0.25f, 0.25f ) : vaVector2( -0.25f, -0.25f );
        }

        virtual void                ResetTemporalHistory( )             { m_temporalFrameIndex = 0; }

        // Applies SMAA to currently selected render target using provided inputs
        virtual vaDrawResultFlags   Draw( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor, const shared_ptr<vaTexture> & optionalInLuma = nullptr,
                                            const shared_ptr<vaTexture> & optionalDepth = nullptr, const vaCameraBase * optionalCamera = nullptr )  = 0;

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
