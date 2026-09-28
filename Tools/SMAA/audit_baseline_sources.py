"""Record baseline lineage and verify all native algorithm files are unchanged."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def git(*args):return subprocess.check_output(['git','-c','safe.directory='+str(ROOT),*args],cwd=ROOT)
def norm(b):return b.replace(b'\r\n',b'\n')
def sha(b):return hashlib.sha256(b).hexdigest()
files=git('ls-tree','-r','--name-only','88893da','Projects/CMAA2/SMAA').decode().splitlines()
rows=[]
accessor=b'        // Harness access to the same preset edited by the existing UI.\n        Settings &                  GetSettings( ) { return m_settings; }\n'
for name in files:
    base=norm(git('show','88893da:'+name));actual=norm((ROOT/name).read_bytes())
    if name.endswith('/vaSMAAWrapper.h'):
        assert actual.count(accessor)==1
        assert actual.replace(accessor,b'')==base
        status='Only preset accessor added; all existing code identical'
    else:assert actual==base,name;status='Identical'
    rows.append(dict(file=name,baseline_sha256=sha(base),current_sha256=sha(actual),status=status))
assert git('show','baseline-original-smaa:Projects/CMAA2/SMAA/SMAA.hlsl')==git('show','88893da:Projects/CMAA2/SMAA/SMAA.hlsl')
for name in ['Modules/Rendering/vaRendering.h','Modules/Rendering/vaShader.h']:
    assert norm((ROOT/name).read_bytes())==norm(git('show','684ac91:'+name))
result=dict(validation='PASS',baseline=git('rev-parse','88893da').decode().strip(),original_spatial=git('rev-parse','baseline-original-smaa^{commit}').decode().strip(),
    branch=git('branch','--show-current').decode().strip(),algorithm_files=rows,
    original_spatial_hlsl_identical=True,runtime_dependency='c513158 from tooling/baseline-shader-lifetime; two-file backport of 684ac91',
    normalization='CRLF to LF only; no whitespace or token normalization',executable_sha256=sha((ROOT/'Projects/CMAA2/CMAA2.exe').read_bytes()))
(ROOT/'Docs/Baseline-Restart/source-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: native baseline files and exact runtime backport audited')
