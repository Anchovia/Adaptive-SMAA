# One-frame raw-edge persistence GPU experiment

- Branch: `experiment/spatial-edge-persistence-depth`.
- Direct verified base: `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459` (corrected case 6).
- Target: `ABL-Spatial-PreviousRawEdge-Depth-PatternOff-R`.
- Controls: original case 6 `ABL-Spatial-FirstEdge-Stencil-PatternOff-R`,
  corrected native case 4 `O-T2X-R`, and capture-only current-edge depth handoff.
- This is a single hypothesis, not the final Adaptive eight-case matrix.

## Explicit dependencies

The noninteractive shader compile failure guard and diagnostic raw/current/previous/
velocity readback methods are reused from `9fefa77` (thin-line trace). No AA shader
from that investigation changes native temporal arithmetic. The binary readers and
CPU native reconstruction helper are reused from `63fbd59`, whose provenance is
`756ff54`. The previous offline hypothesis is not presented as GPU evidence.
The capture/benchmark harness derives from the baseline's stencil-lifecycle harness.

## Algorithm and execution

Keep original spatial SMAA, camera/depth motion, point history sampling, native
velocity-alpha history weight in [0,0.5], and previous **spatial frame** history.
Both selective cases have paired projection-jitter/subsample pattern Off. Native
case 4 retains paired pattern On, so its difference is not coverage alone.

`selected = currentRawEdge OR previousRawEdge(floor((uv-currentPointVelocity)*size))`.
Previous coordinates must be inside the image. Read only the immediately preceding
raw first-pass RG8 edge texture. Never save the union as the next raw edge, dilate,
alter the edge threshold, or change history filtering/clipping/weight.

Two raw edge render targets alternate before pass 1. This adds one RG8 allocation,
not a texture copy pass. The existing pass 3 writes its original spatial RGBA to
the same two color targets and writes selected=1/nonselected=0 through SV_Depth
into SMAA's dedicated D24S8 resource. Scene depth is not modified. The existing
fullscreen triangle has depth 1; EQUAL depth, depth writes Off, stencil Off and
`earlydepthstencil` reject nonselected samples before native temporal PS execution.
Quad/helper execution can exceed selected pixel count and is recorded separately.

The temporal shader itself remains `FirstEdgeStencilPS` / capture-only coverage
variant with native `DX10_SMAAResolvePS` arithmetic. No new draw/dispatch is added.
The extra current-edge read, previous-edge read, point velocity read, mask arithmetic
and depth write occur in pass 3; their cost is included in SF_Spatial and total AA.
This must not be described as zero-overhead data reuse.

Reset invalidates previous-edge use together with color history. The seed frame
uses the current-only depth shader without reading previous raw edge. Resource
recreation also destroys both raw edge textures. Allocation format comes from the
typed RTV, not the typeless resource format.

`SetEdgePersistenceMode(0/1/2)` is a harness setting: baseline / raw union /
current-only depth control. Nonzero modes require spatial SMAA + exact selective
temporal + camera reprojection; this experiment does not expose them as generic UI
combinations or change defaults.

## API basis

- [Microsoft: earlydepthstencil](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/sm5-attributes-earlydepthstencil)
- [Microsoft: depth/stencil configuration](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-depth-stencil)
- [Microsoft: Texture Load and out-of-bounds zero](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load)

The previous capability probe found shader-specified stencil reference unsupported
on this RTX 3060 Ti D3D11 device. This experiment uses the supported SV_Depth path.

## Validation and measurements

Release x64, D3D11, Ultra, fixed60Hz, 1920x1061, VSync Off, hidden window,
Bistro and Minecraft, identical still60/move120/still60 camera timeline.
Every command runs in a fresh clean process; shader failure is noninteractive;
wall-clock timeout is 1200 seconds and only the launched process is terminated.
Saved initial scene is prepared as in the corrected baseline runner.

- FXC compilation before launch and six-frame seed/static Test.
- Capture 240 frames of baseline 6, target, native 4, current-only depth control,
  and target repeat with diagnostics disabled in the repeat.
- Compare all control RGB hashes to the verified baseline; compare current-only
  depth output to baseline 6 and target repeat to target for all 240 frames.
- At 43 diagnostic frames per selective mode save raw input, spatial RGBA, previous
  spatial RGBA, current velocity, raw RG edges, and actual temporal coverage.
- Current spatial/velocity/raw/edge inputs must match between selective modes.
  Current selected output must stay identical; outside union must equal spatial.
- Occlusion samples must equal coverage pixels. PS invocation counts must show
  selective execution, with quad/helper overhead distinguished from output count.
- CPU union and native blend mirror use same saved inputs. UV fractions within
  0.01 texel of a point boundary are reported separately; stable interiors require
  exact mask and <=1 RGB quantization-level color error.
- Performance: 30s precondition, 300 warmup, 4800 frames x 6 alternating repeats,
  three modes within one process per scene. PNG/readback/query disabled. Record
  whole frame, total AA, spatial+selection, camera velocity, temporal resolve,
  wall interval and per-run median/p95/p99/stddev/1% equivalent FPS.
- Quality: aligned supersample spatial proxy, RGB MAE/PSNR, ROI edge strength,
  frame change and reference-delta residual. These are not absolute ghosting truth.
- Open full original PNGs, nearest enlarged six-frame motion and transition sheets,
  and late-still sheets. Export labeled GPU GIFs alongside lossless source sheets.

Full lifecycle resize/teleport and moving-object disocclusion are not automatically
covered by this fixed camera-scene gate; do not claim they have been validated.
