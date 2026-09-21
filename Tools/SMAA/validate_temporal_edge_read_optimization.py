"""Native regressions, unchanged old Load, and executable-order deduplication."""
import json,hashlib
import validate_temporal_contrast_shaders as base
out=base.root/'Docs/Temporal-Edge-Read-Optimization';out.mkdir(exist_ok=True)
old=json.loads((base.root/'Docs/Temporal-Edge-Read-Cost/shader-validation.json').read_text())
rows=[]
names=['One','Point','EarlyLoad','EarlyPoint']
for r in (0,1):
 for name in names+['Verify']:
  entry=f'DX10_SMAAEdgeRead{name}PS'
  blob,asm=base.compile(base.shader/'SMAAWrapper.hlsl',entry,r,'ps_5_0','edge_opt')
  code=[l.strip() for l in asm.splitlines() if l.strip() and not l.strip().startswith('//')]
  loads=[l for l in code if l.startswith('ld_')]
  samples=[l for l in code if l.startswith('sample')]
  if name=='One':
   prior=next(v for v in old['variants'] if v['entry']==entry and v['reprojection']==r)
   assert code==prior['instructions'],'old Load executable instructions changed'
  if name!='Verify':
   assert len(samples)==(3 if r else 2)+(1 if 'Point' in name else 0)
   assert len(loads)==(0 if 'Point' in name else 1)
   assert not any(l.startswith(('if_','deriv_','discard','store_')) for l in code)
   assert any(l.startswith('mad o0.xy,') and 'cb0[2].y' in l for l in code)
  else:
   assert len(samples)==1 and len(loads)==1
  rows.append(dict(name=name,reprojection=r,blob_sha256=hashlib.sha256(blob).hexdigest(),
      instruction_sha256=hashlib.sha256('\n'.join(code).encode()).hexdigest(),instructions=code))
r_on={x['name']:x for x in rows if x['reprojection']==1}
dedup={n:next((p for p in names[:i] if r_on[p]['instruction_sha256']==r_on[n]['instruction_sha256']),None) for i,n in enumerate(names)}
result=dict(native_unchanged=8,old_load_instructions_unchanged=True,duplicate_of=dedup,variants=rows)
(out/'shader-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: native preserved, original Load instructions unchanged')
print(json.dumps(dedup,indent=2))
