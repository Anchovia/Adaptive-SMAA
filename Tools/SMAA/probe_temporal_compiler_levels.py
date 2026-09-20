"""Reject optimization-level changes that emit the same instruction stream."""
import hashlib,json,subprocess
import validate_temporal_contrast_shaders as base
out=base.root/'tmp/temporal-compiler-levels';out.mkdir(parents=True,exist_ok=True)
results=[]
for entry in ('DX10_SMAAContrastResolvePS','DX10_SMAAScalarWeightResolvePS','DX10_SMAAScalarFixedThresholdResolvePS'):
    variants=[]
    for level in (1,2,3):
        asm=out/f'{entry}_O{level}.asm';blob=asm.with_suffix('.dxbc')
        args=[str(base.fxc),'/nologo','/WX',f'/O{level}','/T','ps_5_0','/E',entry,
              '/D','SMAA_HLSL_4_1=1','/D','SMAA_PRESET_ULTRA=1','/D','SMAA_REPROJECTION=1',
              '/I',str(base.shader),'/Fo',str(blob),'/Fc',str(asm),str(base.shader/'SMAAWrapper.hlsl')]
        subprocess.run(args,check=True,capture_output=True)
        code='\n'.join(s.strip() for s in asm.read_text().splitlines() if s.strip() and not s.strip().startswith('//'))
        variants.append(dict(level=level,instruction_sha256=hashlib.sha256(code.encode()).hexdigest()))
    results.append(dict(entry=entry,variants=variants,all_instruction_identical=len({x['instruction_sha256'] for x in variants})==1))
dest=base.root/'Docs/Temporal-Contrast-Cost/compiler-levels.json'
dest.write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
