"""Validate DXBC controls; instruction counts are not hardware cycle counts."""
import hashlib
import json
import re
import validate_temporal_contrast_shaders as base

entries = ['DX10_SMAAResolvePS', 'DX10_SMAALodResolvePS',
           'DX10_SMAACurrentFirstResolvePS', 'DX10_SMAAStructuredResolvePS',
           'DX10_SMAAFlattenResolvePS', 'DX10_SMAAPrefetchVelocityResolvePS']
results = []
for reproj in (0, 1):
    for entry in entries:
        blob, asm = base.compile(base.shader/'SMAAWrapper.hlsl', entry, reproj, 'ps_5_0', 'execution')
        instructions = [s.strip() for s in asm.splitlines() if s and not s.startswith('//')]
        samples = [s for s in instructions if s.startswith('sample')]
        assert len(samples) == (3 if reproj else 2), (entry, samples)
        branches = [s for s in instructions if s.startswith('if_')]
        if entry.endswith(('StructuredResolvePS', 'PrefetchVelocityResolvePS')):
            assert len(branches) == 1
            branch_index = next(i for i,s in enumerate(instructions) if s.startswith('if_'))
            assert all(i < branch_index for i,s in enumerate(instructions) if s.startswith('deriv_'))
        if entry.endswith('FlattenResolvePS'):
            assert not branches and any(s.startswith('movc') for s in instructions)
        assert not any(' t8' in s for s in instructions)
        results.append(dict(entry=entry,reprojection=reproj,sha256=hashlib.sha256(blob).hexdigest(),
            samples=samples,branches=branches,
            slots=int(re.search(r'Approximately (\d+) instruction',asm)[1]),
            temps=int(re.search(r'dcl_temps (\d+)',asm)[1])))
out=base.root/'Docs/Temporal-Contrast-Execution'
out.mkdir(parents=True,exist_ok=True)
(out/'shader-validation.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS: 12 execution controls; actual branches, predicated selection and pre-branch derivatives checked')
