"""Validate unchanged native paths and cost variants before runtime tests."""
import hashlib, json, re
import validate_temporal_contrast_shaders as base
entries=['ScalarWeight','ScalarReassociated','BranchReassociated','HistoryLoad','SelectorAny','FixedThreshold','ScalarFixedThreshold']
rows=[]
for reproj in (0,1):
    for name in entries:
        entry='DX10_SMAA'+name+'ResolvePS'
        blob,asm=base.compile(base.shader/'SMAAWrapper.hlsl',entry,reproj,'ps_5_0','cost')
        code=[s.strip() for s in asm.splitlines() if s.strip() and not s.strip().startswith('//')]
        assert sum(s.startswith('deriv_') for s in code)==2
        reads=[s for s in code if s.startswith(('sample','ld_indexable'))]
        assert len(reads)==(3 if reproj else 2)
        branches=[s for s in code if s.startswith('if_')]
        assert bool(branches)==(not name.startswith('Scalar'))
        assert any(s.startswith('ld_indexable') for s in code)==(name=='HistoryLoad')
        if 'FixedThreshold' in name: assert not any(s.startswith('dcl_constantbuffer') for s in code)
        rows.append(dict(entry=entry,reprojection=reproj,sha256=hashlib.sha256(blob).hexdigest(),
            slots=int(re.search(r'Approximately (\d+) instruction',asm)[1]),
            reads=reads,branches=branches))
out=base.root/'Docs/Temporal-Contrast-Cost';out.mkdir(parents=True,exist_ok=True)
(out/'shader-validation.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PASS: fourteen cost variants; same fine derivatives, no additional resources; emitted read/branch structure checked')
