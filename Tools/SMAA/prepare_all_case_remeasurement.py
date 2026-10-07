"""Pin separate historical case sources; change measurement harnesses only.

Shared Media/_Lib are immutable runtime inputs. No archived renderer/HLSL is
edited. The constructor filters modes to target plus native control; it does
not alter their configuration. Capture diagnostics are omitted (RGB kept).
"""
import argparse, hashlib, io, json, re, subprocess, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'tmp/all-case-remeasurement'
SOURCE_ROOT=Path('C:/Users/USER/Desktop/research/tmp/r17')
BASE='ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB-Fixed080'
ITEMS=[
 (1,'baseline/aa-off-stencil-lifecycle','StencilLifecycleVerification','StencilLifecycle','AA-Off','AA 없음'),
 (2,'baseline/smaa-1x-stencil-lifecycle','StencilLifecycleVerification','StencilLifecycle','O-1X','원본 SMAA 1X'),
 (3,'baseline/temporal-only-stencil-lifecycle','StencilLifecycleVerification','StencilLifecycle','ABL-TemporalOnly-R','전체 temporal만'),
 (4,'baseline/smaa-t2x-r-stencil-lifecycle','StencilLifecycleVerification','StencilLifecycle','O-T2X-R','원본 SMAA T2X-R'),
 (5,'experiment/first-edge-temporal-only-stencil-lifecycle','StencilLifecycleVerification','StencilLifecycle','ABL-FirstEdge-TemporalOnly-Stencil-PatternOff-R','현재 edge temporal만'),
 (6,'experiment/spatial-first-edge-stencil-lifecycle','StencilLifecycleVerification','StencilLifecycle','ABL-Spatial-FirstEdge-Stencil-PatternOff-R','SMAA + 현재 edge'),
 (7,'experiment/spatial-edge-persistence-depth','EdgePersistenceVerification','EdgePersistence','ABL-Spatial-PreviousRawEdge-Depth-PatternOff-R','직전 raw edge 유지, depth'),
 (8,'validation/edge-persistence-cost-audit','EdgePersistenceCostAudit','EdgePersistenceCostAudit','E-PreviousRawEdge-FirstStencil','직전 raw edge, 첫 stencil'),
 (9,'experiment/edge-persistence-velocity-load','EdgeVelocityLoad','EdgeVelocityLoad','L-VelocityIntegerLoad','직전 edge, velocity 정수 읽기'),
 (10,'experiment/edge-persistence-bilinear-history-rgb','EdgeBilinearHistoryRGB','EdgeBilinearHistoryRGB','ABL-ET2X-R-PreviousRawEdge-BilinearRGB','Bilinear history RGB'),
 (11,'experiment/edge-persistence-resolved-rgb-feedback','EdgeResolvedRGBFeedback','EdgeResolvedRGBFeedback','ABL-ET2X-R-PreviousRawEdge-ResolvedRGB','누적 RGB feedback'),
 (12,'experiment/edge-history-adaptive-validation','EdgeValidatedRGBFeedback','EdgeValidatedRGBFeedback','ABL-ET2X-R-PreviousRawEdge-ValidatedRGB','적응형 누적·검증'),
 (13,'experiment/edge-history-catmull-rom-reconstruction','EdgeCatmullRomRGBFeedback','EdgeCatmullRomRGBFeedback','ABL-ET2X-R-PreviousRawEdge-CatmullRomRGB','5-fetch history 재구성'),
 (14,'experiment/edge-history-fixed-weight-080','EdgeFixedWeightRGBFeedback','EdgeFixedWeightRGBFeedback',BASE,'고정 history weight 0.8'),
 (15,'experiment/edge-history-source-clipping','EdgeSourceTemporalComponent','EdgeSourceTemporalComponent',BASE+'-YCoCgVarianceClamp','소스 기반 history clipping'),
 (16,'experiment/edge-history-source-sampling','EdgeSourceTemporalComponent','EdgeSourceTemporalComponent',BASE+'-Recovered5Fetch','소스 기반 history sampling'),
 (17,'experiment/edge-history-source-color-blend','EdgeSourceTemporalComponent','EdgeSourceTemporalComponent',BASE+'-EncodedGamma2Blend','소스 기반 색 혼합'),
]

def git(*args):
 return subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),*args],cwd=ROOT)
def sha(b): return hashlib.sha256(b).hexdigest()
def matching_brace(s,start):
 depth=0; i=start
 while i<len(s):
  if s.startswith('//',i):
   j=s.find('\n',i); i=len(s) if j<0 else j;continue
  if s.startswith('/*',i): i=s.index('*/',i)+2;continue
  if s[i] in '\"\'':
   q=s[i];i+=1
   while i<len(s):
    if s[i]=='\\':i+=2;continue
    if s[i]==q:i+=1;break
    i+=1
   continue
  if s[i]=='{':depth+=1
  if s[i]=='}':
   depth-=1
   if depth==0:return i
  i+=1
 raise ValueError('Unbalanced brace')

def main():
 global BUILD,SOURCE_ROOT
 parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,default=SOURCE_ROOT);parser.add_argument('--record-root',type=Path,default=BUILD)
 args=parser.parse_args();BUILD=args.record_root.resolve();SOURCE_ROOT=args.source_root.resolve()
 workspace=Path('C:/Users/USER/Desktop/research/tmp').resolve()
 assert BUILD.is_relative_to(workspace) and SOURCE_ROOT.is_relative_to(workspace)
 BUILD.mkdir(parents=True,exist_ok=True); records=[]
 lib_tree=git('rev-parse','HEAD:Modules').decode().strip()
 for case,branch,harness,command,target,label in ITEMS:
  commit=git('rev-parse',branch).decode().strip();dest=SOURCE_ROOT/f'c{case:02d}'
  if (dest/'_Lib').exists(): raise RuntimeError('Refuse to overwrite configured/running source '+str(dest))
  module_tree=git('rev-parse',commit+':Modules').decode().strip()
  if module_tree!=lib_tree:
   changed=git('diff','--name-only','HEAD',commit,'--','Modules').decode().splitlines()
   assert set(changed)=={'Modules/Rendering/DirectX/vaShaderDX11.cpp','Modules/Rendering/vaShader.cpp','Modules/Rendering/vaShader.h'},changed
   # Historical 7/8/9 add noninteractive compiler-error reporting only.
  payload=git('archive','--format=zip',commit,'Modules','Projects/CMAA2','Projects/AllModules','Tools/SMAA/run_clean_cmaa2.ps1')
  with zipfile.ZipFile(io.BytesIO(payload)) as z:
   for member in z.infolist():
    if member.filename.startswith('Projects/CMAA2/Media/'):continue
    assert '..' not in Path(member.filename).parts
    z.extract(member,dest)
  if module_tree!=lib_tree:
   # Instance layouts and render code are identical. Supply only the three
   # newer static error-reporting symbols required by historical app code.
   shim=dest/'Projects/CMAA2/LegacyCompilerReporting.cpp'
   shim.write_text('#include "Core/vaCoreIncludes.h"\n#include "Rendering/vaShader.h"\nusing namespace VertexAsylum;\nstd::atomic_bool vaShader::s_nonInteractiveCompilation=false;\nstd::atomic_int vaShader::s_compilationFailures=0;\nbool vaShader::ReportNonInteractiveCompileFailure(const char* source,const char* entry,const char* error,const string& macros){if(!s_nonInteractiveCompilation.load())return false;s_compilationFailures++;VA_LOG_ERROR("NONINTERACTIVE_SHADER_COMPILE_FAILURE source=%s entry=%s\\n%s\\nMacros:\\n%s",source,entry,error,macros.c_str());return true;}\n',encoding='utf-8')
   proj=dest/'Projects/CMAA2/CMAA2.vcxproj';s=proj.read_text(encoding='utf-8-sig')
   s=s.replace('<ClCompile Include="CMAA2Sample.cpp" />','<ClCompile Include="CMAA2Sample.cpp" />\n    <ClCompile Include="LegacyCompilerReporting.cpp" />')
   proj.write_text(s,encoding='utf-8')
  (dest/'tmp').mkdir(exist_ok=True)
  f=dest/f'Projects/CMAA2/{harness}.inl';original=f.read_bytes();text=original.decode('utf-8-sig')
  assert '"'+target+'"' in text,(case,target,[x for x in re.findall(r'\{"([^"]+)"',text)])
  # Restrict scheduling only, after the original constructor populated its modes.
  ctor=re.search(r'BenchItem\w+\(CMAA2Sample& parent',text);assert ctor
  body=text.index('{',ctor.end());close=matching_brace(text,body)
  selector='\n        // Fresh all-case measurement: original target and original native control only.\n        m_modes.erase(std::remove_if(m_modes.begin(),m_modes.end(),[](const Mode& c){return std::string(c.name)!="'+target+'" && std::string(c.name)!="O-T2X-R";}),m_modes.end());\n'
  text=text[:close]+selector+text[close:]
  if 'bool TraceFrame() const' in text:
   start=text.index('{',text.index('bool TraceFrame() const'));end=matching_brace(text,start)
   text=text[:start]+'{ return false; /* RGB capture retained; no repeated diagnostic DDS */ }'+text[end+1:]
  text=text.replace('m_repeats=smoke?1:3','m_repeats=smoke?1:6')
  text=text.replace('4800 frames x 3','4800 frames x 6')
  f.write_text(text,encoding='utf-8')
  # Hash every production source and shader; verify archive against Git bytes.
  checks={}
  for p in (dest/'Projects/CMAA2/SMAA').rglob('*'):
   if p.is_file() and p.suffix in ('.cpp','.h','.hlsl','.hlsli'):
    rel=p.relative_to(dest).as_posix();checks[rel]=sha(p.read_bytes())
    assert p.read_bytes().replace(b'\r\n',b'\n')==git('show',commit+':'+rel).replace(b'\r\n',b'\n'),rel
  (dest/'Projects/CMAA2/ApplicationSettings.xml').write_bytes((ROOT/'Projects/CMAA2/ApplicationSettings.xml').read_bytes())
  row=dict(case=case,label=label,branch=branch,commit=commit,source=str(dest),harness=harness,
    command='-smaa'+command,target=target,native_control='O-T2X-R',production_sha256=checks,module_tree=module_tree,
    harness_original_sha256=sha(original),harness_measurement_sha256=sha(f.read_bytes()),
    modifications=['target/control scheduling only','RGB-only captures','6 paired repeats'],
    spatial=case not in (1,3,5),temporal=case not in (1,2),paired_sample_pattern=case in (3,4),
    reprojection='camera/depth only' if case not in (1,2) else 'None')
  records.append(row);print(json.dumps({k:row[k] for k in ('case','branch','commit','target')},ensure_ascii=False),flush=True)
 (BUILD/'manifest.json').write_text(json.dumps(dict(validation='PASS',source_root=str(SOURCE_ROOT),cases=records,reference='reused supersample spatial proxy, not temporal ground truth',frames=240,warmup=300,measurement_frames=4800,repeats=6),ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
