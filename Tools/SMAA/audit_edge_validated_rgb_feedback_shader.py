"""Compile validation variants and prove prior control shader bytecodes intact."""
import hashlib,json,re,subprocess
from pathlib import Path
r=Path(__file__).resolve().parents[2];src=r/'Projects/CMAA2/SMAA'
out=r/'tmp/edge-validated-rgb-feedback/shaders';out.mkdir(parents=True,exist_ok=True)
doc=r/'Docs/Edge-History-Adaptive-Validation';doc.mkdir(exist_ok=True)
fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
records=[]
for reprojection in (0,1):
 defines=['/D','SMAA_HLSL_4_1=1','/D','SMAA_PRESET_ULTRA=1','/D',f'SMAA_REPROJECTION={reprojection}']
 for file,entries in [('ValidatedRGBFeedback.hlsl',[k+s+'PS' for k in ('ValidatedRGBFeedback','ResponsiveRGBFeedback','ClippedRGBFeedback') for s in ('','Coverage')]),('ResolvedRGBFeedback.hlsl',['NeighborhoodFeedbackSeedPS','ResolvedRGBFeedbackPS','ResolvedRGBFeedbackCoveragePS']),('FirstEdgeStencil.hlsl',['FirstEdgeStencilPS','BilinearHistoryRGBPS'])]:
  for entry in entries:
   name=f'{entry}-R{reprojection}';binary=out/(name+'.dxbc');asm=out/(name+'.asm')
   command=[fxc,'/nologo','/T','ps_5_0','/E',entry,'/I',str(src),*defines,'/Fo',str(binary),'/Fc',str(asm),str(src/file)]
   result=subprocess.run(command,capture_output=True);assert result.returncode==0,result.stdout+result.stderr
   text=asm.read_text();count=len(re.findall(r'^\s*sample\w*\(',text,re.M))
   record=dict(entry=entry,reprojection=reprojection,samples=count,sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
   if file=='ValidatedRGBFeedback.hlsl':assert 'forceEarlyDepthStencil' in text
   else:
    old=subprocess.run(['git','-c',f'safe.directory={r.as_posix()}','show',f'b793b74:Projects/CMAA2/SMAA/{file}'],check=True,capture_output=True).stdout
    oldfile=out/('old-'+file);oldfile.write_bytes(old);oldbinary=out/(name+'-old.dxbc')
    result=subprocess.run([fxc,'/nologo','/T','ps_5_0','/E',entry,'/I',str(src),*defines,'/Fo',str(oldbinary),str(oldfile)],capture_output=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert oldbinary.read_bytes()==binary.read_bytes(),name;record['control_byte_exact']=True
   records.append(record)
(doc/'shader-audit.json').write_text(json.dumps(dict(validation='PASS',records=records),indent=2)+'\n')
print('PASS',len(records),'compiled entries; old controls byte-exact')
