#include <d3d11.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <fstream>
#include <iostream>
#include <vector>
#include <stdexcept>
#include <string>
#include <cstdint>
using Microsoft::WRL::ComPtr;
static void Check(HRESULT hr) { if(FAILED(hr)) throw std::runtime_error("D3D11 operation failed: "+std::to_string(uint32_t(hr))); }
int wmain(int argc,wchar_t **argv) {
    if(argc!=4) return 2;
    try {
        std::ifstream input(argv[1],std::ios::binary);
        uint32_t width,height,count;
        input.read(reinterpret_cast<char*>(&width),4);input.read(reinterpret_cast<char*>(&height),4);input.read(reinterpret_cast<char*>(&count),4);
        if(!input||width==0||height==0||count==0||count>65536) return 3;
        std::vector<uint8_t> pixels(size_t(width)*height*4);
        std::vector<float> uv(size_t(count)*2);
        input.read(reinterpret_cast<char*>(pixels.data()),pixels.size());
        input.read(reinterpret_cast<char*>(uv.data()),uv.size()*4);
        if(!input) return 4;
        ComPtr<ID3D11Device> device;ComPtr<ID3D11DeviceContext> context;
        D3D_FEATURE_LEVEL feature;
        Check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&device,&feature,&context));
        if(feature<D3D_FEATURE_LEVEL_11_0) return 5;
        ComPtr<ID3DBlob> bytecode,errors;
        const auto compile=D3DCompileFromFile(argv[3],nullptr,D3D_COMPILE_STANDARD_FILE_INCLUDE,"main","cs_5_0",D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&bytecode,&errors);
        if(FAILED(compile)&&errors) std::cerr.write(static_cast<const char*>(errors->GetBufferPointer()),errors->GetBufferSize());
        Check(compile);
        ComPtr<ID3D11ComputeShader> shader;Check(device->CreateComputeShader(bytecode->GetBufferPointer(),bytecode->GetBufferSize(),nullptr,&shader));
        D3D11_TEXTURE2D_DESC td={};td.Width=width;td.Height=height;td.MipLevels=1;td.ArraySize=1;td.Format=DXGI_FORMAT_R8G8B8A8_TYPELESS;td.SampleDesc.Count=1;td.Usage=D3D11_USAGE_IMMUTABLE;td.BindFlags=D3D11_BIND_SHADER_RESOURCE;
        D3D11_SUBRESOURCE_DATA data={pixels.data(),width*4,0};
        ComPtr<ID3D11Texture2D> texture;Check(device->CreateTexture2D(&td,&data,&texture));
        D3D11_SHADER_RESOURCE_VIEW_DESC srv={};srv.Format=DXGI_FORMAT_R8G8B8A8_UNORM_SRGB;srv.ViewDimension=D3D11_SRV_DIMENSION_TEXTURE2D;srv.Texture2D.MipLevels=1;
        ComPtr<ID3D11ShaderResourceView> textureView;Check(device->CreateShaderResourceView(texture.Get(),&srv,&textureView));
        D3D11_BUFFER_DESC bd={};bd.ByteWidth=count*8;bd.Usage=D3D11_USAGE_IMMUTABLE;bd.BindFlags=D3D11_BIND_SHADER_RESOURCE;bd.MiscFlags=D3D11_RESOURCE_MISC_BUFFER_STRUCTURED;bd.StructureByteStride=8;
        data={uv.data(),0,0};ComPtr<ID3D11Buffer> positions;Check(device->CreateBuffer(&bd,&data,&positions));
        ComPtr<ID3D11ShaderResourceView> positionsView;Check(device->CreateShaderResourceView(positions.Get(),nullptr,&positionsView));
        bd.ByteWidth=count*32;bd.Usage=D3D11_USAGE_DEFAULT;bd.BindFlags=D3D11_BIND_UNORDERED_ACCESS;bd.StructureByteStride=16;
        ComPtr<ID3D11Buffer> result;Check(device->CreateBuffer(&bd,nullptr,&result));
        ComPtr<ID3D11UnorderedAccessView> resultView;Check(device->CreateUnorderedAccessView(result.Get(),nullptr,&resultView));
        bd.Usage=D3D11_USAGE_STAGING;bd.BindFlags=0;bd.CPUAccessFlags=D3D11_CPU_ACCESS_READ;bd.MiscFlags=0;bd.StructureByteStride=0;
        ComPtr<ID3D11Buffer> staging;Check(device->CreateBuffer(&bd,nullptr,&staging));
        D3D11_SAMPLER_DESC sd={};sd.Filter=D3D11_FILTER_MIN_MAG_LINEAR_MIP_POINT;sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;sd.MaxLOD=D3D11_FLOAT32_MAX;
        ComPtr<ID3D11SamplerState> sampler;Check(device->CreateSamplerState(&sd,&sampler));
        ID3D11ShaderResourceView *views[]={textureView.Get(),positionsView.Get()};
        ID3D11SamplerState *samplers[]={sampler.Get()};ID3D11UnorderedAccessView *uavs[]={resultView.Get()};
        context->CSSetShader(shader.Get(),nullptr,0);context->CSSetShaderResources(0,2,views);context->CSSetSamplers(0,1,samplers);context->CSSetUnorderedAccessViews(0,1,uavs,nullptr);
        context->Dispatch((count+63)/64,1,1);
        ID3D11UnorderedAccessView *empty[]={nullptr};context->CSSetUnorderedAccessViews(0,1,empty,nullptr);
        context->CopyResource(staging.Get(),result.Get());
        D3D11_MAPPED_SUBRESOURCE mapped={};Check(context->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped));
        std::ofstream output(argv[2],std::ios::binary);output.write(static_cast<const char*>(mapped.pData),count*32);context->Unmap(staging.Get(),0);
        std::cout<<"PASS hardware filter probe: "<<count<<" samples\n";
        return output?0:6;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
