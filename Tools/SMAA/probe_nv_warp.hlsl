#define NV_SHADER_EXTN_SLOT u7
#include "../../External/NVAPI/nvHLSLExtns.h"
cbuffer Config : register(b0) { uint mode; };
float4 VS(uint id:SV_VertexID):SV_POSITION {
    return float4(id==2?3:-1,id==1?3:-1,0,1);
}
uint4 PS(float4 position:SV_POSITION):SV_TARGET {
    uint2 p=uint2(position.xy);
    bool selected=mode==1 || (mode==2 && ((p.x+p.y)&1)!=0) || (mode==3 && all(p==uint2(64,8)));
    return uint4(selected,NvAny(selected),NvBallot(selected),NvGetLaneId());
}
