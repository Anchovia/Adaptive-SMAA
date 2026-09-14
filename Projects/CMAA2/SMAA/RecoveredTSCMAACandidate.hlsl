// Shared recovered-source equations; attribution: RecoveredTSCMAAUtility.hlsl.
#ifndef RECOVERED_TSCMAA_CANDIDATE_INCLUDED
#define RECOVERED_TSCMAA_CANDIDATE_INCLUDED
typedef min16float lpfloat;
typedef min16float2 lpfloat2;
typedef min16float3 lpfloat3;
typedef min16float4 lpfloat4;
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
#endif
