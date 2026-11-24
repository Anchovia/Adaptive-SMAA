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

namespace VertexAsylum
{

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
        ID3D11DepthStencilState *   m_DisableDepthNoStencil         = nullptr;   // selected route neighborhood: depth and stencil Off
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

        bool                        m_smaaAdaptiveSearch            = false;    // the setting m_smaa was created with

        // Selected temporal route: history ping-pong, this frame's spatial colour (the resolve writes the
        // next history at the same pixels), camera velocity and the previous frame's velocity for Cross5.
        shared_ptr<vaTexture>       m_temporalHistory[2]            = { nullptr, nullptr };
        shared_ptr<vaTexture>       m_feedbackCurrentSpatial        = nullptr;
        shared_ptr<vaTexture>       m_temporalVelocity              = nullptr;
        shared_ptr<vaTexture>       m_previousVelocity              = nullptr;
        shared_ptr<vaTexture>       m_presentedOutput               = nullptr;  // this frame's next history
        int                         m_historyIndex                  = 0;
        bool                        m_temporalHistoryValid          = false;
        bool                        m_previousViewProjValid         = false;
        vaMatrix4x4                 m_previousViewProj              = vaMatrix4x4::Identity;

        SMAAReprojectionConstants   m_reprojectionConstants;
        vaTypedConstantBufferWrapper<SMAAReprojectionConstants>
                                    m_reprojectionConstantsBuffer;
        vaAutoRMI<vaPixelShader>    m_generateCameraVelocityPS;

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
        virtual shared_ptr<vaTexture>   GetPresentedOutputOverride( ) const override { return m_presentedOutput; }
        virtual bool                    HasTemporalResources( ) const override { return m_temporalHistory[0] != nullptr || m_temporalHistory[1] != nullptr
            || m_feedbackCurrentSpatial != nullptr || m_temporalVelocity != nullptr || m_previousVelocity != nullptr; }

    private:
        bool                            UpdateResources( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor );
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

vaSMAAWrapperDX11::vaSMAAWrapperDX11( const vaRenderingModuleParams & params ) : vaSMAAWrapper( params ),
    m_reprojectionConstantsBuffer( params ), m_generateCameraVelocityPS( params.RenderDevice )
{
    params; // unreferenced

    ID3D11Device * device = params.RenderDevice.SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice();
    m_generateCameraVelocityPS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "ps_5_0", "DX10_SMAAGenerateCameraVelocityPS", {}, true );
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
        CD3D11_DEPTH_STENCIL_DESC desc = CD3D11_DEPTH_STENCIL_DESC( CD3D11_DEFAULT( ) );
        desc.DepthEnable                = FALSE;
        desc.StencilEnable              = FALSE;
        V( device->CreateDepthStencilState( &desc, &m_DisableDepthNoStencil ) );
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
    SAFE_RELEASE( m_DisableDepthNoStencil      );
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
    m_feedbackCurrentSpatial = nullptr;
    m_temporalVelocity = nullptr;
    m_previousVelocity = nullptr;
    ResetTemporalHistory( );
}

void vaSMAAWrapperDX11::ResetTemporalHistory( )
{
    m_presentedOutput = nullptr;
    m_temporalHistoryValid = false;
    m_previousViewProjValid = false;
    if( !m_selectedTemporal )
    {
        m_temporalHistory[0] = nullptr;
        m_temporalHistory[1] = nullptr;
        m_feedbackCurrentSpatial = nullptr;
        m_temporalVelocity = nullptr;
        m_previousVelocity = nullptr;
    }
}

bool vaSMAAWrapperDX11::UpdateResources( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor )
{
    // this should go to UpdateResources
    bool smaaPredication = false;   // search for SMAA_PREDICATION - this is for additional edge detection (depth-based, or etc.)
    bool smaaProjection = false;    // 
    assert( inputColor->GetSampleCount() == 1 ); // if MSAA we expect inputs in a resolved array
    assert( inputColor->GetArrayCount() == 1 || inputColor->GetArrayCount() == 2 ); // only 1 or 2 samples supported
    if( m_smaa == nullptr || m_smaa->getPreset( ) != m_settings.Preset || m_smaa->getWidth( ) != inputColor->GetSizeX( ) || m_smaa->getHeight( ) != inputColor->GetSizeY( ) || inputColor->GetArrayCount() != m_sampleCount || m_externalInputColor != inputColor
        || m_smaaAdaptiveSearch != m_adaptiveSearch )
    {
        SAFE_DELETE( m_smaa );
        CleanupTemporaryResources( );
        SetGlobalStates( deviceContext );
        m_smaa = new SMAA( GetRenderDevice().SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice(), (SMAAShaderConstantsInterface*)this, (SMAATexturesInterface*)this, (SMAATechniqueManagerInterface*)this, inputColor->GetSizeX( ), inputColor->GetSizeY( ),
            ( SMAA::Preset )m_settings.Preset, smaaPredication, smaaProjection, nullptr, SMAA::ExternalStorage( ), m_adaptiveSearch );
        m_smaaAdaptiveSearch = m_adaptiveSearch;
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
    }

    if( m_selectedTemporal && m_temporalHistory[0] == nullptr )
    {
        assert( m_sampleCount == 1 );
        const vaResourceBindSupportFlags bindFlags = vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::ShaderResource;
        auto colorTexture = [&]( ) { return vaTexture::Create2D( inputColor->GetRenderDevice(), inputColor->GetResourceFormat(), inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
            bindFlags, vaResourceAccessFlags::Default, inputColor->GetSRVFormat(), inputColor->GetRTVFormat(), vaResourceFormat::Unknown, vaResourceFormat::Unknown,
            vaTextureFlags::None, inputColor->GetContentsType() ); };
        auto velocityTexture = [&]( ) { return vaTexture::Create2D( inputColor->GetRenderDevice(), vaResourceFormat::R16G16_FLOAT, inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
            bindFlags, vaResourceAccessFlags::Default ); };
        m_temporalHistory[0] = colorTexture( );
        m_temporalHistory[1] = colorTexture( );
        m_feedbackCurrentSpatial = colorTexture( );
        m_temporalVelocity = velocityTexture( );
        m_previousVelocity = velocityTexture( );
        m_temporalHistoryValid = false;
        if( m_temporalHistory[0] == nullptr || m_temporalHistory[1] == nullptr || m_feedbackCurrentSpatial == nullptr || m_temporalVelocity == nullptr || m_previousVelocity == nullptr )
            return false;
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
    m_presentedOutput = nullptr;

    if( !UpdateResources( deviceContext, inputColor ) )
    { assert( false ); return vaDrawResultFlags::UnspecifiedError; }

    for( const shared_ptr<TechniqueThingieDX11> technique : m_techniques )
    {
        if( !technique->PS->IsCreated( ) || !technique->VS->IsCreated( ) )
            { /*VA_WARN( "SMAA: Not all shaders compiled, can't run" );*/ return vaDrawResultFlags::ShadersStillCompiling; }
    }

    // Selected route: camera velocity (current UV - previous UV) from the scene depth and the current and
    // previous view-projection matrices.
    if( m_selectedTemporal )
    {
        if( optionalDepth == nullptr || optionalCamera == nullptr || !m_generateCameraVelocityPS->IsCreated( ) )
            return vaDrawResultFlags::ShadersStillCompiling;

        const vaMatrix4x4 viewProj = optionalCamera->GetViewMatrix( ) * optionalCamera->GetProjMatrix( );
        m_reprojectionConstants.CurrentViewProjInv = viewProj.Inverse( );
        m_reprojectionConstants.CurrentUnjitteredViewProj = viewProj;
        m_reprojectionConstants.PreviousViewProj = m_previousViewProjValid? m_previousViewProj : viewProj;
        m_reprojectionConstantsBuffer.Update( deviceContext, m_reprojectionConstants );

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

        m_previousViewProj = viewProj;
        m_previousViewProjValid = true;
    }

    SetGlobalStates( deviceContext );

    if( inputColor->GetArrayCount() == 1 && m_selectedTemporal )
    {
        // 1. go(): the edge pass marks the stencil at the current raw edges and the camera-reprojected
        //    previous raw edges, and neighborhood blending writes the spatial result to the current spatial
        //    copy and to the next history.
        // 2. resolveSelected(): the marked pixels of the next history mix in the previous history; the next
        //    history is this frame's output (GetPresentedOutputOverride).
        ID3D11ShaderResourceView * colorGammaSRV = (optionalInLuma == nullptr)? m_viewColorIgnoreSRGB0->SafeCast<vaTextureDX11*>( )->GetSRV( ) : optionalInLuma->SafeCast<vaTextureDX11*>( )->GetSRV( );
        SMAA::Input inputMode = (optionalInLuma == nullptr)? SMAA::INPUT_LUMA : SMAA::INPUT_LUMA_RAW;
        const shared_ptr<vaTexture> & nextHistory = m_temporalHistory[m_historyIndex];
        const shared_ptr<vaTexture> & previousHistory = m_temporalHistory[1 - m_historyIndex];
        ID3D11RenderTargetView * nextHistoryRTV = nextHistory->SafeCast<vaTextureDX11*>( )->GetRTV( );
        ID3D11ShaderResourceView * velocitySRV = m_temporalVelocity->SafeCast<vaTextureDX11*>( )->GetSRV( );
        ID3D11DepthStencilView * dsv = m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV( );

        const SMAA::SelectedTemporalTargets selected = { nextHistoryRTV, m_temporalHistoryValid };
        m_smaa->go( dx11Context, colorGammaSRV, m_viewColor0->SafeCast<vaTextureDX11*>( )->GetSRV( ), nullptr, velocitySRV,
            m_feedbackCurrentSpatial->SafeCast<vaTextureDX11*>( )->GetRTV( ), dsv, inputMode, SMAA::MODE_SMAA_1X, 0, &selected );

        // Without valid history the previous history is this frame's spatial colour (seed).
        ID3D11ShaderResourceView * currentSpatialSRV = m_feedbackCurrentSpatial->SafeCast<vaTextureDX11*>( )->GetSRV( );
        ID3D11ShaderResourceView * previousHistorySRV = m_temporalHistoryValid? previousHistory->SafeCast<vaTextureDX11*>( )->GetSRV( ) : currentSpatialSRV;
        // Validation only: the weight debug variant also reads the scene depth (t13) and the reprojection constants (b1).
        const bool weightDebug = m_resolveVariant == 3 && m_temporalHistoryValid;
        ID3D11ShaderResourceView * debugDepthSRV = weightDebug? optionalDepth->SafeCast<vaTextureDX11*>( )->GetSRV( ) : nullptr;
        if( weightDebug )
        {
            dx11Context->PSSetShaderResources( 13, 1, &debugDepthSRV );
            m_reprojectionConstantsBuffer.GetBuffer( )->SafeCast<vaConstantBufferDX11*>( )->SetToAPISlot( deviceContext, 1, false );
        }
        m_smaa->resolveSelected( dx11Context, currentSpatialSRV, previousHistorySRV, velocitySRV, nextHistoryRTV, dsv, !m_temporalHistoryValid,
            m_previousVelocity->SafeCast<vaTextureDX11*>( )->GetSRV( ) );
        if( weightDebug )
        {
            ID3D11ShaderResourceView * none = nullptr;
            dx11Context->PSSetShaderResources( 13, 1, &none );
            m_reprojectionConstantsBuffer.GetBuffer( )->SafeCast<vaConstantBufferDX11*>( )->UnsetFromAPISlot( deviceContext, 1, false );
        }

        std::swap( m_temporalVelocity, m_previousVelocity );
        m_presentedOutput = nextHistory;
        m_temporalHistoryValid = true;
        m_historyIndex = 1 - m_historyIndex;
    }
    else if( inputColor->GetArrayCount() == 1 )
    {
        if( optionalInLuma == nullptr )
        {
            m_smaa->go( dx11Context, m_viewColorIgnoreSRGB0->SafeCast<vaTextureDX11*>( )->GetSRV( ), m_viewColor0->SafeCast<vaTextureDX11*>( )->GetSRV( ), nullptr, nullptr, dstRT->SafeCast<vaTextureDX11*>( )->GetRTV( ), m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV(), 
            SMAA::INPUT_LUMA, SMAA::MODE_SMAA_1X );
        }
        else
        {
            // this is the luma-raw path that uses the R8 luma input (instead of R8G8B8A8 and luma in .a) to reduce BW in the first pass
            m_smaa->go( dx11Context, optionalInLuma->SafeCast<vaTextureDX11*>( )->GetSRV( ), m_viewColor0->SafeCast<vaTextureDX11*>( )->GetSRV( ), nullptr, nullptr, dstRT->SafeCast<vaTextureDX11*>( )->GetRTV( ), m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV(), 
                SMAA::INPUT_LUMA_RAW, SMAA::MODE_SMAA_1X );
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
    ID3D11ShaderResourceView * nullSRVs[10] = { nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr };
    dx11Context->PSSetShaderResources( 0, 10, nullSRVs );
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

    // Selected temporal route: the edge pass marks the stencil, the neighborhood pass ignores it and writes
    // no depth, and the resolve runs on the marked pixels.
    if( name.substr( 0, 8 ) == "Selected" )
    {
        const bool edge = name.find( "EdgePS" ) != string::npos, neighborhood = name.find( "Neighborhood" ) != string::npos;
        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, edge? "DX10_SMAAEdgeDetectionVS" : (neighborhood? "DX10_SMAANeighborhoodBlendingVS" : "DX10_SMAAResolveVS"), inputElements, shaderMacros, true );
        tech->PS->CreateShaderFromFile( L"SMAA/SelectedTemporal.hlsl", "ps_5_0", name, shaderMacros, true );
        tech->DSS = edge? m_DisableDepthReplaceStencil : (neighborhood? m_DisableDepthNoStencil : m_DisableDepthUseStencil);
        tech->BS = m_NoBlending;
        for( int i = 0; i < 4; i++ ) tech->BlendFactor[i] = 0;
        tech->SampleMask = 0xFFFFFFFF;
        tech->StencilRef = neighborhood? 0 : 1;
    }
    else if( name == "LumaEdgeDetection" )
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