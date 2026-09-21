Texture2D edgesTex : register(t8);
SamplerState PointSampler : register(s1);
#include "../../Projects/CMAA2/SMAA/TemporalEdgeAccess.hlsl"
struct VertexOut { float4 position:SV_POSITION; float2 uv:TEXCOORD0; };
VertexOut ProbeVS(uint vertex:SV_VertexID) {
    const float2 positions[3]={float2(-1,-1),float2(-1,3),float2(3,-1)};
    const float2 uvs[3]={float2(0,1),float2(0,-1),float2(2,1)};
    VertexOut o;o.position=float4(positions[vertex],1,1);o.uv=uvs[vertex];return o;
}
float4 ProbePS(VertexOut i):SV_TARGET {
    return float4(SMAAReadFirstEdgeLoad(i.position),SMAAReadFirstEdgePoint(i.uv));
}
