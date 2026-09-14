// Tiny windowless D3D11 diagnostic, no demo, no remote executable.
#include <d3d11.h>
#include <dxgi.h>
#include <wrl/client.h>
#include <fstream>
#include <vector>
#include <cstdio>
#include <cmath>
#include <stdexcept>
using Microsoft::WRL::ComPtr;
static void ck(HRESULT h){if(FAILED(h))throw std::runtime_error("D3D operation failed");}
struct Pixel {float r,g,b,a;};
int wmain(int argc,wchar_t**argv){try{
 if(argc!=3)throw std::runtime_error("Expected compiled shader and binary output paths");
 std::ifstream f(argv[1],std::ios::binary); std::vector<char> code((std::istreambuf_iterator<char>(f)),{});
 if(code.empty())throw std::runtime_error("Missing shader");
 ComPtr<ID3D11Device>d;ComPtr<ID3D11DeviceContext>c;D3D_FEATURE_LEVEL fl;
 ck(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&d,&fl,&c));
 if(fl<D3D_FEATURE_LEVEL_11_0)throw std::runtime_error("FL11 required");
 ComPtr<IDXGIDevice> gd;ck(d.As(&gd));ComPtr<IDXGIAdapter> ad;ck(gd->GetAdapter(&ad));DXGI_ADAPTER_DESC desc{};ck(ad->GetDesc(&desc));
 std::printf("Adapter VendorId=%u DeviceId=%u\n",desc.VendorId,desc.DeviceId);
 ComPtr<ID3D11ComputeShader>cs;ck(d->CreateComputeShader(code.data(),code.size(),nullptr,&cs));
 D3D11_SAMPLER_DESC sd{};sd.Filter=D3D11_FILTER_MIN_MAG_MIP_LINEAR;sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_BORDER;sd.MaxLOD=D3D11_FLOAT32_MAX;
 ComPtr<ID3D11SamplerState>sampler;ck(d->CreateSamplerState(&sd,&sampler));
 const UINT count=35*29*4;
 D3D11_BUFFER_DESC bd{};bd.ByteWidth=count*sizeof(Pixel);bd.Usage=D3D11_USAGE_DEFAULT;bd.BindFlags=D3D11_BIND_UNORDERED_ACCESS;bd.MiscFlags=D3D11_RESOURCE_MISC_BUFFER_STRUCTURED;bd.StructureByteStride=sizeof(Pixel);
 ComPtr<ID3D11Buffer>out,read;ck(d->CreateBuffer(&bd,nullptr,&out));ComPtr<ID3D11UnorderedAccessView>uav;ck(d->CreateUnorderedAccessView(out.Get(),nullptr,&uav));
 bd.Usage=D3D11_USAGE_STAGING;bd.BindFlags=0;bd.MiscFlags=0;bd.StructureByteStride=0;bd.CPUAccessFlags=D3D11_CPU_ACCESS_READ;ck(d->CreateBuffer(&bd,nullptr,&read));
 std::ofstream result(argv[2],std::ios::binary);if(!result)throw std::runtime_error("Output unavailable");
 for(int fixture=0;fixture<8;++fixture){
  std::vector<Pixel>p(35*29),mirror(35*29);
  for(int y=0;y<29;++y)for(int x=0;x<35;++x){
   Pixel v{0,0,0,1};if(fixture==1)v={.5f,.5f,.5f,1};if(fixture==2)v={1,0,0,1};if(fixture==3)v={0,0,1,1};
   if(fixture==4)v={float((x*7+y*3)%17)/16,float((x*5+y*11)%17)/16,float((x*13+y)%17)/16,1};
   if(fixture==5)v={float((x+y)%2),float(x%2),float(y%2),1};
   if(fixture==6)v={float((x*17+y*11)%256)/255,float((x*43+y*19)%256)/255,float((x*31+y*53)%256)/255,1};
   if(fixture==7)v={float(x%7)*.01f,float(y%5)*.03f,float(x%5)*.01f,1};
   p[y*35+x]=v;mirror[y*35+34-x]=v;
  }
  ComPtr<ID3D11Texture2D>tex[2];ComPtr<ID3D11ShaderResourceView>srv[2];
  D3D11_TEXTURE2D_DESC td{};td.Width=35;td.Height=29;td.MipLevels=td.ArraySize=1;td.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;td.SampleDesc.Count=1;td.Usage=D3D11_USAGE_IMMUTABLE;td.BindFlags=D3D11_BIND_SHADER_RESOURCE;
  for(int i=0;i<2;++i){D3D11_SUBRESOURCE_DATA data{};data.pSysMem=i?mirror.data():p.data();data.SysMemPitch=35*sizeof(Pixel);ck(d->CreateTexture2D(&td,&data,&tex[i]));ck(d->CreateShaderResourceView(tex[i].Get(),nullptr,&srv[i]));}
  ID3D11ShaderResourceView* views[]={srv[0].Get(),srv[1].Get()};ID3D11UnorderedAccessView* o=uav.Get();ID3D11SamplerState*s=sampler.Get();
  c->CSSetShader(cs.Get(),nullptr,0);c->CSSetShaderResources(10,2,views);c->CSSetShaderResources(17,1,views);c->CSSetSamplers(0,1,&s);c->CSSetUnorderedAccessViews(0,1,&o,nullptr);float constants[76]{};constants[48]=35;constants[49]=29;constants[53]=.5f;constants[56]=1.0f/22.0f;
  D3D11_BUFFER_DESC cb{};cb.ByteWidth=sizeof(constants);cb.Usage=D3D11_USAGE_IMMUTABLE;cb.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
  D3D11_SUBRESOURCE_DATA cbd{};cbd.pSysMem=constants;ComPtr<ID3D11Buffer> constantBuffer;ck(d->CreateBuffer(&cb,&cbd,&constantBuffer));ID3D11Buffer*cp=constantBuffer.Get();c->CSSetConstantBuffers(1,1,&cp);
  c->Dispatch(35,29,1);
  c->CopyResource(read.Get(),out.Get());D3D11_MAPPED_SUBRESOURCE mapped{};ck(c->Map(read.Get(),0,D3D11_MAP_READ,0,&mapped));
  result.write((const char*)mapped.pData,count*sizeof(Pixel));c->Unmap(read.Get(),0);c->ClearState();
 }
 c->Flush();std::printf("Completed 8 fixtures x 35x29 pixels x 4 production function outputs\n");return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"FAIL: %s\n",e.what());return 1;}}
