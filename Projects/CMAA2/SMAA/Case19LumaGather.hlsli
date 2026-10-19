#ifndef CASE19_LUMA_GATHER_HLSLI
#define CASE19_LUMA_GATHER_HLSLI
// A quarter-texel shift places the footprint safely between the current,
// left and top texel centers. D3D gather order: lower-left, lower-right,
// upper-right, upper-left. No interpolation of the returned values occurs.
// Shared with the hardware fixture; clamp addressing is supplied by the caller.
float3 Case19GatherLumaCurrentLeftTop(Texture2D tex, SamplerState samplerState,
                                    float2 uv, float2 pixelSize) {
    float4 g=tex.Gather(samplerState, uv-0.25*pixelSize);
    return g.yxz;
}
#endif
