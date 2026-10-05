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
        int                         m_temporalFrameIndex                = 0;

        // Research ablation: projection jitter and spatial area pattern change together.
        bool                        m_temporalSamplePatternEnabled = true;
        vaVector2                   m_lastTemporalProjectionOffset = vaVector2(0,0);
        bool                        m_spatialFirstEdgeEnabled = false;
        bool m_firstEdgeStencilEnabled = true;
        bool m_stencilUpstreamControl = false;
        bool m_executionDiagnostics = false;
        bool m_spatialPassProfiling = false;
        bool m_shaderStencilRefSupported=false;
        uint64 m_weightSamples=~uint64(0),m_weightInvocations=~uint64(0);
        int m_edgePersistenceMode = 0; // 0 baseline, 1 one-frame raw union, 2 current-only depth control
        wstring m_thinLineTracePrefix;
        uint64 m_lastResolveInvocations = 0, m_lastResolveSamples = 0;
        bool m_executionQueryOK = false;

        //bool                        m_debugShowEdges;

    protected:
        vaSMAAWrapper( const vaRenderingModuleParams & params );
    public:
        ~vaSMAAWrapper( );

    public:
        // Harness access to the same preset edited by the existing UI.
        Settings &                  GetSettings( ) { return m_settings; }
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

        void SetFirstEdgeStencilEnabled(bool enabled) {
            if(m_firstEdgeStencilEnabled!=enabled){m_firstEdgeStencilEnabled=enabled;ResetTemporalHistory();}
        }
        bool GetFirstEdgeStencilEnabled() const {return m_firstEdgeStencilEnabled;}
        void SetStencilUpstreamControl(bool enabled){if(m_stencilUpstreamControl!=enabled){m_stencilUpstreamControl=enabled;ResetTemporalHistory();}}
        bool GetStencilUpstreamControl() const {return m_stencilUpstreamControl;}
        void SetExecutionDiagnostics(bool enabled){m_executionDiagnostics=enabled;}
        void SetSpatialPassProfiling(bool enabled){m_spatialPassProfiling=enabled;}
        bool GetShaderStencilRefSupported() const {return m_shaderStencilRefSupported;}
        uint64 GetWeightSamples() const {return m_weightSamples;}
        uint64 GetWeightInvocations() const {return m_weightInvocations;}
        bool ExecutionQueryOK() const {return m_executionQueryOK;}
        uint64 GetResolveInvocations() const {return m_lastResolveInvocations;}
        uint64 GetResolveSamples() const {return m_lastResolveSamples;}
        virtual bool SaveExecutionCoverage(vaRenderDeviceContext&,const wstring&){return false;}
        void SetEdgePersistenceMode(int mode) {
            assert(mode>=0 && mode<=13);
            if(m_edgePersistenceMode!=mode){m_edgePersistenceMode=mode;ResetTemporalHistory();}
        }
        int GetEdgePersistenceMode() const {return m_edgePersistenceMode;}
        // Cost audit: 3=storage only, 4=constant depth export, 5=union preparation
        // with baseline stencil resolve, 6=identical union with conservative depth,
        // 7=identical union written by pass 1 into the existing stencil.
        bool UsesPersistenceDepthGate() const {return m_edgePersistenceMode==1 || m_edgePersistenceMode==2 || m_edgePersistenceMode==6;}
        void SetThinLineTracePrefix(const wstring &prefix){m_thinLineTracePrefix=prefix;}
        virtual bool SaveThinLineTraceInputs(vaRenderDeviceContext&,const wstring&){return false;}

        void SetSpatialFirstEdgeEnabled(bool enabled) {
            if(m_spatialFirstEdgeEnabled!=enabled){m_spatialFirstEdgeEnabled=enabled;ResetTemporalHistory();}
        }
        bool GetSpatialFirstEdgeEnabled() const {return m_spatialFirstEdgeEnabled;}
        virtual bool SaveSpatialEdgeSnapshot(vaRenderDeviceContext &,const wstring &,bool,bool){return false;}

        void SetTemporalSamplePatternEnabled(bool enabled) {
            if(m_temporalSamplePatternEnabled!=enabled){m_temporalSamplePatternEnabled=enabled;ResetTemporalHistory();}
        }
        bool GetTemporalSamplePatternEnabled() const {return m_temporalSamplePatternEnabled;}
        vaVector2 GetLastTemporalProjectionOffset() const {return m_lastTemporalProjectionOffset;}
        bool HasZeroSubsampleIndices() const {
            for(int i=0;i<4;++i)if(m_constants.subsampleIndices[i]!=0)return false;
            return true;
        }

        // frame 0/S0 uses SMAA jitter (+0.25, -0.25), while frame 1/S1 uses
        // (-0.25, +0.25) in clip space. vaCameraBase::SetSubpixelOffset flips
        // Y while applying it to the projection matrix.
        vaVector2                   GetTemporalJitterOffset( ) const
        {
            if(!m_temporalSamplePatternEnabled)return vaVector2(0,0);
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
