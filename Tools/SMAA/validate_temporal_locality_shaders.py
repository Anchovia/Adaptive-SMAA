"""Inspect emitted conditional versus unconditional texture access, not GPU ISA."""
import hashlib
import json
import re
import validate_temporal_contrast_shaders as base

results = []
for reproj in (0, 1):
    for style in ('Branch', 'Flatten'):
        entry = f'DX10_SMAAStripe{style}ResolvePS'
        blob, asm = base.compile(base.shader/'SMAAWrapper.hlsl', entry, reproj, 'ps_5_0', 'locality')
        lines = [s.strip() for s in asm.splitlines() if s.strip() and not s.strip().startswith('//')]
        samples = [(i, s) for i, s in enumerate(lines) if s.startswith('sample')]
        branches = [(i, s) for i, s in enumerate(lines) if s.startswith('if_')]
        assert len(samples) == (3 if reproj else 2)
        assert not any(s.startswith('deriv_') for s in lines)
        assert any(s.startswith('ushr') for s in lines), 'Runtime stripe width must survive compilation'
        if style == 'Branch':
            assert len(branches) == 1
            assert samples[0][0] < branches[0][0] < samples[1][0]
        else:
            assert not branches and any(s.startswith('movc') for s in lines)
        results.append(dict(entry=entry,reprojection=reproj,sha256=hashlib.sha256(blob).hexdigest(),
            samples=[s for _,s in samples],branches=[s for _,s in branches],
            slots=int(re.search(r'Approximately (\d+) instruction',asm)[1]),
            temps=int(re.search(r'dcl_temps (\d+)',asm)[1])))
out=base.root/'Docs/Temporal-Contrast-Locality'
out.mkdir(parents=True,exist_ok=True)
(out/'shader-validation.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS: four stripe variants; identical shader per width, conditional fetch vs full fetch checked')
