// Which pixel-coordinate formula reproduces each fullscreen triangle's interpolated uv exactly?
#include <d3d11.h>
#include <d3dcompiler.h>
#include <cstdio>
#include <cstring>
#include <vector>
#include <cmath>
#pragma comment(lib,"d3d11.lib")
#pragma comment(lib,"d3dcompiler.lib")
static const char *src=R"(
void VS(float4 p:POSITION,float2 t:TEXCOORD0,out float4 s:SV_POSITION,out float2 o:TEXCOORD0){s=p;o=t;}
float4 PS(float4 s:SV_POSITION,float2 t:TEXCOORD0):SV_TARGET{return float4(t,s.xy);}
)";
int W=1920,H=1061;
std::vector<float> draw(ID3D11Device*d,ID3D11DeviceContext*c,const float v[3][6]){
  ID3DBlob*vb,*pb,*e;D3DCompile(src,strlen(src),0,0,0,"VS","vs_5_0",0,0,&vb,&e);D3DCompile(src,strlen(src),0,0,0,"PS","ps_5_0",0,0,&pb,&e);
  ID3D11VertexShader*vs;ID3D11PixelShader*ps;d->CreateVertexShader(vb->GetBufferPointer(),vb->GetBufferSize(),0,&vs);d->CreatePixelShader(pb->GetBufferPointer(),pb->GetBufferSize(),0,&ps);
  D3D11_INPUT_ELEMENT_DESC ie[2]={{"POSITION",0,DXGI_FORMAT_R32G32B32A32_FLOAT,0,0,D3D11_INPUT_PER_VERTEX_DATA,0},{"TEXCOORD",0,DXGI_FORMAT_R32G32_FLOAT,0,16,D3D11_INPUT_PER_VERTEX_DATA,0}};
  ID3D11InputLayout*il;d->CreateInputLayout(ie,2,vb->GetBufferPointer(),vb->GetBufferSize(),&il);
  D3D11_BUFFER_DESC bd{};bd.ByteWidth=sizeof(float)*18;bd.BindFlags=D3D11_BIND_VERTEX_BUFFER;bd.Usage=D3D11_USAGE_DEFAULT;D3D11_SUBRESOURCE_DATA sd{};sd.pSysMem=v;ID3D11Buffer*b;d->CreateBuffer(&bd,&sd,&b);
  D3D11_TEXTURE2D_DESC td{};td.Width=W;td.Height=H;td.MipLevels=1;td.ArraySize=1;td.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;td.SampleDesc.Count=1;td.BindFlags=D3D11_BIND_RENDER_TARGET;ID3D11Texture2D*t;d->CreateTexture2D(&td,0,&t);
  td.BindFlags=0;td.Usage=D3D11_USAGE_STAGING;td.CPUAccessFlags=D3D11_CPU_ACCESS_READ;ID3D11Texture2D*st;d->CreateTexture2D(&td,0,&st);
  ID3D11RenderTargetView*rtv;d->CreateRenderTargetView(t,0,&rtv);
  D3D11_RASTERIZER_DESC rd{};rd.FillMode=D3D11_FILL_SOLID;rd.CullMode=D3D11_CULL_NONE;rd.DepthClipEnable=FALSE;ID3D11RasterizerState*rs;d->CreateRasterizerState(&rd,&rs);
  D3D11_VIEWPORT vp{0,0,(float)W,(float)H,0,1};c->RSSetViewports(1,&vp);c->RSSetState(rs);UINT st2=24,of=0;c->IASetVertexBuffers(0,1,&b,&st2,&of);c->IASetInputLayout(il);c->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
  c->VSSetShader(vs,0,0);c->PSSetShader(ps,0,0);c->OMSetRenderTargets(1,&rtv,0);c->Draw(3,0);c->OMSetRenderTargets(0,0,0);c->CopyResource(st,t);
  D3D11_MAPPED_SUBRESOURCE m;c->Map(st,0,D3D11_MAP_READ,0,&m);std::vector<float> o(W*H*4);for(int y=0;y<H;++y)memcpy(&o[y*W*4],(char*)m.pData+y*m.RowPitch,W*16);c->Unmap(st,0);return o;
}
int main(){
  ID3D11Device*d;ID3D11DeviceContext*c;D3D_FEATURE_LEVEL fl=D3D_FEATURE_LEVEL_11_0;if(FAILED(D3D11CreateDevice(0,D3D_DRIVER_TYPE_HARDWARE,0,0,&fl,1,D3D11_SDK_VERSION,&d,0,&c)))return 1;
  const float F[3][6]={{-1,1,0,1,0,0},{3,1,0,1,2,0},{-1,-3,0,1,0,2}};
  const float S[3][6]={{-1,-1,1,1,0,1},{-1,3,1,1,0,-1},{3,-1,1,1,2,1}};
  auto a=draw(d,c,F),b=draw(d,c,S);
  std::vector<float> vf(H),vs(H);for(int y=0;y<H;++y){vf[y]=a[(y*W)*4+1];vs[y]=b[(y*W)*4+1];}
  bool perRow=true;for(int y=0;y<H;++y)for(int x=0;x<W;++x)if(a[(y*W+x)*4+1]!=vf[y]||b[(y*W+x)*4+1]!=vs[y])perRow=false;
  printf("v is a pure function of row: %d\n",perRow);
  FILE*f=fopen("rows.bin","wb");fwrite(vf.data(),4,H,f);fwrite(vs.data(),4,H,f);fclose(f);
}
