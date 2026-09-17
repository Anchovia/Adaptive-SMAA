import subprocess, hashlib, json
from pathlib import Path
fxc=r'C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
root=Path('Projects/CMAA2/SMAA').resolve();scratch=Path('tmp/standard-edge-mask-shaders');scratch.mkdir(exist_ok=True)
old=scratch/'before.hlsl';old.write_bytes(subprocess.check_output(['git','show','81c0d23:Projects/CMAA2/SMAA/SMAAWrapper.hlsl']))
rows=[]
for reproj in (0,1):
 for entry in ('DX10_SMAALumaEdgeDetectionPS','DX10_SMAABlendingWeightCalculationPS','DX10_SMAANeighborhoodBlendingPS','DX10_SMAAResolvePS'):
  blobs=[]
  for label,source in [('before',old),('after',root/'SMAAWrapper.hlsl')]:
   out=scratch/f'{entry}_{reproj}_{label}.dxbc'
   cmd=[fxc,'/nologo','/WX','/O3','/T','ps_4_1','/E',entry,'/D','SMAA_HLSL_4_1=1','/D','SMAA_PRESET_ULTRA=1','/D',f'SMAA_REPROJECTION={reproj}','/I',str(root),'/Fo',str(out),str(source)]
   subprocess.run(cmd,check=True,capture_output=True);blobs.append(out.read_bytes())
  assert blobs[0]==blobs[1],(entry,reproj)
  rows.append({'entry':entry,'reprojection':reproj,'byte_identical':True,'sha256':hashlib.sha256(blobs[1]).hexdigest()})
Path('Docs/Standard-Edge-Mask-20260917/shader-regression.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PASS: 8 native shader variants byte-identical to 81c0d23')
