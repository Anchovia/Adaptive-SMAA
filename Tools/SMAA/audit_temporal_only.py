"""Record exact baseline code and implementation provenance for this isolated control."""
import hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];D=R/'Docs/Temporal-Only-Control';BASE='e14f122d841f432b9c633fdd480740e85fc8edff'
def git(*args):return subprocess.check_output(['git','-c',f'safe.directory={R.as_posix()}',*args],cwd=R)
def normal(b):return b.replace(b'\r\n',b'\n')
def sha(b):return hashlib.sha256(b).hexdigest()
def function(b,start,end):return b[b.index(start):b.index(end,b.index(start))]
def main():
    same=['Projects/CMAA2/SMAA/SMAA.hlsl','Projects/CMAA2/SMAA/SMAAWrapper.hlsl','Projects/CMAA2/BaselineVerification.inl']
    checks={}
    for p in same:
        b=normal((R/p).read_bytes());assert b==normal(git('show',f'{BASE}:{p}'));checks[p]=sha(b)
    p='Projects/CMAA2/SMAA/SMAA.cpp';b=normal((R/p).read_bytes());old=normal(git('show',f'{BASE}:{p}'))
    # Compare entire original reproject implementation through the following function.
    for start,end in [(b'void SMAA::reproject(',b'void SMAA::separate('),(b'void SMAA::go(',b'void SMAA::reproject(')]:
        x=function(b,start,end)
        if start==b'void SMAA::go(':x=x.split(b'void SMAA::prepareTemporalOnly(')[0]
        assert x.rstrip()==function(old,start,end).rstrip()
        checks[start.decode()]=sha(x.rstrip())
    files={}
    for p in ['Projects/CMAA2/CMAA2Sample.cpp','Projects/CMAA2/SMAA/SMAA.cpp','Projects/CMAA2/SMAA/SMAA.h','Projects/CMAA2/SMAA/vaSMAAWrapper.h','Projects/CMAA2/SMAA/vaSMAAWrapperDX11.cpp','Projects/CMAA2/SMAA/TemporalOnlyControl.hlsl','Projects/CMAA2/TemporalOnlyVerification.inl']:
        files[p]=sha(normal((R/p).read_bytes()))
    result=dict(validation='PASS',baseline_commit=BASE,implementation_commit=git('rev-parse','HEAD').decode().strip(),branch=git('branch','--show-current').decode().strip(),
        original_unchanged=checks,source_sha256_lf_normalized=files,executable_sha256=sha((R/'Projects/CMAA2/CMAA2.exe').read_bytes()),
        note='Source audit plus capture proof; native spatial and resolve math retained. New preparation matches native zero-weight behavior. No selective algorithm in this branch.')
    (D/'source-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print('Source audit PASS')
if __name__=='__main__':main()
