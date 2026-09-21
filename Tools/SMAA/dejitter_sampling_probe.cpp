// Bounded offscreen D3D11 sampler probe; never part of the rendering pipeline.
// Usage: probe.exe shader.hlsl rgba8-input.bin float4-output.bin phase-index
#include <d3d11.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <fstream>
#include <vector>
#include <stdexcept>
#include <cstdio>
using Microsoft::WRL::ComPtr;
static void check(HRESULT h) { if(FAILED(h)) throw std::runtime_error("D3D11 call failed"); }
int wmain(int argc,wchar_t** argv) {
 try {
    if(argc!=5)throw std::runtime_error("shader input output index required");
    const UINT w=1920,h=1061;
    std::vector<unsigned char> pixels(w*h*4);
    std::ifstream input(argv[2],std::ios::binary);
    if(!input.read((char*)pixels.data(),pixels.size()))throw std::runtime_error("input size");
    ComPtr<ID3DBlob> blob,errors;
    auto hr=D3DCompileFromFile(argv[1],nullptr,D3D_COMPILE_STANDARD_FILE_INCLUDE,"ProbeCS","cs_5_0",
        D3DCOMPILE_ENABLE_STRICTNESS|D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&blob,&errors);
    if(FAILED(hr)&&errors)std::fprintf(stderr,"%s",(const char*)errors->GetBufferPointer());check(hr);
    ComPtr<ID3D11Device> dev;ComPtr<ID3D11DeviceContext> ctx;D3D_FEATURE_LEVEL level;
    check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&dev,&level,&ctx));
    ComPtr<ID3D11ComputeShader> cs;check(dev->CreateComputeShader(blob->GetBufferPointer(),blob->GetBufferSize(),nullptr,&cs));
    D3D11_TEXTURE2D_DESC td{};td.Width=w;td.Height=h;td.MipLevels=td.ArraySize=1;td.SampleDesc.Count=1;
    td.Format=DXGI_FORMAT_R8G8B8A8_UNORM_SRGB;td.BindFlags=D3D11_BIND_SHADER_RESOURCE;
    D3D11_SUBRESOURCE_DATA init{};init.pSysMem=pixels.data();init.SysMemPitch=w*4;
    ComPtr<ID3D11Texture2D> src,dst,readback;check(dev->CreateTexture2D(&td,&init,&src));
    ComPtr<ID3D11ShaderResourceView> srv;check(dev->CreateShaderResourceView(src.Get(),nullptr,&srv));
    td.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;td.BindFlags=D3D11_BIND_UNORDERED_ACCESS;
    check(dev->CreateTexture2D(&td,nullptr,&dst));
    ComPtr<ID3D11UnorderedAccessView> uav;check(dev->CreateUnorderedAccessView(dst.Get(),nullptr,&uav));
    td.BindFlags=0;td.Usage=D3D11_USAGE_STAGING;td.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    check(dev->CreateTexture2D(&td,nullptr,&readback));
    D3D11_SAMPLER_DESC sd{};sd.Filter=D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;sd.MaxLOD=D3D11_FLOAT32_MAX;
    ComPtr<ID3D11SamplerState> sampler;check(dev->CreateSamplerState(&sd,&sampler));
    float constants[12]={};constants[0]=float(_wtoi(argv[4]));
    D3D11_BUFFER_DESC bd{};bd.ByteWidth=sizeof(constants);bd.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
    init={};init.pSysMem=constants;ComPtr<ID3D11Buffer> cb;check(dev->CreateBuffer(&bd,&init,&cb));
    ctx->CSSetShader(cs.Get(),nullptr,0);
    auto s=srv.Get();ctx->CSSetShaderResources(2,1,&s);
    auto u=uav.Get();ctx->CSSetUnorderedAccessViews(0,1,&u,nullptr);
    auto c=cb.Get();ctx->CSSetConstantBuffers(0,1,&c);
    auto t=sampler.Get();ctx->CSSetSamplers(0,1,&t);
    ctx->Dispatch((w+7)/8,(h+7)/8,1);
    ctx->CopyResource(readback.Get(),dst.Get());
    D3D11_MAPPED_SUBRESOURCE map{};check(ctx->Map(readback.Get(),0,D3D11_MAP_READ,0,&map));
    std::ofstream output(argv[3],std::ios::binary);
    for(UINT y=0;y<h;y++)output.write((char*)map.pData+y*map.RowPitch,w*16);
    if(!output)throw std::runtime_error("write failed");
    ctx->Unmap(readback.Get(),0);ctx->ClearState();ctx->Flush();
    std::puts("PASS: bounded production sampling GPU probe complete");return 0;
 }catch(const std::exception& e){std::fprintf(stderr,"FAIL: %s\n",e.what());return 1;}
}
