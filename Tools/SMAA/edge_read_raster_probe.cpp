// Isolated correctness-only raster probe. No timing or production resources.
#include <d3d11.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <vector>
#include <stdexcept>
#include <cstdio>
#include <cstring>
#include <cmath>
using Microsoft::WRL::ComPtr;
static void check(HRESULT h) { if(FAILED(h))throw std::runtime_error("D3D11 failure"); }
static ComPtr<ID3DBlob> compile(const wchar_t* path,const char* entry,const char* target) {
    ComPtr<ID3DBlob> code,errors;
    HRESULT hr=D3DCompileFromFile(path,nullptr,D3D_COMPILE_STANDARD_FILE_INCLUDE,entry,target,
        D3DCOMPILE_ENABLE_STRICTNESS|D3DCOMPILE_WARNINGS_ARE_ERRORS|D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&code,&errors);
    if(FAILED(hr)&&errors)std::fprintf(stderr,"%s",(const char*)errors->GetBufferPointer());
    check(hr);return code;
}
int wmain(int argc,wchar_t** argv) {
 try {
    if(argc!=2)throw std::runtime_error("shader path required");
    auto vb=compile(argv[1],"ProbeVS","vs_5_0"),pb=compile(argv[1],"ProbePS","ps_5_0");
    ComPtr<ID3D11Device> dev;ComPtr<ID3D11DeviceContext> ctx;D3D_FEATURE_LEVEL level;
    check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&dev,&level,&ctx));
    ComPtr<IDXGIDevice> gd;check(dev.As(&gd));ComPtr<IDXGIAdapter> adapter;check(gd->GetAdapter(&adapter));
    DXGI_ADAPTER_DESC ad{};check(adapter->GetDesc(&ad));
    ComPtr<ID3D11VertexShader> vs;ComPtr<ID3D11PixelShader> ps;
    check(dev->CreateVertexShader(vb->GetBufferPointer(),vb->GetBufferSize(),nullptr,&vs));
    check(dev->CreatePixelShader(pb->GetBufferPointer(),pb->GetBufferSize(),nullptr,&ps));
    D3D11_SAMPLER_DESC sd{};sd.Filter=D3D11_FILTER_MIN_MAG_MIP_POINT;
    sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;sd.MaxLOD=D3D11_FLOAT32_MAX;
    ComPtr<ID3D11SamplerState> sampler;check(dev->CreateSamplerState(&sd,&sampler));
    D3D11_RASTERIZER_DESC rd{};rd.FillMode=D3D11_FILL_SOLID;rd.CullMode=D3D11_CULL_NONE;rd.DepthClipEnable=TRUE;
    ComPtr<ID3D11RasterizerState> raster;check(dev->CreateRasterizerState(&rd,&raster));
    D3D11_DEPTH_STENCIL_DESC dd{};dd.DepthEnable=FALSE;dd.DepthFunc=D3D11_COMPARISON_ALWAYS;
    ComPtr<ID3D11DepthStencilState> depth;check(dev->CreateDepthStencilState(&dd,&depth));
    const UINT dims[][2]={{1,1},{3,5},{1919,1061},{1920,1061},{1920,1080}};
    std::printf("{\"vendor_id\":%u,\"device_id\":%u,\"feature_level\":%u,\"fixtures\":[\n",ad.VendorId,ad.DeviceId,UINT(level));
    bool first=true;unsigned long long allPixels=0;
    for(auto &dim:dims)for(UINT pattern=0;pattern<2;++pattern)for(UINT phase=0;phase<2;++phase) {
        const UINT w=dim[0],h=dim[1];std::vector<unsigned char> pixels(size_t(w)*h*2);
        for(UINT y=0;y<h;++y)for(UINT x=0;x<w;++x)for(UINT c=0;c<2;++c) {
            UINT hash=(x*1664525u)^(y*1013904223u)^(phase*2246822519u)^(c*3266489917u);
            hash^=hash>>13;hash*=1274126177u;hash^=hash>>16;
            pixels[(size_t(y)*w+x)*2+c]=pattern?((hash&1)?255:0):static_cast<unsigned char>(hash&255);
        }
        D3D11_TEXTURE2D_DESC td{};td.Width=w;td.Height=h;td.MipLevels=td.ArraySize=td.SampleDesc.Count=1;
        td.Format=DXGI_FORMAT_R8G8_UNORM;td.BindFlags=D3D11_BIND_SHADER_RESOURCE;
        D3D11_SUBRESOURCE_DATA init{};init.pSysMem=pixels.data();init.SysMemPitch=w*2;
        ComPtr<ID3D11Texture2D> src,dst,staging;check(dev->CreateTexture2D(&td,&init,&src));
        ComPtr<ID3D11ShaderResourceView> srv;check(dev->CreateShaderResourceView(src.Get(),nullptr,&srv));
        td.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;td.BindFlags=D3D11_BIND_RENDER_TARGET;
        check(dev->CreateTexture2D(&td,nullptr,&dst));ComPtr<ID3D11RenderTargetView> rtv;
        check(dev->CreateRenderTargetView(dst.Get(),nullptr,&rtv));
        td.BindFlags=0;td.Usage=D3D11_USAGE_STAGING;td.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
        check(dev->CreateTexture2D(&td,nullptr,&staging));
        const float clear[4]={-1,-1,-1,-1};ctx->ClearRenderTargetView(rtv.Get(),clear);
        auto r=rtv.Get();ctx->OMSetRenderTargets(1,&r,nullptr);ctx->OMSetDepthStencilState(depth.Get(),0);
        ctx->RSSetState(raster.Get());D3D11_VIEWPORT vp{};vp.Width=float(w);vp.Height=float(h);vp.MaxDepth=1;
        ctx->RSSetViewports(1,&vp);ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
        ctx->VSSetShader(vs.Get(),nullptr,0);ctx->PSSetShader(ps.Get(),nullptr,0);
        auto s=srv.Get();auto t=sampler.Get();ctx->PSSetShaderResources(8,1,&s);ctx->PSSetSamplers(1,1,&t);
        ctx->Draw(3,0);ctx->OMSetRenderTargets(0,nullptr,nullptr);ctx->CopyResource(staging.Get(),dst.Get());
        D3D11_MAPPED_SUBRESOURCE map{};check(ctx->Map(staging.Get(),0,D3D11_MAP_READ,0,&map));
        unsigned long long mismatch=0,cpuMismatch=0,borderMismatch=0;
        double maxCPUError=0;
        for(UINT y=0;y<h;++y) {
            auto f=reinterpret_cast<const float*>(static_cast<const char*>(map.pData)+size_t(y)*map.RowPitch);
            for(UINT x=0;x<w;++x) {
                bool bad=std::memcmp(f+x*4,f+x*4+2,2*sizeof(float))!=0;
                mismatch+=bad;if(x==0||y==0||x==w-1||y==h-1)borderMismatch+=bad;
                for(UINT c=0;c<2;++c) {
                    const double expected=double(pixels[(size_t(y)*w+x)*2+c])/255.0;
                    const double error=std::fabs(double(f[x*4+c])-expected);
                    if(error>maxCPUError)maxCPUError=error;
                    if(!std::isfinite(f[x*4+c])||error>1e-7)++cpuMismatch;
                }
            }
        }
        ctx->Unmap(staging.Get(),0);ctx->ClearState();ctx->Flush();
        if(!first)std::printf(",\n");first=false;allPixels+=size_t(w)*h;
        std::printf("{\"width\":%u,\"height\":%u,\"pattern\":%u,\"phase\":%u,\"pixels\":%llu,\"rg_bit_mismatches\":%llu,\"border_mismatches\":%llu,\"cpu_value_mismatches\":%llu,\"max_cpu_error\":%.12g}",w,h,pattern,phase,static_cast<unsigned long long>(w)*h,mismatch,borderMismatch,cpuMismatch,maxCPUError);
        if(mismatch||cpuMismatch)throw std::runtime_error("pixel equality failed");
    }
    std::printf("\n],\"total_pixels\":%llu,\"validation\":\"PASS\"}\n",allPixels);return 0;
 }catch(const std::exception& e){std::fprintf(stderr,"FAIL: %s\n",e.what());return 1;}
}
