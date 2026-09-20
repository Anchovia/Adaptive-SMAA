#include <windows.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <cstdio>
#include <stdexcept>
#include "../../Modules/Rendering/DirectX/vaNvWarpDX11.h"
using Microsoft::WRL::ComPtr;
static void check(HRESULT hr) { if(FAILED(hr)) { printf("HRESULT=%08lx\n",(unsigned long)hr);throw std::runtime_error("D3D11 call failed"); } }
int main() {
 try {
    ComPtr<ID3D11Device> d; ComPtr<ID3D11DeviceContext> c;
    check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&d,nullptr,&c));
    bool any=TemporalNvWarp::Supported(d.Get()),ballot=false,lane=false;
    NvAPI_D3D11_IsNvShaderExtnOpCodeSupported(d.Get(),NV_EXTN_OP_VOTE_BALLOT,&ballot);
    NvAPI_D3D11_IsNvShaderExtnOpCodeSupported(d.Get(),NV_EXTN_OP_GET_LANE_ID,&lane);
    printf("NVAPI support: any=%d ballot=%d lane=%d\n",any,ballot,lane);
    if(!any || !ballot || !lane) return 2;
    ComPtr<ID3DBlob> vsb,psb,error;
    // Compiled by the SDK FXC in the runner, which resolves nested SDK includes.
    check(D3DReadFileToBlob(L"tmp/nvprobe-vs.dxbc",&vsb));
    check(D3DReadFileToBlob(L"tmp/nvprobe-ps.dxbc",&psb));
    ComPtr<ID3D11VertexShader> vs; ComPtr<ID3D11PixelShader> ps;
    check(d->CreateVertexShader(vsb->GetBufferPointer(),vsb->GetBufferSize(),nullptr,&vs));
    printf("PS compiled; slot enable=%d\n",NvAPI_D3D11_SetNvShaderExtnSlotLocalThread(d.Get(),7));
    printf("slot reset=%d\n",NvAPI_D3D11_SetNvShaderExtnSlotLocalThread(d.Get(),~0u));
    check(TemporalNvWarp::CreatePixelShader(d.Get(),psb->GetBufferPointer(),psb->GetBufferSize(),&ps));printf("PS created\n");
    D3D11_TEXTURE2D_DESC td={}; td.Width=129;td.Height=17;td.MipLevels=1;td.ArraySize=1;
    td.Format=DXGI_FORMAT_R32G32B32A32_UINT;td.SampleDesc.Count=1;td.BindFlags=D3D11_BIND_RENDER_TARGET;
    ComPtr<ID3D11Texture2D> t,read;check(d->CreateTexture2D(&td,nullptr,&t));
    td.BindFlags=0;td.Usage=D3D11_USAGE_STAGING;td.CPUAccessFlags=D3D11_CPU_ACCESS_READ;check(d->CreateTexture2D(&td,nullptr,&read));
    ComPtr<ID3D11RenderTargetView> rt;check(d->CreateRenderTargetView(t.Get(),nullptr,&rt));
    D3D11_BUFFER_DESC bd={};bd.ByteWidth=16;bd.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
    ComPtr<ID3D11Buffer> cb;check(d->CreateBuffer(&bd,nullptr,&cb));
    ID3D11RenderTargetView* rp=rt.Get();c->OMSetRenderTargets(1,&rp,nullptr);
    D3D11_VIEWPORT vp={0,0,129,17,0,1};c->RSSetViewports(1,&vp);
    c->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    c->VSSetShader(vs.Get(),nullptr,0);c->PSSetShader(ps.Get(),nullptr,0);
    ID3D11Buffer* cp=cb.Get();c->PSSetConstantBuffers(0,1,&cp);
    unsigned errors=0;
    for(unsigned mode=0;mode<4;mode++) {
        unsigned values[4]={mode,0,0,0};c->UpdateSubresource(cb.Get(),0,nullptr,values,0,0);c->Draw(3,0);
        c->CopyResource(read.Get(),t.Get());D3D11_MAPPED_SUBRESOURCE mapped={};check(c->Map(read.Get(),0,D3D11_MAP_READ,0,&mapped));
        unsigned selected=0,covered=0;
        for(unsigned y=0;y<17;y++)for(unsigned x=0;x<129;x++) {
            const unsigned* p=(const unsigned*)((const char*)mapped.pData+y*mapped.RowPitch)+4*x;
            const bool expected=mode==1 || (mode==2 && ((x+y)&1)) || (mode==3 && x==64 && y==8);
            if(p[0]!=(unsigned)expected || p[3]>=32 || bool(p[2]&(1u<<p[3]))!=expected || bool(p[1])!=bool(p[2])) ++errors;
            if(mode==0 && p[1]!=0)++errors;
            if(mode==1 && p[1]!=0xffffffffu)++errors;
            selected+=expected;covered+=p[1]!=0;
        }
        c->Unmap(read.Get(),0);printf("mode=%u selected=%u executing_pixels=%u\n",mode,selected,covered);
    }
    // Slot restoration: ordinary PS creation immediately after extension creation.
    ComPtr<ID3DBlob> plain;const char* code="float4 PS():SV_TARGET{return 1;}";
    check(D3DCompile(code,strlen(code),nullptr,nullptr,nullptr,"PS","ps_5_0",0,0,&plain,nullptr));
    ComPtr<ID3D11PixelShader> ordinary;check(d->CreatePixelShader(plain->GetBufferPointer(),plain->GetBufferSize(),nullptr,&ordinary));
    printf("vote_errors=%u normal_shader_after_reset=PASS\n",errors);return errors?1:0;
 } catch(const std::exception& e) { printf("FAIL: %s\n",e.what());return 1; }
}
