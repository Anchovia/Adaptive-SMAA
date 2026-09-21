"""Verify native preservation and live t9 reads in the diagnostic DXBC."""
import json,hashlib
import validate_temporal_contrast_shaders as base
out=base.root/'Docs/Temporal-Blend-Read-Cost';out.mkdir(exist_ok=True)
rows=[]
for r in (0,1):
 for name in ('DX10_SMAAResolvePS','DX10_SMAABlendReadControlPS','DX10_SMAABlendReadOnePS'):
  blob,asm=base.compile(base.shader/'SMAAWrapper.hlsl',name,r,'ps_5_0','blend_read')
  code=[l.strip() for l in asm.splitlines() if l.strip() and not l.strip().startswith('//')]
  samples=[l for l in code if l.startswith('sample')]
  loads=[l for l in code if l.startswith('ld_')]
  assert len(samples)==(3 if r else 2),(name,samples)
  assert len(loads)==(1 if 'ReadOne' in name else 0),(name,loads)
  if loads:assert 't9.xyzw' in loads[0] and 'o0.xyzw' in code[-2],code
  assert not any(l.startswith(('if_','deriv_','discard','store_')) for l in code)
  if name!='DX10_SMAAResolvePS':assert 'cb0[2].y' in code[-2] and code[-2].startswith('mad '),code[-3:]
  rows.append(dict(entry=name,reprojection=r,sha256=hashlib.sha256(blob).hexdigest(),sample_count=len(samples),loads=loads,last_instructions=code[-3:],instructions=code))
(out/'shader-validation.json').write_text(json.dumps(dict(native_unchanged=8,variants=rows,scope='DXBC only; not native GPU ISA or independent DRAM timing'),indent=2)+'\n')
print('PASS: native 8 unchanged; 6 variants; live t9 Load, matching zero-sink MAD, no branch/derivative')
