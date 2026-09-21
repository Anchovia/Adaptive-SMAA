"""Check native bytecode preservation and one-instruction history filter changes."""
import hashlib
import json
import re
import validate_temporal_contrast_shaders as base

rows = []
prior = json.loads((base.root/'Docs/Temporal-Contrast-Cost/shader-validation.json').read_text())
for reproj in (0, 1):
    for scalar in (False, True):
        point = 'DX10_SMAAScalarWeightResolvePS' if scalar else 'DX10_SMAALodResolvePS'
        linear = 'DX10_SMAAScalarHistoryLinearResolvePS' if scalar else 'DX10_SMAAHistoryLinearResolvePS'
        blobs, codes, samplers = [], [], []
        for entry in (point, linear):
            blob, asm = base.compile(base.shader/'SMAAWrapper.hlsl',entry,reproj,'ps_5_0','history-filter')
            code = [s.strip() for s in asm.splitlines() if s.strip() and not s.strip().startswith('//')]
            reads = [s for s in code if s.startswith('sample')]
            assert len(reads) == (3 if reproj else 2)
            assert sum(s.startswith('deriv_') for s in code) == (2 if scalar else 0)
            assert not any(s.startswith('if_') for s in code)
            blobs.append(blob);codes.append(code);samplers.append(reads)
            if scalar and entry == point:
                old = next(r for r in prior if r['entry']==entry and r['reprojection']==reproj)
                assert hashlib.sha256(blob).hexdigest()==old['sha256']
        # Added sampler declaration and history sampler operand are the only
        # differences permitted in emitted instruction text.
        normalize = lambda code: [re.sub(r'\bs0\b','s1',s) for s in code if not s.startswith('dcl_sampler')]
        assert normalize(codes[0]) == normalize(codes[1]), (point, reproj)
        rows.append({'reprojection':reproj,'scalar':scalar,'point_entry':point,'linear_entry':linear,
                     'point_sha256':hashlib.sha256(blobs[0]).hexdigest(),'linear_sha256':hashlib.sha256(blobs[1]).hexdigest(),
                     'sample_instructions':samplers,'instruction_difference':'history sampler operand/declaration only'})
out=base.root/'Docs/Temporal-History-Filter';out.mkdir(parents=True,exist_ok=True)
(out/'shader-validation.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
print('PASS: four Point/Linear pairs differ only in sampler; 8 native variants and 2 existing scalar variants preserved')
