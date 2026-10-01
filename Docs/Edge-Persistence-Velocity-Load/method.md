# ⑨의 velocity 읽기 단독 비교

Branch: `experiment/edge-persistence-velocity-load`. Direct base: corrected ⑥ `304f749`.
Required dependency: case-9 renderer `e54f0db` (renderer revision `922ee46`). Only its six SMAA renderer files, three noninteractive shader-error guard files and application hookup were imported. Old persistence benchmark harnesses, professor report, media and unrelated experiment documents were not imported. The new harness derives its deterministic timeline and statistics from the validated case-9 harness.

- A: corrected ⑥ current edge, Pattern Off.
- F: unchanged ⑨ eager previous-raw-edge lookup using point `SampleLevel` for velocity, Pattern Off.
- L: F with only velocity access changed to `Load(int2(SV_Position.xy), mip 0)`.
- O: corrected ④ original SMAA T2X-R, paired Pattern On.

L must retain the original interpolated UV in `previousUV = uv - velocity`, the old-edge integer coordinate/floor, bounds rule, exact current raw edge, union, native spatial and temporal math, history lifecycle and camera/depth reprojection. No new runtime pass, buffer format, dilation, jitter, clipping or weight change. Object motion is outside this experiment.

The existing edge-pass viewport is zero-origin at full texture resolution. Microsoft documents pixel `SV_Position` as screen coordinates offset by 0.5, and `Load` as an integer texel read without sampling/filtering. These support a same-current-texel hypothesis, not a speed guarantee:

- https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-load
- https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel
- https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-semantics
- https://developer.nvidia.com/blog/advanced-api-performance-shaders/

Accessed 2026-10-01. NVIDIA recommends measuring control-flow, register and texture-access tradeoffs. Point sampling already has a fast path in some cases; Load is not assumed faster.

## Validation before conclusions

- Release x64, all four edge-input shader variants compile; native and F control bytecode must match the preserved source.
- A/F/O RGB bridge against the preserved 240-frame-per-scene captures.
- L/F final RGB equality on all 240 frames in Bistro and Minecraft. At 43 diagnostic frames per mode: raw RG, current spatial DDS, actual temporal coverage and nonselected=current preserved; pass-2 samples equal union.
- A separate capture-only full-screen probe uses the actual edge vertex shader, geometry and UVs. For every current pixel, compare `asuint` velocity values from point sampling and Load, and compare `floor(uv*resolution)` with the integer screen coordinate. Both mismatch counts must be zero. The probe draw, temporary target, staging copy/map and queries are completely disabled during timing.
- Inspect original lossless moving, transition and still consecutive frames. Same output is not a repair of existing thin-line failures; do not rerun/relabel CGVQM as new quality improvement.
- Fresh clean process per command, zero CMAA2 processes pre/post, bounded timeout. Hidden, RTX 3060 Ti, DX11, Ultra, 1920×1061, VSync Off. Clean performance: 300 warm-up + 4,800 frames × 3 alternating repeats, capture/readback/probe/per-pass scopes Off. Optional per-pass diagnostic profile: 960 × 3, separate from clean timings.
- Preserve negative results. Do not renumber L as ⑩ or replace ⑨ without an explicit later decision.
