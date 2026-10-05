"""Compile actual variants and check preserved native/case-9 DXBC before execution."""
from pathlib import Path
import subprocess,json,hashlib,re
R=Path(__file__).resolve().parents[2];D=R/'Docs/Edge-Persistence-Eager-Spatial-Mask';T=R/'tmp/eager-spatial-mask-audit';T.mkdir(exist_ok=True)
fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['SMAA.hlsl','SMAAWrapper.hlsl','FirstEdgeStencil.hlsl','PersistenceEdgeStencil.hlsl']:
 (T/name).write_bytes(git('show','e54f0db:Projects/CMAA2/SMAA/'+name))
def compile(folder,source,entry,tag,defines):
 dst=T/(tag+'.dxbc');asm=dst.with_suffix('.asm')
 cmd=[fxc,'/nologo','/T','ps_5_0','/E',entry,'/D','SMAA_PRESET_ULTRA=1','/D','SMAA_RT_METRICS=float4(1.0/1920,1.0/1061,1920,1061)','/Fo',str(dst),'/Fc',str(asm)]
 for define in defines:cmd+=['/D',define]
 result=subprocess.run(cmd+[str(folder/source)],capture_output=True,text=True)
 assert result.returncode==0,result.stdout+result.stderr
 text=asm.read_text();slots=re.search(r'Approximately (\d+) instruction slots',text)
 return dict(dxbc_sha256=sha(dst),instructions=int(slots[1]) if slots else None,assembly=str(asm))
src=R/'Projects/CMAA2/SMAA';rows=[]
for rp in [0,1]:
 for entry in ['ExactLumaEdgePS','ExactLumaRawEdgePS','ExactColorEdgePS','ExactDepthEdgePS','NeighborhoodRetainPS','FirstEdgeStencilPS','FirstEdgeStencilCoveragePS']:
  a=compile(T,'FirstEdgeStencil.hlsl',entry,f'old-{entry}-{rp}',[f'SMAA_REPROJECTION={rp}'])
  b=compile(src,'FirstEdgeStencil.hlsl',entry,f'new-{entry}-{rp}',[f'SMAA_REPROJECTION={rp}'])
  assert a['dxbc_sha256']==b['dxbc_sha256'];rows.append(dict(entry=entry,reprojection=rp,unchanged=True,**b))
for kind in ['Luma','LumaRaw','Color','Depth']:
 entry='Persistence'+kind+'EdgePS';defs=['SMAA_REPROJECTION=1','PERSISTENCE_EAGER_FETCH=1']
 old=compile(T,'PersistenceEdgeStencil.hlsl',entry,'case9-old-'+kind,defs)
 ref=compile(src,'PersistenceEdgeStencil.hlsl',entry,'case9-control-'+kind,defs)
 new=compile(src,'PersistenceEdgeStencil.hlsl',entry,'eager-depth-'+kind,defs+['PERSISTENCE_DEPTH_MASK=1'])
 assert old['dxbc_sha256']==ref['dxbc_sha256'],kind
 assert ref['dxbc_sha256']!=new['dxbc_sha256'],kind
 rows.append(dict(entry=entry,control_identical=True,reference=ref,eager_depth=new))
files=['Projects/CMAA2/CMAA2Sample.cpp','Projects/CMAA2/EdgeEagerSpatialMask.inl']+['Projects/CMAA2/SMAA/'+n for n in ['SMAA.cpp','SMAA.h','vaSMAAWrapperDX11.cpp','vaSMAAWrapper.h','FirstEdgeStencil.hlsl','PersistenceEdgeStencil.hlsl','SMAAWrapper.hlsl','SMAA.hlsl']]
result=dict(validation='PASS',direct_base='304f749',renderer_dependency='e54f0db',shader_checks=rows,source_sha256={n:sha(R/n) for n in files})
(D/'source-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: 14 preserved + 4 case-9 control DXBC unchanged; 4 eager/depth variants compiled')
