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
        bool                        m_temporalHistoryValid           = false;
        bool                        m_previousViewProjValid          = false;
        bool                        m_smaaReprojectionEnabled        = false;
        bool                        m_smaaTSCMAAInspiredEnabled      = false;
        vaMatrix4x4                 m_previousViewProj               = vaMatrix4x4::Identity;

        SMAAReprojectionConstants   m_reprojectionConstants;
        vaTypedConstantBufferWrapper<SMAAReprojectionConstants>
                                    m_reprojectionConstantsBuffer;
        vaAutoRMI<vaPixelShader>    m_generateCameraVelocityPS;
        vaAutoRMI<vaComputeShader>  m_tscmaaExtractCandidatesCS;
        vaAutoRMI<vaComputeShader>  m_tscmaaComputeDispatchArgsCS;
        vaAutoRMI<vaComputeShader>  m_tscmaaResolveCandidatesCS;

        ID3D11UnorderedAccessView * m_tscmaaCandidatesUAV           = nullptr;
        ID3D11Buffer *              m_tscmaaControlBuffer           = nullptr;
        ID3D11UnorderedAccessView * m_tscmaaControlBufferUAV        = nullptr;
        ID3D11Buffer *              m_tscmaaDispatchArgsBuffer      = nullptr;
        ID3D11UnorderedAccessView * m_tscmaaDispatchArgsBufferUAV   = nullptr;


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
    m_reprojectionConstantsBuffer( params ), m_generateCameraVelocityPS( params.RenderDevice ),
    m_tscmaaExtractCandidatesCS( params.RenderDevice ), m_tscmaaComputeDispatchArgsCS( params.RenderDevice ),
    m_tscmaaResolveCandidatesCS( params.RenderDevice )
{
    params; // unreferenced

    ID3D11Device * device = params.RenderDevice.SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice();
    m_generateCameraVelocityPS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "ps_5_0", "DX10_SMAAGenerateCameraVelocityPS", {}, true );
    const vector<pair<string, string>> tscmaaShaderMacros = { { "SMAA_TSCMAA_COMPUTE", "1" } };
    m_tscmaaExtractCandidatesCS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "cs_5_0", "TSCMAAExtractCandidatesCS", tscmaaShaderMacros, true );
    m_tscmaaComputeDispatchArgsCS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "cs_5_0", "TSCMAAComputeDispatchArgsCS", tscmaaShaderMacros, true );
    m_tscmaaResolveCandidatesCS->CreateShaderFromFile( L"SMAA/SMAAWrapper.hlsl", "cs_5_0", "TSCMAAResolveCandidatesCS", tscmaaShaderMacros, true );
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
    m_smaaReprojectionEnabled = false;
    m_smaaTSCMAAInspiredEnabled = false;
    SAFE_RELEASE( m_tscmaaCandidatesUAV );
    SAFE_RELEASE( m_tscmaaControlBufferUAV );
    SAFE_RELEASE( m_tscmaaControlBuffer );
    SAFE_RELEASE( m_tscmaaDispatchArgsBufferUAV );
    SAFE_RELEASE( m_tscmaaDispatchArgsBuffer );
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
        m_temporalSpatialCurrent = nullptr;
    }
}

bool vaSMAAWrapperDX11::UpdateResources( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor )
{
    // this should go to UpdateResources
    bool smaaPredication = false;   // search for SMAA_PREDICATION - this is for additional edge detection (depth-based, or etc.)
    bool smaaProjection = GetTemporalReprojectionEnabled( );
    bool tscmaaInspired = GetTSCMAAInspiredEnabled( );
    assert( inputColor->GetSampleCount() == 1 ); // if MSAA we expect inputs in a resolved array
    assert( inputColor->GetArrayCount() == 1 || inputColor->GetArrayCount() == 2 ); // only 1 or 2 samples supported
    if( m_smaa == nullptr || m_smaa->getPreset( ) != m_settings.Preset || m_smaa->getWidth( ) != inputColor->GetSizeX( ) || m_smaa->getHeight( ) != inputColor->GetSizeY( ) || inputColor->GetArrayCount() != m_sampleCount || m_externalInputColor != inputColor
        || m_smaaReprojectionEnabled != smaaProjection
        || m_smaaTSCMAAInspiredEnabled != tscmaaInspired
        || (GetTemporalModeEnabled( ) && (m_temporalHistory[0] == nullptr || m_temporalHistory[1] == nullptr || (smaaProjection && m_temporalVelocity == nullptr)
            || (tscmaaInspired && (m_temporalSpatialCurrent == nullptr || m_tscmaaCandidatesUAV == nullptr || m_tscmaaControlBufferUAV == nullptr || m_tscmaaDispatchArgsBufferUAV == nullptr)))) )
    {
        SAFE_DELETE( m_smaa );
        CleanupTemporaryResources( );
        SetGlobalStates( deviceContext );
        m_smaa = new SMAA( GetRenderDevice().SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice(), (SMAAShaderConstantsInterface*)this, (SMAATexturesInterface*)this, (SMAATechniqueManagerInterface*)this, inputColor->GetSizeX( ), inputColor->GetSizeY( ),
            ( SMAA::Preset )m_settings.Preset, smaaPredication, smaaProjection );
        m_smaaReprojectionEnabled = smaaProjection;
        m_smaaTSCMAAInspiredEnabled = tscmaaInspired;
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
                | (tscmaaInspired? vaResourceBindSupportFlags::UnorderedAccess : vaResourceBindSupportFlags::None);
            const vaResourceFormat historyUAVFormat = tscmaaInspired? vaResourceFormatHelpers::StripSRGB( inputColor->GetSRVFormat( ) ) : vaResourceFormat::Unknown;
            for( int i = 0; i < 2; i++ )
            {
                m_temporalHistory[i] = vaTexture::Create2D( inputColor->GetRenderDevice(), inputColor->GetResourceFormat(), inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    historyBindFlags, vaResourceAccessFlags::Default, inputColor->GetSRVFormat(), inputColor->GetRTVFormat(), vaResourceFormat::Unknown, historyUAVFormat,
                    vaTextureFlags::None, inputColor->GetContentsType() );
            }
            if( smaaProjection )
                m_temporalVelocity = vaTexture::Create2D( inputColor->GetRenderDevice(), vaResourceFormat::R16G16_FLOAT, inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    historyBindFlags, vaResourceAccessFlags::Default );

            if( tscmaaInspired )
            {
                const vaResourceBindSupportFlags spatialBindFlags = vaResourceBindSupportFlags::RenderTarget | vaResourceBindSupportFlags::ShaderResource;
                m_temporalSpatialCurrent = vaTexture::Create2D( inputColor->GetRenderDevice(), inputColor->GetResourceFormat(), inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    spatialBindFlags, vaResourceAccessFlags::Default, inputColor->GetSRVFormat(), inputColor->GetRTVFormat(), vaResourceFormat::Unknown, vaResourceFormat::Unknown,
                    vaTextureFlags::None, inputColor->GetContentsType() );

                ID3D11Device * d3d11Device = GetRenderDevice().SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice();
                HRESULT hr;
                const UINT candidateCapacity = inputColor->GetSizeX() * inputColor->GetSizeY();
                {
                    CD3D11_BUFFER_DESC bufferDesc( candidateCapacity * sizeof( UINT ), D3D11_BIND_UNORDERED_ACCESS, D3D11_USAGE_DEFAULT, 0,
                        D3D11_RESOURCE_MISC_BUFFER_STRUCTURED, sizeof( UINT ) );
                    V( CreateSMAATemporalBufferAndUAV( d3d11Device, bufferDesc, nullptr, &m_tscmaaCandidatesUAV, 0 ) );
                }
                {
                    CD3D11_BUFFER_DESC bufferDesc( 4 * sizeof( UINT ), D3D11_BIND_UNORDERED_ACCESS, D3D11_USAGE_DEFAULT, 0,
                        D3D11_RESOURCE_MISC_BUFFER_ALLOW_RAW_VIEWS, 0 );
                    V( CreateSMAATemporalBufferAndUAV( d3d11Device, bufferDesc, &m_tscmaaControlBuffer, &m_tscmaaControlBufferUAV, D3D11_BUFFER_UAV_FLAG_RAW ) );
                }
                {
                    CD3D11_BUFFER_DESC bufferDesc( 4 * sizeof( UINT ), D3D11_BIND_UNORDERED_ACCESS, D3D11_USAGE_DEFAULT, 0,
                        D3D11_RESOURCE_MISC_BUFFER_ALLOW_RAW_VIEWS | D3D11_RESOURCE_MISC_DRAWINDIRECT_ARGS, 0 );
                    V( CreateSMAATemporalBufferAndUAV( d3d11Device, bufferDesc, &m_tscmaaDispatchArgsBuffer, &m_tscmaaDispatchArgsBufferUAV, D3D11_BUFFER_UAV_FLAG_RAW ) );
                }
            }

            if( m_temporalHistory[0] == nullptr || m_temporalHistory[1] == nullptr || (smaaProjection && m_temporalVelocity == nullptr)
                || (tscmaaInspired && (m_temporalSpatialCurrent == nullptr || m_tscmaaCandidatesUAV == nullptr || m_tscmaaControlBufferUAV == nullptr
                    || m_tscmaaDispatchArgsBufferUAV == nullptr || m_tscmaaDispatchArgsBuffer == nullptr)) )
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
    if( GetTSCMAAInspiredEnabled( ) && (!m_tscmaaExtractCandidatesCS->IsCreated( ) || !m_tscmaaComputeDispatchArgsCS->IsCreated( )
        || !m_tscmaaResolveCandidatesCS->IsCreated( )) )
        return vaDrawResultFlags::ShadersStillCompiling;

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
        m_reprojectionConstants.TemporalResolution = vaVector4( (float)inputColor->GetSizeX( ), (float)inputColor->GetSizeY( ),
            1.0f / (float)inputColor->GetSizeX( ), 1.0f / (float)inputColor->GetSizeY( ) );
        m_reprojectionConstants.TSCMAAParams = vaVector4( 0.8f, 0.5f, m_temporalHistoryValid? 1.0f : 0.0f,
            vaResourceFormatHelpers::IsSRGB( inputColor->GetSRVFormat( ) )? 1.0f : 0.0f );
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

            ID3D11ShaderResourceView * spatialColorSRV = m_viewColor0->SafeCast<vaTextureDX11*>( )->GetSRV( );
            ID3D11DepthStencilView * depthDSV = m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV( );

            ID3D11ShaderResourceView * velocitySRV = GetTemporalReprojectionEnabled( )? m_temporalVelocity->SafeCast<vaTextureDX11*>( )->GetSRV( ) : nullptr;
            if( GetTSCMAAInspiredEnabled( ) )
            {
                assert( m_temporalSpatialCurrent != nullptr );
                assert( GetTemporalReprojectionEnabled( ) );
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

    ID3D11UnorderedAccessView * UAVs[4] =
    {
        outputHistoryDX11->GetUAV( ),
        m_tscmaaCandidatesUAV,
        m_tscmaaControlBufferUAV,
        m_tscmaaDispatchArgsBufferUAV
    };
    ID3D11UnorderedAccessView * nullUAVs[4] = { nullptr, nullptr, nullptr, nullptr };
    if( UAVs[0] == nullptr )
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
    dx11Context->ClearUnorderedAccessViewUint( m_tscmaaControlBufferUAV, zeroes );
    dx11Context->ClearUnorderedAccessViewUint( m_tscmaaDispatchArgsBufferUAV, zeroes );

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

    {
        VA_SCOPE_CPUGPU_TIMER( TSCMAAOutputCopy, deviceContext );
        dx11Context->CopyResource( destinationDX11->GetResource( ), outputHistoryDX11->GetResource( ) );
    }

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
