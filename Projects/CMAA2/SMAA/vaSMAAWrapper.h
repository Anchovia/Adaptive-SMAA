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

    enum class vaSMAATemporalEdgeHistoryMode : int32
    {
        None = 0,
        Union = 1,
        Intersection = 2
    };

    struct vaSMAATemporalEdgeStats
    {
        uint32                      CurrentEdgePixels       = 0;
        uint32                      PreviousEdgePixels      = 0;
        uint32                      UnionPixels             = 0;
        uint32                      IntersectionPixels      = 0;
        uint32                      HistoryAppliedPixels    = 0;
        uint32                      TotalPixels             = 0;
        bool                        Valid                   = false;
    };

    class vaSMAAWrapper : public VertexAsylum::vaRenderingModule, public vaUIPanel
    {
    public:
        // enum Mode { MODE_SMAA_1X, MODE_SMAA_T2X, MODE_SMAA_S2X, MODE_SMAA_4X, MODE_SMAA_COUNT = MODE_SMAA_4X };
        enum Preset { PRESET_LOW, PRESET_MEDIUM, PRESET_HIGH, PRESET_ULTRA, PRESET_CUSTOM, PRESET_COUNT = PRESET_CUSTOM };

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

        bool                        m_temporalModeEnabled               = false;
        bool                        m_temporalReprojectionEnabled       = false;
        bool                        m_temporalEdgeGuidedEnabled         = false;
        bool                        m_temporalEdgeGuidedStabilized      = false;
        vaSMAATemporalEdgeHistoryMode
                                    m_temporalEdgeHistoryMode           = vaSMAATemporalEdgeHistoryMode::None;
        int                         m_temporalEdgeSupportRadius         = 1;
        bool                        m_temporalStatsEnabled              = false;
        vaSMAATemporalEdgeStats     m_temporalEdgeStats;
        int                         m_temporalFrameIndex                = 0;

        //bool                        m_debugShowEdges;

    protected:
        vaSMAAWrapper( const vaRenderingModuleParams & params );
    public:
        ~vaSMAAWrapper( );

    public:
        void                        SetTemporalModeEnabled( bool enabled )
        {
            if( m_temporalModeEnabled != enabled )
            {
                m_temporalModeEnabled = enabled;
                ResetTemporalHistory( );
            }
        }
        bool                        GetTemporalModeEnabled( ) const      { return m_temporalModeEnabled; }
        void                        SetTemporalReprojectionEnabled( bool enabled )
        {
            if( m_temporalReprojectionEnabled != enabled )
            {
                m_temporalReprojectionEnabled = enabled;
                ResetTemporalHistory( );
            }
        }
        bool                        GetTemporalReprojectionEnabled( ) const { return m_temporalReprojectionEnabled; }
        void                        SetTemporalEdgeGuidedEnabled( bool enabled )
        {
            if( m_temporalEdgeGuidedEnabled != enabled )
            {
                m_temporalEdgeGuidedEnabled = enabled;
                ResetTemporalHistory( );
            }
        }
        bool                        GetTemporalEdgeGuidedEnabled( ) const { return m_temporalEdgeGuidedEnabled; }
        void                        SetTemporalEdgeGuidedStabilized( bool enabled )
        {
            if( m_temporalEdgeGuidedStabilized != enabled )
            {
                m_temporalEdgeGuidedStabilized = enabled;
                ResetTemporalHistory( );
            }
        }
        bool                        GetTemporalEdgeGuidedStabilized( ) const { return m_temporalEdgeGuidedStabilized; }
        void                        SetTemporalEdgeHistoryMode( vaSMAATemporalEdgeHistoryMode mode )
        {
            if( m_temporalEdgeHistoryMode != mode )
            {
                m_temporalEdgeHistoryMode = mode;
                ResetTemporalHistory( );
            }
        }
        vaSMAATemporalEdgeHistoryMode
                                    GetTemporalEdgeHistoryMode( ) const { return m_temporalEdgeHistoryMode; }
        void                        SetTemporalEdgeSupportRadius( int radius )
        {
            radius = vaMath::Clamp( radius, 0, 1 );
            if( m_temporalEdgeSupportRadius != radius )
            {
                m_temporalEdgeSupportRadius = radius;
                ResetTemporalHistory( );
            }
        }
        int                         GetTemporalEdgeSupportRadius( ) const { return m_temporalEdgeSupportRadius; }
        void                        SetTemporalStatsEnabled( bool enabled )
        {
            if( m_temporalStatsEnabled != enabled )
            {
                m_temporalStatsEnabled = enabled;
                m_temporalEdgeStats = vaSMAATemporalEdgeStats();
                ResetTemporalHistory( );
            }
        }
        bool                        GetTemporalStatsEnabled( ) const { return m_temporalStatsEnabled; }
        const vaSMAATemporalEdgeStats &
                                    GetTemporalEdgeStats( ) const { return m_temporalEdgeStats; }

        // frame 0/S0 uses SMAA jitter (+0.25, -0.25), while frame 1/S1 uses
        // (-0.25, +0.25) in clip space. vaCameraBase::SetSubpixelOffset flips
        // Y while applying it to the projection matrix.
        vaVector2                   GetTemporalJitterOffset( ) const
        {
            return (m_temporalFrameIndex == 0)? vaVector2( 0.25f, 0.25f ) : vaVector2( -0.25f, -0.25f );
        }

        virtual void                ResetTemporalHistory( )             { m_temporalFrameIndex = 0; m_temporalEdgeStats = vaSMAATemporalEdgeStats(); }

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
