"""Validate native preservation and current-only diagnostic texture work in DXBC."""
import hashlib
import json
import validate_temporal_contrast_shaders as base

out = base.root / 'Docs/Temporal-Current-Edge-Cost'
out.mkdir(exist_ok=True)
old = json.loads((base.root / 'Docs/Temporal-Edge-Only-Cost/shader-validation.json').read_text())
rows = []
for r in (0, 1):
    for name in ['DX10_SMAAEdgeReadOnePS', 'DX10_SMAACurrentOutputControlPS', 'DX10_SMAACurrentEdgeReadPS']:
        blob, asm = base.compile(base.shader / 'SMAAWrapper.hlsl', name, r, 'ps_5_0', 'current_edge')
        code = [l.strip() for l in asm.splitlines() if l.strip() and not l.strip().startswith('//')]
        samples = [l for l in code if l.startswith('sample')]
        loads = [l for l in code if l.startswith('ld_')]
        if name == 'DX10_SMAAEdgeReadOnePS':
            prior = next(v for v in old['variants'] if v['entry'] == name and v['reprojection'] == r)
            assert code == prior['instructions'], 'combined shader changed'
        else:
            edge = name == 'DX10_SMAACurrentEdgeReadPS'
            assert len(samples) == 1 and 't2.xyzw' in samples[0] and 's1' in samples[0], samples
            assert len(loads) == int(edge), loads
            if edge:
                assert 't8.xyzw' in loads[0], loads
            declarations = [l for l in code if l.startswith('dcl_resource')]
            assert len(declarations) == 1 + int(edge), declarations
            assert all(l.endswith((' t2', ' t8')) for l in declarations)
            assert any(l.startswith('mad ') and 'cb0[2].y' in l for l in code), code
            assert not any(l.startswith(('if_', 'deriv_', 'discard', 'store_', 'sqrt')) for l in code)
        rows.append(dict(entry=name, reprojection=r, sha256=hashlib.sha256(blob).hexdigest(),
                         sample_count=len(samples), loads=loads, instructions=code))
result = dict(native_unchanged=8, combined_instructions_unchanged=True, variants=rows,
              scope='DXBC; native GPU ISA/DRAM transactions not measured')
(out / 'shader-validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print('PASS: native 8 and combined unchanged; current controls read t2 once; edge variant adds one t8 Load')
