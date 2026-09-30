// Read-only device capability and shader creation probe. No window, draw or capture.
#include <d3d11.h>
#include <d3dcompiler.h>
#include <cstdio>
#include <cstring>
int main() {
    ID3D11Device *dev=nullptr; ID3D11DeviceContext *ctx=nullptr;
    D3D_FEATURE_LEVEL requested[]={D3D_FEATURE_LEVEL_11_1,D3D_FEATURE_LEVEL_11_0},actual;
    HRESULT hr=D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,requested,2,D3D11_SDK_VERSION,&dev,&actual,&ctx);
    if(FAILED(hr)){std::printf("device_hr=%08x\n",unsigned(hr));return 1;}
    IDXGIDevice *dxgi=nullptr;IDXGIAdapter *adapter=nullptr;
    if(SUCCEEDED(dev->QueryInterface(__uuidof(IDXGIDevice),(void**)&dxgi))) {
        if(SUCCEEDED(dxgi->GetAdapter(&adapter))) {DXGI_ADAPTER_DESC d={};adapter->GetDesc(&d);std::printf("adapter=%ls\n",d.Description);adapter->Release();}
        dxgi->Release();
    }
    D3D11_FEATURE_DATA_D3D11_OPTIONS2 opts={};
    hr=dev->CheckFeatureSupport(D3D11_FEATURE_D3D11_OPTIONS2,&opts,sizeof(opts));
    std::printf("feature_level=%x\noptions2_hr=%08x\nps_stencil_ref=%d\n",unsigned(actual),unsigned(hr),int(opts.PSSpecifiedStencilRefSupported));
    const char *src="void main(float4 p:SV_POSITION,out float4 c:SV_TARGET0,out uint s:SV_StencilRef){c=1;s=((uint)p.x)&1;}";
    const char *profiles[]={"ps_5_0","ps_5_1"};
    for(const char *profile:profiles) {
        ID3DBlob *code=nullptr,*err=nullptr;ID3D11PixelShader *ps=nullptr;
        hr=D3DCompile(src,std::strlen(src),"stencil-capability-probe",nullptr,nullptr,"main",profile,D3DCOMPILE_ENABLE_STRICTNESS,0,&code,&err);
        std::printf("%s_compile_hr=%08x\n",profile,unsigned(hr));
        if(SUCCEEDED(hr)) {hr=dev->CreatePixelShader(code->GetBufferPointer(),code->GetBufferSize(),nullptr,&ps);std::printf("%s_create_hr=%08x\n",profile,unsigned(hr));}
        if(err){std::fprintf(stderr,"%s: %.*s\n",profile,int(err->GetBufferSize()),(const char*)err->GetBufferPointer());err->Release();}
        if(ps)ps->Release();if(code)code->Release();
    }
    ctx->Release();dev->Release();return 0;
}
