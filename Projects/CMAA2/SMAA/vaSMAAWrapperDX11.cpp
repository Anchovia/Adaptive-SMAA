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
#include "Rendering/DirectX/vaNvWarpDX11.h"

#include "Rendering/DirectX/vaRenderDeviceContextDX12.h" // only so the dx12 stub compiles - will be removed once ported to dx12 file

namespace VertexAsylum
{

    struct TechniqueThingieDX11 : public SMAATechniqueInterface
    {
        // TechniqueThingieDX11( ) { }
        // virtual ~TechniqueThingieDX11( ) { }

        bool                            NvWarp = false;
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
    public:
        virtual bool SupportsTemporalWarp() override { return TemporalNvWarp::Supported(GetRenderDevice().SafeCast<vaRenderDeviceDX11*>()->GetPlatformDevice()); }
        virtual bool SupportsTemporalWarpGroups() override { return TemporalNvWarp::GroupsSupported(GetRenderDevice().SafeCast<vaRenderDeviceDX11*>()->GetPlatformDevice()); }
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
        shared_ptr<vaTexture>       m_temporalVelocity              = nullptr;
        bool                        m_temporalHistoryValid           = false;
        bool                        m_previousViewProjValid          = false;
        bool                        m_smaaReprojectionEnabled        = false;
        vaMatrix4x4                 m_previousViewProj               = vaMatrix4x4::Identity;

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
    m_temporalVelocity = nullptr;
    m_smaaReprojectionEnabled = false;
    ResetTemporalHistory( );
}

void vaSMAAWrapperDX11::ResetTemporalHistory( )
{
    vaSMAAWrapper::ResetTemporalHistory( );
    m_temporalHistoryValid = false;
    m_previousViewProjValid = false;
    if( m_smaa != nullptr )
        m_smaa->resetFrame( );

    if( !GetTemporalModeEnabled( ) )
    {
        m_temporalHistory[0] = nullptr;
        m_temporalHistory[1] = nullptr;
    }
}

bool vaSMAAWrapperDX11::UpdateResources( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor )
{
    // this should go to UpdateResources
    bool smaaPredication = false;   // search for SMAA_PREDICATION - this is for additional edge detection (depth-based, or etc.)
    bool smaaProjection = GetTemporalReprojectionEnabled( );
    assert( inputColor->GetSampleCount() == 1 ); // if MSAA we expect inputs in a resolved array
    assert( inputColor->GetArrayCount() == 1 || inputColor->GetArrayCount() == 2 ); // only 1 or 2 samples supported
    if( m_smaa == nullptr || m_smaa->getPreset( ) != m_settings.Preset || m_smaa->getWidth( ) != inputColor->GetSizeX( ) || m_smaa->getHeight( ) != inputColor->GetSizeY( ) || inputColor->GetArrayCount() != m_sampleCount || m_externalInputColor != inputColor
        || m_smaaReprojectionEnabled != smaaProjection
        || (GetTemporalModeEnabled( ) && (m_temporalHistory[0] == nullptr || m_temporalHistory[1] == nullptr || (smaaProjection && m_temporalVelocity == nullptr))) )
    {
        SAFE_DELETE( m_smaa );
        CleanupTemporaryResources( );
        SetGlobalStates( deviceContext );
        m_smaa = new SMAA( GetRenderDevice().SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice(), (SMAAShaderConstantsInterface*)this, (SMAATexturesInterface*)this, (SMAATechniqueManagerInterface*)this, inputColor->GetSizeX( ), inputColor->GetSizeY( ),
            ( SMAA::Preset )m_settings.Preset, smaaPredication, smaaProjection );
        m_smaaReprojectionEnabled = smaaProjection;
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
            const vaResourceBindSupportFlags historyBindFlags = vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::ShaderResource;
            for( int i = 0; i < 2; i++ )
            {
                m_temporalHistory[i] = vaTexture::Create2D( inputColor->GetRenderDevice(), inputColor->GetResourceFormat(), inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    historyBindFlags, vaResourceAccessFlags::Default, inputColor->GetSRVFormat(), inputColor->GetRTVFormat(), vaResourceFormat::Unknown, vaResourceFormat::Unknown,
                    vaTextureFlags::None, inputColor->GetContentsType() );
            }
            if( smaaProjection )
                m_temporalVelocity = vaTexture::Create2D( inputColor->GetRenderDevice(), vaResourceFormat::R16G16_FLOAT, inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    historyBindFlags, vaResourceAccessFlags::Default );
            if( m_temporalHistory[0] == nullptr || m_temporalHistory[1] == nullptr || (smaaProjection && m_temporalVelocity == nullptr) )
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

    if( GetTemporalReprojectionEnabled( ) )
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

        m_previousViewProj = currentUnjitteredViewProj;
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

            vaTextureDX11 * currentHistoryDX11 = currentHistory->SafeCast<vaTextureDX11*>( );
            ID3D11RenderTargetView * currentHistoryRTV = currentHistoryDX11->GetRTV( );
            ID3D11ShaderResourceView * spatialColorSRV = m_viewColor0->SafeCast<vaTextureDX11*>( )->GetSRV( );
            ID3D11DepthStencilView * depthDSV = m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV( );

            ID3D11ShaderResourceView * velocitySRV = GetTemporalReprojectionEnabled( )? m_temporalVelocity->SafeCast<vaTextureDX11*>( )->GetSRV( ) : nullptr;
            {
                VA_SCOPE_CPUGPU_TIMER(SMAASpatial, deviceContext);
                // Disable the paired pattern as a unit: zero projection jitter and
                // ordinary 1X area-table indices. Keep temporal history/resolve active.
                m_smaa->go( dx11Context, colorGammaSRV, spatialColorSRV, nullptr, velocitySRV, currentHistoryRTV, depthDSV, inputMode,
                    GetTemporalSamplePatternEnabled() ? SMAA::MODE_SMAA_T2X : SMAA::MODE_SMAA_1X );
            }

            ID3D11ShaderResourceView * currentHistorySRV = currentHistory->SafeCast<vaTextureDX11*>( )->GetSRV( );
            ID3D11ShaderResourceView * previousHistorySRV = m_temporalHistoryValid? previousHistory->SafeCast<vaTextureDX11*>( )->GetSRV( ) : currentHistorySRV;
            {
                VA_SCOPE_CPUGPU_TIMER(SMAATemporalResolve, deviceContext);
                int resolveKind = GetTemporalContrastKind();
                // New current-de-jitter modes seed with their own current value,
                // avoiding a blend with uncorrected self-history on first frame.
                // Same fullscreen draw; no extra pass or resource.
                if(resolveKind==39 || resolveKind==40)
                    resolveKind=m_constants.subsampleIndices[0]==1.0f?39:(m_constants.subsampleIndices[0]==2.0f?40:35);
                if(!m_temporalHistoryValid && (resolveKind == 28 || resolveKind == 29 || (resolveKind >= 32 && resolveKind <= 45))) resolveKind = 31;
                if(!m_temporalHistoryValid) {
                    if(resolveKind==46) resolveKind=3;
                    if(resolveKind==47) resolveKind=31;
                    if(resolveKind==48 || resolveKind==49) resolveKind=50;
                }
                m_smaa->reproject( dx11Context, currentHistorySRV, previousHistorySRV, velocitySRV, dstRT->SafeCast<vaTextureDX11*>( )->GetRTV( ), resolveKind );
            }

            m_temporalHistoryValid = true;
            m_smaa->nextFrame( );
            AdvanceTemporalFrame( );
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
    // Reuse padding in the existing 48-byte buffer and its existing update.
    // Quarter-pixel scaling is exact binary scaling of the float reciprocal.
    const bool speedUniform = (GetTemporalContrastKind()>=35 && GetTemporalContrastKind()<=38) || (GetTemporalContrastKind()>=41 && GetTemporalContrastKind()<=45);
    const float phase = subsampleIndicesVariable[0]==1.0f ? 0.25f : (subsampleIndicesVariable[0]==2.0f ? -0.25f : 0.0f);
    m_constants.padding1 = speedUniform ? phase*(1.0f/float(m_externalInputColor->GetSizeX())) : 0.0f;
    m_constants.padding2 = speedUniform ? phase*(1.0f/float(m_externalInputColor->GetSizeY())) : 0.0f;
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
    else if( name == "Resolve" || name == "ContrastResolve" || name == "ContrastMask" || name == "CurrentSpatial" ||
        name == "NativeSM5" || name == "LodResolve" || name == "CurrentFirstResolve" ||
        name == "StructuredResolve" || name == "FlattenResolve" || name == "PrefetchVelocityResolve" || name == "LoadCurrentResolve" ||
        name == "LoadCurrentVelocityResolve" || name == "LoadContrastMask" ||
        name == "StripeBranchResolve" || name == "StripeFlattenResolve" || name == "ScalarWeightResolve" ||
        name == "ScalarReassociatedResolve" || name == "BranchReassociatedResolve" || name == "HistoryLoadResolve" || name == "SelectorAnyResolve" ||
        name == "FixedThresholdResolve" || name == "ScalarFixedThresholdResolve" || name == "NvWarpResolve" || name == "NvWarpMask" ||
        name == "HistoryLinearResolve" || name == "ScalarHistoryLinearResolve" ||
        name == "ScalarCurrentLinearResolve" || name == "CurrentDeJitterResolve" ||
        name == "ScalarDeJitterResolve" || name == "DeJitterMask" || name == "DeJitterSpatial" || name == "PairedDeJitterResolve" || name == "ScalarPairedDeJitterResolve" || name == "SpeedBranch" || name == "SpeedUniformScalar" || name == "SpeedUniformBranch" || name == "SpeedUniformPrefetch" || name == "SpeedUniformWarp" || name == "SpeedPhasePositive" || name == "SpeedPhaseNegative" || name == "SpeedGroup4" || name == "SpeedGroup8" || name == "SpeedGroup16" || name == "SpeedDensity8" || name == "SpeedDensity16" || name == "ContributionNative" || name == "ContributionPaired" || name == "ContributionNativeMask" || name == "ContributionPairedMask" || name == "ContributionZeroMask" || name == "BlendReadControl" || name == "BlendReadOne" || name == "EdgeReadControl" || name == "EdgeReadOne" || name == "EdgeReadPoint" || name == "EdgeReadVerify" || name == "EdgeOnlyOutput" || name == "EdgeOnlyRead" )
    {
        //technique10 Resolve {
        tech->VS->CreateShaderAndILFromFile( shaderFileName, vsVersion, "DX10_SMAAResolveVS", inputElements, shaderMacros, true );
        const char * entry = name == "ScalarCurrentLinearResolve" ? "DX10_SMAAScalarCurrentLinearResolvePS" :
            name == "CurrentDeJitterResolve" ? "DX10_SMAACurrentDeJitterResolvePS" :
            name == "ScalarDeJitterResolve" ? "DX10_SMAAScalarDeJitterResolvePS" :
            name == "DeJitterMask" ? "DX10_SMAADeJitterMaskPS" :
            name == "DeJitterSpatial" ? "DX10_SMAADeJitterSpatialPS" :
            name == "PairedDeJitterResolve" ? "DX10_SMAAPairedDeJitterResolvePS" :
            name == "BlendReadControl" ? "DX10_SMAABlendReadControlPS" :
            name == "BlendReadOne" ? "DX10_SMAABlendReadOnePS" :
            name == "EdgeReadControl" ? "DX10_SMAAEdgeReadControlPS" :
            name == "EdgeReadOne" ? "DX10_SMAAEdgeReadOnePS" :
            name == "EdgeReadPoint" ? "DX10_SMAAEdgeReadPointPS" :
            name == "EdgeReadVerify" ? "DX10_SMAAEdgeReadVerifyPS" :
            name == "EdgeOnlyOutput" ? "DX10_SMAAEdgeOnlyOutputPS" :
            name == "EdgeOnlyRead" ? "DX10_SMAAEdgeOnlyReadPS" :
            name == "ContributionNative" ? "DX10_SMAAContributionNativePS" :
            name == "ContributionPaired" ? "DX10_SMAAContributionPairedPS" :
            name == "ContributionNativeMask" ? "DX10_SMAAContributionNativeMaskPS" :
            name == "ContributionPairedMask" ? "DX10_SMAAContributionPairedMaskPS" :
            name == "ContributionZeroMask" ? "DX10_SMAAContributionZeroMaskPS" :
            name == "SpeedPhasePositive" ? "DX10_SMAASpeedPhasePositivePS" :
            name == "SpeedPhaseNegative" ? "DX10_SMAASpeedPhaseNegativePS" :
            name == "SpeedGroup4" ? "DX10_SMAASpeedGroup4PS" :
            name == "SpeedGroup8" ? "DX10_SMAASpeedGroup8PS" :
            name == "SpeedGroup16" ? "DX10_SMAASpeedGroup16PS" :
            name == "SpeedDensity8" ? "DX10_SMAASpeedDensity8PS" :
            name == "SpeedDensity16" ? "DX10_SMAASpeedDensity16PS" :
            name == "SpeedBranch" ? "DX10_SMAASpeedBranchPS" :
            name == "SpeedUniformScalar" ? "DX10_SMAASpeedUniformScalarPS" :
            name == "SpeedUniformBranch" ? "DX10_SMAASpeedUniformBranchPS" :
            name == "SpeedUniformPrefetch" ? "DX10_SMAASpeedUniformPrefetchPS" :
            name == "SpeedUniformWarp" ? "DX10_SMAASpeedUniformWarpPS" :
            name == "ScalarPairedDeJitterResolve" ? "DX10_SMAAScalarPairedDeJitterResolvePS" :
            name == "HistoryLinearResolve" ? "DX10_SMAAHistoryLinearResolvePS" :
            name == "ScalarHistoryLinearResolve" ? "DX10_SMAAScalarHistoryLinearResolvePS" :
            name == "NvWarpResolve" ? "DX10_SMAANvWarpResolvePS" :
            name == "NvWarpMask" ? "DX10_SMAANvWarpMaskPS" : name == "FixedThresholdResolve" ? "DX10_SMAAFixedThresholdResolvePS" :
            name == "ScalarFixedThresholdResolve" ? "DX10_SMAAScalarFixedThresholdResolvePS" :
            name == "ScalarWeightResolve" ? "DX10_SMAAScalarWeightResolvePS" :
            name == "ScalarReassociatedResolve" ? "DX10_SMAAScalarReassociatedResolvePS" :
            name == "BranchReassociatedResolve" ? "DX10_SMAABranchReassociatedResolvePS" :
            name == "HistoryLoadResolve" ? "DX10_SMAAHistoryLoadResolvePS" :
            name == "SelectorAnyResolve" ? "DX10_SMAASelectorAnyResolvePS" :
            name == "StripeBranchResolve" ? "DX10_SMAAStripeBranchResolvePS" :
            name == "StripeFlattenResolve" ? "DX10_SMAAStripeFlattenResolvePS" :
            name == "ContrastResolve" ? "DX10_SMAAContrastResolvePS" :
            name == "ContrastMask" ? "DX10_SMAAContrastMaskPS" :
            name == "CurrentSpatial" ? "DX10_SMAACurrentSpatialPS" :
            name == "LodResolve" ? "DX10_SMAALodResolvePS" :
            name == "CurrentFirstResolve" ? "DX10_SMAACurrentFirstResolvePS" :
            name == "StructuredResolve" ? "DX10_SMAAStructuredResolvePS" :
            name == "FlattenResolve" ? "DX10_SMAAFlattenResolvePS" :
            name == "LoadCurrentResolve" ? "DX10_SMAALoadCurrentResolvePS" :
            name == "LoadCurrentVelocityResolve" ? "DX10_SMAALoadCurrentVelocityResolvePS" :
            name == "LoadContrastMask" ? "DX10_SMAALoadContrastMaskPS" :
            name == "PrefetchVelocityResolve" ? "DX10_SMAAPrefetchVelocityResolvePS" : "DX10_SMAAResolvePS";
        if(name=="NvWarpResolve" || name=="NvWarpMask" || name=="SpeedUniformWarp" || name=="SpeedGroup4" || name=="SpeedGroup8" || name=="SpeedGroup16" || name=="SpeedDensity8" || name=="SpeedDensity16") {
            const bool groups = name.find("SpeedGroup")==0 || name.find("SpeedDensity")==0;
            if(groups ? SupportsTemporalWarpGroups() : SupportsTemporalWarp()) { shaderMacros.push_back({"VA_NV_WARP_EXTENSION","1"});tech->NvWarp=true; }
            else entry=name.substr(0,5)=="Speed" ? "DX10_SMAAScalarPairedDeJitterResolvePS" : "DX10_SMAAScalarWeightResolvePS"; // Driver rejects unsupported warp experiments before rendering.
        }
        tech->PS->CreateShaderFromFile( shaderFileName, name == "Resolve" ? psVersion : "ps_5_0", entry, shaderMacros, true );
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
    if(NvWarp) {
        ID3D11UnorderedAccessView* empty=nullptr;
        context->OMSetRenderTargetsAndUnorderedAccessViews(D3D11_KEEP_RENDER_TARGETS_AND_DEPTH_STENCIL,
            nullptr,nullptr,7,1,&empty,nullptr);
    }
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
