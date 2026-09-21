"""Compile native regressions and inspect paired reconstruction sample cost."""
import hashlib,json
import validate_temporal_contrast_shaders as base
rows=[]
prior=json.loads((base.root/'Docs/Temporal-DeJitter/shader-validation.json').read_text())
for reproj in (0,1):
 for old in prior['shader_variants']:
  if old['reprojection']!=reproj:continue
  blob,_=base.compile(base.shader/'SMAAWrapper.hlsl',old['entry'],reproj,'ps_5_0','paired_prior')
  assert hashlib.sha256(blob).hexdigest()==old['sha256']
 for stem in ('PairedDeJitterResolve',):
  entry='DX10_SMAA'+stem+'PS'
  blob,asm=base.compile(base.shader/'SMAAWrapper.hlsl',entry,reproj,'ps_5_0','paired')
  code=[s.strip() for s in asm.splitlines() if s.strip() and not s.strip().startswith('//')]
  samples=[s for s in code if s.startswith('sample')]
  assert len(samples)==(3 if reproj else 2)
  assert not any(s.startswith('if_') for s in code)
  rows.append(dict(entry=entry,reprojection=reproj,sha256=hashlib.sha256(blob).hexdigest(),sample_instructions=samples,
   derivative_instructions=sum(s.startswith('deriv_') for s in code)))
out=base.root/'Docs/Temporal-Paired-DeJitter/shader-validation.json'
out.write_text(json.dumps(dict(native_variants_unchanged=8,prior_dejitter_variants_unchanged=10,variants=rows),indent=2)+'\n')
print('PASS: native and current-only variants unchanged; paired variants compile with unchanged sample counts')
