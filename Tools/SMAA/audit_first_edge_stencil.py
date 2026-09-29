"""Source/compiled shader audit; not an output or GPU performance test."""
import hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2]; S=R/'Projects/CMAA2/SMAA'
D=R/'Docs/First-Edge-Temporal-Only-Stencil'; T=R/'tmp/stencil-shaders'
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(b):return b.replace(b'\r\n',b'\n')
def main():
    D.mkdir(parents=True,exist_ok=True);T.mkdir(parents=True,exist_ok=True)
    unchanged={}
    for name in ['SMAA.hlsl','SMAAWrapper.hlsl']:
        b=norm((S/name).read_bytes())
        original=subprocess.check_output(['git','show','c51ca28:Projects/CMAA2/SMAA/'+name],cwd=R)
        assert b==norm(original),name
        unchanged[name]=sha(b)
    raw=norm((S/'TemporalOnlyControl.hlsl').read_bytes())
    assert raw==norm(subprocess.check_output(['git','show','7c2feeb:Projects/CMAA2/SMAA/TemporalOnlyControl.hlsl'],cwd=R))
    unchanged['TemporalOnlyControl.hlsl']=sha(raw)
    cpp=norm((S/'SMAA.cpp').read_bytes())
    base=norm(subprocess.check_output(['git','show','c51ca28:Projects/CMAA2/SMAA/SMAA.cpp'],cwd=R))
    go=cpp[cpp.index(b'void SMAA::go('):cpp.index(b'void SMAA::detectFirstEdges(')].rstrip()
    assert go==base[base.index(b'void SMAA::go('):base.index(b'void SMAA::reproject(')].rstrip()
    resolve=cpp[cpp.index(b'void SMAA::reproject('):cpp.index(b'void SMAA::separate(')].rstrip()
    assert resolve==base[base.index(b'void SMAA::reproject('):base.index(b'void SMAA::separate(')].rstrip()
    unchanged['native_go']=sha(go);unchanged['native_reproject']=sha(resolve)
    fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.19041.0/x64/fxc.exe'
    variants=[]
    entries=['ExactLumaEdgePS','ExactLumaRawEdgePS','ExactColorEdgePS','ExactDepthEdgePS',
             'RawRetainPS','FirstEdgeStencilPS','FirstEdgeStencilCoveragePS']
    for reprojection in [0,1]:
        for entry in entries:
            obj=T/f'{entry}-{reprojection}.dxbc'; asm=obj.with_suffix('.asm')
            result=subprocess.run([fxc,'/nologo','/O3','/T','ps_5_0','/E',entry,
                '/D',f'SMAA_REPROJECTION={reprojection}','/D','SMAA_PRESET_ULTRA=1',
                '/D','SMAA_RT_METRICS=float4(1.0/1920,1.0/1061,1920,1061)',
                '/Fo',str(obj),'/Fc',str(asm),str(S/'FirstEdgeStencil.hlsl')],capture_output=True)
            assert result.returncode==0,(entry,result.stdout.decode(errors='replace'),result.stderr.decode(errors='replace'))
            code=[x.strip() for x in asm.read_text().splitlines() if x.strip() and not x.strip().startswith('//')]
            if entry.startswith('FirstEdgeStencil'):
                assert any('forceEarlyDepthStencil' in x for x in code),code
                assert not any('t8' in x for x in code)
                assert not any(x.startswith(('if_','discard','ld ')) for x in code)
                samples=[x for x in code if x.startswith('sample')]
                assert sum('t2.' in x for x in samples)==sum('t4.' in x for x in samples)==1
                assert sum('t7.' in x for x in samples)==reprojection
            variants.append(dict(entry=entry,reprojection=reprojection,dxbc_sha256=sha(obj.read_bytes()),instructions=code))
    sources={p.relative_to(R).as_posix():sha(norm(p.read_bytes())) for p in [S/'SMAA.h',S/'SMAA.cpp',S/'FirstEdgeStencil.hlsl',S/'vaSMAAWrapper.h',S/'vaSMAAWrapperDX11.cpp',R/'Projects/CMAA2/FirstEdgeStencilVerification.inl']}
    data=dict(validation='PASS',scope='source-and-DXBC-only',base='c51ca28',dependencies=['7c2feeb','a774772','543e657','037fd8b-stencil-components-only'],
              native_shader_unchanged=unchanged,source_sha256_lf=sources,variants=variants,
              executable_sha256=sha((R/'Projects/CMAA2/CMAA2.exe').read_bytes()),compiler=fxc)
    (D/'source-audit.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print('PASS: native shaders unchanged; early stencil flag, no edge load/selection branch in resolve; 14 shader variants compile')
if __name__=='__main__':main()
