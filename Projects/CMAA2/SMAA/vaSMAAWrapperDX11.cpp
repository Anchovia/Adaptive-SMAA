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
#include "Core/Misc/vaProfiler.h"
#include <fstream>

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
        ID3D11DepthStencilState *   m_DisableDepthNoStencil         = nullptr;   // depth and stencil Off: no depth writes
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
        shared_ptr<vaTexture>       m_feedbackCurrentSpatial;
        shared_ptr<vaTexture>       m_temporalVelocity              = nullptr;
        shared_ptr<vaTexture>       m_executionCoverage;
        bool m_thinLineRawSaved=false;
        shared_ptr<vaTexture> m_historyWeightDiagnostic;
        shared_ptr<vaTexture> m_presentedOutput;                    // present-history candidate: this frame's next history
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
        virtual shared_ptr<vaTexture>   GetPresentedOutputOverride( ) const override { return m_presentedOutput; }
        virtual int GetEdgeStorageFormatForDiagnostics() const override {
            if(!m_smaa)return 0;
            ID3D11RenderTargetView *view=*m_smaa->getEdgesRenderTarget();
            D3D11_RENDER_TARGET_VIEW_DESC desc;view->GetDesc(&desc);
            return int(desc.Format);
        }
        virtual bool SaveThinLineTraceInputs(vaRenderDeviceContext &ctx,const wstring &prefix) override {
            return m_thinLineRawSaved && !m_thinLineTracePrefix.empty() && m_thinLineTracePrefix==prefix
                && m_temporalHistoryValid
                && (GetResolvedRGBFeedbackEnabled()?m_feedbackCurrentSpatial:m_temporalHistory[1-GetTemporalFrameIndex()])->SaveToDDSFile(ctx,prefix+L"-current.dds")
                && m_temporalHistory[GetTemporalFrameIndex()]->SaveToDDSFile(ctx,prefix+L"-previous.dds")
                && m_temporalVelocity->SaveToDDSFile(ctx,prefix+L"-velocity.dds");
        }
        virtual bool SaveResolvedHistoryDiagnostic(vaRenderDeviceContext &ctx,const wstring &path) override {
            return m_temporalHistoryValid && m_temporalHistory[1-GetTemporalFrameIndex()]->SaveToDDSFile(ctx,path);
        }
        virtual bool SaveHistoryWeightDiagnostic(vaRenderDeviceContext &ctx,const wstring &path) override {
            return m_historyWeightDiagnostic && m_executionDiagnostics && m_historyWeightDiagnostic->SaveToDDSFile(ctx,path);
        }
        virtual bool SaveExecutionCoverage(vaRenderDeviceContext &ctx,const wstring &path) override {
            return m_executionCoverage && m_executionCoverage->SaveToDDSFile(ctx,path);
        }
        virtual bool SaveSpatialEdgeSnapshot(vaRenderDeviceContext &ctx, const wstring &path, bool saveEdge, bool probe) override
        {
            if(m_smaa==nullptr || !m_temporalHistoryValid) return false;
            bool ok=true;
            if(saveEdge) {
            auto dc=ctx.SafeCast<vaRenderDeviceContextDX11*>()->GetDXContext();
            ID3D11Texture2D *edge=*m_smaa->getEdgesRenderTarget();
            D3D11_TEXTURE2D_DESC desc;edge->GetDesc(&desc);
            if(desc.Format!=DXGI_FORMAT_R8G8_UNORM && desc.Format!=DXGI_FORMAT_R8G8_TYPELESS) return false;
            desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;desc.MiscFlags=0;
            ID3D11Texture2D *stage=nullptr;
            if(FAILED(GetRenderDevice().SafeCast<vaRenderDeviceDX11*>()->GetPlatformDevice()->CreateTexture2D(&desc,nullptr,&stage))) return false;
            dc->CopyResource(stage,edge);
            D3D11_MAPPED_SUBRESOURCE mapped;
            if(FAILED(dc->Map(stage,0,D3D11_MAP_READ,0,&mapped))) {stage->Release();return false;}
            std::ofstream out((path+L"-edge.rg8").c_str(),std::ios::binary);
            out.write("EDG1",4);out.write(reinterpret_cast<const char*>(&desc.Width),4);out.write(reinterpret_cast<const char*>(&desc.Height),4);
            for(UINT y=0;y<desc.Height;++y) out.write(static_cast<const char*>(mapped.pData)+y*mapped.RowPitch,desc.Width*2);
            ok=out.good();out.close();dc->Unmap(stage,0);stage->Release();
            }
            const auto spatial=GetResolvedRGBFeedbackEnabled()?m_feedbackCurrentSpatial:m_temporalHistory[1-GetTemporalFrameIndex()];
            ok=ok && spatial->SaveToPNGFile(ctx,path+L"-current.png");
            if(probe) ok=ok && m_externalInputColor->SaveToDDSFile(ctx,path+L"-input.dds")
                && spatial->SaveToDDSFile(ctx,path+L"-spatial.dds")
                && m_temporalVelocity->SaveToDDSFile(ctx,path+L"-velocity.dds");
            return ok;
        }

    private:
        bool                            UpdateResources( vaRenderDeviceContext & deviceContext, const shared_ptr<vaTexture> & inputColor );
        bool                            TemporalResourcesMissing( bool smaaProjection ) const;
        bool                            ValidateSelectedTemporalConfiguration( ) const;

        // Capture-only witnesses around the selected resolve; inactive unless m_executionDiagnostics.
        struct ExecutionDiagnostics
        {
            ID3D11Query *               Stats       = nullptr;
            ID3D11Query *               Samples     = nullptr;
            ID3D11RenderTargetView *    CoverageRTV = nullptr;
            ID3D11RenderTargetView *    WeightRTV   = nullptr;
        };
        bool                            BeginExecutionDiagnostics( ID3D11DeviceContext * dx11Context, const shared_ptr<vaTexture> & inputColor, ExecutionDiagnostics & diagnostics );
        void                            EndExecutionDiagnostics( ID3D11DeviceContext * dx11Context, ExecutionDiagnostics & diagnostics );
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
    m_executionCoverage = nullptr;
    m_historyWeightDiagnostic = nullptr;
    m_presentedOutput = nullptr;
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
        m_feedbackCurrentSpatial = nullptr;
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
        || (GetTemporalModeEnabled( ) && TemporalResourcesMissing( smaaProjection )) )
    {
        SAFE_DELETE( m_smaa );
        CleanupTemporaryResources( );
        SetGlobalStates( deviceContext );
        if(GetResolvedRGBFeedbackEnabled() && m_selectedEdgeRGBA8) {
            UINT support=0;
            const UINT required=D3D11_FORMAT_SUPPORT_TEXTURE2D|D3D11_FORMAT_SUPPORT_SHADER_SAMPLE|D3D11_FORMAT_SUPPORT_RENDER_TARGET;
            if(FAILED(GetRenderDevice().SafeCast<vaRenderDeviceDX11*>()->GetPlatformDevice()->CheckFormatSupport(DXGI_FORMAT_R8G8B8A8_UNORM,&support)) || (support&required)!=required) {
                UnsetGlobalStates(deviceContext);VA_LOG_ERROR("Case19 RGBA8 edge format unsupported");return false;
            }
        }
        m_smaa = new SMAA( GetRenderDevice().SafeCast<vaRenderDeviceDX11*>( )->GetPlatformDevice(), (SMAAShaderConstantsInterface*)this, (SMAATexturesInterface*)this, (SMAATechniqueManagerInterface*)this, inputColor->GetSizeX( ), inputColor->GetSizeY( ),
            ( SMAA::Preset )m_settings.Preset, smaaPredication, smaaProjection, nullptr, SMAA::ExternalStorage(),
            GetResolvedRGBFeedbackEnabled() && m_selectedEdgeRGBA8 );
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
            if(GetResolvedRGBFeedbackEnabled())
                m_feedbackCurrentSpatial = vaTexture::Create2D( inputColor->GetRenderDevice(), inputColor->GetResourceFormat(), inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    historyBindFlags, vaResourceAccessFlags::Default, inputColor->GetSRVFormat(), inputColor->GetRTVFormat(), vaResourceFormat::Unknown, vaResourceFormat::Unknown,
                    vaTextureFlags::None, inputColor->GetContentsType() );
            if( smaaProjection )
                m_temporalVelocity = vaTexture::Create2D( inputColor->GetRenderDevice(), vaResourceFormat::R16G16_FLOAT, inputColor->GetSizeX(), inputColor->GetSizeY(), 1, 1, 1,
                    historyBindFlags, vaResourceAccessFlags::Default );
            if( TemporalResourcesMissing( smaaProjection ) )
                return false;
        }
    }
    
    return true;
}

// History ping-pong, camera velocity and (selected feedback route) the current
// spatial copy that the stencil-gated resolve reads while it writes history.
bool vaSMAAWrapperDX11::TemporalResourcesMissing( bool smaaProjection ) const
{
    return m_temporalHistory[0] == nullptr || m_temporalHistory[1] == nullptr || (smaaProjection && m_temporalVelocity == nullptr)
        || (GetResolvedRGBFeedbackEnabled() && m_feedbackCurrentSpatial == nullptr);
}

// The feedback-route shaders exist only as complete case 11-17 configurations.
bool vaSMAAWrapperDX11::ValidateSelectedTemporalConfiguration( ) const
{
    const bool feedback=GetResolvedRGBFeedbackEnabled();
    if((m_selectedEdgeRGBA8 || m_selectedGatherLuma) && (!feedback || !GetSourceTemporalComponentEnabled())) {
        VA_LOG_ERROR("Case19 spatial candidates require the complete case17 feedback configuration");return false;
    }
    if(GetSourceTemporalComponentEnabled() && !GetFixedHistoryWeight080Enabled()) {
        VA_LOG_ERROR("Source component requires fixed080 case14 configuration");return false;
    }
    if(GetFixedHistoryWeight080Enabled() && (!feedback || !GetCatmullRomHistoryRGBEnabled())) {
        VA_LOG_ERROR("Case14 fixed weight requires case13 selected Catmull-Rom RGB feedback");
        return false;
    }
    if(GetCatmullRomHistoryRGBEnabled() && !feedback) {
        VA_LOG_ERROR("Case13 Catmull-Rom RGB requires resolved RGB feedback");
        return false;
    }
    if(feedback && (!GetSpatialFirstEdgeEnabled() || !GetFirstEdgeStencilEnabled() ||
        !GetPreviousRawEdgesEnabled() || !GetBilinearHistoryRGBEnabled() ||
        GetTemporalSamplePatternEnabled() || !GetTemporalReprojectionEnabled() || GetStencilUpstreamControl())) {
        VA_LOG_ERROR("Resolved RGB feedback requires case10 selected Pattern-Off camera-R configuration");
        return false;
    }
    return true;
}

// Pipeline-statistics/occlusion queries and coverage/weight targets for capture
// evidence only. Timing commands keep m_executionDiagnostics off.
bool vaSMAAWrapperDX11::BeginExecutionDiagnostics( ID3D11DeviceContext * dx11Context, const shared_ptr<vaTexture> & inputColor, ExecutionDiagnostics & diagnostics )
{
    m_executionQueryOK=false;
    if(!m_executionDiagnostics)
        return true;
    auto device=GetRenderDevice().SafeCast<vaRenderDeviceDX11*>()->GetPlatformDevice();
    D3D11_QUERY_DESC q={D3D11_QUERY_PIPELINE_STATISTICS,0};
    if(FAILED(device->CreateQuery(&q,&diagnostics.Stats))) return false;
    q.Query=D3D11_QUERY_OCCLUSION;
    if(FAILED(device->CreateQuery(&q,&diagnostics.Samples))){diagnostics.Stats->Release();return false;}
    if(GetSpatialFirstEdgeEnabled() && GetFirstEdgeStencilEnabled()) {
        if(!m_executionCoverage || m_executionCoverage->GetSizeX()!=inputColor->GetSizeX() || m_executionCoverage->GetSizeY()!=inputColor->GetSizeY())
            m_executionCoverage=vaTexture::Create2D(GetRenderDevice(),vaResourceFormat::R8_UNORM,inputColor->GetSizeX(),inputColor->GetSizeY(),1,1,1,
                vaResourceBindSupportFlags::RenderTarget|vaResourceBindSupportFlags::ShaderResource);
        if(!m_executionCoverage){diagnostics.Stats->Release();diagnostics.Samples->Release();return false;}
        diagnostics.CoverageRTV=m_executionCoverage->SafeCast<vaTextureDX11*>()->GetRTV();
        const float zero[4]={0,0,0,0};dx11Context->ClearRenderTargetView(diagnostics.CoverageRTV,zero);
        if(!m_historyWeightDiagnostic || m_historyWeightDiagnostic->GetSizeX()!=inputColor->GetSizeX() || m_historyWeightDiagnostic->GetSizeY()!=inputColor->GetSizeY())
            m_historyWeightDiagnostic=vaTexture::Create2D(GetRenderDevice(),vaResourceFormat::R32_FLOAT,inputColor->GetSizeX(),inputColor->GetSizeY(),1,1,1,
                vaResourceBindSupportFlags::RenderTarget|vaResourceBindSupportFlags::ShaderResource);
        if(!m_historyWeightDiagnostic){diagnostics.Stats->Release();diagnostics.Samples->Release();return false;}
        diagnostics.WeightRTV=m_historyWeightDiagnostic->SafeCast<vaTextureDX11*>()->GetRTV();
        dx11Context->ClearRenderTargetView(diagnostics.WeightRTV,zero);
    }
    dx11Context->Begin(diagnostics.Stats);dx11Context->Begin(diagnostics.Samples);
    return true;
}

void vaSMAAWrapperDX11::EndExecutionDiagnostics( ID3D11DeviceContext * dx11Context, ExecutionDiagnostics & diagnostics )
{
    if(!m_executionDiagnostics)
        return;
    dx11Context->End(diagnostics.Samples);dx11Context->End(diagnostics.Stats);
    D3D11_QUERY_DATA_PIPELINE_STATISTICS stats={};UINT64 samples=0;
    const ULONGLONG deadline=GetTickCount64()+5000;
    HRESULT a=S_FALSE,b=S_FALSE;
    while((a==S_FALSE || b==S_FALSE) && GetTickCount64()<deadline) {
        if(a==S_FALSE)a=dx11Context->GetData(diagnostics.Stats,&stats,sizeof(stats),0);
        if(b==S_FALSE)b=dx11Context->GetData(diagnostics.Samples,&samples,sizeof(samples),0);
        if(a==S_FALSE || b==S_FALSE)Sleep(0);
    }
    m_executionQueryOK=a==S_OK&&b==S_OK;
    m_lastResolveInvocations=stats.PSInvocations;m_lastResolveSamples=samples;
    diagnostics.Stats->Release();diagnostics.Samples->Release();
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

    if( GetTemporalReprojectionEnabled( ) )
    {
        vaScopeTimer cameraTimer("SR_CameraVelocity", &deviceContext);
        if( optionalDepth == nullptr || optionalCamera == nullptr || !m_generateCameraVelocityPS->IsCreated( ) )
            return vaDrawResultFlags::ShadersStillCompiling;

        m_lastTemporalProjectionOffset = const_cast<vaCameraBase*>(optionalCamera)->GetSubpixelOffset();
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

    // Capture-only input snapshot; never enabled by a timing command.
    m_thinLineRawSaved=false;
    if(!m_thinLineTracePrefix.empty())
        m_thinLineRawSaved=inputColor->SaveToDDSFile(deviceContext,m_thinLineTracePrefix+L"-raw.dds");
    SetGlobalStates( deviceContext );

    if( inputColor->GetArrayCount() == 1 )
    {
        ID3D11ShaderResourceView * colorGammaSRV = (optionalInLuma == nullptr)? m_viewColorIgnoreSRGB0->SafeCast<vaTextureDX11*>( )->GetSRV( ) : optionalInLuma->SafeCast<vaTextureDX11*>( )->GetSRV( );
        SMAA::Input inputMode = (optionalInLuma == nullptr)? SMAA::INPUT_LUMA : SMAA::INPUT_LUMA_RAW;

        if( GetTemporalModeEnabled( ) )
        {
            // Native T2X(-R) uses the original passes. The selected route (cases 6-17) is:
            //  1. go(): the first-pass edge stencil marks the temporal pixels (case 17: current
            //     raw edge OR camera-reprojected previous raw edge; RG keeps current edges only),
            //     weights run on that stencil, and neighborhood blending writes the spatial
            //     result to dstRT (visible) and, with feedback, to currentSpatial and the next
            //     history for every pixel.
            //  2. reprojectFirstEdgeStencil(): stencil-selected pixels overwrite visible and next
            //     history RGB with the resolve. Next-history alpha keeps the current spatial
            //     (velocity) alpha; visible alpha is the resolve's alpha lerp.
            if( !ValidateSelectedTemporalConfiguration( ) )
                return vaDrawResultFlags::UnspecifiedError;
            const bool feedback=GetResolvedRGBFeedbackEnabled();
            const bool firstEdgeStencilRoute=GetSpatialFirstEdgeEnabled() && GetFirstEdgeStencilEnabled();
            assert( m_temporalHistory[0] != nullptr && m_temporalHistory[1] != nullptr );
            assert( m_smaa->getFrameIndex( ) == GetTemporalFrameIndex( ) );

            const int currentIndex = GetTemporalFrameIndex( );
            const int previousIndex = 1 - currentIndex;
            shared_ptr<vaTexture> & currentHistory = m_temporalHistory[currentIndex];
            shared_ptr<vaTexture> & previousHistory = m_temporalHistory[previousIndex];

            // Feedback route: the resolve reads this frame's spatial colour from a separate
            // texture because it writes the next history at the same selected pixels.
            const auto currentSpatial=feedback?m_feedbackCurrentSpatial:currentHistory;
            ID3D11RenderTargetView * currentSpatialRTV = currentSpatial->SafeCast<vaTextureDX11*>( )->GetRTV( );
            ID3D11RenderTargetView * nextHistoryRTV = feedback? currentHistory->SafeCast<vaTextureDX11*>()->GetRTV() : nullptr;
            ID3D11RenderTargetView * visibleRTV = dstRT->SafeCast<vaTextureDX11*>()->GetRTV();
            // Present-history candidate: the next history RGB equals the visible RGB, so the visible
            // slot is left unbound in neighborhood blending and the resolve; same shaders.
            const bool presentHistory = feedback && m_selectedPresentHistory;
            if( presentHistory && m_executionDiagnostics )
            { VA_LOG_ERROR("Present-history candidate has no capture witnesses"); return vaDrawResultFlags::UnspecifiedError; }
            ID3D11ShaderResourceView * spatialColorSRV = m_viewColor0->SafeCast<vaTextureDX11*>( )->GetSRV( );
            ID3D11DepthStencilView * depthDSV = m_texDepthStencil->SafeCast<vaTextureDX11*>( )->GetDSV( );

            ID3D11ShaderResourceView * velocitySRV = GetTemporalReprojectionEnabled( )? m_temporalVelocity->SafeCast<vaTextureDX11*>( )->GetSRV( ) : nullptr;
            {
                vaScopeTimer spatialTimer("SF_Spatial", &deviceContext);
                m_smaa->setPassProfilingContext( m_passProfiling ? &deviceContext : nullptr );
                m_smaa->setClearDepthWithStencil( feedback && m_selectedDepthStencilClear );
                m_smaa->setNeighborhoodWithoutDepth( feedback && m_selectedNeighborhoodWithoutDepth );
                m_smaa->go( dx11Context, colorGammaSRV, spatialColorSRV, nullptr, velocitySRV, currentSpatialRTV, depthDSV, inputMode, GetTemporalSamplePatternEnabled()? SMAA::MODE_SMAA_T2X : SMAA::MODE_SMAA_1X, 0,
                    firstEdgeStencilRoute ? (presentHistory ? nullptr : visibleRTV) : nullptr, GetStencilUpstreamControl(), GetPreviousRawEdgesEnabled(), m_temporalHistoryValid,
                    nextHistoryRTV );
            }

            // Without valid history the previous SRV is the current spatial colour (seed/reset).
            ID3D11ShaderResourceView * currentSpatialSRV = currentSpatial->SafeCast<vaTextureDX11*>( )->GetSRV( );
            ID3D11ShaderResourceView * previousHistorySRV = m_temporalHistoryValid? previousHistory->SafeCast<vaTextureDX11*>( )->GetSRV( ) : currentSpatialSRV;
            ExecutionDiagnostics diagnostics;
            if( !BeginExecutionDiagnostics( dx11Context, inputColor, diagnostics ) )
                return vaDrawResultFlags::UnspecifiedError;
            {
                vaScopeTimer resolveTimer("SR_Resolve", &deviceContext);
                if(firstEdgeStencilRoute) {
                    SMAA::FirstEdgeResolveOptions options;
                    options.bilinearHistoryRGB=GetBilinearHistoryRGBEnabled();
                    options.catmullRomHistoryRGB=GetCatmullRomHistoryRGBEnabled();
                    options.fixedHistoryWeight080=GetFixedHistoryWeight080Enabled();
                    // Seed/reset frames bypass the colour blend and use the fixed-weight resolve.
                    options.sourceTemporalComponent=GetSourceTemporalComponentEnabled() && m_temporalHistoryValid;
                    options.presentHistory=presentHistory;
                    m_smaa->reprojectFirstEdgeStencil(dx11Context,currentSpatialSRV,previousHistorySRV,velocitySRV,visibleRTV,depthDSV,options,
                        nextHistoryRTV,diagnostics.CoverageRTV,diagnostics.WeightRTV);
                }
                else if(GetSpatialFirstEdgeEnabled())
                    m_smaa->reprojectSpatialFirstEdges(dx11Context,currentSpatialSRV,previousHistorySRV,velocitySRV,visibleRTV);
                else
                m_smaa->reproject( dx11Context, currentSpatialSRV, previousHistorySRV, velocitySRV, visibleRTV );
            }
            EndExecutionDiagnostics( dx11Context, diagnostics );
            if( presentHistory )
                m_presentedOutput = currentHistory;
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

    // Selected resolve with visible + next-history MRTs, gated by the first-pass stencil (ref 1).
    auto stencilGatedFeedbackResolve = [&]( const wchar_t * psFileName )
    {
        tech->VS->CreateShaderAndILFromFile(shaderFileName,vsVersion,"DX10_SMAAResolveVS",inputElements,shaderMacros,true);
        tech->PS->CreateShaderFromFile(psFileName,"ps_5_0",name,shaderMacros,true);
        tech->DSS=m_DisableDepthUseStencil;tech->BS=m_NoBlending;
        for(int i=0;i<4;++i)tech->BlendFactor[i]=0;
        tech->SampleMask=0xFFFFFFFF;tech->StencilRef=1;
    };

    if(name.substr(0,16)=="EagerPersistence") {
        shaderMacros.push_back({"PERSISTENCE_EAGER_FETCH","1"});
        const string entry=name.substr(5);
        tech->VS->CreateShaderAndILFromFile(shaderFileName,vsVersion,"DX10_SMAAEdgeDetectionVS",inputElements,shaderMacros,true);
        auto edgeMacros=shaderMacros;
        if(m_selectedGatherLuma && entry=="PersistenceLumaRawEdgePS")
            edgeMacros.push_back({"CASE19_GATHER_LUMA","1"});
        tech->PS->CreateShaderFromFile(L"SMAA/PersistenceEdgeStencil.hlsl","ps_5_0",entry,edgeMacros,true);
        tech->DSS=m_DisableDepthReplaceStencil;tech->BS=m_NoBlending;
        for(int i=0;i<4;++i)tech->BlendFactor[i]=0;
        tech->SampleMask=0xFFFFFFFF;tech->StencilRef=1;
    }
    else if(name=="SourceComponentPS" || name=="SourceComponentCoveragePS")
        stencilGatedFeedbackResolve(L"SMAA/SourceTemporalComponent.hlsl");          // case 17
    else if(name=="FixedWeightRGBFeedbackPS" || name=="FixedWeightRGBFeedbackCoveragePS")
        stencilGatedFeedbackResolve(L"SMAA/FixedWeightRGBFeedback.hlsl");           // case 14; case 17 seed/reset
    else if(name=="CatmullRomRGBFeedbackPS" || name=="CatmullRomRGBFeedbackCoveragePS")
        stencilGatedFeedbackResolve(L"SMAA/CatmullRomRGBFeedback.hlsl");            // case 13
    else if(name=="ResolvedRGBFeedbackPS" || name=="ResolvedRGBFeedbackCoveragePS")
        stencilGatedFeedbackResolve(L"SMAA/ResolvedRGBFeedback.hlsl");              // case 11
    else if(name=="NeighborhoodFeedbackSeedPS" || name=="NeighborhoodFeedbackSeedNoDepthPS") {
        // Full-screen neighborhood blending into spatial, visible and next-history targets.
        // The NoDepth variant runs the same pixel shader with depth disabled (no depth writes).
        tech->VS->CreateShaderAndILFromFile(shaderFileName,vsVersion,"DX10_SMAANeighborhoodBlendingVS",inputElements,shaderMacros,true);
        tech->PS->CreateShaderFromFile(L"SMAA/ResolvedRGBFeedback.hlsl","ps_5_0","NeighborhoodFeedbackSeedPS",shaderMacros,true);
        tech->DSS=name=="NeighborhoodFeedbackSeedNoDepthPS"?m_DisableDepthNoStencil:m_DisableDepthStencil;
        tech->BS=m_NoBlending;
        for(int i=0;i<4;++i)tech->BlendFactor[i]=0;
        tech->SampleMask=0xFFFFFFFF;tech->StencilRef=0;
    }
    else if(name=="ExactLumaEdgePS" || name=="ExactLumaRawEdgePS" || name=="ExactColorEdgePS" || name=="ExactDepthEdgePS"
       || name=="NeighborhoodRetainPS" || name=="FirstEdgeStencilPS" || name=="FirstEdgeStencilCoveragePS"
       || name=="BilinearHistoryRGBPS" || name=="BilinearHistoryRGBCoveragePS" || name=="FirstEdgeStencilWeightCoveragePS") {
        const bool edge=name.substr(0,5)=="Exact";
        const bool retain=name=="NeighborhoodRetainPS";
        tech->VS->CreateShaderAndILFromFile(shaderFileName,vsVersion,edge?"DX10_SMAAEdgeDetectionVS":retain?"DX10_SMAANeighborhoodBlendingVS":"DX10_SMAAResolveVS",inputElements,shaderMacros,true);
        tech->PS->CreateShaderFromFile(L"SMAA/FirstEdgeStencil.hlsl","ps_5_0",name,shaderMacros,true);
        tech->DSS=edge?m_DisableDepthReplaceStencil:retain?m_DisableDepthStencil:m_DisableDepthUseStencil;
        tech->BS=m_NoBlending;
        for(int i=0;i<4;++i)tech->BlendFactor[i]=0;
        tech->SampleMask=0xFFFFFFFF;tech->StencilRef=retain?0:1;
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
    else if( name == "SpatialFirstEdge" )
    {
        tech->VS->CreateShaderAndILFromFile(shaderFileName,vsVersion,"DX10_SMAAResolveVS",inputElements,shaderMacros,true);
        tech->PS->CreateShaderFromFile(L"SMAA/SpatialFirstEdge.hlsl",psVersion,"SpatialFirstEdgePS",shaderMacros,true);
        tech->DSS=m_DisableDepthStencil;tech->BS=m_NoBlending;
        tech->BlendFactor[0]=tech->BlendFactor[1]=tech->BlendFactor[2]=tech->BlendFactor[3]=0;
        tech->SampleMask=0xFFFFFFFF;tech->StencilRef=0;
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
