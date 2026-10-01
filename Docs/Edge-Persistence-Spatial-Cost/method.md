# 이전 raw edge 유지: 공간 패스 비용 분리

- Branch: `experiment/edge-persistence-spatial-cost`.
- Direct base: corrected case 6, `304f749`. Explicit dependencies only: `a8eca21`, `9b9953e`, `24c26fb` (case 7/8 renderer, audit controls and verified results). Professor report/capture additions excluded.
- A = case 6 current edge. E = case 8 first-pass union stencil. O = native case 4.
- Preserve E's current OR camera-reprojected previous RAW edge, raw RG, spatial frame history, point history sampling, weights, pattern Off and output. No dilation or quality-algorithm change.
- First add optional SP_Prepare / SP_Edge / SP_Weights / SP_Neighborhood GPU scopes. Final performance runs turn these diagnostic scopes off. Profile and clean timing must not be mixed.
- Same-execution paired measurements, 300 warm-up + 4,800 frames x 3 alternating repeats, hidden, 1920x1061, Ultra, RTX 3060 Ti. Captures/readbacks/invocation diagnostics separate from timing. Fresh process per command.
- Candidate design: distinguish current-edge spatial work from union temporal work with separate stencil bits, using hardware-supported shader stencil reference only if available. Preserve old E as explicit control. A same-export union-gated control isolates reduced pass-2 execution from the cost of exporting stencil.
- Accept only after raw RG, current spatial, actual temporal coverage and final RGB match E; native A/O hash bridge also required. Inspect six consecutive moving/transition/still frames. Output equality does not solve existing thin-line defects.

## Primary sources and limits

1. [Original SMAA source](https://github.com/iryoku/smaa/blob/master/Demo/DX10/Shaders/SMAA.fx) and [SMAA paper](https://www.iryoku.com/smaa/downloads/SMAA-Enhanced-Subpixel-Morphological-Antialiasing.pdf): spatial three-pass organization; edge/stencil-driven weight calculation. No claim these implement our previous-edge union.
2. [Unity HDRP SMAA](https://github.com/Unity-Technologies/Graphics/blob/master/Packages/com.unity.render-pipelines.high-definition/Runtime/PostProcessing/Shaders/SubpixelMorphologicalAntialiasing.shader) and [stencil bits](https://github.com/Unity-Technologies/Graphics/blob/master/Packages/com.unity.render-pipelines.high-definition/Runtime/RenderPipeline/HDStencilUsage.cs): dedicated mask bits and masked comparison for SMAA. Supports separating meanings; does not establish our speed.
3. [Microsoft shader-specified stencil reference](https://learn.microsoft.com/en-us/windows/win32/direct3d11/shader-specified-stencil-reference-value): optional D3D11.3 capability `PSSpecifiedStencilRefSupported`; shader output replaces reference for test and REPLACE. Check support; never silently substitute another selection policy.
4. [Microsoft depth/stencil descriptor](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_depth_stencil_desc): read/write masks define independent stencil bits.
5. [NVIDIA shader performance guidance](https://developer.nvidia.com/blog/advanced-api-performance-shaders/): hardware stencil/depth rejection preferred to manual testing; branching and memory latency trade-offs require profiling. No hardware-counter diagnosis inferred from timestamps.
6. [Yang, Liu, Salvi 2020 TAA survey](https://research.nvidia.com/labs/rtr/publication/yang2020survey/): distinguishes accumulation and history validation. Edge persistence is a selection heuristic, not proof of valid history/disocclusion or sufficient subpixel reconstruction. This task changes execution only.

Accessed 2026-10-01. These are design references, not measured performance evidence for this GPU.
