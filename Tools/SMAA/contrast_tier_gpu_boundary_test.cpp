// Standalone, bounded D3D11 engineering test. No scene, window, or benchmark.
// Compile from an x64 VS developer prompt with:
// cl /EHsc /W4 contrast_tier_gpu_boundary_test.cpp d3d11.lib d3dcompiler.lib dxguid.lib
// argv[1]: generated HLSL harness including the actual SMAAWrapper.hlsl.
#include <d3d11.h>
#include <d3dcompiler.h>
#include <d3d11shader.h>
#include <wrl/client.h>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <vector>
using Microsoft::WRL::ComPtr;
static void check(HRESULT hr) { if(FAILED(hr)) throw std::runtime_error("D3D call failed"); }
int wmain(int argc, wchar_t **argv)
{
    try {
        if(argc != 2) throw std::runtime_error("Expected HLSL harness path");
        ComPtr<ID3DBlob> bytecode, errors;
        HRESULT hr = D3DCompileFromFile(argv[1], nullptr, D3D_COMPILE_STANDARD_FILE_INCLUDE,
            "ContrastBoundaryCS", "cs_5_0", D3DCOMPILE_ENABLE_STRICTNESS |
            D3DCOMPILE_WARNINGS_ARE_ERRORS | D3DCOMPILE_OPTIMIZATION_LEVEL3, 0,
            &bytecode, &errors);
        if(FAILED(hr) && errors) std::fprintf(stderr, "%s", (const char*)errors->GetBufferPointer());
        check(hr);
        ComPtr<ID3D11Device> device;
        ComPtr<ID3D11DeviceContext> context;
        D3D_FEATURE_LEVEL level;
        check(D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0,
            nullptr, 0, D3D11_SDK_VERSION, &device, &level, &context));
        if(level < D3D_FEATURE_LEVEL_11_0) throw std::runtime_error("D3D11 required");
        ComPtr<ID3D11ComputeShader> shader;
        check(device->CreateComputeShader(bytecode->GetBufferPointer(), bytecode->GetBufferSize(), nullptr, &shader));
        ComPtr<ID3D11ShaderReflection> reflection;
        check(D3DReflect(bytecode->GetBufferPointer(), bytecode->GetBufferSize(),
            IID_ID3D11ShaderReflection, (void**)reflection.GetAddressOf()));
        auto cb = reflection->GetConstantBufferByIndex(0);
        // Locate the constant buffer containing the actual production variable.
        D3D11_SHADER_DESC shaderDesc{};
        check(reflection->GetDesc(&shaderDesc));
        ID3D11ShaderReflectionVariable *variable = nullptr;
        D3D11_SHADER_VARIABLE_DESC vd{};
        for(UINT i=0; i<shaderDesc.ConstantBuffers; ++i) {
            auto candidate = reflection->GetConstantBufferByIndex(i);
            auto v = candidate->GetVariableByName("g_SMAAReprojection");
            if(SUCCEEDED(v->GetDesc(&vd))) { cb=candidate; variable=v; break; }
        }
        if(!variable) throw std::runtime_error("Production constants not found");
        D3D11_SHADER_BUFFER_DESC cbd{}; check(cb->GetDesc(&cbd));
        D3D11_SHADER_TYPE_DESC member{};
        check(variable->GetType()->GetMemberTypeByName("TSCMAACandidateParams")->GetDesc(&member));
        D3D11_SHADER_INPUT_BIND_DESC binding{};
        check(reflection->GetResourceBindingDescByName(cbd.Name, &binding));
        std::vector<unsigned char> constants(cbd.Size, 0);
        const size_t policyOffset = vd.StartOffset + member.Offset + sizeof(float);
        if(policyOffset + sizeof(float) > constants.size()) throw std::runtime_error("Constant offset out of range");
        ComPtr<ID3D11Buffer> constantBuffer;
        D3D11_BUFFER_DESC bd{};
        bd.ByteWidth=cbd.Size; bd.Usage=D3D11_USAGE_DEFAULT; bd.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
        check(device->CreateBuffer(&bd, nullptr, &constantBuffer));
        std::vector<float> inputs;
        for(float bound : {0.1f, 1.0f/3.0f}) {
            inputs.push_back(std::nextafter(bound, -std::numeric_limits<float>::infinity()));
            inputs.push_back(bound);
            inputs.push_back(std::nextafter(bound, std::numeric_limits<float>::infinity()));
        }
        inputs.push_back(0.0f); inputs.push_back(1.0f);
        const UINT n=(UINT)inputs.size();
        ComPtr<ID3D11Buffer> input, output, staging;
        bd={}; bd.ByteWidth=n*sizeof(float); bd.Usage=D3D11_USAGE_DEFAULT;
        bd.BindFlags=D3D11_BIND_SHADER_RESOURCE; bd.MiscFlags=D3D11_RESOURCE_MISC_BUFFER_STRUCTURED;
        bd.StructureByteStride=sizeof(float);
        D3D11_SUBRESOURCE_DATA init{}; init.pSysMem=inputs.data();
        check(device->CreateBuffer(&bd, &init, &input));
        bd.ByteWidth=n*2*sizeof(UINT); bd.BindFlags=D3D11_BIND_UNORDERED_ACCESS;
        check(device->CreateBuffer(&bd, nullptr, &output));
        bd.Usage=D3D11_USAGE_STAGING; bd.BindFlags=0; bd.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
        bd.MiscFlags=0; bd.StructureByteStride=0;
        check(device->CreateBuffer(&bd, nullptr, &staging));
        ComPtr<ID3D11ShaderResourceView> srv;
        ComPtr<ID3D11UnorderedAccessView> uav;
        check(device->CreateShaderResourceView(input.Get(), nullptr, &srv));
        check(device->CreateUnorderedAccessView(output.Get(), nullptr, &uav));
        context->CSSetShader(shader.Get(), nullptr, 0);
        ID3D11Buffer *cbPtr=constantBuffer.Get();
        context->CSSetConstantBuffers(binding.BindPoint,1,&cbPtr);
        ID3D11ShaderResourceView *srvPtr=srv.Get();
        context->CSSetShaderResources(0,1,&srvPtr);
        ID3D11UnorderedAccessView *uavPtr=uav.Get();
        context->CSSetUnorderedAccessViews(0,1,&uavPtr,nullptr);
        UINT checked=0;
        for(int policy : {3,4,5}) {
            const float policyFloat=(float)policy;
            std::memcpy(constants.data()+policyOffset,&policyFloat,sizeof(float));
            context->UpdateSubresource(constantBuffer.Get(),0,nullptr,constants.data(),0,0);
            context->Dispatch(n,1,1);
            context->CopyResource(staging.Get(),output.Get());
            D3D11_MAPPED_SUBRESOURCE mapped{};
            check(context->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped));
            const UINT *values=(const UINT*)mapped.pData;
            bool pass=true;
            for(UINT i=0;i<n;++i) {
                bool expected=policy==3 ? inputs[i]>=1.0f/3.0f : policy==4 ? inputs[i]>=0.1f : inputs[i]<0.1f;
                pass=pass && values[2*i]==(UINT)expected && values[2*i+1]==0;
                checked+=2;
            }
            context->Unmap(staging.Get(),0);
            if(!pass) throw std::runtime_error("GPU boundary/base-gating mismatch");
        }
        context->ClearState(); context->Flush();
        std::printf("PASS: actual production selector, hardware D3D11, %u boundary/base-gating checks\n",checked);
        return 0;
    } catch(const std::exception &e) { std::fprintf(stderr,"FAIL: %s\n",e.what()); return 1; }
}
