# ⑲ 자료 검토 목록: 114개

관련 기술 본문·소스 구간을 검토한 자료 목록이다. 전체 논문 정독 개수가 아니다. 실패·중복·본문 부족 자료는 개수에서 제외했다.

1. [ClearRenderTargetView](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-clearrendertargetview) — Whole-view clear; removing a clear requires complete defined writes, not sparse edge output.

2. [ClearDepthStencilView](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-cleardepthstencilview) — Stencil-only and depth clear are separate flags; retain current-frame stencil lifecycle.

3. [OMSetRenderTargets](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-omsetrendertargets) — MRT slots and subresource read/write hazards constrain fusion; keep separate spatial SRV.

4. [PSSetShaderResources](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-pssetshaderresources) — Conflicting output bindings can null an SRV; explicit resource transitions remain necessary.

5. [D3D11_BIND_FLAG](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_bind_flag) — Resource roles affect driver optimizations; no unused UAV flags in existing history.

6. [D3D11_TEXTURE2D_DESC](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_texture2d_desc) — Resource format and bind flags must be captured for reproducible format experiments.

7. [D3D11_USAGE](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_usage) — Keep production textures DEFAULT; staging/readback stays outside timing.

8. [DXGI_FORMAT](https://learn.microsoft.com/en-us/windows/win32/api/dxgiformat/ne-dxgiformat-dxgi_format) — RG8 and RGBA8 retain eight bits per RG channel; binary edge format candidate.

9. [CheckFormatSupport](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11device-checkformatsupport) — Check render-target and shader sample support before alternate edge formats.

10. [D3D11_FORMAT_SUPPORT](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_format_support) — Texture filtering and output support are independent capability bits.

11. [Depth-stencil pipeline](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-depth-stencil) — Stencil selection must survive any depth-state optimization.

12. [D3D11_DEPTH_STENCIL_DESC](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_depth_stencil_desc) — Read/write masks and stencil pass operations control exact mask lifetime.

13. [D3D11_RENDER_TARGET_BLEND_DESC](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_render_target_blend_desc) — Full channel write masks can differ in compression cost; output alpha semantics constrain them.

14. [D3D11_SAMPLER_DESC](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_sampler_desc) — Point/linear/clamp filtering cannot be changed casually in exact-output experiments.

15. [DiscardView](https://learn.microsoft.com/en-us/windows/win32/api/d3d11_1/nf-d3d11_1-id3d11devicecontext1-discardview) — Discard makes contents undefined; cannot replace required zero-clears of sparse targets.

16. [CopyResource](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-copyresource) — Copy is GPU asynchronous and requires compatible resources; 18 final display copy remains.

17. [D3D11 query types](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_query) — TIMESTAMP/DISJOINT distinguish valid GPU duration from frequency changes.

18. [TIMESTAMP_DISJOINT data](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_query_data_timestamp_disjoint) — Reject disjoint timestamps; use frequency only for valid measurements.

19. [PIPELINE_STATISTICS data](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_query_data_pipeline_statistics) — PS invocation counts can diagnose stencil efficiency but queries must remain off in formal timing.

20. [GetData](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-getdata) — Polling can submit or stall work; diagnostic readback separated.

21. [D3D11_ASYNC_GETDATA_FLAG](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_async_getdata_flag) — DONOTFLUSH avoids implicit submission while polling diagnostic queries.

22. [Map](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-map) — CPU resource mapping is a potential synchronization point; keep out of benchmark.

23. [NVIDIA shaders](https://developer.nvidia.com/blog/advanced-api-performance-shaders/) — Registers and shader specialization matter; never accept arithmetic reordering without output proof.

24. [NVIDIA pipeline state](https://developer.nvidia.com/blog/advanced-api-performance-pipeline-state-objects/) — PSO advice is DX12-specific; do not claim CPU state savings as measured GPU savings.

25. [NVIDIA barriers](https://developer.nvidia.com/blog/advanced-api-performance-barriers/) — Dependency ordering matters, but explicit DX12 barriers cannot be transplanted to DX11.

26. [NVIDIA peak-performance analysis](https://developer.nvidia.com/blog/the-peak-performance-analysis-method-for-optimizing-any-gpu-workload/) — Identify a saturated unit; timestamp differences alone do not establish bandwidth saturation.

27. [NVIDIA thread-group swizzling](https://developer.nvidia.com/blog/optimizing-compute-shaders-for-l2-locality-using-thread-group-id-swizzling/) — Tile locality could help a compute redesign, but current pixel path has no threadgroup dispatch.

28. [AMD occupancy explained](https://gpuopen.com/learn/occupancy-explained/) — Higher occupancy can hurt cache behavior; do not assume more waves is always faster.

29. [AMD large thread groups](https://gpuopen.com/learn/optimizing-gpu-occupancy-resource-usage-large-thread-groups/) — Group size trades occupancy against resource use; compute rewrite needs separate validation.

30. [AMD context rolls](https://gpuopen.com/learn/understanding-gpu-context-rolls/) — State changes can have hardware costs; vendor-specific concept, not a measured RTX diagnosis.

31. [MJP early-Z](https://therealmjp.github.io/posts/to-earlyz-or-not-to-earlyz/) — Discard and stencil writes constrain early testing; preserve exact selection semantics.

32. [SMAA paper](https://www.iryoku.com/smaa/downloads/SMAA-Enhanced-Subpixel-Morphological-Antialiasing.pdf) — Preserve accurate area/search reconstruction; changing presets is a quality tradeoff, not output preservation.

33. [SMAA official C++](https://raw.githubusercontent.com/iryoku/smaa/master/Demo/DX10/Code/SMAA.cpp) — Official sample explicitly selects RGBA8 for NVIDIA; local wrapper passes no adapter, so edge format is RG8.

34. [Intel TSCMAA paper](https://www.intel.com/content/dam/develop/external/us/en/documents/tscmaa-codesample-v1.pdf) — Sparse candidate work can save resolve time while requiring candidate setup; no new weight/filter changes.

35. [Intel CMAA2 paper](https://www.intel.com/content/dam/develop/external/us/en/documents/conservative-morphological-anti-aliasing-2-0-v2.pdf) — Compute compaction and reconstruction design is not a drop-in exact SMAA optimization.

36. [MJP EarlyZTest implementation](https://github.com/TheRealMJP/EarlyZTest) — Controlled invocation-count experiments distinguish shader discard and early test cases.

37. [SMAA original shader](https://github.com/iryoku/smaa/blob/master/SMAA.hlsl) — Author integration comments discuss stencil, sampler choices and lookup textures.

38. [AMD RDNA guide](https://gpuopen.com/learn/rdna-performance-guide/) — Single-channel gather is a concrete luma fetch hypothesis; vendor result must be tested on RTX.

39. [NVIDIA Ampere tuning guide](https://docs.nvidia.com/cuda/ampere-tuning-guide/index.html) — Ampere cache and FP32/FP16 behavior; CUDA-specific scheduling guidance cannot justify a DX11 claim.

40. [HLSL flow control](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-flow-control) — Loop/branch selection can affect latency; preserve control output.

41. [HLSL Gather](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-gather) — Gather gets four red texels used for bilinear footprint; exact swizzle and border tests needed.

42. [HLSL earlydepthstencil](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/sm5-attributes-earlydepthstencil) — Already used in resolve; applying it to discard-driven stencil writer would change selection.

43. [HLSL precise variables](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-variable-syntax) — Precise constrains order/fusion, but adding it changes baseline arithmetic; not a free equality proof.

44. [HLSL Load](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load) — OOB Load returns zero rather than sampler clamp; keep edge-neighbor boundary behavior.

45. [HLSL Sample](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-sample) — Sampling applies normalized coordinates, offsets and format conversion.

46. [HLSL SampleLevel](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel) — Explicit LOD is needed with no mips and divergent control.

47. [HLSL discard](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-discard) — Discard suppresses pixel outputs and interacts with stencil writes.

48. [HLSL if](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-if) — Branch vs flatten controls execution scheduling; previous eager/deferred query results are preserved.

49. [HLSL for](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-for) — Loop/unroll attributes affect code expansion in SMAA searches.

50. [HLSL while](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-while) — Variable search length produces divergent loops; reducing preset would alter output.

51. [HLSL data types](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-data-types) — Precision and conversion rules rule out casual half-precision replacement.

52. [HLSL gather4 instruction](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/gather4--sm5---asm-) — Order is bilinear footprint, not filtered result; prove swizzle with GPU fixture.

53. [HLSL GatherRed](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/texture2d-gatherred) — Single red channel gather is available in shader model 5; restrict new entry profile accordingly.

54. [D3D floating-point rules](https://learn.microsoft.com/en-us/windows/win32/direct3d11/floating-point-rules) — UNORM conversion and arithmetic tolerances mean equation equality alone is insufficient.

55. [D3D11 functional specification](https://microsoft.github.io/DirectX-Specs/d3d/archive/D3D11_3_FunctionalSpec.htm) — Sampling quantization, border behavior, output-merger rules provide the normative constraints.

56. [D3DCompile flags](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/d3dcompile-constants) — All-resources-bound requires all referenced resources to be bound, violated by seed previous-edge null.

57. [Shader optimization guide](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-optimize) — Instruction scheduling and flow changes require measurement; preserve baseline shader compilation.

58. [Shader minimum precision](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/using-hlsl-minimum-precision) — min16 is not a portable exact-output optimization; do not change arithmetic precision.

59. [Morphological Antialiasing (Reshetov 2009)](https://www.intel.com/content/dam/develop/external/us/en/documents/z-shape-arm-785403.pdf) — Spatial edge classification is algorithmic work; keep pattern coverage, optimize data delivery.

60. [Practical indirect occlusion (Jimenez et al.)](https://www.activision.com/cdn/research/PracticalRealtimeStrategiesTRfinal.pdf) — Neighborhood data locality/gather is transferable as implementation idea; AO equations are out of scope.

61. [An excursion in temporal supersampling (Salvi)](https://developer.download.nvidia.com/gameworks/events/GDC2016/msalvi_temporal_supersampling.pdf) — History sampling/clipping belongs to temporal-quality design; no reason to change successful resolve here.

62. [A Directionally Adaptive Edge Anti-Aliasing Filter](https://www.iryoku.com/aacourse/downloads/02-A-Directionally-Adaptive-Edge-Anti-Aliasing-Filter.pdf) — MSAA plane fitting changes inputs and reconstruction; excluded from exact RGB scope.

63. [Morphological Anti-Aliasing](https://www.iryoku.com/aacourse/downloads/03-Morphological-Anti-Aliasing.pdf) — MLAA shape classification and neighborhood blending motivate locality, not candidate reduction.

64. [Jimenez’s MLAA & SMAA: Subpixel Morphological Anti-Aliasing](https://www.iryoku.com/aacourse/downloads/04-Jimenez%27s-MLAA-%26-SMAA-%28Subpixel-Morphological-Anti-Aliasing%29.pdf) — SMAA texture layouts, search acceleration and GPU stages underpin spatial cost audit.

65. [SRAA: Subpixel Reconstruction Anti-Aliasing](https://www.iryoku.com/aacourse/downloads/07-SRAA-Subpixel-Reconstruction-Anti-Aliasing.pdf) — SRAA needs geometric multisample buffers and a different reconstruction; excluded.

66. [FXAA 3.11 in 15 Slides](https://www.iryoku.com/aacourse/downloads/09-FXAA-3.11-in-15-Slides.pdf) — FXAA single-pass design is a different filter and output; cannot substitute for exact SMAA.

67. [Distance-to-edge AA](https://www.iryoku.com/aacourse/downloads/10-Distance-to-edge-AA-%28DEAA%29.pdf) — Distance-to-edge requires geometry integration and changes coverage; excluded.

68. [Geometry Buffer Anti-Aliasing](https://www.iryoku.com/aacourse/downloads/11-Geometry-Buffer-Anti-Aliasing-%28GBAA%29.pdf) — GBAA requires geometry buffer and different reconstruction; excluded.

69. [Unity SMAA runtime](https://raw.githubusercontent.com/Unity-Technologies/PostProcessing/v2/PostProcessing/Runtime/Effects/SubpixelMorphologicalAntialiasing.cs) — Temporary targets, color-space and stencil setup are explicit; reference rather than new semantics.

70. [Three.js SMAAPass](https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/jsm/postprocessing/SMAAPass.js) — Two intermediate targets and pass lifetimes clarify non-temporal buffer overhead.

71. [Three.js SMAAShader](https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/jsm/shaders/SMAAShader.js) — Luma sampling, accurate search and area reconstruction stay quality-critical.

72. [Godot SMAA integration](https://raw.githubusercontent.com/godotengine/godot/master/servers/rendering/renderer_rd/effects/smaa.cpp) — Modern integration provides resource-format and pass scheduling comparison.

73. [DiligentFX temporal implementation documentation](https://diligentgraphics.github.io/docs/db/d24/DiligentFX_PostProcess_TemporalAntiAliasing_README.html) — Retain reset/history consistency while optimizing spatial data access.

74. [Unity anti-aliasing documentation](https://github.com/Unity-Technologies/Graphics/blob/master/com.unity.postprocessing/Documentation~/Anti-aliasing.md) — Lower quality is explicitly a speed tradeoff, not acceptable as same-output optimization.

75. [NVIDIA GPU Gems pipeline performance](https://developer.nvidia.com/gpugems/gpugems/part-v-performance-and-practicalities/chapter-28-graphics-pipeline-performance) — Vary workload/format to isolate bottlenecks rather than infer them from code.

76. [NVIDIA GPU Gems deferred stencil locality](https://developer.nvidia.com/gpugems/gpugems3/part-iii-rendering/chapter-19-deferred-shading-tabula-rasa) — Stencil masking efficiency depends on locality; selected-pixel count alone does not predict speed.

77. [NVIDIA GPU Gems occlusion queries](https://developer.nvidia.com/gpugems/gpugems/part-v-performance-and-practicalities/chapter-29-efficient-occlusion-culling) — GPU/CPU query dependencies can cost more than saved work; no readback-driven per-frame policy.

78. [NVIDIA GPU Gems parallel prefix sum](https://developer.nvidia.com/gpugems/gpugems3/part-vi-gpu-computing/chapter-39-parallel-prefix-sum-scan-cuda) — Stream compaction has setup/synchronization cost; not free sparse execution.

79. [Intel Xe-LP optimization](https://www.intel.com/content/www/us/en/developer/articles/guide/lp-api-developer-optimization-guide.html) — Use minimum resources and careful sampling; Intel-specific advice is not RTX performance proof.

80. [Intel Gen11 optimization](https://www.intel.com/content/www/us/en/developer/articles/guide/developer-and-optimization-guide-for-intel-processor-graphics-gen11-api.html) — Reduce unnecessary channels but recognize vendor-specific format exceptions.

81. [MJP half precision](https://therealmjp.github.io/posts/shader-fp16/) — Conversion overhead and numerical changes make half precision a poor exact-output default.

82. [CreateTexture2D](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11device-createtexture2d) — Check creation errors and reject unsupported target format rather than silently fall back.

83. [CreateRenderTargetView](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11device-createrendertargetview) — RTV type must match resource format; both ping-pong edges must change together.

84. [CreateShaderResourceView](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11device-createshaderresourceview) — SRV view compatibility required for resource-format optimization.

85. [D3D11_SHADER_RESOURCE_VIEW_DESC](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_shader_resource_view_desc) — Preserve exact edge UNORM interpretation and mip range.

86. [D3D11_RENDER_TARGET_VIEW_DESC](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_render_target_view_desc) — Use RTV format to construct matching previous-raw ping-pong target.

87. [OMSetDepthStencilState](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-omsetdepthstencilstate) — Reference value and read/write masks must remain unchanged across candidates.

88. [RSSetViewports](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-rssetviewports) — Viewport defines pixel-center mapping; fixture must use same full-screen geometry as production.

89. [D3D11_RASTERIZER_DESC](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ns-d3d11-d3d11_rasterizer_desc) — Scissor/cull/sample changes cannot silently alter edge coverage.

90. [D3DCompileFromFile](https://learn.microsoft.com/en-us/windows/win32/api/d3dcompiler/nf-d3dcompiler-d3dcompilefromfile) — Compile production helper in isolated fixture with exact macros/targets.

91. [D3DDisassemble](https://learn.microsoft.com/en-us/windows/win32/api/d3dcompiler/nf-d3dcompiler-d3ddisassemble) — Compare generated texture instruction counts and reject unexpected baseline shader changes.

92. [D3D11 output-merger stage](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-output-merger-stage) — Output-merger format conversion/blend masks are part of result semantics.

93. [D3D11 rasterizer stage](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-rasterizer-stage) — Preserve full-screen interpolation and coverage when changing texture access.

94. [D3D11 shader resource introduction](https://learn.microsoft.com/en-us/windows/win32/direct3d11/overviews-direct3d-11-resources-intro) — Resources and views have separate roles and typed interpretations.

95. [D3D11 feature levels](https://learn.microsoft.com/en-us/windows/win32/direct3d11/overviews-direct3d-11-devices-downlevel-intro) — New Gather entry must use a supported shader profile; current production device uses FL11.

96. [HLSL semantics](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-semantics) — Pixel-center position and semantic interpolation are critical to gather placement.

97. [HLSL Texture2D GetDimensions](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-getdimensions) — Production resolution is compile-time macro; avoid redundant dimension queries.

98. [HLSL saturate](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-saturate) — Do not change clamp/saturate domain in the color blend.

99. [HLSL mad](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/mad) — Fused or unfused arithmetic may differ; exact RGB gate remains mandatory.

100. [HLSL ddx](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-ddx) — Implicit derivatives depend on quad execution; do not infer arbitrary divergent sampling equivalence.

101. [NVIDIA CUDA best practices](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html) — Use measured bandwidth/latency diagnosis; CUDA APIs and scheduling are not DX11 evidence.

102. [D3D11 Flush](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-flush) — Flush has overhead and does not guarantee GPU completion; do not insert per-pass synchronization.

103. [Intel PresentMon implementation](https://github.com/GameTechDev/PresentMon) — Presentation timing and application GPU scopes differ; do not turn AA savings into FPS claims.

104. [SciPy paired t-test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_rel.html) — Pair each candidate with same repeat control; confidence intervals need paired differences.

105. [NIST paired comparisons](https://www.itl.nist.gov/div898/handbook/eda/section3/eda353.htm) — Distinguish paired samples from cross-process absolute mean comparisons.

106. [NumPy array_equal](https://numpy.org/doc/stable/reference/generated/numpy.array_equal.html) — Pixel equality must include equal dimensions and exact decoded values.

107. [Pillow Image conversion](https://pillow.readthedocs.io/en/stable/reference/Image.html) — RGB conversion intentionally omits alpha; state separate RGB and RGBA equality scopes.

108. [NVIDIA shader intrinsics](https://developer.nvidia.com/blog/unlocking-gpu-intrinsics-in-hlsl/) — Vendor intrinsics/wave ops add portability constraints; not needed for first minimal candidates.

109. [D3D11 rasterization rules](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-rasterizer-stage-rules) — Full-screen triangle fixture must preserve pixel centers and edge coverage.

110. [GPU Program Optimization, correct chapter](https://developer.nvidia.com/gpugems/gpugems2/part-iv-general-purpose-computation-gpus-primer/chapter-35-gpu-program-optimization) — Move invariant work out of high-frequency pixel execution; verify arithmetic and instruction scheduling.

111. [Fullscreen triangle execution (Wallis)](https://wallisc.github.io/rendering/2021/04/18/Fullscreen-Pass.html) — Already uses a single fullscreen triangle; replacing a quad is not a new optimization here.

112. [Shader Specified Stencil Reference Value (D3D11)](https://learn.microsoft.com/en-us/windows/win32/direct3d11/shader-specified-stencil-reference-value) — Per-pixel stencil export could separate current and temporal masks, but is optional and needs a separate capability/lifecycle/performance gate.

113. [Practical DX12: Programming Model and Hardware Capabilities](https://gpuopen.com/download/Practical_DX12_Programming_Model_and_Hardware_Capabilities.pdf) — Stencil output has depth-output-like costs; do not assume dual mask export is a free AA optimization. DX12 guidance is not RTX/DX11 performance proof.

114. [HLSL operators](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-operators) — FXC HLSL Boolean expressions do not short-circuit; use actual control flow to avoid a history read.
