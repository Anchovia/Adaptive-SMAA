import json,hashlib,subprocess
from pathlib import Path
import validate_temporal_contrast_shaders as base
out=base.root/'Docs/Temporal-First-Edge-Selective';out.mkdir(exist_ok=True)
old=json.loads((base.root/'Docs/Temporal-Current-Edge-Cost/shader-validation.json').read_text())
legacy=subprocess.check_output(['git','-c',f'safe.directory={base.root.as_posix()}','show','experiment/standard-t2x-edge-mask:Projects/CMAA2/SMAA/SMAAWrapper.hlsl'],cwd=base.root).decode('utf-8-sig')
a=legacy.index('float4 DX10_SMAAResolveEdgeMaskPS(');z=legacy.index('\n}',a)+2
expected=legacy[a:z].replace('DX10_SMAAResolveEdgeMaskPS','DX10_SMAAFirstEdgeLegacyPS').replace('\r\n','\n')
source=(base.shader/'TemporalFirstEdge.hlsl').read_text();assert expected in source
rows=[]
for r in (0,1):
 for name in ['DX10_SMAAEdgeReadOnePS','DX10_SMAACurrentEdgeReadPS','DX10_SMAAFirstEdgeReusePS','DX10_SMAAFirstEdgeLegacyPS']:
  blob,asm=base.compile(base.shader/'SMAAWrapper.hlsl',name,r,'ps_5_0','first_edge')
  code=[l.strip() for l in asm.splitlines() if l.strip() and not l.strip().startswith('//')]
  if 'FirstEdge' not in name:
   prior=next(v for v in old['variants'] if v['entry']==name and v['reprojection']==r)
   assert code==prior['instructions'],name
  else:
   loads=[l for l in code if l.startswith('ld_')];assert len(loads)==1 and 't8.xyzw' in loads[0],loads
   branches=[i for i,l in enumerate(code) if l.startswith('if_')];assert branches,code
   samples=[(i,l) for i,l in enumerate(code) if l.startswith('sample')]
   # A non-edge early return precedes history/velocity reads in emitted DXBC.
   first_return=next(i for i,l in enumerate(code) if l=='ret')
   for i,l in samples:
    if 't4.xyzw' in l or 't7.xyzw' in l:assert i>branches[0] and i>first_return,(name,l)
   assert sum('t4.xyzw' in l for i,l in samples)==1
   assert sum('t7.xyzw' in l for i,l in samples)==r
   if 'Reuse' in name:assert sum('t2.xyzw' in l for i,l in samples)==1
  rows.append(dict(entry=name,reprojection=r,sha256=hashlib.sha256(blob).hexdigest(),instructions=code))
result=dict(native_unchanged=8,controls_unchanged=True,legacy_source_unchanged_except_name=True,legacy_function_sha256=hashlib.sha256(expected.encode()).hexdigest(),variants=rows,scope='DXBC conditional texture instructions; not hardware warp efficiency or DRAM transaction counts')
(out/'shader-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('PASS: native 8 and read controls unchanged; legacy body preserved; edge load and conditional history/velocity verified')
