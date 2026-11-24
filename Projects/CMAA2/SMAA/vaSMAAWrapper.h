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

        bool                        m_adaptiveSearch                = false;  // Adaptive SMAA: 1% contrast-tiered search lengths
        bool                        m_selectedTemporal              = false;  // selected temporal route with (c') Cross5
        bool                        m_temporalEnabled               = true;   // Temporal checkbox of SMAA Adaptive + Temporal (key Y)

        //bool                        m_debugShowEdges;

    protected:
        vaSMAAWrapper( const vaRenderingModuleParams & params );
    public:
        ~vaSMAAWrapper( );

    public:
        // Validation harness access to the preset edited by the UI.
        Settings &                  GetSettings( )                      { return m_settings; }
        // Adaptive SMAA (SMAA_ADAPTIVE_SEARCH): per-preset search tiers stored with the edges in an RGBA8 target.
        void                        SetAdaptiveSearch( bool enabled )   { m_adaptiveSearch = enabled; }
        bool                        GetAdaptiveSearch( ) const          { return m_adaptiveSearch; }

        // Selected temporal route: SMAA 1X, then history (weight 0.8, Catmull-Rom 5-tap) at the current raw
        // edges and the camera-reprojected previous raw edges, with the (c') Cross5 velocity weight. Camera/depth
        // reprojection only, no jitter. Draw() then needs the scene depth and camera.
        void                        SetSelectedTemporal( bool enabled ) { if( m_selectedTemporal != enabled ) { m_selectedTemporal = enabled; ResetTemporalHistory( ); } }
        bool                        GetSelectedTemporal( ) const        { return m_selectedTemporal; }
        // Temporal checkbox of SMAA Adaptive + Temporal (key Y). Off leaves Adaptive SMAA 1X of the same preset. The
        // sample passes it on through SetSelectedTemporal, so each switch restarts the history from a seed.
        void                        SetTemporalEnabled( bool enabled )  { m_temporalEnabled = enabled; }
        bool                        GetTemporalEnabled( ) const         { return m_temporalEnabled; }
        // The next frame starts again from a seed (camera load, scene or image change; resize recreates everything).
        virtual void                ResetTemporalHistory( )             { }
        // Non-null only for a frame drawn on the selected route: its next history, which is the final colour.
        virtual shared_ptr<vaTexture> GetPresentedOutputOverride( ) const { return nullptr; }
        // Validation harness: whether any temporal texture (history, spatial copy, velocity) is allocated.
        virtual bool                HasTemporalResources( ) const       { return false; }

        // Applies SMAA to currently selected render target using provided inputs
        virtual vaDrawResultFlags   Draw( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor, const shared_ptr<vaTexture> & optionalInLuma = nullptr,
                                            const shared_ptr<vaTexture> & optionalDepth = nullptr, const vaCameraBase * optionalCamera = nullptr )  = 0;

        // if SMAA is no longer used make sure it's not reserving any memory
        virtual void                CleanupTemporaryResources( )                                                            = 0;

    protected:
        // virtual void                UpdateConstants( vaRenderDeviceContext & renderContext );

    private:
        virtual void                UIPanelDraw( ) override;
        virtual bool                UIPanelIsListed( ) const override          { return false; }
    };

}
