// Recovered-source SMAA adaptation. See Docs/SMAA-Recovered-TSCMAA-Comparison-Protocol-ko.md.
// Source formula attribution and license are in RecoveredTSCMAAUtility.hlsl.
#include "SMAAWrapper.hlsl"
typedef min16float lpfloat;
typedef min16float2 lpfloat2;
typedef min16float3 lpfloat3;
typedef min16float4 lpfloat4;
#define CMAA2_COLOR_PACK_FORMAT_R8G8B8_UNORM
#include "RecoveredTSCMAAUtility.hlsl"

Texture2D<float4> recoveredInput : register(t17);

lpfloat3 RecoveredLoad(int2 p, int2 size) {
    // Explicit black halo, matching Texture.Load's outside-resource zero value.
    if(any(p < 0) || any(p >= size)) return 0;
    return lpfloat3(recoveredInput.Load(int3(p,0)).rgb);
}
lpfloat RecoveredDifference(lpfloat3 a, lpfloat3 b) {
    const lpfloat3 weights = lpfloat3(0.299,0.587,0.114);
    lpfloat3 delta = abs(a*weights-b*weights);
    return max(max(delta.r,delta.g),delta.b);
}
lpfloat2 RecoveredEdge(int2 p, int2 size) {
    lpfloat3 c = RecoveredLoad(p,size);
    return saturate(lpfloat2(RecoveredDifference(c,RecoveredLoad(p+int2(1,0),size)),
        RecoveredDifference(c,RecoveredLoad(p+int2(0,1),size)))
        - lpfloat(g_SMAAReprojection.TSCMAACandidateParams.x));
}
lpfloat2 RecoveredResidual(int2 p, int2 size) {
    lpfloat2 e = RecoveredEdge(p,size);
    lpfloat horizontal = (RecoveredEdge(p+int2(0,-1),size).y + e.y
        + RecoveredEdge(p+int2(1,-1),size).y + RecoveredEdge(p+int2(1,0),size).y)*lpfloat(0.25);
    lpfloat vertical = (RecoveredEdge(p+int2(-1,0),size).x + e.x
        + RecoveredEdge(p+int2(-1,1),size).x + RecoveredEdge(p+int2(0,1),size).x)*lpfloat(0.25);
    return saturate(e-lpfloat(g_SMAAReprojection.TSCMAAParams.y)*lpfloat2(horizontal,vertical));
}
lpfloat4 RecoveredFourEdges(int2 p, int2 size) {
    return lpfloat4(RecoveredResidual(p,size),RecoveredResidual(p+int2(-1,0),size).x,
        RecoveredResidual(p+int2(0,-1),size).y);
}
[numthreads(8,8,1)]
void RecoveredExtractCS(uint3 id:SV_DispatchThreadID) {
    uint w,h; recoveredInput.GetDimensions(w,h);
    if(id.x>=w || id.y>=h) return;
    lpfloat4 ce = RecoveredFourEdges(int2(id.xy),int2(w,h));
    bool base = any(ce>0);
    bool selected = any(ce>lpfloat(g_SMAAReprojection.TSCMAACandidateParams.x)*lpfloat(0.5));
    if(g_SMAAReprojection.TSCMAACandidateParams.w>0.5) {
        base = selected = id.y*w+id.x < min(uint(g_SMAAReprojection.TSCMAACandidateParams.z+0.5),w*h);
    }
    tscmaaBaseEdgeMask[id.xy] = base?1:0;
    tscmaaCandidateMask[id.xy] = selected?1:0;
    uint index;
    if(base) tscmaaControl.InterlockedAdd(TSCMAA_EDGE_COUNTER_OFFSET,1,index);
    if(!selected) return;
    tscmaaControl.InterlockedAdd(TSCMAA_CANDIDATE_COUNTER_OFFSET,1,index);
    uint capacity,stride; tscmaaCandidates.GetDimensions(capacity,stride);
    if(index<capacity) tscmaaCandidates[index]=(id.x<<16)|id.y;
}

float4 RecoveredTemporalPixel(int2 p, int2 size) {
    float2 uv = (float2(p)+0.5)/float2(size);
    float4 current = tscmaaCurrentColor.Load(int3(p,0));
    float2 velocity = g_SMAAReprojection.TSCMAAParams.z>0.5?velocityTex.Load(int3(p,0)).xy:float2(0,0);
    if(!all(isfinite(velocity))) return current; // explicit numeric safety, not a UV bounds rejection
    float3 history = BicubicTextureSample(tscmaaHistoryColor,LinearSampler,uv-velocity,size.x,size.y);
    history = ClipColor(history,current.rgb,tscmaaCurrentColor,uv,LinearSampler,0.263157904,size.x,size.y);
    // Preserve source min-precision helper boundaries and its square/sqrt approximation.
    lpfloat3 h = lpfloat3(history), c = lpfloat3(current.rgb);
    lpfloat3 hh = h*h, cc = c*c;
    float3 linearColor = 0.789473712*float3(hh)+(1.0-0.789473712)*float3(cc);
    lpfloat3 result = sqrt(lpfloat3(linearColor));
    // Source PackColorFF rounds explicitly after a min16float cast. The renderer's typed
    // UNORM UAV gets already-quantized bytes, avoiding a second, different tie rounding.
    uint packed = PackColorFF(float4(result,current.a));
    return UnpackColorFF(packed);
}
[numthreads(TSCMAA_RESOLVE_NUM_THREADS,1,1)]
void RecoveredResolveCS(uint3 id:SV_DispatchThreadID) {
    uint count=tscmaaControl.Load(TSCMAA_PROCESS_COUNT_OFFSET);
    uint capacity,stride; tscmaaCandidates.GetDimensions(capacity,stride);
    if(id.x>=min(count,capacity)) return; // guard BEFORE list read; fixes recovered >count bug
    uint packed=tscmaaCandidates[id.x];
    int2 p=int2(packed>>16,packed&65535), size=int2(g_SMAAReprojection.TemporalResolution.xy);
    if(any(p>=size)) return;
    tscmaaOutput[p]=RecoveredTemporalPixel(p,size);
}
