// Shared by production diagnostics and the isolated raster correctness probe.
// Contract: origin-zero viewport, same-size edge texture, in-bounds pixel center.
float2 SMAAReadFirstEdgeLoad(float4 position) {
    return edgesTex.Load(int3(int2(position.xy),0)).rg;
}
float2 SMAAReadFirstEdgePoint(float2 uv) {
    return edgesTex.SampleLevel(PointSampler,uv,0).rg;
}
