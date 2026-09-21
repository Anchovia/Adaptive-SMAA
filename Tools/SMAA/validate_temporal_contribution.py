"""Preserve native/paired shaders and inspect real contribution shader bytecode."""
import hashlib,json
import validate_temporal_contrast_shaders as base
prior=json.loads((base.root/'Docs/Temporal-Paired-DeJitter/shader-validation.json').read_text())
for old in prior['variants']:
 blob,_=base.compile(base.shader/'SMAAWrapper.hlsl',old['entry'],old['reprojection'],'ps_5_0','contribution_before')
 assert hashlib.sha256(blob).hexdigest()==old['sha256']
rows=[]
for r in (0,1):
 for stem in ('ContributionNative','ContributionPaired','ContributionNativeMask','ContributionPairedMask','ContributionZeroMask'):
  blob,asm=base.compile(base.shader/'SMAAWrapper.hlsl','DX10_SMAA'+stem+'PS',r,'ps_5_0','contribution')
  code=[s.strip() for s in asm.splitlines() if s.strip() and not s.strip().startswith('//')]
  samples=[s for s in code if s.startswith('sample')]
  assert len(samples)==(0 if stem.endswith('ZeroMask') else 3 if r else 2)
  assert not any(s.startswith(('deriv_','if_')) for s in code)
  rows.append(dict(entry=stem,reprojection=r,sha256=hashlib.sha256(blob).hexdigest(),samples=samples,
   instruction_count=sum(not s.startswith(('dcl_','ps_')) for s in code)))
out=base.root/'Docs/Temporal-Selection-Validity/shader-validation.json'
out.write_text(json.dumps(dict(native_unchanged=8,paired_unchanged=4,variants=rows),indent=2)+'\n')
print('PASS: native 8 / paired 4 unchanged; 10 contribution variants; no added sample, derivative or dynamic branch')
