# 얇은 선 소실 지점 추적

- Branch: `validation/spatial-edge-thin-line-trace`.
- Direct base: corrected case 6 `304f7493c6a5e53fa3cfac5dfd084ce0e86ca459`.
- Target: Original spatial SMAA + exact first-pass edge stencil selective native
  T2X-R, paired jitter/subsample pattern Off, camera/depth reprojection On.
- Control: original spatial SMAA + native full-screen T2X-R, paired pattern On.
- A target repeat disables diagnostic readback and coverage instrumentation.

This is a diagnostic item, not a new AA algorithm. No candidate, history sampler,
weight, feedback, clipping, jitter, spatial math or production pass is changed.
The previous full-screen Pattern-Off experiment remains on its own branch; its
verified captures may be used as external evidence with source hashes.

Dependencies are limited to the noninteractive shader failure guard from
`12f5d56`, the existing corrected baseline capture runner, and the idea of raw
current/previous/velocity DDS readback from `eb1bd0b`. The previous experiments'
renderer changes are not merged. All SMAA HLSL files must remain byte-identical
to the direct base. Branch policy and mandatory direct frame inspection rules
are carried forward as documentation only.

## Capture and acceptance

Bistro and Minecraft use independent clean processes, Ultra, 1920x1061, fixed
60 Hz, 60-frame warmup and the existing still60/move120/still60 camera timeline.
All final RGB PNGs must match the corrected baseline, including a diagnostic-Off
repeat. Capture wall time is not a performance result.

Trace frames 127..138, 173..185 and 189..195 capture:

1. Raw AA input before spatial processing (DDS).
2. Current spatial RGBA, previous spatial RGBA and camera velocity (DDS).
3. Final first-pass RG edges and current RGB preview.
4. Actual selected GPU coverage and native invocation/sample counts.
5. Final RGB output.

Point-history lookup and native weight are reconstructed offline from those
exact GPU inputs. Point-sample boundary uncertainty, sRGB conversion and fused
multiply-add arithmetic must be checked against real output; ambiguous samples
are not presented as exact GPU fetch witnesses. Prior adjacent-frame history
bytes must match. Nonselected target RGB must equal current spatial RGB.

## Interpretation

Directly inspect at least six consecutive original frames at the known chair,
window and Minecraft line ROIs, covering motion, motion-to-still and late still.
Separate missing raw input, spatial changes, nonselection, history sampling and
blend attenuation. Preserve original colors; label magnification and any mask or
difference visualization. Supersample reference is only a spatial proxy.

No whole-image metric can override visible line loss or disconnection. This
diagnostic does not establish a new method's quality or speed. Recommendations
must follow the observed loss stage; do not change multiple temporal elements.
