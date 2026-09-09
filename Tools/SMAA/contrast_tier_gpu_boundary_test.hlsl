// Run the C++ harness with the working directory Projects/CMAA2/SMAA so
// D3D_COMPILE_STANDARD_FILE_INCLUDE also resolves SMAA.hlsl.
#define SMAA_PRESET_ULTRA 1
#define SMAA_INTEGRATED_TEMPORAL_CANDIDATES 1
#include "../../Projects/CMAA2/SMAA/SMAAWrapper.hlsl"
StructuredBuffer<float> boundaryInput : register(t0);
RWStructuredBuffer<uint> boundaryOutput : register(u0);
[numthreads(1,1,1)]
void ContrastBoundaryCS(uint3 id : SV_DispatchThreadID) {
    bool selected = TSCMAAIntegratedSelectCandidate(uint2(0,0), 0,0,0,0,0, boundaryInput[id.x]);
    boundaryOutput[id.x * 2] = selected ? 1 : 0;
    bool baseEdge = false;
    boundaryOutput[id.x * 2 + 1] = (baseEdge && selected) ? 1 : 0;
}
