#define NOMINMAX
#include <d3d11.h>
#include <d3dcompiler.h>
#include <dxgi.h>
#include <wrl/client.h>
#include <vector>
#include <iostream>
#include <stdexcept>
#include <cmath>
#include <cstdint>
#include <string>
#include <algorithm>
using Microsoft::WRL::ComPtr;
static void check(HRESULT h){if(FAILED(h))throw std::runtime_error("D3D failure "+std::to_string(unsigned(h)));}
int main()try {
    ComPtr<ID3D11Device> d;ComPtr<ID3D11DeviceContext> c;D3D_FEATURE_LEVEL fl;
    D3D_FEATURE_LEVEL want=D3D_FEATURE_LEVEL_11_0;
    check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,&want,1,D3D11_SDK_VERSION,&d,&fl,&c));
    ComPtr<IDXGIDevice> gd;check(d.As(&gd));ComPtr<IDXGIAdapter> ad;check(gd->GetAdapter(&ad));
    DXGI_ADAPTER_DESC adapter;check(ad->GetDesc(&adapter));
    std::wcout<<L"Adapter: "<<adapter.Description<<L"\n";
    for(auto f:{DXGI_FORMAT_R8_UNORM,DXGI_FORMAT_R8G8_UNORM,DXGI_FORMAT_R8G8B8A8_UNORM}) {
        UINT support=0;check(d->CheckFormatSupport(f,&support));
        const UINT required=D3D11_FORMAT_SUPPORT_TEXTURE2D|D3D11_FORMAT_SUPPORT_SHADER_SAMPLE|D3D11_FORMAT_SUPPORT_RENDER_TARGET;
        if((support&required)!=required)throw std::runtime_error("Missing format capability");
        std::cout<<"format "<<int(f)<<" support "<<support<<"\n";
    }
    ComPtr<ID3DBlob> code,msg;
    HRESULT h=D3DCompileFromFile(L"Tools/SMAA/Case19GpuProbe.hlsl",nullptr,D3D_COMPILE_STANDARD_FILE_INCLUDE,
        "Probe","cs_5_0",D3DCOMPILE_ENABLE_STRICTNESS|D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&code,&msg);
    if(msg)std::cerr.write((const char*)msg->GetBufferPointer(),msg->GetBufferSize());check(h);
    ComPtr<ID3D11ComputeShader> shader;check(d->CreateComputeShader(code->GetBufferPointer(),code->GetBufferSize(),nullptr,&shader));
    D3D11_SAMPLER_DESC sd={};sd.Filter=D3D11_FILTER_MIN_MAG_MIP_POINT;
    sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;sd.MaxLOD=D3D11_FLOAT32_MAX;
    ComPtr<ID3D11SamplerState> point,linear;check(d->CreateSamplerState(&sd,&point));
    sd.Filter=D3D11_FILTER_MIN_MAG_LINEAR_MIP_POINT;check(d->CreateSamplerState(&sd,&linear));
    ID3D11SamplerState *samplers[]={point.Get(),linear.Get()};c->CSSetSamplers(0,2,samplers);
    c->CSSetShader(shader.Get(),nullptr,0);
    uint64_t checkedPixels=0;int cases=0;uint32_t rng=12345;
    for(auto size:std::vector<std::pair<int,int>>{{1,1},{2,3},{7,5},{65,33},{1920,1061},{1901,1003}})for(int pattern=0;pattern<5;++pattern) {
        const int w=size.first,hh=size.second,n=w*hh;
        std::vector<unsigned char> raw(n),rg(n*2),rgba(n*4);
        for(int y=0;y<hh;++y)for(int x=0;x<w;++x) {
            const int i=x+y*w;rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;
            raw[i]=pattern==0?0:pattern==1?255:pattern==2?(x+31*y)%256:pattern==3?((x+y)%2?255:0):rng&255;
            rg[2*i]=rgba[4*i]=(raw[i]&1)?255:0;
            rg[2*i+1]=rgba[4*i+1]=(raw[i]&2)?255:0;
        }
        ComPtr<ID3D11Texture2D> textures[3];ComPtr<ID3D11ShaderResourceView> views[3];
        const DXGI_FORMAT formats[]={DXGI_FORMAT_R8_UNORM,DXGI_FORMAT_R8G8_UNORM,DXGI_FORMAT_R8G8B8A8_UNORM};
        const void *data[]={raw.data(),rg.data(),rgba.data()};
        for(int j=0;j<3;++j) {
            D3D11_TEXTURE2D_DESC td={};td.Width=w;td.Height=hh;td.MipLevels=td.ArraySize=1;
            td.Format=formats[j];td.SampleDesc.Count=1;td.Usage=D3D11_USAGE_IMMUTABLE;td.BindFlags=D3D11_BIND_SHADER_RESOURCE;
            D3D11_SUBRESOURCE_DATA init={data[j],UINT(w*(1<<j)),0};
            check(d->CreateTexture2D(&td,&init,&textures[j]));check(d->CreateShaderResourceView(textures[j].Get(),nullptr,&views[j]));
        }
        ID3D11ShaderResourceView *srvs[]={views[0].Get(),views[1].Get(),views[2].Get()};c->CSSetShaderResources(0,3,srvs);
        const float metrics[]={1.0f/w,1.0f/hh,float(w),float(hh)};
        D3D11_BUFFER_DESC bd={};bd.ByteWidth=sizeof(metrics);bd.Usage=D3D11_USAGE_IMMUTABLE;bd.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
        D3D11_SUBRESOURCE_DATA init={metrics,0,0};ComPtr<ID3D11Buffer> cb;check(d->CreateBuffer(&bd,&init,&cb));
        ID3D11Buffer *cbs[]={cb.Get()};c->CSSetConstantBuffers(0,1,cbs);
        bd={};bd.ByteWidth=n*16;bd.Usage=D3D11_USAGE_DEFAULT;bd.BindFlags=D3D11_BIND_UNORDERED_ACCESS;
        bd.MiscFlags=D3D11_RESOURCE_MISC_BUFFER_STRUCTURED;bd.StructureByteStride=16;
        ComPtr<ID3D11Buffer> out,staging;check(d->CreateBuffer(&bd,nullptr,&out));
        ComPtr<ID3D11UnorderedAccessView> uav;check(d->CreateUnorderedAccessView(out.Get(),nullptr,&uav));
        ID3D11UnorderedAccessView *uavs[]={uav.Get()};c->CSSetUnorderedAccessViews(0,1,uavs,nullptr);
        c->Dispatch((w+7)/8,(hh+7)/8,1);
        ID3D11UnorderedAccessView *nullUAV=nullptr;c->CSSetUnorderedAccessViews(0,1,&nullUAV,nullptr);
        bd.Usage=D3D11_USAGE_STAGING;bd.BindFlags=0;bd.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
        bd.MiscFlags=0;bd.StructureByteStride=0;check(d->CreateBuffer(&bd,nullptr,&staging));c->CopyResource(staging.Get(),out.Get());
        D3D11_MAPPED_SUBRESOURCE mapped;check(c->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped));
        const float *values=(const float*)mapped.pData;
        int bad=0;float worst=0;for(int i=0;i<n*4;++i)if(!std::isfinite(values[i])||values[i]!=0){++bad;worst=std::max(worst,values[i]);}
        c->Unmap(staging.Get(),0);if(bad){std::cerr<<"FAIL "<<w<<"x"<<hh<<" pattern "<<pattern<<" mismatches "<<bad<<" max "<<worst<<"\n";return 1;}
        checkedPixels+=n;++cases;
    }
    std::cout<<"PASS: "<<cases<<" fixtures, "<<checkedPixels<<" pixels, gather and RG8/RGBA8 linear-sample mismatch 0\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}
