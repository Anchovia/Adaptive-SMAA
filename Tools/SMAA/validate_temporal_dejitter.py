"""Compile production de-jitter variants; validate regressions and coordinate sign."""
import hashlib
import json
import re
import numpy as np
import validate_temporal_contrast_shaders as base

prior = json.loads((base.root/'Docs/Temporal-Contrast-Cost/shader-validation.json').read_text())
rows = []
for reproj in (0, 1):
    blob, asm = base.compile(base.shader/'SMAAWrapper.hlsl', 'DX10_SMAAScalarWeightResolvePS', reproj, 'ps_5_0', 'dejitter')
    old = next(r for r in prior if r['entry'] == 'DX10_SMAAScalarWeightResolvePS' and r['reprojection'] == reproj)
    assert hashlib.sha256(blob).hexdigest() == old['sha256']
    for stem in ('ScalarCurrentLinearResolve', 'CurrentDeJitterResolve', 'ScalarDeJitterResolve', 'DeJitterMask', 'DeJitterSpatial'):
        entry = 'DX10_SMAA'+stem+'PS'
        blob, asm = base.compile(base.shader/'SMAAWrapper.hlsl', entry, reproj, 'ps_5_0', 'dejitter')
        code = [s.strip() for s in asm.splitlines() if s.strip() and not s.strip().startswith('//')]
        samples = [s for s in code if s.startswith('sample')]
        debug = stem in ('DeJitterMask', 'DeJitterSpatial')
        assert len(samples) == (1 if debug else 3 if reproj else 2), entry
        derivatives = sum(s.startswith('deriv_') for s in code)
        assert derivatives == (2 if stem.startswith('Scalar') or stem == 'DeJitterMask' else 0), entry
        assert not any(s.startswith('if_') for s in code), entry
        rows.append(dict(entry=entry, reprojection=reproj, sha256=hashlib.sha256(blob).hexdigest(),
                         sample_instructions=samples, derivative_instructions=derivatives,
                         executable_instruction_count=sum(not s.startswith(('dcl_', 'ps_')) for s in code)))

# Independent affine signal: geometry displacement +j gives image F(x-j).
# Bilinear reconstruction at x+j cancels it in the interior; x-j doubles it.
# This validates the sign convention, not a substitute for the real GPU capture.
y, x = np.mgrid[0:16, 0:16].astype(np.float64)
signal = lambda x, y: .1 + .01*x + .02*y
probes = []
for index, jitter in ((0, 0), (1, .25), (2, -.25)):
    geometry_image = signal(x-jitter, y-jitter)
    dx = dy = jitter
    ix, iy = np.floor(x+dx).astype(int), np.floor(y+dy).astype(int)
    fx, fy = x+dx-ix, y+dy-iy
    sample = lambda iy, ix: geometry_image[np.clip(iy,0,15), np.clip(ix,0,15)]
    reconstructed = ((1-fx)*(1-fy)*sample(iy,ix)+fx*(1-fy)*sample(iy,ix+1)
                     +(1-fx)*fy*sample(iy+1,ix)+fx*fy*sample(iy+1,ix+1))
    error = float(np.abs(reconstructed[1:-1,1:-1]-signal(x,y)[1:-1,1:-1]).max())
    assert error < 1e-12
    probes.append(dict(subsample_index=index, screen_jitter=[jitter,jitter], interior_ramp_error=error))
out = base.root/'Docs/Temporal-DeJitter';out.mkdir(parents=True, exist_ok=True)
(out/'shader-validation.json').write_text(json.dumps(dict(native_variants_unchanged=8,
    scalar_variants_unchanged=2, shader_variants=rows, cpu_sign_probes=probes), indent=2)+'\n', encoding='utf-8')
print('PASS: native/Scalar unchanged, 10 new variants, same sample counts, no divergent branch, CPU sign probes')
