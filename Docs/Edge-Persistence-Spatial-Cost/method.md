# 이전 raw edge 유지: 공간 패스 비용 분리

- Branch: `experiment/edge-persistence-spatial-cost`.
- Direct base: corrected case 6, `304f749`. Explicit dependencies only: `a8eca21`, `9b9953e`, `24c26fb` (case 7/8 renderer, audit controls and verified results). Professor report/capture additions excluded.
- A = case 6 current edge. E = case 8 first-pass union stencil. O = native case 4.
- Preserve E's current OR camera-reprojected previous RAW edge, raw RG, spatial frame history, point history sampling, weights, pattern Off and output. No dilation or quality-algorithm change.
- First add optional SP_Prepare / SP_Edge / SP_Weights / SP_Neighborhood GPU scopes. Final performance runs turn these diagnostic scopes off. Profile and clean timing must not be mixed.
- Same-execution paired measurements: 300 warm-up + 4,800 frames x 3 alternating repeats for clean performance; final diagnostic per-pass profiles use 960 x 3. Hidden, 1920x1061, Ultra, RTX 3060 Ti. Captures/readbacks/invocation diagnostics separate from timing. Fresh process per command.
- Initial candidate design: distinguish current-edge spatial work from union temporal work with separate stencil bits, using shader stencil reference only if supported. The device check rejected that route; the concrete U/G depth-mask alternative below replaces it. Preserve old E as an explicit control.
- Accept only after raw RG, current spatial, actual temporal coverage and final RGB match E; native A/O hash bridge also required. Inspect six consecutive moving/transition/still frames. Output equality does not solve existing thin-line defects.

## Primary sources and limits

1. [Original SMAA source](https://github.com/iryoku/smaa/blob/master/Demo/DX10/Shaders/SMAA.fx) and [SMAA paper](https://www.iryoku.com/smaa/downloads/SMAA-Enhanced-Subpixel-Morphological-Antialiasing.pdf): spatial three-pass organization; edge/stencil-driven weight calculation. No claim these implement our previous-edge union.
2. [Unity HDRP SMAA](https://github.com/Unity-Technologies/Graphics/blob/master/Packages/com.unity.render-pipelines.high-definition/Runtime/PostProcessing/Shaders/SubpixelMorphologicalAntialiasing.shader) and [stencil bits](https://github.com/Unity-Technologies/Graphics/blob/master/Packages/com.unity.render-pipelines.high-definition/Runtime/RenderPipeline/HDStencilUsage.cs): dedicated mask bits and masked comparison for SMAA. Supports separating meanings; does not establish our speed.
3. [Microsoft shader-specified stencil reference](https://learn.microsoft.com/en-us/windows/win32/direct3d11/shader-specified-stencil-reference-value): optional D3D11.3 capability `PSSpecifiedStencilRefSupported`; shader output replaces reference for test and REPLACE. Check support; never silently substitute another selection policy.
4. [Microsoft depth/stencil descriptor](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_depth_stencil_desc): read/write masks define independent stencil bits.
5. [NVIDIA shader performance guidance](https://developer.nvidia.com/blog/advanced-api-performance-shaders/): hardware stencil/depth rejection preferred to manual testing; branching and memory latency trade-offs require profiling. No hardware-counter diagnosis inferred from timestamps.
6. [Yang, Liu, Salvi 2020 TAA survey](https://research.nvidia.com/labs/rtr/publication/yang2020survey/): distinguishes accumulation and history validation. Edge persistence is a selection heuristic, not proof of valid history/disocclusion or sufficient subpixel reconstruction. This task changes execution only.

Accessed 2026-10-01. These are design references, not measured performance evidence for this GPU.

## Capability and concrete alternatives

The actual demo device reports `PSSpecifiedStencilRefSupported=0` (capture CSV), so the proposed two-bit shader-reference implementation is not used. Optional API support must not be assumed from GPU marketing generation.

- F: unconditional previous-raw-edge/point-velocity fetch before current-edge evaluation; same coordinates, bounds, raw union and stencil. NVIDIA's control-flow guidance motivates testing whether independent loads outweigh the extra reads. It is not assumed faster.
- U: first-pass shader exports current-edge 1/non-current 0 as depth, while retaining union stencil; weight pass still uses union stencil.
- G: exact same first-pass export as U, but weight pass requires depth=1 as well. This removes previous-only weight invocations with no extra pass. The third pass remains original. The U/G pair isolates hardware weight rejection; E/U exposes the added depth-export cost. Given the old case-7 result, export is a risk and this is a controlled alternative, not a presumed fix.
- Optional capture-only occlusion and pipeline statistics bracket pass 2. G samples must equal current raw mask count; E/F/U samples must equal union count. Temporal coverage and final RGB must be identical for E/F/U/G.

The initial three-mode Bistro profile is preserved separately. It shows pass 1 as the principal increase; pass 2 is a smaller contributor. A capability probe created a default D3D11 device during this run's initial 30-second precondition, before measured frames; all later runs use no concurrent device probes.

The technique pointer array had three elements for four input modes. Its size is corrected to four to remove an out-of-bounds constructor write; LumaRaw/current benchmark controls are verified against preserved hashes. No edge equation changes accompany this bounds correction.

The first full Bistro capture (20261001_123345) completed its GPU harness but G/frame_00129.png failed PNG decoding. All 1,440 primary images plus auxiliary PNGs were scanned; only this file failed. That entire capture is excluded from formal output validation and preserved unchanged. A fresh full six-mode capture (20261001_124127) passed; no missing image was replaced from another run.

Capture and final timing executables differ only in the diagnostic profile length (4,800 to 960) and its descriptive text. Renderer source hashes are identical; `capture-to-timing-source-bridge.json` records the exact bridge. Clean benchmarks remain 4,800 frames per repeat. Shader hashes are checked before and after every independent run.

F intentionally removes a current-edge-dependent texture-fetch branch. It does not add full-screen temporal color blending: the temporal draw still uses the same union stencil as E. Previous raw edges are retained with the existing ping-pong targets; this experiment does not add a CopyResource, draw, or dispatch. Extra raw-edge/velocity reads and better scheduling are competing costs, so compiled control flow and paired GPU timing must be examined together.
