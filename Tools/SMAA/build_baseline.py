"""Build with a case-insensitively unique Windows environment (Path/PATH)."""
import os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
env={};seen=set()
for k,v in os.environ.items():
    if k.upper() not in seen:env['Path' if k.upper()=='PATH' else k]=v;seen.add(k.upper())
env['MSBUILDDISABLENODEREUSE']='1'
(root/'tmp').mkdir(exist_ok=True)
with (root/'tmp/baseline-restart-build.log').open('w') as log:
    result=subprocess.run(['C:/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe','CMAA2.sln','/m:1','/nr:false','/p:Configuration=Release','/p:Platform=x64','/v:minimal','/nologo'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
print('Build exit:',result.returncode,flush=True)
raise SystemExit(result.returncode)
