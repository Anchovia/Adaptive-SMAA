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

#include "Core/vaCoreIncludes.h"

#include "Rendering/DirectX/vaDirectXIncludes.h"

#include "Rendering/DirectX/vaDirectXTools.h"

#include "Scene/vaSceneIncludes.h"

#include "Rendering/vaRenderingIncludes.h"

#include "Rendering/DirectX/vaRenderDeviceContextDX11.h"

#include "Rendering/Shaders/vaSharedTypes.h"

#include "Rendering/DirectX/vaTextureDX11.h"

#include "Rendering/DirectX/vaRenderBuffersDX11.h"

#include "vaSMAAWrapper.h"

#include "SMAA.h"

#include "Rendering/DirectX/vaRenderDeviceContextDX12.h" // only so the dx12 stub compiles - will be removed once ported to dx12 file

#include <DirectXPackedVector.h>
#include <array>
#include <cmath>

namespace VertexAsylum
{
    static bool SMAATemporalMatrixIsFinite( const vaMatrix4x4 & matrix )
    {
        for( uint32 row = 0; row < 4; row++ )
            for( uint32 column = 0; column < 4; column++ )
                if( !std::isfinite( matrix( row, column ) ) )
                    return false;
        return true;
    }

    static bool SMAATemporalSubsampleIndicesMatch( const float actual[4], const vaVector4 & expected )
    {
        return vaMath::NearEqual( actual[0], expected.x, 1e-6f )
            && vaMath::NearEqual( actual[1], expected.y, 1e-6f )
            && vaMath::NearEqual( actual[2], expected.z, 1e-6f )
            && vaMath::NearEqual( actual[3], expected.w, 1e-6f );
    }

    struct SMAACatmullDiagnosticColor
    {
        float R;
        float G;
        float B;
        float A;
    };

    static SMAACatmullDiagnosticColor SMAACatmullColorAdd(
        const SMAACatmullDiagnosticColor & left, const SMAACatmullDiagnosticColor & right )
    {
        return { left.R + right.R, left.G + right.G, left.B + right.B, left.A + right.A };
    }

    static SMAACatmullDiagnosticColor SMAACatmullColorScale(
        const SMAACatmullDiagnosticColor & value, float scale )
    {
        return { value.R * scale, value.G * scale, value.B * scale, value.A * scale };
    }

    static float SMAACatmullColorMaximumAbsoluteDifference(
        const SMAACatmullDiagnosticColor & left, const SMAACatmullDiagnosticColor & right )
    {
        return vaMath::Max(
            vaMath::Max( vaMath::Abs( left.R - right.R ), vaMath::Abs( left.G - right.G ) ),
            vaMath::Max( vaMath::Abs( left.B - right.B ), vaMath::Abs( left.A - right.A ) ) );
    }

    static double SMAACatmullColorSquaredDifference(
        const SMAACatmullDiagnosticColor & left, const SMAACatmullDiagnosticColor & right )
    {
        const double differenceR = (double)left.R - (double)right.R;
        const double differenceG = (double)left.G - (double)right.G;
        const double differenceB = (double)left.B - (double)right.B;
        const double differenceA = (double)left.A - (double)right.A;
        return differenceR * differenceR + differenceG * differenceG
            + differenceB * differenceB + differenceA * differenceA;
    }

    static void SMAACatmullRomWeights( float fraction, float weights[4] )
    {
        weights[0] = fraction * (-0.5f + fraction * (1.0f - 0.5f * fraction));
        weights[1] = 1.0f + fraction * fraction * (-2.5f + 1.5f * fraction);
        weights[2] = fraction * (0.5f + fraction * (2.0f - 1.5f * fraction));
        weights[3] = fraction * fraction * (-0.5f + 0.5f * fraction);
    }

    static const SMAACatmullDiagnosticColor & SMAACatmullReadClamped(
        const SMAACatmullDiagnosticColor * source, int width, int height, int x, int y )
    {
        x = vaMath::Clamp( x, 0, width - 1 );
        y = vaMath::Clamp( y, 0, height - 1 );
        return source[y * width + x];
    }

    static SMAACatmullDiagnosticColor SMAACatmullSampleLinearClamp(
        const SMAACatmullDiagnosticColor * source, int width, int height, float u, float v )
    {
        const float texelX = u * (float)width - 0.5f;
        const float texelY = v * (float)height - 0.5f;
        const int x0 = (int)std::floor( texelX );
        const int y0 = (int)std::floor( texelY );
        const float fractionX = texelX - (float)x0;
        const float fractionY = texelY - (float)y0;

        const SMAACatmullDiagnosticColor top = SMAACatmullColorAdd(
            SMAACatmullColorScale( SMAACatmullReadClamped( source, width, height, x0, y0 ), 1.0f - fractionX ),
            SMAACatmullColorScale( SMAACatmullReadClamped( source, width, height, x0 + 1, y0 ), fractionX ) );
        const SMAACatmullDiagnosticColor bottom = SMAACatmullColorAdd(
            SMAACatmullColorScale( SMAACatmullReadClamped( source, width, height, x0, y0 + 1 ), 1.0f - fractionX ),
            SMAACatmullColorScale( SMAACatmullReadClamped( source, width, height, x0 + 1, y0 + 1 ), fractionX ) );
        return SMAACatmullColorAdd(
            SMAACatmullColorScale( top, 1.0f - fractionY ),
            SMAACatmullColorScale( bottom, fractionY ) );
    }

    static SMAACatmullDiagnosticColor SMAACatmullSample5Tap(
        const SMAACatmullDiagnosticColor * source, int width, int height, float u, float v )
    {
        const float samplePositionX = u * (float)width;
        const float samplePositionY = v * (float)height;
        const float texelPosition1X = std::floor( samplePositionX - 0.5f ) + 0.5f;
        const float texelPosition1Y = std::floor( samplePositionY - 0.5f ) + 0.5f;
        float weightsX[4];
        float weightsY[4];
        SMAACatmullRomWeights( samplePositionX - texelPosition1X, weightsX );
        SMAACatmullRomWeights( samplePositionY - texelPosition1Y, weightsY );

        const float weight12X = weightsX[1] + weightsX[2];
        const float weight12Y = weightsY[1] + weightsY[2];
        const float offset12X = weightsX[2] / vaMath::Max( weight12X, 1.0e-6f );
        const float offset12Y = weightsY[2] / vaMath::Max( weight12Y, 1.0e-6f );
        const float texelPosition0X = texelPosition1X - 1.0f;
        const float texelPosition0Y = texelPosition1Y - 1.0f;
        const float texelPosition3X = texelPosition1X + 2.0f;
        const float texelPosition3Y = texelPosition1Y + 2.0f;
        const float texelPosition12X = texelPosition1X + offset12X;
        const float texelPosition12Y = texelPosition1Y + offset12Y;

        const float topWeight = weight12X * weightsY[0];
        const float leftWeight = weightsX[0] * weight12Y;
        const float centerWeight = weight12X * weight12Y;
        const float rightWeight = weightsX[3] * weight12Y;
        const float bottomWeight = weight12X * weightsY[3];
        const float totalWeight = topWeight + leftWeight + centerWeight + rightWeight + bottomWeight;

        SMAACatmullDiagnosticColor result = { 0.0f, 0.0f, 0.0f, 0.0f };
        result = SMAACatmullColorAdd( result, SMAACatmullColorScale(
            SMAACatmullSampleLinearClamp( source, width, height,
                texelPosition12X / (float)width, texelPosition0Y / (float)height ), topWeight ) );
        result = SMAACatmullColorAdd( result, SMAACatmullColorScale(
            SMAACatmullSampleLinearClamp( source, width, height,
                texelPosition0X / (float)width, texelPosition12Y / (float)height ), leftWeight ) );
        result = SMAACatmullColorAdd( result, SMAACatmullColorScale(
            SMAACatmullSampleLinearClamp( source, width, height,
                texelPosition12X / (float)width, texelPosition12Y / (float)height ), centerWeight ) );
        result = SMAACatmullColorAdd( result, SMAACatmullColorScale(
            SMAACatmullSampleLinearClamp( source, width, height,
                texelPosition3X / (float)width, texelPosition12Y / (float)height ), rightWeight ) );
        result = SMAACatmullColorAdd( result, SMAACatmullColorScale(
            SMAACatmullSampleLinearClamp( source, width, height,
                texelPosition12X / (float)width, texelPosition3Y / (float)height ), bottomWeight ) );
        return SMAACatmullColorScale( result, (vaMath::Abs( totalWeight ) > 1.0e-6f)? (1.0f / totalWeight) : 1.0f );
    }

    static SMAACatmullDiagnosticColor SMAACatmullSample16Tap(
        const SMAACatmullDiagnosticColor * source, int width, int height, float u, float v )
    {
        const float samplePositionX = u * (float)width;
        const float samplePositionY = v * (float)height;
        const int texelIndex1X = (int)std::floor( samplePositionX - 0.5f );
        const int texelIndex1Y = (int)std::floor( samplePositionY - 0.5f );
        float weightsX[4];
        float weightsY[4];
        SMAACatmullRomWeights( samplePositionX - ((float)texelIndex1X + 0.5f), weightsX );
        SMAACatmullRomWeights( samplePositionY - ((float)texelIndex1Y + 0.5f), weightsY );

        SMAACatmullDiagnosticColor result = { 0.0f, 0.0f, 0.0f, 0.0f };
        for( int y = 0; y < 4; y++ )
            for( int x = 0; x < 4; x++ )
                result = SMAACatmullColorAdd( result, SMAACatmullColorScale(
                    SMAACatmullReadClamped( source, width, height, texelIndex1X + x - 1, texelIndex1Y + y - 1 ),
                    weightsX[x] * weightsY[y] ) );
        return result;
    }

    struct TechniqueThingieDX11 : public SMAATechniqueInterface
    {
        // TechniqueThingieDX11( ) { }
        // virtual ~TechniqueThingieDX11( ) { }

        FLOAT                           BlendFactor[ 4 ];
        FLOAT *                         BlendFactorAltSource = nullptr;     // when BlendFactorAltSource is non-null, update BlendFactor values from it each time! warning - it's a ptr to single float, not an array
        UINT                            SampleMask;
        UINT                            StencilRef;

        ID3D11DepthStencilState *       DSS;
        ID3D11BlendState *              BS;

        vaAutoRMI<vaVertexShader>       VS;
        vaAutoRMI<vaPixelShader>        PS;

        TechniqueThingieDX11( const vaRenderingModuleParams & params ) : VS( params ), PS( params ) { }

        // SMAATechniqueInterface impl
        virtual void                    ApplyStates( ID3D11DeviceContext * context ) override;
    };

    

    class vaSMAAWrapperDX11 : public vaSMAAWrapper, public SMAAShaderConstantsInterface, public SMAATexturesInterface, public SMAATechniqueManagerInterface
    {
        VA_RENDERING_MODULE_MAKE_FRIENDS( );
    private:

        // States used by the effect passes
        ID3D11DepthStencilState *   m_DisableDepthStencil           = nullptr;
        ID3D11DepthStencilState *   m_DisableDepthReplaceStencil    = nullptr;
        ID3D11DepthStencilState *   m_DisableDepthUseStencil        = nullptr;
        ID3D11BlendState *          m_Blend                         = nullptr;
        ID3D11BlendState *          m_NoBlending                    = nullptr;

        ID3D11SamplerState *        m_LinearSampler                 = nullptr;
        ID3D11SamplerState *        m_PointSampler                  = nullptr;

        vector<shared_ptr<TechniqueThingieDX11>>
                                    m_techniques;

        SMAA *                      m_smaa                          = nullptr;
        int                         m_sampleCount                   = -1;       // need to re-create views if sample count changed

        shared_ptr<vaTexture>       m_texDepthStencil               = nullptr;

        shared_ptr<vaTexture>       m_externalInputColor            = nullptr;

        shared_ptr<vaTexture>       m_viewColor0                    = nullptr;
        shared_ptr<vaTexture>       m_viewColor1                    = nullptr;
        shared_ptr<vaTexture>       m_viewColorIgnoreSRGB0          = nullptr;
        shared_ptr<vaTexture>       m_viewColorIgnoreSRGB1          = nullptr;

        shared_ptr<vaTexture>       m_temporalHistory[2]            = { nullptr, nullptr };
        shared_ptr<vaTexture>       m_temporalSpatialCurrent        = nullptr;
        shared_ptr<vaTexture>       m_temporalVelocity              = nullptr;
        ID3D11Texture2D *           m_temporalVelocityReadback      = nullptr;
        bool                        m_temporalHistoryValid           = false;
        bool                        m_previousViewProjValid          = false;
        bool                        m_smaaReprojectionEnabled        = false;
        bool                        m_smaaEdgeSelectiveEnabled      = false;
        bool                        m_velocityDiagnosticsResourcesEnabled = false;
        vaMatrix4x4                 m_previousViewProj               = vaMatrix4x4::Identity;

        SMAAReprojectionConstants   m_reprojectionConstants;
        vaTypedConstantBufferWrapper<SMAAReprojectionConstants>
                                    m_reprojectionConstantsBuffer;
        vaAutoRMI<vaPixelShader>    m_generateCameraVelocityPS;
        vaAutoRMI<vaPixelShader>    m_tscmaaDebugMaskPS;
        vaAutoRMI<vaComputeShader>  m_tscmaaExtractCandidatesCS;
        vaAutoRMI<vaComputeShader>  m_tscmaaComputeDispatchArgsCS;
        vaAutoRMI<vaComputeShader>  m_tscmaaResolveCandidatesCS;
        vaAutoRMI<vaComputeShader>  m_tscmaaCatmullRomDiagnosticCS;

        shared_ptr<vaTexture>       m_tscmaaBaseEdgeMask             = nullptr;
        shared_ptr<vaTexture>       m_tscmaaCandidateMask            = nullptr;
        ID3D11Buffer *              m_tscmaaCandidatesBuffer        = nullptr;
        ID3D11UnorderedAccessView * m_tscmaaCandidatesUAV           = nullptr;
        ID3D11Buffer *              m_tscmaaCandidatesReadback      = nullptr;
        bool                        m_tscmaaCandidatesReadbackPending = false;
        uint32                      m_tscmaaCandidatesReadbackGeneration = 0;
        uint32                      m_tscmaaCandidateCapacity        = 0;
        ID3D11Buffer *              m_tscmaaControlBuffer           = nullptr;
        ID3D11UnorderedAccessView * m_tscmaaControlBufferUAV        = nullptr;
        ID3D11Buffer *              m_tscmaaDispatchArgsBuffer      = nullptr;
        ID3D11UnorderedAccessView * m_tscmaaDispatchArgsBufferUAV   = nullptr;
        static const int            c_tscmaaReadbackBufferCount      = 4;
        ID3D11Buffer *              m_tscmaaControlReadback[c_tscmaaReadbackBufferCount] = { nullptr, nullptr, nullptr, nullptr };
        bool                        m_tscmaaReadbackPending[c_tscmaaReadbackBufferCount] = { false, false, false, false };
        uint32                      m_tscmaaReadbackGeneration[c_tscmaaReadbackBufferCount] = { 0, 0, 0, 0 };
        int                         m_tscmaaReadbackCursor           = 0;
        uint32                      m_tscmaaStatisticsGeneration      = 1;
        bool                        m_tscmaaStatisticsLogged          = false;


        // m_scratchPostProcessColorIgnoreSRGBConvView = vaTexture::CreateView( *m_scratchPostProcessColor, m_scratchPostProcessColor->GetBindSupportFlags(), 
        //     vaResourceFormatHelpers::StripSRGB( m_scratchPostProcessColor->GetSRVFormat() ), vaResourceFormatHelpers::StripSRGB( m_scratchPostProcessColor->GetRTVFormat() ), vaResourceFormatHelpers::StripSRGB( m_scratchPostProcessColor->GetDSVFormat() ), vaResourceFormatHelpers::StripSRGB( m_scratchPostProcessColor->GetUAVFormat() ) );


    protected:
        explicit vaSMAAWrapperDX11( const vaRenderingModuleParams & params );
        ~vaSMAAWrapperDX11( );

    private:
        virtual vaDrawResultFlags       Draw( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor, const shared_ptr<vaTexture> & optionalInLuma = nullptr,
                                                const shared_ptr<vaTexture> & optionalDepth = nullptr, const vaCameraBase * optionalCamera = nullptr ) override;
        virtual void                    CleanupTemporaryResources( ) override;
        virtual void                    ResetTemporalHistory( ) override;

    private:
        bool                            UpdateResources( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor );
        vaDrawResultFlags               ExecuteTSCMAAInspiredResolve( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & currentSpatial,
                                                const shared_ptr<vaTexture> & previousHistory, const shared_ptr<vaTexture> & outputHistory,
                                                const shared_ptr<vaTexture> & luma, const shared_ptr<vaTexture> & destination );
        void                            QueueAndConsumeTSCMAAStatisticsReadback( ID3D11DeviceContext * context, uint32 width, uint32 height );
        void                            ReadbackTemporalVelocityDiagnostics( ID3D11DeviceContext * context, uint32 width, uint32 height );
        void                            RunCatmullRomDiagnostics( ID3D11DeviceContext * context );
        vaDrawResultFlags               DrawTSCMAADebugView( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & destination );
        //void                            Reset( );

        void                            SetGlobalStates( vaRenderDeviceContext & deviceContext );
        void                            UnsetGlobalStates( vaRenderDeviceContext & deviceContext );

    private:
        // SMAAShaderConstantsInterface impl
        virtual void                    SetVariablesA( ID3D11DeviceContext * context, float thresholdVariable, float cornerRoundingVariable, float maxSearchStepsVariable, float maxSearchStepsDiagVariable, float blendFactorVariable ) override;
        virtual void                    SetVariablesB( ID3D11DeviceContext * context, float subsampleIndicesVariable[4] ) override;
        // SMAATexturesInterface impl
        virtual void                    SetResource_areaTex        ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        virtual void                    SetResource_searchTex      ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        virtual void                    SetResource_colorTex       ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        virtual void                    SetResource_colorTexGamma  ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        virtual void                    SetResource_colorTexPrev   ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        virtual void                    SetResource_colorTexMS     ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        virtual void                    SetResource_depthTex       ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        virtual void                    SetResource_velocityTex    ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        virtual void                    SetResource_edgesTex       ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        virtual void                    SetResource_blendTex       ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) override;
        // SMAATechniqueManagerInterface impl
        virtual SMAATechniqueInterface* CreateTechnique( const char * name, const std::vector<D3D_SHADER_MACRO> & defines ) override;
        virtual void                    DestroyAllTechniques( ) override;
    };

    // there is no DX12 port yet so just stub it out here
    class vaSMAAWrapperDX12 : public vaSMAAWrapper
    {
        VA_RENDERING_MODULE_MAKE_FRIENDS( );

    public:
        explicit vaSMAAWrapperDX12( const vaRenderingModuleParams & params ) : vaSMAAWrapper( params ) { }
        ~vaSMAAWrapperDX12( ) { }

        // Applies SMAA to currently selected render target using provided inputs
        virtual vaDrawResultFlags   Draw( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor, const shared_ptr<vaTexture> & optionalInLuma = nullptr,
                                            const shared_ptr<vaTexture> & optionalDepth = nullptr, const vaCameraBase * optionalCamera = nullptr ) override
        { 
            // NOT IMPLEMENTED IN DX12
            deviceContext; inputColor, optionalInLuma, optionalDepth, optionalCamera;
            deviceContext.GetRenderTarget()->ClearRTV( deviceContext, vaVector4( 1.0f, 0.0f, 1.0f, 0.0f ) );
            return vaDrawResultFlags::None;  
        }

        // if SMAA is no longer used make sure it's not reserving any memory
        virtual void                CleanupTemporaryResources( ) override { }
    };


}

using namespace VertexAsylum;

static const bool c_useTypedUAVStores = false;

static HRESULT CreateSMAATemporalBufferAndUAV( ID3D11Device * device, const D3D11_BUFFER_DESC & bufferDesc,
    ID3D11Buffer ** buffer, ID3D11UnorderedAccessView ** uav, UINT uavFlags )
{
    HRESULT hr;
    ID3D11Buffer * temporaryBuffer = nullptr;
    ID3D11Buffer ** outputBuffer = (buffer != nullptr)? buffer : &temporaryBuffer;
    V_RETURN( device->CreateBuffer( &bufferDesc, nullptr, outputBuffer ) );

    D3D11_UNORDERED_ACCESS_VIEW_DESC uavDesc;
    ZeroMemory( &uavDesc, sizeof( uavDesc ) );
    uavDesc.Format = (bufferDesc.MiscFlags & D3D11_RESOURCE_MISC_BUFFER_STRUCTURED)? DXGI_FORMAT_UNKNOWN : DXGI_FORMAT_R32_UINT;
    if( (uavFlags & D3D11_BUFFER_UAV_FLAG_RAW) != 0 )
        uavDesc.Format = DXGI_FORMAT_R32_TYPELESS;
    uavDesc.ViewDimension = D3D11_UAV_DIMENSION_BUFFER;
    uavDesc.Buffer.FirstElement = 0;
    const UINT elementStride = (bufferDesc.MiscFlags & D3D11_RESOURCE_MISC_BUFFER_STRUCTURED)? bufferDesc.StructureByteStride : sizeof( UINT );
    uavDesc.Buffer.NumElements = bufferDesc.ByteWidth / elementStride;
    uavDesc.Buffer.Flags = uavFlags;
    V_RETURN( device->CreateUnorderedAccessView( *outputBuffer, &uavDesc, uav ) );

    SAFE_RELEASE( temporaryBuffer );
    return S_OK;
}

vaSMAAWrapperDX11::vaSMAAWrapperDX11( const vaRenderingModuleParams & params ) : vaSMAAWrapper( params ),
    m_reprojectionConstantsBuffer( params ), m_generateCameraVelocityPS( params.RenderDevice ), m_tscmaaDebugMaskPS( params.RenderDevice ),
    m_tscmaaExtractCandidatesCS( params.RenderDevice ), m_tscmaaComputeDispatchArgsCS( params.RenderDevice ),
    m_tscmaaResolveCandidatesCS( params.RenderDevice ), m_tscmaaCatmullRomDiagnosticCS( params.RenderDevice )
{
    params; // unreferenced

    ID3D11Device * device = params.RenderDevice.SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice();
    m_generateCameraVelocityPS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "ps_5_0", "DX10_SMAAGenerateCameraVelocityPS", {}, true );
    m_tscmaaDebugMaskPS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "ps_5_0", "TSCMAADebugMaskPS", {}, true );
    const vector<pair<string, string>> tscmaaShaderMacros = { { "SMAA_TSCMAA_COMPUTE", "1" } };
    m_tscmaaExtractCandidatesCS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "cs_5_0", "TSCMAAExtractCandidatesCS", tscmaaShaderMacros, true );
    m_tscmaaComputeDispatchArgsCS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "cs_5_0", "TSCMAAComputeDispatchArgsCS", tscmaaShaderMacros, true );
    m_tscmaaResolveCandidatesCS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "cs_5_0", "TSCMAAResolveCandidatesCS", tscmaaShaderMacros, true );
    m_tscmaaCatmullRomDiagnosticCS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "cs_5_0", "TSCMAACatmullRomDiagnosticCS", tscmaaShaderMacros, true );
    HRESULT hr;
    {
        CD3D11_DEPTH_STENCIL_DESC desc = CD3D11_DEPTH_STENCIL_DESC( CD3D11_DEFAULT( ) );
        desc.DepthEnable                = TRUE;
        desc.DepthFunc                  = D3D11_COMPARISON_ALWAYS;
        V( device->CreateDepthStencilState( &desc, &m_DisableDepthStencil ) );
    }
    {
        CD3D11_DEPTH_STENCIL_DESC desc = CD3D11_DEPTH_STENCIL_DESC( CD3D11_DEFAULT( ) );
        desc.DepthEnable                = FALSE;
        desc.StencilEnable              = TRUE;
        desc.FrontFace.StencilPassOp    = D3D11_STENCIL_OP_REPLACE;
        V( device->CreateDepthStencilState( &desc, &m_DisableDepthReplaceStencil ) );
    }
    {
        CD3D11_DEPTH_STENCIL_DESC desc = CD3D11_DEPTH_STENCIL_DESC( CD3D11_DEFAULT( ) );
        desc.DepthEnable                = FALSE;
        desc.StencilEnable              = TRUE;
        desc.FrontFace.StencilFunc      = D3D11_COMPARISON_EQUAL;
        V( device->CreateDepthStencilState( &desc, &m_DisableDepthUseStencil ) );
    }
    {
        CD3D11_BLEND_DESC desc = CD3D11_BLEND_DESC( CD3D11_DEFAULT( ) );
        desc.AlphaToCoverageEnable      = FALSE;
        desc.RenderTarget[0].BlendEnable= TRUE;
        desc.RenderTarget[0].SrcBlend   = D3D11_BLEND_BLEND_FACTOR;
        desc.RenderTarget[0].DestBlend  = D3D11_BLEND_INV_BLEND_FACTOR;
        desc.RenderTarget[0].BlendOp    = D3D11_BLEND_OP_ADD;

        V( device->CreateBlendState( &desc, &m_Blend ) );
    }
    {
        CD3D11_BLEND_DESC desc = CD3D11_BLEND_DESC( CD3D11_DEFAULT( ) );
        desc.AlphaToCoverageEnable      = FALSE;
        desc.RenderTarget[0].BlendEnable= FALSE;

        V( device->CreateBlendState( &desc, &m_NoBlending ) );
    }
    {
        CD3D11_SAMPLER_DESC desc = CD3D11_SAMPLER_DESC( CD3D11_DEFAULT() );

        desc.Filter = D3D11_FILTER_MIN_MAG_MIP_POINT;
        desc.AddressU = desc.AddressV = desc.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP;
        device->CreateSamplerState( &desc, &m_PointSampler );

        desc.Filter = D3D11_FILTER_MIN_MAG_MIP_LINEAR;
        desc.AddressU = desc.AddressV = desc.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP;
        device->CreateSamplerState( &desc, &m_LinearSampler );
     }
}

vaSMAAWrapperDX11::~vaSMAAWrapperDX11( )
{
    CleanupTemporaryResources();
    // Reset( );

    SAFE_RELEASE( m_DisableDepthStencil        );
    SAFE_RELEASE( m_DisableDepthReplaceStencil );
    SAFE_RELEASE( m_DisableDepthUseStencil     );
    SAFE_RELEASE( m_Blend                      );
    SAFE_RELEASE( m_NoBlending                 );
    SAFE_RELEASE( m_PointSampler    );
    SAFE_RELEASE( m_LinearSampler   );

    SAFE_DELETE( m_smaa );

    SAFE_DELETE( m_smaa );
}

void vaSMAAWrapperDX11::CleanupTemporaryResources( )
{
    SAFE_DELETE( m_smaa );
    m_externalInputColor = nullptr;
    m_texDepthStencil = nullptr;
    m_viewColor0 = nullptr;
    m_viewColor1 = nullptr;
    m_viewColorIgnoreSRGB0 = nullptr;
    m_viewColorIgnoreSRGB1 = nullptr;
    m_temporalHistory[0] = nullptr;
    m_temporalHistory[1] = nullptr;
    m_temporalSpatialCurrent = nullptr;
    m_temporalVelocity = nullptr;
    SAFE_RELEASE( m_temporalVelocityReadback );
    m_tscmaaBaseEdgeMask = nullptr;
    m_tscmaaCandidateMask = nullptr;
    m_smaaReprojectionEnabled = false;
    m_smaaEdgeSelectiveEnabled = false;
    m_velocityDiagnosticsResourcesEnabled = false;
    SAFE_RELEASE( m_tscmaaCandidatesUAV );
    SAFE_RELEASE( m_tscmaaCandidatesBuffer );
    SAFE_RELEASE( m_tscmaaCandidatesReadback );
    m_tscmaaCandidatesReadbackPending = false;
    m_tscmaaCandidatesReadbackGeneration = 0;
    m_tscmaaCandidateCapacity = 0;
    SAFE_RELEASE( m_tscmaaControlBufferUAV );
    SAFE_RELEASE( m_tscmaaControlBuffer );
    SAFE_RELEASE( m_tscmaaDispatchArgsBufferUAV );
    SAFE_RELEASE( m_tscmaaDispatchArgsBuffer );
    for( int i = 0; i < c_tscmaaReadbackBufferCount; i++ )
    {
        SAFE_RELEASE( m_tscmaaControlReadback[i] );
        m_tscmaaReadbackPending[i] = false;
        m_tscmaaReadbackGeneration[i] = 0;
    }
    m_tscmaaReadbackCursor = 0;
    ResetTemporalHistory( );
}

void vaSMAAWrapperDX11::ResetTemporalHistory( )
{
    vaSMAAWrapper::ResetTemporalHistory( );
    m_temporalHistoryValid = false;
    m_previousViewProjValid = false;
    m_temporalCandidateStatistics = TemporalCandidateStatistics( );
    m_temporalCandidateValidation = TemporalCandidateValidation( );
    m_tscmaaStatisticsGeneration++;
    m_tscmaaStatisticsLogged = false;
    m_tscmaaCandidatesReadbackPending = false;
    m_tscmaaCandidatesReadbackGeneration = 0;
    for( int i = 0; i < c_tscmaaReadbackBufferCount; i++ )
    {
        m_tscmaaReadbackPending[i] = false;
        m_tscmaaReadbackGeneration[i] = 0;
    }
    if( m_smaa != nullptr )
        m_smaa->resetFrame( );

    if( !GetTemporalModeEnabled( ) )
    {
        m_temporalHistory[0] = nullptr;
        m_temporalHistory[1] = nullptr;
        m_temporalSpatialCurrent = nullptr;
    }
}

bool vaSMAAWrapperDX11::UpdateResources( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor )
{
    // this should go to UpdateResources
    bool smaaPredication = false;   // search for SMAA_PREDICATION - this is for additional edge detection (depth-based, or etc.)
    bool smaaProjection = GetTemporalReprojectionEnabled( );
    bool edgeSelective = GetEdgeSelectiveTemporalEnabled( );
    assert( inputColor->GetSampleCount() == 1 ); // if MSAA we expect inputs in a resolved array
    assert( inputColor->GetArrayCount() == 1 || inputColor->GetArrayCount() == 2 ); // only 1 or 2 samples supported
    if( m_smaa == nullptr || m_smaa->getPreset( ) != m_settings.Preset || m_smaa->getWidth( ) != inputColor->GetSizeX( ) || m_smaa->getHeight( ) != inputColor->GetSizeY( ) || inputColor->GetArrayCount() != m_sampleCount || m_externalInputColor != inputColor
        || m_smaaReprojectionEnabled != smaaProjection
        || m_smaaEdgeSelectiveEnabled != edgeSelective
        || m_velocityDiagnosticsResourcesEnabled != GetTemporalVelocityDiagnosticsEnabled( )
        || (GetTemporalModeEnabled( ) && (m_temporalHistory[0] == nullptr || m_temporalHistory[1] == nullptr || ((smaaProjection || edgeSelective) && m_temporalVelocity == nullptr)
            || (GetTemporalVelocityDiagnosticsEnabled( ) && m_temporalVelocityReadback == nullptr)
            || (edgeSelective && (m_temporalSpatialCurrent == nullptr || m_tscmaaBaseEdgeMask == nullptr || m_tscmaaCandidateMask == nullptr
                || m_tscmaaCandidatesBuffer == nullptr || m_tscmaaCandidatesUAV == nullptr
                || (GetForcedCandidateCountEnabled( ) && m_tscmaaCandidatesReadback == nullptr)
                || m_tscmaaControlBufferUAV == nullptr || m_tscmaaDispatchArgsBufferUAV == nullptr)))) )
    {
        SAFE_DELETE( m_smaa );
        CleanupTemporaryResources( );
        SetGlobalStates( deviceContext );
        m_smaa = new SMAA( GetRenderDevice().SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice(), (SMAAShaderConstantsInterface*)this, (SMAATexturesInterface*)this, (SMAATechniqueManagerInterface*)this, inputColor->GetSizeX( ), inputColor->GetSizeY( ),
            ( SMAA::Preset )m_settings.Preset, smaaPredication, smaaProjection );
        m_smaaReprojectionEnabled = smaaProjection;
        m_smaaEdgeSelectiveEnabled = edgeSelective;
        m_velocityDiagnosticsResourcesEnabled = GetTemporalVelocityDiagnosticsEnabled( );
        UnsetGlobalStates( deviceContext );
        m_texDepthStencil = vaTexture::Create2D( GetRenderDevice(), vaResourceFormat::D24_UNORM_S8_UINT, m_smaa->getWidth( ), m_smaa->getHeight( ), 1, 1, 1, vaResourceBindSupportFlags::DepthStencil );
        m_externalInputColor = inputColor;

        m_sampleCount = inputColor->GetArrayCount();
        if( m_sampleCount == 1 )
        {
            m_viewColor0 = vaTexture::CreateView( inputColor, /*inputColor->GetBindSupportFlags()*/vaResourceBindSupportFlags::ShaderResource, inputColor->GetSRVFormat(),
                vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaTextureFlags::None, 0, 1, 0, 1 );
            m_viewColorIgnoreSRGB0 = vaTexture::CreateView( inputColor, /*inputColor->GetBindSupportFlags()*/vaResourceBindSupportFlags::ShaderResource, vaResourceFormatHelpers::StripSRGB( inputColor->GetSRVFormat( ) ),
                vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaTextureFlags::None, 0, 1, 0, 1 );
        }
        else
        {
            assert( m_sampleCount == 2 );
            m_viewColor0 = vaTexture::CreateView( inputColor, /*inputColor->GetBindSupportFlags()*/vaResourceBindSupportFlags::ShaderResource, inputColor->GetSRVFormat( ),
                vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaTextureFlags::None, 0, 1, 0, 1 );
            m_viewColorIgnoreSRGB0 = vaTexture::CreateView( inputColor, /*inputColor->GetBindSupportFlags()*/vaResourceBindSupportFlags::ShaderResource, vaResourceFormatHelpers::StripSRGB( inputColor->GetSRVFormat( ) ),
                vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaTextureFlags::None, 0, 1, 0, 1 );
            m_viewColor1 = vaTexture::CreateView( inputColor, /*inputColor->GetBindSupportFlags()*/vaResourceBindSupportFlags::ShaderResource, inputColor->GetSRVFormat( ),
                vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaTextureFlags::None, 0, 1, 1, 1 );
            m_viewColorIgnoreSRGB1 = vaTexture::CreateView( inputColor, /*inputColor->GetBindSupportFlags()*/vaResourceBindSupportFlags::ShaderResource, vaResourceFormatHelpers::StripSRGB( inputColor->GetSRVFormat( ) ),
                vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaResourceFormat::Automatic, vaTextureFlags::None, 0, 1, 1, 1 );
        }

        if( GetTemporalModeEnabled( ) )
        {
            assert( m_sampleCount == 1 );
            const vaResourceBindSupportFlags historyBindFlags = vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::ShaderResource
                | (edgeSelective? vaResourceBindSupportFlags::UnorderedAccess : vaResourceBindSupportFlags::None);
            const vaResourceFormat historyUAVFormat = edgeSelective? vaResourceFormatHelpers::StripSRGB( inputColor->GetSRVFormat( ) ) : vaResourceFormat::Unknown;
            for( int i = 0; i < 2; i++ )
            {
                m_temporalHistory[i] = vaTexture::Create2D( inputColor->GetRenderDevice(), inputColor->GetResourceFormat(), inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    historyBindFlags, vaResourceAccessFlags::Default, inputColor->GetSRVFormat(), inputColor->GetRTVFormat(), vaResourceFormat::Unknown, historyUAVFormat,
                    vaTextureFlags::None, inputColor->GetContentsType() );
            }
            if( smaaProjection || edgeSelective )
                m_temporalVelocity = vaTexture::Create2D( inputColor->GetRenderDevice(), vaResourceFormat::R16G16_FLOAT, inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    historyBindFlags, vaResourceAccessFlags::Default );

            if( GetTemporalVelocityDiagnosticsEnabled( ) && m_temporalVelocity != nullptr )
            {
                ID3D11Texture2D * velocityTexture = nullptr;
                HRESULT hr = m_temporalVelocity->SafeCast<vaTextureDX11*>( )->GetResource( )->QueryInterface(
                    __uuidof( ID3D11Texture2D ), reinterpret_cast<void **>( &velocityTexture ) );
                if( SUCCEEDED( hr ) )
                {
                    D3D11_TEXTURE2D_DESC readbackDesc;
                    velocityTexture->GetDesc( &readbackDesc );
                    readbackDesc.Usage = D3D11_USAGE_STAGING;
                    readbackDesc.BindFlags = 0;
                    readbackDesc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
                    readbackDesc.MiscFlags = 0;
                    hr = GetRenderDevice().SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice()->CreateTexture2D(
                        &readbackDesc, nullptr, &m_temporalVelocityReadback );
                    velocityTexture->Release( );
                }
                if( FAILED( hr ) )
                    return false;
            }

            if( edgeSelective )
            {
                const vaResourceBindSupportFlags spatialBindFlags = vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::ShaderResource;
                m_temporalSpatialCurrent = vaTexture::Create2D( inputColor->GetRenderDevice(), inputColor->GetResourceFormat(), inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    spatialBindFlags, vaResourceAccessFlags::Default, inputColor->GetSRVFormat(), inputColor->GetRTVFormat(), vaResourceFormat::Unknown, vaResourceFormat::Unknown,
                    vaTextureFlags::None, inputColor->GetContentsType() );
                const vaResourceBindSupportFlags maskBindFlags = vaResourceBindSupportFlags::ShaderResource | vaResourceBindSupportFlags::UnorderedAccess;
                m_tscmaaBaseEdgeMask = vaTexture::Create2D( inputColor->GetRenderDevice(), vaResourceFormat::R8_UNORM, inputColor->GetSizeX(), inputColor->GetSizeY(),
                    1, 1, 1, maskBindFlags, vaResourceAccessFlags::Default );
                m_tscmaaCandidateMask = vaTexture::Create2D( inputColor->GetRenderDevice(), vaResourceFormat::R8_UNORM, inputColor->GetSizeX(), inputColor->GetSizeY(),
                    1, 1, 1, maskBindFlags, vaResourceAccessFlags::Default );

                ID3D11Device * d3d11Device = GetRenderDevice().SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice();
                HRESULT hr;
                const UINT candidateCapacity = inputColor->GetSizeX() * inputColor->GetSizeY();
                m_tscmaaCandidateCapacity = candidateCapacity;
                {
                    CD3D11_BUFFER_DESC bufferDesc( candidateCapacity * sizeof( UINT ), D3D11_BIND_UNORDERED_ACCESS, D3D11_USAGE_DEFAULT, 0,
                        D3D11_RESOURCE_MISC_BUFFER_STRUCTURED, sizeof( UINT ) );
                    V( CreateSMAATemporalBufferAndUAV( d3d11Device, bufferDesc, &m_tscmaaCandidatesBuffer, &m_tscmaaCandidatesUAV, 0 ) );
                    if( GetForcedCandidateCountEnabled( ) )
                    {
                        CD3D11_BUFFER_DESC readbackDesc( bufferDesc.ByteWidth, 0, D3D11_USAGE_STAGING, D3D11_CPU_ACCESS_READ, 0, 0 );
                        V( d3d11Device->CreateBuffer( &readbackDesc, nullptr, &m_tscmaaCandidatesReadback ) );
                    }
                }
                {
                    CD3D11_BUFFER_DESC bufferDesc( 4 * sizeof( UINT ), D3D11_BIND_UNORDERED_ACCESS, D3D11_USAGE_DEFAULT, 0,
                        D3D11_RESOURCE_MISC_BUFFER_ALLOW_RAW_VIEWS, 0 );
                    V( CreateSMAATemporalBufferAndUAV( d3d11Device, bufferDesc, &m_tscmaaControlBuffer, &m_tscmaaControlBufferUAV, D3D11_BUFFER_UAV_FLAG_RAW ) );
                    CD3D11_BUFFER_DESC readbackDesc( 4 * sizeof( UINT ), 0, D3D11_USAGE_STAGING, D3D11_CPU_ACCESS_READ, 0, 0 );
                    for( int i = 0; i < c_tscmaaReadbackBufferCount; i++ )
                        V( d3d11Device->CreateBuffer( &readbackDesc, nullptr, &m_tscmaaControlReadback[i] ) );
                }
                {
                    CD3D11_BUFFER_DESC bufferDesc( 4 * sizeof( UINT ), D3D11_BIND_UNORDERED_ACCESS, D3D11_USAGE_DEFAULT, 0,
                        D3D11_RESOURCE_MISC_BUFFER_ALLOW_RAW_VIEWS | D3D11_RESOURCE_MISC_DRAWINDIRECT_ARGS, 0 );
                    V( CreateSMAATemporalBufferAndUAV( d3d11Device, bufferDesc, &m_tscmaaDispatchArgsBuffer, &m_tscmaaDispatchArgsBufferUAV, D3D11_BUFFER_UAV_FLAG_RAW ) );
                }
            }

            bool readbackBuffersReady = true;
            for( int i = 0; i < c_tscmaaReadbackBufferCount; i++ )
                readbackBuffersReady = readbackBuffersReady && (m_tscmaaControlReadback[i] != nullptr);
            if( m_temporalHistory[0] == nullptr || m_temporalHistory[1] == nullptr || ((smaaProjection || edgeSelective) && m_temporalVelocity == nullptr)
                || (GetTemporalVelocityDiagnosticsEnabled( ) && m_temporalVelocityReadback == nullptr)
                || (edgeSelective && (m_temporalSpatialCurrent == nullptr || m_tscmaaBaseEdgeMask == nullptr || m_tscmaaCandidateMask == nullptr
                    || m_tscmaaCandidatesBuffer == nullptr || m_tscmaaCandidatesUAV == nullptr
                    || (GetForcedCandidateCountEnabled( ) && m_tscmaaCandidatesReadback == nullptr)
                    || m_tscmaaControlBufferUAV == nullptr || m_tscmaaDispatchArgsBufferUAV == nullptr
                    || m_tscmaaDispatchArgsBuffer == nullptr || !readbackBuffersReady)) )
                return false;
        }
    }
    
    return true;
}

vaDrawResultFlags vaSMAAWrapperDX11::Draw( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor, const shared_ptr<vaTexture> & optionalInLuma,
    const shared_ptr<vaTexture> & optionalDepth, const vaCameraBase * optionalCamera )
{
    vaRenderDeviceContext::RenderOutputsState rtState = deviceContext.GetOutputs( );

    assert( rtState.RenderTargetCount == 1 );
    assert( rtState.RenderTargets[0] != nullptr );
    const shared_ptr<vaTexture> & dstRT = rtState.RenderTargets[0];

    deviceContext.SetRenderTarget( nullptr, nullptr, false );

    ID3D11DeviceContext * dx11Context = vaSaferStaticCast< vaRenderDeviceContextDX11 * >( &deviceContext )->GetDXContext( );

    if( !UpdateResources( deviceContext, inputColor ) )
    { assert( false ); return vaDrawResultFlags::UnspecifiedError; }

    for( const shared_ptr<TechniqueThingieDX11> technique : m_techniques )
    {
        if( !technique->PS->IsCreated( ) || !technique->VS->IsCreated( ) )
            { /*VA_WARN( "SMAA: Not all shaders compiled, can't run" );*/ return vaDrawResultFlags::ShadersStillCompiling; }
    }
    if( GetEdgeSelectiveTemporalEnabled( ) && (!m_tscmaaExtractCandidatesCS->IsCreated( ) || !m_tscmaaComputeDispatchArgsCS->IsCreated( )
        || !m_tscmaaResolveCandidatesCS->IsCreated( )
        || ((GetTemporalDebugView( ) == TemporalDebugView::BaseEdges || GetTemporalDebugView( ) == TemporalDebugView::SelectedCandidates)
            && !m_tscmaaDebugMaskPS->IsCreated( ))) )
        return vaDrawResultFlags::ShadersStillCompiling;

    if( GetCatmullRomDiagnosticPending( ) )
    {
        if( !m_tscmaaCatmullRomDiagnosticCS->IsCreated( ) )
            return vaDrawResultFlags::ShadersStillCompiling;
        RunCatmullRomDiagnostics( dx11Context );
    }

    const bool temporalReprojectionEnabled = GetTemporalReprojectionEnabled( );
    const bool edgeSelectiveTemporalEnabled = GetEdgeSelectiveTemporalEnabled( );
    const bool temporalLifecycleDiagnosticsEnabled = m_temporalLifecycleDiagnostics.Enabled && GetTemporalModeEnabled( );
    const int temporalFrameIndexBefore = GetTemporalFrameIndex( );
    const bool temporalHistoryValidBefore = m_temporalHistoryValid;
    const bool previousViewProjValidBefore = m_previousViewProjValid;
    if( temporalLifecycleDiagnosticsEnabled )
    {
        const int expectedFrameIndex = (int)(m_temporalLifecycleFramesSinceReset % 2);
        if( temporalFrameIndexBefore != expectedFrameIndex || m_smaa->getFrameIndex( ) != temporalFrameIndexBefore )
            m_temporalLifecycleDiagnostics.FrameIndexMismatchCount++;

        const bool expectedHistoryValid = m_temporalLifecycleFramesSinceReset > 0;
        if( temporalHistoryValidBefore != expectedHistoryValid )
            m_temporalLifecycleDiagnostics.HistoryStateMismatchCount++;

        if( m_temporalHistory[0] == nullptr || m_temporalHistory[1] == nullptr || m_temporalHistory[0] == m_temporalHistory[1] )
            m_temporalLifecycleDiagnostics.HistoryResourceMismatchCount++;

        const vaVector2 expectedJitter = GetTemporalJitterEnabled( )? GetTemporalJitterOffset( ) : vaVector2( 0.0f, 0.0f );
        vaVector2 actualJitter( 0.0f, 0.0f );
        if( optionalCamera != nullptr )
            actualJitter = const_cast<vaCameraBase *>( optionalCamera )->GetSubpixelOffset( );
        if( optionalCamera == nullptr || !vaVector2::NearEqual( actualJitter, expectedJitter, 1e-6f ) )
            m_temporalLifecycleDiagnostics.JitterMismatchCount++;

        m_temporalLifecycleDiagnostics.LastFrameIndexBefore = temporalFrameIndexBefore;
        m_temporalLifecycleDiagnostics.LastHistoryValidBefore = temporalHistoryValidBefore;
        m_temporalLifecycleDiagnostics.LastWasSeed = !temporalHistoryValidBefore;
        m_temporalLifecycleDiagnostics.LastUsedReprojection = temporalReprojectionEnabled;
        m_temporalLifecycleDiagnostics.LastJitter = actualJitter;
        m_temporalLifecycleDiagnostics.LastWidth = (uint32)inputColor->GetSizeX( );
        m_temporalLifecycleDiagnostics.LastHeight = (uint32)inputColor->GetSizeY( );
        m_temporalLastSubsampleIndicesValid = false;
    }

    vaMatrix4x4 currentUnjitteredViewProjForHistory = vaMatrix4x4::Identity;
    if( temporalReprojectionEnabled || edgeSelectiveTemporalEnabled )
    {
        const TemporalSettings & temporalSettings = GetTemporalSettings( );
        m_reprojectionConstants.CurrentViewProjInv = vaMatrix4x4::Identity;
        m_reprojectionConstants.CurrentUnjitteredViewProj = vaMatrix4x4::Identity;
        m_reprojectionConstants.PreviousViewProj = vaMatrix4x4::Identity;
        m_reprojectionConstants.TemporalResolution = vaVector4( (float)inputColor->GetSizeX( ), (float)inputColor->GetSizeY( ),
            1.0f / (float)inputColor->GetSizeX( ), 1.0f / (float)inputColor->GetSizeY( ) );
        m_reprojectionConstants.TSCMAAParams = vaVector4( temporalSettings.HistoryWeight, temporalSettings.NonDominantRemovalAmount,
            temporalReprojectionEnabled? 1.0f : 0.0f,
            vaResourceFormatHelpers::IsSRGB( inputColor->GetSRVFormat( ) )? 1.0f : 0.0f );
        const uint32 clampedForcedCandidateCount = vaMath::Min( GetForcedCandidateCount( ),
            (uint32)(inputColor->GetSizeX( ) * inputColor->GetSizeY( )) );
        m_reprojectionConstants.TSCMAACandidateParams = vaVector4( temporalSettings.EdgeThreshold, (float)(int)GetEffectiveCandidatePolicy( ),
            (float)clampedForcedCandidateCount, GetForcedCandidateCountEnabled( )? 1.0f : 0.0f );
        m_reprojectionConstants.TSCMAAResolveParams = vaVector4( (float)(int)GetEffectiveHistorySampler( ),
            (float)(int)GetEffectiveHistoryClipping( ), 0.0f, 0.0f );

        if( temporalReprojectionEnabled )
        {
            if( optionalDepth == nullptr || optionalCamera == nullptr || !m_generateCameraVelocityPS->IsCreated( ) )
                return vaDrawResultFlags::ShadersStillCompiling;

            const vaMatrix4x4 currentJitteredViewProj = optionalCamera->GetViewMatrix( ) * optionalCamera->GetProjMatrix( );
            vaCameraBase unjitteredCamera = *optionalCamera;
            vaVector2 zeroJitter( 0.0f, 0.0f );
            unjitteredCamera.SetSubpixelOffset( zeroJitter );
            unjitteredCamera.Tick( 0.0f, false );
            const vaMatrix4x4 currentUnjitteredViewProj = unjitteredCamera.GetViewMatrix( ) * unjitteredCamera.GetProjMatrix( );

            m_reprojectionConstants.CurrentViewProjInv = currentJitteredViewProj.Inverse( );
            m_reprojectionConstants.CurrentUnjitteredViewProj = currentUnjitteredViewProj;
            m_reprojectionConstants.PreviousViewProj = m_previousViewProjValid? m_previousViewProj : currentUnjitteredViewProj;
            currentUnjitteredViewProjForHistory = currentUnjitteredViewProj;

            if( temporalLifecycleDiagnosticsEnabled )
            {
                m_temporalLifecycleDiagnostics.ReprojectionFrameCount++;
                const bool matricesFinite = SMAATemporalMatrixIsFinite( m_reprojectionConstants.CurrentViewProjInv )
                    && SMAATemporalMatrixIsFinite( m_reprojectionConstants.CurrentUnjitteredViewProj )
                    && SMAATemporalMatrixIsFinite( m_reprojectionConstants.PreviousViewProj );
                const bool inverseMatches = vaMatrix4x4::NearEqual(
                    currentJitteredViewProj * m_reprojectionConstants.CurrentViewProjInv, vaMatrix4x4::Identity, 2e-3f );
                const bool firstFramePreviousMatches = previousViewProjValidBefore
                    || vaMatrix4x4::NearEqual( m_reprojectionConstants.PreviousViewProj,
                        m_reprojectionConstants.CurrentUnjitteredViewProj, 1e-5f );
                if( !matricesFinite || !inverseMatches || !firstFramePreviousMatches )
                    m_temporalLifecycleDiagnostics.MatrixMismatchCount++;
            }
        }

        m_reprojectionConstantsBuffer.Update( deviceContext, m_reprojectionConstants );
    }

    if( temporalReprojectionEnabled )
    {
        deviceContext.SetRenderTarget( m_temporalVelocity, nullptr, true );
        vaGraphicsItem velocityRenderItem;
        deviceContext.FillFullscreenPassRenderItem( velocityRenderItem );
        velocityRenderItem.ConstantBuffers[1] = m_reprojectionConstantsBuffer;
        velocityRenderItem.ShaderResourceViews[6] = optionalDepth;
        velocityRenderItem.PixelShader = m_generateCameraVelocityPS;
        const vaDrawResultFlags velocityResult = deviceContext.ExecuteSingleItem( velocityRenderItem );
        deviceContext.SetRenderTarget( nullptr, nullptr, false );
        if( velocityResult != vaDrawResultFlags::None )
            return velocityResult;

        if( GetTemporalVelocityDiagnosticsEnabled( ) )
            ReadbackTemporalVelocityDiagnostics( dx11Context, (uint32)inputColor->GetSizeX( ), (uint32)inputColor->GetSizeY( ) );

        m_previousViewProj = currentUnjitteredViewProjForHistory;
        m_previousViewProjValid = true;
    }

    SetGlobalStates( deviceContext );

    if( inputColor->GetArrayCount() == 1 )
    {
        ID3D11ShaderResourceView * colorGammaSRV = (optionalInLuma == nullptr)? m_viewColorIgnoreSRGB0->SafeCast<vaTextureDX11*>( )->GetSRV( ) : optionalInLuma->SafeCast<vaTextureDX11*>( )->GetSRV( );
        SMAA::Input inputMode = (optionalInLuma == nullptr)? SMAA::INPUT_LUMA : SMAA::INPUT_LUMA_RAW;

        if( GetTemporalModeEnabled( ) )
        {
            assert( m_temporalHistory[0] != nullptr && m_temporalHistory[1] != nullptr );
            assert( m_smaa->getFrameIndex( ) == GetTemporalFrameIndex( ) );

            const int currentIndex = GetTemporalFrameIndex( );
            const int previousIndex = 1 - currentIndex;
            shared_ptr<vaTexture> & currentHistory = m_temporalHistory[currentIndex];
            shared_ptr<vaTexture> & previousHistory = m_temporalHistory[previousIndex];

            ID3D11ShaderResourceView * spatialColorSRV = m_viewColor0->SafeCast<vaTextureDX11*>( )->GetSRV( );
            ID3D11DepthStencilView * depthDSV = m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV( );

            ID3D11ShaderResourceView * velocitySRV = GetTemporalReprojectionEnabled( )? m_temporalVelocity->SafeCast<vaTextureDX11*>( )->GetSRV( ) : nullptr;
            if( GetEdgeSelectiveTemporalEnabled( ) )
            {
                assert( m_temporalSpatialCurrent != nullptr );
                assert( optionalInLuma != nullptr );

                ID3D11RenderTargetView * currentSpatialRTV = m_temporalSpatialCurrent->SafeCast<vaTextureDX11*>( )->GetRTV( );
                // Intel's public TSCMAA material does not prescribe deliberate
                // subpixel projection jitter. Non-candidates use the current
                // spatial result directly, so a full-frame T2X jitter would
                // otherwise remain visible as a two-frame oscillation.
                m_smaa->go( dx11Context, colorGammaSRV, spatialColorSRV, nullptr, velocitySRV, currentSpatialRTV, depthDSV, inputMode, SMAA::MODE_SMAA_1X );

                const vaDrawResultFlags tscmaaResult = ExecuteTSCMAAInspiredResolve( deviceContext, m_temporalSpatialCurrent,
                    m_temporalHistoryValid? previousHistory : m_temporalSpatialCurrent, currentHistory, optionalInLuma, dstRT );
                if( tscmaaResult != vaDrawResultFlags::None )
                {
                    UnsetGlobalStates( deviceContext );
                    deviceContext.SetOutputs( rtState );
                    return tscmaaResult;
                }
            }
            else
            {
                vaTextureDX11 * currentHistoryDX11 = currentHistory->SafeCast<vaTextureDX11*>( );
                ID3D11RenderTargetView * currentHistoryRTV = currentHistoryDX11->GetRTV( );
                m_smaa->go( dx11Context, colorGammaSRV, spatialColorSRV, nullptr, velocitySRV, currentHistoryRTV, depthDSV, inputMode, SMAA::MODE_SMAA_T2X );

                ID3D11ShaderResourceView * currentHistorySRV = currentHistory->SafeCast<vaTextureDX11*>( )->GetSRV( );
                ID3D11ShaderResourceView * previousHistorySRV = m_temporalHistoryValid? previousHistory->SafeCast<vaTextureDX11*>( )->GetSRV( ) : currentHistorySRV;
                m_smaa->reproject( dx11Context, currentHistorySRV, previousHistorySRV, velocitySRV, dstRT->SafeCast<vaTextureDX11*>( )->GetRTV( ) );
            }

            m_temporalHistoryValid = true;
            m_smaa->nextFrame( );
            AdvanceTemporalFrame( );

            if( temporalLifecycleDiagnosticsEnabled )
            {
                const vaVector4 expectedSubsampleIndices = edgeSelectiveTemporalEnabled?
                    vaVector4( 0.0f, 0.0f, 0.0f, 0.0f ) :
                    ((temporalFrameIndexBefore == 0)? vaVector4( 1.0f, 1.0f, 1.0f, 0.0f ) : vaVector4( 2.0f, 2.0f, 2.0f, 0.0f ));
                if( !m_temporalLastSubsampleIndicesValid
                    || !SMAATemporalSubsampleIndicesMatch( m_temporalLastSubsampleIndices, expectedSubsampleIndices ) )
                    m_temporalLifecycleDiagnostics.SubsampleMismatchCount++;

                const int expectedFrameIndexAfter = 1 - temporalFrameIndexBefore;
                if( GetTemporalFrameIndex( ) != expectedFrameIndexAfter || m_smaa->getFrameIndex( ) != expectedFrameIndexAfter )
                    m_temporalLifecycleDiagnostics.FrameIndexMismatchCount++;

                m_temporalLifecycleDiagnostics.CompletedFrameCount++;
                if( temporalHistoryValidBefore )
                    m_temporalLifecycleDiagnostics.ResolvedFrameCount++;
                else
                    m_temporalLifecycleDiagnostics.SeedFrameCount++;
                m_temporalLifecycleDiagnostics.LastFrameIndexAfter = GetTemporalFrameIndex( );
                m_temporalLifecycleDiagnostics.LastSubsampleIndices = vaVector4(
                    m_temporalLastSubsampleIndices[0], m_temporalLastSubsampleIndices[1],
                    m_temporalLastSubsampleIndices[2], m_temporalLastSubsampleIndices[3] );
                m_temporalLifecycleFramesSinceReset++;
                m_temporalLifecycleDiagnostics.Passed = m_temporalLifecycleDiagnostics.GetFailureCount( ) == 0;

                if( m_temporalLifecycleFramesSinceReset <= 2 || !m_temporalLifecycleDiagnostics.Passed )
                {
                    VA_LOG( "SMAA temporal lifecycle: frame=%d->%d, history=%s, historyRT=%d/%d, jitter=(%.3f, %.3f), subsample=(%.0f, %.0f, %.0f, %.0f), reprojection=%s, size=%ux%u => %s",
                        temporalFrameIndexBefore, GetTemporalFrameIndex( ),
                        temporalHistoryValidBefore? "resolve" : "seed",
                        temporalFrameIndexBefore, 1 - temporalFrameIndexBefore,
                        m_temporalLifecycleDiagnostics.LastJitter.x, m_temporalLifecycleDiagnostics.LastJitter.y,
                        m_temporalLastSubsampleIndices[0], m_temporalLastSubsampleIndices[1],
                        m_temporalLastSubsampleIndices[2], m_temporalLastSubsampleIndices[3],
                        temporalReprojectionEnabled? "camera-depth-matrices" : "off",
                        m_temporalLifecycleDiagnostics.LastWidth, m_temporalLifecycleDiagnostics.LastHeight,
                        m_temporalLifecycleDiagnostics.Passed? "PASS" : "FAIL" );
                }
            }
        }
        else
        {
            m_smaa->go( dx11Context, colorGammaSRV, m_viewColor0->SafeCast<vaTextureDX11*>( )->GetSRV( ), nullptr, nullptr,
                dstRT->SafeCast<vaTextureDX11*>( )->GetRTV( ), m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV(), inputMode, SMAA::MODE_SMAA_1X );
        }
    }
    else
    {
        m_smaa->go( dx11Context, m_viewColorIgnoreSRGB0->SafeCast<vaTextureDX11*>( )->GetSRV( ), m_viewColor0->SafeCast<vaTextureDX11*>( )->GetSRV( ), nullptr, nullptr, dstRT->SafeCast<vaTextureDX11*>( )->GetRTV( ), m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV( ),
            SMAA::INPUT_LUMA, SMAA::MODE_SMAA_S2X, 0 );
        m_smaa->go( dx11Context, m_viewColorIgnoreSRGB1->SafeCast<vaTextureDX11*>( )->GetSRV( ), m_viewColor1->SafeCast<vaTextureDX11*>( )->GetSRV( ), nullptr, nullptr, dstRT->SafeCast<vaTextureDX11*>( )->GetRTV( ), m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV( ),
            SMAA::INPUT_LUMA, SMAA::MODE_SMAA_S2X, 1 );
    }

    UnsetGlobalStates( deviceContext );

    // restore previous RTs
    deviceContext.SetOutputs( rtState );

    return vaDrawResultFlags::None;
}

vaDrawResultFlags vaSMAAWrapperDX11::ExecuteTSCMAAInspiredResolve( vaRenderDeviceContext & deviceContext,
    const shared_ptr<vaTexture> & currentSpatial, const shared_ptr<vaTexture> & previousHistory,
    const shared_ptr<vaTexture> & outputHistory, const shared_ptr<vaTexture> & luma,
    const shared_ptr<vaTexture> & destination )
{
    assert( currentSpatial != nullptr && previousHistory != nullptr && outputHistory != nullptr && luma != nullptr && destination != nullptr );
    assert( m_temporalVelocity != nullptr && m_smaa != nullptr );

    ID3D11DeviceContext * dx11Context = deviceContext.SafeCast<vaRenderDeviceContextDX11*>( )->GetDXContext( );
    vaTextureDX11 * currentSpatialDX11 = currentSpatial->SafeCast<vaTextureDX11*>( );
    vaTextureDX11 * previousHistoryDX11 = previousHistory->SafeCast<vaTextureDX11*>( );
    vaTextureDX11 * outputHistoryDX11 = outputHistory->SafeCast<vaTextureDX11*>( );
    vaTextureDX11 * destinationDX11 = destination->SafeCast<vaTextureDX11*>( );

    // Non-candidate pixels keep the current spatial SMAA value. Candidate
    // threads overwrite only their own pixels below.
    {
        VA_SCOPE_CPUGPU_TIMER( TSCMAAInitializeHistory, deviceContext );
        dx11Context->CopyResource( outputHistoryDX11->GetResource( ), currentSpatialDX11->GetResource( ) );
    }

    // The first valid frame seeds history without reading stale data.
    if( !m_temporalHistoryValid )
    {
        dx11Context->CopyResource( destinationDX11->GetResource( ), outputHistoryDX11->GetResource( ) );
        return vaDrawResultFlags::None;
    }

    ID3D11ComputeShader * extractCandidatesShader = m_tscmaaExtractCandidatesCS->SafeCast<vaComputeShaderDX11*>( )->GetShader( );
    ID3D11ComputeShader * computeDispatchArgsShader = m_tscmaaComputeDispatchArgsCS->SafeCast<vaComputeShaderDX11*>( )->GetShader( );
    ID3D11ComputeShader * resolveCandidatesShader = m_tscmaaResolveCandidatesCS->SafeCast<vaComputeShaderDX11*>( )->GetShader( );
    if( extractCandidatesShader == nullptr || computeDispatchArgsShader == nullptr || resolveCandidatesShader == nullptr )
        return vaDrawResultFlags::ShadersStillCompiling;

    ID3D11UnorderedAccessView * UAVs[6] =
    {
        outputHistoryDX11->GetUAV( ),
        m_tscmaaCandidatesUAV,
        m_tscmaaControlBufferUAV,
        m_tscmaaDispatchArgsBufferUAV,
        m_tscmaaBaseEdgeMask->SafeCast<vaTextureDX11*>( )->GetUAV( ),
        m_tscmaaCandidateMask->SafeCast<vaTextureDX11*>( )->GetUAV( )
    };
    ID3D11UnorderedAccessView * nullUAVs[6] = { nullptr, nullptr, nullptr, nullptr, nullptr, nullptr };
    if( UAVs[0] == nullptr || UAVs[4] == nullptr || UAVs[5] == nullptr )
        return vaDrawResultFlags::UnspecifiedError;

    ID3D11ShaderResourceView * SRVs[6] =
    {
        m_temporalVelocity->SafeCast<vaTextureDX11*>( )->GetSRV( ),
        *m_smaa->getEdgesRenderTarget( ),
        nullptr,
        currentSpatialDX11->GetSRV( ),
        previousHistoryDX11->GetSRV( ),
        luma->SafeCast<vaTextureDX11*>( )->GetSRV( )
    };
    ID3D11ShaderResourceView * nullSRVs[6] = { nullptr, nullptr, nullptr, nullptr, nullptr, nullptr };

    const UINT zeroes[4] = { 0, 0, 0, 0 };
    const FLOAT maskZeroes[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
    dx11Context->ClearUnorderedAccessViewUint( m_tscmaaControlBufferUAV, zeroes );
    dx11Context->ClearUnorderedAccessViewUint( m_tscmaaDispatchArgsBufferUAV, zeroes );
    dx11Context->ClearUnorderedAccessViewFloat( UAVs[4], maskZeroes );
    dx11Context->ClearUnorderedAccessViewFloat( UAVs[5], maskZeroes );

    ID3D11SamplerState * samplers[2] = { m_LinearSampler, m_PointSampler };
    dx11Context->CSSetSamplers( 0, 2, samplers );

    ID3D11Buffer * reprojectionConstants = m_reprojectionConstantsBuffer.GetBuffer()->SafeCast<vaConstantBufferDX11*>( )->GetBuffer( );
    dx11Context->CSSetConstantBuffers( 1, 1, &reprojectionConstants );
    dx11Context->CSSetUnorderedAccessViews( 0, _countof( UAVs ), UAVs, nullptr );
    dx11Context->CSSetShaderResources( 7, _countof( SRVs ), SRVs );

    {
        VA_SCOPE_CPUGPU_TIMER( TSCMAAExtractCandidates, deviceContext );
        dx11Context->CSSetShader( extractCandidatesShader, nullptr, 0 );
        dx11Context->Dispatch( (currentSpatial->GetSizeX( ) + 7) / 8, (currentSpatial->GetSizeY( ) + 7) / 8, 1 );
    }

    {
        VA_SCOPE_CPUGPU_TIMER( TSCMAAComputeDispatchArgs, deviceContext );
        dx11Context->CSSetShader( computeDispatchArgsShader, nullptr, 0 );
        dx11Context->Dispatch( 1, 1, 1 );
    }

    {
        VA_SCOPE_CPUGPU_TIMER( TSCMAAResolveCandidates, deviceContext );
        dx11Context->CSSetShader( resolveCandidatesShader, nullptr, 0 );
        dx11Context->DispatchIndirect( m_tscmaaDispatchArgsBuffer, 0 );
    }

    dx11Context->CSSetShader( nullptr, nullptr, 0 );
    dx11Context->CSSetUnorderedAccessViews( 0, _countof( nullUAVs ), nullUAVs, nullptr );
    dx11Context->CSSetShaderResources( 7, _countof( nullSRVs ), nullSRVs );

    ID3D11Buffer * nullConstantBuffer = nullptr;
    dx11Context->CSSetConstantBuffers( 1, 1, &nullConstantBuffer );
    ID3D11SamplerState * nullSamplers[2] = { nullptr, nullptr };
    dx11Context->CSSetSamplers( 0, 2, nullSamplers );
    QueueAndConsumeTSCMAAStatisticsReadback( dx11Context, (uint32)currentSpatial->GetSizeX( ), (uint32)currentSpatial->GetSizeY( ) );

    {
        VA_SCOPE_CPUGPU_TIMER( TSCMAAOutputCopy, deviceContext );
        dx11Context->CopyResource( destinationDX11->GetResource( ), outputHistoryDX11->GetResource( ) );
    }

    return DrawTSCMAADebugView( deviceContext, destination );
}

void vaSMAAWrapperDX11::ReadbackTemporalVelocityDiagnostics( ID3D11DeviceContext * context, uint32 width, uint32 height )
{
    if( !m_temporalVelocityDiagnosticPending || m_temporalVelocityReadback == nullptr || m_temporalVelocity == nullptr
        || GetTemporalVelocityDiagnosticMode( ) == TemporalVelocityDiagnosticMode::Disabled )
        return;

    m_temporalVelocityDiagnostics = TemporalVelocityDiagnostics( );
    m_temporalVelocityDiagnostics.Mode = GetTemporalVelocityDiagnosticMode( );
    context->CopyResource( m_temporalVelocityReadback, m_temporalVelocity->SafeCast<vaTextureDX11*>( )->GetResource( ) );
    D3D11_MAPPED_SUBRESOURCE mapped;
    ZeroMemory( &mapped, sizeof( mapped ) );
    const HRESULT mapResult = context->Map( m_temporalVelocityReadback, 0, D3D11_MAP_READ, 0, &mapped );
    if( FAILED( mapResult ) )
        return;

    const uint32 pixelCount = width * height;
    uint32 finitePixelCount = 0;
    uint32 significantXCount = 0;
    uint32 expectedNegativeXCount = 0;
    uint32 historyUVInBoundsCount = 0;
    double velocitySumX = 0.0;
    double velocitySumY = 0.0;
    float minimumX = std::numeric_limits<float>::max( );
    float minimumY = std::numeric_limits<float>::max( );
    float maximumX = -std::numeric_limits<float>::max( );
    float maximumY = -std::numeric_limits<float>::max( );
    float maximumAbsoluteVelocity = 0.0f;

    for( uint32 y = 0; y < height; y++ )
    {
        const uint16 * row = reinterpret_cast<const uint16 *>( reinterpret_cast<const uint8 *>( mapped.pData ) + y * mapped.RowPitch );
        for( uint32 x = 0; x < width; x++ )
        {
            const float velocityX = DirectX::PackedVector::XMConvertHalfToFloat( row[x * 2 + 0] );
            const float velocityY = DirectX::PackedVector::XMConvertHalfToFloat( row[x * 2 + 1] );
            if( !std::isfinite( velocityX ) || !std::isfinite( velocityY ) )
                continue;

            finitePixelCount++;
            velocitySumX += velocityX;
            velocitySumY += velocityY;
            minimumX = vaMath::Min( minimumX, velocityX );
            minimumY = vaMath::Min( minimumY, velocityY );
            maximumX = vaMath::Max( maximumX, velocityX );
            maximumY = vaMath::Max( maximumY, velocityY );
            maximumAbsoluteVelocity = vaMath::Max( maximumAbsoluteVelocity,
                vaMath::Max( vaMath::Abs( velocityX ), vaMath::Abs( velocityY ) ) );

            if( vaMath::Abs( velocityX ) > 1e-5f )
            {
                significantXCount++;
                if( velocityX < 0.0f )
                    expectedNegativeXCount++;
            }

            const float currentU = ((float)x + 0.5f) / (float)width;
            const float currentV = ((float)y + 0.5f) / (float)height;
            const float historyU = currentU - velocityX;
            const float historyV = currentV - velocityY;
            if( historyU > 0.0f && historyU < 1.0f && historyV > 0.0f && historyV < 1.0f )
                historyUVInBoundsCount++;
        }
    }
    context->Unmap( m_temporalVelocityReadback, 0 );
    m_temporalVelocityDiagnosticPending = false;

    m_temporalVelocityDiagnostics.Valid = true;
    m_temporalVelocityDiagnostics.PixelCount = pixelCount;
    m_temporalVelocityDiagnostics.FinitePixelCount = finitePixelCount;
    m_temporalVelocityDiagnostics.SignificantXCount = significantXCount;
    m_temporalVelocityDiagnostics.ExpectedNegativeXCount = expectedNegativeXCount;
    m_temporalVelocityDiagnostics.HistoryUVInBoundsCount = historyUVInBoundsCount;
    if( finitePixelCount > 0 )
    {
        m_temporalVelocityDiagnostics.MeanVelocity = vaVector2(
            (float)(velocitySumX / (double)finitePixelCount), (float)(velocitySumY / (double)finitePixelCount) );
        m_temporalVelocityDiagnostics.MinimumVelocity = vaVector2( minimumX, minimumY );
        m_temporalVelocityDiagnostics.MaximumVelocity = vaVector2( maximumX, maximumY );
    }
    m_temporalVelocityDiagnostics.MaximumAbsoluteVelocity = maximumAbsoluteVelocity;

    switch( m_temporalVelocityDiagnostics.Mode )
    {
    case TemporalVelocityDiagnosticMode::StaticCameraZero:
        m_temporalVelocityDiagnostics.Passed = finitePixelCount == pixelCount
            && maximumAbsoluteVelocity <= 2e-4f
            && historyUVInBoundsCount == finitePixelCount;
        break;
    case TemporalVelocityDiagnosticMode::CameraRightTranslation:
        m_temporalVelocityDiagnostics.Passed = finitePixelCount == pixelCount
            && significantXCount >= pixelCount / 4
            && m_temporalVelocityDiagnostics.GetExpectedNegativeXRatio( ) >= 0.95f
            && m_temporalVelocityDiagnostics.MeanVelocity.x < -1e-5f
            && m_temporalVelocityDiagnostics.GetHistoryUVInBoundsRatio( ) >= 0.95f;
        break;
    default:
        m_temporalVelocityDiagnostics.Passed = false;
        break;
    }

    const char * modeName = (m_temporalVelocityDiagnostics.Mode == TemporalVelocityDiagnosticMode::StaticCameraZero)?
        "static-zero" : "camera-right";
    VA_LOG( "SMAA GPU velocity diagnostics [%s]: finite=%u/%u, mean=(%.8f, %.8f), rangeX=[%.8f, %.8f], maxAbs=%.8f, negativeX=%u/%u (%.3f%%), historyUVInBounds=%u/%u (%.3f%%) => %s",
        modeName, finitePixelCount, pixelCount,
        m_temporalVelocityDiagnostics.MeanVelocity.x, m_temporalVelocityDiagnostics.MeanVelocity.y,
        m_temporalVelocityDiagnostics.MinimumVelocity.x, m_temporalVelocityDiagnostics.MaximumVelocity.x,
        maximumAbsoluteVelocity, expectedNegativeXCount, significantXCount,
        100.0f * m_temporalVelocityDiagnostics.GetExpectedNegativeXRatio( ),
        historyUVInBoundsCount, finitePixelCount,
        100.0f * m_temporalVelocityDiagnostics.GetHistoryUVInBoundsRatio( ),
        m_temporalVelocityDiagnostics.Passed? "PASS" : "FAIL" );
}

void vaSMAAWrapperDX11::RunCatmullRomDiagnostics( ID3D11DeviceContext * context )
{
    static const int sourceWidth = 8;
    static const int sourceHeight = 8;
    static const int outputWidth = 16;
    static const int outputHeight = 16;
    static const int cpuReferenceGridSize = 64;
    static_assert( sizeof( SMAACatmullDiagnosticColor ) == sizeof( float ) * 4, "Unexpected diagnostic color layout" );

    m_catmullRomDiagnosticPending = false;
    m_catmullRomDiagnostics = CatmullRomDiagnostics( );

    std::array<SMAACatmullDiagnosticColor, sourceWidth * sourceHeight> sourceData;
    for( int y = 0; y < sourceHeight; y++ )
    {
        for( int x = 0; x < sourceWidth; x++ )
        {
            const float pseudoRandom = (float)((x * 37 + y * 17 + x * y * 13) % 101) / 100.0f;
            const float planarGradient = (float)(x + y * 2) / (float)((sourceWidth - 1) + (sourceHeight - 1) * 2);
            sourceData[y * sourceWidth + x] = { pseudoRandom, planarGradient, 0.375f, 1.0f };
        }
    }

    for( int fractionIndex = 0; fractionIndex <= 4096; fractionIndex++ )
    {
        const float fraction = (float)fractionIndex / 4096.0f;
        float weights[4];
        float mirroredWeights[4];
        SMAACatmullRomWeights( fraction, weights );
        SMAACatmullRomWeights( 1.0f - fraction, mirroredWeights );
        const float weightSum = weights[0] + weights[1] + weights[2] + weights[3];
        m_catmullRomDiagnostics.MaximumWeightSumError = vaMath::Max(
            m_catmullRomDiagnostics.MaximumWeightSumError, vaMath::Abs( weightSum - 1.0f ) );
        for( int weightIndex = 0; weightIndex < 4; weightIndex++ )
        {
            m_catmullRomDiagnostics.MaximumSymmetryError = vaMath::Max(
                m_catmullRomDiagnostics.MaximumSymmetryError,
                vaMath::Abs( weights[weightIndex] - mirroredWeights[3 - weightIndex] ) );
        }
    }
    for( int fractionYIndex = 0; fractionYIndex <= 256; fractionYIndex++ )
    {
        float weightsY[4];
        SMAACatmullRomWeights( (float)fractionYIndex / 256.0f, weightsY );
        for( int fractionXIndex = 0; fractionXIndex <= 256; fractionXIndex++ )
        {
            float weightsX[4];
            SMAACatmullRomWeights( (float)fractionXIndex / 256.0f, weightsX );
            const float weight12X = weightsX[1] + weightsX[2];
            const float weight12Y = weightsY[1] + weightsY[2];
            const float topWeight = weight12X * weightsY[0];
            const float leftWeight = weightsX[0] * weight12Y;
            const float centerWeight = weight12X * weight12Y;
            const float rightWeight = weightsX[3] * weight12Y;
            const float bottomWeight = weight12X * weightsY[3];
            const float totalWeight = topWeight + leftWeight + centerWeight + rightWeight + bottomWeight;
            const float normalizedWeightSum = (vaMath::Abs( totalWeight ) > 1.0e-6f)?
                ((topWeight + leftWeight + centerWeight + rightWeight + bottomWeight) / totalWeight) : 0.0f;
            m_catmullRomDiagnostics.MaximumWeightSumError = vaMath::Max(
                m_catmullRomDiagnostics.MaximumWeightSumError, vaMath::Abs( normalizedWeightSum - 1.0f ) );
        }
    }

    double cpuReferenceSquaredError = 0.0;
    for( int y = 0; y < cpuReferenceGridSize; y++ )
    {
        for( int x = 0; x < cpuReferenceGridSize; x++ )
        {
            const float u = ((float)x + 0.37f) / (float)cpuReferenceGridSize;
            const float v = ((float)y + 0.63f) / (float)cpuReferenceGridSize;
            const SMAACatmullDiagnosticColor approximation = SMAACatmullSample5Tap(
                sourceData.data( ), sourceWidth, sourceHeight, u, v );
            const SMAACatmullDiagnosticColor reference = SMAACatmullSample16Tap(
                sourceData.data( ), sourceWidth, sourceHeight, u, v );
            m_catmullRomDiagnostics.CPU5TapTo16TapMaximumError = vaMath::Max(
                m_catmullRomDiagnostics.CPU5TapTo16TapMaximumError,
                SMAACatmullColorMaximumAbsoluteDifference( approximation, reference ) );
            cpuReferenceSquaredError += SMAACatmullColorSquaredDifference( approximation, reference );
        }
    }
    m_catmullRomDiagnostics.CPUReferenceSampleCount = cpuReferenceGridSize * cpuReferenceGridSize;
    m_catmullRomDiagnostics.CPU5TapTo16TapRMSE = (float)std::sqrt(
        cpuReferenceSquaredError / (double)(m_catmullRomDiagnostics.CPUReferenceSampleCount * 4) );

    ID3D11Device * device = GetRenderDevice().SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice( );
    ComPtr<ID3D11Texture2D> sourceTexture;
    ComPtr<ID3D11ShaderResourceView> sourceSRV;
    ComPtr<ID3D11Texture2D> outputTexture;
    ComPtr<ID3D11UnorderedAccessView> outputUAV;
    ComPtr<ID3D11Texture2D> outputReadback;

    D3D11_TEXTURE2D_DESC sourceDesc;
    ZeroMemory( &sourceDesc, sizeof( sourceDesc ) );
    sourceDesc.Width = sourceWidth;
    sourceDesc.Height = sourceHeight;
    sourceDesc.MipLevels = 1;
    sourceDesc.ArraySize = 1;
    sourceDesc.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
    sourceDesc.SampleDesc.Count = 1;
    sourceDesc.Usage = D3D11_USAGE_IMMUTABLE;
    sourceDesc.BindFlags = D3D11_BIND_SHADER_RESOURCE;
    D3D11_SUBRESOURCE_DATA sourceInitialData;
    ZeroMemory( &sourceInitialData, sizeof( sourceInitialData ) );
    sourceInitialData.pSysMem = sourceData.data( );
    sourceInitialData.SysMemPitch = sourceWidth * sizeof( SMAACatmullDiagnosticColor );

    HRESULT result = device->CreateTexture2D( &sourceDesc, &sourceInitialData, sourceTexture.GetAddressOf( ) );
    if( SUCCEEDED( result ) )
        result = device->CreateShaderResourceView( sourceTexture.Get( ), nullptr, sourceSRV.GetAddressOf( ) );

    D3D11_TEXTURE2D_DESC outputDesc;
    ZeroMemory( &outputDesc, sizeof( outputDesc ) );
    outputDesc.Width = outputWidth;
    outputDesc.Height = outputHeight;
    outputDesc.MipLevels = 1;
    outputDesc.ArraySize = 1;
    outputDesc.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
    outputDesc.SampleDesc.Count = 1;
    outputDesc.Usage = D3D11_USAGE_DEFAULT;
    outputDesc.BindFlags = D3D11_BIND_UNORDERED_ACCESS;
    if( SUCCEEDED( result ) )
        result = device->CreateTexture2D( &outputDesc, nullptr, outputTexture.GetAddressOf( ) );
    if( SUCCEEDED( result ) )
        result = device->CreateUnorderedAccessView( outputTexture.Get( ), nullptr, outputUAV.GetAddressOf( ) );

    D3D11_TEXTURE2D_DESC readbackDesc = outputDesc;
    readbackDesc.Usage = D3D11_USAGE_STAGING;
    readbackDesc.BindFlags = 0;
    readbackDesc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    if( SUCCEEDED( result ) )
        result = device->CreateTexture2D( &readbackDesc, nullptr, outputReadback.GetAddressOf( ) );

    ID3D11ComputeShader * diagnosticShader =
        m_tscmaaCatmullRomDiagnosticCS->SafeCast<vaComputeShaderDX11*>( )->GetShader( );
    if( FAILED( result ) || diagnosticShader == nullptr )
    {
        m_catmullRomDiagnostics.Valid = true;
        m_catmullRomDiagnostics.Passed = false;
        VA_LOG_ERROR( "SMAA Catmull-Rom diagnostic resource/shader creation failed (HRESULT 0x%08X)", (uint32)result );
        return;
    }

    ID3D11ShaderResourceView * sourceSRVPointer = sourceSRV.Get( );
    ID3D11UnorderedAccessView * outputUAVPointer = outputUAV.Get( );
    context->CSSetSamplers( 0, 1, &m_LinearSampler );
    context->CSSetShaderResources( 11, 1, &sourceSRVPointer );
    context->CSSetUnorderedAccessViews( 0, 1, &outputUAVPointer, nullptr );
    context->CSSetShader( diagnosticShader, nullptr, 0 );
    context->Dispatch( (outputWidth + 7) / 8, (outputHeight + 7) / 8, 1 );

    ID3D11ShaderResourceView * nullSRV = nullptr;
    ID3D11UnorderedAccessView * nullUAV = nullptr;
    ID3D11SamplerState * nullSampler = nullptr;
    context->CSSetShader( nullptr, nullptr, 0 );
    context->CSSetShaderResources( 11, 1, &nullSRV );
    context->CSSetUnorderedAccessViews( 0, 1, &nullUAV, nullptr );
    context->CSSetSamplers( 0, 1, &nullSampler );
    context->CopyResource( outputReadback.Get( ), outputTexture.Get( ) );

    D3D11_MAPPED_SUBRESOURCE mapped;
    ZeroMemory( &mapped, sizeof( mapped ) );
    result = context->Map( outputReadback.Get( ), 0, D3D11_MAP_READ, 0, &mapped );
    if( FAILED( result ) )
    {
        m_catmullRomDiagnostics.Valid = true;
        m_catmullRomDiagnostics.Passed = false;
        VA_LOG_ERROR( "SMAA Catmull-Rom diagnostic readback failed (HRESULT 0x%08X)", (uint32)result );
        return;
    }

    double gpuSquaredError = 0.0;
    bool gpuValuesFinite = true;
    for( int y = 0; y < outputHeight; y++ )
    {
        const SMAACatmullDiagnosticColor * row = reinterpret_cast<const SMAACatmullDiagnosticColor *>(
            reinterpret_cast<const uint8 *>( mapped.pData ) + y * mapped.RowPitch );
        for( int x = 0; x < outputWidth; x++ )
        {
            const SMAACatmullDiagnosticColor & gpuValue = row[x];
            gpuValuesFinite = gpuValuesFinite
                && std::isfinite( gpuValue.R ) && std::isfinite( gpuValue.G )
                && std::isfinite( gpuValue.B ) && std::isfinite( gpuValue.A );
            const float u = ((float)x - 1.25f) / 12.5f;
            const float v = ((float)y - 1.25f) / 12.5f;
            const SMAACatmullDiagnosticColor cpuValue = SMAACatmullSample5Tap(
                sourceData.data( ), sourceWidth, sourceHeight, u, v );
            m_catmullRomDiagnostics.GPUToCPU5TapMaximumError = vaMath::Max(
                m_catmullRomDiagnostics.GPUToCPU5TapMaximumError,
                SMAACatmullColorMaximumAbsoluteDifference( gpuValue, cpuValue ) );
            gpuSquaredError += SMAACatmullColorSquaredDifference( gpuValue, cpuValue );
            m_catmullRomDiagnostics.GPUConstantMaximumError = vaMath::Max(
                m_catmullRomDiagnostics.GPUConstantMaximumError,
                vaMath::Max( vaMath::Abs( gpuValue.B - 0.375f ), vaMath::Abs( gpuValue.A - 1.0f ) ) );
        }
    }
    context->Unmap( outputReadback.Get( ), 0 );

    m_catmullRomDiagnostics.GPUComparisonSampleCount = outputWidth * outputHeight;
    m_catmullRomDiagnostics.GPUToCPU5TapRMSE = (float)std::sqrt(
        gpuSquaredError / (double)(m_catmullRomDiagnostics.GPUComparisonSampleCount * 4) );
    const bool allMetricsFinite = std::isfinite( m_catmullRomDiagnostics.MaximumWeightSumError )
        && std::isfinite( m_catmullRomDiagnostics.MaximumSymmetryError )
        && std::isfinite( m_catmullRomDiagnostics.GPUConstantMaximumError )
        && std::isfinite( m_catmullRomDiagnostics.GPUToCPU5TapMaximumError )
        && std::isfinite( m_catmullRomDiagnostics.GPUToCPU5TapRMSE )
        && std::isfinite( m_catmullRomDiagnostics.CPU5TapTo16TapMaximumError )
        && std::isfinite( m_catmullRomDiagnostics.CPU5TapTo16TapRMSE );
    m_catmullRomDiagnostics.Valid = true;
    m_catmullRomDiagnostics.Passed = gpuValuesFinite && allMetricsFinite
        && m_catmullRomDiagnostics.MaximumWeightSumError <= 2.0e-6f
        && m_catmullRomDiagnostics.MaximumSymmetryError <= 2.0e-6f
        && m_catmullRomDiagnostics.GPUConstantMaximumError <= 2.0e-5f
        && m_catmullRomDiagnostics.GPUToCPU5TapMaximumError <= 5.0e-3f;

    VA_LOG( "SMAA Catmull-Rom 5-tap validation: weightSumMax=%.9f, symmetryMax=%.9f, GPUConstantMax=%.9f, GPUvsCPU5 max=%.9f RMSE=%.9f, CPU5vs16 max=%.9f RMSE=%.9f => %s",
        m_catmullRomDiagnostics.MaximumWeightSumError,
        m_catmullRomDiagnostics.MaximumSymmetryError,
        m_catmullRomDiagnostics.GPUConstantMaximumError,
        m_catmullRomDiagnostics.GPUToCPU5TapMaximumError,
        m_catmullRomDiagnostics.GPUToCPU5TapRMSE,
        m_catmullRomDiagnostics.CPU5TapTo16TapMaximumError,
        m_catmullRomDiagnostics.CPU5TapTo16TapRMSE,
        m_catmullRomDiagnostics.Passed? "PASS" : "FAIL" );
}

void vaSMAAWrapperDX11::QueueAndConsumeTSCMAAStatisticsReadback( ID3D11DeviceContext * context, uint32 width, uint32 height )
{
    const uint32 pixelCount = width * height;
    for( int i = 0; i < c_tscmaaReadbackBufferCount; i++ )
    {
        if( !m_tscmaaReadbackPending[i] )
            continue;

        D3D11_MAPPED_SUBRESOURCE mapped;
        ZeroMemory( &mapped, sizeof( mapped ) );
        const HRESULT mapResult = context->Map( m_tscmaaControlReadback[i], 0, D3D11_MAP_READ, D3D11_MAP_FLAG_DO_NOT_WAIT, &mapped );
        if( mapResult == DXGI_ERROR_WAS_STILL_DRAWING )
            continue;

        m_tscmaaReadbackPending[i] = false;
        if( FAILED( mapResult ) )
            continue;

        const UINT * counters = reinterpret_cast<const UINT *>( mapped.pData );
        if( m_tscmaaReadbackGeneration[i] == m_tscmaaStatisticsGeneration )
        {
            m_temporalCandidateStatistics.Valid = true;
            m_temporalCandidateStatistics.CandidateCount = counters[0];
            m_temporalCandidateStatistics.ProcessCount = counters[1];
            m_temporalCandidateStatistics.BaseEdgeCount = counters[2];
            m_temporalCandidateStatistics.DispatchGroupCount = counters[3];
            m_temporalCandidateStatistics.PixelCount = pixelCount;
            m_temporalCandidateStatistics.Policy = GetEffectiveCandidatePolicy( );

            if( !m_tscmaaStatisticsLogged )
            {
                const char * policyName = "Unknown";
                switch( m_temporalCandidateStatistics.Policy )
                {
                case CandidatePolicy::AllBaseEdges:                    policyName = "AllBaseEdges"; break;
                case CandidatePolicy::IntelFamilyNonDominant:          policyName = "IntelFamilyNonDominant"; break;
                case CandidatePolicy::ExperimentalLocalMeanMax3x3:     policyName = "ExperimentalLocalMeanMax3x3"; break;
                }
                VA_LOG( "TSCMAA candidate counters [%s%s]: base=%u (%.3f%% pixels), candidates=%u (%.3f%% pixels, %.3f%% of base), indirect=%u, groups=%u",
                    policyName, GetForcedCandidateCountEnabled( )? ", forced-count diagnostics" : "",
                    m_temporalCandidateStatistics.BaseEdgeCount,
                    pixelCount > 0? 100.0f * (float)m_temporalCandidateStatistics.BaseEdgeCount / (float)pixelCount : 0.0f,
                    m_temporalCandidateStatistics.CandidateCount,
                    100.0f * m_temporalCandidateStatistics.GetCandidateToPixelRatio( ),
                    100.0f * m_temporalCandidateStatistics.GetCandidateToBaseRatio( ),
                    m_temporalCandidateStatistics.ProcessCount,
                    m_temporalCandidateStatistics.DispatchGroupCount );
                m_tscmaaStatisticsLogged = true;
            }
        }
        context->Unmap( m_tscmaaControlReadback[i], 0 );
    }

    if( GetForcedCandidateCountEnabled( ) && m_tscmaaCandidatesReadback != nullptr )
    {
        if( m_tscmaaCandidatesReadbackPending && m_temporalCandidateStatistics.Valid )
        {
            D3D11_MAPPED_SUBRESOURCE mapped;
            ZeroMemory( &mapped, sizeof( mapped ) );
            const HRESULT mapResult = context->Map( m_tscmaaCandidatesReadback, 0, D3D11_MAP_READ, D3D11_MAP_FLAG_DO_NOT_WAIT, &mapped );
            if( mapResult != DXGI_ERROR_WAS_STILL_DRAWING )
            {
                m_tscmaaCandidatesReadbackPending = false;
                if( SUCCEEDED( mapResult ) )
                {
                    if( m_tscmaaCandidatesReadbackGeneration == m_tscmaaStatisticsGeneration )
                    {
                        const uint32 expectedCount = vaMath::Min( GetForcedCandidateCount( ), pixelCount );
                        const uint32 readbackCount = vaMath::Min( m_temporalCandidateStatistics.ProcessCount, m_tscmaaCandidateCapacity );
                        const UINT * candidates = reinterpret_cast<const UINT *>( mapped.pData );
                        vector<uint8> seen( pixelCount, 0 );
                        uint32 duplicateCount = 0;
                        uint32 outOfRangeCount = 0;

                        for( uint32 candidateIndex = 0; candidateIndex < readbackCount; candidateIndex++ )
                        {
                            const uint32 packedPixel = candidates[candidateIndex];
                            const uint32 x = packedPixel >> 16;
                            const uint32 y = packedPixel & 0xffff;
                            if( x >= width || y >= height )
                            {
                                outOfRangeCount++;
                                continue;
                            }

                            const uint32 linearIndex = y * width + x;
                            if( seen[linearIndex] != 0 )
                                duplicateCount++;
                            else
                                seen[linearIndex] = 1;
                        }

                        const uint32 overflowCount = (m_temporalCandidateStatistics.CandidateCount > m_tscmaaCandidateCapacity)?
                            m_temporalCandidateStatistics.CandidateCount - m_tscmaaCandidateCapacity : 0;
                        const uint32 expectedDispatchGroups = (expectedCount + 63) / 64;
                        m_temporalCandidateValidation.Valid = true;
                        m_temporalCandidateValidation.RequestedCount = GetForcedCandidateCount( );
                        m_temporalCandidateValidation.ExpectedCount = expectedCount;
                        m_temporalCandidateValidation.ReadbackCount = readbackCount;
                        m_temporalCandidateValidation.DuplicateCount = duplicateCount;
                        m_temporalCandidateValidation.OutOfRangeCount = outOfRangeCount;
                        m_temporalCandidateValidation.CapacityOverflowCount = overflowCount;
                        m_temporalCandidateValidation.Passed =
                            m_temporalCandidateStatistics.BaseEdgeCount == expectedCount
                            && m_temporalCandidateStatistics.CandidateCount == expectedCount
                            && m_temporalCandidateStatistics.ProcessCount == expectedCount
                            && m_temporalCandidateStatistics.DispatchGroupCount == expectedDispatchGroups
                            && readbackCount == expectedCount
                            && duplicateCount == 0
                            && outOfRangeCount == 0
                            && overflowCount == 0;

                        VA_LOG( "TSCMAA candidate boundary validation: requested=%u, expected=%u, candidate=%u, process=%u, groups=%u/%u, readback=%u, duplicate=%u, outOfRange=%u, overflow=%u => %s",
                            m_temporalCandidateValidation.RequestedCount,
                            expectedCount,
                            m_temporalCandidateStatistics.CandidateCount,
                            m_temporalCandidateStatistics.ProcessCount,
                            m_temporalCandidateStatistics.DispatchGroupCount,
                            expectedDispatchGroups,
                            readbackCount,
                            duplicateCount,
                            outOfRangeCount,
                            overflowCount,
                            m_temporalCandidateValidation.Passed? "PASS" : "FAIL" );
                    }
                    context->Unmap( m_tscmaaCandidatesReadback, 0 );
                }
            }
        }

        if( !m_tscmaaCandidatesReadbackPending && !m_temporalCandidateValidation.Valid )
        {
            context->CopyResource( m_tscmaaCandidatesReadback, m_tscmaaCandidatesBuffer );
            m_tscmaaCandidatesReadbackPending = true;
            m_tscmaaCandidatesReadbackGeneration = m_tscmaaStatisticsGeneration;
        }
    }

    for( int attempt = 0; attempt < c_tscmaaReadbackBufferCount; attempt++ )
    {
        const int readbackIndex = (m_tscmaaReadbackCursor + attempt) % c_tscmaaReadbackBufferCount;
        if( m_tscmaaReadbackPending[readbackIndex] )
            continue;

        context->CopyResource( m_tscmaaControlReadback[readbackIndex], m_tscmaaControlBuffer );
        m_tscmaaReadbackPending[readbackIndex] = true;
        m_tscmaaReadbackGeneration[readbackIndex] = m_tscmaaStatisticsGeneration;
        m_tscmaaReadbackCursor = (readbackIndex + 1) % c_tscmaaReadbackBufferCount;
        break;
    }
}

vaDrawResultFlags vaSMAAWrapperDX11::DrawTSCMAADebugView( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & destination )
{
    if( GetTemporalDebugView( ) == TemporalDebugView::None )
        return vaDrawResultFlags::None;

    if( GetTemporalDebugView( ) == TemporalDebugView::CurrentSpatial )
    {
        if( m_temporalSpatialCurrent == nullptr )
            return vaDrawResultFlags::UnspecifiedError;
        ID3D11DeviceContext * dx11Context = deviceContext.SafeCast<vaRenderDeviceContextDX11*>( )->GetDXContext( );
        dx11Context->CopyResource( destination->SafeCast<vaTextureDX11*>( )->GetResource( ),
            m_temporalSpatialCurrent->SafeCast<vaTextureDX11*>( )->GetResource( ) );
        return vaDrawResultFlags::None;
    }

    const shared_ptr<vaTexture> & debugMask = (GetTemporalDebugView( ) == TemporalDebugView::BaseEdges)?
        m_tscmaaBaseEdgeMask : m_tscmaaCandidateMask;
    if( debugMask == nullptr || !m_tscmaaDebugMaskPS->IsCreated( ) )
        return vaDrawResultFlags::ShadersStillCompiling;

    deviceContext.SetRenderTarget( destination, nullptr, true );
    vaGraphicsItem debugRenderItem;
    deviceContext.FillFullscreenPassRenderItem( debugRenderItem );
    debugRenderItem.ShaderResourceViews[10] = debugMask;
    debugRenderItem.PixelShader = m_tscmaaDebugMaskPS;
    const vaDrawResultFlags result = deviceContext.ExecuteSingleItem( debugRenderItem );
    deviceContext.SetRenderTarget( nullptr, nullptr, false );
    return result;
}

void vaSMAAWrapperDX11::SetGlobalStates( vaRenderDeviceContext & deviceContext )
{
    ID3D11DeviceContext * dx11Context = deviceContext.SafeCast<vaRenderDeviceContextDX11*>( )->GetDXContext();
    ID3D11SamplerState * samplerState[2] = { m_LinearSampler, m_PointSampler };
    dx11Context->PSSetSamplers( 0, 2, samplerState );
    m_constantsBuffer.GetBuffer()->SafeCast<vaConstantBufferDX11*>()->SetToAPISlot( deviceContext, 0 );
}
void vaSMAAWrapperDX11::UnsetGlobalStates( vaRenderDeviceContext & deviceContext )
{
    ID3D11DeviceContext * dx11Context = deviceContext.SafeCast<vaRenderDeviceContextDX11*>( )->GetDXContext();
    ID3D11SamplerState * samplerState[2] = { nullptr, nullptr };
    dx11Context->PSSetSamplers( 0, 2, samplerState );
    m_constantsBuffer.GetBuffer()->SafeCast<vaConstantBufferDX11*>()->UnsetFromAPISlot( deviceContext, 0 );
    ID3D11ShaderResourceView * nullSRVs[11] = { nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr };
    dx11Context->PSSetShaderResources( 0, _countof( nullSRVs ), nullSRVs );
    dx11Context->OMSetBlendState( nullptr, nullptr, 0 );
    dx11Context->OMSetDepthStencilState( nullptr, 0 );
    dx11Context->IASetInputLayout( nullptr );
    dx11Context->VSSetShader( nullptr, nullptr, 0 );
    dx11Context->PSSetShader( nullptr, nullptr, 0 );
}

// SMAAShaderConstantsInterface impl
void vaSMAAWrapperDX11::SetVariablesA( ID3D11DeviceContext * context, float thresholdVariable, float cornerRoundingVariable, float maxSearchStepsVariable, float maxSearchStepsDiagVariable, float blendFactorVariable )
{
    m_constants.threshld            = thresholdVariable;
    m_constants.cornerRounding      = cornerRoundingVariable;
    m_constants.maxSearchSteps      = maxSearchStepsVariable;
    m_constants.maxSearchStepsDiag  = maxSearchStepsDiagVariable;
    m_constants.blendFactor         = blendFactorVariable;
    m_constantsBuffer.GetBuffer()->SafeCast<vaConstantBufferDX11*>()->Update( context, &m_constants, sizeof(m_constants) );
}
void vaSMAAWrapperDX11::SetVariablesB( ID3D11DeviceContext * context, float subsampleIndicesVariable[4] )
{
    memcpy( m_constants.subsampleIndices, subsampleIndicesVariable, sizeof(float)*4 );
    if( m_temporalLifecycleDiagnostics.Enabled )
    {
        memcpy( m_temporalLastSubsampleIndices, subsampleIndicesVariable, sizeof(float)*4 );
        m_temporalLastSubsampleIndicesValid = true;
    }
    m_constantsBuffer.GetBuffer()->SafeCast<vaConstantBufferDX11*>()->Update( context, &m_constants, sizeof(m_constants) );
}

// SMAATexturesInterface impl
void vaSMAAWrapperDX11::SetResource_areaTex( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource )
{
    context->PSSetShaderResources( 0, 1, &pResource );
}
void vaSMAAWrapperDX11::SetResource_searchTex      ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) 
{
    context->PSSetShaderResources( 1, 1, &pResource );
}
void vaSMAAWrapperDX11::SetResource_colorTex       ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) 
{
    context->PSSetShaderResources( 2, 1, &pResource );
}
void vaSMAAWrapperDX11::SetResource_colorTexGamma  ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) 
{
    context->PSSetShaderResources( 3, 1, &pResource );
}
void vaSMAAWrapperDX11::SetResource_colorTexPrev   ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) 
{
    context->PSSetShaderResources( 4, 1, &pResource );
}
void vaSMAAWrapperDX11::SetResource_colorTexMS     ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) 
{
    context->PSSetShaderResources( 5, 1, &pResource );
}
void vaSMAAWrapperDX11::SetResource_depthTex       ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) 
{
    context->PSSetShaderResources( 6, 1, &pResource );
}
void vaSMAAWrapperDX11::SetResource_velocityTex    ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) 
{
    context->PSSetShaderResources( 7, 1, &pResource );
}
void vaSMAAWrapperDX11::SetResource_edgesTex       ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) 
{
    context->PSSetShaderResources( 8, 1, &pResource );
}
void vaSMAAWrapperDX11::SetResource_blendTex       ( ID3D11DeviceContext * context, ID3D11ShaderResourceView * pResource ) 
{
    context->PSSetShaderResources( 9, 1, &pResource );
}

// SMAATechniqueManagerInterface impl
SMAATechniqueInterface* vaSMAAWrapperDX11::CreateTechnique( const char * _name, const std::vector<D3D_SHADER_MACRO> & defines )
{
    string name = _name;
    defines;
    shared_ptr<TechniqueThingieDX11> tech = std::make_shared<TechniqueThingieDX11>( vaRenderingModuleParams(GetRenderDevice()) );

    std::vector<vaVertexInputElementDesc> inputElements;
    inputElements.push_back( { "POSITION",  0, vaResourceFormat::R32G32B32_FLOAT,    0, vaVertexInputElementDesc::AppendAlignedElement, vaVertexInputElementDesc::InputClassification::PerVertexData, 0 } );
    inputElements.push_back( { "TEXCOORD",  0, vaResourceFormat::R32G32_FLOAT,       0, vaVertexInputElementDesc::AppendAlignedElement, vaVertexInputElementDesc::InputClassification::PerVertexData, 0 } );

    vector< pair< string, string > > shaderMacros;
    for( const D3D_SHADER_MACRO & sm : defines )
        if( sm.Name != nullptr ) 
            shaderMacros.push_back( { (string)sm.Name, (string)((sm.Definition!=nullptr)?(sm.Definition):("")) } );

    wstring shaderFileName = L"SMAA/SMAAWrapper.hlsl";
    string vsVersion = "vs_4_0";
    string psVersion = "ps_4_1";

    if( name == "LumaEdgeDetection" )
    {
        //technique10 LumaEdgeDetection {
        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, "DX10_SMAAEdgeDetectionVS", inputElements, shaderMacros, true );
        tech->PS->CreateShaderFromFile( shaderFileName, psVersion, "DX10_SMAALumaEdgeDetectionPS", shaderMacros, true );
        tech->DSS = m_DisableDepthReplaceStencil;
        tech->BS  = m_NoBlending;
        tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
        tech->SampleMask = 0xFFFFFFFF;
        tech->StencilRef = 1;
    }
    else if( name == "LumaRawEdgeDetection" )
    {
        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, "DX10_SMAAEdgeDetectionVS", inputElements, shaderMacros, true );
        tech->PS->CreateShaderFromFile( shaderFileName, psVersion, "DX10_SMAALumaRawEdgeDetectionPS", shaderMacros, true );
        tech->DSS = m_DisableDepthReplaceStencil;
        tech->BS  = m_NoBlending;
        tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
        tech->SampleMask = 0xFFFFFFFF;
        tech->StencilRef = 1;
    }
    else if( name == "ColorEdgeDetection" )
    {
        //technique10 ColorEdgeDetection {
        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, "DX10_SMAAEdgeDetectionVS", inputElements, shaderMacros, true );
        tech->PS->CreateShaderFromFile( shaderFileName, psVersion, "DX10_SMAAColorEdgeDetectionPS", shaderMacros, true );
        tech->DSS = m_DisableDepthReplaceStencil;
        tech->BS  = m_NoBlending;
        tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
        tech->SampleMask = 0xFFFFFFFF;
        tech->StencilRef = 1;
    }
    else if( name == "DepthEdgeDetection" )
    {
        //technique10 DepthEdgeDetection {
        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, "DX10_SMAAEdgeDetectionVS", inputElements, shaderMacros, true );
        tech->PS->CreateShaderFromFile( shaderFileName, psVersion, "DX10_SMAADepthEdgeDetectionPS", shaderMacros, true );
        tech->DSS = m_DisableDepthReplaceStencil;
        tech->BS  = m_NoBlending;
        tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
        tech->SampleMask = 0xFFFFFFFF;
        tech->StencilRef = 1;
    }
    else if( name == "BlendingWeightCalculation" )
    {
        //technique10 BlendingWeightCalculation {
        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, "DX10_SMAABlendingWeightCalculationVS", inputElements, shaderMacros, true );
        tech->PS->CreateShaderFromFile( shaderFileName, psVersion, "DX10_SMAABlendingWeightCalculationPS", shaderMacros, true );
        tech->DSS = m_DisableDepthUseStencil;
        tech->BS  = m_NoBlending;
        tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
        tech->SampleMask = 0xFFFFFFFF;
        tech->StencilRef = 1;
    }
    else if( name == "NeighborhoodBlending" )
    {
        //technique10 NeighborhoodBlending {

        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, "DX10_SMAANeighborhoodBlendingVS", inputElements, shaderMacros, true );
        tech->PS->CreateShaderFromFile( shaderFileName, psVersion, "DX10_SMAANeighborhoodBlendingPS", shaderMacros, true );
        tech->DSS = m_DisableDepthStencil;
        tech->BS  = m_Blend;
        tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
        tech->BlendFactorAltSource = &m_constants.blendFactor;
        tech->SampleMask = 0xFFFFFFFF;
        tech->StencilRef = 0;
    }
    else if( name == "Resolve" )
    {
        //technique10 Resolve {
        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, "DX10_SMAAResolveVS", inputElements, shaderMacros, true );
        tech->PS->CreateShaderFromFile( shaderFileName, psVersion, "DX10_SMAAResolvePS", shaderMacros, true );
        tech->DSS = m_DisableDepthStencil;
        tech->BS  = m_NoBlending;
        tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
        tech->SampleMask = 0xFFFFFFFF;
        tech->StencilRef = 0;
    }
    else if( name == "Separate" )
    {
        //technique10 Separate {
        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, "DX10_SMAASeparateVS", inputElements, shaderMacros, true );
        tech->PS->CreateShaderFromFile( shaderFileName, psVersion, "DX10_SMAASeparatePS", shaderMacros, true );
        tech->DSS = m_DisableDepthStencil;
        tech->BS  = m_NoBlending;
        tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
        tech->SampleMask = 0xFFFFFFFF;
        tech->StencilRef = 0;
    }
    else if( name.substr(0, 16) == "detectMSAAOrder_" )
    {
        string s =  string("") +
                    "float4 RenderVS(float4 pos : POSITION,    inout float2 coord : TEXCOORD0) : SV_POSITION { pos.x = -0.5 + 0.5 * pos.x; return pos; }" +
                    "float4 RenderPS(float4 pos : SV_POSITION,       float2 coord : TEXCOORD0) : SV_TARGET   { return 1.0; }" + 
                    "Texture2DMS<float4, 2> srcMultiSampled : register( t5 );" + 
                    "float4 LoadVS(float4 pos : POSITION,    inout float2 coord : TEXCOORD0) : SV_POSITION { return pos; }" + 
                    "float4 LoadPS(float4 pos : SV_POSITION,       float2 coord : TEXCOORD0) : SV_TARGET   { int2 ipos = int2(pos.xy); return srcMultiSampled.Load(ipos, 0); }";

        if( name == "detectMSAAOrder_Render" )
        {
            tech->VS->CreateShaderAndILFromBuffer( s, "vs_4_0", "RenderVS", inputElements, shaderMacros, true );
            tech->PS->CreateShaderFromBuffer( s, "ps_4_0", "RenderPS", shaderMacros, true );
            tech->DSS = m_DisableDepthStencil;
            tech->BS  = m_NoBlending;
            tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
            tech->SampleMask = 0xFFFFFFFF;
            tech->StencilRef = 0;
        }
        else if( name == "detectMSAAOrder_Load" )
        {
            tech->VS->CreateShaderAndILFromBuffer( s, "vs_4_0", "LoadVS", inputElements, shaderMacros, true );
            tech->PS->CreateShaderFromBuffer( s, "ps_4_0", "LoadPS", shaderMacros, true );
            tech->DSS = m_DisableDepthStencil;
            tech->BS  = m_NoBlending;
            tech->BlendFactor[0] = 0.0f; tech->BlendFactor[1] = 0.0f; tech->BlendFactor[2] = 0.0f; tech->BlendFactor[3] = 0.0f;
            tech->SampleMask = 0xFFFFFFFF;
            tech->StencilRef = 0;
        }
        else
        {
            assert( false );
            return nullptr;
        }
    }
    else
    {
        assert( false ); // technique name not found?
        return nullptr;
    }

    m_techniques.push_back( tech );

    return tech.get();
}
void vaSMAAWrapperDX11::DestroyAllTechniques( )
{
    m_techniques.clear();
}

// SMAATechniqueInterface impl
void TechniqueThingieDX11::ApplyStates( ID3D11DeviceContext * context )
{
    if( BlendFactorAltSource != nullptr )
    {
        // when BlendFactorAltSource is non-null, update BlendFactor values from it each time!
        BlendFactor[0] = BlendFactor[1] = BlendFactor[2] = BlendFactor[3] = *BlendFactorAltSource;
    }
    context->RSSetState( nullptr );
    context->OMSetBlendState( this->BS, this->BlendFactor, this->SampleMask );
    context->OMSetDepthStencilState( this->DSS, this->StencilRef );
    context->IASetInputLayout( this->VS->SafeCast<vaVertexShaderDX11*>()->GetInputLayout() );

    ID3D11VertexShader * vs = this->VS->SafeCast<vaVertexShaderDX11*>()->GetShader();
    ID3D11PixelShader * ps = this->PS->SafeCast<vaPixelShaderDX11*>()->GetShader();
    context->VSSetShader( vs, nullptr, 0 );
    context->PSSetShader( ps, nullptr, 0 );
}

void RegisterSMAAWrapperDX11( )
{
    VA_RENDERING_MODULE_REGISTER( vaRenderDeviceDX11, vaSMAAWrapper, vaSMAAWrapperDX11 );
}

void RegisterSMAAWrapperDX12( )
{
    VA_RENDERING_MODULE_REGISTER( vaRenderDeviceDX12, vaSMAAWrapper, vaSMAAWrapperDX12 );
}
