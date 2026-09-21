"""Compile speed schedules, reject equivalent code and preserve prior bytecode."""
import hashlib,json,re,subprocess
import validate_temporal_contrast_shaders as base
out=base.root/'Docs/Temporal-Speed-Limits';out.mkdir(parents=True,exist_ok=True)
prior=json.loads((base.root/'Docs/Temporal-Paired-DeJitter/shader-validation.json').read_text())
for old in prior['variants']:
 blob,_=base.compile(base.shader/'SMAAWrapper.hlsl',old['entry'],old['reprojection'],'ps_5_0','speed_before')
 assert hashlib.sha256(blob).hexdigest()==old['sha256']
rows=[]
for reproj in (0,1):
 for stem in ('SpeedBranch','SpeedUniformScalar','SpeedUniformBranch','SpeedUniformPrefetch','SpeedUniformWarp','SpeedPhasePositive','SpeedPhaseNegative','SpeedGroup4','SpeedGroup8','SpeedGroup16','SpeedDensity8','SpeedDensity16'):
  entry='DX10_SMAA'+stem+'PS';blob=base.out/f'speed_{stem}_{reproj}.dxbc';asm=blob.with_suffix('.asm')
  cmd=[str(base.fxc),'/nologo','/WX','/O3','/T','ps_5_0','/E',entry,'/D','SMAA_HLSL_4_1=1',
   '/D','SMAA_PRESET_ULTRA=1','/D',f'SMAA_REPROJECTION={reproj}','/D',f'VA_NV_WARP_EXTENSION={int(stem.endswith("Warp") or stem.startswith(("SpeedGroup","SpeedDensity")))}',
   '/I',str(base.shader),'/Fo',str(blob),'/Fc',str(asm),str(base.shader/'SMAAWrapper.hlsl')]
  p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
  code=[s.strip() for s in asm.read_text().splitlines() if s.strip() and not s.strip().startswith('//')]
  samples=[s for s in code if s.startswith('sample')]
  assert len(samples)==(3 if reproj else 2)
  assert sum(s.startswith('deriv_') for s in code)==2
  resources={int(re.search(r' t(\d+)',s).group(1)) for s in code if s.startswith('dcl_resource_texture2d')}
  assert resources==({2,4,7} if reproj else {2,4})
  branch_positions=[i for i,s in enumerate(code) if s.startswith('if_')]
  assert bool(branch_positions)==(stem not in ('SpeedUniformScalar','SpeedPhasePositive','SpeedPhaseNegative'))
  if branch_positions:
   assert max(i for i,s in enumerate(code) if s.startswith('deriv_'))<min(branch_positions)
   assert next(i for i,s in enumerate(code) if s.startswith('sample') and ' t4.' in s)>min(branch_positions)
  rows.append(dict(entry=entry,reprojection=reproj,sha256=hashlib.sha256(blob.read_bytes()).hexdigest(),
   instruction_hash=hashlib.sha256('\n'.join(code).encode()).hexdigest(),
   instruction_count=sum(not s.startswith(('dcl_','ps_')) for s in code),samples=samples,branch_positions=branch_positions))
duplicates=[]
for i,a in enumerate(rows):
 for b in rows[i+1:]:
  if a['reprojection']==b['reprojection'] and a['instruction_hash']==b['instruction_hash']:
   duplicates.append([a['entry'],b['entry'],a['reprojection']])
(out/'shader-validation.json').write_text(json.dumps(dict(native_unchanged=8,paired_unchanged=4,variants=rows,duplicate_instruction_streams=duplicates),indent=2)+'\n')
print(json.dumps(dict(status='PASS',variants=[(r['entry'],r['reprojection'],r['instruction_count']) for r in rows],duplicates=duplicates),indent=2))
