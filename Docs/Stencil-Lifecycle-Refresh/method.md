# Stencil lifecycle refresh — case 3

Branch `baseline/temporal-only-stencil-lifecycle` starts from `eb5117ce39177910bb9df6b741fc1719e2ec494a`. Target `ABL-TemporalOnly-R` only; corrected native
`O-T2X-R` is the within-process performance control (case 4 is the control itself).
Old branches and results remain unchanged. 1/3 receive the same spatial clear code
but do not execute spatial SMAA; unused stencil is never artificially cleared.
5/6 keep early-stencil selective temporal and pattern Off. Native 3/4 keep pattern On.
This six-control experiment is not the final Adaptive 8-case matrix or a TSCMAA port.

The dedicated stencil is cleared once before each spatial edge pass. Case 5's
existing raw exact-edge clear remains unchanged. Case 6 expands its existing clear
to the native spatial control too, without a second clear. No edge/weight/temporal
shader or history topology is changed. Shader hashes must match the branch base.

Release x64, DX11, Ultra, 1920x1061, fixed 60 Hz, Bistro/Minecraft. Camera profile:
t=2+clamp(frame%240-60,0,120)/60, still60/move120/still60. Reset history at loop wrap,
recreate resources at each mode; no camera/object-motion policy changes.
Capture target/control and repeat; verify all RGB pixels against preserved captures.
CGVQM scores may be reused only after exact 240-frame RGB bridge; no new quality
improvement is inferred. Missing old images or mismatch blocks performance adoption.

Capture and GPU timing are separate clean processes. Performance: 30s precondition,
300 warmup per mode, 4800 frames x6 alternating repeats (smoke 240 x1). No image,
mask, query or counter readback. Total AA includes stencil clear; temporal resolve
excludes camera velocity and preparation, which remain in total AA. AA-Off is zero
AA GPU work by definition, not a zero-duration timestamp observation. WholeFrame
and CPU wall frame are reported separately. Different executable absolute times
are not a paired contrast; use each branch's corrected native control for ratios.

Upstream origin: Intel CMAA2 `071c6b0857559f4e36f614362e6d2aab1b61938a` SMAA wrapper
omits stencil clear; SMAA author demo `71c806a838bdd7d517df19192a20f0c61b3ca29d`
clears stencil before SMAA. This corrects integration, not the SMAA algorithm.
