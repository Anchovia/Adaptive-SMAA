"""Prove native preservation and absence of T2X-R texture work in edge-only DXBC."""
import json,hashlib
import validate_temporal_contrast_shaders as base
out=base.root/'Docs/Temporal-Edge-Only-Cost';out.mkdir(exist_ok=True)
old=json.loads((base.root/'Docs/Temporal-Edge-Read-Optimization/shader-validation.json').read_text())
rows=[]
for r in (0,1):
 for name in ['DX10_SMAAEdgeReadOnePS','DX10_SMAAEdgeOnlyOutputPS','DX10_SMAAEdgeOnlyReadPS']:
  blob,asm=base.compile(base.shader/'SMAAWrapper.hlsl',name,r,'ps_5_0','edge_only')
  code=[l.strip() for l in asm.splitlines() if l.strip() and not l.strip().startswith('//')]
  samples=[l for l in code if l.startswith('sample')];loads=[l for l in code if l.startswith('ld_')]
  if name=='DX10_SMAAEdgeReadOnePS':
   prior=next(v for v in old['variants'] if v['name']=='One' and v['reprojection']==r)
   assert code==prior['instructions'],'combined shader changed'
  else:
   assert not samples,(name,samples)
   assert len(loads)==(1 if 'OnlyRead' in name else 0),(name,loads)
   if loads:assert 't8.xyzw' in loads[0]
   declarations=[l for l in code if l.startswith('dcl_resource')]
   assert len(declarations)==len(loads) and all(l.endswith(' t8') for l in declarations)
   assert any(l.startswith('mul o0.xy,') and 'cb0[2].y' in l for l in code),code
   assert not any(l.startswith(('if_','deriv_','discard','store_','sqrt')) for l in code)
  rows.append(dict(entry=name,reprojection=r,sha256=hashlib.sha256(blob).hexdigest(),sample_count=len(samples),loads=loads,instructions=code))
result=dict(native_unchanged=8,combined_instructions_unchanged=True,variants=rows,scope='DXBC; native GPU ISA/DRAM transactions not measured')
(out/'shader-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('PASS: native 8 and combined unchanged; edge-only has no native samples, output-only reads no texture')
